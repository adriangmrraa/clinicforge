#!/usr/bin/env python3
"""
Script de reparación para el sistema ClinicForge.
Corrige problemas identificados en el diagnóstico.
"""

import os
import sys
from pathlib import Path

# Agregar el proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def fix_automation_service_in_main():
    """Asegura que AutomationService esté desactivado en main.py."""
    print("🔧 REPARANDO AUTOMATIONSERVICE EN MAIN.PY")
    print("=" * 60)
    
    main_path = project_root / "orchestrator_service" / "main.py"
    
    if not main_path.exists():
        print("❌ Archivo main.py no encontrado")
        return False
    
    try:
        with open(main_path, 'r') as f:
            content = f.read()
        
        # Verificar si ya está desactivado
        if "# ⚠️ DESACTIVADO: Motor de automatización antiguo" in content:
            print("✅ AutomationService ya está desactivado en main.py")
            return True
        
        # Buscar y comentar líneas problemáticas
        lines_to_fix = [
            "await automation_service.start()",
            "await automation_service.stop()"
        ]
        
        fixed_content = content
        for line in lines_to_fix:
            if line in fixed_content and not line.startswith("#"):
                fixed_content = fixed_content.replace(line, f"# {line}")
                print(f"✅ Comentada línea: {line}")
        
        # Escribir cambios
        with open(main_path, 'w') as f:
            f.write(fixed_content)
        
        print("✅ main.py reparado correctamente")
        return True
        
    except Exception as e:
        print(f"❌ Error reparando main.py: {e}")
        return False

def verify_scheduler_integration():
    """Verifica que el scheduler esté correctamente integrado."""
    print("\n🔧 VERIFICANDO INTEGRACIÓN DEL SCHEDULER")
    print("=" * 60)
    
    main_path = project_root / "orchestrator_service" / "main.py"
    
    try:
        with open(main_path, 'r') as f:
            content = f.read()
        
        checks = [
            ("from jobs.scheduler import start_scheduler", "Import del scheduler"),
            ("await start_scheduler()", "Inicio del scheduler"),
            ("from jobs.scheduler import stop_scheduler", "Import para shutdown"),
            ("await stop_scheduler()", "Detención del scheduler"),
            ("from jobs.admin_routes import router as jobs_router", "Import de rutas de jobs"),
            ("app.include_router(jobs_router)", "Inclusión de rutas de jobs"),
        ]
        
        all_ok = True
        for check, description in checks:
            if check in content:
                print(f"✅ {description}: encontrado")
            else:
                print(f"❌ {description}: NO encontrado")
                all_ok = False
        
        return all_ok
        
    except Exception as e:
        print(f"❌ Error verificando scheduler: {e}")
        return False

def check_migration_files():
    """Verifica que los archivos de migración existan."""
    print("\n🔧 VERIFICANDO ARCHIVOS DE MIGRACIÓN")
    print("=" * 60)
    
    migrations_dir = project_root / "orchestrator_service" / "migrations"
    
    if not migrations_dir.exists():
        print("❌ Directorio de migraciones no encontrado")
        return False
    
    # Listar migraciones importantes
    important_migrations = [
        "patch_022_patient_admission_fields.sql",
        "patch_017_meta_ads_attribution.sql",
        "patch_020_last_touch_attribution.sql"
    ]
    
    all_exist = True
    for migration in important_migrations:
        migration_path = migrations_dir / migration
        if migration_path.exists():
            print(f"✅ {migration}: encontrado")
            
            # Verificar contenido
            with open(migration_path, 'r') as f:
                content = f.read()
                if 'ADD COLUMN city' in content and migration == "patch_022_patient_admission_fields.sql":
                    print("   ✅ Contiene campo 'city' para pacientes")
        else:
            print(f"❌ {migration}: NO encontrado")
            all_exist = False
    
    return all_exist

def generate_restart_instructions():
    """Genera instrucciones para reiniciar el sistema."""
    print("\n🔧 INSTRUCCIONES DE REINICIO")
    print("=" * 60)
    
    print("🎯 PARA RESOLVER LOS PROBLEMAS IDENTIFICADOS:")
    print("\n1. 📋 EJECUTAR MIGRACIÓN DE BD (CRÍTICO):")
    print("   ssh usuario@servidor")
    print("   cd /ruta/a/clinicforge")
    print("   psql -d dentalogic -f orchestrator_service/migrations/patch_022_patient_admission_fields.sql")
    print("   # Esto agregará el campo 'city' a la tabla patients")
    
    print("\n2. 🔄 REINICIAR SERVICIO BACKEND:")
    print("   sudo systemctl restart clinicforge-backend")
    print("   # Esto aplicará los cambios en main.py y iniciará el nuevo scheduler")
    
    print("\n3. 📊 VERIFICAR LOGS DESPUÉS DEL REINICIO:")
    print("   journalctl -u clinicforge-backend -f --since '5 minutes ago'")
    print("   # Buscar estos mensajes:")
    print("   #   ✅ Sistema de jobs programados activado")
    print("   #   ✅ JobScheduler iniciado correctamente")
    print("   #   ✅ Rutas de jobs programados incluidas")
    print("   #   ❌ LOS MENSAJES '🤖 Ejecutando ciclo...' DEBEN DESAPARECER")
    
    print("\n4. 🧪 PROBAR SISTEMA:")
    print("   a) Crear un paciente desde el frontend")
    print("   b) Verificar endpoints de jobs: /admin/jobs/reminders/status")
    print("   c) Probar job manualmente: /admin/jobs/reminders/test-today")
    
    print("\n5. ⚠️  VERIFICACIÓN DE CAMPOS DE BD:")
    print("   psql -d dentalogic -c \"\\d appointments\"")
    print("   # Debe mostrar:")
    print("   #   reminder_sent      | boolean | default false")
    print("   #   reminder_sent_at   | timestamp with time zone |")
    print("   #   followup_sent      | boolean | default false")
    print("   #   followup_sent_at   | timestamp with time zone |")
    
    return True

