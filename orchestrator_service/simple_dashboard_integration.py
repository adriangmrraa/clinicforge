#!/usr/bin/env python3
"""
Integración simple del dashboard - Sin dependencias externas
"""

import os
import re

def read_file(filename):
    with open(filename, 'r') as f:
        return f.read()

def write_file(filename, content):
    with open(filename, 'w') as f:
        f.write(content)

def integrate_dashboard_simple():
    """Integración simple del dashboard"""
    
    main_content = read_file("main.py")
    
    # 1. Agregar imports
    imports_to_add = '''
# Dashboard CEO
import os
'''
    
    # Insertar después de otros imports
    if "from core import db" in main_content:
        main_content = main_content.replace(
            "from core import db",
            "from core import db" + imports_to_add
        )
        print("✅ Imports agregados")
    
    # 2. Agregar inicialización después de la app
    app_init = '''
# --- DASHBOARD CEO ---
# Clave de acceso (configurar en .env)
CEO_ACCESS_KEY = os.getenv("CEO_ACCESS_KEY", "dralauradelgado2026")

# Inicialización diferida del dashboard
dashboard_initialized = False
try:
    from dashboard import init_dashboard
    dashboard_initialized = init_dashboard(app, db.pool)
    if dashboard_initialized:
        logger.info("🚀 Dashboard CEO inicializado")
except ImportError as e:
    logger.warning(f"⚠️ Dashboard no disponible: {e}")
'''
    
    # Buscar después de CORS middleware
    if "app.add_middleware(CORSMiddleware" in main_content:
        pos = main_content.find("app.add_middleware(CORSMiddleware")
        end_pos = main_content.find(")", pos) + 1
        
        # Encontrar el final de la línea
        while main_content[end_pos] != '\n':
            end_pos += 1
        
        main_content = main_content[:end_pos+1] + app_init + main_content[end_pos+1:]
        print("✅ Inicialización del dashboard agregada")
    
    # 3. Agregar tracking de tokens en /chat
    chat_section = '''
        # 12. Trackear uso de tokens
        try:
            # Importar diferido para evitar errores de inicialización
            from dashboard.token_tracker import TokenUsage
            from dashboard import get_token_tracker, get_config_manager
            from datetime import datetime, timezone
            
            # Estimar tokens
            input_tokens = len(req.final_message) // 4
            output_tokens = len(output) // 4
            total_tokens = input_tokens + output_tokens
            
            # Obtener modelo y calcular costo
            config_mgr = get_config_manager()
            current_model = await config_mgr.get_config("OPENAI_MODEL", tenant_id) or "gpt-4o-mini"
            
            tracker = get_token_tracker()
            cost_usd = tracker.calculate_cost(current_model, input_tokens, output_tokens)
            
            # Crear registro
            usage = TokenUsage(
                conversation_id=conversation_id,
                patient_phone=req.final_phone,
                model=current_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                timestamp=datetime.now(timezone.utc),
                tenant_id=tenant_id
            )
            
            # Guardar async
            import asyncio
            asyncio.create_task(tracker.track_usage(usage))
            
        except Exception as token_err:
            logger.debug(f"Token tracking skipped: {token_err}")
'''
    
    # Buscar donde agregar después de guardar la respuesta
    save_pattern = "await db.append_chat_message"
    if save_pattern in main_content:
        # Encontrar todas las ocurrencias
        lines = main_content.split('\n')
        for i, line in enumerate(lines):
            if save_pattern in line and "role='assistant'" in line:
                # Insertar después de esta línea
                insert_pos = i + 1
                lines.insert(insert_pos, chat_section)
                main_content = '\n'.join(lines)
                print("✅ Tracking de tokens agregado")
                break
    
    # 4. Agregar .env si no existe
    env_file = ".env"
    if os.path.exists(env_file):
        env_content = read_file(env_file)
        if "CEO_ACCESS_KEY" not in env_content:
            env_content += "\n# Dashboard CEO\nCEO_ACCESS_KEY=dralauradelgado2026\n"
            write_file(env_file, env_content)
            print("✅ CEO_ACCESS_KEY agregada a .env")
    else:
        # Crear .env simple
        env_content = """# Dashboard CEO
CEO_ACCESS_KEY=dralauradelgado2026
"""
        write_file(env_file, env_content)
        print("✅ .env creado con CEO_ACCESS_KEY")
    
    # 5. Guardar main.py actualizado
    write_file("main.py", main_content)
    
    # 6. Verificar sintaxis
    try:
        compile(main_content, "main.py", "exec")
        print("✅ main.py tiene sintaxis válida")
        return True
    except SyntaxError as e:
        print(f"❌ Error de sintaxis: {e}")
        return False

def main():
    print("=" * 60)
    print("INTEGRACIÓN SIMPLE DASHBOARD CEO")
    print("=" * 60)
    
    if integrate_dashboard_simple():
        print("\n✅ Dashboard integrado exitosamente")
        print("\n📊 URL del Dashboard:")
        print("   https://app.dralauradelgado.com/dashboard/status")
        print("   https://app.dralauradelgado.com/dashboard/status?key=dralauradelgado2026")
        print("\n🔑 Clave de acceso: dralauradelgado2026")
        print("\n🚀 Sistema listo para commit y deploy")
        return True
    else:
        print("❌ Error en la integración")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)