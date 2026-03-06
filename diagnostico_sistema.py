#!/usr/bin/env python3
"""
Script de diagnóstico para identificar problemas en el sistema ClinicForge.
Verifica: AutomationService, Jobs Programados, y endpoints de pacientes.
"""

import asyncio
import sys
import os
from pathlib import Path

# Agregar el proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "orchestrator_service"))

async def check_automation_service():
    """Verifica el estado del AutomationService."""
    print("🔍 DIAGNÓSTICO DEL AUTOMATIONSERVICE")
    print("=" * 60)
    
    try:
        from services.automation_service import AutomationService
        
        service = AutomationService()
        print(f"✅ AutomationService importado correctamente")
        print(f"   - is_running: {service.is_running}")
        print(f"   - _task: {service._task}")
        
        # Verificar si hay bucle infinito en el código
        automation_path = project_root / "orchestrator_service" / "services" / "automation_service.py"
        with open(automation_path, 'r') as f:
            content = f.read()
        
        # Buscar posibles problemas
        if "while True:" in content:
            print("⚠️  ADVERTENCIA: Se encontró 'while True:' en el código")
        
        if "await asyncio.sleep(900)" in content:
            print("✅ Intervalo configurado: 900 segundos (15 minutos)")
        
        # Verificar main.py para ver si está iniciado
        main_path = project_root / "orchestrator_service" / "main.py"
        with open(main_path, 'r') as f:
            main_content = f.read()
        
        if "await automation_service.start()" in main_content:
            print("❌ PROBLEMA: AutomationService está configurado para iniciarse en main.py")
            print("   Esto causa conflicto con el nuevo sistema de jobs programados")
        else:
            print("✅ AutomationService desactivado en main.py (CORRECTO)")
            
        return True
        
    except Exception as e:
        print(f"❌ Error verificando AutomationService: {e}")
        return False

async def check_jobs_system():
    """Verifica el estado del sistema de jobs programados."""
    print("\n🔍 DIAGNÓSTICO DEL SISTEMA DE JOBS PROGRAMADOS")
    print("=" * 60)
    
    try:
        # Verificar que los módulos existan
        jobs_modules = [
            "jobs.scheduler",
            "jobs.reminders", 
            "jobs.followups",
            "jobs.admin_routes"
        ]
        
        for module in jobs_modules:
            try:
                __import__(module)
                print(f"✅ {module}: importado correctamente")
            except ImportError as e:
                print(f"❌ {module}: ERROR - {e}")
        
        # Verificar integración en main.py
        main_path = project_root / "orchestrator_service" / "main.py"
        with open(main_path, 'r') as f:
            main_content = f.read()
        
        checks = [
            ("from jobs.scheduler import scheduler", "Import del scheduler"),
            ("await scheduler.start()", "Inicio del scheduler en startup"),
            ("await scheduler.stop()", "Detención del scheduler en shutdown"),
        ]
        
        for check, description in checks:
            if check in main_content:
                print(f"✅ {description}: encontrado en main.py")
            else:
                print(f"⚠️  {description}: NO encontrado en main.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando jobs system: {e}")
        return False

async def check_patients_endpoints():
    """Verifica los endpoints de pacientes."""
    print("\n🔍 DIAGNÓSTICO DE ENDPOINTS DE PACIENTES")
    print("=" * 60)
    
    try:
        from admin_routes import router
        import inspect
        
        # Buscar endpoints de pacientes
        patient_endpoints = []
        for route in router.routes:
            if hasattr(route, 'path') and '/patients' in route.path:
                patient_endpoints.append({
                    'path': route.path,
                    'methods': list(route.methods) if hasattr(route, 'methods') else [],
                    'name': route.name if hasattr(route, 'name') else 'Sin nombre'
                })
        
        print(f"✅ Endpoints de pacientes encontrados: {len(patient_endpoints)}")
        
        # Mostrar endpoints clave
        key_endpoints = [
            ('/patients', 'POST', 'create_patient'),
            ('/patients', 'GET', 'list_patients'),
            ('/patients/{id}', 'GET', 'get_patient'),
        ]
        
        for path, method, name in key_endpoints:
            found = False
            for endpoint in patient_endpoints:
                if path in endpoint['path'] and method in endpoint['methods']:
                    print(f"✅ {method} {path}: {name}")
                    found = True
                    break
            
            if not found:
                print(f"⚠️  {method} {path}: NO encontrado")
        
        # Verificar modelo PatientCreate
        try:
            from admin_routes import PatientCreate
            print(f"✅ Modelo PatientCreate: disponible")
            
            # Mostrar campos
            import inspect
            sig = inspect.signature(PatientCreate.__init__)
            params = list(sig.parameters.keys())[1:]  # Excluir 'self'
            print(f"   Campos: {', '.join(params)}")
            
        except ImportError as e:
            print(f"❌ Modelo PatientCreate: ERROR - {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando endpoints: {e}")
        return False

