from app.core.exceptions import AppError

class AuthenticationError(AppError):
    """Error raised when authentication fails."""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(code="authentication_error", message=message, status_code=401)

class NotAuthenticatedError(AppError):
    """Error raised when an action requires authentication but none is present."""
    def __init__(self, message: str = "Not authenticated"):
        super().__init__(code="not_authenticated", message=message, status_code=401)
