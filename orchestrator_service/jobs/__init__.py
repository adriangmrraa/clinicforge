"""
Módulo de jobs programados para ClinicForge.

Jobs disponibles:
- reminders: Recordatorios automáticos de turnos por WhatsApp
- followups: Seguimiento post-atención para pacientes de cirugía
- lead_recovery: Recuperación de leads que no agendaron
"""

import logging

logger = logging.getLogger(__name__)

# Importar jobs para que se registren automáticamente
try:
    from . import reminders
    logger.info("✅ Job de recordatorios importado correctamente")
except ImportError as e:
    logger.warning(f"⚠️ No se pudo importar job de recordatorios: {e}")

try:
    from . import followups
    logger.info("✅ Job de seguimiento post-atención importado correctamente")
except ImportError as e:
    logger.warning(f"⚠️ No se pudo importar job de seguimiento: {e}")

try:
    from . import lead_recovery
    logger.info("✅ Job de recuperación de leads importado correctamente")
except ImportError as e:
    logger.warning(f"⚠️ No se pudo importar job de recuperación de leads: {e}")

__all__ = ['reminders', 'followups', 'lead_recovery']