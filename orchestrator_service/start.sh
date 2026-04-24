#!/bin/sh

echo "Verificando estado de migraciones..."

# Helper: drop all public tables and alembic_version, then run migrations fresh
nuke_and_rebuild() {
    echo "Dropeando todas las tablas para rebuild limpio..."
    python -c "
import os, psycopg2
dsn = os.environ.get('POSTGRES_DSN', '').replace('postgresql+asyncpg://', 'postgresql://')
if dsn.startswith('postgres://'):
    dsn = dsn.replace('postgres://', 'postgresql://', 1)
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()
cur.execute(\"SELECT tablename FROM pg_tables WHERE schemaname = 'public'\")
tables = [r[0] for r in cur.fetchall()]
for t in tables:
    cur.execute('DROP TABLE IF EXISTS public.\"' + t + '\" CASCADE')
    print(f'  Dropped {t}')
conn.close()
print('Todas las tablas dropeadas.')
"
    echo "Ejecutando migraciones desde cero..."
    alembic upgrade head
    echo "Migraciones aplicadas correctamente."
}

# Detect DB state
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
conn.close()
if has_tenants and not has_alembic:
    print('STAMP')
else:
    print('UPGRADE')
" 2>/dev/null || echo "UPGRADE")

if [ "$DB_ACTION" = "STAMP" ]; then
    echo "DB existente detectada sin Alembic. Marcando baseline..."
    alembic stamp head
    echo "Baseline marcado correctamente."
else
    echo "Aplicando migraciones..."
    if ! alembic upgrade head 2>&1; then
        echo "⚠️ Migraciones fallaron — detectado schema inconsistente. Rebuildeando..."
        nuke_and_rebuild
    else
        echo "Migraciones aplicadas correctamente."
    fi
fi

# Asegurar permisos de escritura en directorios de uploads/media
mkdir -p /app/uploads /app/media
chmod -R 777 /app/uploads /app/media

echo "Iniciando servidor..."
exec uvicorn main:socket_app --host 0.0.0.0 --port 8000 \
  --timeout-keep-alive 75 \
  --timeout-graceful-shutdown 30 \
  --limit-concurrency 500
