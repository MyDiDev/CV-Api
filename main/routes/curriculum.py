from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from model.model import evaluate_cv_document

curriculum_router = APIRouter()
security = HTTPBearer()


def get_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    key = credentials.credentials
    
        
    return {}

@curriculum_router.post("/")
async def evaluate_curriculum(content: str):
    pass