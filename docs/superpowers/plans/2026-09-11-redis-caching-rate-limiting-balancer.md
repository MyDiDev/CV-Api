# Redis Caching, Load Balancing & Strict Rate Limiting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Redis caching for AI outputs and API keys, load-balancing / concurrency management across Gemini API keys, and distributed strict rate limiting in CV-Api.

**Architecture:** 
- A resilient `redis_service.py` connects to Redis with connection pooling and graceful offline fallback.
- `gemini_balancer.py` manages a pool of Gemini API keys, rotating them round-robin and enforcing an async semaphore (`MAX_CONCURRENT_GEMINI_REQUESTS`) to prevent model overload.
- `model.py` and `api_key_repository.py` integrate SHA256-based response caching (24h TTL for AI outputs, 5m TTL for API key checks).
- `app.py` initializes `FastAPILimiter` via an async lifespan context with Redis, applying strict limits to curriculum and authentication routes.

**Tech Stack:** Python 3.10+, FastAPI, `redis.asyncio`, `fastapi-limiter`, `google-genai`, `pytest`, `pytest-asyncio`, `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-09-11-redis-caching-rate-limiting-balancer-design.md`

## Global Constraints
- Target Python 3.10+ compatibility.
- Graceful degradation: If Redis is offline or not configured, the API must not crash; operations should fallback to live execution.
- Preserve existing request/response schemas for `/api/curriculum`, `/api/curriculum/quiz`, and `/api/curriculum/documents`.
- All Redis keys must follow the standardized namespaces: `cache:ai:cv:{hash}`, `cache:ai:quiz:{hash}`, and `cache:apikey:{hash}`.

---

### Task 1: Redis Service & Resilience Layer

**Files:**
- Create: `src/services/redis_service.py`
- Modify: `requirements.txt`
- Test: `tests/test_redis_service.py`

**Interfaces:**
- Produces: 
  - `RedisService.get_json(key: str) -> dict | list | None`
  - `RedisService.set_json(key: str, value: Any, ttl: int = 3600) -> bool`
  - `RedisService.delete(key: str) -> bool`
  - `RedisService.exists(key: str) -> bool`
  - `RedisService.get_raw_client() -> redis.asyncio.Redis | None`
  - `RedisService.close() -> None`

- [ ] **Step 1: Write failing unit test for RedisService**

```python
# tests/test_redis_service.py
import pytest
from unittest.mock import AsyncMock, patch
from services.redis_service import RedisService

@pytest.mark.asyncio
async def test_redis_service_set_and_get_json():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"foo": "bar"}'
    mock_redis.set.return_value = True

    with patch.object(RedisService, "get_raw_client", return_value=mock_redis):
        # Test set
        res_set = await RedisService.set_json("test_key", {"foo": "bar"}, ttl=60)
        assert res_set is True
        mock_redis.set.assert_awaited_once_with("test_key", '{"foo": "bar"}', ex=60)

        # Test get
        res_get = await RedisService.get_json("test_key")
        assert res_get == {"foo": "bar"}
        mock_redis.get.assert_awaited_once_with("test_key")

@pytest.mark.asyncio
async def test_redis_service_graceful_fallback_on_error():
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = Exception("Redis connection failed")
    mock_redis.set.side_effect = Exception("Redis connection failed")

    with patch.object(RedisService, "get_raw_client", return_value=mock_redis):
        res_get = await RedisService.get_json("test_key")
        assert res_get is None

        res_set = await RedisService.set_json("test_key", {"foo": "bar"})
        assert res_set is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_redis_service.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'services.redis_service')

- [ ] **Step 3: Update requirements.txt and implement RedisService**

Add `redis>=5.0.0`, `pytest>=8.0.0`, `pytest-asyncio>=0.23.0` to `requirements.txt`.
Implement `src/services/redis_service.py`:

```python
import os
import json
import logging
from typing import Any
import redis.asyncio as aioredis
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("redis_service")

