import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from fastapi import Request
from app import app, lifespan
from services.rate_limiter import FastAPILimiter, default_identifier, default_http_callback, RateLimiter
from services.redis_service import RedisService
from pyrate_limiter import Limiter, Rate, Duration


@pytest.mark.asyncio
async def test_health_check_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["up"] is True
        assert "datetime" in data


@pytest.mark.asyncio
async def test_custom_rate_limit_identifier_bearer():
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/curriculum/documents",
        "headers": [(b"authorization", b"Bearer sample-api-key-12345")],
    }
    request = Request(scope)
    identifier = await default_identifier(request)
    assert identifier == "sample-api-key-12345"


@pytest.mark.asyncio
async def test_custom_rate_limit_identifier_forwarded_for():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/login",
        "headers": [(b"x-forwarded-for", b"203.0.113.195, 70.41.3.18")],
    }
    request = Request(scope)
    identifier = await default_identifier(request)
    assert identifier == "203.0.113.195"


@pytest.mark.asyncio
async def test_custom_rate_limit_identifier_client_host():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/register",
        "headers": [],
        "client": ("192.168.1.50", 12345),
    }
    request = Request(scope)
    identifier = await default_identifier(request)
    assert identifier == "192.168.1.50"


@pytest.mark.asyncio
async def test_custom_rate_limit_identifier_fallback():
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/register",
        "headers": [],
        "client": None,
    }
    request = Request(scope)
    identifier = await default_identifier(request)
    assert identifier == "127.0.0.1"


@pytest.mark.asyncio
async def test_custom_http_callback():
    from fastapi.exceptions import HTTPException
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/api/curriculum",
        "headers": [],
    }
    request = Request(scope)
    
    with pytest.raises(HTTPException) as exc_info:
        await default_http_callback(request, None, pexpire=5000)
    
    assert exc_info.value.status_code == 429
    assert "Too Many Requests. Rate limit exceeded. Retry in 5 seconds." in exc_info.value.detail


@pytest.mark.asyncio
async def test_fastapi_limiter_init_and_lifespan():
    mock_redis = AsyncMock()
    
    with patch.object(RedisService, "get_raw_client", return_value=mock_redis), \
         patch.object(RedisService, "close", new_callable=AsyncMock) as mock_close, \
         patch.object(FastAPILimiter, "init", new_callable=AsyncMock) as mock_limiter_init:
        
        async with lifespan(app):
            mock_limiter_init.assert_awaited_once_with(
                mock_redis,
                identifier=default_identifier,
                http_callback=default_http_callback
            )
            mock_close.assert_not_awaited()
        
        mock_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_handles_redis_init_failure_gracefully():
    mock_redis = AsyncMock()
    
    with patch.object(RedisService, "get_raw_client", return_value=mock_redis), \
         patch.object(RedisService, "close", new_callable=AsyncMock) as mock_close, \
         patch.object(FastAPILimiter, "init", side_effect=Exception("Redis connection error")):
        
        async with lifespan(app):
            pass
        
        mock_close.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_when_redis_client_none():
    with patch.object(RedisService, "get_raw_client", return_value=None), \
         patch.object(RedisService, "close", new_callable=AsyncMock) as mock_close, \
         patch.object(FastAPILimiter, "init", new_callable=AsyncMock) as mock_limiter_init:
        
        async with lifespan(app):
            mock_limiter_init.assert_not_awaited()
        
        mock_close.assert_awaited_once()
