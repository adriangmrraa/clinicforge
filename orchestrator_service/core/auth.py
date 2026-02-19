import os
import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple
from fastapi import Header, HTTPException, Depends, Request, status
from db import db
from auth_service import auth_service

logger = logging.getLogger(__name__)

# Configuración
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin-secret-token")

async def verify_admin_token(
    request: Request,
    x_admin_token: str = Header(None),
    authorization: str = Header(None)
):
    """
    Implementa la validación de doble factor para administración:
    1. Validar Token JWT (Identidad y Sesión)
    2. Validar X-Admin-Token (Autorización Estática de Infraestructura)
    """
    if x_admin_token != ADMIN_TOKEN:
        logger.warning(f"❌ 401: X-Admin-Token mismatch.")
        raise HTTPException(status_code=401, detail="Token de infraestructura (X-Admin-Token) inválido.")

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sesión no válida. Token JWT requerido.")
    
    token = authorization.split(" ")[1]
    user_data = auth_service.decode_token(token)
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Token de sesión expirado o inválido.")
    
    if user_data.role not in ['ceo', 'secretary', 'professional']:
        raise HTTPException(status_code=403, detail="No tienes permisos suficientes.")

    request.state.user = user_data
    return user_data

async def get_resolved_tenant_id(user_data=Depends(verify_admin_token)) -> int:
    """
    Resuelve el tenant_id real consultando la tabla professionals mediante el UUID del current_user.
    """
    try:
        tid = await db.pool.fetchval(
            "SELECT tenant_id FROM professionals WHERE user_id = $1",
            uuid.UUID(user_data.user_id)
        )
        if tid is not None:
            return int(tid)
    except Exception:
        pass
        
    # Fallback CEO/secretary
    tenant_id = await db.pool.fetchval("SELECT id FROM tenants ORDER BY id ASC LIMIT 1") or 1
    return int(tenant_id)

async def get_current_user_and_tenant(
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id)
) -> Tuple[Dict[str, Any], int]:
    """
    Helper para obtener el user dict y el tenant_id en una sola dependencia.
    """
    # Convertir user_data (TokenData) a dict para compatibilidad
    user_dict = {
        "id": user_data.user_id,
        "email": user_data.email,
        "role": user_data.role,
        "tenant_id": tenant_id
    }
    return user_dict, tenant_id