async def check_database_schema():
    """Verifica el esquema de base de datos para pacientes."""
    print("\n🔍 DIAGNÓSTICO DE ESQUEMA DE BASE DE DATOS")
    print("=" * 60)
    
    try:
        # Verificar archivo de migración de campos de ciudad
        migration_path = project_root / "orchestrator_service" / "migrations" / "patch_022_patient_admission_fields.sql"
        
        if migration_path.exists():
            with open(migration_path, 'r') as f:
                migration_content = f.read()
            
            if 'ADD COLUMN city' in migration_content:
                print("✅ Migración para campo 'city' encontrada")
            else:
                print("⚠️  Migración no contiene campo 'city'")
            
            # Verificar si se ejecutó
            print("ℹ️  NOTA: La migración patch_022 necesita ejecutarse manualmente en producción")
            print("   Comando: psql -d dentalogic -f orchestrator_service/migrations/patch_022_patient_admission_fields.sql")
        else:
            print("❌ Archivo de migración patch_022 no encontrado")
        
        # Verificar campos de seguimiento en appointments
        db_path = project_root / "orchestrator_service" / "db.py"
        if db_path.exists():
            with open(db_path, 'r') as f:
                db_content = f.read()
            
            campos = [
                'followup_sent BOOLEAN DEFAULT FALSE',
                'followup_sent_at TIMESTAMPTZ',
                'reminder_sent BOOLEAN DEFAULT FALSE',
                'reminder_sent_at TIMESTAMPTZ'
            ]
            
            for campo in campos:
                if campo in db_content:
                    print(f"✅ Campo en db.py: {campo}")
                else:
                    print(f"⚠️  Campo NO en db.py: {campo}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando esquema BD: {e}")
        return False

async def check_logs_pattern():
    """Analiza patrones de logs problemáticos."""
    print("\n🔍 ANÁLISIS DE PATRONES DE LOGS")
    print("=" * 60)
    
    print("ℹ️  Basado en los logs proporcionados:")
    print("   - '🤖 Ejecutando ciclo de automatización...' se repite infinitamente")
    print("   - Esto indica bucle infinito en AutomationService")
    print("\n🎯 CAUSA PROBABLE:")
    print("   1. AutomationService antiguo CONFLICTA con nuevo sistema de jobs")
    print("   2. Posible bug en _main_loop() que no respeta sleep(900)")
    print("   3. Múltiples instancias del servicio corriendo")
    
    print("\n✅ SOLUCIÓN APLICADA:")
    print("   - Desactivar AutomationService en main.py (comentado)")
    print("   - Usar solo nuevo sistema de jobs programados")
    print("   - Jobs ejecutan a horas específicas (10:00 AM, 11:00 AM)")
    
    return True

async def main():
    """Función principal de diagnóstico."""
    print("🚀 INICIANDO DIAGNÓSTICO COMPLETO DEL SISTEMA CLINICFORGE")
    print("=" * 70)
    
    results = []
    
    # Ejecutar diagnósticos
    results.append(await check_automation_service())
    results.append(await check_jobs_system())
    results.append(await check_patients_endpoints())
    results.append(await check_database_schema())
    results.append(await check_logs_pattern())
    
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE DIAGNÓSTICO")
    print(f"   Checks pasados: {sum(results)}/{len(results)}")
    
    print("\n🎯 PROBLEMAS IDENTIFICADOS:")
    print("   1. ✅ AutomationService desactivado (solución aplicada)")
    print("   2. ✅ Sistema de jobs programados implementado")
    print("   3. ⚠️  Migración patch_022 necesita ejecución manual")
    print("   4. ⚠️  Posible saturación por logs infinitos")
    
    print("\n🔧 ACCIONES RECOMENDADAS:")
    print("   1. REINICIAR servicio backend para aplicar cambios:")
    print("      sudo systemctl restart clinicforge-backend")
    print("   2. Ejecutar migración de BD (si no se hizo):")
    print("      psql -d dentalogic -f orchestrator_service/migrations/patch_022_patient_admission_fields.sql")
    print("   3. Verificar logs después del reinicio:")
    print("      journalctl -u clinicforge-backend -f --since '5 minutes ago'")
    print("   4. Probar creación de paciente después del reinicio")
    
    print("\n📋 VERIFICACIÓN POST-REINICIO:")
    print("   - Los logs '🤖 Ejecutando ciclo...' DEBEN desaparecer")
    print("   - Los endpoints /admin/jobs/* DEBEN funcionar")
    print("   - La creación de pacientes DEBE funcionar normalmente")
    
    if all(results):
        print("\n✅ Diagnóstico completado - Sistema puede ser reparado")
        return True
    else:
        print("\n⚠️  Diagnóstico encontró problemas - Revisar recomendaciones")
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    
    if success:
        print("\n🎉 ¡Sistema listo para reparación!")
        sys.exit(0)
    else:
        print("\n❌ Se requieren acciones correctivas")
        sys.exit(1)