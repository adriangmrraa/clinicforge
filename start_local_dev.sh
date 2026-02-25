#!/bin/bash
# Script para levantar ClinicForge localmente en modo desarrollo

set -e

echo "🚀 INICIANDO CLINICFORGE EN MODO DESARROLLO LOCAL"
echo "=================================================="

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para verificar si un puerto está en uso
check_port() {
    local port=$1
    if netstat -tulpn 2>/dev/null | grep ":$port " > /dev/null; then
        return 0  # Puerto en uso
    else
        return 1  # Puerto libre
    fi
}

# Función para matar proceso en puerto
kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        echo -e "${YELLOW}⚠️  Matando proceso en puerto $port (PID: $pid)${NC}"
        kill -9 $pid 2>/dev/null || true
        sleep 1
    fi
}

# Función para esperar hasta que un servicio esté listo
wait_for_service() {
    local host=$1
    local port=$2
    local service=$3
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Esperando $service en $host:$port...${NC}"
    
    while [ $attempt -le $max_attempts ]; do
        if nc -z $host $port 2>/dev/null; then
            echo -e "${GREEN}✅ $service listo en $host:$port${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        ((attempt++))
    done
    
    echo -e "${RED}❌ Timeout esperando $service${NC}"
    return 1
}

# Función para iniciar servicio en background
start_service() {
    local name=$1
    local command=$2
    local log_file=$3
    
    echo -e "${YELLOW}🚀 Iniciando $name...${NC}"
    echo "Comando: $command"
    echo "Log: $log_file"
    
    # Ejecutar en background y redirigir output
    eval "$command > \"$log_file\" 2>&1 &"
    local pid=$!
    echo $pid > "/tmp/$name.pid"
    echo -e "${GREEN}✅ $name iniciado (PID: $pid)${NC}"
}

# Crear directorio de logs
mkdir -p logs

echo -e "\n${YELLOW}1. CONFIGURANDO VARIABLES DE ENTORNO${NC}"
export $(grep -v '^#' .env | xargs)

echo -e "\n${YELLOW}2. INICIANDO SERVICIOS DE INFRAESTRUCTURA${NC}"

# Iniciar Redis si no está corriendo
if ! check_port 6379; then
    echo -e "${YELLOW}🚀 Iniciando Redis...${NC}"
    redis-server --daemonize yes --port 6379
    wait_for_service localhost 6379 "Redis"
else
    echo -e "${GREEN}✅ Redis ya está corriendo en puerto 6379${NC}"
fi

# Iniciar PostgreSQL si no está corriendo
if ! check_port 5432; then
    echo -e "${YELLOW}🚀 Iniciando PostgreSQL...${NC}"
    sudo service postgresql start 2>/dev/null || \
    sudo systemctl start postgresql 2>/dev/null || \
    echo -e "${RED}⚠️  No se pudo iniciar PostgreSQL automáticamente${NC}"
    
    # Esperar a que PostgreSQL esté listo
    sleep 3
    if check_port 5432; then
        echo -e "${GREEN}✅ PostgreSQL iniciado en puerto 5432${NC}"
        
        # Crear base de datos si no existe
        echo -e "${YELLOW}🔧 Configurando base de datos...${NC}"
        sudo -u postgres psql -c "CREATE DATABASE clinicforge;" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE USER postgres WITH PASSWORD 'clinicforge';" 2>/dev/null || true
        sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE clinicforge TO postgres;" 2>/dev/null || true
    else
        echo -e "${RED}❌ PostgreSQL no se inició correctamente${NC}"
    fi
else
    echo -e "${GREEN}✅ PostgreSQL ya está corriendo en puerto 5432${NC}"
fi

echo -e "\n${YELLOW}3. INICIANDO BACKEND SERVICES${NC}"

# Matar servicios previos si existen
kill_port 8000  # orchestrator_service
kill_port 8002  # whatsapp_service
kill_port 3000  # bff_service

# Iniciar orchestrator_service (puerto 8000)
cd orchestrator_service
start_service "orchestrator_service" \
    "python3 main.py" \
    "../logs/orchestrator.log"
cd ..

