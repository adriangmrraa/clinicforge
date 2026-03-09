#!/usr/bin/env python3
"""
Auditoría completa de documentación vs código en ClinicForge.
Identifica desfases entre lo documentado y la realidad del código.
"""

import os
import sys
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set

# Agregar el proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def analyze_system_prompt_documentation() -> Tuple[bool, List[str]]:
    """Analiza la documentación del system prompt vs código real."""
    print("🔍 AUDITORÍA: SYSTEM PROMPT")
    print("=" * 60)
    
    issues = []
    
    # Leer documentación del system prompt
    prompt_docs = [
        project_root / "docs" / "CONTEXTO_AGENTE_IA.md",
        project_root / "docs" / "06_ai_prompt_template.md",
        project_root / "docs" / "04_agent_logic_and_persona.md"
    ]
    
    # Leer system prompt real del código
    main_path = project_root / "orchestrator_service" / "main.py"
    
    if not main_path.exists():
        issues.append("❌ main.py no encontrado")
        return False, issues
    
    try:
        with open(main_path, 'r') as f:
            main_content = f.read()
        
        # Buscar función build_system_prompt
        if 'def build_system_prompt(' not in main_content:
            issues.append("❌ Función build_system_prompt no encontrada en main.py")
        else:
            print("✅ Función build_system_prompt encontrada en código")
        
        # Extraer system prompt del código
        prompt_start = main_content.find('def build_system_prompt(')
        if prompt_start != -1:
            # Buscar el return del prompt
            return_start = main_content.find('return f"""', prompt_start)
            if return_start != -1:
                prompt_end = main_content.find('"""', return_start + len('return f"""'))
                if prompt_end != -1:
                    actual_prompt = main_content[return_start + len('return f"""'):prompt_end]
                    
                    # Verificar elementos clave
                    key_elements = [
                        ("Dra. María Laura Delgado", "Identidad de la Dra."),
                        ("secretaria virtual", "Rol de secretaria virtual"),
                        ("voseo argentino", "Uso de voseo"),
                        ("book_appointment", "Tool de agendar turnos"),
                        ("triage_urgency", "Tool de triage"),
                        ("SEGUIMIENTO POST-ATENCIÓN", "Instrucciones de seguimiento"),
                        ("6 reglas maxilofaciales", "Reglas de urgencia"),
                    ]
                    
                    for element, description in key_elements:
                        if element in actual_prompt:
                            print(f"✅ {description}: presente en system prompt")
                        else:
                            issues.append(f"⚠️  {description}: NO presente en system prompt")
                    
                    # Verificar documentación vs realidad
                    for doc_path in prompt_docs:
                        if doc_path.exists():
                            with open(doc_path, 'r') as f:
                                doc_content = f.read()
                            
                            # Verificar que la documentación mencione elementos reales
                            doc_name = doc_path.name
                            if "Dra. María Laura Delgado" in doc_content:
                                print(f"✅ Documentación {doc_name}: menciona identidad correcta")
                            else:
                                issues.append(f"⚠️  Documentación {doc_name}: NO menciona identidad correcta")
                            
                            if "secretaria virtual" in doc_content:
                                print(f"✅ Documentación {doc_name}: menciona rol correcto")
                            else:
                                issues.append(f"⚠️  Documentación {doc_name}: NO menciona rol correcto")
        
        return len(issues) == 0, issues
        
    except Exception as e:
        issues.append(f"❌ Error analizando system prompt: {e}")
        return False, issues