class RedisService:
    _client: aioredis.Redis | None = None

    @classmethod
    def get_raw_client(cls) -> aioredis.Redis | None:
        if cls._client is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            try:
                cls._client = aioredis.from_url(
                    redis_url, 
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
            except Exception as e:
                logger.warning(f"Failed to create Redis client: {e}")
                return None
        return cls._client

    @classmethod
    async def get_json(cls, key: str) -> dict | list | None:
        try:
            client = cls.get_raw_client()
            if client is None:
                return None
            data = await client.get(key)
            if data is None:
                return None
            return json.loads(data)
        except Exception as e:
            logger.warning(f"Redis get_json error for key '{key}': {e}")
            return None

    @classmethod
    async def set_json(cls, key: str, value: Any, ttl: int = 3600) -> bool:
        try:
            client = cls.get_raw_client()
            if client is None:
                return False
            payload = json.dumps(value)
            await client.set(key, payload, ex=ttl)
            return True
        except Exception as e:
            logger.warning(f"Redis set_json error for key '{key}': {e}")
            return False

    @classmethod
    async def delete(cls, key: str) -> bool:
        try:
            client = cls.get_raw_client()
            if client is None:
                return False
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning(f"Redis delete error for key '{key}': {e}")
            return False

    @classmethod
    async def exists(cls, key: str) -> bool:
        try:
            client = cls.get_raw_client()
            if client is None:
                return False
            res = await client.exists(key)
            return bool(res)
        except Exception as e:
            logger.warning(f"Redis exists error for key '{key}': {e}")
            return False

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            try:
                await cls._client.aclose()
            except Exception:
                pass
            cls._client = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_redis_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt src/services/redis_service.py tests/test_redis_service.py
git commit -m "feat: add redis service with connection pooling and graceful error handling"
```

---

### Task 2: Gemini Balancer & Concurrency Control

**Files:**
- Create: `src/services/gemini_balancer.py`
- Test: `tests/test_gemini_balancer.py`

**Interfaces:**
- Produces:
  - `GeminiBalancer.get_client() -> genai.Client`
  - `GeminiBalancer.generate_content(model: str, contents: Any, config: dict) -> Any`
  - `GeminiBalancer.count_tokens(model: str, contents: Any) -> Any`
  - `GeminiBalancer.concurrency_limit: asyncio.Semaphore`

- [ ] **Step 1: Write failing unit test for GeminiBalancer**

```python
# tests/test_gemini_balancer.py
import pytest
import asyncio
from unittest.mock import MagicMock, patch
from services.gemini_balancer import GeminiBalancer

@pytest.mark.asyncio
async def test_balancer_round_robin_rotation():
    with patch.dict("os.environ", {"GEMINI_API_KEYS": "key1,key2,key3", "MAX_CONCURRENT_GEMINI_REQUESTS": "2"}):
        balancer = GeminiBalancer()
        assert len(balancer.clients) == 3

        client_1 = balancer.get_next_client()
        client_2 = balancer.get_next_client()
        client_3 = balancer.get_next_client()
        client_4 = balancer.get_next_client()

        assert client_1 != client_2
        assert client_2 != client_3
        assert client_1 == client_4

@pytest.mark.asyncio
async def test_balancer_concurrency_gate():
    with patch.dict("os.environ", {"GEMINI_API_KEYS": "key1", "MAX_CONCURRENT_GEMINI_REQUESTS": "1"}):
        balancer = GeminiBalancer()
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = MagicMock(text='{"result": "ok"}')
        balancer.clients = [mock_client]

        active_count = 0
        max_active = 0

        async def simulated_call():
            nonlocal active_count, max_active
            async with balancer.semaphore:
                active_count += 1
                max_active = max(max_active, active_count)
                await asyncio.sleep(0.05)
                active_count -= 1

        await asyncio.gather(simulated_call(), simulated_call(), simulated_call())
        assert max_active == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_gemini_balancer.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'services.gemini_balancer')

- [ ] **Step 3: Implement GeminiBalancer**

Implement `src/services/gemini_balancer.py`:

