from fastapi import APIRouter
from app.api.v1 import health
from app.api.v1 import auth
from app.api.v1 import github
from app.api.v1 import repositories
from app.api.v1 import webhooks
from app.api.v1 import monitoring
from app.api.v1 import findings
from app.api.v1 import repo_health
from app.api.v1 import ai_connections
from app.api.v1 import bot_interactions
from app.api.v1 import notification_preferences
from app.api.v1 import internal
from app.api.routes import notifications

api_router = APIRouter()

# Include feature-specific routers here
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(github.router)
api_router.include_router(repositories.router)
api_router.include_router(webhooks.router)
api_router.include_router(monitoring.router)
api_router.include_router(findings.router)
api_router.include_router(repo_health.router)
api_router.include_router(ai_connections.router)
api_router.include_router(bot_interactions.router)
api_router.include_router(
    notification_preferences.router,
    prefix="/notifications",
    tags=["notifications"],
)
api_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["notifications"],
)
api_router.include_router(internal.router)
