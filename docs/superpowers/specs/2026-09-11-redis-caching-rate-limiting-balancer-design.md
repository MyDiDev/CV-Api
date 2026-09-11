# Design Document: Redis Caching, Load Balancing & Strict Rate Limiting for CV-Api

- **Date:** 2026-09-11
- **Status:** Approved
- **Target Release:** 1.1.0

---

## 1. Overview & Problem Statement

**CV-Api** provides AI-powered resume evaluation, PDF report generation, and tailored profile quiz generation using Google Gemini 2.5 Flash. As usage scales:
1. Identical or repeated CV evaluations and quizzes hit the Gemini API repeatedly, wasting tokens and incurring unnecessary latency and cost.
2. Uncontrolled burst traffic can exhaust Gemini rate limits (429 errors) and trigger `ServiceUnavailable` exceptions.
3. Every authenticated request queries PostgreSQL to validate the API key.
4. `fastapi-limiter` lacks central Redis initialization, leaving endpoints unprotected in multi-worker or production deployments.

This design introduces a **Redis-backed caching layer**, **Gemini API multi-key load balancing and concurrency control**, and **strict Redis-backed rate limiting with graceful fallback**.

---

## 2. Architecture & Component Design

```
                     +---------------------------------------+
                     |            Client Request             |
                     +---------------------------------------+
                                         │
                                         ▼
                     +---------------------------------------+
                     |         FastAPI App (Lifespan)        |
                     |  - Redis-backed FastAPILimiter        |
                     |  - Custom Key/IP Rate Limiting        |
                     +---------------------------------------+
                                         │
                    ┌────────────────────┴────────────────────┐
                    ▼                                         ▼
        +─────────────────────────+              +─────────────────────────+
        |   Auth / User Routes    |              |    Curriculum Routes    |
        +─────────────────────────+              +─────────────────────────+
                    │                                         │
                    ▼                                         ▼
        +─────────────────────────+              +─────────────────────────+
        |   API Key Validation    |              |   AI Request Caching    |
        | (5 min TTL in Redis)    |              |  - CV evaluation cache  |
        +─────────────────────────+              |  - Quiz cache (24h TTL) |
                    │                            +─────────────────────────+
                    │                                         │ (Cache Miss)
                    │                                         ▼
                    │                            +─────────────────────────+
                    │                            |   Gemini Load Balancer  |
                    │                            |  - Multi-Key Rotation   |
                    │                            |  - Concurrency Gate     |
                    │                            |    (Semaphore max=5)    |
                    │                            +─────────────────────────+
                    │                                         │
                    ▼                                         ▼
        +─────────────────────────+              +─────────────────────────+
        |   PostgreSQL Database   |              |    Google Gemini API    |
        +─────────────────────────+              +─────────────────────────+
```

---

## 3. Detailed Components & Modules

### 3.1 Redis Connection Service (`src/services/redis_service.py`)
- **Async Client**: Utilizes `redis.asyncio` with connection pooling.
- **Configuration**:
  - `REDIS_URL` from `.env` (default: `redis://localhost:6379/0`).
- **Resilience & Fallback**:
  - Every Redis operation is wrapped in a try/except block.
  - If Redis is offline or drops, it logs a warning and returns `None` / passes through without raising HTTP 500 errors to the client.
- **Methods**:
  - `get_json(key: str) -> dict | list | None`
  - `set_json(key: str, value: Any, ttl: int = 3600) -> bool`
  - `delete(key: str) -> bool`
  - `exists(key: str) -> bool`
  - `get_raw_client() -> redis.asyncio.Redis`

### 3.2 Caching Strategy & Implementation

#### A. AI Evaluation & Quiz Caching (`src/model/model.py`)
- **CV Evaluation**:
  - Hash Key: `cache:ai:cv:{SHA256(cv_content)}`
  - Cache TTL: `AI_CACHE_TTL` (default 86,400s / 24h).
  - Behavior:
    1. Compute SHA256 of `content`.
    2. Check Redis for `cache:ai:cv:{hash}`.
    3. If cache hit: return cached evaluation JSON and Cloudinary document URL immediately (skipping Gemini invocation and PDF re-generation, logging zero tokens).
    4. If cache miss: acquire Gemini slot via load balancer, invoke Gemini, generate PDF, store result in Redis, and return response.
