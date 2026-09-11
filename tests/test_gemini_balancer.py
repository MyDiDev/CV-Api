import pytest
import asyncio
from unittest.mock import MagicMock, patch
from services.gemini_balancer import GeminiBalancer


@pytest.mark.asyncio
async def test_balancer_round_robin_rotation():
    with patch.dict("os.environ", {"GEMINI_API_KEYS": "key1,key2,key3", "MAX_CONCURRENT_GEMINI_REQUESTS": "2"}):
        balancer = GeminiBalancer()
        assert len(balancer.clients) == 3
        assert balancer.api_keys == ["key1", "key2", "key3"]

        client_1 = balancer.get_next_client()
        client_2 = balancer.get_next_client()
        client_3 = balancer.get_next_client()
        client_4 = balancer.get_next_client()

        assert client_1 != client_2
        assert client_2 != client_3
        assert client_1 == client_4
        assert balancer.get_client() == client_2


@pytest.mark.asyncio
async def test_balancer_single_key_fallback():
    with patch.dict("os.environ", {"GEMINI_API_KEYS": "", "API_KEY": "fallback_key_123"}, clear=True):
        balancer = GeminiBalancer()
        assert len(balancer.clients) == 1
        assert balancer.api_keys == ["fallback_key_123"]
        client = balancer.get_next_client()
        assert client is not None


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
        assert balancer.concurrency_limit == balancer.semaphore


@pytest.mark.asyncio
async def test_balancer_generate_content_success_and_retry():
    with patch.dict("os.environ", {"GEMINI_API_KEYS": "key1,key2"}):
        balancer = GeminiBalancer()

        mock_client_fail = MagicMock()
        mock_client_fail.models.generate_content.side_effect = Exception("Quota exceeded")

        mock_client_ok = MagicMock()
        mock_response = MagicMock(text='{"result": "success"}')
        mock_client_ok.models.generate_content.return_value = mock_response

        balancer.clients = [mock_client_fail, mock_client_ok]

        res = await balancer.generate_content("gemini-2.5-flash", {"text": "hello"}, {})
        assert res == mock_response
        assert mock_client_fail.models.generate_content.called
        assert mock_client_ok.models.generate_content.called


@pytest.mark.asyncio
async def test_balancer_generate_content_all_fail():
    with patch.dict("os.environ", {"GEMINI_API_KEYS": "key1,key2"}):
        balancer = GeminiBalancer()

        mock_client_1 = MagicMock()
        mock_client_1.models.generate_content.side_effect = Exception("Error 1")

        mock_client_2 = MagicMock()
        mock_client_2.models.generate_content.side_effect = Exception("Error 2")

        balancer.clients = [mock_client_1, mock_client_2]

        with pytest.raises(Exception, match="Error 2"):
            await balancer.generate_content("gemini-2.5-flash", {"text": "hello"}, {})


@pytest.mark.asyncio
async def test_balancer_count_tokens_success_and_retry():
    with patch.dict("os.environ", {"GEMINI_API_KEYS": "key1,key2"}):
        balancer = GeminiBalancer()

        mock_client_fail = MagicMock()
        mock_client_fail.models.count_tokens.side_effect = Exception("Token error")

        mock_client_ok = MagicMock()
        mock_tokens = MagicMock(total_tokens=42)
        mock_client_ok.models.count_tokens.return_value = mock_tokens

        balancer.clients = [mock_client_fail, mock_client_ok]

        res = await balancer.count_tokens("gemini-2.5-flash", {"text": "hello"})
        assert res.total_tokens == 42


@pytest.mark.asyncio
async def test_balancer_count_tokens_all_fail():
    with patch.dict("os.environ", {"GEMINI_API_KEYS": "key1,key2"}):
        balancer = GeminiBalancer()

        mock_client_1 = MagicMock()
        mock_client_1.models.count_tokens.side_effect = Exception("Token error 1")

        mock_client_2 = MagicMock()
        mock_client_2.models.count_tokens.side_effect = Exception("Token error 2")

        balancer.clients = [mock_client_1, mock_client_2]

        with pytest.raises(Exception, match="Token error 2"):
            await balancer.count_tokens("gemini-2.5-flash", {"text": "hello"})