```python
import os
import asyncio
import logging
from typing import Any
from google import genai
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("gemini_balancer")

class GeminiBalancer:
    def __init__(self) -> None:
        raw_keys = os.getenv("GEMINI_API_KEYS", "")
        fallback_key = os.getenv("API_KEY", "")
        
        keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        if not keys and fallback_key:
            keys = [fallback_key.strip()]
        
        self.api_keys = keys
        self.clients: list[genai.Client] = [genai.Client(api_key=k) for k in keys] if keys else []
        self._index = 0
        
        max_concurrency = int(os.getenv("MAX_CONCURRENT_GEMINI_REQUESTS", "5"))
        self.semaphore = asyncio.Semaphore(max_concurrency)

    def get_next_client(self) -> genai.Client:
        if not self.clients:
            # Fallback client if no keys were in environment
            return genai.Client(api_key=os.getenv("API_KEY"))
        client = self.clients[self._index % len(self.clients)]
        self._index += 1
        return client

    async def generate_content(self, model: str, contents: Any, config: dict[str, Any]) -> Any:
        async with self.semaphore:
            attempts = max(1, len(self.clients))
            last_err = None
            for _ in range(attempts):
                client = self.get_next_client()
                try:
                    # Run sync Google SDK generate_content in default executor thread
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(
                        None,
                        lambda c=client: c.models.generate_content(
                            model=model,
                            contents=contents,
                            config=config
                        )
                    )
                    return response
                except Exception as ex:
                    last_err = ex
                    logger.warning(f"Gemini client invocation error: {ex}. Retrying next available client...")
            raise last_err or Exception("All Gemini clients failed")

    async def count_tokens(self, model: str, contents: Any) -> Any:
        async with self.semaphore:
            client = self.get_next_client()
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(
                None,
                lambda: client.models.count_tokens(model=model, contents=contents)
            )

gemini_balancer = GeminiBalancer()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_gemini_balancer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/services/gemini_balancer.py tests/test_gemini_balancer.py
git commit -m "feat: add gemini multi-key load balancer and async concurrency gate"
```

---

### Task 3: AI Response & API Key Caching

**Files:**
- Modify: `src/model/model.py`
- Modify: `src/repository/api_key_repository.py`
- Test: `tests/test_caching.py`

**Interfaces:**
- Consumes:
  - `RedisService` (`get_json`, `set_json`)
  - `gemini_balancer` (`generate_content`, `count_tokens`)
- Produces:
  - Cached `evaluate_cv_document(content: str, api_key: APIKey)`
  - Cached `generate_quiz(data: str, api_key: APIKey, requirements: str)`
  - Cached `ApiKeyRepository.validate_api_key(key: str)`

- [ ] **Step 1: Write failing unit test for AI and API Key caching**

```python
# tests/test_caching.py
import pytest
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from dto.user import APIKey
from model.model import evaluate_cv_document, generate_quiz
from repository.api_key_repository import ApiKeyRepository
from services.redis_service import RedisService

@pytest.mark.asyncio
async def test_cv_evaluation_cache_hit():
    content = "Sample CV text for caching test"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    cache_key = f"cache:ai:cv:{content_hash}"
    cached_data = {
        "global_score": 90,
        "evaluation": {"structure_and_quality": {"score": 90, "comment": "Good"}},
        "suggestions": ["Add more details"],
        "document": "https://res.cloudinary.com/demo/image/upload/sample.pdf"
    }

    with patch.object(RedisService, "get_json", return_value=cached_data) as mock_get:
        res = await evaluate_cv_document(content, APIKey(id=1))
        assert res == cached_data
        mock_get.assert_awaited_once_with(cache_key)

@pytest.mark.asyncio
async def test_api_key_validation_caching():
    token = "test-secret-token"
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    cache_key = f"cache:apikey:{token_hash}"
    cached_key_info = {"api_key": (1, "hashed_val", 100, 50)}

    with patch.object(RedisService, "get_json", return_value=cached_key_info) as mock_get:
        res = await ApiKeyRepository.validate_api_key(token)
        assert res == cached_key_info
        mock_get.assert_awaited_once_with(cache_key)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_caching.py -v`
Expected: FAIL (Redis caching is not yet integrated in model.py and api_key_repository.py)

- [ ] **Step 3: Update `src/model/model.py` and `src/repository/api_key_repository.py`**

