"""
Spec 11: Sanitización de Logs
Filtro de logging que ofusca tokens, secrets y PII antes de escribir
en el log. Se aplica como filtro global al root logger.

CLINICASV1.0 - Integración Meta Ads & Dentalogic.
"""
import logging
import re
from typing import List, Tuple

# Patrones de sanitización: (regex_compilado, texto_reemplazo)
_SANITIZE_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # access_token en query params (ej. ?access_token=EAABxxx...)
    (re.compile(r'(access_token=)[^\s&"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    # META_ADS_TOKEN o cualquier header con "Token" / "Authorization"
    (re.compile(r'(META_ADS_TOKEN[:\s=]+)[^\s,;"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    (re.compile(r'(Authorization[:\s]+(?:Bearer\s)?)[^\s,;"\']+', re.IGNORECASE), r'\1[REDACTED]'),
    # Claves genéricas sensibles: token, secret, password, key, api_key
    (re.compile(
        r'("(?:token|secret|password|api_key|private_key|fernet_key|credentials_fernet_key)"'
        r'\s*:\s*")[^"]+(")',
        re.IGNORECASE
    ), r'\1[REDACTED]\2'),
    # Formato key=value para variables de entorno logueadas
    (re.compile(
        r'((?:token|secret|password|api_key|private_key|fernet_key|META_ADS_TOKEN)'
        r'\s*=\s*)[^\s,;]+',
        re.IGNORECASE
    ), r'\1[REDACTED]'),
]


def sanitize_message(message: str) -> str:
    """Aplica todos los patrones de sanitización a un mensaje."""
    for pattern, replacement in _SANITIZE_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


class SensitiveDataFilter(logging.Filter):
    """
    Filtro de logging que intercepta cada record y sanitiza el mensaje
    formateado antes de que llegue al handler.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        # Sanitizar el mensaje principal
        if isinstance(record.msg, str):
            record.msg = sanitize_message(record.msg)

        # Sanitizar args si contienen strings
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: sanitize_message(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    sanitize_message(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )

        return True  # Siempre permite el record; solo lo transforma


def install_log_sanitizer() -> None:
    """
    Instala el filtro de sanitización en el root logger.
    Debe llamarse DESPUÉS de logging.basicConfig() en main.py.
    """
    root_logger = logging.getLogger()
    sanitizer = SensitiveDataFilter()
    root_logger.addFilter(sanitizer)

    # También instalar en cada handler existente
    for handler in root_logger.handlers:
        handler.addFilter(sanitizer)

    logging.getLogger(__name__).info("🛡️ Log sanitizer instalado correctamente.")
