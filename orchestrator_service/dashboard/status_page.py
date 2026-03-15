"""
Status Page Simple - Dashboard CEO integrado con autenticación existente
"""

import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

from .auth_integrated import ceo_access_required, ceo_api_access, get_current_user

logger = logging.getLogger(__name__)

# Configurar templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)

templates = Jinja2Templates(directory=templates_dir)

# Crear router para el dashboard
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Dashboard principal - Solo requiere autenticación existente
@router.get("/status", response_class=HTMLResponse)
async def status_dashboard(
    request: Request,
    days: int = 30,
    _: bool = Depends(ceo_access_required)  # ← Usa autenticación existente
):
    """
    Dashboard de status para CEO
    URL: https://app.dralauradelgado.com/dashboard/status
    Acceso: Cualquier usuario autenticado en ClinicForge
    """
    try:
        # Obtener información del usuario actual
        user = get_current_user(request)
        
        # Obtener métricas del sistema (si están disponibles)
        try:
            from .token_tracker import token_tracker
            from .config_manager import config_manager
            from agent.integration import enhanced_system
            
            token_metrics = await token_tracker.get_total_metrics(tenant_id=1, days=days)
            daily_usage = await token_tracker.get_daily_usage(tenant_id=1, days=days)
            model_usage = await token_tracker.get_model_usage(tenant_id=1, days=days)
            available_models = await token_tracker.get_available_models()
            current_config = await config_manager.get_all_config(tenant_id=1)
            system_metrics = await enhanced_system.get_system_metrics(days=days)
            
            # Obtener estadísticas de la base de datos
            from db import db
            db_stats = await get_database_stats()
            
            # Calcular proyecciones
            projections = calculate_projections(token_metrics)
            
            metrics_available = True
            
        except ImportError as e:
            logger.warning(f"⚠️ Módulos del dashboard no disponibles: {e}")
            # Datos de ejemplo para desarrollo
            token_metrics = {
                "totals": {
                    "total_cost_usd": 0.0,
                    "total_tokens": 0,
                    "total_conversations": 0,
                    "avg_tokens_per_conversation": 0,
                    "avg_cost_per_conversation": 0
                },
                "today": {
                    "cost_usd": 0.0,
                    "total_tokens": 0,
                    "conversations": 0
                },
                "current_month": {
                    "cost_usd": 0.0
                }
            }
            daily_usage = []
            model_usage = []
            available_models = []
            current_config = {}
            system_metrics = {"status": "simplified"}
            db_stats = {}
            projections = {}
            metrics_available = False
        
        # Preparar contexto para el template
        context = {
            "request": request,
            "current_time": datetime.now().isoformat(),
            "user_authenticated": user["authenticated"],
            "metrics_available": metrics_available,
            "token_metrics": token_metrics,
            "daily_usage": daily_usage,
            "model_usage": model_usage,
            "available_models": available_models,
            "current_config": current_config,
            "system_metrics": system_metrics,
            "db_stats": db_stats,
            "projections": projections,
            "days": days
        }
        
        return templates.TemplateResponse("status_simple.html", context)
        
    except Exception as e:
        logger.error(f"❌ Error generando dashboard: {e}")
        # Fallback a página simple de error
        return HTMLResponse(f"""
        <html>
            <head><title>Error Dashboard</title></head>
            <body>
                <h1>Error en Dashboard CEO</h1>
                <p>{str(e)}</p>
                <p><a href="/">Volver al inicio</a></p>
            </body>
        </html>
        """)

