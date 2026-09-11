from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from typing import Annotated, Any
from repository.api_key_repository import ApiKeyRepository
from services.tokenizer import get_token
from dto.user import UserDTO
from pyrate_limiter import Duration, Limiter, Rate
from services.rate_limiter import RateLimiter

user_router = APIRouter()


@user_router.post(
    "/key",
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.MINUTE))))]
)
async def get_api_keys(data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, Any]:
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    api_keys = await ApiKeyRepository.get_user_api_key(UserDTO(username=data.username, password=data.password))
    if not api_keys:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"api_key": api_keys}


@user_router.post(
    "/create/key",
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.MINUTE))))]
)
async def create_api_key(data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, Any]:
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    
    user = UserDTO(username=data.username, password=data.password)
    res = await ApiKeyRepository.save_api_key(user)
    
    if res is None:
        raise HTTPException(status_code=400, detail="Invalid data to create API key")
        
    return {"created": True, "api_key": res}


@user_router.get(
    "/dashboard",
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(20, Duration.MINUTE))))]
)
async def get_api_dashboard_info(token: dict[str, Any] = Depends(get_token)) -> dict[str, Any]:        
    user = UserDTO(username=token.get("username"), password=token.get("password"))
    if not user.username or not user.password:
        raise HTTPException(status_code=401, detail="Invalid user credentials")
    
    res = await ApiKeyRepository.get_api_information(user)
    if res is None:
        raise HTTPException(status_code=404, detail="No API key or dashboard information found")
    
    return res
