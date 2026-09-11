# CV-Api - Agent Context and Documentation

## Purpose of the Project
**CV-Api** is a high-performance REST API built with FastAPI (Python) designed to process and evaluate Curriculums Vitae (Resumes) using Google's **Gemini 2.5 Flash** AI model. The main goals of the API are:
1. **CV Evaluation:** Analyze a candidate's CV and generate a detailed report (scored by sections) on how well it is structured and its quality.
2. **Report Generation:** Convert the AI evaluation into a Markdown document, which is then rendered as a PDF, uploaded to **Cloudinary** (CDN), and returned to the user via a URL.
3. **Professional Profile Quizzes:** Generate adaptive quizzes specifically tailored to a candidate's profile and, optionally, a company's requirements.
4. **User & Usage Management:** Implement authentication via JWT and an API Key system to track the usage of each user (number of tokens consumed, response time) using a PostgreSQL database.
5. **Caching & Resiliency:** Utilize **Redis** caching for AI responses and API Key validation, a **multi-key Gemini load balancer** with round-robin rotation and automatic failover, concurrency gating via semaphores, and distributed rate limiting.

## Agent Context
When working on this project, agents must keep the following in mind:
- **FastAPI & Python 3.10+**: All endpoints and asynchronous logic are built with modern Python.
- **PostgreSQL**: Used for persistence, utilizing raw SQL via `psycopg` context managers rather than an ORM.
- **Redis Caching (`src/services/redis_service.py`)**:
  - CV evaluations are cached by content SHA256 (`cv_eval:{sha256}`) with TTL 24h (`AI_CACHE_TTL`).
  - Quizzes are cached by content + requirements SHA256 (`quiz:{sha256}`) with TTL 24h (`AI_CACHE_TTL`).
  - API Key validations are cached (`api_key:{key_hash}`) with TTL 5m (`API_KEY_CACHE_TTL`) and invalidated on key removal.
  - All Redis operations fail gracefully: if Redis is unreachable, the system transparently falls back to direct database/Gemini execution.
- **Gemini Load Balancer & Concurrency Control (`src/services/gemini_balancer.py`)**:
  - Supports comma-separated API keys in `GEMINI_API_KEYS` with fallback to `API_KEY`.
  - Rotates clients using round-robin and catches exceptions to automatically retry with the next available key.
  - Concurrency is throttled via an `asyncio.Semaphore` controlled by `MAX_CONCURRENT_GEMINI_REQUESTS` (default 5).
- **Data Transfer Objects (DTOs)**: Used extensively for request validation and parsing (powered by Pydantic in `src/dto/`).
- **Prompt Engineering**: The core AI logic relies on two markdown system prompts (`role.md` and `quiz_role.md`). Any changes to the AI output structure must be reflected in these files.
- **Distributed Rate Limiting**: Managed in `src/app.py` via `fastapi-limiter` backed by Redis. Custom identifier resolves Bearer API Key, JWT, `X-Forwarded-For`, or client IP. Returns HTTP 429 with retry delay.

## API Flow
1. **Authentication:** A user registers (`POST /api/register`) and logs in (`POST /api/login`) to obtain a JWT.
2. **API Key Generation:** The user generates an API Key (`POST /api/create/key` or `/api/key`) which acts as the credential for core functionalities.
3. **Core Services:** The user makes requests to `/api/curriculum` and `/api/curriculum/quiz` using the API Key in the `Authorization: Bearer <key>` header.
4. **Key Validation & Rate Limiting:** `ApiKeyRepository.validate_api_key()` checks Redis first, falling back to PostgreSQL and caching the result for 5 minutes. `FastAPILimiter` enforces rate limits per endpoint.
5. **AI Processing & Caching:**
   - `model.py` checks Redis for cached evaluations or quizzes.
   - If a cache miss occurs, `GeminiBalancer` handles token counting and content generation with concurrency throttling and multi-key failover.
   - Results are stored in Redis (TTL 24h) and returned to the caller.