wait_for_service localhost 8000 "orchestrator_service"

# Iniciar whatsapp_service (puerto 8002)
cd whatsapp_service
start_service "whatsapp_service" \
    "python3 main.py" \
    "../logs/whatsapp.log"
cd ..

wait_for_service localhost 8002 "whatsapp_service"

# Iniciar bff_service (puerto 3000)
cd bff_service
# Instalar dependencias Node si es necesario
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}📦 Instalando dependencias de bff_service...${NC}"
    npm install 2>&1 | tail -10
fi

start_service "bff_service" \
    "node index.js" \
    "../logs/bff.log"
cd ..

wait_for_service localhost 3000 "bff_service"

echo -e "\n${YELLOW}4. INICIANDO FRONTEND REACT${NC}"

cd frontend_react

# Configurar variables para desarrollo
export VITE_API_BASE_URL="http://localhost:3000"

# Matar proceso previo en puerto 5173
kill_port 5173

echo -e "${YELLOW}🚀 Iniciando frontend React con Vite...${NC}"
echo -e "${YELLOW}📡 API Base URL: $VITE_API_BASE_URL${NC}"

# Iniciar Vite en modo desarrollo
npm run dev &
VITE_PID=$!
echo $VITE_PID > "/tmp/frontend_react.pid"

echo -e "${GREEN}✅ Frontend React iniciado (PID: $VITE_PID)${NC}"

# Esperar a que Vite esté listo
wait_for_service localhost 5173 "Frontend React"

echo -e "\n${GREEN}==================================================${NC}"
echo -e "${GREEN}🎉 CLINICFORGE INICIADO EXITOSAMENTE${NC}"
echo -e "${GREEN}==================================================${NC}"
echo ""
echo -e "${YELLOW}📊 SERVICIOS:${NC}"
echo -e "  • Frontend React: ${GREEN}http://localhost:5173${NC}"
echo -e "  • BFF Service:    ${GREEN}http://localhost:3000${NC}"
echo -e "  • Orchestrator:   ${GREEN}http://localhost:8000${NC}"
echo -e "  • WhatsApp:       ${GREEN}http://localhost:8002${NC}"
echo -e "  • PostgreSQL:     ${GREEN}localhost:5432${NC}"
echo -e "  • Redis:          ${GREEN}localhost:6379${NC}"
echo ""
echo -e "${YELLOW}📁 LOGS:${NC}"
echo -e "  • orchestrator:   ${GREEN}logs/orchestrator.log${NC}"
echo -e "  • whatsapp:       ${GREEN}logs/whatsapp.log${NC}"
echo -e "  • bff:            ${GREEN}logs/bff.log${NC}"
echo ""
echo -e "${YELLOW}🔧 PARA DETENER TODOS LOS SERVICIOS:${NC}"
echo -e "  ./stop_local_dev.sh"
echo ""
echo -e "${YELLOW}🚀 PARA GENERAR TÚNEL PÚBLICO:${NC}"
echo -e "  ngrok http 5173  # o usar localhost.run / serveo.net"
echo ""

# Mantener script corriendo
echo -e "${YELLOW}⏳ Manteniendo servicios activos...${NC}"
echo -e "${YELLOW}Presiona Ctrl+C para detener todos los servicios${NC}"

# Función para limpiar al salir
cleanup() {
    echo -e "\n${RED}🛑 Deteniendo todos los servicios...${NC}"
    
    # Matar todos los procesos que iniciamos
    for service in orchestrator_service whatsapp_service bff_service frontend_react; do
        if [ -f "/tmp/$service.pid" ]; then
            pid=$(cat "/tmp/$service.pid")
            if kill -0 $pid 2>/dev/null; then
                echo -e "${YELLOW}⏳ Deteniendo $service (PID: $pid)...${NC}"
                kill $pid 2>/dev/null || true
            fi
            rm -f "/tmp/$service.pid"
        fi
    done
    
    echo -e "${GREEN}✅ Todos los servicios detenidos${NC}"
    exit 0
}

# Capturar Ctrl+C
trap cleanup SIGINT SIGTERM

# Mantener script corriendo
while true; do
    sleep 1
done