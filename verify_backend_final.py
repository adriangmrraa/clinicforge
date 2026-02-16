#!/usr/bin/env python3
"""
VERIFY_BACKEND_FINAL.py
Script de verificación final para el backend dental.
Ejecutar después de las migraciones SQL.
"""
import asyncio
import asyncpg
import os
import sys

POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/dental_clinic")

async def verify_database():
    """Verifica que la BD esté configurada correctamente."""
    print("=" * 60)
    print("🔍 VERIFICACIÓN FINAL DEL BACKEND DENTAL")
    print("=" * 60)
    
    try:
        # 1. Conectar a la BD
        print("\n📡 Conectando a PostgreSQL...")
        conn = await asyncpg.connect(POSTGRES_DSN)
        print("✅ Conexión exitosa")
        
        # 2. Verificar tablas necesarias
        print("\n📋 Verificando tablas...")
        required_tables = [
            'patients', 'professionals', 'appointments', 
            'appointment_statuses', 'chat_messages', 'inbound_messages',
            'clinical_records', 'system_events'
        ]
        
        result = await conn.fetch("""
            SELECT tablename FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """)
        existing_tables = [row['tablename'] for row in result]
        
        missing = []
        for table in required_tables:
            if table in existing_tables:
                print(f"   ✅ {table}")
            else:
                print(f"   ❌ {table} (FALTA)")
                missing.append(table)
        
        if missing:
            print(f"\n⚠️  Faltan tablas: {missing}")
            print("   Ejecutar: psql -d dental_clinic -f db/init/RUN_MIGRATIONS.sql")
            return False
        
        # 3. Verificar profesionales activos
        print("\n👨‍⚕️ Verificando profesionales...")
        pros = await conn.fetch("SELECT id, name FROM professionals WHERE is_active = true")
        if pros:
            for p in pros:
                print(f"   ✅ Dr. {p['name']} (ID: {p['id']})")
        else:
            print("   ⚠️  No hay profesionales activos (necesario para agendar turnos)")
        
        # 4. Verificar statuses de turnos
        print("\n📊 Verificando statuses de turnos...")
        statuses = await conn.fetch("SELECT id, name FROM appointment_statuses")
        for s in statuses:
            print(f"   ✅ {s['name']} (ID: {s['id']})")
        
        await conn.close()
        print("\n" + "=" * 60)
        print("✅ VERIFICACIÓN COMPLETA - TODO OK")
        print("=" * 60)
        return True
        
    except asyncpg.InvalidCatalogSequenceError as e:
        print(f"\n❌ Error: Faltan migraciones SQL")
        print(f"   Ejecutar: psql -d dental_clinic -f db/init/RUN_MIGRATIONS.sql")
        print(f"\n   Error detalle: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Error conectando a BD: {e}")
        print("   Verificar POSTGRES_DSN en .env")
        return False

async def verify_tools_import():
    """Verifica que las tools se puedan importar."""
    print("\n🔧 Verificando imports de tools...")
    try:
        # Intentar importar main.py
        sys.path.insert(0, 'orchestrator_service')
        from main import DENTAL_TOOLS, check_availability, book_appointment
        print("   ✅ main.py importado correctamente")
        print(f"   ✅ Tools disponibles: {[t.name for t in DENTAL_TOOLS]}")
        return True
    except Exception as e:
        print(f"   ❌ Error importando: {e}")
        return False

async def main():
    """Ejecuta todas las verificaciones."""
    print("\n🚀 INICIANDO VERIFICACIÓN...")
    
    # Verificar DB
    db_ok = await verify_database()
    
    # Verificar imports
    tools_ok = await verify_tools_import()
    
    # Resumen final
    print("\n" + "=" * 60)
    print("📊 RESUMEN FINAL")
    print("=" * 60)
    print(f"   Base de Datos: {'✅ OK' if db_ok else '❌ FALTA'}")
    print(f"   Tools importadas: {'✅ OK' if tools_ok else '❌ ERROR'}")
    print()
    
    if db_ok and tools_ok:
        print("🎉 EL BACKEND ESTÁ COMPLETO Y LISTO PARA USAR")
        print("\n📝 PRÓXIMOS PASOS:")
        print("   1. Iniciar el servidor: python -m orchestrator_service.main")
        print("   2. Probar con: curl -X POST http://localhost:8000/health")
        return 0
    else:
        print("⚠️  HAY PENDIENTES POR RESOLVER")
        if not db_ok:
            print("   → Ejecutar migraciones SQL")
        if not tools_ok:
            print("   → Revisar errores de import")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
