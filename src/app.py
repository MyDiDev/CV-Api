from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.v1 import v1_router, legacy_router
from datetime import datetime, timezone

app = FastAPI(title="CV-Api", version="1.0.0")
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