Update `src/model/model.py` to:
1. Hash input contents (`SHA256`).
2. Query `RedisService.get_json(cache_key)` before calling Gemini.
3. Use `gemini_balancer.generate_content` and `gemini_balancer.count_tokens` on cache miss.
4. Save resulting response in Redis via `RedisService.set_json(cache_key, data, ttl=AI_CACHE_TTL)`.

Update `src/repository/api_key_repository.py` to:
1. Check `RedisService.get_json(f"cache:apikey:{token_hash}")` in `validate_api_key`.
2. Cache DB lookup result with 300s TTL.
3. Invalidate/delete cache in `delete_api_key` or `update_api_key_rate_limit`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_caching.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/model/model.py src/repository/api_key_repository.py tests/test_caching.py
git commit -m "feat: implement redis caching for AI evaluations, quizzes, and api key lookups"
```

---

### Task 4: Redis-backed Rate Limiting & Lifespan Integration

**Files:**
- Modify: `src/app.py`
- Modify: `src/routes/curriculum.py`
- Modify: `src/routes/auth.py`
- Modify: `src/routes/user.py`
- Test: `tests/test_rate_limiter.py`

**Interfaces:**
- Consumes:
  - `RedisService.get_raw_client()`
  - `FastAPILimiter`
- Produces:
  - Lifespan initialized rate limiter in `app.py`
  - Strict endpoint limits with custom key identifier

- [ ] **Step 1: Write integration test for rate limiter setup & routes**

```python
# tests/test_rate_limiter.py
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app import app

@pytest.mark.asyncio
async def test_health_check_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
        assert response.status_code == 200
        assert response.json()["up"] is True
```

- [ ] **Step 2: Run test to verify initial status**

Run: `python3 -m pytest tests/test_rate_limiter.py -v`

- [ ] **Step 3: Update `src/app.py` with Lifespan & FastAPILimiter configuration**

Implement async lifespan in `src/app.py`:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
from routes.v1 import v1_router, legacy_router
from services.redis_service import RedisService
from datetime import datetime, timezone
import logging

logger = logging.getLogger("app")

async def custom_rate_limit_identifier(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"

async def custom_http_callback(request: Request, response: Response, pexpire: int):
    expire_seconds = max(1, pexpire // 1000)
    from fastapi.exceptions import HTTPException
    raise HTTPException(
        status_code=429, 
        detail=f"Too Many Requests. Rate limit exceeded. Retry in {expire_seconds} seconds."
    )

@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = RedisService.get_raw_client()
    if redis_client:
        try:
            await FastAPILimiter.init(
                redis_client,
                identifier=custom_rate_limit_identifier,
                http_callback=custom_http_callback
            )
            logger.info("FastAPILimiter initialized with Redis.")
        except Exception as e:
            logger.warning(f"Could not initialize FastAPILimiter: {e}")
    yield
    await RedisService.close()

app = FastAPI(title="CV-Api", version="1.1.0", lifespan=lifespan)
# ... middlewares & router inclusions
```

Update route rate limits in `src/routes/curriculum.py`, `src/routes/auth.py`, `src/routes/user.py`.

- [ ] **Step 4: Run all test suites to verify passing status**

Run: `python3 -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add src/app.py src/routes/curriculum.py src/routes/auth.py src/routes/user.py tests/test_rate_limiter.py
git commit -m "feat: configure redis-backed rate limiting via fastapi lifespan and strict route rules"
```

---

### Task 5: Documentation & Configuration Updates

**Files:**
- Create: `.env.example`
- Modify: `README.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Create `.env.example`**
Include `REDIS_URL`, `GEMINI_API_KEYS`, `MAX_CONCURRENT_GEMINI_REQUESTS`, `AI_CACHE_TTL`, `API_KEY_CACHE_TTL`.

- [ ] **Step 2: Update `README.md` and `AGENTS.md`**
Document Redis caching layer, Gemini load balancing, rate limiting changes, and new environment variables.

- [ ] **Step 3: Run complete verification**
Run: `python3 -m pytest tests/ -v`

- [ ] **Step 4: Commit**

```bash
git add .env.example README.md AGENTS.md
git commit -m "docs: update documentation and env variables for redis caching and gemini load balancer"
```
