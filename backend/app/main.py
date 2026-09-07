from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.health import router as health_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.api.errors import app_error_handler, global_exception_handler
from app.core.exceptions import AppError

logger = get_logger(__name__)

app = FastAPI(title="RepoMedic Backend")

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, global_exception_handler)

@app.on_event("startup")
async def startup_event():

    configure_logging()
    logger.info("Application starting up...")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"service": "repomedic-backend", "status": "ok"}

app.include_router(health_router, prefix="/api/v1")
