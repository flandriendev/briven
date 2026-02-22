"""
python/helpers/security_headers.py

ASGI middleware that adds security headers to all HTTP responses.

Headers added:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: SAMEORIGIN
  - Referrer-Policy: strict-origin-when-cross-origin
  - Permissions-Policy: (restrictive defaults)
  - X-XSS-Protection: 0 (disabled per modern best practices — use CSP instead)

CSP and HSTS are intentionally omitted:
  - CSP would break inline scripts/styles in the existing UI
  - HSTS should be set by the reverse proxy (nginx/caddy), not the app
"""

from starlette.types import ASGIApp, Receive, Scope, Send


class SecurityHeadersMiddleware:
    """ASGI middleware that injects security headers into HTTP responses."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.extend([
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"SAMEORIGIN"),
                    (b"referrer-policy", b"strict-origin-when-cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(self), geolocation=()"),
                    # Modern browsers ignore X-XSS-Protection in favor of CSP.
                    # Setting to 0 avoids the XSS auditor's own vulnerabilities.
                    (b"x-xss-protection", b"0"),
                ])
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)
