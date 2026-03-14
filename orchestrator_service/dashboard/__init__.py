"""
Dashboard CEO - Sistema de métricas y configuración
"""

import logging
from fastapi import APIRouter
from .status_page import router as status_router
from .token_tracker import init_token_tracker, token_tracker
from .config_manager import init_config_manager, config_manager

logger = logging.getLogger(__name__)

# Crear router principal del dashboard
router = APIRouter()

# Incluir sub-routers
router.include_router(status_router)

def init_dashboard(app, db_pool):
    """
    Inicializa el dashboard completo
    """
    try:
        # Inicializar componentes
        init_token_tracker(db_pool)
        init_config_manager(db_pool)
        
        # Incluir router en la app principal
        app.include_router(router)
        
        # Configurar middleware para servir archivos estáticos
        from fastapi.staticfiles import StaticFiles
        import os
        
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        os.makedirs(static_dir, exist_ok=True)
        
        app.mount("/dashboard/static", StaticFiles(directory=static_dir), name="dashboard_static")
        
        logger.info("✅ Dashboard CEO inicializado correctamente")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error inicializando dashboard: {e}")
        return False

# Funciones de conveniencia para uso en otros módulos
def get_token_tracker():
    """Obtiene el tracker de tokens"""
    return token_tracker

def get_config_manager():
    """Obtiene el gestor de configuración"""
    return config_manager

# Variables exportadas
__all__ = [
    'init_dashboard',
    'get_token_tracker',
    'get_config_manager',
    'router'
]