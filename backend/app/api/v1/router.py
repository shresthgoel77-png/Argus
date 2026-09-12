from fastapi import APIRouter
from app.api.v1 import health
from app.api.v1 import auth
from app.api.v1 import github
from app.api.v1 import repositories
from app.api.v1 import webhooks
from app.api.v1 import monitoring

api_router = APIRouter()

# Include feature-specific routers here
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(github.router)
api_router.include_router(repositories.router)
api_router.include_router(webhooks.router)
api_router.include_router(monitoring.router)
