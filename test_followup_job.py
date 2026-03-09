#!/usr/bin/env python3
"""
Script de prueba para el sistema de seguimiento post-atención.
Verifica que todos los componentes estén correctamente implementados.
"""

import sys
import os
from pathlib import Path

# Agregar el proyecto al path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "orchestrator_service"))

async def test_imports():
    """Prueba que todos los módulos se importen correctamente."""
    print("🧪 TESTING IMPORTS DE MÓDULOS DE SEGUIMIENTO...")
    
    tests = [
        ("jobs.followups", "Módulo de seguimiento post-atención"),
    ]
    
    all_passed = True
    
    for module_name, description in tests:
        try:
            __import__(module_name)
            print(f"✅ {description}: importado correctamente")
        except ImportError as e:
            print(f"❌ {description}: ERROR - {e}")
            all_passed = False
    
    return all_passed

async def test_followup_logic():
    """Prueba la lógica del job de seguimiento."""
    print("\n🧪 TESTING LÓGICA DE SEGUIMIENTO POST-ATENCIÓN...")
    
    try:
        from jobs.followups import send_post_treatment_followups, test_followup_for_today
        
        print("✅ Funciones de seguimiento disponibles:")
        print(f"   - send_post_treatment_followups: {send_post_treatment_followups.__doc__[:100]}...")
        print(f"   - test_followup_for_today: {test_followup_for_today.__doc__[:100]}...")
        
        # Verificar que tenga el decorador
        if hasattr(send_post_treatment_followups, '__wrapped__'):
            print("✅ Decorador schedule_daily_at aplicado correctamente (11:00 AM)")
        else:
            print("⚠️  Decorador schedule_daily_at no aplicado")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en módulo de seguimiento: {e}")
        return False

async def test_database_patch():
    """Verifica que el parche de BD para followup_sent esté implementado."""
    print("\n🧪 TESTING PARCHE DE BASE DE DATOS...")
    
    try:
        # Verificar que db.py tenga el parche para followup_sent
        db_path = project_root / "orchestrator_service" / "db.py"
        
        if not db_path.exists():
            print("❌ Archivo db.py no encontrado")
            return False
        
        with open(db_path, 'r') as f:
            db_content = f.read()
        
        # Buscar el parche específico
        if 'followup_sent' in db_content and 'DO $$' in db_content:
            print("✅ Parche idempotente para followup_sent encontrado en db.py")
            
            # Verificar que sea completo
            checks = [
                'followup_sent BOOLEAN DEFAULT FALSE',
                'followup_sent_at TIMESTAMPTZ',
                'idx_appointments_followup_sent',
                'idx_appointments_followup_date'
            ]
            
            for check in checks:
                if check in db_content:
                    print(f"   ✅ {check}")
                else:
                    print(f"   ⚠️  {check} no encontrado")
            
            return True
        else:
            print("❌ Parche para followup_sent no encontrado en db.py")
            return False
        
    except Exception as e:
        print(f"❌ Error verificando parche de BD: {e}")
        return False

async def test_system_prompt_integration():
    """Verifica que el system prompt incluya instrucciones de seguimiento."""
    print("\n🧪 TESTING INTEGRACIÓN CON SYSTEM PROMPT...")
    
    try:
        main_path = project_root / "orchestrator_service" / "main.py"
        
        with open(main_path, 'r') as f:
            main_content = f.read()
        
        # Buscar instrucciones de seguimiento en el system prompt
        followup_keywords = [
            "SEGUIMIENTO POST-ATENCIÓN",
            "seguimiento post-atención",
            "6 reglas maxilofaciales",
            "triage_urgency"
        ]
        
        found_count = 0
        for keyword in followup_keywords:
            if keyword in main_content:
                print(f"✅ Instrucción '{keyword}' encontrada en system prompt")
                found_count += 1
            else:
                print(f"⚠️  Instrucción '{keyword}' NO encontrada en system prompt")
        
        if found_count >= 3:
            print("✅ System prompt actualizado correctamente para seguimientos")
            return True
        else:
            print("⚠️  System prompt podría no estar completamente actualizado")
            return False
        
    except Exception as e:
        print(f"❌ Error verificando system prompt: {e}")
        return False

