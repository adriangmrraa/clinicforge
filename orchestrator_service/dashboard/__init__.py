"""
Dashboard CEO - Sistema de métricas y configuración con autenticación automática
"""

import logging
import os
from fastapi import APIRouter
from .status_page_updated import router as status_router
from .token_tracker import init_token_tracker, token_tracker
from .config_manager import init_config_manager, config_manager
from .auth_middleware import session_manager

logger = logging.getLogger(__name__)

# Crear router principal del dashboard
router = APIRouter()

# Incluir sub-routers
router.include_router(status_router)

def init_dashboard(app, db_pool):
    """
    Inicializa el dashboard completo con autenticación automática
    """
    try:
        # Configurar variables de entorno necesarias
        if not os.getenv("CEO_ACCESS_KEY"):
            os.environ["CEO_ACCESS_KEY"] = "dralauradelgado2026"
            logger.info("✅ CEO_ACCESS_KEY configurada por defecto")
        
        if not os.getenv("CEO_SECRET_KEY"):
            import secrets
            os.environ["CEO_SECRET_KEY"] = secrets.token_hex(32)
            logger.info("✅ CEO_SECRET_KEY generada automáticamente")
        
        # Inicializar componentes
        init_token_tracker(db_pool)
        init_config_manager(db_pool)
        
        # Incluir router en la app principal
        app.include_router(router)
        
        # Configurar middleware para servir archivos estáticos
        from fastapi.staticfiles import StaticFiles
        
        static_dir = os.path.join(os.path.dirname(__file__), "static")
        os.makedirs(static_dir, exist_ok=True)
        
        app.mount("/dashboard/static", StaticFiles(directory=static_dir), name="dashboard_static")
        
        # Configurar middleware para inyectar contexto CEO
        @app.middleware("http")
        async def add_ceo_context(request: Request, call_next):
            from .auth_middleware import get_ceo_session
            response = await call_next(request)
            
            # Solo para respuestas HTML
            if response.headers.get("content-type", "").startswith("text/html"):
                # Podríamos inyectar contexto aquí si fuera necesario
                pass
            
            return response
        
        logger.info("✅ Dashboard CEO con autenticación automática inicializado correctamente")
        logger.info(f"   📊 URL: https://app.dralauradelgado.com/dashboard/status")
        logger.info(f"   🔐 Login: https://app.dralauradelgado.com/dashboard/login")
        logger.info(f"   🗝️  Clave por defecto: dralauradelgado2026")
        
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

def get_session_manager():
    """Obtiene el gestor de sesiones"""
    return session_manager

# Variables exportadas
__all__ = [
    'init_dashboard',
    'get_token_tracker',
    'get_config_manager',
    'get_session_manager',
    'router'
]