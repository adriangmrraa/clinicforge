#!/usr/bin/env python3
"""
Script para diagnosticar por qué las rutas /admin/leads/* devuelven 404
"""

import sys
import os

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("🔍 DIAGNÓSTICO DEL BACKEND - RUTAS /admin/leads/*")
print("=" * 60)

# 1. Verificar que el archivo routes/leads.py existe
print("\n1. Verificando archivo routes/leads.py...")
leads_path = "orchestrator_service/routes/leads.py"
if os.path.exists(leads_path):
    print(f"   ✅ Archivo existe: {leads_path}")
    print(f"   📏 Tamaño: {os.path.getsize(leads_path)} bytes")
else:
    print(f"   ❌ Archivo NO existe: {leads_path}")
    sys.exit(1)

# 2. Verificar que se puede importar
print("\n2. Intentando importar routes.leads...")
try:
    # Simular importación básica
    with open(leads_path, 'r') as f:
        content = f.read()
    
    # Buscar la definición del router
    if "router = APIRouter" in content:
        print("   ✅ Router APIRouter encontrado en el archivo")
    else:
        print("   ❌ No se encontró 'router = APIRouter'")
    
    # Buscar rutas específicas
    if "@router.get(\"/webhook/url\")" in content:
        print("   ✅ Ruta /webhook/url encontrada")
    else:
        print("   ❌ Ruta /webhook/url NO encontrada")
        
    if "@router.get(\"/stats/summary\")" in content:
        print("   ✅ Ruta /stats/summary encontrada")
    else:
        print("   ❌ Ruta /stats/summary NO encontrada")
        
except Exception as e:
    print(f"   ❌ Error al leer archivo: {e}")

# 3. Verificar main.py incluye el router
print("\n3. Verificando main.py...")
main_path = "orchestrator_service/main.py"
if os.path.exists(main_path):
    with open(main_path, 'r') as f:
        main_content = f.read()
    
    if "from routes.leads import router as leads_router" in main_content:
        print("   ✅ Import de leads_router encontrado")
    else:
        print("   ❌ Import de leads_router NO encontrado")
        
    if "app.include_router(leads_router)" in main_content:
        print("   ✅ app.include_router(leads_router) encontrado")
    else:
        print("   ❌ app.include_router(leads_router) NO encontrado")
        
    # Buscar línea específica
    lines = main_content.split('\n')
    for i, line in enumerate(lines):
        if "leads_router" in line:
            print(f"   📍 Línea {i+1}: {line.strip()}")
else:
    print(f"   ❌ main.py no existe")

# 4. Verificar prefijo del router
print("\n4. Verificando prefijo del router en leads.py...")
try:
    with open(leads_path, 'r') as f:
        for line in f:
            if "APIRouter" in line and "prefix" in line:
                print(f"   📍 Línea del router: {line.strip()}")
                break
        else:
            print("   ⚠️  No se encontró línea con APIRouter y prefix")
except Exception as e:
    print(f"   ❌ Error: {e}")

# 5. Verificar estructura de rutas esperadas
print("\n5. Rutas esperadas según el código:")
print("   - GET /admin/leads/webhook/url")
print("   - GET /admin/leads/stats/summary")
print("   - GET /admin/leads")
print("   - GET /admin/leads/{id}")
print("   - PUT /admin/leads/{id}/status")
print("   - POST /admin/leads/{id}/convert")
print("   - GET /admin/leads/{id}/notes")
print("   - POST /admin/leads/{id}/notes")

print("\n" + "=" * 60)
print("🎯 RECOMENDACIONES:")

# Verificar si hay errores de sintaxis
print("\n6. Buscando posibles errores de sintaxis...")
try:
    import ast
    with open(leads_path, 'r') as f:
        ast.parse(f.read())
    print("   ✅ Sintaxis Python válida")
except SyntaxError as e:
    print(f"   ❌ Error de sintaxis: {e}")
    print(f"   📍 Línea {e.lineno}, Columna {e.offset}: {e.text}")

print("\n" + "=" * 60)
print("🚀 ACCIONES SUGERIDAS:")
print("1. Revisar logs del deploy del orchestrator_service")
print("2. Verificar que no haya errores de importación al iniciar")
print("3. Probar con curl después de reiniciar el servicio")
print("4. Verificar permisos y rutas en el contenedor Docker")