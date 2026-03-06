#!/usr/bin/env python3
"""
Script de verificación rápida: Documentación vs Código Real.
Usar para verificar que la documentación refleja exactamente el código.
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent

def verificar_campo_city():
    """Verifica que el campo city esté correctamente documentado e implementado."""
    print("🔍 VERIFICANDO CAMPO 'city' EN PACIENTES")
    print("=" * 50)
    
    # 1. Verificar en db.py
    db_path = project_root / "orchestrator_service" / "db.py"
    with open(db_path, 'r') as f:
        db_content = f.read()
    
    if "ADD COLUMN city VARCHAR(100)" in db_content:
        print("✅ Parche automático para 'city' encontrado en db.py")
    else:
        print("❌ Parche automático para 'city' NO encontrado en db.py")
    
    # 2. Verificar en documentación
    doc_path = project_root / "docs" / "NUEVO_PROCESO_ADMISION_ANAMNESIS.md"
    with open(doc_path, 'r') as f:
        doc_content = f.read()
    
    if "⚠️ NOTA IMPORTANTE SOBRE EL CAMPO `city`" in doc_content:
        print("✅ Documentación incluye nota sobre campo 'city'")
    else:
        print("❌ Documentación NO incluye nota sobre campo 'city'")
    
    # 3. Verificar migración
    migration_path = project_root / "orchestrator_service" / "migrations" / "patch_022_patient_admission_fields.sql"
    if migration_path.exists():
        print("✅ Migración patch_022 disponible")
    else:
        print("⚠️  Migración patch_022 NO encontrada")

def verificar_jobs_programados():
    """Verifica que el sistema de jobs esté correctamente documentado."""
    print("\n🔍 VERIFICANDO SISTEMA DE JOBS PROGRAMADOS")
    print("=" * 50)
    
    # 1. Verificar directorio jobs
    jobs_dir = project_root / "orchestrator_service" / "jobs"
    if jobs_dir.exists():
        files = list(jobs_dir.glob("*.py"))
        print(f"✅ Directorio jobs encontrado ({len(files)} archivos)")
    else:
        print("❌ Directorio jobs NO encontrado")
    
    # 2. Verificar documentación
    docs_to_check = [
        ("CONTEXTO_AGENTE_IA.md", "CONTEXTO_AGENTE_IA.md"),
        ("SISTEMA_JOBS_PROGRAMADOS.md", "Documentación específica de jobs"),
        ("SISTEMA_SEGUIMIENTO_POST_ATENCION.md", "Documentación de seguimiento"),
    ]
    
    for doc_name, desc in docs_to_check:
        doc_path = project_root / "docs" / doc_name
        if doc_path.exists():
            with open(doc_path, 'r') as f:
                content = f.read()
            
            if "JobScheduler" in content or "jobs programados" in content:
                print(f"✅ {desc}: menciona sistema de jobs")
            else:
                print(f"⚠️  {desc}: NO menciona sistema de jobs")
        else:
            print(f"❌ {desc}: documento NO encontrado")

def verificar_automationservice():
    """Verifica que AutomationService esté desactivado."""
    print("\n🔍 VERIFICANDO AUTOMATIONSERVICE")
    print("=" * 50)
    
    main_path = project_root / "orchestrator_service" / "main.py"
    with open(main_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    automation_active = False
    for line in lines:
        if "await automation_service.start()" in line and not line.strip().startswith("#"):
            automation_active = True
            break
    
    if automation_active:
        print("❌ AutomationService ACTIVO (debe estar desactivado)")
    else:
        print("✅ AutomationService desactivado (correcto)")

def verificar_estado_documento():
    """Verifica que el documento de estado actual exista."""
    print("\n🔍 VERIFICANDO DOCUMENTACIÓN DE ESTADO ACTUAL")
    print("=" * 50)
    
    estado_path = project_root / "ESTADO_ACTUAL_SISTEMA.md"
    if estado_path.exists():
        print("✅ Documento ESTADO_ACTUAL_SISTEMA.md encontrado")
        
        with open(estado_path, 'r') as f:
            content = f.read()
        
        if "DOCUMENTACIÓN ACTUALIZADA PARA REFLEJAR CÓDIGO REAL" in content:
            print("✅ Documento actualizado correctamente")
        else:
            print("⚠️  Documento podría no estar actualizado")
    else:
        print("❌ Documento ESTADO_ACTUAL_SISTEMA.md NO encontrado")

def main():
    """Función principal."""
    print("🚀 VERIFICACIÓN DE DOCUMENTACIÓN vs CÓDIGO")
    print("=" * 70)
    print("Propósito: Verificar que la documentación refleja exactamente el código real.")
    print("=" * 70)
    
    verificar_campo_city()
    verificar_jobs_programados()
    verificar_automationservice()
    verificar_estado_documento()
    
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE VERIFICACIÓN")
    print("\n🎯 INTERPRETACIÓN DE RESULTADOS:")
    print("✅ = Correcto - Documentación coincide con código")
    print("⚠️  = Advertencia - Posible desfase menor")
    print("❌ = Error - Desfase crítico identificado")
    
    print("\n🔧 ACCIONES RECOMENDADAS:")
    print("1. Corregir cualquier ❌ identificado")
    print("2. Revisar ⚠️  para posibles mejoras")
    print("3. Ejecutar este script regularmente para mantener sincronización")
    print("4. Consultar ESTADO_ACTUAL_SISTEMA.md para estado completo")

if __name__ == "__main__":
    main()