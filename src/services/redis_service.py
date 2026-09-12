import os
import json
import logging
from datetime import datetime, date, time
from decimal import Decimal
from uuid import UUID
from typing import Any
import redis.asyncio as aioredis
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
logger = logging.getLogger("redis_service")


def json_serializer(obj: Any) -> Any:
    """Fallback JSON serializer for datetimes, UUIDs, decimals, and complex objects."""
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, (bytes, memoryview)):
        return bytes(obj).decode("utf-8", errors="replace")
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        return obj.dict()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


class RedisService:
    _client: aioredis.Redis | None = None
    _loop: Any = None

    @classmethod
    def get_raw_client(cls) -> aioredis.Redis | None:
        try:
            import asyncio
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if cls._client is None or cls._loop != current_loop:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            try:
                cls._client = aioredis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2,
                )
                cls._loop = current_loop
                logger.info(f"[REDIS CONNECTED] Successfully connected to Redis at '{redis_url}'")
            except Exception as e:
                logger.warning(f"[REDIS OFFLINE] Failed to create Redis client: {e}")
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
                logger.info(f"[REDIS CACHE MISS] key='{key}'")
                return None
            logger.info(f"[REDIS CACHE HIT] key='{key}'")
            return json.loads(data)
        except Exception as e:
            logger.warning(f"[REDIS ERROR] get_json failed for key '{key}': {e}")
            return None

    @classmethod
    async def set_json(cls, key: str, value: Any, ttl: int = 3600) -> bool:
        try:
            client = cls.get_raw_client()
            if client is None:
                return False
            payload = json.dumps(value, default=json_serializer)
            await client.set(key, payload, ex=ttl)
            logger.info(f"[REDIS CACHE STORED] key='{key}' (TTL={ttl}s)")
            return True
        except Exception as e:
            logger.warning(f"[REDIS ERROR] set_json failed for key '{key}': {e}")
            return False

    @classmethod
    async def delete(cls, key: str) -> bool:
        try:
            client = cls.get_raw_client()
            if client is None:
                return False
            await client.delete(key)
            logger.info(f"[REDIS KEY DELETED] key='{key}'")
            return True
        except Exception as e:
            logger.warning(f"[REDIS ERROR] delete failed for key '{key}': {e}")
            return False

    @classmethod
    async def exists(cls, key: str) -> bool:
        try:
            client = cls.get_raw_client()
            if client is None:
                return False
            res = await client.exists(key)
            logger.info(f"[REDIS KEY EXISTS] key='{key}' exists={bool(res)}")
            return bool(res)
        except Exception as e:
            logger.warning(f"[REDIS ERROR] exists failed for key '{key}': {e}")
            return False

    @classmethod
    async def close(cls) -> None:
        if cls._client is not None:
            try:
                logger.info("[REDIS CLOSED] Closing Redis client connection pool")
                await cls._client.aclose()
            except Exception:
                pass
            cls._client = None
