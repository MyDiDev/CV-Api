from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated, Any
from data.db import get_user_api_key, save_api_key, get_api_information
from services.tokenizer import get_token
from dto.user import UserDTO

user_router = APIRouter()

@user_router.post("/api/key")
async def get_api_keys(data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, Any]:
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    api_keys = await get_user_api_key(UserDTO(username=data.username, password=data.password))
    if not api_keys:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"api_key": api_keys}

@user_router.post("/api/create/key")
async def create_api_key(data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, Any]:
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password)
    res = await save_api_key(user)
    
    if res is None:
        raise HTTPException(status_code=400, detail="Invalid data to create API key")
        
    return {"created": True, "api_key": res}

@user_router.get("/api/dashboard")
async def get_api_dashboard_info(token: dict[str, Any] = Depends(get_token)) -> dict[str, Any]:        
    user = UserDTO(username=token.get("username"), password=token.get("password"))
    if not user.username or not user.password:
        raise HTTPException(status_code=401, detail="Invalid user credentials")
    
    res = await get_api_information(user)
    if res is None:
        raise HTTPException(status_code=404, detail="No API key or dashboard information found")
    
    return res
