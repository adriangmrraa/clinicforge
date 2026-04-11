"""
Endpoints de administración para jobs programados.
Permiten probar y monitorear los jobs manualmente.

CLINICASV1.0 - Panel de Control de Jobs
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from .reminders import send_appointment_reminders
from .followups import send_post_treatment_followups

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/jobs", tags=["Jobs Programados"])


@router.post("/reminders/test-today")
async def test_reminders_today():
    """
    Endpoint para probar el job de recordatorios con turnos de hoy.
    Útil para testing sin esperar a la ejecución programada.
    
    Returns:
        Dict con resultado del test
    """
    logger.info("🧪 Solicitado test manual de recordatorios")
    
    try:
        await send_appointment_reminders()
        return {
            "status": "success",
            "message": "Test de recordatorios ejecutado correctamente",
            "details": "Se ejecutó el job de recordatorios. Revisar logs para detalles."
        }
            
    except Exception as e:
        logger.error(f"❌ Error en test manual: {e}")
        raise HTTPException(status_code=500, detail=f"Error en test: {str(e)}")


@router.post("/reminders/run-now")
async def run_reminders_now():
    """
    Ejecuta el job de recordatorios inmediatamente.
    Buscará turnos para mañana y enviará recordatorios.
    
    Returns:
        Dict con estadísticas de la ejecución
    """
    logger.info("🚀 Solicitada ejecución manual de recordatorios")
    
    try:
        await send_appointment_reminders()
        
        return {
            "status": "success",
            "message": "Job de recordatorios ejecutado manualmente",
            "details": "Revisar logs para ver detalles de la ejecución"
        }
        
    except Exception as e:
        logger.error(f"❌ Error en ejecución manual: {e}")
        raise HTTPException(status_code=500, detail=f"Error en ejecución: {str(e)}")


@router.get("/reminders/status")
async def get_reminders_status():
    """
    Obtiene información sobre el estado del job de recordatorios.
    
    Returns:
        Dict con información de configuración y próximas ejecuciones
    """
    from datetime import datetime, timedelta
    
    # Calcular próxima ejecución (10:00 AM del día siguiente)
    now = datetime.now()
    tomorrow = now.date() + timedelta(days=1)
    next_execution = datetime.combine(tomorrow, datetime.strptime("10:00", "%H:%M").time())
    
    if now.time() < datetime.strptime("10:00", "%H:%M").time():
        # Si aún no son las 10:00, ejecutar hoy
        next_execution = datetime.combine(now.date(), datetime.strptime("10:00", "%H:%M").time())
    
    seconds_until_next = (next_execution - now).total_seconds()
    
    return {
        "job": "appointment_reminders",
        "enabled": True,
        "schedule": "Diario a las 10:00 AM",
        "next_execution": next_execution.isoformat(),
        "seconds_until_next": int(seconds_until_next),
        "description": "Envía recordatorios de turnos para el día siguiente",
        "endpoints": {
            "test": "/admin/jobs/reminders/test-today",
            "run_now": "/admin/jobs/reminders/run-now"
        }
    }


@router.post("/followups/test-today")
async def test_followups_today():
    """
    Endpoint para probar el job de seguimiento post-atención con turnos de hoy.
    
    Returns:
        Dict con resultado del test
    """
    logger.info("🧪 Solicitado test manual de seguimiento post-atención")
    
    try:
        await send_post_treatment_followups()
        return {
            "status": "success",
            "message": "Test de seguimiento ejecutado correctamente",
            "details": "Se ejecutó el job de followups. Revisar logs para detalles."
        }
            
    except Exception as e:
        logger.error(f"❌ Error en test manual de seguimiento: {e}")
        raise HTTPException(status_code=500, detail=f"Error en test: {str(e)}")


@router.post("/followups/run-now")
async def run_followups_now():
    """
    Ejecuta el job de seguimiento post-atención inmediatamente.
    Buscará turnos completados ayer y enviará seguimientos.
    
    Returns:
        Dict con estadísticas de la ejecución
    """
    logger.info("🚀 Solicitada ejecución manual de seguimiento post-atención")
    
    try:
        await send_post_treatment_followups()
        
        return {
            "status": "success",
            "message": "Job de seguimiento post-atención ejecutado manualmente",
            "details": "Revisar logs para ver detalles de la ejecución"
        }
        
    except Exception as e:
        logger.error(f"❌ Error en ejecución manual de seguimiento: {e}")
        raise HTTPException(status_code=500, detail=f"Error en ejecución: {str(e)}")


@router.get("/followups/status")
async def get_followups_status():
    """
    Obtiene información sobre el estado del job de seguimiento post-atención.
    
    Returns:
        Dict con información de configuración y próximas ejecuciones
    """
    from datetime import datetime, timedelta
    
    # Calcular próxima ejecución (11:00 AM del día siguiente)
    now = datetime.now()
    tomorrow = now.date() + timedelta(days=1)
    next_execution = datetime.combine(tomorrow, datetime.strptime("11:00", "%H:%M").time())
    
    if now.time() < datetime.strptime("11:00", "%H:%M").time():
        # Si aún no son las 11:00, ejecutar hoy
        next_execution = datetime.combine(now.date(), datetime.strptime("11:00", "%H:%M").time())
    
    seconds_until_next = (next_execution - now).total_seconds()
    
    return {
        "job": "post_treatment_followups",
        "enabled": True,
        "schedule": "Diario a las 11:00 AM",
        "next_execution": next_execution.isoformat(),
        "seconds_until_next": int(seconds_until_next),
        "description": "Envía seguimiento post-atención a pacientes atendidos ayer",
        "criteria": {
            "status": "completed",
            "date": "ayer (fecha actual - 1 día)",
            "excludes": "consultation (solo tratamientos/cirugías)",
            "requires": "phone_number no nulo, followup_sent = false"
        },
        "message_template": "Hola [Nombre], soy la asistente de la Dra. Delgado. Te escribo para saber cómo te sentís hoy después de la atención de ayer ([Fecha]). ¿Tuviste alguna molestia o va todo bien?",
        "agent_integration": {
            "triage_activation": "Si el paciente responde, el agente LLM evalúa triage de urgencia",
            "rules_applied": "6 reglas maxilofaciales configuradas previamente"
        },
        "endpoints": {
            "test": "/admin/jobs/followups/test-today",
            "run_now": "/admin/jobs/followups/run-now"
        }
    }


@router.get("/scheduler/status")
async def get_scheduler_status():
    """
    Obtiene información sobre el estado del scheduler.
    
    Returns:
        Dict con información del scheduler y jobs registrados
    """
    try:
        from .scheduler import scheduler
        
        jobs_info = []
        for task_func, interval_seconds, run_at_startup in scheduler.tasks:
            jobs_info.append({
                "name": task_func.__name__ if hasattr(task_func, '__name__') else str(task_func),
                "interval_seconds": interval_seconds,
                "run_at_startup": run_at_startup,
                "description": task_func.__doc__ or "Sin descripción"
            })
        
        return {
            "scheduler": {
                "running": scheduler.running,
                "total_jobs": len(scheduler.tasks),
                "jobs": jobs_info
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estado del scheduler: {e}")
        return {
            "scheduler": {
                "running": False,
                "error": str(e),
                "total_jobs": 0,
                "jobs": []
            }
        }