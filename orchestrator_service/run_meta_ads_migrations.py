#!/usr/bin/env python3
"""
Script para ejecutar migraciones de Meta Ads Attribution en ClinicForge.

Ejecuta:
1. Migración patch_017_meta_ads_attribution.sql
2. Verifica que las columnas se hayan agregado correctamente
3. Proporciona rollback opcional

Uso:
    python3 run_meta_ads_migrations.py
"""

import os
import sys
import asyncpg
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

POSTGRES_DSN = os.getenv("POSTGRES_DSN")

if not POSTGRES_DSN:
    logger.error("❌ ERROR: POSTGRES_DSN environment variable is not set!")
    logger.error("   Exporte la variable: export POSTGRES_DSN=postgresql://user:pass@host:port/dbname")
    sys.exit(1)

# Ajustar DSN para asyncpg
DSN = POSTGRES_DSN.replace("postgresql+asyncpg://", "postgresql://")


async def run_migration():
    """Ejecuta la migración de Meta Ads attribution."""
    try:
        # Conectar a PostgreSQL
        conn = await asyncpg.connect(DSN)
        logger.info("✅ Conectado a PostgreSQL")
        
        # Leer archivo de migración
        migration_path = Path(__file__).parent / "migrations" / "patch_017_meta_ads_attribution.sql"
        
        if not migration_path.exists():
            logger.error(f"❌ Archivo de migración no encontrado: {migration_path}")
            await conn.close()
            return False
        
        with open(migration_path, "r", encoding="utf-8") as f:
            migration_sql = f.read()
        
        logger.info(f"📄 Ejecutando migración: {migration_path.name}")
        
        # Ejecutar migración en una transacción
        async with conn.transaction():
            await conn.execute(migration_sql)
        
        logger.info("✅ Migración ejecutada exitosamente")
        
        # Verificar que las columnas se hayan agregado
        await verify_migration(conn)
        
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error ejecutando migración: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


async def verify_migration(conn):
    """Verifica que las columnas se hayan agregado correctamente."""
    logger.info("🔍 Verificando migración...")
    
    # Columnas esperadas
    expected_columns = [
        "acquisition_source",
        "meta_ad_id",
        "meta_ad_name",
        "meta_ad_headline",
        "meta_ad_body",
        "meta_adset_id",
        "meta_adset_name",
        "meta_campaign_id",
        "meta_campaign_name"
    ]
    
    query = """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'patients'
        ORDER BY column_name
    """
    
    rows = await conn.fetch(query)
    existing_columns = {row["column_name"] for row in rows}
    
    logger.info("📊 Columnas existentes en tabla 'patients':")
    for row in rows:
        logger.info(f"   - {row['column_name']} ({row['data_type']})")
    
    # Verificar columnas esperadas
    missing_columns = []
    for col in expected_columns:
        if col not in existing_columns:
            missing_columns.append(col)
    
    if missing_columns:
        logger.warning(f"⚠️ Columnas faltantes: {missing_columns}")
    else:
        logger.info("✅ Todas las columnas de atribución están presentes")
    
    # Verificar índices
    index_query = """
        SELECT indexname, indexdef 
        FROM pg_indexes 
        WHERE tablename = 'patients' 
        AND indexname LIKE 'idx_patients_%'
    """
    
    indexes = await conn.fetch(index_query)
    logger.info("📊 Índices en tabla 'patients':")
    for idx in indexes:
        logger.info(f"   - {idx['indexname']}")
    
    # Verificar índices esperados
    expected_indexes = [
        "idx_patients_acquisition_source",
        "idx_patients_meta_ad_id",
        "idx_patients_meta_campaign_id",
        "idx_patients_meta_adset_id"
    ]
    
    existing_indexes = {idx["indexname"] for idx in indexes}
    missing_indexes = [idx for idx in expected_indexes if idx not in existing_indexes]
    
    if missing_indexes:
        logger.warning(f"⚠️ Índices faltantes: {missing_indexes}")
    else:
        logger.info("✅ Todos los índices de atribución están presentes")