def analyze_jobs_system_documentation() -> Tuple[bool, List[str]]:
    """Analiza la documentación del sistema de jobs vs código real."""
    print("\n🔍 AUDITORÍA: SISTEMA DE JOBS PROGRAMADOS")
    print("=" * 60)
    
    issues = []
    
    # Verificar estructura real del código
    jobs_dir = project_root / "orchestrator_service" / "jobs"
    
    if not jobs_dir.exists():
        issues.append("❌ Directorio de jobs no encontrado")
        return False, issues
    
    # Archivos esperados vs reales
    expected_files = [
        ("scheduler.py", "Sistema de scheduling"),
        ("reminders.py", "Job de recordatorios"),
        ("followups.py", "Job de seguimiento"),
        ("admin_routes.py", "Endpoints de administración"),
        ("__init__.py", "Módulo de jobs"),
    ]
    
    for filename, description in expected_files:
        file_path = jobs_dir / filename
        if file_path.exists():
            print(f"✅ {description}: archivo encontrado")
            
            # Verificar contenido básico
            with open(file_path, 'r') as f:
                content = f.read()
                
            if filename == "scheduler.py":
                if "class JobScheduler" in content or "class AsyncScheduler" in content:
                    print(f"   ✅ Contiene clase scheduler")
                else:
                    issues.append(f"⚠️  {filename}: NO contiene clase scheduler")
                    
            elif filename == "reminders.py":
                if "send_appointment_reminders" in content:
                    print(f"   ✅ Contiene función send_appointment_reminders")
                else:
                    issues.append(f"⚠️  {filename}: NO contiene función principal")
                    
            elif filename == "followups.py":
                if "send_post_treatment_followups" in content:
                    print(f"   ✅ Contiene función send_post_treatment_followups")
                else:
                    issues.append(f"⚠️  {filename}: NO contiene función principal")
                    
        else:
            issues.append(f"❌ {description}: archivo NO encontrado")
    
    # Verificar integración en main.py
    main_path = project_root / "orchestrator_service" / "main.py"
    with open(main_path, 'r') as f:
        main_content = f.read()
    
    integration_checks = [
        ("from jobs.scheduler import start_scheduler", "Import del scheduler"),
        ("await start_scheduler()", "Inicio del scheduler"),
        ("from jobs.admin_routes import router as jobs_router", "Import de rutas"),
        ("app.include_router(jobs_router)", "Inclusión de rutas"),
    ]
    
    for check, description in integration_checks:
        if check in main_content:
            print(f"✅ {description}: integrado en main.py")
        else:
            issues.append(f"⚠️  {description}: NO integrado en main.py")
    
    # Verificar documentación vs realidad
    docs_path = project_root / "docs" / "SISTEMA_JOBS_PROGRAMADOS.md"
    if docs_path.exists():
        with open(docs_path, 'r') as f:
            docs_content = f.read()
        
        # Verificar que la documentación mencione elementos reales
        if "JobScheduler" in docs_content or "AsyncScheduler" in docs_content:
            print("✅ Documentación menciona scheduler correcto")
        else:
            issues.append("⚠️  Documentación NO menciona scheduler correcto")
            
        if "send_appointment_reminders" in docs_content:
            print("✅ Documentación menciona job de recordatorios")
        else:
            issues.append("⚠️  Documentación NO menciona job de recordatorios")
            
        if "send_post_treatment_followups" in docs_content:
            print("✅ Documentación menciona job de seguimiento")
        else:
            issues.append("⚠️  Documentación NO menciona job de seguimiento")
    
    return len(issues) == 0, issues

