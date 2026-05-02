from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from model.model import evaluate_cv_document
from data.db import validate_api_key

security = HTTPBearer()
curriculum_router = APIRouter()

def get_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    key = credentials.credentials
    res = validate_api_key(key)
    
    if not res or not type(res) == dict:
        return HTTPException(status_code=400, detail="Invalid API Key")
    
    return res.get("api_key")

@curriculum_router.post("/api/curriculum", tags=["curriculums"])
async def evaluate_curriculum(data: dict, api_key=Depends(get_api_key)):
    if not data["content"] or len(data["content"]) == 0:
        return HTTPException(status_code=400, detail="Invalid document data to process")
    
    if not api_key:
        return HTTPException(status_code=400, detail="Invalid API key")
    print(api_key)
    
    # res = await evaluate_cv_document(data["content"])
    return {"res":True}
    # return {"result":res} if res != None else HTTPException(status_code=500, detail="Error while processing CV document")