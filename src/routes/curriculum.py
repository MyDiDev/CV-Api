from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from model.model import evaluate_cv_document, generate_quiz
from data.db import validate_api_key, get_documents
from dto.user import APIKey
from pyrate_limiter import Duration, Limiter, Rate
from fastapi_limiter.depends import RateLimiter

security = HTTPBearer()
curriculum_router = APIRouter()

async def get_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    key = credentials.credentials
    res = await validate_api_key(key)
    
    if not res:
        return HTTPException(status_code=400, detail="Invalid API Key")
    
    return res.get("api_key")

@curriculum_router.post("/api/curriculum/quiz", tags=["curriculums"],
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.MINUTE * 2))))]                    
)
async def generate_quizziz(data: dict, api_key=Depends(get_api_key)):
    if not data or not data.get("content") or not data.get("requirements"):
        print(data)
        raise HTTPException(status_code=400, detail="Invalid user information")
    
    if not api_key or len(api_key) == 0:
        raise HTTPException(status_code=400, detail="Invalid API key")
    
    api_key = APIKey(id=api_key[0])
    res = await generate_quiz(str(data.get("content", "")), api_key, str(data.get("requirements", "")))
    return {"result":res}

@curriculum_router.post("/api/curriculum", tags=["curriculums"],
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(20, Duration.MINUTE * 15))))]
)
async def evaluate_curriculum(data: dict, api_key=Depends(get_api_key)):
    if not data["content"] or len(data["content"]) == 0:
        raise HTTPException(status_code=400, detail="Invalid document data to process")
    
    if not api_key or len(api_key) == 0:
        raise HTTPException(status_code=400, detail="Invalid API key")
    
    api_key = APIKey(id=api_key[0])
    res = await evaluate_cv_document(data.get("content", ""), api_key)

    if res.get("error"):
        raise HTTPException(status_code=501, detail=res)
    return {"result":res}

@curriculum_router.get("/api/curriculum/documents", tags=["curriculums"], 
    dependencies=[Depends(RateLimiter(limiter=Limiter(Rate(5, Duration.MINUTE * 5))))]                       
)
async def get_user_documents(api_key=Depends(get_api_key)):
    if not api_key or len(api_key) == 0:
        raise HTTPException(status_code=400, detail="Invalid API key")
    
    res = await get_documents(api_key[0])
    if not res:
        raise HTTPException(status_code=400, detail="Invalid documents to fetch")
    return {"result":res}