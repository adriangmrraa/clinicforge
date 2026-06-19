# -*- coding: utf-8 -*-
import re

with open('orchestrator_service/services/nova_tools.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update NOVA_TOOLS definitions
registry_pattern = r'''\s*"historial_clinico":\s*{[^}]+},\s*"registrar_nota_clinica":\s*{[^}]+},'''
registry_replacement = r'''
    "ver_historia_clinica": {
        "description": "Muestra el historial clínico del paciente (consultas, evoluciones, cirugías, diagnósticos) y el estado actualizado del odontograma. Úsalo SIEMPRE ANTES de crear una nota, cuando el paciente pregunte por su historia, o cuando necesites ver la evolución del paciente.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente."}
            },
            "required": ["patient_id"]
        }
    },
    "crear_nota_clinica": {
        "description": "Crea un registro de evolución clínica (consulta, control, urgencia o cirugía) luego de atender a un paciente. Úsalo cuando el profesional indique que terminó de atender, indique el motivo, qué le hizo y el diagnóstico.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente."},
                "record_type": {"type": "string", "enum": ["Consulta General", "Control", "Urgencia", "Cirugia"], "description": "El tipo de atención o registro."},
                "chief_complaint": {"type": "string", "description": "Motivo de la consulta del paciente."},
                "notes": {"type": "string", "description": "Descripción detallada del procedimiento realizado, notas clínicas."},
                "treatment_plan": {"type": "string", "description": "Plan a seguir para las próximas sesiones o derivación."},
                "diagnosis": {"type": "string", "description": "El diagnóstico."}
            },
            "required": ["patient_id", "record_type", "chief_complaint"]
        }
    },
    "resumen_evolucion": {
        "description": "Genera un resumen natural de la evolución clínica del paciente. Úsalo cuando el staff pida un 'resumen', 'cómo viene este paciente' o quiera entender el progreso general.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente."}
            },
            "required": ["patient_id"]
        }
    },'''
# Wait, actually let's use a robust string replacement for tool registry:
old_registry = '''    "historial_clinico": {
        "description": "Muestra el historial clínico del paciente (consultas anteriores, diagnósticos, etc).",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente."}
            },
            "required": ["patient_id"],
        },
    },
    "registrar_nota_clinica": {
        "description": "Crea una nota clínica o evolución para el paciente actual, y OPCIONALMENTE actualiza UNA pieza en el odontograma. Sólo para profesionales.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "integer", "description": "ID del paciente."},
                "diagnosis": {
                    "type": "string",
                    "description": "El diagnóstico o título principal.",
                },
                "treatment_notes": {
                    "type": "string",
                    "description": "Notas sobre el tratamiento realizado.",
                },
                "tooth_number": {
                    "type": "integer",
                    "description": "(Opcional) Número de pieza dental FDI (ej. 11, 48).",
                },
                "tooth_status": {
                    "type": "string",
                    "description": "(Opcional) Estado de la pieza (ej. caries, resina).",
                },
                "surface": {
                    "type": "string",
                    "description": "(Opcional) Superficie afectada (ej. mesial, oclusal).",
                },
            },
            "required": ["patient_id", "diagnosis"],
        },
    },'''
if old_registry in content:
    content = content.replace(old_registry, registry_replacement.strip('\n'))
else:
    print("Warning: could not find old_registry")

# 2. Update tool dispatch mapping
old_dispatch = '''        "historial_clinico": _historial_clinico,
        "registrar_nota_clinica": _registrar_nota_clinica,'''
new_dispatch = '''        "ver_historia_clinica": _ver_historia_clinica,
        "crear_nota_clinica": _crear_nota_clinica,
        "resumen_evolucion": _resumen_evolucion,'''
if old_dispatch in content:
    content = content.replace(old_dispatch, new_dispatch)
else:
    print("Warning: could not find old_dispatch")

# 3. Update _modificar_odontograma
old_mod_odonto_start = '''    try:
        from services.odontogram_svg import render_odontogram_svg
        import uuid'''
new_mod_odonto_start = '''    try:
        from services.odontogram_svg import render_odontogram_svg
        import uuid
        import json
        from datetime import datetime'''
if old_mod_odonto_start in content:
    content = content.replace(old_mod_odonto_start, new_mod_odonto_start)
    
old_mod_odonto_body = '''            # Create new row via INSERT instead of UPDATE (temporal record keeping)
            new_record_id = uuid.uuid4()
            await db.pool.execute(
                """
                INSERT INTO clinical_records 
                (id, tenant_id, patient_id, professional_id, record_date, odontogram_data)
                VALUES (, , , , CURRENT_DATE, ::jsonb)
                """,
                new_record_id,
                tenant_id,
                patient_id,
                None, # Could pass professional_id if needed in the future
                odontogram_data,
            )'''
new_mod_odonto_body = '''            # Create new row via INSERT instead of UPDATE (temporal record keeping)
            new_record_id = uuid.uuid4()
            
            cnotes = {
                "record_type": "Odontograma",
                "chief_complaint": "Actualización de odontograma",
                "notes": "Se han detectado o registrado los siguientes cambios anatómicos: " + diff_text
            }
            
            await db.pool.execute(
                """
                INSERT INTO clinical_records 
                (id, tenant_id, patient_id, professional_id, record_date, diagnosis, clinical_notes, odontogram_data)
                VALUES (, , , , CURRENT_DATE, , ::jsonb, ::jsonb)
                """,
                new_record_id,
                tenant_id,
                patient_id,
                None, # Could pass professional_id if needed in the future
                "Odontograma actualizado",
                json.dumps(cnotes),
                odontogram_data,
            )
            
            # Emit PATIENT_UPDATED so UI updates clinical records list as well
            await _nova_emit(
                "PATIENT_UPDATED",
                {"patient_id": patient_id, "tenant_id": tenant_id},
            )'''

old_mod_odonto_diff = '''        # Record differences if any existing data
        diff_text = ""
        if existing_odata:
            changes = []
            import json'''
new_mod_odonto_diff = '''        # Record differences if any existing data
        diff_text = ""
        if True:
            changes = []
            import json'''

if old_mod_odonto_body in content and old_mod_odonto_diff in content:
    content = content.replace(old_mod_odonto_diff, new_mod_odonto_diff)
    content = content.replace(old_mod_odonto_body, new_mod_odonto_body)
else:
    print("Warning: could not find old_mod_odonto parts")

# 4. Replace implementations
old_impl_start = "async def _historial_clinico(args: Dict, tenant_id: int, user_role: str) -> str:"
old_impl_end = "return f\"Nota clinica registrada para paciente {pid}.{tooth_msg}\""

new_impl = '''async def _ver_historia_clinica(args: Dict, tenant_id: int, user_role: str) -> str:
    if user_role not in ("ceo", "professional"):
        return _role_error("ver_historia_clinica", ["ceo", "professional"])

    pid = args.get("patient_id")
    if not pid:
        return "Necesito el ID del paciente."

    from db import db
    import json
    rows = await db.pool.fetch(
        """
        SELECT cr.id, cr.record_date, cr.diagnosis, cr.clinical_notes,
               cr.odontogram_data, cr.treatments, cr.recommendations,
               p.first_name || ' ' || p.last_name AS professional_name
        FROM clinical_records cr
        LEFT JOIN professionals p ON p.id = cr.professional_id
        WHERE cr.patient_id =  AND cr.tenant_id = 
        ORDER BY cr.record_date DESC
        LIMIT 10
        """,
        int(pid),
        tenant_id,
    )

    if not rows:
        return "Este paciente no tiene registros clinicos."

    lines = [f"Historial clinico ({len(rows)} registros mas recientes):"]
    for r in rows:
        dt = r["record_date"].strftime("%d/%m/%Y") if r["record_date"] else "Sin fecha"
        prof = r["professional_name"] or "sin profesional"
        diag = r["diagnosis"] or ""
        
        # Parse modern clinical_notes JSON
        cnotes_text = ""
        cnotes = r["clinical_notes"]
        if isinstance(cnotes, str):
            try:
                cnotes = json.loads(cnotes)
            except:
                pass
                
        if isinstance(cnotes, dict):
            parts = []
            if cnotes.get("record_type"):
                parts.append(f"Tipo: {cnotes['record_type']}")
            if cnotes.get("chief_complaint"):
                parts.append(f"Motivo: {cnotes['chief_complaint']}")
            if cnotes.get("notes"):
                parts.append(f"Notas: {cnotes['notes']}")
            cnotes_text = " | ".join(parts)
        elif cnotes and isinstance(cnotes, str):
            cnotes_text = cnotes

        lines.append(f" {dt}  Dr. {prof}")
        if diag:
            lines.append(f"  Diagnostico/Evolucion: {diag}")
        if cnotes_text:
            lines.append(f"  Detalles: {cnotes_text}")

        # Odontogram summary
        odata = r["odontogram_data"]
        if isinstance(odata, str):
            try:
                odata = json.loads(odata)
            except:
                pass
                
        if odata and isinstance(odata, dict) and len(odata) > 0:
            lines.append(f"  [Odontograma actualizado en este registro]")
    return "\\n".join(lines)


async def _crear_nota_clinica(args: Dict, tenant_id: int, user_role: str, user_id: str) -> str:
    if user_role != "professional":
        return _role_error("crear_nota_clinica", ["professional"])

    pid = args.get("patient_id")
    rtype = args.get("record_type")
    
    if not pid or not rtype:
        return "Necesito patient_id y record_type."

    from db import db
    # Verify patient exists
    exists = await db.pool.fetchval(
        "SELECT id FROM patients WHERE id =  AND tenant_id = ",
        int(pid),
        tenant_id,
    )
    if not exists:
        return "No encontre a ese paciente."

    # resolve professional id
    prof_id = None
    if user_id:
        p_row = await db.pool.fetchrow("SELECT id FROM professionals WHERE user_id =  AND tenant_id = ", user_id, tenant_id)
        if p_row:
            prof_id = p_row["id"]

    # Build JSONs
    cnotes = {
        "record_type": rtype,
        "chief_complaint": args.get("chief_complaint", ""),
        "notes": args.get("notes", "")
    }
    tplan = {"plan": args.get("treatment_plan", "")} if args.get("treatment_plan") else None
    diagnosis = args.get("diagnosis", "")

    import uuid
    import json
    from datetime import datetime
    record_id = uuid.uuid4()
    
    await db.pool.execute(
        """
        INSERT INTO clinical_records
            (id, tenant_id, patient_id, professional_id, record_date,
             diagnosis, clinical_notes, treatment_plan)
        VALUES (, , , , , , ::jsonb, ::jsonb)
        """,
        record_id, tenant_id, int(pid), prof_id, datetime.now().date(),
        diagnosis, json.dumps(cnotes), json.dumps(tplan) if tplan else None
    )

    await _nova_emit("PATIENT_UPDATED", {"patient_id": int(pid), "tenant_id": tenant_id})
    return f"Nota clinica ({rtype}) registrada exitosamente para el paciente {pid}."


async def _resumen_evolucion(args: Dict, tenant_id: int, user_role: str) -> str:
    # Just return ver_historia_clinica so Nova can summarize it
    history = await _ver_historia_clinica(args, tenant_id, user_role)
    return "Resume el siguiente historial clínico en un párrafo coherente en lenguaje natural para el usuario:\\n" + history'''

start_idx = content.find(old_impl_start)
end_idx = content.find(old_impl_end)
if start_idx != -1 and end_idx != -1:
    content = content[:start_idx] + new_impl + content[end_idx + len(old_impl_end):]
else:
    print("Warning: could not find old_impl block")

with open('orchestrator_service/services/nova_tools.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done patching.")
