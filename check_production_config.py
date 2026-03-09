#!/usr/bin/env python3
"""
Script para diagnosticar problemas de configuración en producción.
"""

import os

print("=== DIAGNÓSTICO DE CONFIGURACIÓN PRODUCCIÓN ===\n")

# Variables críticas que deben estar configuradas
CRITICAL_VARS = [
    "FRONTEND_URL",
    "PLATFORM_URL", 
    "CORS_ALLOWED_ORIGINS",
    "META_REDIRECT_URI",
    "ADMIN_TOKEN",
    "JWT_SECRET_KEY",
    "OPENAI_API_KEY",
    "YCLOUD_API_KEY",
    "YCLOUD_WEBHOOK_SECRET",
    "META_APP_ID",
    "META_APP_SECRET"
]

print("📋 Variables de entorno críticas para producción:")
print("-" * 50)

for var in CRITICAL_VARS:
    value = os.getenv(var, "NO CONFIGURADA")
    if value == "NO CONFIGURADA":
        print(f"❌ {var}: NO CONFIGURADA")
    elif "dummy" in str(value).lower() or "example" in str(value).lower():
        print(f"⚠️  {var}: Configurada con valor dummy/ejemplo")
    else:
        # Mostrar solo primeros y últimos caracteres por seguridad
        val_str = str(value)
        if len(val_str) > 20:
            display = f"{val_str[:10]}...{val_str[-10:]}"
        else:
            display = "***CONFIGURADA***"
        print(f"✅ {var}: {display}")

print("\n" + "=" * 50)
print("\n🎯 DOMINIO ACTUAL DEL FRONTEND: app.dralauradelgado.com")
print("\n🔧 Configuración CORS recomendada:")
print("CORS_ALLOWED_ORIGINS=https://app.dralauradelgado.com,http://localhost:3000")
print("FRONTEND_URL=https://app.dralauradelgado.com")
print("PLATFORM_URL=https://app.dralauradelgado.com")

print("\n⚠️  PROBLEMAS COMUNES:")
print("1. CORS_ALLOWED_ORIGINS no incluye el nuevo dominio")
print("2. Las cookies/sesiones están vinculadas al dominio antiguo")
print("3. Las credenciales (YCloud, Meta) no se cargaron correctamente")
print("4. El ADMIN_TOKEN cambió o no es el correcto")

print("\n🚀 SOLUCIÓN RECOMENDADA:")
print("1. Verificar TODAS las variables en Easypanel")
print("2. Reiniciar todos los servicios")
print("3. Limpiar caché del navegador")
print("4. Verificar logs del backend")
