import hmac
import hashlib
import time
import os
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Clave secreta para firmar URLs de medios. Debe definirse en producción via MEDIA_PROXY_SECRET.
# Si no está definida, se genera un valor aleatorio por sesión (invalida URLs firmadas al reiniciar).
_raw_secret = os.getenv("MEDIA_PROXY_SECRET", "")
if not _raw_secret:
    import uuid as _uuid
    _raw_secret = _uuid.uuid4().hex
    logger.warning(
        "⚠️ MEDIA_PROXY_SECRET no definida. Se usará un secreto temporal aleatorio. "
        "Las URLs de medios firmadas se invalidarán al reiniciar el servidor. "
        "Define MEDIA_PROXY_SECRET en las variables de entorno del orchestrator."
    )
MEDIA_PROXY_SECRET = _raw_secret
MEDIA_URL_TTL = 3600 * 24  # 24 horas de validez por defecto para medios locales

def generate_signed_url(url_path: str, tenant_id: int) -> Tuple[str, int]:
    """
    Genera una firma HMAC y un timestamp de expiración para una URL/Path.
    """
    expires = int(time.time()) + MEDIA_URL_TTL
    
    # Crear firma HMAC
    message = f"{url_path}|{tenant_id}|{expires}"
    signature = hmac.new(
        MEDIA_PROXY_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return signature, expires

def verify_signed_url(url_path: str, tenant_id: int, signature: str, expires: int) -> bool:
    """
    Verifica que la firma HMAC sea válida y no haya expirado.
    """
    # Verificar expiración
    if int(time.time()) > expires:
        return False
    
    # Verificar firma
    message = f"{url_path}|{tenant_id}|{expires}"
    expected_signature = hmac.new(
        MEDIA_PROXY_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)
