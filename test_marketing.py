import asyncio
import sys

# Agregar ruta para que importe todo bien
sys.path.append("orchestrator_service")
from db import db
from core.credentials import get_tenant_credential
from services.marketing_service import MarketingService
import logging
logging.basicConfig(level=logging.INFO)

async def test():
    # Inicializar pool
    await db.init()
    
    # tenant_id = 1 (usualmente el de pruebas)
    stats = await MarketingService.get_campaign_stats(1, time_range="all")
    print(stats)
    
if __name__ == "__main__":
    asyncio.run(test())
