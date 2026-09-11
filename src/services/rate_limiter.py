from typing import Callable, Any
from fastapi import Request, Response
from fastapi.exceptions import HTTPException
from pyrate_limiter import Limiter, Rate, Duration
import logging

logger = logging.getLogger("rate_limiter")


async def default_identifier(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


async def default_http_callback(request: Request, response: Response, pexpire: int = 1000) -> None:
    expire_seconds = max(1, pexpire // 1000)
    raise HTTPException(
        status_code=429,
        detail=f"Too Many Requests. Rate limit exceeded. Retry in {expire_seconds} seconds."
    )


class FastAPILimiter:
    redis: Any = None
    identifier: Callable = default_identifier
    http_callback: Callable = default_http_callback

    @classmethod
    async def init(
        cls,
        redis: Any,
        identifier: Callable = default_identifier,
        http_callback: Callable = default_http_callback
    ) -> None:
        cls.redis = redis
        cls.identifier = identifier
        cls.http_callback = http_callback


class RateLimiter:
    def __init__(
        self,
        limiter: Limiter,
        identifier: Callable | None = None,
        callback: Callable | None = None,
        blocking: bool = False,
    ):
        self.limiter = limiter
        self.identifier = identifier
        self.callback = callback
        self.blocking = blocking

    async def __call__(self, request: Request, response: Response) -> Any:
        identifier_func = self.identifier or FastAPILimiter.identifier or default_identifier
        callback_func = self.callback or FastAPILimiter.http_callback or default_http_callback

        path = request.scope.get("path", "")
        method = request.method
        try:
            rate_key = await identifier_func(request)
        except Exception:
            rate_key = "127.0.0.1"
        key = f"{rate_key}:{method}:{path}"

        try:
            if self.limiter:
                success = await self.limiter.try_acquire_async(key, blocking=self.blocking)
                if not success:
                    return await callback_func(request, response, 1000)
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"Rate limiter exception for key '{key}': {e}")
