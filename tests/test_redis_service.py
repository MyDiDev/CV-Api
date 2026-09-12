import pytest
from datetime import datetime, date, timezone
from decimal import Decimal
from uuid import UUID
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
async def test_redis_service_datetime_and_complex_types_serialization():
    mock_redis = AsyncMock()
    mock_redis.set.return_value = True

    now = datetime(2026, 9, 11, 20, 50, 0, tzinfo=timezone.utc)
    today = date(2026, 9, 11)
    test_uuid = UUID("12345678-1234-5678-1234-567812345678")
    test_decimal = Decimal("45.99")

    complex_data = {
        "api_key": (1, "hash_value", 10, now, today),
        "id": test_uuid,
        "price": test_decimal,
    }

    with patch.object(RedisService, "get_raw_client", return_value=mock_redis):
        res_set = await RedisService.set_json("complex_key", complex_data, ttl=300)
        assert res_set is True
        mock_redis.set.assert_awaited_once()
        saved_payload = mock_redis.set.call_args[0][1]
        assert "2026-09-11T20:50:00+00:00" in saved_payload
        assert "2026-09-11" in saved_payload
        assert "12345678-1234-5678-1234-567812345678" in saved_payload
        assert "45.99" in saved_payload


@pytest.mark.asyncio
async def test_redis_service_delete_and_exists():
    mock_redis = AsyncMock()
    mock_redis.delete.return_value = 1
    mock_redis.exists.return_value = 1

    with patch.object(RedisService, "get_raw_client", return_value=mock_redis):
        # Test exists
        exists = await RedisService.exists("test_key")
        assert exists is True
        mock_redis.exists.assert_awaited_once_with("test_key")

        # Test delete
        deleted = await RedisService.delete("test_key")
        assert deleted is True
        mock_redis.delete.assert_awaited_once_with("test_key")


@pytest.mark.asyncio
async def test_redis_service_graceful_fallback_on_error():
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = Exception("Redis connection failed")
    mock_redis.set.side_effect = Exception("Redis connection failed")
    mock_redis.delete.side_effect = Exception("Redis connection failed")
    mock_redis.exists.side_effect = Exception("Redis connection failed")

    with patch.object(RedisService, "get_raw_client", return_value=mock_redis):
        res_get = await RedisService.get_json("test_key")
        assert res_get is None

        res_set = await RedisService.set_json("test_key", {"foo": "bar"})
        assert res_set is False

        res_delete = await RedisService.delete("test_key")
        assert res_delete is False

        res_exists = await RedisService.exists("test_key")
        assert res_exists is False


@pytest.mark.asyncio
async def test_redis_service_when_client_is_none():
    with patch.object(RedisService, "get_raw_client", return_value=None):
        res_get = await RedisService.get_json("test_key")
        assert res_get is None

        res_set = await RedisService.set_json("test_key", {"foo": "bar"})
        assert res_set is False

        res_delete = await RedisService.delete("test_key")
        assert res_delete is False

        res_exists = await RedisService.exists("test_key")
        assert res_exists is False


@pytest.mark.asyncio
async def test_redis_service_close():
    mock_redis = AsyncMock()
    RedisService._client = mock_redis
    await RedisService.close()
    mock_redis.aclose.assert_awaited_once()
    assert RedisService._client is None
