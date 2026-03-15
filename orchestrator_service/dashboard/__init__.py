"""
Dashboard CEO Simple - Sistema integrado con autenticación existente
"""

import logging
import os
from fastapi import APIRouter
from .status_page import router as status_router

logger = logging.getLogger(__name__)

# Crear router principal del dashboard
router = APIRouter()

# Incluir sub-routers
router.include_router(status_router)

def init_dashboard(app, db_pool):
    """
    Inicializa el dashboard simple integrado con autenticación existente
    """
    try:
        # Inicializar token tracker y config manager (fuente de verdad para OPENAI_MODEL)
        from .token_tracker import init_token_tracker
        from .config_manager import init_config_manager
        init_token_tracker(db_pool)
        init_config_manager(db_pool)
        # Incluir router en la app principal
        app.include_router(router)
        
        # Agregar middleware de debug
        from .auth_integrated import debug_auth_middleware
        app.middleware("http")(debug_auth_middleware)
        
        # Configurar middleware para servir archivos estáticos
        from fastapi.staticfiles import StaticFiles
        
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        os.makedirs(static_dir, exist_ok=True)
        
        app.mount("/dashboard/static", StaticFiles(directory=static_dir), name="dashboard_static")
        
        logger.info("✅ Dashboard CEO Simple inicializado correctamente")
        logger.info(f"   📊 URL: https://app.dralauradelgado.com/dashboard/status")
        logger.info(f"   🔐 Acceso: Cualquier usuario autenticado en ClinicForge")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error inicializando dashboard simple: {e}")
        # Fallback: intentar inicializar sin características avanzadas
        try:
            app.include_router(router)
            logger.warning("⚠️ Dashboard inicializado en modo mínimo (sin métricas)")
            return True
        except:
            logger.error("❌ No se pudo inicializar el dashboard en modo mínimo")
            return False

# Variables exportadas
__all__ = [
    'init_dashboard',
    'router'
]