- **Quiz Generation**:
  - Hash Key: `cache:ai:quiz:{SHA256(candidate_data + "::" + requirements)}`
  - Cache TTL: `AI_CACHE_TTL` (default 86,400s / 24h).
  - Behavior:
    1. Compute SHA256 of candidate info + company requirements.
    2. If cache hit: return cached quiz JSON immediately.
    3. If cache miss: invoke Gemini, cache in Redis, and return.

#### B. API Key & DB Cache (`src/repository/api_key_repository.py`)
- Hash Key: `cache:apikey:{SHA256(api_key_token)}`
- Cache TTL: `API_KEY_CACHE_TTL` (default 300s / 5m).
- Behavior:
  - Cache valid API key metadata so frequent requests avoid repetitive SQL queries against PostgreSQL.
  - Invalidate cache entry when an API key is deleted or modified.

### 3.3 Gemini API Load Balancer & Concurrency Control (`src/services/gemini_balancer.py`)
- **Multi-Key Round-Robin**:
  - Parses comma-separated `GEMINI_API_KEYS` or falls back to `API_KEY`.
  - Maintains `genai.Client` instances in an active pool.
  - Rotates client selection using an atomic index counter.
  - Temporary 429 Quota Backoff: If a client encounters a quota limit, marks it temporarily suspended for a cooldown period (e.g. 60s) and attempts the next client before raising an error.
- **Concurrency Limiting (Model Overload Protection)**:
  - Manages an `asyncio.Semaphore(MAX_CONCURRENT_GEMINI_REQUESTS)` (default: 5).
  - Wraps all `generate_content` and `count_tokens` calls in the semaphore context.
  - Prevents request bursts from overwhelming Google API quotas and crashing workers.

### 3.4 Rate Limiting & Lifecycle (`src/app.py` & `src/routes/curriculum.py`)
- **FastAPI Lifespan**:
  - Connects to Redis on startup.
  - Initializes `FastAPILimiter.init(redis_client, identifier=custom_rate_limit_identifier)`.
  - `custom_rate_limit_identifier` uses `Authorization` header token if present, falling back to client IP for unauthenticated routes.
- **Endpoint Limits**:
  - `POST /api/curriculum`: **10 requests / 10 minutes** per API Key.
  - `POST /api/curriculum/quiz`: **5 requests / 5 minutes** per API Key.
  - `GET /api/curriculum/documents`: **10 requests / 5 minutes** per API Key.
  - `POST /api/login`, `POST /api/register`, `POST /api/key`: **5 requests / minute** per IP.

---

## 4. Error Handling & Edge Cases

1. **Redis Unavailable at Startup / Runtime**:
   - `redis_service` handles `ConnectionError` gracefully; caching becomes a no-op pass-through.
   - `FastAPILimiter` is conditionally initialized only if Redis connection succeeds; if down, endpoints continue serving traffic with warning logs.
2. **All Gemini API Keys Exhausted / 429**:
   - Return clean `503 Service Unavailable` with message `"All Gemini model instances are currently busy or rate-limited. Please retry in a few moments."`
3. **Cache Invalidation / Corrupted Cache**:
   - JSON decode errors on cached values automatically trigger cache eviction and fallback to live generation.

---

## 5. Verification & Testing Plan

1. **Redis Connection & Fallback Tests**:
   - Verify operations succeed when Redis is online.
   - Verify graceful degradation when Redis is stopped or unreachable.
2. **AI Caching Verification**:
   - Call `/api/curriculum` twice with identical content; verify the second call responds in <50ms with 0 additional Gemini tokens.
   - Call `/api/curriculum/quiz` with same inputs; verify cached response match.
3. **Load Balancer & Concurrency Tests**:
   - Configure multiple dummy keys and verify round-robin client distribution.
   - Fire concurrent calls exceeding `MAX_CONCURRENT_GEMINI_REQUESTS` and verify semaphore throttling without dropping connections.
4. **Rate Limiting Tests**:
   - Verify HTTP 429 status code when exceeding configured rate limits on curriculum and auth endpoints.
