
import asyncio
import os
import sys

# DATABASE_URL for testing on this VPS
TEST_DSN = "postgresql://postgres:postgres@localhost:5432/clinica_dental"

# Load .env file manually to get cryptography keys
def load_env():
    env_path = os.path.join(os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key] = value.strip().strip('"').strip("'")
        print("✅ Environment keys loaded from .env")
    else:
        print("❌ .env not found")

load_env()

# Override POSTGRES_DSN for this script
os.environ["POSTGRES_DSN"] = TEST_DSN

# Ensure we can import from orchestrator_service
sys.path.append(os.path.join(os.getcwd(), "orchestrator_service"))

from db import db
from core.credentials import get_tenant_credential
from services.meta_ads_service import MetaAdsClient

async def diagnostic():
    try:
        print(f"Connecting to: {TEST_DSN}")
        await db.connect()
        tenant_id = 1
        
        print(f"\n--- 🔍 DIAGNÓSTICO META ADS (TENANT {tenant_id}) ---")
        
        token = await get_tenant_credential(tenant_id, "META_USER_LONG_TOKEN")
        ad_account_id = await get_tenant_credential(tenant_id, "META_AD_ACCOUNT_ID")
        
        print(f"Token presente: {bool(token)}")
        print(f"Ad Account ID: {ad_account_id}")
        
        if not token:
            print("❌ Error: No se encontró el token de Meta.")
            return

        # Print partial token for manual verification without exposing everything
        print(f"Token (start): {token[:15]}...")

        client = MetaAdsClient(token)
        
        # 1. Verificar Cuentas Disponibles
        print("\n1. Verificando cuentas accesibles con este token...")
        try:
            accounts = await client.get_ad_accounts()
            print(f"Cuentas encontradas: {len(accounts)}")
            found_target = False
            for acc in accounts:
                clean_id = acc.get('id', '').replace('act_', '')
                print(f"   - {acc.get('name')} (ID: {acc.get('id')}) [{acc.get('currency')}]")
                if ad_account_id and (ad_account_id == acc.get('id') or ad_account_id == clean_id):
                    found_target = True
            
            if ad_account_id and not found_target:
                print(f"⚠️ Alerta: El ID configurado '{ad_account_id}' no parece estar en la lista de cuentas accesibles.")
        except Exception as e:
            print(f"❌ Error listando cuentas: {e}")

        if ad_account_id:
            # 2. Probar Insights con diferentes presets
            account_to_test = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
            
            # Using 'maximum' as requested for the 'All' filter fix
            presets = ["maximum", "last_30d"]
            
            print(f"\n2. Probando Insights para {account_to_test}...")
            for preset in presets:
                print(f"   --- Preset: {preset} ---")
                try:
                    insights = await client.get_ads_insights(account_to_test, date_preset=preset)
                    total_spend = sum(float(item.get('spend', 0)) for item in insights)
                    print(f"   Resultado: {len(insights)} anuncios encontrados.")
                    print(f"   Inversión Total: {total_spend}")
                    if insights:
                        # Print first item to see structure
                        print(f"   Sample data: {insights[0]}")
                except Exception as e:
                    print(f"   ❌ Error con preset {preset}: {e}")
        else:
            print("\n❌ No hay Ad Account ID configurado para probar insights.")

    except Exception as e:
        print(f"\n❌ Error General: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(diagnostic())
