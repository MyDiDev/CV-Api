from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated, Any
from repository.user_repository import UserRepository
from dto.user import UserDTO
from services.tokenizer import create_token

auth_router = APIRouter()

@auth_router.post("/login")
async def login(data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, Any]:
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password)
    res = await UserRepository.get_user(user)
    if res is None:
        raise HTTPException(status_code=401, detail="Invalid user found")
    
    token = create_token(res)
    return {"access_token": token}

@auth_router.post("/register")
async def register(data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, Any]:
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password)
    res = await UserRepository.create_user(user)
    
    if not res:
        raise HTTPException(status_code=400, detail="User creation failed")
        
    return {"created": res}