6. **Logging:** Every non-cached AI usage is logged via `LogRepository` into the `apilogusage` PostgreSQL table to track token usage and performance.
7. **File Storage:** PDF reports are rendered via `markdown-pdf`, uploaded to Cloudinary via `cdn.py`, and recorded in the `documents` table.

## Directory and File Structure

### Root Directory
- `README.md`: Human-readable documentation, technology stack, architecture, and API endpoints.
- `role.md`: System prompt instructing Gemini on how to evaluate CVs and output the strict JSON schema required by the API.
- `quiz_role.md`: System prompt instructing Gemini on how to generate adaptive quizzes, considering both candidate context and company requirements.
- `requirements.txt`: Python dependencies list.
- `.env.example`: Template with required environment variables.

### `tests/` (Test Suite)
- `test_caching.py`: Tests for Redis caching across CV evaluation, quiz generation, API key validation, and cache invalidation.
- `test_gemini_balancer.py`: Tests for multi-key round-robin rotation, fallback, concurrency limiting, and error retries.
- `test_rate_limiter.py`: Tests for custom rate limit identifier, HTTP 429 callback, health check, and lifespan lifecycle.
- `test_redis_service.py`: Tests for RedisService CRUD, TTL, and graceful error fallback.

### `src/` (Source Code)
- `app.py`: Entry point for the FastAPI application. Sets up CORS, lifespan Redis initialization, custom rate limit identifier, HTTP 429 callback, and registers routers.

#### `src/routes/` (Controllers/Endpoints)
This layer defines HTTP endpoints, dependencies, and rate limit rules.
- `__init__.py` & `v1.py`: Router aggregators for v1 and legacy paths.
- `auth.py`: User registration (`POST /api/register`, 5 req/min) and login (`POST /api/login`, 10 req/min).
- `curriculum.py`: Core endpoints for CV evaluation (`POST /api/curriculum`, 10 req/10min), Quiz generation (`POST /api/curriculum/quiz`, 5 req/5min), and document retrieval (`GET /api/curriculum/documents`, 10 req/5min).
- `user.py`: Endpoints for API Keys (`POST /api/key`, `POST /api/create/key`, 5 req/min) and usage dashboard (`GET /api/dashboard`, 20 req/min).

#### `src/model/` (Business Logic / AI)
- `model.py`: Core business logic that handles interactions with the Gemini 2.5 Flash model via `gemini_balancer`. Handles SHA256-based Redis caching, token counting, markdown-to-PDF conversion, and Cloudinary upload.

#### `src/data/` (Database Connection)
- `db.py`: Provides the database connection logic using `psycopg` context managers (`get_db()`).

#### `src/repository/` (Data Access Layer)
This layer acts as the bridge between the database (`db.py`), Redis caching, and the rest of the app:
- `api_key_repository.py`: CRUD operations for API Keys with Redis caching (`api_key:{key_hash}`) and invalidation.
- `document_repository.py`: Storing and retrieving URLs for generated PDF documents.
- `log_repository.py`: Tracking API usage, tokens consumed, and response times (`apilogusage` table).
- `user_repository.py`: CRUD operations for user accounts (registration, authentication checks).

#### `src/dto/` (Data Transfer Objects)
Pydantic models used for strict request/response validation:
- `cv.py`: Schemas related to Curriculum evaluation requests and responses.
- `logs.py`: Schemas for dashboard and usage logs.
- `user.py`: Schemas for User registration, authentication, and API Key responses.

#### `src/services/` (External Services & Infrastructure)
- `redis_service.py`: Async Redis client wrapper providing `get_json`, `set_json`, `delete`, `exists`, and `close` with automatic error handling.
- `gemini_balancer.py`: Multi-key load balancer and `asyncio.Semaphore` concurrency limiter for Google GenAI calls with automatic retry.
- `cdn.py`: Handles file uploads to the Cloudinary CDN.
- `tokenizer.py`: Handles JWT generation, encoding, decoding, and password hashing (`pwdlib`).

---
*Note for Agents: When modifying AI output schemas, always keep the Pydantic models in `src/dto/`, the prompt definitions in `*.md` files, and the parsing & caching logic in `src/model/model.py` strictly in sync.*
