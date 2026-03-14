"""
Status Page - Dashboard privado para el CEO
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

logger = logging.getLogger(__name__)

# Configurar templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)

templates = Jinja2Templates(directory=templates_dir)

# Crear router para el dashboard
router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Clave secreta para acceso CEO (debería estar en .env)
CEO_ACCESS_KEY = os.getenv("CEO_ACCESS_KEY", "dralauradelgado2026")

def verify_ceo_access(request: Request):
    """Verifica que el acceso sea del CEO"""
    # Verificar clave en query parameter
    access_key = request.query_params.get("key")
    if access_key == CEO_ACCESS_KEY:
        return True
    
    # Verificar en headers
    access_key_header = request.headers.get("X-CEO-Access-Key")
    if access_key_header == CEO_ACCESS_KEY:
        return True
    
    # Verificar cookie (para sesiones)
    access_key_cookie = request.cookies.get("ceo_access")
    if access_key_cookie == CEO_ACCESS_KEY:
        return True
    
    raise HTTPException(status_code=403, detail="Acceso restringido al CEO")

@router.get("/status", response_class=HTMLResponse)
async def status_dashboard(
    request: Request,
    days: int = 30,
    _: bool = Depends(verify_ceo_access)
):
    """
    Dashboard de status privado para el CEO
    URL: https://app.dralauradelgado.com/dashboard/status?key=CEO_ACCESS_KEY
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
            "ceo_access_key": CEO_ACCESS_KEY
        }
        
        return templates.TemplateResponse("status.html", context)
        
    except Exception as e:
        logger.error(f"❌ Error generando dashboard: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@router.get("/api/metrics")
async def get_dashboard_metrics(
    days: int = 30,
    _: bool = Depends(verify_ceo_access)
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
    config_updates: Dict[str, Any],
    _: bool = Depends(verify_ceo_access)
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
    _: bool = Depends(verify_ceo_access)
):
    """API para obtener modelos disponibles"""
    try:
        from .token_tracker import token_tracker
        models = await token_tracker.get_available_models()
        return {"models": models}
    except Exception as e:
        logger.error(f"❌ Error obteniendo modelos: {e}")
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

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

# Crear template HTML para el dashboard
status_template = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard CEO - Dra. Laura Delgado</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/luxon@3.4.4/build/global/luxon.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/axios@1.6.7/dist/axios.min.js"></script>
    <style>
        :root {
            --primary: #2563eb;
            --primary-dark: #1d4ed8;
            --secondary: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-300: #d1d5db;
            --gray-700: #374151;
            --gray-900: #111827;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: var(--gray-900);
        }
        
        .dashboard-container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }
        
        .dashboard-header {
            background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
            color: white;
            padding: 30px 40px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .header-title h1 {
            font-size: 28px;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .header-title p {
            opacity: 0.9;
            font-size: 14px;
        }
        
        .header-stats {
            display: flex;
            gap: 30px;
        }
        
        .stat-box {
            text-align: center;
        }
        
        .stat-value {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 5px;
        }
        
        .stat-label {
            font-size: 12px;
            opacity: 0.8;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .dashboard-content {
            padding: 30px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }
        
        .card {
            background: var(--gray-50);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid var(--gray-200);
            transition: transform 0.3s, box-shadow 0.3s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
        }
        
        .card-title {
            font-size: 18px;
            font-weight: 600;
            color: var(--gray-900);
        }
        
        .card-subtitle {
            font-size: 14px;
            color: var(--gray-700);
            margin-top: 5px;
        }
        
        .metric-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        
        .metric-item {
            background: white;
            padding: 15px;
            border-radius: 10px;
            border-left: 4px solid var(--primary);
        }
        
        .metric-value {
            font-size: 24px;
            font-weight: 700;
            color: var(--gray-900);
        }
        
        .metric-label {
            font-size: 12px;
            color: var(--gray-700);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 5px;
        }
        
        .chart-container {
            height: 300px;
            margin-top: 20px;
            position: relative;
        }
        
        .config-section {
            background: white;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .config-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 15px 0;
            border-bottom: 1px solid var(--gray-200);
        }
        
        .config-item:last-child {
            border-bottom: none;
        }
        
        .config-label {
            font-weight: 500;
        }
        
        .config-value {
            font-family: 'Monaco', 'Courier New', monospace;
            background: var(--gray-100);
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 14px;
        }
        
        .select-model {
            padding: 8px 15px;
            border-radius: 8px;
            border: 2px solid var(--gray-300);
            background: white;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .select-model:hover {
            border-color: var(--primary);
        }
        
        .btn {
            padding: 10px 20px;
            border-radius: 8px;
            border: none;
            font-weight: 600;
