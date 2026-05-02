from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.exceptions import HTTPException
from datetime import datetime
from routes.curriculum import curriculum_router
from routes.auth import auth_router

app = FastAPI()
app.add_middleware(CORSMiddleware, 
    allow_origins=["*"],
    allow_methods=["*"],
    allow_credentials=True,
    allow_headers=["*"]
)

app.add_api_route("/api/curriculums", curriculum_router)
app.add_api_route("/api/auth", auth_router)

@app.get("/")
async def get_health() -> dict:
    return {"up": True, "datetime": datetime.now()}