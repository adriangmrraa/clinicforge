"""078: Escudo Anti-Ausencias — flujo completo con confirmación blindada.

Reconfigura el playbook 'Escudo Anti-Ausencias' (trigger appointment_reminder) de cada
tenant para encadenar recordatorio → 2º aviso → liberar/avisar, con la CONFIRMACIÓN
BLINDADA (capa IA + cambio de estado real del turno). Antes: el recordatorio confirmaba
por palabras clave y NO cambiaba el estado del turno (el bot decía "gracias" y el turno
seguía en amarillo). Ahora:

  Paso 0   recordatorio 1º (plantilla del tenant)           → sigue al 1
  Paso 1   esperar 2h  [capa IA on]
             · confirma (botón/palabra/IA) → salta a 10 (marca CONFIRMADO)
             · cancela                     → aborta (lo maneja la IA / se libera)
             · reprograma                  → pasa a la IA
             · no responde                 → salta a 2 (2º aviso)
  Paso 2   2º aviso (plantilla 'Segundo Aviso')             → sigue al 3
  Paso 3   esperar 2h  [capa IA on]
             · confirma → salta a 10 (CONFIRMADO)
             · no responde → salta a 20 (avisar a la Dra)
  Paso 10  update_status appointment_status = confirmed     → completa (no hay 11)
  Paso 20  notify_team (MODO SEGURO: avisa, NO libera solo) → completa (no hay 21)

MODO SEGURO por defecto: el paso 20 avisa a la Dra para que libere el lugar a mano.
Para pasar a LIBERACIÓN AUTOMÁTICA más adelante, reemplazar el paso 20 por:
  20 = send_text  (3º mensaje al paciente: "liberamos tu turno, escribinos para reubicarte")
  21 = update_status appointment_status = cancelled
(así el turno se libera solo, pero el paciente puede recuperarlo escribiendo).

Idempotente: lee las plantillas ya configuradas por tenant y las reusa.
"""
import json

import sqlalchemy as sa
from alembic import op

revision = "078"
down_revision = "077"
branch_labels = None
depends_on = None


# Reglas de respuesta. ORDEN IMPORTA: el clasificador matchea por substring, así que
# las NEGACIONES van primero ("no voy" → cancelar antes de que "voy" caiga en confirmado).
# Y las keywords son solo las INEQUÍVOCAS (evitamos "si"/"voy"/"ok" sueltas: matchearían
# dentro de otras palabras — "nece-si-to", "con-voy"). El resto ("sí", "dale", "obvio que
# voy", "perfecto"...) lo resuelve la CAPA IA (on_unclassified='classify_with_ai'), que
# entiende la intención sin falsos positivos.
_RULES = json.dumps([
    {
        "name": "cancelar",
        # Negaciones AMPLIAS: el matching es por substring y "confirmado" tiene
        # "asistiré"/"cuenten conmigo" — sin estas variantes, "no asistiré" caería en
        # confirmado. Cubrimos las formas negadas de las keywords de confirmación.
        "keywords": [
            "no puedo", "no voy", "no asisto", "no asistire", "no asistiré",
            "no asistira", "no asistiran", "no llego", "no ire", "no iré",
            "no podre", "no podré", "no confirmo", "no cuenten", "no me sirve",
            "no voy a ir", "no voy a asistir", "no cuento", "no lo confirmo",
            "cancelar", "cancelo", "cancela el turno", "no asistiremos",
        ],
        "action": "abort",
    },
    {
        "name": "reprogramar",
        "keywords": [
            "reprogramar", "reagendar", "otro dia", "otro día", "otro horario",
            "mover el turno", "cambiar el turno", "cambiar el horario", "cambiar la fecha",
        ],
        "action": "pass_to_ai",
    },
    {
        "name": "confirmado",
        "keywords": [
            "confirmo", "confirmar", "confirmado", "asisto", "asistire", "asistiré",
            "cuenten conmigo", "ahi estare", "ahí estaré", "ahi estoy", "ahí estoy",
            "ahi voy", "ahí voy", "dale", "de una",
        ],
        "action": "continue",
    },
])


def _jsonb(v, default="{}"):
    """Normaliza un valor a string JSON para insertar en columna JSONB."""
    if v is None:
        return default
    if isinstance(v, str):
        return v or default
    return json.dumps(v)


def _insert_step(conn, pid, **kw):
    cols = ["playbook_id"] + list(kw.keys())
    vals = [":playbook_id"] + [f":{k}" for k in kw.keys()]
    # Castear los JSONB con CAST(:x AS jsonb). OJO: el sufijo ":x::jsonb" ROMPE el
    # parser de binds de SQLAlchemy 2.0 — deja de reconocer el parámetro y manda ":x"
    # literal a Postgres → "syntax error at or near ':'" → aborta alembic upgrade head
    # → el orchestrator NO arranca. CAST(:x AS jsonb) sí conserva el bind.
    for i, c in enumerate(cols):
        if c in ("template_vars", "response_rules"):
            vals[i] = f"CAST({vals[i]} AS jsonb)"
    sql = f"INSERT INTO automation_steps ({', '.join(cols)}) VALUES ({', '.join(vals)})"
    params = {"playbook_id": pid, **kw}
    conn.execute(sa.text(sql), params)


