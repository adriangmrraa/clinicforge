#!/bin/sh

echo "Verificando estado de migraciones..."

# Detect DB state:
# - FRESH: no tables, no alembic → run baseline + stamp head
# - STAMPED_BROKEN: alembic says head but columns missing → nuke + baseline + stamp
# - EXISTING_NO_ALEMBIC: tables exist but no alembic → stamp head
# - NORMAL: alembic + tables + columns OK → upgrade head
DB_ACTION=$(python -c "
import os, psycopg2
dsn = os.environ.get('POSTGRES_DSN', '').replace('postgresql+asyncpg://', 'postgresql://')
if dsn.startswith('postgres://'):
    dsn = dsn.replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version')\")
has_alembic = cur.fetchone()[0]
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='tenants')\")
has_tenants = cur.fetchone()[0]

if has_tenants and not has_alembic:
    print('EXISTING_NO_ALEMBIC')
elif has_alembic and has_tenants:
    # Check if schema is actually complete
    cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='acquisition_source')\")
    has_recent = cur.fetchone()[0]
    if has_recent:
        print('NORMAL')
    else:
        # Stamped but schema incomplete — nuke everything
        cur.execute(\"SELECT tablename FROM pg_tables WHERE schemaname = 'public'\")
        for r in cur.fetchall():
            cur.execute('DROP TABLE IF EXISTS public.\"' + r[0] + '\" CASCADE')
        print('FRESH')
elif has_alembic and not has_tenants:
    # Alembic exists but no tables — drop alembic and start fresh
    cur.execute('DROP TABLE IF EXISTS alembic_version CASCADE')
    print('FRESH')
else:
    print('FRESH')

conn.close()
" 2>/dev/null || echo "FRESH")

echo "DB_ACTION=$DB_ACTION"

if [ "$DB_ACTION" = "EXISTING_NO_ALEMBIC" ]; then
    echo "DB existente sin Alembic. Marcando baseline..."
    alembic stamp head
    echo "Baseline marcado."
elif [ "$DB_ACTION" = "FRESH" ]; then
    echo "DB fresca. Ejecutando baseline + stamp head..."
    # Run ONLY the baseline migration (creates full schema)
    alembic upgrade a1b2c3d4e5f6
    # Then stamp at head so incremental migrations are skipped
    alembic stamp head
    echo "Schema creado y stamp aplicado."
else
    echo "Aplicando migraciones incrementales..."
    alembic upgrade head
    echo "Migraciones aplicadas."
fi

# Asegurar permisos de escritura en directorios de uploads/media
mkdir -p /app/uploads /app/media
chmod -R 777 /app/uploads /app/media

echo "Iniciando servidor..."
exec uvicorn main:socket_app --host 0.0.0.0 --port 8000 \
  --timeout-keep-alive 75 \
  --timeout-graceful-shutdown 30 \
  --limit-concurrency 500
