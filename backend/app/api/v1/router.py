from fastapi import APIRouter
from app.api.v1 import health

api_router = APIRouter()

# Include feature-specific routers here
api_router.include_router(health.router)
