#!/bin/bash
# Script simple para iniciar ClinicForge

echo "🚀 INICIANDO CLINICFORGE (MODO SIMPLE)"
echo "======================================"

# Cargar variables de entorno
echo "📋 Cargando variables de entorno..."
export INTERNAL_API_TOKEN=clinicforge-internal-token-local-dev
export OPENAI_API_KEY=sk-dummy-key-for-local-testing-only
export REDIS_URL=redis://localhost:6379
export POSTGRES_DSN=postgresql://postgres:clinicforge@localhost:5432/clinicforge
export ADMIN_TOKEN=admin-secret-token-local-dev
export JWT_SECRET_KEY=jwt-secret-key-local-development-only
export JWT_ALGORITHM=HS256
export ACCESS_TOKEN_EXPIRE_MINUTES=43200
export PLATFORM_URL=http://localhost:5173
export CORS_ALLOWED_ORIGINS=http://localhost:5173
export CREDENTIALS_FERNET_KEY=w6qX7Y8z9A0B1C2D3E4F5G6H7I8J9K0L1M2N3O4P5Q6R7S8T9U0V1W2X3Y4Z=
export LOG_LEVEL=INFO
export MEDIA_PROXY_SECRET=$(openssl rand -hex 32)
export ENVIRONMENT=development

# Crear directorio de logs
mkdir -p logs

echo ""
echo "📊 SERVICIOS A INICIAR:"
echo "  1. PostgreSQL (5432)"
echo "  2. Redis (6379)"
echo "  3. Orchestrator Service (8000)"
echo "  4. BFF Service (3000)"
echo "  5. Frontend React (5173)"
echo ""

# Iniciar PostgreSQL si no está corriendo
if ! netstat -tulpn 2>/dev/null | grep ":5432 " > /dev/null; then
    echo "🐘 Iniciando PostgreSQL..."
    sudo service postgresql start
    sleep 2
fi

# Iniciar Redis si no está corriendo
if ! netstat -tulpn 2>/dev/null | grep ":6379 " > /dev/null; then
    echo "🔴 Iniciando Redis..."
    sudo service redis-server start
    sleep 1
fi

# Matar servicios previos
echo "🛑 Limpiando servicios previos..."
pkill -f "python3 main.py" 2>/dev/null
pkill -f "node index.js" 2>/dev/null
pkill -f "vite" 2>/dev/null
sleep 1

# Iniciar Orchestrator Service
echo "🤖 Iniciando Orchestrator Service (puerto 8000)..."
cd orchestrator_service
python3 main.py > ../logs/orchestrator.log 2>&1 &
ORCHESTRATOR_PID=$!
echo $ORCHESTRATOR_PID > /tmp/orchestrator.pid
cd ..
sleep 3

# Iniciar BFF Service
echo "🔗 Iniciando BFF Service (puerto 3000)..."
cd bff_service
# Instalar dependencias si es necesario
if [ ! -d "node_modules" ]; then
    echo "📦 Instalando dependencias BFF..."
    npm install --silent
fi
node index.js > ../logs/bff.log 2>&1 &
BFF_PID=$!
echo $BFF_PID > /tmp/bff.pid
cd ..
sleep 2

# Iniciar Frontend React
echo "⚛️  Iniciando Frontend React (puerto 5173)..."
cd frontend_react
export VITE_API_BASE_URL="http://localhost:3000"
npm run dev > ../logs/frontend.log 2>&1 &
FRONTEND_PID=$!
echo $FRONTEND_PID > /tmp/frontend.pid
cd ..
sleep 3

echo ""
echo "✅ TODOS LOS SERVICIOS INICIADOS"
echo "================================"
echo ""
echo "🌐 URLS DISPONIBLES:"
echo "  • Frontend:    http://localhost:5173"
echo "  • BFF API:     http://localhost:3000"
echo "  • Orchestrator: http://localhost:8000"
echo "  • PostgreSQL:  localhost:5432"
echo "  • Redis:       localhost:6379"
echo ""
echo "📁 LOGS:"
echo "  • logs/orchestrator.log"
echo "  • logs/bff.log"
echo "  • logs/frontend.log"
echo ""
echo "🛑 Para detener: ./stop_simple.sh"
echo ""
echo "🚀 Generando túnel público..."

# Intentar generar túnel con localhost.run
echo "🌍 Intentando con localhost.run..."
ssh -R 80:localhost:5173 nokey@localhost.run 2>&1 | tee logs/tunnel.log &
TUNNEL_PID=$!
echo $TUNNEL_PID > /tmp/tunnel.pid

echo "⏳ Esperando túnel... (puede tardar unos segundos)"
sleep 5

# Mostrar URL del túnel si está disponible
if [ -f "logs/tunnel.log" ]; then
    echo ""
    echo "🔗 URL PÚBLICA DISPONIBLE EN:"
    grep -o "https://.*\.localhost\.run" logs/tunnel.log | head -1
fi

echo ""
echo "🎉 ClinicForge listo para pruebas!"
echo "   Bug de agenda corregido en: frontend_react/src/views/AgendaView.tsx"