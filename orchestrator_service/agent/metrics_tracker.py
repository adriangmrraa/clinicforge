"""
Sistema de métricas y analytics del agente - FASE 2
Dashboard de performance para monitoreo del agente
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import logging
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Tipos de métricas registradas"""
    TOOL_SUCCESS = "tool_success"
    TOOL_FAILURE = "tool_failure"
    CONVERSATION_START = "conversation_start"
    CONVERSATION_END = "conversation_end"
    FALLBACK_TRIGGERED = "fallback_triggered"
    DERIVATION = "derivation"
    USER_SATISFACTION = "user_satisfaction"
    ERROR = "error"


@dataclass
class AgentMetric:
    """Métrica individual del agente"""
    metric_type: MetricType
    timestamp: datetime
    patient_id: Optional[str] = None
    tenant_id: Optional[int] = None
    tool_name: Optional[str] = None
    error_message: Optional[str] = None
    conversation_length: Optional[int] = None
    derivation_reason: Optional[str] = None
    satisfaction_score: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a dict para serialización"""
        return {
            "metric_type": self.metric_type.value,
            "timestamp": self.timestamp.isoformat(),
            "patient_id": self.patient_id,
            "tenant_id": self.tenant_id,
            "tool_name": self.tool_name,
            "error_message": self.error_message,
            "conversation_length": self.conversation_length,
            "derivation_reason": self.derivation_reason,
            "satisfaction_score": self.satisfaction_score,
            "metadata": self.metadata
        }


class MetricsTracker:
    """Tracker de métricas del agente con almacenamiento en memoria"""
    
    def __init__(self, retention_days: int = 30):
        self.metrics: List[AgentMetric] = []
        self.retention_days = retention_days
        self._lock = asyncio.Lock()
        
        # Estadísticas en tiempo real
        self.tool_stats = defaultdict(lambda: {"success": 0, "failure": 0})
        self.conversation_stats = {
            "total": 0,
            "avg_length": 0.0,
            "completed": 0
        }
        self.derivation_stats = defaultdict(int)
        self.error_stats = defaultdict(int)
        
        # Iniciar limpieza periódica
        asyncio.create_task(self._periodic_cleanup())
    
    async def _periodic_cleanup(self):
        """Limpia métricas antiguas periódicamente"""
        while True:
            await asyncio.sleep(3600)  # Cada hora
            await self.cleanup_old_metrics()
    
    async def cleanup_old_metrics(self):
        """Elimina métricas más antiguas que retention_days"""
        async with self._lock:
            cutoff_date = datetime.now() - timedelta(days=self.retention_days)
            initial_count = len(self.metrics)
            
            self.metrics = [
                metric for metric in self.metrics 
                if metric.timestamp > cutoff_date
            ]
            
            removed = initial_count - len(self.metrics)
            if removed > 0:
                logger.info(f"Limpieza de métricas: {removed} métricas antiguas eliminadas")
    
    async def record_metric(self, metric: AgentMetric):
        """Registra una nueva métrica"""
        async with self._lock:
            self.metrics.append(metric)
            
            # Actualizar estadísticas en tiempo real
            self._update_real_time_stats(metric)
            
            logger.debug(f"Métrica registrada: {metric.metric_type.value}")
    
    def _update_real_time_stats(self, metric: AgentMetric):
        """Actualiza estadísticas en tiempo real"""
        if metric.metric_type == MetricType.TOOL_SUCCESS:
            if metric.tool_name:
                self.tool_stats[metric.tool_name]["success"] += 1
        
        elif metric.metric_type == MetricType.TOOL_FAILURE:
            if metric.tool_name:
                self.tool_stats[metric.tool_name]["failure"] += 1
        
        elif metric.metric_type == MetricType.CONVERSATION_START:
            self.conversation_stats["total"] += 1
        
        elif metric.metric_type == MetricType.CONVERSATION_END:
            self.conversation_stats["completed"] += 1
            if metric.conversation_length:
                # Actualizar promedio móvil
                current_avg = self.conversation_stats["avg_length"]
                completed = self.conversation_stats["completed"]
                self.conversation_stats["avg_length"] = (
                    (current_avg * (completed - 1) + metric.conversation_length) / completed
                )
        
        elif metric.metric_type == MetricType.DERIVATION:
            if metric.derivation_reason:
                self.derivation_stats[metric.derivation_reason] += 1
        
        elif metric.metric_type == MetricType.ERROR:
            if metric.error_message:
                # Extraer tipo de error del mensaje
                error_type = self._extract_error_type(metric.error_message)
                self.error_stats[error_type] += 1
    
    def _extract_error_type(self, error_message: str) -> str:
        """Extrae tipo de error del mensaje"""
        error_lower = error_message.lower()
        
        if "fecha" in error_lower or "date" in error_lower:
            return "date_format"
        elif "dni" in error_lower:
            return "dni_format"
        elif "tratamiento" in error_lower or "treatment" in error_lower:
            return "treatment_not_found"
        elif "disponibilidad" in error_lower or "availability" in error_lower:
            return "availability_error"
        elif "validación" in error_lower or "validation" in error_lower:
            return "validation_error"
        else:
            return "general_error"
    
    async def get_agent_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        Obtiene métricas del agente para el dashboard
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        async with self._lock:
            recent_metrics = [
                metric for metric in self.metrics 
                if metric.timestamp > cutoff_date
            ]
            
            return self._calculate_metrics_summary(recent_metrics)
    
    def _calculate_metrics_summary(self, metrics: List[AgentMetric]) -> Dict[str, Any]:
        """Calcula resumen de métricas"""
        # Calcular éxito de herramientas
        tool_success_rates = {}
        for tool_name, stats in self.tool_stats.items():
            total = stats["success"] + stats["failure"]
            if total > 0:
                success_rate = (stats["success"] / total) * 100
                tool_success_rates[tool_name] = {
                    "success_rate": round(success_rate, 2),
                    "success_count": stats["success"],
                    "failure_count": stats["failure"],
                    "total_calls": total
                }
        
        # Calcular razones de derivación
        derivation_reasons = dict(self.derivation_stats)
        
        # Calcular errores comunes
        common_failures = []
        for error_type, count in self.error_stats.items():
            if count > 0:
                common_failures.append({
                    "error_type": error_type,
                    "count": count
                })
        
        # Ordenar por frecuencia
        common_failures.sort(key=lambda x: x["count"], reverse=True)
        
        return {
            "tool_success_rate": tool_success_rates,
            "conversation_length": round(self.conversation_stats["avg_length"], 1),
            "conversation_stats": {
                "total": self.conversation_stats["total"],
                "completed": self.conversation_stats["completed"],
                "completion_rate": (
                    (self.conversation_stats["completed"] / self.conversation_stats["total"] * 100)
                    if self.conversation_stats["total"] > 0 else 0
                )
            },
            "derivation_reasons": derivation_reasons,
            "derivation_rate": (
                (sum(derivation_reasons.values()) / self.conversation_stats["total"] * 100)
                if self.conversation_stats["total"] > 0 else 0
            ),
            "common_failures": common_failures[:10],  # Top 10 errores
            "metrics_collected": len(metrics),
            "time_period_days": 7  # Por defecto
        }
    
    async def record_tool_success(self, tool_name: str, patient_id: str = None, 
                                 tenant_id: int = None, metadata: Dict = None):
        """Registra éxito de herramienta"""
        metric = AgentMetric(
            metric_type=MetricType.TOOL_SUCCESS,
            timestamp=datetime.now(),
            patient_id=patient_id,
            tenant_id=tenant_id,
            tool_name=tool_name,
            metadata=metadata or {}
        )
        await self.record_metric(metric)
    
    async def record_tool_failure(self, tool_name: str, error_message: str,
                                 patient_id: str = None, tenant_id: int = None,
                                 metadata: Dict = None):
        """Registra fallo de herramienta"""
        metric = AgentMetric(
            metric_type=MetricType.TOOL_FAILURE,
            timestamp=datetime.now(),
            patient_id=patient_id,
            tenant_id=tenant_id,
            tool_name=tool_name,
            error_message=error_message,
            metadata=metadata or {}
        )
        await self.record_metric(metric)
    
    async def record_conversation_start(self, patient_id: str, tenant_id: int):
        """Registra inicio de conversación"""
        metric = AgentMetric(
            metric_type=MetricType.CONVERSATION_START,
            timestamp=datetime.now(),
            patient_id=patient_id,
            tenant_id=tenant_id
        )
        await self.record_metric(metric)
    
    async def record_conversation_end(self, patient_id: str, tenant_id: int,
                                     conversation_length: int):
        """Registra fin de conversación"""
        metric = AgentMetric(
            metric_type=MetricType.CONVERSATION_END,
            timestamp=datetime.now(),
            patient_id=patient_id,
            tenant_id=tenant_id,
            conversation_length=conversation_length
        )
        await self.record_metric(metric)
    
    async def record_fallback(self, patient_id: str, tenant_id: int):
        """Registra activación de fallback"""
        metric = AgentMetric(
            metric_type=MetricType.FALLBACK_TRIGGERED,
            timestamp=datetime.now(),
            patient_id=patient_id,
            tenant_id=tenant_id
        )
        await self.record_metric(metric)
    
    async def record_derivation(self, patient_id: str, tenant_id: int,
                               reason: str):
        """Registra derivación a humano"""
        metric = AgentMetric(
            metric_type=MetricType.DERIVATION,
            timestamp=datetime.now(),
            patient_id=patient_id,
            tenant_id=tenant_id,
            derivation_reason=reason
        )
        await self.record_metric(metric)
    
    async def record_error(self, error_message: str, patient_id: str = None,
                          tenant_id: int = None):
        """Registra error general"""
        metric = AgentMetric(
            metric_type=MetricType.ERROR,
            timestamp=datetime.now(),
            patient_id=patient_id,
            tenant_id=tenant_id,
            error_message=error_message
        )
        await self.record_metric(metric)
    
    async def export_metrics(self, format: str = "json") -> str:
        """Exporta métricas en formato especificado"""
        async with self._lock:
            metrics_dict = [metric.to_dict() for metric in self.metrics]
            
            if format == "json":
                return json.dumps(metrics_dict, indent=2, ensure_ascii=False)
            else:
                raise ValueError(f"Formato no soportado: {format}")


# Instancia global del tracker de métricas
metrics_tracker = MetricsTracker()


# Funciones de conveniencia para uso en el agente
async def track_tool_call(tool_name: str, success: bool, 
                         error_message: str = None,
                         patient_id: str = None, 
                         tenant_id: int = None,
                         metadata: Dict = None):
    """Trackea llamada a herramienta"""
    if success:
        await metrics_tracker.record_tool_success(
            tool_name, patient_id, tenant_id, metadata
        )
    else:
        await metrics_tracker.record_tool_failure(
            tool_name, error_message, patient_id, tenant_id, metadata
        )


async def track_conversation(patient_id: str, tenant_id: int, 
                            start: bool = True, 
                            length: int = None):
    """Trackea conversación"""
    if start:
        await metrics_tracker.record_conversation_start(patient_id, tenant_id)
    else:
        if length is None:
            logger.warning("Longitud de conversación no proporcionada para tracking")
        else:
            await metrics_tracker.record_conversation_end(patient_id, tenant_id, length)


async def get_agent_performance_report(days: int = 7) -> Dict[str, Any]:
    """Obtiene reporte de performance del agente"""
    return await metrics_tracker.get_agent_metrics(days)


async def save_metrics_to_database(db_pool):
    """Guarda métricas en base de datos para persistencia"""
    try:
        metrics_json = await metrics_tracker.export_metrics("json")
        
        await db_pool.execute("""
            INSERT INTO agent_metrics_snapshot 
            (snapshot_data, created_at)
            VALUES ($1, NOW())
        """, metrics_json)
        
        logger.info("Métricas guardadas en BD")
        
    except Exception as e:
        logger.error(f"Error guardando métricas en BD: {e}")