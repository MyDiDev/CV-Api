from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from model.model import evaluate_cv_document
from data.db import validate_api_key
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

# add cloudflare CDN to save documents and responses

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
    if res is not None:
        return res if res.get("error") else {"result":res}
    
    raise HTTPException(status_code=500, detail="Error while processing CV and analysing the document, please check body and authorization headers")