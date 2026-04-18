import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Nexus Security Middleware (v2.0): Implementa cabeceras proactivas para blindar
    el orchestrator contra XSS, Clickjacking y degradación de protocolo.

    All security headers are computed once at startup (env vars are read-only at
    runtime) and stored as instance attributes to avoid repeated string operations
    on every request.
    """

    def __init__(self, app):
        super().__init__(app)

        # 4. Content-Security-Policy — computed once from env vars at startup.
        allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        extra_domains = os.getenv("CSP_EXTRA_DOMAINS", "").split(",")

        # Limpiar y normalizar dominios (quitar protocolos/rutas)
        csp_domains: set = set()
        for domain in allowed_origins + extra_domains:
            d = domain.strip()
            if d:
                if "://" in d:
                    d = d.split("://")[1].split("/")[0]
                csp_domains.add(d)

        # Dominios de confianza base (OpenAI, Meta) + dinámicos
        trusted_connect = ["*.openai.com", "*.facebook.com", "*.messenger.com", "*.fbcdn.net", "cdn.jsdelivr.net"]
        connect_src = " ".join(["'self'"] + trusted_connect + list(csp_domains))

        self._csp_policy = (
            f"default-src 'self'; "
            f"script-src 'self' 'unsafe-inline' cdn.jsdelivr.net; "
            f"style-src 'self' 'unsafe-inline' fonts.googleapis.com cdn.jsdelivr.net; "
            f"font-src 'self' fonts.gstatic.com; "
            f"img-src 'self' data: fastapi.tiangolo.com; "
            f"connect-src {connect_src}; "
            f"frame-ancestors 'none'; "
            f"object-src 'none';"
        )

        # Pre-build the full header dict so dispatch is a pure dict copy per request.
        self._security_headers = {
            # 1. Anti-clickjacking
            "X-Frame-Options": "DENY",
            # 2. Anti-MIME-sniffing
            "X-Content-Type-Options": "nosniff",
            # 3. HSTS — max-age 6 months
            "Strict-Transport-Security": "max-age=15768000; includeSubDomains",
            # 4. CSP
            "Content-Security-Policy": self._csp_policy,
        }

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for header, value in self._security_headers.items():
            response.headers[header] = value
        return response
