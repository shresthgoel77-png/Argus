class AppError(Exception):
    """Base class for all expected application errors."""
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found"):
        super().__init__(code="not_found", message=message, status_code=404)

class ValidationAppError(AppError):
    def __init__(self, message: str = "Validation failed"):
        super().__init__(code="validation_error", message=message, status_code=422)
