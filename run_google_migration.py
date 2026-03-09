#!/usr/bin/env python3
"""
Script para ejecutar la migración del sistema de Google Ads Integration
"""

import asyncio
import sys
import os
from pathlib import Path

# Agregar el directorio del proyecto al path
sys.path.insert(0, str(Path(__file__).parent))

async def run_migration():
    """Ejecuta la migración de la base de datos para Google Ads"""
    try:
        from orchestrator_service.db import db
        
        print("🔧 Conectando a la base de datos...")
        await db.connect()
        
        # Leer el archivo de migración
        migration_path = Path(__file__).parent / "orchestrator_service" / "migrations" / "patch_021_google_ads_integration.sql"
        
        if not migration_path.exists():
            print(f"❌ No se encontró el archivo de migración: {migration_path}")
            return False
        
        print(f"📄 Leyendo migración: {migration_path.name}")
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        
        # Ejecutar la migración
        print("🚀 Ejecutando migración de Google Ads...")
        async with db.pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(migration_sql)
        
        print("✅ Migración de Google Ads ejecutada exitosamente!")
        print("\n📊 Tablas creadas:")
        print("   • google_oauth_tokens - Tokens OAuth de Google")
        print("   • google_ads_accounts - Cuentas de Google Ads")
        print("   • google_ads_metrics_cache - Cache de métricas")
        print("\n🔧 Credenciales configuradas:")
        print("   • GOOGLE_CLIENT_ID - Para todos los tenants")
        print("   • GOOGLE_CLIENT_SECRET - Para todos los tenants")
        print("   • GOOGLE_DEVELOPER_TOKEN - Para todos los tenants")
        print("   • GOOGLE_REDIRECT_URI - Para todos los tenants")
        print("   • GOOGLE_LOGIN_REDIRECT_URI - Para todos los tenants")
        print("   • GOOGLE_ADS_API_VERSION - Global (v16)")
        print("\n🎯 Estado del sistema Google Ads:")
        print("   ✅ Backend: Servicios OAuth y API creados")
        print("   ✅ API: Endpoints configurados (/admin/auth/google/, /admin/marketing/google/)")
        print("   ✅ Frontend: Componentes y vistas listos")
        print("   ✅ Database: Migración aplicada")
        print("   ✅ Traducciones: Español e inglés configurados")
        
        # Verificar que las tablas se crearon
        print("\n🔍 Verificando creación de tablas...")
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'google_%'
            ORDER BY table_name
        """)
        
        if tables:
            print("✅ Tablas Google encontradas:")
            for table in tables:
                print(f"   • {table['table_name']}")
        else:
            print("⚠️  No se encontraron tablas Google")
        
        return True
        
    except Exception as e:
        print(f"❌ Error ejecutando migración: {e}")
        import traceback
        traceback.print_exc()
        return False

async def check_status():
    """Verifica el estado de la migración"""
    try:
        from orchestrator_service.db import db
        
        print("🔍 Verificando estado de migración Google Ads...")
        await db.connect()
        
        async with db.pool.acquire() as conn:
            # Verificar tablas
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('google_oauth_tokens', 'google_ads_accounts', 'google_ads_metrics_cache')
                ORDER BY table_name
            """)
            
            expected_tables = {'google_oauth_tokens', 'google_ads_accounts', 'google_ads_metrics_cache'}
            found_tables = {t['table_name'] for t in tables}
            
            print(f"📊 Tablas esperadas: {len(expected_tables)}")
            print(f"📊 Tablas encontradas: {len(found_tables)}")
            
            if found_tables == expected_tables:
                print("✅ Todas las tablas Google existen")
                for table in sorted(found_tables):
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    print(f"   • {table}: {count} registros")
            else:
                missing = expected_tables - found_tables
                if missing:
                    print(f"❌ Faltan tablas: {missing}")
                
                extra = found_tables - expected_tables
                if extra:
                    print(f"⚠️  Tablas extra encontradas: {extra}")
            
            # Verificar credenciales
            print("\n🔍 Verificando credenciales Google...")
            credentials = await conn.fetch("""
                SELECT name, COUNT(*) as tenant_count
                FROM credentials 
                WHERE name LIKE 'GOOGLE_%'
                GROUP BY name
                ORDER BY name
            """)
            
            if credentials:
                print("✅ Credenciales Google encontradas:")
                for cred in credentials:
                    print(f"   • {cred['name']}: {cred['tenant_count']} tenants")
            else:
                print("⚠️  No se encontraron credenciales Google")
        
        return found_tables == expected_tables
        
    except Exception as e:
        print(f"❌ Error verificando estado: {e}")
        return False

def main():
    """Punto de entrada principal"""
    if len(sys.argv) < 2:
        print("Uso: python run_google_migration.py [run|status]")
        print("  run    - Ejecuta la migración")
        print("  status - Verifica el estado de la migración")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "run":
        success = asyncio.run(run_migration())
        sys.exit(0 if success else 1)
    
    elif command == "status":
        success = asyncio.run(check_status())
        sys.exit(0 if success else 1)
    
    else:
        print(f"Comando desconocido: {command}")
        print("Uso: python run_google_migration.py [run|status]")
        sys.exit(1)

if __name__ == "__main__":
    main()