"""
python/helpers/request_throttle.py

ASGI middleware for per-IP request rate limiting.

Uses a sliding window counter to throttle excessive requests.
Returns HTTP 429 Too Many Requests when the limit is exceeded.

Defaults:
  - 60 requests per 60 seconds per IP (for API endpoints)
  - Static assets and health checks are excluded
"""

import time
import threading
from typing import Dict, Tuple

from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.responses import Response

# Default limits
DEFAULT_MAX_REQUESTS = 60
DEFAULT_WINDOW_SECONDS = 60

# Paths that bypass rate limiting
_EXEMPT_PREFIXES = (
    "/static/",
    "/webui/",
    "/health",
    "/favicon",
)

_lock = threading.RLock()
# ip -> (request_count, window_start)
_counters: Dict[str, Tuple[int, float]] = {}


def _cleanup_old_entries(now: float, window: float) -> None:
    """Remove expired entries to prevent memory leak."""
    expired = [ip for ip, (_, start) in _counters.items() if now - start > window * 2]
    for ip in expired:
        del _counters[ip]


class RequestThrottleMiddleware:
    """ASGI middleware that rate-limits requests per client IP."""

    def __init__(
        self,
        app: ASGIApp,
        max_requests: int = DEFAULT_MAX_REQUESTS,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ):
        self.app = app
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Skip rate limiting for exempt paths
        if any(path.startswith(prefix) for prefix in _EXEMPT_PREFIXES):
            await self.app(scope, receive, send)
            return

        # Extract client IP
        client = scope.get("client")
        ip = client[0] if client else "unknown"

        if not self._check_rate(ip):
            # Log the rate limit hit
            try:
                from python.helpers.audit_log import log_event
                log_event("rate_limit_hit", ip=ip, detail=f"Path: {path}")
            except Exception:
                pass

            response = Response(
                content="Rate limit exceeded. Try again later.",
                status_code=429,
                headers={"Retry-After": str(self.window_seconds)},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)

    def _check_rate(self, ip: str) -> bool:
        """Returns True if the request is within rate limits."""
        now = time.time()

        with _lock:
            # Periodic cleanup
            if len(_counters) > 1000:
                _cleanup_old_entries(now, self.window_seconds)

            if ip in _counters:
                count, window_start = _counters[ip]

                # Reset window if expired
                if now - window_start > self.window_seconds:
                    _counters[ip] = (1, now)
                    return True

                if count >= self.max_requests:
                    return False

                _counters[ip] = (count + 1, window_start)
                return True
            else:
                _counters[ip] = (1, now)
                return True
