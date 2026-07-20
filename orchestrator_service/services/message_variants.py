# -*- coding: utf-8 -*-
"""Variantes rotativas para mensajes automáticos (confirmación + seguimiento).

Pedido Carlos 2026-07-20: los mensajes fijos se sienten robóticos cuando se
repiten ("✅ ¡Gracias por confirmar!..." idéntico siempre; "Hola FRANCESCO TOMAS"
en mayúsculas). Acá: variantes fijas ROTADAS de forma determinista (sin LLM,
costo cero) + nombre humanizado.

Rotación: crc32(seed) % N — estable entre procesos (no depende de PYTHONHASHSEED),
así el mismo paciente tiende a recibir variantes distintas usando seeds distintos
(ej. phone+fecha) y los tests son reproducibles.

SOLO funciones puras → test gratis en eval/test_message_variants.py.
"""
from __future__ import annotations

import zlib

_DIAS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def nombre_bonito(first_name: str | None) -> str:
    """'FRANCESCO TOMAS' → 'Francesco' (primer nombre, capitalizado)."""
    n = (first_name or "").strip()
    if not n:
        return ""
    primero = n.split()[0]
    return primero[:1].upper() + primero[1:].lower()


def dia_humano(dt) -> str:
    """datetime → 'miércoles 23/07' (para hablar como una persona, no como sistema)."""
    try:
        return f"{_DIAS_ES[dt.weekday()]} {dt.strftime('%d/%m')}"
    except Exception:
        return ""


def _pick(seed: str, opciones: list) -> str:
    idx = zlib.crc32((seed or "x").encode("utf-8", errors="ignore")) % len(opciones)
    return opciones[idx]


def variante_confirmacion(seed: str, dia: str = "") -> str:
    """Mensaje al confirmar asistencia. Con el día si está disponible."""
    if dia:
        opciones = [
            f"✅ ¡Gracias por confirmar! Te esperamos el {dia} 🦷",
            f"¡Perfecto! Tu turno del {dia} queda confirmado. ¡Nos vemos! 😊",
            f"¡Genial, quedó confirmado tu turno del {dia}! Te esperamos 🦷",
        ]
    else:
        opciones = [
            "✅ ¡Gracias por confirmar! Te esperamos en tu próximo turno 🦷",
            "¡Perfecto! Queda confirmada tu asistencia. ¡Nos vemos! 😊",
            "¡Genial! Tu turno queda confirmado. Te esperamos 🦷",
        ]
    return _pick(seed, opciones)


def variante_followup(seed: str, nombre: str, fecha: str, para_guardian: bool = False) -> str:
    """Mensaje de seguimiento post-atención. Si va al guardián (menor/familiar sin
    WhatsApp propio), pregunta cómo SIGUE el paciente, no 'cómo te sentís'."""
    n = nombre_bonito(nombre) or "!"
    if para_guardian:
        opciones = [
            f"Hola! ¿Cómo sigue {n} después de la atención de ayer ({fecha})? Cualquier molestia, avisanos 😊",
            f"Hola! Queríamos saber cómo está {n} después de la consulta de ayer ({fecha}). ¿Todo bien?",
            f"Hola! ¿Cómo anduvo {n} después de la atención de ayer ({fecha})? Si aparece alguna molestia, escribinos 😊",
        ]
    else:
        opciones = [
            f"Hola {n}! ¿Cómo te sentiste después de la atención de ayer ({fecha})? Cualquier molestia, avisanos 😊",
            f"Hola {n}! Queríamos saber cómo va todo después de tu consulta de ayer ({fecha}). ¿Alguna molestia o está todo bien?",
            f"{n}, ¿cómo seguís después de la atención de ayer ({fecha})? Si aparece cualquier molestia, escribinos 😊",
        ]
    return _pick(seed, opciones)
