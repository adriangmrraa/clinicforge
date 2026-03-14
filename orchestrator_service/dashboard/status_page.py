"""
Status Page - Dashboard privado para el CEO con autenticación automática
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
import os

from .auth_middleware import (
    ceo_auth_required,
    ceo_api_auth,
    create_login_response,
    create_logout_response,
    get_ceo_session,
    ceo_context
)

logger = logging.getLogger(__name__)

# Configurar templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)

templates = Jinja2Templates(directory=templates_dir)

# Crear router para el dashboard
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Página de login
@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Página de login para CEO"""
    # Si ya está autenticado, redirigir al dashboard
    if get_ceo_session(request):
        return RedirectResponse(url="/dashboard/status", status_code=302)
    
    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": None
    })

@router.post("/login")
async def login_submit(
    request: Request,
    access_key: str = Form(...)
):
    """Endpoint para submit de login"""
    from .auth_middleware import CEO_ACCESS_KEY
    
    if access_key == CEO_ACCESS_KEY:
        from .auth_middleware import session_manager
        session_id = session_manager.create_session(request)
        return create_login_response(session_id, "/dashboard/status")
    else:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": "Clave de acceso incorrecta"
        })

@router.get("/logout")
async def logout():
    """Endpoint para logout"""
    return create_logout_response()

# Dashboard principal - ahora con autenticación automática
@router.get("/status", response_class=HTMLResponse)
async def status_dashboard(
    request: Request,
    days: int = 30,
    session_id: str = Depends(ceo_auth_required)  # ← Autenticación automática
):
    """
    Dashboard de status privado para el CEO
    URL: https://app.dralauradelgado.com/dashboard/status
    """
    try:
        # Obtener métricas del sistema
        from .token_tracker import token_tracker
        from .config_manager import config_manager
        from agent.integration import enhanced_system
        
        # Obtener métricas de tokens
        token_metrics = await token_tracker.get_total_metrics(tenant_id=1, days=days)
        daily_usage = await token_tracker.get_daily_usage(tenant_id=1, days=days)
        model_usage = await token_tracker.get_model_usage(tenant_id=1, days=days)
        available_models = await token_tracker.get_available_models()
        
        # Obtener configuración actual
        current_config = await config_manager.get_all_config(tenant_id=1)
        config_by_category = await config_manager.get_config_by_category(tenant_id=1)
        
        # Obtener métricas del sistema mejorado
        system_metrics = await enhanced_system.get_system_metrics(days=days)
        
        # Obtener estadísticas de la base de datos
        from core import db
        db_stats = await get_database_stats()
        
        # Calcular proyecciones
        projections = calculate_projections(token_metrics)
        
        # Obtener contexto de autenticación
        auth_context = await ceo_context(request)
        
        # Preparar contexto para el template
        context = {
            "request": request,
            "current_time": datetime.now().isoformat(),
            "token_metrics": token_metrics,
            "daily_usage": daily_usage,
            "model_usage": model_usage,
            "available_models": available_models,
            "current_config": current_config,
            "config_by_category": config_by_category,
            "system_metrics": system_metrics,
            "db_stats": db_stats,
            "projections": projections,
            "days": days,
            **auth_context  # Inyectar contexto de autenticación
        }
        
        return templates.TemplateResponse("status.html", context)
        
    except Exception as e:
        logger.error(f"❌ Error generando dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# APIs protegidas
@router.get("/api/metrics")
async def get_dashboard_metrics(
    request: Request,
    days: int = 30,
    session_id: str = Depends(ceo_api_auth)  # ← Autenticación para API
):
    """API para obtener métricas del dashboard (JSON)"""
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
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo métricas: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.post("/api/config")
async def update_config(
    request: Request,
    config_updates: Dict[str, Any],
    session_id: str = Depends(ceo_api_auth)
):
    """API para actualizar configuración desde el dashboard"""
    try:
        from .config_manager import config_manager
        
        results = {}
        for key, value in config_updates.items():
            success = await config_manager.set_config(
                key=key,
                value=value,
                tenant_id=1,
                updated_by="ceo_dashboard"
            )
            results[key] = success
        
        return {
            "success": all(results.values()),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"❌ Error actualizando configuración: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/api/models")
async def get_available_models_api(
    request: Request,
    session_id: str = Depends(ceo_api_auth)
):
    """API para obtener modelos disponibles"""
    try:
        from .token_tracker import token_tracker
        models = await token_tracker.get_available_models()
        return {"models": models}
    except Exception as e:
        logger.error(f"❌ Error obteniendo modelos: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Funciones auxiliares
async def get_database_stats() -> Dict[str, Any]:
    """Obtiene estadísticas de la base de datos"""
    try:
        from core import db
        
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
                AND date_time >= NOW() 
                AND date_time <= NOW() + INTERVAL '7 days'
            """)
            stats["upcoming_appointments"] = upcoming_row["count"] if upcoming_row else 0
            
            # Pacientes nuevos este mes
            new_patients_row = await conn.fetchrow("""
                SELECT COUNT(*) as count 
                FROM patients 
                WHERE tenant_id = 1 
                AND created_at >= DATE_TRUNC('month', CURRENT_DATE)
            """)
            stats["new_patients_this_month"] = new_patients_row["count"] if new_patients_row else 0
        
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
        # Tokens ideales por conversación: 500-1000
        # Costo ideal por conversación: $0.01-$0.05
        
        token_score = max(0, min(100, (1000 - avg_tokens) / 10))
        cost_score = max(0, min(100, (0.05 - avg_cost) * 2000))
        
        # Ponderación: 60% tokens, 40% costo
        efficiency_score = (token_score * 0.6) + (cost_score * 0.4)
        
        return round(efficiency_score, 1)
    except:
        return 0.0