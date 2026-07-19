# -*- coding: utf-8 -*-
"""Resolución central de teléfonos familiares (menores / terceros que comparten número).

Diseño (2026-07-18, pedido Carlos: "que no se dupliquen teléfonos y el seguimiento
se lo hagan realmente a la persona a cargo"):

- Un MENOR/familiar sin WhatsApp propio se registra con teléfono placeholder
  `{telefono_del_adulto}-M{N}` y `guardian_phone = teléfono del adulto`
  (mecanismo que el BOT ya usa en book_appointment; acá se centraliza para que
  el PANEL y los JOBS usen la misma regla).

- REGLA DE ENVÍO: todo mensaje saliente a un paciente debe ir a
  `resolve_contact_phone(phone, guardian)` — si el teléfono es placeholder
  (-M{N} o SIN-TEL-*), el destino real es el guardián.

- REGLA DE CREACIÓN (panel): si el número ya pertenece a OTRA persona (nombre
  distinto), NO se pisa la ficha existente — se crea un familiar con -M{N}.

SOLO funciones puras: testeables gratis (eval/test_family_phones.py).
"""
from __future__ import annotations

import re
import unicodedata

_PLACEHOLDER_RE = re.compile(r"-M\d+$", re.IGNORECASE)


def is_placeholder_phone(phone: str | None) -> bool:
    """True si el teléfono NO es un WhatsApp real: sufijo -M{N} (menor/familiar)
    o placeholder de import (SIN-TEL-*)."""
    p = (phone or "").strip()
    if not p:
        return True
    if _PLACEHOLDER_RE.search(p):
        return True
    if p.upper().startswith("SIN-TEL"):
        return True
    return False


def resolve_contact_phone(phone: str | None, guardian_phone: str | None) -> str | None:
    """El número al que REALMENTE hay que escribir: el guardián si el teléfono del
    paciente es placeholder y hay guardián; si no, el propio. None si no hay a quién."""
    g = (guardian_phone or "").strip()
    if is_placeholder_phone(phone):
        return g or None
    return (phone or "").strip() or (g or None)


def _norm_name(name: str | None) -> str:
    """minúsculas, sin tildes, solo el PRIMER nombre."""
    n = (name or "").strip().lower()
    n = unicodedata.normalize("NFD", n)
    n = "".join(ch for ch in n if unicodedata.category(ch) != "Mn")
    return n.split()[0] if n.split() else ""


def same_person(name_a: str | None, name_b: str | None) -> bool:
    """Heurística conservadora: misma persona si el primer nombre normalizado
    coincide (case/tildes-insensitive). Nombres vacíos NO deciden (True para no
    crear familiares fantasma por un alta sin nombre)."""
    a, b = _norm_name(name_a), _norm_name(name_b)
    if not a or not b:
        return True
    return a == b


def next_minor_phone(parent_phone: str, existing_family_count: int) -> str:
    """El siguiente placeholder -M{N} para un familiar del adulto (mismo formato
    que usa el bot en book_appointment)."""
    return f"{(parent_phone or '').strip()}-M{int(existing_family_count) + 1}"
