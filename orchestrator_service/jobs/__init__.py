"""
Módulo de jobs programados para ClinicForge.

Jobs disponibles:
- reminders: Recordatorios automáticos de turnos por WhatsApp
- followups: Seguimiento post-atención para pacientes de cirugía
- lead_recovery: Recuperación de leads que no agendaron
- nova_morning: Resumen matutino diario via Telegram (hora configurable por tenant)
- smart_alerts: Alertas proactivas cada 4h (no-shows, sin confirmar, morosidad)
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

try:
    from . import nova_morning
    logger.info("✅ Job de resumen matutino Nova importado correctamente")
except ImportError as e:
    logger.warning(f"⚠️ No se pudo importar job nova_morning: {e}")

try:
    from . import smart_alerts
    logger.info("✅ Job de alertas inteligentes importado correctamente")
except ImportError as e:
    logger.warning(f"⚠️ No se pudo importar job smart_alerts: {e}")

try:
    from . import expire_unpaid
    logger.info("✅ Job de expiración de seña importado correctamente")
except ImportError as e:
    logger.warning(f"⚠️ No se pudo importar job expire_unpaid: {e}")

try:
    from . import playbook_executor
    logger.info("✅ Job de playbook executor importado correctamente")
except ImportError as e:
    logger.warning(f"⚠️ No se pudo importar job playbook_executor: {e}")

try:
    from . import business_insights
    logger.info("✅ Job de business insights importado correctamente")
except ImportError as e:
    logger.warning(f"⚠️ No se pudo importar job business_insights: {e}")

__all__ = ['reminders', 'followups', 'lead_recovery', 'nova_morning', 'smart_alerts', 'expire_unpaid', 'playbook_executor']