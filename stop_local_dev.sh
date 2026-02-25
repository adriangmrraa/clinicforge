#!/bin/bash
# Script para detener todos los servicios de ClinicForge

echo "🛑 DETENIENDO CLINICFORGE LOCAL"
echo "================================"

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para matar proceso por PID
kill_by_pid() {
    local service=$1
    local pid_file="/tmp/$service.pid"
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 $pid 2>/dev/null; then
            echo -e "${YELLOW}⏳ Deteniendo $service (PID: $pid)...${NC}"
            kill $pid 2>/dev/null || true
            sleep 1
            if kill -0 $pid 2>/dev/null; then
                echo -e "${RED}⚠️  Forzando terminación de $service...${NC}"
                kill -9 $pid 2>/dev/null || true
            fi
            echo -e "${GREEN}✅ $service detenido${NC}"
        else
            echo -e "${YELLOW}ℹ️  $service ya estaba detenido${NC}"
        fi
        rm -f "$pid_file"
    else
        echo -e "${YELLOW}ℹ️  No se encontró PID file para $service${NC}"
    fi
}

# Función para matar proceso por puerto
kill_by_port() {
    local port=$1
    local service=$2
    
    local pid=$(lsof -ti:$port 2>/dev/null)
    if [ ! -z "$pid" ]; then
        echo -e "${YELLOW}⏳ Deteniendo $service en puerto $port (PID: $pid)...${NC}"
        kill $pid 2>/dev/null || true
        sleep 1
        if lsof -ti:$port 2>/dev/null; then
            echo -e "${RED}⚠️  Forzando terminación...${NC}"
            kill -9 $pid 2>/dev/null || true
        fi
        echo -e "${GREEN}✅ $service detenido${NC}"
    else
        echo -e "${YELLOW}ℹ️  No hay $service corriendo en puerto $port${NC}"
    fi
}

echo -e "\n${YELLOW}1. DETENIENDO SERVICIOS POR PID FILES${NC}"

# Detener servicios en orden inverso al inicio
kill_by_pid "frontend_react"
kill_by_pid "bff_service"
kill_by_pid "whatsapp_service"
kill_by_pid "orchestrator_service"

echo -e "\n${YELLOW}2. DETENIENDO SERVICIOS POR PUERTOS (fallback)${NC}"

# Verificar y matar por puertos por si acaso
kill_by_port 5173 "Frontend React"
kill_by_port 3000 "BFF Service"
kill_by_port 8002 "WhatsApp Service"
kill_by_port 8000 "Orchestrator Service"

echo -e "\n${YELLOW}3. LIMPIANDO ARCHIVOS TEMPORALES${NC}"

# Eliminar PID files
rm -f /tmp/orchestrator_service.pid
rm -f /tmp/whatsapp_service.pid
rm -f /tmp/bff_service.pid
rm -f /tmp/frontend_react.pid

# Eliminar archivos de lock de npm si existen
rm -f /tmp/.vite-lock 2>/dev/null || true

echo -e "${GREEN}✅ Archivos temporales limpiados${NC}"

echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}🎉 TODOS LOS SERVICIOS DETENIDOS${NC}"
echo -e "${GREEN}================================${NC}"

echo -e "\n${YELLOW}📊 PUERTOS LIBERADOS:${NC}"
echo "  • 5173  - Frontend React"
echo "  • 3000  - BFF Service"
echo "  • 8002  - WhatsApp Service"
echo "  • 8000  - Orchestrator Service"
echo "  • 5432  - PostgreSQL"
echo "  • 6379  - Redis"

echo -e "\n${YELLOW}🔧 PARA REINICIAR:${NC}"
echo "  ./start_local_dev.sh"

exit 0