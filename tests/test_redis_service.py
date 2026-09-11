import pytest
from unittest.mock import AsyncMock, patch, MagicMock
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
