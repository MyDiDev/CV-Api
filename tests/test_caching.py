import pytest
import hashlib
from unittest.mock import AsyncMock, patch, MagicMock
from dto.user import APIKey
from model.model import evaluate_cv_document, generate_quiz
from repository.api_key_repository import ApiKeyRepository


@pytest.mark.asyncio
async def test_evaluate_cv_document_cache_hit():
    sample_cv = "Experienced Software Engineer with Python and FastAPI skills."
    content_hash = hashlib.sha256(sample_cv.encode("utf-8")).hexdigest()
    expected_cache_key = f"cache:ai:cv:{content_hash}"
    cached_payload = {
        "analysis": "Great CV",
        "score": 95,
        "document": "https://res.cloudinary.com/demo/cv_report.pdf"
    }

    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"analysis": "Great CV", "score": 95, "document": "https://res.cloudinary.com/demo/cv_report.pdf"}'

    with patch("services.redis_service.RedisService.get_raw_client", return_value=mock_redis), \
         patch("services.gemini_balancer.gemini_balancer.generate_content", new_callable=AsyncMock) as mock_generate, \
         patch("services.gemini_balancer.gemini_balancer.count_tokens", new_callable=AsyncMock) as mock_count, \
         patch("repository.log_repository.LogRepository.register_log", new_callable=AsyncMock, return_value={"log": [1]}) as mock_reg_log, \
         patch("repository.log_repository.LogRepository.update_log", new_callable=AsyncMock) as mock_upd_log:

        api_key = APIKey(id=1, key_hash="test_hash")
        result = await evaluate_cv_document(sample_cv, api_key)

        assert result == cached_payload
        mock_redis.get.assert_awaited_once_with(expected_cache_key)
        # Verify Gemini balancer was NOT called on cache hit
        mock_generate.assert_not_called()
        mock_count.assert_not_called()
        mock_reg_log.assert_awaited_once()
        mock_upd_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_evaluate_cv_document_cache_miss():
    sample_cv = "Junior Developer seeking new opportunities."
    content_hash = hashlib.sha256(sample_cv.encode("utf-8")).hexdigest()
    expected_cache_key = f"cache:ai:cv:{content_hash}"

    ai_response_json = '{"score": 80, "document": {"file_name": "report.pdf", "content": "# Report"}}'
    mock_response = MagicMock()
    mock_response.text = f"```json\n{ai_response_json}\n```"

    mock_tokens = MagicMock()
    mock_tokens.total_tokens = 150

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True

    with patch("services.redis_service.RedisService.get_raw_client", return_value=mock_redis), \
         patch("services.gemini_balancer.gemini_balancer.generate_content", new_callable=AsyncMock, return_value=mock_response) as mock_generate, \
         patch("services.gemini_balancer.gemini_balancer.count_tokens", new_callable=AsyncMock, return_value=mock_tokens) as mock_count, \
         patch("model.model.create_and_save_document", new_callable=AsyncMock, return_value="https://res.cloudinary.com/demo/saved.pdf") as mock_save_doc, \
         patch("repository.log_repository.LogRepository.register_log", new_callable=AsyncMock, return_value={"log": [1]}) as mock_reg_log, \
         patch("repository.log_repository.LogRepository.update_log", new_callable=AsyncMock) as mock_upd_log:

        api_key = APIKey(id=2, key_hash="test_hash")
        result = await evaluate_cv_document(sample_cv, api_key)

        assert result.get("score") == 80
        assert result.get("document") == "https://res.cloudinary.com/demo/saved.pdf"

        mock_redis.get.assert_awaited_once_with(expected_cache_key)
        mock_count.assert_awaited_once()
        mock_generate.assert_awaited_once()
        mock_save_doc.assert_awaited_once_with("report.pdf", "# Report", 2)
        mock_redis.set.assert_awaited_once()
        # Ensure it was cached with 24h (86400s) default TTL
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == expected_cache_key
        assert call_args[1]["ex"] == 86400
        mock_reg_log.assert_awaited_once()
        mock_upd_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_quiz_cache_hit():
    candidate_data = "Skills: Python, Redis, Postgres"
    requirements = "Senior Backend Engineer"
    prompt_hash = hashlib.sha256(f"{candidate_data}::{requirements}".encode("utf-8")).hexdigest()
    expected_cache_key = f"cache:ai:quiz:{prompt_hash}"

    cached_payload = {
        "questions": [
            {"question": "What is Redis?", "options": ["Cache", "Relational DB"], "answer": "Cache"}
        ]
    }

    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"questions": [{"question": "What is Redis?", "options": ["Cache", "Relational DB"], "answer": "Cache"}]}'

    with patch("services.redis_service.RedisService.get_raw_client", return_value=mock_redis), \
         patch("services.gemini_balancer.gemini_balancer.generate_content", new_callable=AsyncMock) as mock_generate, \
         patch("services.gemini_balancer.gemini_balancer.count_tokens", new_callable=AsyncMock) as mock_count, \
         patch("repository.log_repository.LogRepository.register_log", new_callable=AsyncMock, return_value={"log": [1]}) as mock_reg_log, \
         patch("repository.log_repository.LogRepository.update_log", new_callable=AsyncMock) as mock_upd_log:

        api_key = APIKey(id=1, key_hash="test_hash")
        result = await generate_quiz(candidate_data, api_key, requirements)

        assert result == cached_payload
        mock_redis.get.assert_awaited_once_with(expected_cache_key)
        mock_generate.assert_not_called()
        mock_count.assert_not_called()
        mock_reg_log.assert_awaited_once()
        mock_upd_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_quiz_cache_miss():
    candidate_data = "Skills: Docker, Kubernetes"
    requirements = "DevOps Engineer"
    prompt_hash = hashlib.sha256(f"{candidate_data}::{requirements}".encode("utf-8")).hexdigest()
    expected_cache_key = f"cache:ai:quiz:{prompt_hash}"

    ai_quiz_json = '{"questions": [{"question": "What is K8s?", "options": ["Orchestrator", "OS"], "answer": "Orchestrator"}]}'
    mock_response = MagicMock()
    mock_response.text = ai_quiz_json

    mock_tokens = MagicMock()
    mock_tokens.total_tokens = 90

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True

    with patch("services.redis_service.RedisService.get_raw_client", return_value=mock_redis), \
         patch("services.gemini_balancer.gemini_balancer.generate_content", new_callable=AsyncMock, return_value=mock_response) as mock_generate, \
         patch("services.gemini_balancer.gemini_balancer.count_tokens", new_callable=AsyncMock, return_value=mock_tokens) as mock_count, \
         patch("repository.log_repository.LogRepository.register_log", new_callable=AsyncMock, return_value={"log": [1]}) as mock_reg_log, \
         patch("repository.log_repository.LogRepository.update_log", new_callable=AsyncMock) as mock_upd_log:

        api_key = APIKey(id=3, key_hash="test_hash")
        result = await generate_quiz(candidate_data, api_key, requirements)

        assert "questions" in result
        mock_redis.get.assert_awaited_once_with(expected_cache_key)
        mock_count.assert_awaited_once()
        mock_generate.assert_awaited_once()
        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == expected_cache_key
        assert call_args[1]["ex"] == 86400
        mock_reg_log.assert_awaited_once()
        mock_upd_log.assert_awaited_once()


