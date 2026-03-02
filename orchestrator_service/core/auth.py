import os
import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple
from fastapi import Header, HTTPException, Depends, Request, status
from db import db
from auth_service import auth_service

logger = logging.getLogger(__name__)

# Configuración
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
if not ADMIN_TOKEN:
    import logging as _logging
    _logging.getLogger(__name__).critical(
        "🚨 SECURITY CRITICAL: ADMIN_TOKEN no está definido en las variables de entorno. "
        "Todas las peticiones admin serán rechazadas con 401. "
        "Define ADMIN_TOKEN en el entorno del orchestrator."
    )

async def verify_admin_token(
    request: Request,
    x_admin_token: str = Header(None),
    authorization: str = Header(None)
):
    """
    Implementa la validación de doble factor para administración:
    1. Validar Token JWT (Identidad y Sesión) - Soporta Bearer y Cookies
    2. Validar X-Admin-Token (Autorización Estática de Infraestructura)
    """
    # Capa 1: Infraestructura (Strict en Producción)
    if x_admin_token != ADMIN_TOKEN:
        logger.warning(f"❌ 401: X-Admin-Token mismatch or missing. IP: {request.client.host if request.client else 'unknown'}")
        if not x_admin_token:
             logger.error("🛡️ SECURITY ALERT: X-Admin-Token is missing in request headers.")
        raise HTTPException(status_code=401, detail="Token de infraestructura (X-Admin-Token) inválido o inexistente.")

    # Capa 2: Identidad (JWT)
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ")[1]
        logger.debug("🔑 Identity: Using Bearer token fallback.")
    else:
        # Fallback a Cookie HttpOnly para mitigar XSS
        token = request.cookies.get("access_token")
        if token:
            logger.debug("🍪 Identity: Using access_token cookie.")

    if not token:
        logger.warning(f"❌ 401: JWT Token missing (No Bearer and No Cookie). IP: {request.client.host if request.client else 'unknown'}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Sesión no válida. Token JWT requerido (Bearer o Cookie)."
        )
    
    user_data = auth_service.decode_token(token)
    
    if not user_data:
        logger.warning(f"❌ 401: Invalid or expired JWT. IP: {request.client.host if request.client else 'unknown'}")
        raise HTTPException(status_code=401, detail="Token de sesión expirado o inválido.")
    
    if user_data.role not in ['ceo', 'secretary', 'professional']:
        raise HTTPException(status_code=403, detail="No tienes permisos suficientes.")

    request.state.user = user_data
    return user_data


async def verify_ceo_token(
    user_data=Depends(verify_admin_token)
):
    """
    Garantiza que el usuario tenga rol de 'ceo'.
    """
    if user_data.role != 'ceo':
        logger.warning(f"❌ 403: Role {user_data.role} is not CEO.")
        raise HTTPException(status_code=403, detail="Esta acción solo puede ser realizada por el CEO.")
    return user_data

async def verify_staff_token(
    user_data=Depends(verify_admin_token)
):
    """
    Garantiza que el usuario sea 'ceo', 'secretary' o 'professional'.
    Uso: Operaciones administrativas de chat y gestión (según Spec 18/19).
    """
    if user_data.role not in ['ceo', 'secretary', 'professional']:
        logger.warning(f"❌ 403: Role {user_data.role} is not authorized for staff operations.")
        raise HTTPException(status_code=403, detail="Esta acción requiere rol de Staff (CEO, Secretaría o Profesional).")
    return user_data

def require_role(allowed_roles: List[str]):
    """
    Factory para dependencias de RBAC granular.
    """
    async def role_dependency(user_data=Depends(verify_admin_token)):
        if user_data.role not in allowed_roles:
            raise HTTPException(
                status_code=403, 
                detail=f"Permisos insuficientes. Se requiere uno de: {', '.join(allowed_roles)}"
            )
        return user_data
    return role_dependency

