from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from typing import Any
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from routes.v1 import v1_router, legacy_router
from services.redis_service import RedisService

logger = logging.getLogger("app")


class FastAPILimiter:
    """FastAPILimiter compatibility wrapper for initializing distributed Redis rate limiter."""
    redis: Any = None
    identifier: Any = None
    http_callback: Any = None

    @classmethod
    async def init(
        cls,
        redis: Any,
        identifier: Any = None,
        http_callback: Any = None
    ) -> None:
        cls.redis = redis
        cls.identifier = identifier
        cls.http_callback = http_callback


async def custom_rate_limit_identifier(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


async def custom_http_callback(request: Request, response: Response, pexpire: int) -> None:
    expire_seconds = max(1, pexpire // 1000)
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_credentials=False,
    allow_headers=["*"]
)

app.include_router(v1_router)
app.include_router(legacy_router)


@app.get("/")
async def get_health() -> dict:
    return {
        "up": True,
        "datetime": datetime.now(timezone.utc).isoformat()
    }
