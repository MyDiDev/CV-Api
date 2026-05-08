from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.security.oauth2 import OAuth2PasswordRequestFormEmail
from typing import Annotated
from data.db import create_user, get_user
from dto.user import UserDTO
from services.tokenizer import create_token, decode_token

auth_router = APIRouter()

@auth_router.post("/api/login")
async def login(data: Annotated[OAuth2PasswordRequestFormEmail, Depends()]):
    if not (data.username or data.email) or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, email=data.email, password=data.password)
    res = await get_user(user)
    if res is None: raise HTTPException(status_code=400, detail="Invalid user found")
    
    token = create_token(res)
    return {"access_token":token}
    

@auth_router.post("/api/register")
async def register(data: Annotated[OAuth2PasswordRequestFormEmail, Depends()]):
    if not data.username or not data.password or not data.email:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password, email=data.email)
    res = await create_user(user)
    return {"created":res} if res else {"error":"try again and check request"}
