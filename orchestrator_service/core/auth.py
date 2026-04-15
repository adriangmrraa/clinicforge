import os
import uuid
import hashlib
import logging
from typing import Optional, List, Dict, Any, Tuple
from fastapi import Header, HTTPException, Depends, Request, status
from db import db
from auth_service import auth_service

logger = logging.getLogger(__name__)

# Configuración
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def validate_admin_token_entropy():
    """Valida que ADMIN_TOKEN tenga mínimo 32 caracteres. Llamar al startup."""
    if not ADMIN_TOKEN:
        logger.critical(
            "ADMIN_TOKEN no está definido en las variables de entorno. "
            "Define ADMIN_TOKEN en el entorno del orchestrator (mínimo 32 caracteres)."
        )
        raise SystemExit(1)
    if len(ADMIN_TOKEN) < 32:
        logger.critical(
            f"ADMIN_TOKEN debe tener al menos 32 caracteres (actual: {len(ADMIN_TOKEN)}). "
            'Genera un token seguro con: python -c "import secrets; print(secrets.token_hex(32))"'
        )
        raise SystemExit(1)


async def verify_admin_token(
    request: Request,
    x_admin_token: str = Header(None),
    authorization: str = Header(None),
):
    """
    Implementa la validación de doble factor para administración:
    1. Validar Token JWT (Identidad y Sesión) - Soporta Bearer y Cookies
    2. Validar X-Admin-Token (Autorización Estática de Infraestructura)
    """
    # Capa 1: Infraestructura (Strict en Producción)
    if x_admin_token != ADMIN_TOKEN:
        logger.warning(
            f"❌ 401: X-Admin-Token mismatch or missing. IP: {request.client.host if request.client else 'unknown'}"
        )
        if not x_admin_token:
            logger.error(
                "🛡️ SECURITY ALERT: X-Admin-Token is missing in request headers."
            )
        raise HTTPException(
            status_code=401,
            detail="Token de infraestructura (X-Admin-Token) inválido o inexistente.",
        )

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
        logger.warning(
            f"❌ 401: JWT Token missing (No Bearer and No Cookie). IP: {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no válida. Token JWT requerido (Bearer o Cookie).",
        )

    user_data = auth_service.decode_token(token)

    if not user_data:
        logger.warning(
            f"❌ 401: Invalid or expired JWT. IP: {request.client.host if request.client else 'unknown'}"
        )
        raise HTTPException(
            status_code=401, detail="Token de sesión expirado o inválido."
        )

    if user_data.role not in ["ceo", "secretary", "professional"]:
        raise HTTPException(status_code=403, detail="No tienes permisos suficientes.")

    request.state.user = user_data
    return user_data


async def verify_ceo_token(user_data=Depends(verify_admin_token)):
    """
    Garantiza que el usuario tenga rol de 'ceo'.
    """
    if user_data.role != "ceo":
        logger.warning(f"❌ 403: Role {user_data.role} is not CEO.")
        raise HTTPException(
            status_code=403, detail="Esta acción solo puede ser realizada por el CEO."
        )
    return user_data


async def verify_staff_token(user_data=Depends(verify_admin_token)):
    """
    Garantiza que el usuario sea 'ceo', 'secretary' o 'professional'.
    Uso: Operaciones administrativas de chat y gestión (según Spec 18/19).
    """
    if user_data.role not in ["ceo", "secretary", "professional"]:
        logger.warning(
            f"❌ 403: Role {user_data.role} is not authorized for staff operations."
        )
        raise HTTPException(
            status_code=403,
            detail="Esta acción requiere rol de Staff (CEO, Secretaría o Profesional).",
        )
    return user_data


def require_role(allowed_roles: List[str]):
    """
    Factory para dependencias de RBAC granular.
    """

    async def role_dependency(user_data=Depends(verify_admin_token)):
        if user_data.role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Permisos insuficientes. Se requiere uno de: {', '.join(allowed_roles)}",
            )
        return user_data

    return role_dependency