async def rollback_migration():
    """Rollback de la migración (opcional)."""
    logger.warning("⚠️  ¿Está seguro de que desea hacer rollback de la migración?")
    logger.warning("   Esto eliminará las columnas de atribución Meta Ads.")
    confirm = input("   Escriba 'SI' para confirmar: ")
    
    if confirm.upper() != "SI":
        logger.info("❌ Rollback cancelado")
        return False
    
    try:
        conn = await asyncpg.connect(DSN)
        
        rollback_sql = """
        -- Rollback de migración 017: Meta Ads Attribution
        BEGIN;
        
        -- Eliminar índices
        DROP INDEX IF EXISTS idx_patients_acquisition_source;
        DROP INDEX IF EXISTS idx_patients_meta_ad_id;
        DROP INDEX IF EXISTS idx_patients_meta_campaign_id;
        DROP INDEX IF EXISTS idx_patients_meta_adset_id;
        
        -- Eliminar columnas (si existen)
        ALTER TABLE patients DROP COLUMN IF EXISTS meta_adset_id;
        ALTER TABLE patients DROP COLUMN IF EXISTS meta_campaign_name;
        ALTER TABLE patients DROP COLUMN IF EXISTS meta_adset_name;
        ALTER TABLE patients DROP COLUMN IF EXISTS meta_ad_name;
        
        -- NOTA: No eliminamos acquisition_source, meta_ad_id, meta_ad_headline, meta_ad_body, meta_campaign_id
        -- ya que pueden ser usados por otras funcionalidades
        
        COMMIT;
        """
        
        async with conn.transaction():
            await conn.execute(rollback_sql)
        
        logger.info("✅ Rollback ejecutado exitosamente")
        await conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en rollback: {e}")
        return False


async def check_current_state():
    """Muestra el estado actual de la base de datos."""
    try:
        conn = await asyncpg.connect(DSN)
        
        # Contar pacientes por fuente de adquisición
        query = """
            SELECT 
                acquisition_source,
                COUNT(*) as total,
                COUNT(DISTINCT meta_ad_id) as unique_ads,
                COUNT(DISTINCT meta_campaign_id) as unique_campaigns
            FROM patients
            GROUP BY acquisition_source
            ORDER BY total DESC
        """
        
        rows = await conn.fetch(query)
        
        logger.info("📊 Estado actual de atribución:")
        logger.info("=" * 50)
        
        total_patients = 0
        meta_ads_patients = 0
        
        for row in rows:
            source = row["acquisition_source"] or "NULL"
            total = row["total"]
            unique_ads = row["unique_ads"]
            unique_campaigns = row["unique_campaigns"]
            
            logger.info(f"   {source}:")
            logger.info(f"     - Total pacientes: {total}")
            logger.info(f"     - Anuncios únicos: {unique_ads}")
            logger.info(f"     - Campañas únicas: {unique_campaigns}")
            
            total_patients += total
            if source == "META_ADS":
                meta_ads_patients = total
        
        logger.info("=" * 50)
        logger.info(f"   Total pacientes: {total_patients}")
        
        if total_patients > 0:
            percentage = (meta_ads_patients / total_patients) * 100
            logger.info(f"   Pacientes Meta Ads: {meta_ads_patients} ({percentage:.1f}%)")
        
        await conn.close()
        
    except Exception as e:
        logger.error(f"❌ Error verificando estado: {e}")


def main():
    """Función principal."""
    import asyncio
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "rollback":
            asyncio.run(rollback_migration())
        elif command == "check":
            asyncio.run(check_current_state())
        elif command == "help":
            print("""
Uso:
    python3 run_meta_ads_migrations.py [comando]
    
Comandos:
    (sin comando)    - Ejecuta la migración
    rollback         - Hace rollback de la migración
    check            - Verifica estado actual
    help             - Muestra esta ayuda
            """)
        else:
            print(f"❌ Comando desconocido: {command}")
            print("   Use 'help' para ver los comandos disponibles")
    else:
        # Ejecutar migración por defecto
        success = asyncio.run(run_migration())
        
        if success:
            logger.info("🎉 ¡Migración completada exitosamente!")
            logger.info("")
            logger.info("📋 Resumen:")
            logger.info("   ✅ Columnas de atribución Meta Ads agregadas")
            logger.info("   ✅ Índices para consultas rápidas creados")
            logger.info("   ✅ Sistema de doble atribución listo")
            logger.info("")
            logger.info("🚀 Próximos pasos:")
            logger.info("   1. Configurar webhook Meta en Developers Console")
            logger.info("   2. Probar atribución WhatsApp con anuncios Meta")
            logger.info("   3. Probar formularios de leads Meta")
            logger.info("   4. Verificar dashboard de marketing")
        else:
            logger.error("❌ La migración falló")
            sys.exit(1)


if __name__ == "__main__":
    main()