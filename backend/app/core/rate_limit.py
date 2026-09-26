from collections import deque
import threading
import time

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class ApiRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a small process-local sliding-window limit to API requests."""

    _MAX_TRACKED_CLIENTS = 8192

    def __init__(
        self,
        app,
        *,
        max_requests: int,
        window_seconds: int,
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith("/api/") and request.method != "OPTIONS":
            client_ip = request.client.host if request.client else "unknown"
            now = time.monotonic()
            cutoff = now - self.window_seconds
            with self._lock:
                if (
                    client_ip not in self._requests
                    and len(self._requests) >= self._MAX_TRACKED_CLIENTS
                ):
                    for tracked_ip, tracked_timestamps in list(self._requests.items()):
                        while tracked_timestamps and tracked_timestamps[0] <= cutoff:
                            tracked_timestamps.popleft()
                        if not tracked_timestamps:
                            del self._requests[tracked_ip]
                    if len(self._requests) >= self._MAX_TRACKED_CLIENTS:
                        self._requests.pop(next(iter(self._requests)))

                timestamps = self._requests.setdefault(client_ip, deque())
                while timestamps and timestamps[0] <= cutoff:
                    timestamps.popleft()
                if len(timestamps) >= self.max_requests:
                    retry_after = max(
                        1, int(timestamps[0] + self.window_seconds - now)
                    )
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": {
                                "code": "rate_limit_exceeded",
                                "message": "Too many requests. Please try again later.",
                            }
                        },
                        headers={"Retry-After": str(retry_after)},
                    )
                timestamps.append(now)

        return await call_next(request)