async def get_resolved_tenant_id(
    request: Request, user_data=Depends(verify_admin_token)
) -> int:
    """
    Resuelve el tenant_id real con aislamiento estricto (Spec 32):
    1. CEOs: Global Access. Usan X-Tenant-ID header para alternar sedes.
    2. Staff (Sec/Prof): Locked Access. Solo pueden acceder a su tenant_id de registro.
    """
    # Lookup real tenant_id from database
    real_tenant_id = None
    try:
        # Para profesionales y secretarios, buscar en professionals con is_active=true
        # CEO puede no tener fila en professionals
        if user_data.role in ("secretary", "professional"):
            real_tenant_id = await db.pool.fetchval(
                "SELECT tenant_id FROM professionals WHERE user_id = $1 AND is_active = true ORDER BY tenant_id ASC LIMIT 1",
                uuid.UUID(user_data.user_id),
            )
        elif user_data.role == "ceo":
            # CEO: buscar cualquier fila en professionals (aunque sea inactiva) o usar tenants
            real_tenant_id = await db.pool.fetchval(
                "SELECT tenant_id FROM professionals WHERE user_id = $1 ORDER BY tenant_id ASC LIMIT 1",
                uuid.UUID(user_data.user_id),
            )
            if real_tenant_id is None:
                # CEO sin fila en professionals: usar primera clínica
                real_tenant_id = await db.pool.fetchval(
                    "SELECT id FROM tenants ORDER BY id ASC LIMIT 1"
                )
    except Exception as e:
        logger.error(f"Error fetching real_tenant_id for {user_data.user_id}: {e}")

    # Input Header Hint
    header_tid = request.headers.get("X-Tenant-ID")

    if user_data.role == "ceo":
        # CEO: Validate header tenant_id exists before trusting it.
        if header_tid and header_tid.isdigit():
            requested_tid = int(header_tid)
            has_access = await db.pool.fetchval(
                "SELECT EXISTS(SELECT 1 FROM tenants WHERE id = $1)", requested_tid
            )
            if not has_access:
                logger.warning(
                    f"🛡️ CEO_TENANT_ACCESS_DENIED: user={user_data.email} tenant={requested_tid}"
                )
                raise HTTPException(status_code=403, detail="Tenant access denied")
            return requested_tid
        return int(real_tenant_id) if real_tenant_id is not None else 1
    else:
        # STAFF/PROF: Aislamiento estricto.
        if real_tenant_id is None:
            # Si no tiene fila en professionals (raro para staff activo), denegar acceso a datos.
            raise HTTPException(
                status_code=403,
                detail="Aislamiento Nexus: Usuario de staff sin clínica asignada.",
            )

        # Bloquear intentos de ver otros tenants
        if (
            header_tid
            and header_tid.isdigit()
            and int(header_tid) != int(real_tenant_id)
        ):
            logger.warning(
                f"🛡️ BLOQUEO NEXUS: Intento de Tenant Mismatch por {user_data.role} {user_data.email}"
            )
            # Forzamos su tenant real en lugar de lanzar error para no romper la navegación si el frontend se confunde,
            # pero garantizamos que los datos devueltos sean los correctos.

        return int(real_tenant_id)


async def log_pii_access(
    request: Request, user_data, patient_id: Any, action: str = "read_clinical_record"
):
    """
    Registra auditoría de acceso a datos sensibles (Nexus Protocol v7.6).
    """
    pid_hash = hashlib.sha256(str(patient_id).encode()).hexdigest()[:8]
    logger.info(
        f"🛡️ AUDIT: User {user_data.role} accessed PII for Patient #{pid_hash}. Action: {action}."
    )


async def get_ceo_user_and_tenant(
    user_data=Depends(verify_ceo_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
) -> Tuple[Any, int]:
    """
    Dependencia combinada para rutas que requieren rol de CEO y un tenant_id resuelto.
    Usado principalmente en módulos de Marketing y Analítica Global.
    Retorna (user_data, tenant_id).
    """
    return user_data, tenant_id
