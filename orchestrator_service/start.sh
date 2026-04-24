#!/bin/sh
set -e

echo "Verificando estado de migraciones..."

# Detect DB state and fix broken stamps
DB_ACTION=$(python -c "
import os, psycopg2
dsn = os.environ.get('POSTGRES_DSN', '').replace('postgresql+asyncpg://', 'postgresql://')
if dsn.startswith('postgres://'):
    dsn = dsn.replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(dsn)
cur = conn.cursor()
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version')\")
has_alembic = cur.fetchone()[0]
cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='tenants')\")
has_tenants = cur.fetchone()[0]

if has_tenants and not has_alembic:
    # Existing DB that never used Alembic
    print('STAMP')
elif has_alembic and not has_tenants:
    # Alembic stamped but tables never created (broken stamp from old start.sh)
    cur.execute('DELETE FROM alembic_version')
    conn.commit()
    print('UPGRADE')
elif has_alembic and has_tenants:
    # Check for a column from a recent migration to detect false stamps
    cur.execute(\"SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='acquisition_source')\")
    has_recent_col = cur.fetchone()[0]
    if not has_recent_col:
        # Stamped at head but migrations never actually ran — nuke and rebuild
        # Drop all tables so baseline + incremental migrations don't conflict
        cur.execute('DELETE FROM alembic_version')
        cur.execute(\"\"\"
            DO $$
            DECLARE r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename != 'alembic_version')
                LOOP
                    EXECUTE 'DROP TABLE IF EXISTS public.' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
        \"\"\")
        conn.commit()
        print('UPGRADE')
    else:
        print('UPGRADE')
else:
    # Fresh DB — no tables, no alembic
    print('UPGRADE')

conn.close()
" 2>/dev/null || echo "UPGRADE")

if [ "$DB_ACTION" = "STAMP" ]; then
    echo "DB existente detectada sin Alembic. Marcando baseline..."
    alembic stamp head
    echo "Baseline marcado correctamente."
else
    echo "Aplicando migraciones..."
    alembic upgrade head
    echo "Migraciones aplicadas correctamente."
fi

# Asegurar permisos de escritura en directorios de uploads/media
mkdir -p /app/uploads /app/media
chmod -R 777 /app/uploads /app/media

echo "Iniciando servidor..."
exec uvicorn main:socket_app --host 0.0.0.0 --port 8000 \
  --timeout-keep-alive 75 \
  --timeout-graceful-shutdown 30 \
  --limit-concurrency 500
