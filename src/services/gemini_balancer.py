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

    @property
    def concurrency_limit(self) -> asyncio.Semaphore:
        return self.semaphore

    def get_next_client(self) -> genai.Client:
        if not self.clients:
            return genai.Client(api_key=os.getenv("API_KEY"))
        client = self.clients[self._index % len(self.clients)]
        self._index += 1
        return client

    def get_client(self) -> genai.Client:
        return self.get_next_client()

    async def generate_content(
        self,
        model: str,
        contents: Any,
        config: dict[str, Any] | None = None
    ) -> Any:
        async with self.semaphore:
            attempts = max(1, len(self.clients))
            last_err: Exception | None = None
            for _ in range(attempts):
                client = self.get_next_client()
                try:
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
            attempts = max(1, len(self.clients))
            last_err: Exception | None = None
            for _ in range(attempts):
                client = self.get_next_client()
                try:
                    loop = asyncio.get_running_loop()
                    return await loop.run_in_executor(
                        None,
                        lambda c=client: c.models.count_tokens(model=model, contents=contents)
                    )
                except Exception as ex:
                    last_err = ex
                    logger.warning(f"Gemini count_tokens error: {ex}. Retrying next available client...")
            raise last_err or Exception("All Gemini clients failed during count_tokens")


gemini_balancer = GeminiBalancer()