# APIs protegidas
@router.get("/api/metrics")
async def get_dashboard_metrics(
    request: Request,
    days: int = 30,
    _: bool = Depends(ceo_api_access)
):
    """API para obtener métricas del dashboard (JSON)"""
    try:
        # Intentar cargar módulos
        try:
            from .token_tracker import token_tracker
            from .config_manager import config_manager
            from agent.integration import enhanced_system
            
            token_metrics = await token_tracker.get_total_metrics(tenant_id=1, days=days)
            daily_usage = await token_tracker.get_daily_usage(tenant_id=1, days=days)
            model_usage = await token_tracker.get_model_usage(tenant_id=1, days=days)
            current_config = await config_manager.get_all_config(tenant_id=1)
            system_metrics = await enhanced_system.get_system_metrics(days=days)
            db_stats = await get_database_stats()
            
            return {
                "timestamp": datetime.now().isoformat(),
                "token_metrics": token_metrics,
                "daily_usage": daily_usage,
                "model_usage": model_usage,
                "current_config": current_config,
                "system_metrics": system_metrics,
                "db_stats": db_stats,
                "projections": calculate_projections(token_metrics)
            }
            
        except ImportError:
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "modules_not_available",
                "message": "Módulos del dashboard no cargados correctamente"
            }
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo métricas: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post("/api/config", tags=["Dashboard"])
async def update_dashboard_config(
    request: Request,
    payload: Dict[str, Any],
    _: bool = Depends(ceo_api_access)
):
    """Actualiza configuración (OPENAI_MODEL, etc.). Fuente de verdad: system_config en DB."""
    try:
        from .config_manager import config_manager
        if config_manager is None:
            raise HTTPException(status_code=503, detail="Config manager no inicializado")
        tenant_id = 1
        allowed = {"OPENAI_MODEL", "OPENAI_TEMPERATURE", "MAX_TOKENS_PER_RESPONSE"}
        for key, value in payload.items():
            if key in allowed:
                if isinstance(value, str) and key == "OPENAI_MODEL":
                    await config_manager.set_config(key, value.strip(), data_type="string", category="ai", tenant_id=tenant_id)
                elif key == "OPENAI_TEMPERATURE":
                    await config_manager.set_config(key, str(float(value)), data_type="float", category="ai", tenant_id=tenant_id)
                elif key == "MAX_TOKENS_PER_RESPONSE":
                    await config_manager.set_config(key, str(int(value)), data_type="integer", category="ai", tenant_id=tenant_id)
                logger.info(f"✅ {key} actualizado a: {value}")
        return {"status": "ok", "message": "Configuración actualizada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error actualizando config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Funciones auxiliares
async def get_database_stats() -> Dict[str, Any]:
    """Obtiene estadísticas de la base de datos"""
    try:
        from db import db
        
        stats = {}
        
        async with db.pool.acquire() as conn:
            # Contar pacientes
            patients_row = await conn.fetchrow("SELECT COUNT(*) as count FROM patients WHERE tenant_id = 1")
            stats["total_patients"] = patients_row["count"] if patients_row else 0
            
            # Contar conversaciones
            convs_row = await conn.fetchrow("SELECT COUNT(*) as count FROM conversations WHERE tenant_id = 1")
            stats["total_conversations"] = convs_row["count"] if convs_row else 0
            
            # Contar turnos
            apps_row = await conn.fetchrow("SELECT COUNT(*) as count FROM appointments WHERE tenant_id = 1")
            stats["total_appointments"] = apps_row["count"] if apps_row else 0
            
            # Turnos próximos (próximos 7 días)
            upcoming_row = await conn.fetchrow("""
                SELECT COUNT(*) as count 
                FROM appointments 
                WHERE tenant_id = 1 
                AND status NOT IN ('cancelled', 'no-show')
                AND appointment_datetime >= NOW() 
                AND appointment_datetime <= NOW() + INTERVAL '7 days'
            """)
            stats["upcoming_appointments"] = upcoming_row["count"] if upcoming_row else 0
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo estadísticas de BD: {e}")
        return {}

def calculate_projections(token_metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Calcula proyecciones basadas en métricas actuales"""
    try:
        totals = token_metrics.get("totals", {})
        today = token_metrics.get("today", {})
        current_month = token_metrics.get("current_month", {})
        
        # Proyección mensual basada en hoy
        today_cost = today.get("cost_usd", 0)
        days_in_month = datetime.now().day
        avg_daily_cost_this_month = current_month.get("cost_usd", 0) / max(days_in_month, 1)
        
        # Proyecciones
        days_remaining = 30 - days_in_month
        projected_monthly_cost = current_month.get("cost_usd", 0) + (avg_daily_cost_this_month * days_remaining)
        
        # Proyección anual
        projected_annual_cost = projected_monthly_cost * 12
        
        # Eficiencia de tokens (tokens por conversación)
        avg_tokens_per_conv = totals.get("avg_tokens_per_conversation", 0)
        avg_cost_per_conv = totals.get("avg_cost_per_conversation", 0)
        
        return {
            "projected_monthly_cost_usd": round(projected_monthly_cost, 2),
            "projected_annual_cost_usd": round(projected_annual_cost, 2),
            "avg_daily_cost_this_month": round(avg_daily_cost_this_month, 4),
            "avg_tokens_per_conversation": round(avg_tokens_per_conv, 2),
            "avg_cost_per_conversation": round(avg_cost_per_conv, 4),
            "cost_per_1000_tokens": round((totals.get("total_cost_usd", 0) / max(totals.get("total_tokens", 1), 1)) * 1000, 4),
            "efficiency_score": calculate_efficiency_score(avg_tokens_per_conv, avg_cost_per_conv)
        }
    except Exception as e:
        logger.error(f"❌ Error calculando proyecciones: {e}")
        return {}

def calculate_efficiency_score(avg_tokens: float, avg_cost: float) -> float:
    """Calcula score de eficiencia (0-100)"""
    try:
        token_score = max(0, min(100, (1000 - avg_tokens) / 10))
        cost_score = max(0, min(100, (0.05 - avg_cost) * 2000))
        efficiency_score = (token_score * 0.6) + (cost_score * 0.4)
        return round(efficiency_score, 1)
    except:
        return 0.0