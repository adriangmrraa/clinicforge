#!/usr/bin/env python3
"""
Script para integrar el dashboard completo en main.py
"""

import re
import os

def read_file(filename):
    """Lee el contenido de un archivo"""
    with open(filename, 'r') as f:
        return f.read()

def write_file(filename, content):
    """Escribe contenido en un archivo"""
    with open(filename, 'w') as f:
        f.write(content)

def integrate_dashboard():
    """Integra el dashboard en main.py"""
    
    # Leer main.py actual
    main_content = read_file("main.py")
    
    # 1. Agregar imports del dashboard
    imports_to_add = '''
# Dashboard CEO
from dashboard import init_dashboard
'''
    
    # Buscar lugar para agregar imports (después de otros imports)
    import_pattern = r'(from core import db)'
    match = re.search(import_pattern, main_content)
    
    if match:
        insert_pos = match.end()
        main_content = main_content[:insert_pos] + imports_to_add + main_content[insert_pos:]
        print("✅ Imports del dashboard agregados")
    
    # 2. Agregar inicialización del dashboard después de la inicialización de la app
    init_pattern = r'app = FastAPI\([^)]+\)'
    match = re.search(init_pattern, main_content)
    
    if match:
        # Buscar después de la configuración de CORS
        cors_pattern = r'app\.add_middleware\(CORSMiddleware[^)]+\)'
        cors_match = re.search(cors_pattern, main_content[match.end():])
        
        if cors_match:
            insert_pos = match.end() + cors_match.end()
            dashboard_init = '''

# --- INICIALIZACIÓN DASHBOARD CEO ---
# Configurar clave de acceso CEO (debería estar en .env)
CEO_ACCESS_KEY = os.getenv("CEO_ACCESS_KEY", "dralauradelgado2026")

# Inicializar dashboard
dashboard_initialized = init_dashboard(app, db.pool)
if dashboard_initialized:
    logger.info("🚀 Dashboard CEO inicializado: https://app.dralauradelgado.com/dashboard/status?key=" + CEO_ACCESS_KEY)
else:
    logger.warning("⚠️ Dashboard CEO no pudo inicializarse")
'''
            main_content = main_content[:insert_pos] + dashboard_init + main_content[insert_pos:]
            print("✅ Inicialización del dashboard agregada")
    
    # 3. Agregar tracking de tokens en el endpoint /chat
    # Buscar el endpoint /chat
    chat_pattern = r'@app\.post\("/chat"[^}]+}'
    chat_match = re.search(chat_pattern, main_content, re.DOTALL)
    
    if chat_match:
        chat_endpoint = chat_match.group(0)
        
        # Buscar donde guardar la respuesta del asistente
        save_response_pattern = r'await db\.append_chat_message\([^)]+\)'
        save_match = re.search(save_response_pattern, chat_endpoint)
        
        if save_match:
            # Agregar tracking de tokens después de guardar la respuesta
            insert_pos_in_chat = save_match.end()
            
            token_tracking_code = '''
        
        # 12. Trackear uso de tokens (si está disponible)
        try:
            from dashboard import get_token_tracker
            from dashboard.token_tracker import TokenUsage
            from datetime import datetime, timezone
            
            # Estimar tokens (aproximación basada en longitud)
            # En producción, esto debería venir de la respuesta de OpenAI
            input_tokens = len(req.final_message) // 4
            output_tokens = len(output) // 4
            total_tokens = input_tokens + output_tokens
            
            # Obtener modelo actual
            from dashboard import get_config_manager
            config_mgr = get_config_manager()
            current_model = await config_mgr.get_config("OPENAI_MODEL", tenant_id) or "gpt-4o-mini"
            
            # Calcular costo
            tracker = get_token_tracker()
            cost_usd = tracker.calculate_cost(current_model, input_tokens, output_tokens)
            
            # Crear registro de uso
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
            
            # Guardar en base de datos (async)
            import asyncio
            asyncio.create_task(tracker.track_usage(usage))
            
        except Exception as token_err:
            logger.warning(f"⚠️ Error trackeando tokens: {token_err}")
'''
            
            # Insertar en el endpoint /chat
            new_chat_endpoint = chat_endpoint[:insert_pos_in_chat] + token_tracking_code + chat_endpoint[insert_pos_in_chat:]
            main_content = main_content.replace(chat_endpoint, new_chat_endpoint)
            print("✅ Tracking de tokens agregado al endpoint /chat")
    
    # 4. Agregar variable de entorno CEO_ACCESS_KEY al .env si existe
    env_file = ".env"
    if os.path.exists(env_file):
        env_content = read_file(env_file)
        if "CEO_ACCESS_KEY" not in env_content:
            env_content += "\n# Dashboard CEO\nCEO_ACCESS_KEY=dralauradelgado2026\n"
            write_file(env_file, env_content)
            print("✅ Variable CEO_ACCESS_KEY agregada a .env")
    
    # 5. Guardar main.py actualizado
    write_file("main.py", main_content)
    print("✅ main.py actualizado con dashboard completo")
    
    return True

def create_static_files():
    """Crea archivos estáticos necesarios"""
    static_dir = "dashboard/static"
    os.makedirs(static_dir, exist_ok=True)
    
    # Copiar dashboard.js si no existe
    js_file = os.path.join(static_dir, "dashboard.js")
    if not os.path.exists(js_file):
        from dashboard.static import dashboard
        import shutil
        shutil.copy("dashboard/static/dashboard.js", js_file)
        print("✅ Archivo dashboard.js copiado")
    
    return True

def main():
    """Función principal"""
    print("=" * 60)
    print("INTEGRACIÓN DASHBOARD CEO COMPLETO")
    print("=" * 60)
    
    try:
        # Verificar que los módulos del dashboard existen
        import dashboard
        print("✅ Módulos del dashboard cargados correctamente")
        
        # Integrar dashboard en main.py
        if integrate_dashboard():
            print("\n✅ Dashboard integrado exitosamente")
            
            # Crear archivos estáticos
            create_static_files()
            
            # Verificar que main.py sea válido
            import subprocess
            result = subprocess.run(["python3", "-m", "py_compile", "main.py"], 
                                  capture_output=True, text=True)
            
            if result.returncode == 0:
                print("✅ main.py compila correctamente")
                
                print("\n" + "=" * 60)
                print("🎉 DASHBOARD CEO COMPLETO IMPLEMENTADO")
                print("=" * 60)
                print("\n📊 URL del Dashboard:")
                print("   https://app.dralauradelgado.com/dashboard/status?key=CEO_ACCESS_KEY")
                print("\n🔑 Clave de acceso por defecto: dralauradelgado2026")
                print("   (Cambiar en variable de entorno CEO_ACCESS_KEY)")
                print("\n🚀 Sistema listo para deploy")
                
                return True
            else:
                print(f"❌ Error compilando main.py: {result.stderr}")
                return False
                
    except ImportError as e:
        print(f"❌ Error importando dashboard: {e}")
        print("Asegúrate de que los módulos del dashboard estén en el directorio correcto")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)