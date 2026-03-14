"""
Middleware de autenticación CEO - Detecta sesión automáticamente
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import secrets
from fastapi import Request, HTTPException, Depends
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

# Clave secreta para cookies (debería estar en .env)
SECRET_KEY = os.getenv("CEO_SECRET_KEY", secrets.token_hex(32))
CEO_ACCESS_KEY = os.getenv("CEO_ACCESS_KEY", "dralauradelgado2026")

# Sesiones activas (en producción usar Redis)
active_sessions: Dict[str, Dict[str, Any]] = {}

class CEOSessionManager:
    """Gestor de sesiones CEO"""
    
    def __init__(self):
        self.secret_key = SECRET_KEY
        self.session_timeout = timedelta(hours=24)
    
    def create_session(self, request: Request) -> str:
        """Crea una nueva sesión CEO"""
        session_id = secrets.token_urlsafe(32)
        
        active_sessions[session_id] = {
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "user_agent": request.headers.get("user-agent", ""),
            "ip_address": request.client.host if request.client else "unknown"
        }
        
        logger.info(f"✅ Nueva sesión CEO creada: {session_id[:8]}...")
        return session_id
    
    def validate_session(self, session_id: str) -> bool:
        """Valida una sesión CEO"""
        if session_id not in active_sessions:
            return False
        
        session = active_sessions[session_id]
        
        # Verificar timeout
        if datetime.now() - session["last_activity"] > self.session_timeout:
            del active_sessions[session_id]
            return False
        
        # Actualizar última actividad
        session["last_activity"] = datetime.now()
        return True
    
    def destroy_session(self, session_id: str):
        """Destruye una sesión CEO"""
        if session_id in active_sessions:
            del active_sessions[session_id]
            logger.info(f"✅ Sesión CEO destruida: {session_id[:8]}...")

# Instancia global
session_manager = CEOSessionManager()

def get_ceo_session(request: Request) -> Optional[str]:
    """Obtiene la sesión CEO de la request"""
    # 1. Verificar cookie de sesión
    session_id = request.cookies.get("ceo_session")
    if session_id and session_manager.validate_session(session_id):
        return session_id
    
    # 2. Verificar header de acceso
    access_key = request.headers.get("X-CEO-Access-Key")
    if access_key == CEO_ACCESS_KEY:
        # Crear sesión automáticamente
        session_id = session_manager.create_session(request)
        return session_id
    
    # 3. Verificar query parameter (para login inicial)
    access_key_param = request.query_params.get("key")
    if access_key_param == CEO_ACCESS_KEY:
        session_id = session_manager.create_session(request)
        return session_id
    
    return None

async def ceo_auth_required(request: Request):
    """
    Dependency que verifica autenticación CEO
    Redirige al login si no está autenticado
    """
    session_id = get_ceo_session(request)
    
    if not session_id:
        # No autenticado - redirigir al login
        raise HTTPException(
            status_code=307,  # Temporary Redirect
            headers={"Location": "/dashboard/login"}
        )
    
    return session_id

async def ceo_api_auth(request: Request):
    """
    Dependency para APIs - retorna error 403 en lugar de redirigir
    """
    session_id = get_ceo_session(request)
    
    if not session_id:
        raise HTTPException(
            status_code=403,
            detail="Acceso restringido al CEO. Use X-CEO-Access-Key header o inicie sesión."
        )
    
    return session_id

def create_login_response(session_id: str, redirect_url: str = "/dashboard/status"):
    """Crea respuesta con cookie de sesión"""
    response = RedirectResponse(url=redirect_url, status_code=302)
    
    # Configurar cookie de sesión
    response.set_cookie(
        key="ceo_session",
        value=session_id,
        httponly=True,
        secure=True,  # Solo HTTPS en producción
        samesite="lax",
        max_age=86400,  # 24 horas
        path="/dashboard"
    )
    
    # Cookie adicional para frontend (no httponly para JS)
    response.set_cookie(
        key="ceo_authenticated",
        value="true",
        secure=True,
        samesite="lax",
        max_age=86400,
        path="/"
    )
    
    return response

def create_logout_response():
    """Crea respuesta para logout"""
    response = RedirectResponse(url="/", status_code=302)
    
    # Eliminar cookies
    response.delete_cookie("ceo_session", path="/dashboard")
    response.delete_cookie("ceo_authenticated", path="/")
    
    return response

# Middleware para inyectar contexto CEO en templates
async def ceo_context(request: Request):
    """Inyecta contexto CEO en templates"""
    session_id = get_ceo_session(request)
    
    return {
        "is_ceo_authenticated": bool(session_id),
        "ceo_session_id": session_id[:8] + "..." if session_id else None
    }