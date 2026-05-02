from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from typing import Annotated
from dotenv import load_dotenv
from data.db import create_user, get_user
from dto.user import UserDTO

auth_router = APIRouter()

@auth_router.post("/login")
async def login(data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password)
    res = get_user(user)
    return {"access_authorized":True} if res != None else {"access_authorized":False, "error":"Invalid user"}
    

@auth_router.post("/register")
async def register(data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password)
    res = create_user(user)
    return {"user_created":True} if res == True else {"error":"Error while creating user, try again and check body request"}
