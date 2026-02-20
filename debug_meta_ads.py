import asyncio
import os
import sys
import json
import logging

# Configurar logs básicos
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_meta")

# Agregar orchestrator_service al path si es necesario
sys.path.append(os.path.join(os.getcwd(), 'orchestrator_service'))

# Cargar .env manualmente si existe
from dotenv import load_dotenv
load_dotenv()

# Parchear DSN para ejecución local en Windows si apunta a Docker
import os
dsn = os.getenv("POSTGRES_DSN", "")
if "@dentalforge_postgres" in dsn:
    os.environ["POSTGRES_DSN"] = dsn.replace("@dentalforge_postgres", "@localhost")
    logger.info("🔧 Parcheando POSTGRES_DSN para usar localhost")

async def main():
    try:
        from orchestrator_service.db import db
        from orchestrator_service.core.credentials import get_tenant_credential
        from orchestrator_service.services.meta_ads_service import MetaAdsClient
        
        await db.connect()
        
        tenant_id = 1
        logger.info(f"🚀 Iniciando diagnóstico para Tenant {tenant_id}")
        
        token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
        ad_account_id = await get_tenant_credential(tenant_id, "META_AD_ACCOUNT_ID")
        
        if not token or not ad_account_id:
            logger.error("❌ Credenciales no encontradas para tenant 1")
            await db.disconnect()
            return

        logger.info(f"✅ Credenciales obtenidas. Ad Account: {ad_account_id}")
        
        client = MetaAdsClient(token)
        
        # Probar campañas
        logger.info("📡 Consultando campañas (Campaign-First)...")
        campaigns = await client.get_campaigns_with_insights(ad_account_id, date_preset="maximum")
        logger.info(f"📊 Campañas encontradas: {len(campaigns)}")
        for i, c in enumerate(campaigns[:5]): # Mostrar solo las primeras 5
            logger.info(f"  {i+1}. [{c.get('id')}] {c.get('name')} | Status: {c.get('effective_status')}")
        if len(campaigns) > 5:
            logger.info(f"  ... (+ {len(campaigns)-5} más)")
            
        # Probar anuncios
        logger.info("📡 Consultando anuncios (Ads-Insights)...")
        ads = await client.get_ads_with_insights(ad_account_id, date_preset="maximum")
        logger.info(f"🎨 Anuncios encontrados: {len(ads)}")
        
        if ads:
            for i, a in enumerate(ads):
                insights = a.get('insights', {}).get('data', [])
                spend = insights[0].get('spend', '0') if insights else "0"
                logger.info(f"  {i+1}. [{a.get('id')}] {a.get('name')} | Campaign: {a.get('campaign', {}).get('name')} | Spend: {spend} | Status: {a.get('effective_status')}")
        else:
            logger.warning("⚠️ La lista de anuncios regresó VACÍA desde Meta.")

        await db.disconnect()
        
    except Exception as e:
        logger.exception(f"💥 Error crítico en diagnóstico: {e}")

if __name__ == "__main__":
    asyncio.run(main())
