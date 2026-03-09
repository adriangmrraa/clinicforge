#!/usr/bin/env python3
"""
Auditoría rápida de documentación vs código.
"""

import os
import re
from pathlib import Path

project_root = Path(__file__).parent

def check_system_prompt():
    print("🔍 SYSTEM PROMPT")
    print("=" * 50)
    
    main_path = project_root / "orchestrator_service" / "main.py"
    with open(main_path, 'r') as f:
        content = f.read()
    
    # Buscar system prompt
    if 'def build_system_prompt(' in content:
        print("✅ Función build_system_prompt encontrada")
        
        # Extraer prompt
        start = content.find('def build_system_prompt(')
        return_start = content.find('return f"""', start)
        if return_start != -1:
            prompt_end = content.find('"""', return_start + len('return f"""'))
            prompt = content[return_start + len('return f"""'):prompt_end]
            
            checks = [
                ("Dra. María Laura Delgado", "Identidad"),
                ("secretaria virtual", "Rol"),
                ("book_appointment", "Tool agendar"),
                ("triage_urgency", "Tool triage"),
                ("SEGUIMIENTO POST-ATENCIÓN", "Seguimiento"),
                ("6 reglas maxilofaciales", "Reglas urgencia"),
            ]
            
            for text, desc in checks:
                if text in prompt:
                    print(f"   ✅ {desc}: presente")
                else:
                    print(f"   ⚠️  {desc}: NO presente")
    else:
        print("❌ Función build_system_prompt NO encontrada")

def check_jobs_system():
    print("\n🔍 SISTEMA DE JOBS")
    print("=" * 50)
    
    jobs_dir = project_root / "orchestrator_service" / "jobs"
    
    if jobs_dir.exists():
        files = list(jobs_dir.glob("*.py"))
        print(f"✅ Directorio jobs encontrado ({len(files)} archivos)")
        
        for file in files:
            with open(file, 'r') as f:
                content = f.read()
            
            if file.name == "scheduler.py":
                if "class JobScheduler" in content:
                    print("   ✅ JobScheduler implementado")
                elif "class AsyncScheduler" in content:
                    print("   ✅ AsyncScheduler implementado")
                else:
                    print("   ⚠️  No se encontró clase scheduler")
            
            elif file.name == "reminders.py":
                if "send_appointment_reminders" in content:
                    print("   ✅ Job reminders implementado")
                else:
                    print("   ⚠️  Job reminders NO implementado")
            
            elif file.name == "followups.py":
                if "send_post_treatment_followups" in content:
                    print("   ✅ Job followups implementado")
                else:
                    print("   ⚠️  Job followups NO implementado")
    else:
        print("❌ Directorio jobs NO encontrado")
    
    # Verificar integración
    main_path = project_root / "orchestrator_service" / "main.py"
    with open(main_path, 'r') as f:
        content = f.read()
    
    if "await start_scheduler()" in content:
        print("✅ Scheduler integrado en main.py")
    else:
        print("⚠️  Scheduler NO integrado en main.py")

def check_database_schema():
    print("\n🔍 ESQUEMA DE BD")
    print("=" * 50)
    
    db_path = project_root / "orchestrator_service" / "db.py"
    with open(db_path, 'r') as f:
        content = f.read()
    
    checks = [
        ("followup_sent BOOLEAN DEFAULT FALSE", "Campo followup_sent"),
        ("followup_sent_at TIMESTAMPTZ", "Campo followup_sent_at"),
        ("reminder_sent BOOLEAN DEFAULT FALSE", "Campo reminder_sent"),
        ("reminder_sent_at TIMESTAMPTZ", "Campo reminder_sent_at"),
        ("ADD COLUMN city", "Campo city en patients"),
    ]
    
    for text, desc in checks:
        if text in content:
            print(f"✅ {desc}: presente")
        else:
            print(f"⚠️  {desc}: NO presente")

def check_automation_service():
    print("\n🔍 AUTOMATIONSERVICE")
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
        print("✅ AutomationService desactivado")

def check_documentation_vs_reality():
    print("\n🔍 DOCUMENTACIÓN vs REALIDAD")
    print("=" * 50)
    
    # Verificar documentos clave
    docs_to_check = [
        ("SISTEMA_JOBS_PROGRAMADOS.md", "Documentación de jobs"),
        ("SISTEMA_SEGUIMIENTO_POST_ATENCION.md", "Documentación seguimiento"),
        ("NUEVO_PROCESO_ADMISION_ANAMNESIS.md", "Documentación admisión"),
        ("12_resumen_funcional_no_tecnico.md", "Resumen funcional"),
    ]
    
    for doc_name, desc in docs_to_check:
        doc_path = project_root / "docs" / doc_name
        if doc_path.exists():
            print(f"✅ {desc}: documento existe")
            
            with open(doc_path, 'r') as f:
                content = f.read()
            
            # Verificar contenido básico
            if doc_name == "SISTEMA_JOBS_PROGRAMADOS.md":
                if "JobScheduler" in content or "AsyncScheduler" in content:
                    print(f"   ✅ Menciona scheduler")
                else:
                    print(f"   ⚠️  NO menciona scheduler")
            
            elif doc_name == "NUEVO_PROCESO_ADMISION_ANAMNESIS.md":
                if "city" in content:
                    print(f"   ✅ Menciona campo city")
                else:
                    print(f"   ⚠️  NO menciona campo city")
        else:
            print(f"❌ {desc}: documento NO existe")

def main():
    print("🚀 AUDITORÍA RÁPIDA: DOCUMENTACIÓN vs CÓDIGO")
    print("=" * 70)
    
    check_system_prompt()
    check_jobs_system()
    check_database_schema()
    check_automation_service()
    check_documentation_vs_reality()
    
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE AUDITORÍA")
    print("\n🎯 ACCIONES RECOMENDADAS:")
    print("1. Verificar que todos los ✅ estén presentes")
    print("2. Corregir los ⚠️  identificados")
    print("3. Actualizar documentación para reflejar código real")
    print("4. Asegurar que AutomationService esté desactivado")
    print("5. Verificar integración completa del scheduler")

if __name__ == "__main__":
    main()