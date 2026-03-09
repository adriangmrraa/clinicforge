#!/usr/bin/env python3
"""
Script para reemplazar URLs hardcodeadas por variables de entorno en ClinicForge.
"""

import os
import re
from pathlib import Path

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent

# Archivos a modificar con sus reemplazos
FILES_TO_UPDATE = [
    {
        "path": "orchestrator_service/routes/meta_auth.py",
        "replacements": [
            {
                "old": 'frontend_url = os.getenv("FRONTEND_URL", "https://dentalforge-frontend.gvdlcu.easypanel.host").rstrip("/")',
                "new": 'frontend_url = os.getenv("FRONTEND_URL", "").rstrip("/")'
            },
            {
                "old": '"url": "https://dentalforge-frontend.gvdlcu.easypanel.host/privacy",',
                "new": '"url": f"{frontend_url}/privacy" if frontend_url else "https://example.com/privacy",'
            }
        ]
    },
    {
        "path": "orchestrator_service/auth_service.py",
        "replacements": [
            {
                "old": 'base_url = os.getenv("PLATFORM_URL", "https://dentalogic-frontend.ugwrjq.easypanel.host")',
                "new": 'base_url = os.getenv("PLATFORM_URL", "")'
            }
        ]
    },
    {
        "path": "ENVIRONMENT_VARIABLES.md",
        "replacements": [
            {
                "old": "CORS_ALLOWED_ORIGINS=https://dentalogic-frontend.ugwrjq.easypanel.host,http://localhost:3000",
                "new": "CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com,http://localhost:3000"
            },
            {
                "old": "VITE_API_URL=https://dentalogic-orchestrator.ugwrjq.easypanel.host",
                "new": "VITE_API_URL=https://your-orchestrator-domain.com"
            },
            {
                "old": "VITE_BFF_URL=https://dentalogic-bff.ugwrjq.easypanel.host",
                "new": "VITE_BFF_URL=https://your-bff-domain.com"
            }
        ]
    },
    {
        "path": "docs/API_REFERENCE.md",
        "replacements": [
            {
                "old": "Sustituye `localhost:8000` por la URL del Orchestrator en tu entorno (ej. en producción: `https://clinicforge-orchestrator.ugwrjq.easypanel.host`).",
                "new": "Sustituye `localhost:8000` por la URL del Orchestrator en tu entorno (ej. en producción: `https://your-orchestrator-domain.com`)."
            }
        ]
    }
]

def update_file(file_path: Path, replacements: list):
    """Actualiza un archivo con los reemplazos especificados."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        for replacement in replacements:
            if replacement["old"] in content:
                content = content.replace(replacement["old"], replacement["new"])
                print(f"  ✓ Reemplazado en {file_path.name}")
            else:
                print(f"  ⚠️  No se encontró: {replacement['old'][:50]}...")
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        else:
            print(f"  ⚠️  No se realizaron cambios en {file_path.name}")
            return False
            
    except Exception as e:
        print(f"  ❌ Error procesando {file_path}: {e}")
        return False

def main():
    print("=== ACTUALIZANDO URLs HARCODEADAS EN CLINICFORGE ===\n")
    
    updated_count = 0
    total_files = len(FILES_TO_UPDATE)
    
    for file_info in FILES_TO_UPDATE:
        file_path = BASE_DIR / file_info["path"]
        
        if not file_path.exists():
            print(f"❌ Archivo no encontrado: {file_path}")
            continue
        
        print(f"📄 Procesando: {file_info['path']}")
        
        if update_file(file_path, file_info["replacements"]):
            updated_count += 1
        
        print()
    
    print(f"=== RESUMEN ===")
    print(f"Archivos procesados: {updated_count}/{total_files}")
    
    if updated_count > 0:
        print("\n✅ URLs hardcodeadas actualizadas correctamente.")
        print("\n📋 VARIABLES DE ENTORNO QUE DEBES CONFIGURAR:")
        print("1. FRONTEND_URL - URL del frontend (ej: https://tu-dominio.com)")
        print("2. PLATFORM_URL - URL de la plataforma (puede ser igual a FRONTEND_URL)")
        print("3. META_REDIRECT_URI - URL de callback de Meta OAuth")
        print("\n📝 Archivos actualizados:")
        for file_info in FILES_TO_UPDATE:
            file_path = BASE_DIR / file_info["path"]
            if file_path.exists():
                print(f"  - {file_info['path']}")
    else:
        print("⚠️ No se realizaron cambios. Verifica que los archivos existan.")

if __name__ == "__main__":
    main()