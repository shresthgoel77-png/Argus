from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.middleware.sessions import SessionMiddleware
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.errors import app_error_handler, global_exception_handler
from app.api.errors import request_validation_exception_handler
from app.core.exceptions import AppError
from app.core.rate_limit import ApiRateLimitMiddleware
from app.integrations.ai import register_provider
from app.integrations.ai.gemini_provider import GeminiProvider

logger = get_logger(__name__)

app = FastAPI(title="RepoMedic Backend")

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    https_only=settings.app_env == "production",
    same_site="lax",
)
app.add_middleware(
    ApiRateLimitMiddleware,
    max_requests=settings.api_rate_limit_requests,
    window_seconds=settings.api_rate_limit_window_seconds,
)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

@app.on_event("startup")
async def startup_event():

    configure_logging()
    register_provider(GeminiProvider.key, GeminiProvider)
    logger.info("Application starting up...")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

@app.get("/")
def read_root():
    return {"service": "repomedic-backend", "status": "ok"}

app.include_router(api_router, prefix="/api/v1")
