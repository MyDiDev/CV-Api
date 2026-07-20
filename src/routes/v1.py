from fastapi import APIRouter
from routes.curriculum import curriculum_router
from routes.user import user_router
from routes.auth import auth_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(curriculum_router)
v1_router.include_router(auth_router)
v1_router.include_router(user_router)

legacy_router = APIRouter(prefix="/api")
legacy_router.include_router(curriculum_router)
legacy_router.include_router(auth_router)
legacy_router.include_router(user_router)