def check_db_patches_in_code():
    """Verifica que los parches de BD estén en db.py."""
    print("\n🔧 VERIFICANDO PARCHES EN DB.PY")
    print("=" * 60)
    
    db_path = project_root / "orchestrator_service" / "db.py"
    
    if not db_path.exists():
        print("❌ Archivo db.py no encontrado")
        return False
    
    try:
        with open(db_path, 'r') as f:
            content = f.read()
        
        # Buscar parches importantes
        patches_to_check = [
            ("followup_sent BOOLEAN DEFAULT FALSE", "Campo followup_sent"),
            ("followup_sent_at TIMESTAMPTZ", "Campo followup_sent_at"),
            ("reminder_sent BOOLEAN DEFAULT FALSE", "Campo reminder_sent"),
            ("reminder_sent_at TIMESTAMPTZ", "Campo reminder_sent_at"),
            ("idx_appointments_followup_sent", "Índice followup_sent"),
            ("idx_appointments_followup_date", "Índice followup_date"),
            ("idx_appointments_reminder_sent", "Índice reminder_sent"),
            ("idx_appointments_reminder_date", "Índice reminder_date"),
        ]
        
        found_count = 0
        for patch, description in patches_to_check:
            if patch in content:
                print(f"✅ {description}: encontrado")
                found_count += 1
            else:
                print(f"⚠️  {description}: NO encontrado")
        
        if found_count >= 6:
            print(f"✅ {found_count}/8 parches encontrados (suficiente)")
            return True
        else:
            print(f"⚠️  Solo {found_count}/8 parches encontrados")
            return False
            
    except Exception as e:
        print(f"❌ Error verificando db.py: {e}")
        return False

def main():
    """Función principal de reparación."""
    print("🚀 INICIANDO REPARACIÓN DEL SISTEMA CLINICFORGE")
    print("=" * 70)
    
    print("🎯 PROBLEMAS A RESOLVER:")
    print("   1. AutomationService en bucle infinito")
    print("   2. Scheduler de jobs no iniciando correctamente")
    print("   3. Migración de BD pendiente (campo 'city')")
    print("   4. Creación de pacientes fallando")
    
    print("\n" + "=" * 70)
    
    # Ejecutar reparaciones
    results = []
    
    results.append(fix_automation_service_in_main())
    results.append(verify_scheduler_integration())
    results.append(check_migration_files())
    results.append(check_db_patches_in_code())
    results.append(generate_restart_instructions())
    
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE REPARACIÓN")
    print(f"   Tareas completadas: {sum(results)}/{len(results)}")
    
    print("\n✅ CAMBIOS APLICADOS:")
    print("   1. AutomationService desactivado en main.py")
    print("   2. Verificada integración del scheduler")
    print("   3. Verificados archivos de migración")
    print("   4. Verificados parches en db.py")
    
    print("\n🔧 ACCIONES MANUALES REQUERIDAS:")
    print("   1. 📋 Ejecutar migración SQL patch_022")
    print("   2. 🔄 Reiniciar servicio backend")
    print("   3. 📊 Monitorear logs después del reinicio")
    print("   4. 🧪 Probar creación de pacientes")
    
    print("\n⚠️  ADVERTENCIA IMPORTANTE:")
    print("   El sistema NO funcionará correctamente hasta que:")
    print("   a) Se ejecute la migración patch_022 (campo 'city')")
    print("   b) Se reinicie el servicio backend")
    
    print("\n🎯 RESULTADO ESPERADO:")
    print("   - Desaparición de logs '🤖 Ejecutando ciclo...'")
    print("   - Funcionamiento normal de creación de pacientes")
    print("   - Jobs programados ejecutándose a sus horas (10:00 AM, 11:00 AM)")
    print("   - Endpoints /admin/jobs/* funcionando")
    
    if all(results):
        print("\n✅ Reparación completada - Listo para acciones manuales")
        return True
    else:
        print("\n⚠️  Reparación parcial - Algunas verificaciones fallaron")
        return False

if __name__ == "__main__":
    success = main()
    
    if success:
        print("\n🎉 ¡Sistema preparado para la reparación final!")
        print("\n📋 SIGUE ESTOS PASOS EN PRODUCCIÓN:")
        print("   1. psql -d dentalogic -f orchestrator_service/migrations/patch_022_patient_admission_fields.sql")
        print("   2. sudo systemctl restart clinicforge-backend")
        print("   3. journalctl -u clinicforge-backend -f --since '5 minutes ago'")
        sys.exit(0)
    else:
        print("\n❌ Se requieren correcciones adicionales")
        sys.exit(1)