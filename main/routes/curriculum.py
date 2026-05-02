from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from model.model import evaluate_cv_document

curriculum_router = APIRouter()
security = HTTPBearer()


def get_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    key = credentials.credentials
    # check in db and compare
        
    return key

@curriculum_router.post("/")
async def evaluate_curriculum(data: dict, api_key=Depends(get_api_key)) -> dict | HTTPException:
    if not data["content"] or len(data["content"]) == 0:
        raise HTTPException(status_code=400, detail="Invalid document data to process")
    
    res = await evaluate_cv_document(data["content"])
    return res if res != None else HTTPException(status_code=500, detail="Error while processing CV document")