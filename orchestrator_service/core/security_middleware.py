import os
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from fastapi import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Nexus Security Middleware (v2.0): Implementa cabeceras proactivas para blindar
    el orchestrator contra XSS, Clickjacking y degradación de protocolo.
    """
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        
        # 1. X-Frame-Options: Prevenir que la API sea embebida en iframes maliciosos (anti-clickjacking)
        response.headers["X-Frame-Options"] = "DENY"
        
        # 2. X-Content-Type-Options: Forzar al navegador a respetar el MIME-type enviado (anti-sniffing)
        response.headers["X-Content-Type-Options"] = "nosniff"
        
        # 3. Strict-Transport-Security (HSTS): Defensa en profundidad. Inyectamos incluso si hay proxy.
        # max-age de 6 meses (15768000 seg)
        response.headers["Strict-Transport-Security"] = "max-age=15768000; includeSubDomains"
        
        # 4. Content-Security-Policy (CSP) Dinámico:
        # Permite 'self' por defecto y expande connect-src basado en variables de entorno.
        allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
        extra_domains = os.getenv("CSP_EXTRA_DOMAINS", "").split(",")
        
        # Limpiar y normalizar dominios (quitar protocolos/rutas)
        csp_domains = set()
        for domain in allowed_origins + extra_domains:
            d = domain.strip()
            if d:
                # Extraer host si viene con protocolo
                if "://" in d:
                    d = d.split("://")[1].split("/")[0]
                csp_domains.add(d)
        
        # Dominios de confianza base (OpenAI, Meta) + dinámicos
        trusted_connect = ["*.openai.com", "*.facebook.com", "*.messenger.com", "*.fbcdn.net"]
        connect_src = " ".join(["'self'"] + trusted_connect + list(csp_domains))
        
        csp_policy = (
            f"default-src 'self'; "
            f"script-src 'self' 'unsafe-inline'; "
            f"style-src 'self' 'unsafe-inline' fonts.googleapis.com; "
            f"font-src 'self' fonts.gstatic.com; "
            f"img-src 'self' data:; "
            f"connect-src {connect_src}; "
            f"frame-ancestors 'none'; "
            f"object-src 'none';"
        )
        response.headers["Content-Security-Policy"] = csp_policy
        
        return response