def analyze_database_schema_documentation() -> Tuple[bool, List[str]]:
    """Analiza la documentación del esquema de BD vs código real."""
    print("\n🔍 AUDITORÍA: ESQUEMA DE BASE DE DATOS")
    print("=" * 60)
    
    issues = []
    
    # Verificar parches en db.py
    db_path = project_root / "orchestrator_service" / "db.py"
    
    if not db_path.exists():
        issues.append("❌ db.py no encontrado")
        return False, issues
    
    with open(db_path, 'r') as f:
        db_content = f.read()
    
    # Buscar parches importantes
    patches_to_check = [
        ("followup_sent BOOLEAN DEFAULT FALSE", "Campo followup_sent"),
        ("followup_sent_at TIMESTAMPTZ", "Campo followup_sent_at"),
        ("reminder_sent BOOLEAN DEFAULT FALSE", "Campo reminder_sent"),
        ("reminder_sent_at TIMESTAMPTZ", "Campo reminder_sent_at"),
        ("ADD COLUMN city", "Campo city en patients"),
    ]
    
    for patch, description in patches_to_check:
        if patch in db_content:
            print(f"✅ {description}: presente en db.py")
        else:
            issues.append(f"⚠️  {description}: NO presente en db.py")
    
    # Verificar migraciones
    migrations_dir = project_root / "orchestrator_service" / "migrations"
    if migrations_dir.exists():
        important_migrations = [
            "patch_022_patient_admission_fields.sql",
            "patch_017_meta_ads_attribution.sql",
            "patch_020_last_touch_attribution.sql",
        ]
        
        for migration in important_migrations:
            migration_path = migrations_dir / migration
            if migration_path.exists():
                print(f"✅ Migración {migration}: encontrada")
            else:
                issues.append(f"⚠️  Migración {migration}: NO encontrada")
    
    # Verificar documentación de esquema
    schema_docs = [
        project_root / "docs" / "meta_ads_database.md",
        project_root / "docs" / "NUEVO_PROCESO_ADMISION_ANAMNESIS.md",
    ]
    
    for doc_path in schema_docs:
        if doc_path.exists():
            with open(doc_path, 'r') as f:
                doc_content = f.read()
            
            doc_name = doc_path.name
            # Verificar menciones de campos importantes
            if "city" in doc_content and doc_name == "NUEVO_PROCESO_ADMISION_ANAMNESIS.md":
                print(f"✅ {doc_name}: menciona campo city")
            elif "city" not in doc_content and doc_name == "NUEVO_PROCESO_ADMISION_ANAMNESIS.md":
                issues.append(f"⚠️  {doc_name}: NO menciona campo city")
    
    return len(issues) == 0, issues

def analyze_patient_admission_documentation() -> Tuple[bool, List[str]]:
    """Analiza la documentación del proceso de admisión vs código real."""
    print("\n🔍 AUDITORÍA: PROCESO DE ADMISIÓN DE PACIENTES")
    print("=" * 60)
    
    issues = []
    
    # Leer documentación del proceso
    admission_doc = project_root / "docs" / "NUEVO_PROCESO_ADMISION_ANAMNESIS.md"
    
    if not admission_doc.exists():
        issues.append("❌ Documentación de admisión no encontrada")
        return False, issues
    
    with open(admission_doc, 'r') as f:
        doc_content = f.read()
    
    # Verificar campos documentados
    documented_fields = []
    field_patterns = [
        r"first_name", r"last_name", r"dni", r"birth_date",
        r"email", r"city", r"acquisition_source", r"insurance_provider"
    ]
    
    for pattern in field_patterns:
        if re.search(pattern, doc_content, re.IGNORECASE):
            documented_fields.append(pattern)
            print(f"✅ Campo {pattern}: documentado")
        else:
            issues.append(f"⚠️  Campo {pattern}: NO documentado")
    
    # Verificar tool book_appointment en código
    main_path = project_root / "orchestrator_service" / "main.py"
    with open(main_path, 'r') as f:
        main_content = f.read()
    
    # Buscar tool book_appointment
    if '@tool' in main_content and 'book_appointment' in main_content:
        tool_start = main_content.find('async def book_appointment(')
        if tool_start != -1:
            # Extraer parámetros de la tool
            tool_end = main_content.find('):', tool_start)
            if tool_end != -1:
                params_section = main_content[tool_start:tool_end + 2]
                
                # Verificar parámetros documentados vs reales
                expected_params = [
                    "first_name", "last_name", "dni", "birth_date",
                    "email", "city", "acquisition_source"
                ]
                
                for param in expected_params:
                    if param in params_section:
                        print(f"✅ Parámetro {param}: presente en tool book_appointment")
                    else:
                        issues.append(f"⚠️  Parámetro {param}: NO presente en tool book_appointment")
    
    # Verificar tool save_patient_anamnesis
    if 'save_patient_anamnesis' in main_content:
        print("✅ Tool save_patient_anamnesis: presente en código")
    else:
        issues.append("⚠️  Tool save_patient_anamnesis: NO presente en código")
    
    return len(issues) == 0, issues

