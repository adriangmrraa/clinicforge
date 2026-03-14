"""
Autenticación integrada para Dashboard CEO - Usa el sistema existente de ClinicForge
"""

import logging
from typing import Optional
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

def get_current_user(request: Request):
    """
    Obtiene el usuario actual basado en la sesión existente de ClinicForge
    """
    # 1. Verificar token de acceso en cookies (sistema existente)
    access_token = request.cookies.get("access_token")
    if access_token:
        # Aquí normalmente validaríamos el token JWT con auth_service
        # Por ahora, asumimos que si hay access_token, el usuario está autenticado
        logger.debug(f"✅ Usuario autenticado via access_token cookie")
        return {"authenticated": True, "token": access_token}
    
    # 2. Verificar header Authorization (Bearer token)
    authorization = request.headers.get("authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        logger.debug(f"✅ Usuario autenticado via Bearer token")
        return {"authenticated": True, "token": token}
    
    # 3. Verificar si hay sesión de Google OAuth
    google_token = request.cookies.get("google_token") or request.cookies.get("oauth_token")
    if google_token:
        logger.debug(f"✅ Usuario autenticado via Google OAuth")
        return {"authenticated": True, "token": google_token, "source": "google"}
    
    # No autenticado
    return {"authenticated": False}

def is_ceo_authenticated(request: Request) -> bool:
    """
    Verifica si el usuario actual es CEO basado en el sistema existente
    """
    user = get_current_user(request)
    
    if not user["authenticated"]:
        return False
    
    # En un sistema real, aquí verificaríamos el rol del usuario en la base de datos
    # Por ahora, asumimos que cualquier usuario autenticado en ClinicForge puede acceder al dashboard CEO
    
    # TODO: Implementar verificación real de rol CEO
    # Por ahora, permitimos acceso a cualquier usuario autenticado
    return True

async def ceo_access_required(request: Request):
    """
    Dependency que verifica acceso CEO usando el sistema existente
    Redirige al home si no está autenticado
    """
    if not is_ceo_authenticated(request):
        # Redirigir al home de ClinicForge (no a un login separado)
        logger.warning(f"❌ Acceso denegado al dashboard CEO - Usuario no autenticado")
        raise HTTPException(
            status_code=307,  # Temporary Redirect
            headers={"Location": "/"}  # Redirigir al home principal
        )
    
    return True

async def ceo_api_access(request: Request):
    """
    Dependency para APIs - retorna error 403 en lugar de redirigir
    """
    if not is_ceo_authenticated(request):
        raise HTTPException(
            status_code=403,
            detail="Acceso restringido al CEO. Inicie sesión en ClinicForge primero."
        )
    
    return True

# Middleware simple para debug
async def debug_auth_middleware(request: Request, call_next):
    """
    Middleware para debug de autenticación
    """
    # Solo para rutas del dashboard
    if request.url.path.startswith("/dashboard"):
        user = get_current_user(request)
        logger.debug(f"🔍 Dashboard auth check: path={request.url.path}, authenticated={user['authenticated']}")
        
        # Agregar headers de debug
        response = await call_next(request)
        response.headers["X-Dashboard-Auth"] = "checked"
        response.headers["X-User-Authenticated"] = str(user["authenticated"])
        return response
    
    return await call_next(request)