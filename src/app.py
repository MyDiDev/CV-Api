from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.v1 import v1_router, legacy_router
from services.redis_service import RedisService
from services.rate_limiter import FastAPILimiter, default_identifier, default_http_callback

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_client = RedisService.get_raw_client()
    if redis_client:
        try:
            await FastAPILimiter.init(
                redis_client,
                identifier=default_identifier,
                http_callback=default_http_callback
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
