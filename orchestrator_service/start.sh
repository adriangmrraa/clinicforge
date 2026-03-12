#!/bin/sh
set -e

echo "Aplicando migraciones de base de datos..."
alembic upgrade head
echo "Migraciones aplicadas correctamente."

echo "Iniciando servidor..."
exec uvicorn main:socket_app --host 0.0.0.0 --port 8000
