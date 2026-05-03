from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.exceptions import HTTPException
from datetime import datetime
from routes.curriculum import curriculum_router
from routes.user import user_router
from routes.auth import auth_router

app = FastAPI()
app.add_middleware(CORSMiddleware, 
    allow_origins=["*"],
    allow_methods=["*"],
    allow_credentials=True,
    allow_headers=["*"]
)

app.include_router(curriculum_router)
app.include_router(auth_router)
app.include_router(user_router)

@app.get("/")
async def get_health() -> dict:
    return {"up": True, "datetime": datetime.now()}