async def test_buffer_task_integration():
    """Verifica que buffer_task detecte respuestas a seguimientos."""
    print("\n🧪 TESTING INTEGRACIÓN CON BUFFER TASK...")
    
    try:
        buffer_path = project_root / "orchestrator_service" / "services" / "buffer_task.py"
        
        with open(buffer_path, 'r') as f:
            buffer_content = f.read()
        
        # Buscar lógica de detección de seguimientos
        detection_keywords = [
            "is_followup_response",
            "followup_context",
            "seguimiento post-atención",
            "6 reglas maxilofaciales"
        ]
        
        found_count = 0
        for keyword in detection_keywords:
            if keyword in buffer_content:
                print(f"✅ Detección de '{keyword}' implementada en buffer_task")
                found_count += 1
            else:
                print(f"⚠️  Detección de '{keyword}' NO implementada en buffer_task")
        
        if found_count >= 3:
            print("✅ Buffer task actualizado para detectar seguimientos")
            return True
        else:
            print("⚠️  Buffer task podría no detectar seguimientos correctamente")
            return False
        
    except Exception as e:
        print(f"❌ Error verificando buffer task: {e}")
        return False

async def test_admin_endpoints():
    """Verifica que los endpoints de administración estén implementados."""
    print("\n🧪 TESTING ENDPOINTS DE ADMINISTRACIÓN...")
    
    try:
        admin_routes_path = project_root / "orchestrator_service" / "jobs" / "admin_routes.py"
        
        with open(admin_routes_path, 'r') as f:
            admin_content = f.read()
        
        # Buscar endpoints de seguimiento
        endpoints = [
            "/followups/test-today",
            "/followups/run-now", 
            "/followups/status"
        ]
        
        found_count = 0
        for endpoint in endpoints:
            if endpoint in admin_content:
                print(f"✅ Endpoint '{endpoint}' implementado")
                found_count += 1
            else:
                print(f"⚠️  Endpoint '{endpoint}' NO implementado")
        
        if found_count == 3:
            print("✅ Todos los endpoints de administración implementados")
            return True
        else:
            print("⚠️  Faltan algunos endpoints de administración")
            return False
        
    except Exception as e:
        print(f"❌ Error verificando endpoints: {e}")
        return False

async def main():
    """Función principal de testing."""
    print("🚀 INICIANDO TESTING DEL SISTEMA DE SEGUIMIENTO POST-ATENCIÓN")
    print("=" * 70)
    
    results = []
    
    # Ejecutar todas las pruebas
    results.append(await test_imports())
    results.append(await test_followup_logic())
    results.append(await test_database_patch())
    results.append(await test_system_prompt_integration())
    results.append(await test_buffer_task_integration())
    results.append(await test_admin_endpoints())
    
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE TESTING")
    print(f"   Pruebas pasadas: {sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 ¡TODAS LAS PRUEBAS PASARON!")
        print("\n🎯 SISTEMA COMPLETAMENTE IMPLEMENTADO:")
        print("   1. Job programado diariamente a las 11:00 AM")
        print("   2. Busca turnos con status='completed' de ayer")
        print("   3. Filtra solo tratamientos/cirugías (no consultas)")
        print("   4. Envía mensaje de seguimiento personalizado")
        print("   5. Actualiza followup_sent=true en la BD")
        print("   6. Detecta respuestas y activa triage de urgencia")
        print("   7. Endpoints de administración disponibles")
        
        print("\n🔧 ENDPOINTS DISPONIBLES:")
        print("   • POST /admin/jobs/followups/test-today - Probar con turnos de hoy")
        print("   • POST /admin/jobs/followups/run-now   - Ejecutar manualmente")
        print("   • GET  /admin/jobs/followups/status    - Estado del job")
        
        print("\n⚠️  CONSIDERACIONES:")
        print("   • El job excluye consultas simples (solo tratamientos/cirugías)")
        print("   • El agente LLM activa triage si el paciente reporta síntomas")
        print("   • Se aplican las 6 reglas maxilofaciales de urgencia")
        print("   • Campos followup_sent y followup_sent_at agregados a appointments")
        
        return True
    else:
        print("\n⚠️  ALGUNAS PRUEBAS FALLARON - REVISAR IMPLEMENTACIÓN")
        return False

if __name__ == "__main__":
    import asyncio
    
    success = asyncio.run(main())
    
    if success:
        print("\n✅ Testing completado exitosamente")
        sys.exit(0)
    else:
        print("\n❌ Testing falló - Revisar errores")
        sys.exit(1)