def analyze_automation_service_status() -> Tuple[bool, List[str]]:
    """Analiza el estado del AutomationService vs documentación."""
    print("\n🔍 AUDITORÍA: AUTOMATIONSERVICE")
    print("=" * 60)
    
    issues = []
    
    # Verificar código del AutomationService
    automation_path = project_root / "orchestrator_service" / "services" / "automation_service.py"
    
    if not automation_path.exists():
        issues.append("❌ automation_service.py no encontrado")
        return False, issues
    
    with open(automation_path, 'r') as f:
        automation_content = f.read()
    
    # Verificar si está activo en main.py
    main_path = project_root / "orchestrator_service" / "main.py"
    with open(main_path, 'r') as f:
        main_content = f.read()
    
    # Buscar referencias a automation_service
    if "await automation_service.start()" in main_content:
        # Verificar si está comentado
        lines = main_content.split('\n')
        for i, line in enumerate(lines):
            if "await automation_service.start()" in line:
                if line.strip().startswith("#"):
                    print("✅ AutomationService: desactivado (comentado) en main.py")
                else:
                    issues.append("❌ AutomationService: ACTIVO en main.py (debe estar desactivado)")
                break
    
    # Verificar documentación
    docs_mention_automation = False
    docs_dir = project_root / "docs"
    for doc_file in docs_dir.glob("*.md"):
        with open(doc_file, 'r') as f:
            content = f.read()
            if "AutomationService" in content:
                docs_mention_automation = True
                print(f"✅ Documentación {doc_file.name}: menciona AutomationService")
    
    if not docs_mention_automation:
        print("ℹ️  AutomationService no mencionado en documentación (esperado si está desactivado)")
    
    return len(issues) == 0, issues

def generate_documentation_update_plan(all_issues: List[str]) -> Dict[str, List[str]]:
    """Genera un plan para actualizar la documentación."""
    print("\n📋 PLAN DE ACTUALIZACIÓN DE DOCUMENTACIÓN")
    print("=" * 60)
    
    update_plan = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": []
    }
    
    for issue in all_issues:
        if "❌" in issue:
            update_plan["critical"].append(issue)
        elif "⚠️" in issue and ("NO presente" in issue or "NO integrado" in issue):
            update_plan["high"].append(issue)
        elif "⚠️" in issue:
            update_plan["medium"].append(issue)
        else:
            update_plan["low"].append(issue)
    
    # Mostrar plan
    print(f"🔴 CRÍTICAS ({len(update_plan['critical'])}):")
    for issue in update_plan["critical"]:
        print(f"   • {issue}")
    
    print(f"\n🟠 ALTAS ({len(update_plan['high'])}):")
    for issue in update_plan["high"]:
        print(f"   • {issue}")
    
    print(f"\n🟡 MEDIAS ({len(update_plan['medium'])}):")
    for issue in update_plan["medium"]:
        print(f"   • {issue}")
    
    print(f"\n🟢 BAJAS ({len(update_plan['low'])}):")
    for issue in update_plan["low"]:
        print(f"   • {issue}")
    
    return update_plan

def main():
    """Función principal de auditoría."""
    print("🚀 AUDITORÍA COMPLETA: DOCUMENTACIÓN vs CÓDIGO")
    print("=" * 70)
    
    all_issues = []
    
    # Ejecutar auditorías
    results = []
    
    print("\n" + "=" * 70)
    print("🔍 EJECUTANDO AUDITORÍAS...")
    print("=" * 70)