async def get_resolved_tenant_id(request: Request, user_data=Depends(verify_admin_token)) -> int:
    """
    Resuelve el tenant_id real con aislamiento estricto (Spec 32):
    1. CEOs: Global Access. Usan X-Tenant-ID header para alternar sedes.
    2. Staff (Sec/Prof): Locked Access. Solo pueden acceder a su tenant_id de registro.
    """
    # Lookup real tenant_id from database
    real_tenant_id = None
    try:
        real_tenant_id = await db.pool.fetchval(
            "SELECT tenant_id FROM professionals WHERE user_id = $1",
            uuid.UUID(user_data.user_id)
        )
    except Exception as e:
        logger.error(f"Error fetching real_tenant_id for {user_data.user_id}: {e}")

    # Input Header Hint
    header_tid = request.headers.get("X-Tenant-ID")
    
    if user_data.role == 'ceo':
        # CEO: Confía en el header si existe, si no usa el de su registro o fallback.
        if header_tid and header_tid.isdigit():
            return int(header_tid)
        return int(real_tenant_id) if real_tenant_id is not None else 1
    else:
        # STAFF/PROF: Aislamiento estricto.
        if real_tenant_id is None:
            # Si no tiene fila en professionals (raro para staff activo), denegar acceso a datos.
            raise HTTPException(status_code=403, detail="Aislamiento Nexus: Usuario de staff sin clínica asignada.")
        
        # Bloquear intentos de ver otros tenants
        if header_tid and header_tid.isdigit() and int(header_tid) != int(real_tenant_id):
            logger.warning(f"🛡️ BLOQUEO NEXUS: Intento de Tenant Mismatch por {user_data.role} {user_data.email}")
            # Forzamos su tenant real en lugar de lanzar error para no romper la navegación si el frontend se confunde,
            # pero garantizamos que los datos devueltos sean los correctos.
        
        return int(real_tenant_id)

async def log_pii_access(request: Request, user_data, patient_id: Any, action: str = "read_clinical_record"):
    """
    Registra auditoría de acceso a datos sensibles (Nexus Protocol v7.6).
    """
    logger.info(f"🛡️ AUDIT: User {user_data.email} ({user_data.role}) accessed PII for Patient {patient_id}. Action: {action}. IP: {request.client.host if request.client else 'unknown'}")

async def get_ceo_user_and_tenant(
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id)
) -> Tuple[Any, int]:
    """
    Dependencia combinada para rutas que requieren rol de CEO y un tenant_id resuelto.
    Usado principalmente en módulos de Marketing y Analítica Global.
    Retorna (user_data, tenant_id).
    """
    return user_data, tenant_id


async def verify_infra_token_only(
    request: Request,
    x_admin_token: str = Header(None),
):
    """
    Middleware simplificado que solo valida el token de infraestructura (x-admin-token).
    Para uso en producción cuando el frontend no maneja JWT.
    """
    # Validar Token de Infraestructura
    if x_admin_token != ADMIN_TOKEN:
        logger.warning(f"❌ 401: X-Admin-Token mismatch or missing. IP: {request.client.host if request.client else 'unknown'}")
        if not x_admin_token:
            logger.error("🛡️ SECURITY ALERT: X-Admin-Token is missing in request headers.")
        raise HTTPException(status_code=401, detail="Token de infraestructura (X-Admin-Token) inválido o inexistente.")
    
    # Para compatibilidad, crear un user_data básico
    from pydantic import BaseModel
    
    class SimpleUserData(BaseModel):
        user_id: str = "infra-user"
        email: str = "infra@system"
        role: str = "ceo"
        tenant_id: int = 1
    
    user_data = SimpleUserData()
    
    # Obtener tenant_id del header si está presente
    header_tid = request.headers.get("X-Tenant-ID")
    if header_tid and header_tid.isdigit():
        user_data.tenant_id = int(header_tid)
    
    request.state.user = user_data
    return user_data


async def get_ceo_infra_only(
    user_data=Depends(verify_infra_token_only),
):
    """
    Dependencia para rutas CEO que solo usan token de infraestructura.
    """
    return user_data, user_data.tenant_id
