from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security.oauth2 import OAuth2PasswordRequestFormEmail
from typing import Annotated
from data.db import get_user_api_keys, save_api_key
from dto.user import UserDTO

user_router = APIRouter()

@user_router.get("/api/key")
async def get_api_keys(data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    api_keys = get_user_api_keys(UserDTO(username=data.username, password=data.password))
    return {"keys":api_keys}

@user_router.post("/api/key/create")
async def create_api_key(data: Annotated[OAuth2PasswordRequestFormEmail, Depends()]):
    if not data.username or not data.password or not data.email:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password, email=data.email)
    res = save_api_key(user)
    
    return {"created":True, "api_key":res} if res == True else {"error":"Validate your credentials if you are authenticated to use the service"}
