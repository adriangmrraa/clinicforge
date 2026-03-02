#!/usr/bin/env python3
"""
Test simple para verificar rutas del backend
"""

import requests
import sys

def test_backend():
    base_url = "https://dentalforge-orchestrator.gvdlcu.easypanel.host"
    headers = {
        "x-admin-token": "admin-secret-token12093876456352884654839",
        "x-tenant-id": "1"
    }
    
    print("🧪 TESTEANDO BACKEND EN PRODUCCIÓN")
    print("=" * 60)
    
    # 1. Test health endpoint (siempre debería funcionar)
    print("\n1. Probando /health...")
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:100]}...")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 2. Test endpoint que SÍ funciona (para comparar)
    print("\n2. Probando endpoint conocido (/admin/settings/clinic)...")
    try:
        response = requests.get(f"{base_url}/admin/settings/clinic", 
                              headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Funciona (200 OK)")
        else:
            print(f"   ❌ Status inesperado: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 3. Test endpoint de leads (el problema)
    print("\n3. Probando endpoint problemático (/admin/leads/webhook/url)...")
    try:
        response = requests.get(f"{base_url}/admin/leads/webhook/url", 
                              headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ ¡FUNCIONA! (200 OK)")
            print(f"   Response: {response.text[:200]}")
        elif response.status_code == 404:
            print(f"   ❌ 404 Not Found - La ruta NO existe en el backend")
            print(f"   Headers: {dict(response.headers)}")
        else:
            print(f"   ⚠️  Status inesperado: {response.status_code}")
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    # 4. Test otro endpoint de leads
    print("\n4. Probando /admin/leads/stats/summary...")
    try:
        response = requests.get(f"{base_url}/admin/leads/stats/summary", 
                              headers=headers, timeout=10)
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Funciona (200 OK)")
        elif response.status_code == 404:
            print(f"   ❌ 404 Not Found")
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 CONCLUSIÓN:")
    
    # Análisis
    if "404" in locals() and response.status_code == 404:
        print("""
⚠️  LAS RUTAS /admin/leads/* NO EXISTEN EN EL BACKEND

Posibles causas:
1. El código NO se desplegó correctamente
2. Hay un error al importar routes/leads.py
3. El router no se está registrando en app.include_router()
4. El contenedor tiene una versión vieja del código

SOLUCIÓN:
1. Revisar logs de inicio del backend (orchestrator_service)
2. Buscar errores de importación o sintaxis
3. Reiniciar completamente el servicio
4. Verificar que el commit correcto esté en producción
        """)
    else:
        print("✅ El backend responde, pero necesitamos más diagnóstico")

if __name__ == "__main__":
    test_backend()