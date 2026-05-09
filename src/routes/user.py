from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm, HTTPAuthorizationCredentials, HTTPBearer
from typing import Annotated
from data.db import get_user_api_key, save_api_key, get_api_information
from services.tokenizer import get_token
from dto.user import UserDTO

user_router = APIRouter()

@user_router.get("/api/key")
async def get_api_keys(data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    api_keys = await get_user_api_key(UserDTO(username=data.username, password=data.password))
    return {"api_key":api_keys}

@user_router.post("/api/key")
async def create_api_key(data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password)
    res = await save_api_key(user)
    
    return {"created": True, "api_key":res} if res != None else {"error":"Invalid data to create api key"}

# create endpoints to resume data like api usage, counted tokens, logs history, etc... 
@user_router.get("/api/dashboard")
async def get_api_dashboard_info(token=Depends(get_token)):        
    user = UserDTO(username=token.get("username", None), password=token.get("password", None))
    if not user.username or not user.password:
        raise HTTPException(status_code=400, detail="Invalid user credentials")
    
    res = await get_api_information(user)
    if not res:
        raise HTTPException(status_code=400, detail="No API key found")
    
    return res

# check every endpoint with token verification inside every endpoint request.