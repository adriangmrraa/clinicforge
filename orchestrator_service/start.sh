#!/bin/sh
set -e

echo "Verificando estado de migraciones..."

# Si la tabla alembic_version no existe pero tenants sí,
# es una DB existente que nunca usó Alembic → stamp en vez de upgrade
if ! python -c "
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
    exit(0)
else:
    print('UPGRADE')
    exit(1)
" 2>/dev/null; then
    echo "Aplicando migraciones..."
    alembic upgrade head
    echo "Migraciones aplicadas correctamente."
else
    echo "DB existente detectada sin Alembic. Marcando baseline..."
    alembic stamp head
    echo "Baseline marcado correctamente."
fi

# Asegurar permisos de escritura en directorios de uploads/media
mkdir -p /app/uploads /app/media
chmod -R 777 /app/uploads /app/media

echo "Iniciando servidor..."
exec uvicorn main:socket_app --host 0.0.0.0 --port 8000 \
  --timeout-keep-alive 75 \
  --timeout-graceful-shutdown 30 \
  --limit-concurrency 500
