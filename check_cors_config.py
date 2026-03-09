#!/usr/bin/env python3
"""
Script para verificar y diagnosticar problemas de configuración CORS en ClinicForge.
"""

import os
import sys
from pathlib import Path

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent

def check_cors_configuration():
    """Verifica la configuración de CORS en el proyecto."""
    
    print("=== DIAGNÓSTICO DE CONFIGURACIÓN CORS ===\n")
    
    # 1. Verificar archivo .env
    env_file = BASE_DIR / ".env"
    cors_value = None
    
    if env_file.exists():
        print("📄 Revisando archivo .env:")
        with open(env_file, 'r') as f:
            for line in f:
                if line.strip().startswith("CORS_ALLOWED_ORIGINS="):
                    cors_value = line.strip().split("=", 1)[1]
                    print(f"  ✅ Encontrado: CORS_ALLOWED_ORIGINS={cors_value}")
                    break
        if not cors_value:
            print("  ⚠️  No se encontró CORS_ALLOWED_ORIGINS en .env")
    else:
        print("  ⚠️  Archivo .env no encontrado")
    
    print()
    
    # 2. Verificar configuración en main.py
    main_py = BASE_DIR / "orchestrator_service" / "main.py"
    if main_py.exists():
        print("📄 Revisando configuración CORS en main.py:")
        with open(main_py, 'r') as f:
            lines = f.readlines()
            in_cors_section = False
            cors_lines = []
            
            for i, line in enumerate(lines):
                if "# Configurar CORS" in line:
                    in_cors_section = True
                if in_cors_section and i > 0 and "#" in lines[i-1] and "Configurar CORS" not in lines[i-1]:
                    in_cors_section = False
                
                if in_cors_section:
                    cors_lines.append(f"  Línea {i+1}: {line.rstrip()}")
            
            if cors_lines:
                print("\n".join(cors_lines[:10]))  # Mostrar primeras 10 líneas
            else:
                print("  ⚠️  No se encontró la sección de configuración CORS")
    else:
        print("  ❌ Archivo main.py no encontrado")
    
    print()
    
    # 3. Verificar archivo de variables de entorno de producción
    env_prod_example = BASE_DIR / ".env.production.example"
    if env_prod_example.exists():
        print("📄 Revisando plantilla de producción (.env.production.example):")
        with open(env_prod_example, 'r') as f:
            for line in f:
                if "CORS_ALLOWED_ORIGINS" in line:
                    print(f"  📋 Ejemplo: {line.strip()}")
    
    print()
    
    # 4. Diagnóstico del problema
    print("=== DIAGNÓSTICO DEL PROBLEMA ===")
    
    if cors_value:
        origins = [o.strip() for o in cors_value.split(",") if o.strip()]
        print(f"\n1. Orígenes configurados actualmente: {origins}")
        
        # Preguntar al usuario cuál es su dominio actual
        print("\n2. Para diagnosticar, necesito saber:")
        print("   - ¿Cuál es tu dominio actual del frontend? (ej: https://tu-dominio.com)")
        print("   - ¿Estás en desarrollo local o en producción?")
        
        print("\n3. Posibles problemas:")
        print("   a) El dominio no está en CORS_ALLOWED_ORIGINS")
        print("   b) El protocolo (http/https) no coincide")
        print("   c) El puerto no está incluido")
        print("   d) La variable no se cargó correctamente en Easypanel")
    
    print("\n=== SOLUCIÓN RECOMENDADA ===")
    print("\n1. En Easypanel (orchestrator_service), configura:")
    print("   CORS_ALLOWED_ORIGINS=https://tu-dominio-frontend.com,http://localhost:3000")
    print("\n2. Reemplaza 'tu-dominio-frontend.com' con tu dominio real")
    print("\n3. Reinicia el servicio orchestrator_service")
    print("\n4. Verifica con:")
    print("   curl -I -H 'Origin: https://tu-dominio-frontend.com' https://tu-dominio-orchestrator.com/health")
    
    return cors_value

def generate_easypanel_config():
    """Genera configuración específica para Easypanel."""
    
    print("\n=== CONFIGURACIÓN PARA EASYPANEL ===")
    
    config = {
        "orchestrator_service": {
            "CORS_ALLOWED_ORIGINS": "https://TU-DOMINIO-FRONTEND.com,http://localhost:3000",
            "FRONTEND_URL": "https://TU-DOMINIO-FRONTEND.com",
            "PLATFORM_URL": "https://TU-DOMINIO-FRONTEND.com",
            "META_REDIRECT_URI": "https://TU-DOMINIO-ORCHESTRATOR.com/auth/meta/callback"
        },
        "frontend_react": {
            "VITE_API_BASE_URL": "https://TU-DOMINIO-ORCHESTRATOR.com"
        }
    }
    
    print("\n📋 Copia y pega estas variables en Easypanel:")
    
    for service, vars in config.items():
        print(f"\n🔧 {service}:")
        for key, value in vars.items():
            print(f"  {key}={value}")
    
    print("\n⚠️  IMPORTANTE: Reemplaza TU-DOMINIO-FRONTEND y TU-DOMINIO-ORCHESTRATOR con tus dominios reales")

if __name__ == "__main__":
    check_cors_configuration()
    generate_easypanel_config()
    
    print("\n=== PASOS A SEGUIR ===")
    print("1. Identifica tus dominios actuales")
    print("2. Actualiza las variables en Easypanel")
    print("3. Reinicia los servicios")
    print("4. Prueba la conexión")
    print("\n¿Necesitas ayuda con algún paso específico?")