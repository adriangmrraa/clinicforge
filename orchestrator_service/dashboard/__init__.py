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

def init_dashboard(app, db_pool=None):
    """
    Inicializa el dashboard: registra routers, middleware y archivos estáticos.
    NO inicializa token_tracker/config_manager aquí (requieren db_pool activo).
    Usar init_dashboard_async() después de db.connect() para eso.
    """
    try:
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
        try:
            app.include_router(router)
            logger.warning("⚠️ Dashboard inicializado en modo mínimo (sin métricas)")
            return True
        except:
            logger.error("❌ No se pudo inicializar el dashboard en modo mínimo")
            return False


async def init_dashboard_async(db_pool):
    """
    Inicializa componentes del dashboard que requieren db_pool activo.
    Llamar desde lifespan después de db.connect().
    """
    try:
        from .token_tracker import init_token_tracker
        from .config_manager import init_config_manager

        tracker = init_token_tracker(db_pool)
        await tracker.ensure_table()

        manager = init_config_manager(db_pool)
        await manager.ensure_table()

        logger.info("✅ Dashboard: token_tracker y config_manager inicializados")
    except Exception as e:
        logger.warning(f"⚠️ Dashboard async init parcial: {e}")


# Variables exportadas
__all__ = [
    'init_dashboard',
    'init_dashboard_async',
    'router'
]
