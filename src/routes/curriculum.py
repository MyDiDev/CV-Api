from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from model.model import evaluate_cv_document, generate_quiz
from repository.api_key_repository import ApiKeyRepository
from repository.document_repository import DocumentRepository
from dto.user import APIKey
from pyrate_limiter import Duration, Limiter, Rate
from fastapi_limiter.depends import RateLimiter
from typing import Any

security = HTTPBearer()
curriculum_router = APIRouter()

async def get_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Any:
    key = credentials.credentials
    res = await ApiKeyRepository.validate_api_key(key)
    
    if not res or not res.get("api_key"):
        raise HTTPException(status_code=401, detail="Invalid API Key")
    
    return res.get("api_key")

@curriculum_router.post("/curriculum/quiz", tags=["curriculums"],
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.MINUTE * 2))))]                    
)
async def generate_quizziz(data: dict[str, Any], api_key: Any = Depends(get_api_key)) -> dict[str, Any]:
    if not data or not data.get("content") or not data.get("requirements"):
        raise HTTPException(status_code=400, detail="Invalid content or requirements information")
    
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    key_id = api_key[0] if isinstance(api_key, (list, tuple)) else api_key
    key_obj = APIKey(id=key_id)
    res = await generate_quiz(str(data.get("content", "")), key_obj, str(data.get("requirements", "")))
    return {"result": res}

@curriculum_router.post("/curriculum", tags=["curriculums"],
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(20, Duration.MINUTE * 15))))]
)
async def evaluate_curriculum(data: dict[str, Any], api_key: Any = Depends(get_api_key)) -> dict[str, Any]:
    if not data or not data.get("content"):
        raise HTTPException(status_code=400, detail="Invalid document data to process")
    
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    key_id = api_key[0] if isinstance(api_key, (list, tuple)) else api_key
    key_obj = APIKey(id=key_id)
    res = await evaluate_cv_document(str(data.get("content", "")), key_obj)

    if isinstance(res, dict) and res.get("error"):
        raise HTTPException(status_code=500, detail="Error evaluating CV document")
    return {"result": res}

@curriculum_router.get("/curriculum/documents", tags=["curriculums"], 
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.MINUTE * 5))))]                       
)
async def get_user_documents(api_key: Any = Depends(get_api_key)) -> dict[str, Any]:
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    key_id = api_key[0] if isinstance(api_key, (list, tuple)) else api_key
    res = await DocumentRepository.get_documents(key_id)
    if res is None:
        raise HTTPException(status_code=404, detail="Invalid documents to fetch")
    return {"result": res}