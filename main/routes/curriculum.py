from fastapi import Depends
from fastapi.routing import APIRouter
from fastapi.exceptions import HTTPException
from model.model import evaluate_cv_document

curriculum_router = APIRouter()

@curriculum_router.post("/")
async def evaluate_curriculum(content: str):
    pass