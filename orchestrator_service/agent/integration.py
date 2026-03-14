"""
Integración Simplificada - Bridge para sistema mejorado
"""
import logging

logger = logging.getLogger(__name__)

class EnhancedAgentSystem:
    def __init__(self):
        logger.info("Sistema mejorado inicializado (modo simplificado)")
    
    async def build_optimized_prompt(self, context):
        """Fallback al prompt original - compatible inmediato"""
        from main import build_system_prompt_fallback
        return build_system_prompt_fallback(
            context.get("clinic_name", "Clínica Dental"),
            context.get("current_time", ""),
            context.get("response_language", "es"),
            context.get("hours_start", "08:00"),
            context.get("hours_end", "19:00"),
            context.get("ad_context", ""),
            context.get("patient_context", "")
        )
    
    async def get_system_metrics(self, days=7):
        return {
            "status": "simplified",
            "message": "Sistema mejorado en modo compatible",
            "timestamp": "2026-03-14T20:00:00Z"
        }

enhanced_system = EnhancedAgentSystem()