def upgrade():
    conn = op.get_bind()

    shields = conn.execute(sa.text("""
        SELECT id, tenant_id FROM automation_playbooks
        WHERE trigger_type = 'appointment_reminder'
          AND (name ILIKE '%anti-ausencia%' OR icon = '🛡️')
    """)).fetchall()

    for pb_id, tenant_id in shields:
        # Plantilla del 1º recordatorio (step 0 actual del 🛡️)
        s0 = conn.execute(sa.text("""
            SELECT action_type, template_name, template_lang, template_vars, message_text
            FROM automation_steps WHERE playbook_id = :pid AND step_order = 0
            ORDER BY id LIMIT 1
        """), {"pid": pb_id}).fetchone()
        # Plantilla del 2º aviso (playbook 'Segundo Aviso' del mismo tenant)
        s2 = conn.execute(sa.text("""
            SELECT s.action_type, s.template_name, s.template_lang, s.template_vars, s.message_text
            FROM automation_playbooks p
            JOIN automation_steps s ON s.playbook_id = p.id AND s.step_order = 0
            WHERE p.tenant_id = :tid AND p.trigger_type = 'appointment_reminder'
              AND (p.name ILIKE '%segundo aviso%' OR p.icon = '⏰')
            ORDER BY p.id LIMIT 1
        """), {"tid": tenant_id}).fetchone()

        r_action = (s0[0] if s0 else None) or "send_text"
        r_tname = s0[1] if s0 else None
        r_tlang = (s0[2] if s0 else None) or "es"
        r_tvars = _jsonb(s0[3] if s0 else None)
        r_msg = (s0[4] if s0 else None) or (
            "Hola {{nombre_paciente}}, te recordamos tu turno de mañana a las "
            "{{hora_turno}}. ¿Nos confirmás tu asistencia?"
        )

        a_action = (s2[0] if s2 else None) or "send_text"
        a_tname = s2[1] if s2 else None
        a_tlang = (s2[2] if s2 else None) or "es"
        a_tvars = _jsonb(s2[3] if s2 else None)
        a_msg = (s2[4] if s2 else None) or (
            "Hola {{nombre_paciente}}, necesitamos que confirmes tu turno de mañana a las "
            "{{hora_turno}}. Si no lo confirmás, liberamos el lugar. ¿Venís?"
        )

        # Reset de los pasos del 🛡️
        conn.execute(sa.text("DELETE FROM automation_steps WHERE playbook_id = :pid"), {"pid": pb_id})

        # Paso 0 — recordatorio 1º
        _insert_step(
            conn, pb_id, step_order=0, step_label="Recordatorio 24h",
            action_type=r_action, delay_minutes=0,
            template_name=r_tname, template_lang=r_tlang, template_vars=r_tvars,
            message_text=None if r_action == "send_template" else r_msg,
        )
        # Paso 1 — esperar confirmación (capa IA on)
        _insert_step(
            conn, pb_id, step_order=1, step_label="Esperar confirmación",
            action_type="wait_response", delay_minutes=0,
            wait_timeout_minutes=120, on_no_response="continue",
            on_no_response_next_step=2, on_response_next_step=10,
            on_unclassified="classify_with_ai", response_rules=_RULES,
        )
        # Paso 2 — 2º aviso
        _insert_step(
            conn, pb_id, step_order=2, step_label="Segundo aviso",
            action_type=a_action, delay_minutes=0,
            template_name=a_tname, template_lang=a_tlang, template_vars=a_tvars,
            message_text=None if a_action == "send_template" else a_msg,
        )
        # Paso 3 — esperar confirmación otra vez (capa IA on)
        _insert_step(
            conn, pb_id, step_order=3, step_label="Esperar confirmación 2",
            action_type="wait_response", delay_minutes=0,
            wait_timeout_minutes=120, on_no_response="continue",
            on_no_response_next_step=20, on_response_next_step=10,
            on_unclassified="classify_with_ai", response_rules=_RULES,
        )
        # Paso 10 — CONFIRMADO (cambia el estado real del turno). Sin paso 11 → completa.
        _insert_step(
            conn, pb_id, step_order=10, step_label="Marcar confirmado",
            action_type="update_status", delay_minutes=0,
            update_field="appointment_status", update_value="confirmed",
        )
        # Paso 20 — MODO SEGURO: avisar a la Dra (no libera solo). Sin paso 21 → completa.
        _insert_step(
            conn, pb_id, step_order=20, step_label="Avisar sin confirmar (modo seguro)",
            action_type="notify_team", delay_minutes=0,
            notify_channel="both",
            notify_message=(
                "⚠️ {{nombre_paciente}} no confirmó su turno de mañana tras 2 avisos. "
                "Revisá si conviene liberar el lugar para dárselo a otro."
            ),
        )

        # El 'Segundo Aviso' ya no corre por separado: su lógica vive dentro del 🛡️.
        conn.execute(sa.text("""
            UPDATE automation_playbooks SET is_active = false
            WHERE tenant_id = :tid AND trigger_type = 'appointment_reminder'
              AND (name ILIKE '%segundo aviso%' OR icon = '⏰')
        """), {"tid": tenant_id})


def downgrade():
    # No se restauran los pasos anteriores automáticamente (los reconstruye el seed 048
    # si se re-corre). Dejar la bajada como no-op evita romper datos en producción.
    pass
