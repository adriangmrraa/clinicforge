# -*- coding: utf-8 -*-
"""Test LOCAL y GRATIS de la consolidación de burbujas de los playbooks.

Optimización 2026-07-17 (pedido Carlos: "los playbooks en una burbuja"): antes
_action_send_instructions mandaba cada sección (intro + qué traer + medicación +
ayuno + preparación) como un globito aparte → 2 a 5 mensajes facturables por Meta.
Ahora se juntan en UN solo mensaje (single_bubble). Este test verifica, sin API ni
BD, que el join produce UN mensaje que conserva TODAS las secciones.

SYNC: la lógica de _join replica la de jobs/playbook_executor.py:_action_send_instructions.
Si se cambia allá, actualizar acá.

Uso:  python orchestrator_service/eval/test_playbook_burbujas.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from jobs.playbook_executor import _format_pre_instructions, _format_post_instructions


def _join(bubbles):
    """Espejo EXACTO del join de _action_send_instructions (playbook_executor.py)."""
    parts = [b.strip() for b in bubbles if b and b.strip()]
    if not parts:
        return ""
    return parts[0] + "\n\n" + "\n".join(parts[1:]) if len(parts) > 1 else parts[0]


def _globitos_reales(text):
    """Globitos que salen DE VERDAD: el envío usa single_bubble=True, así que
    ResponseSender NO parte por \\n\\n → 1 solo globito si hay texto, 0 si está vacío."""
    return 1 if text.strip() else 0


PRE_FULL = {
    "what_to_bring": ["Traé estudios previos (radiografías u otros)", "DNI"],
    "medications_to_take": ["Tomá tu medicación habitual"],
    "medications_to_avoid": ["Evitá aspirina 48hs antes"],
    "fasting_required": True,
    "fasting_hours": 6,
    "preparation_days_before": 2,
}

POST_DICT = {
    "care_duration_days": 3,
    "dietary_restrictions": ["Evitá comidas duras 3 días", "Nada de alcohol"],
    "activity_restrictions": ["No hacer ejercicio intenso 48hs"],
}

CASOS = [
    (
        "PRE completo (5 secciones) → 1 globito con todo",
        _format_pre_instructions(PRE_FULL, "Implante"),
        lambda joined: (
            _globitos_reales(joined) == 1  # UN solo globito, no 5
            and "estudios previos" in joined
            and "medicación habitual" in joined
            and "aspirina" in joined
            and "Ayuno" in joined
            and "Preparación" in joined
            and "Implante" in joined  # el encabezado con el tratamiento
        ),
    ),
    (
        "PRE solo 'qué traer' (caso María) → 1 globito, intro + item",
        _format_pre_instructions(
            {"what_to_bring": ["Traé estudios previos (radiografías u otros)"]}, "Consulta General"
        ),
        lambda joined: _globitos_reales(joined) == 1 and "estudios previos" in joined and "Consulta General" in joined,
    ),
    (
        "PRE vacío (tratamiento sin instrucciones) → NO manda nada",
        _format_pre_instructions({}, "Consulta General"),
        lambda joined: joined == "",
    ),
    (
        "POST dict (3 secciones) → 1 globito con todo",
        _format_post_instructions(POST_DICT, "Extracción"),
        lambda joined: (
            _globitos_reales(joined) == 1
            and "comidas duras" in joined
            and "ejercicio intenso" in joined
            and "Extracción" in joined
        ),
    ),
    (
        "POST lista legacy (solo inmediatas) → 1 globito",
        _format_post_instructions(
            [{"timing": "immediate", "text": "Aplicá frío 20 min"}, {"timing": "24h", "text": "esto NO va ahora"}],
            "Cirugía",
        ),
        lambda joined: _globitos_reales(joined) == 1 and "frío" in joined and "esto NO va ahora" not in joined,
    ),
]


def main() -> int:
    fallas = 0
    for nombre, bubbles, check in CASOS:
        joined = _join(bubbles)
        n_globitos = _globitos_reales(joined)
        ok = check(joined)
        print(f"{'✅ PASA ' if ok else '❌ FALLA'} — {nombre}  ({n_globitos} globito/s)")
        if not ok:
            fallas += 1
            print(f"     bubbles crudos: {bubbles}")
            print(f"     joined: {joined!r}")
    print()
    if fallas:
        print(f"RESULTADO: {fallas}/{len(CASOS)} FALLARON")
        return 1
    print(f"RESULTADO: {len(CASOS)}/{len(CASOS)} PASAN — playbooks consolidados en 1 globito (costo: $0)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
