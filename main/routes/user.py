from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated
from data.db import get_user_api_keys, save_api_key
from main.data.dto.user import UserDTO

user_router = APIRouter()

@user_router.get("/api/key")
async def get_api_keys(data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    api_keys = await get_user_api_keys(UserDTO(username=data.username, password=data.password))
    return {"api_key":api_keys}

@user_router.post("/api/key")
async def create_api_key(data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password)
    res = await save_api_key(user)
    
    return {"created": True, "api_key":res} if res != None else {"error":"invalid to create api key"}
