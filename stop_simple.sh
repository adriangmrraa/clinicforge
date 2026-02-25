#!/bin/bash
# Script para detener ClinicForge

echo "🛑 DETENIENDO CLINICFORGE"
echo "========================"

# Matar todos los procesos
echo "⏳ Deteniendo servicios..."

pkill -f "python3 main.py" 2>/dev/null
pkill -f "node index.js" 2>/dev/null
pkill -f "vite" 2>/dev/null
pkill -f "localhost.run" 2>/dev/null

# Eliminar PID files
rm -f /tmp/orchestrator.pid
rm -f /tmp/bff.pid
rm -f /tmp/frontend.pid
rm -f /tmp/tunnel.pid

echo "✅ Servicios detenidos"
echo ""
echo "🔧 Para reiniciar: ./start_simple.sh"