@pytest.mark.asyncio
async def test_validate_api_key_cache_hit():
    raw_key = "secret_api_key_123"
    token_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    expected_cache_key = f"cache:apikey:{token_hash}"

    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"api_key": [1, 42, "hashed_key", 0]}'

    with patch("services.redis_service.RedisService.get_raw_client", return_value=mock_redis), \
         patch("repository.api_key_repository.get_db") as mock_get_db:

        res = await ApiKeyRepository.validate_api_key(raw_key)
        assert res == {"api_key": [1, 42, "hashed_key", 0]}
        mock_redis.get.assert_awaited_once_with(expected_cache_key)
        # Database query must be bypassed on cache hit
        mock_get_db.assert_not_called()


@pytest.mark.asyncio
async def test_validate_api_key_cache_miss():
    raw_key = "new_secret_api_key_456"
    token_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    expected_cache_key = f"cache:apikey:{token_hash}"

    mock_redis = AsyncMock()
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [5, 10, "db_hash_val", 0]
    mock_conn = MagicMock()

    mock_db_context = MagicMock()
    mock_db_context.__enter__.return_value = (mock_conn, mock_cursor)
    mock_db_context.__exit__.return_value = None

    with patch("services.redis_service.RedisService.get_raw_client", return_value=mock_redis), \
         patch("repository.api_key_repository.get_db", return_value=mock_db_context):

        res = await ApiKeyRepository.validate_api_key(raw_key)
        assert res == {"api_key": [5, 10, "db_hash_val", 0]}
        mock_redis.get.assert_awaited_once_with(expected_cache_key)
        mock_cursor.execute.assert_called_once()
        mock_redis.set.assert_awaited_once()
        call_args = mock_redis.set.call_args
        assert call_args[0][0] == expected_cache_key
        assert call_args[1]["ex"] == 300


@pytest.mark.asyncio
async def test_remove_api_key_invalidates_cache():
    key = APIKey(owner_id=1, key_hash="sample_hash_to_delete")

    mock_redis = AsyncMock()
    mock_redis.delete.return_value = 1

    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_db_context = MagicMock()
    mock_db_context.__enter__.return_value = (mock_conn, mock_cursor)
    mock_db_context.__exit__.return_value = None

    with patch("services.redis_service.RedisService.get_raw_client", return_value=mock_redis), \
         patch("repository.api_key_repository.get_db", return_value=mock_db_context):

        res = await ApiKeyRepository.remove_api_key(key)
        assert res is True
        mock_cursor.execute.assert_called_once()
        # Verify cache invalidation deletes the cache key
        assert mock_redis.delete.call_count >= 1
