from fastapi import Request
from fastapi.responses import JSONResponse
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handles expected AppError subclasses and returns a standardized JSON response."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled exceptions to prevent stack trace leaks and return a 500."""
    # Log the full traceback internally
    logger.error(f"Unhandled server error: {str(exc)}", exc_info=exc)
    
    # Do not return HTTP response for websocket connections
    if request.scope.get("type") == "websocket":
        raise exc
    
    # Return a generic, safe response to the client
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_server_error", "message": "An unexpected error occurred."}},
    )
