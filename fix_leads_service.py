"""
Fix: Las 4 funciones helper a nivel de módulo quedan entre los métodos de la clase,
haciendo que _save_lead y todo lo que sigue (incluyendo get_leads, get_leads_summary)
quede anidado dentro de _get_page_details_with_fallback en vez de ser métodos de MetaLeadsService.

Solución: Eliminar las 4 funciones helper de esa posición y agregarlas al final del archivo.
"""

fpath = r'c:\Users\Asus\Documents\estabilizacion\Laura Delgado\clinicforge\orchestrator_service\services\meta_leads_service.py'

with open(fpath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Total líneas original: {len(lines)}")

# Encontrar el inicio del bloque problemático (línea 443 en 1-indexed = índice 442)
# y el fin del bloque (antes de "    @staticmethod" que pertenece a _save_lead)
start_bad = None
end_bad = None  # línea con "    @staticmethod" que es el _save_lead mal indentado

for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped == 'async def _get_ad_details_with_fallback(client, lead_data):' and start_bad is None:
        start_bad = i
    # El @staticmethod con 4 espacios justo antes de _save_lead
    if line.rstrip() == '    @staticmethod' and start_bad is not None and end_bad is None:
        # Verificar que la siguiente línea no vacía sea _save_lead
        next_meaningful = i + 1
        while next_meaningful < len(lines) and lines[next_meaningful].strip() == '':
            next_meaningful += 1
        if next_meaningful < len(lines) and '_save_lead' in lines[next_meaningful]:
            end_bad = i
            break

print(f"Bloque helper: líneas {start_bad+1} a {end_bad} (1-indexed)")

if start_bad is None or end_bad is None:
    print("ERROR: No se encontró el patrón. Abortando.")
    exit(1)

# Guardar el bloque de helpers (con indent correcto = 0 espacios ya los tienen)
helper_block = lines[start_bad:end_bad]

# La línea justo antes de start_bad (línea vacía después de _enrich_with_meta_data)
# La dejamos como está.

# Construir nuevo contenido:
# - líneas 0..start_bad (sin las helpers)
# - las líneas desde end_bad hasta el final (que incluye @staticmethod _save_lead en adelante)
new_lines = lines[:start_bad] + lines[end_bad:]

# Agregar las helpers al final del archivo
new_lines.append('\n')
new_lines.append('\n')
for hl in helper_block:
    new_lines.append(hl)

print(f"Total líneas nuevo: {len(new_lines)}")

with open(fpath, 'w', encoding='utf-8', newline='') as f:
    f.writelines(new_lines)

print("OK: Archivo corregido. Verifica con python -c \"import ast; ast.parse(open(r'" + fpath + "').read()); print('Sintaxis OK')\"")
