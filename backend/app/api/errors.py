from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handles expected AppError subclasses and returns a standardized JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled exceptions to prevent stack trace leaks and return a 500."""
    if settings.app_env == "development":
        logger.error("Unhandled server error", exc_info=exc)
    else:
        logger.error("Unhandled server error (%s)", type(exc).__name__)
    
    # Do not return HTTP response for websocket connections
    if request.scope.get("type") == "websocket":
        raise exc
    
    # Return a generic, safe response to the client
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_server_error", "message": "An unexpected error occurred."}},
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    if settings.app_env == "production":
        return JSONResponse(
            status_code=422,
            content={"detail": "Invalid request."},
        )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})
