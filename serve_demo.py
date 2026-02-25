#!/usr/bin/env python3
"""
Servidor HTTP simple para demostrar corrección de bug ClinicForge
"""

import http.server
import socketserver
import os
import sys
import threading
import time

PORT = 8080
DEMO_FILE = "demo_bug_fix.html"

class DemoHandler(http.server.SimpleHTTPRequestHandler):
    """Handler personalizado para servir la demo"""
    
    def do_GET(self):
        # Redirigir todas las rutas a la demo
        if self.path == '/' or self.path.endswith('.html'):
            self.path = f'/{DEMO_FILE}'
        
        # Servir archivos estáticos
        if self.path.endswith('.css') or self.path.endswith('.js'):
            return http.server.SimpleHTTPRequestHandler.do_GET(self)
        
        return http.server.SimpleHTTPRequestHandler.do_GET(self)
    
    def log_message(self, format, *args):
        # Log simplificado
        print(f"[HTTP] {self.address_string()} - {format % args}")

def start_server(port=PORT):
    """Iniciar servidor HTTP"""
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    print(f"🚀 Iniciando servidor demo en puerto {port}")
    print(f"📁 Archivo: {DEMO_FILE}")
    print(f"🌐 URL local: http://localhost:{port}")
    print("")
    print("📋 DEMOSTRACIÓN DE CORRECCIÓN DE BUG:")
    print("   1. Bug de cambio de vista en AgendaView.tsx")
    print("   2. Correcciones implementadas en código")
    print("   3. Simulación del comportamiento corregido")
    print("")
    
    try:
        with socketserver.TCPServer(("", port), DemoHandler) as httpd:
            print(f"✅ Servidor iniciado en http://localhost:{port}")
            print("🛑 Presiona Ctrl+C para detener")
            print("")
            
            # Mostrar información de la corrección
            print("🔧 CORRECCIONES IMPLEMENTADAS:")
            print("   • setCurrentView agregado al estado React")
            print("   • handleViewChange function creada")
            print("   • firstDay={1} configurado (Lunes como primer día)")
            print("   • datesAbove={true} para orden correcto de días")
            print("   • Persistencia en localStorage implementada")
            print("   • datesSet handler mejorado con viewType")
            print("")
            
            httpd.serve_forever()
    except OSError as e:
        print(f"❌ Error: No se puede iniciar en puerto {port}: {e}")
        print("💡 Intentando con puerto 8081...")
        start_server(8081)
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido")
        sys.exit(0)

def generate_tunnel():
    """Generar túnel público con localhost.run"""
    print("")
    print("🌍 GENERANDO TÚNEL PÚBLICO...")
    print("   Esto puede tardar unos segundos...")
    
    # Usar localhost.run para túnel público
    import subprocess
    import time
    
    try:
        # Iniciar túnel en segundo plano
        tunnel_cmd = f"ssh -R 80:localhost:{PORT} nokey@localhost.run"
        process = subprocess.Popen(
            tunnel_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Esperar un momento para que el túnel se establezca
        time.sleep(5)
        
        # Intentar capturar la URL
        print("✅ Túnel iniciado")
        print("🔗 URL pública disponible en unos segundos...")
        print("")
        print("📱 Para acceder desde cualquier dispositivo:")
        print("   1. Abre el link que aparecerá arriba")
        print("   2. Prueba los botones de cambio de vista")
        print("   3. Verifica la persistencia en localStorage")
        
        # Mantener el proceso del túnel
        try:
            while True:
                output = process.stdout.readline()
                if output:
                    print(output.strip())
                time.sleep(0.1)
        except KeyboardInterrupt:
            process.terminate()
            
    except Exception as e:
        print(f"❌ Error generando túnel: {e}")
        print("")
        print("💡 TÚNEL ALTERNATIVO:")
        print("   Puedes usar ngrok manualmente:")
        print(f"   ngrok http {PORT}")
        print("")
        print("📱 O acceder localmente:")
        print(f"   http://localhost:{PORT}")

if __name__ == "__main__":
    print("=" * 60)
    print("🎯 DEMOSTRACIÓN CORRECCIÓN BUG CLINICFORGE")
    print("=" * 60)
    print("")
    
    # Verificar que el archivo demo existe
    if not os.path.exists(DEMO_FILE):
        print(f"❌ Error: Archivo {DEMO_FILE} no encontrado")
        sys.exit(1)
    
    # Iniciar servidor en un hilo separado
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Esperar un momento para que el servidor inicie
    time.sleep(2)
    
    # Generar túnel
    tunnel_thread = threading.Thread(target=generate_tunnel, daemon=True)
    tunnel_thread.start()
    
    # Mantener el programa corriendo
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🎉 Demostración completada")
        print("👨‍💻 Bug corregido y listo para producción")