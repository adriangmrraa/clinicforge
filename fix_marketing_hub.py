#!/usr/bin/env python3
"""
Script para eliminar la sección "Webhook Configuration" de MarketingHubView.tsx
"""

import re

def remove_webhook_section():
    file_path = "frontend_react/src/views/MarketingHubView.tsx"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Encontrar la sección completa de Webhook Configuration
    # Buscar desde "Webhook Configuration Section" hasta el siguiente div con clase que empiece con "bg-white border"
    pattern = r'/\*+\s*Webhook Configuration Section\s*\*+/.*?(?=\s*/\*+\s*Campaign/Ad Table|$)'
    
    # Usar modo DOTALL para que . coincida con saltos de línea
    new_content = re.sub(pattern, '', content, flags=re.DOTALL)
    
    # También eliminar líneas vacías múltiples
    new_content = re.sub(r'\n\s*\n\s*\n', '\n\n', new_content)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ Sección 'Webhook Configuration' eliminada de MarketingHubView.tsx")
    
    # Verificar que también eliminamos las funciones relacionadas
    lines = new_content.split('\n')
    webhook_lines = [i for i, line in enumerate(lines) if 'webhook' in line.lower()]
    
    if webhook_lines:
        print("⚠️  Advertencia: Todavía hay referencias a 'webhook' en el archivo:")
        for line_num in webhook_lines[:5]:
            print(f"  Línea {line_num}: {lines[line_num][:80]}...")
    else:
        print("✅ No hay referencias a 'webhook' en el archivo")

if __name__ == "__main__":
    remove_webhook_section()