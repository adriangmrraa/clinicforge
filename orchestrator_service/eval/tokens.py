"""Desglose de tokens del system prompt por sección — para saber QUÉ recortar.

El prompt pesa ~49.500 tokens por mensaje. Este script lo arma (real, del tenant)
y lo parte en secciones, contando tokens de cada una, ordenadas de mayor a menor.
Así vemos dónde está la "grasa" antes de cortar, y medimos sin adivinar.

Uso (en el contenedor de pruebas):
    python -m eval.tokens                 # tenant 1, estado new_lead, top 25 secciones
    python -m eval.tokens --status patient_with_appointment
    python -m eval.tokens --top 40
"""
from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None

from eval.fixture import build_eval_prompt, load_prompt_inputs


def _encoder():
    try:
        import tiktoken
        try:
            return tiktoken.encoding_for_model("gpt-4o")
        except Exception:
            return tiktoken.get_encoding("o200k_base")
    except Exception:
        return None


def _count(enc, text: str) -> int:
    if enc:
        return len(enc.encode(text))
    return max(1, len(text) // 4)  # estimación si no hay tiktoken


_HEADER = re.compile(
    r"^(={2,}.*|PASO\s+\d.*|CAMINO\s+\d.*|FASE\s+\d.*|F\d+[:\).].*|M\d+\s*[—\-:].*|"
    r"[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ0-9 \-/()·]{7,}:?.*)$"
)


def _split_sections(prompt: str):
    """Parte el prompt en secciones usando líneas que parecen encabezados."""
    sections = []
    title = "· (encabezado / identidad)"
    buf: list[str] = []
    for ln in prompt.split("\n"):
        if _HEADER.match(ln.strip()) and len(ln.strip()) > 4:
            if buf:
                sections.append((title, "\n".join(buf)))
            title = ln.strip()[:68]
            buf = [ln]
        else:
            buf.append(ln)
    if buf:
        sections.append((title, "\n".join(buf)))
    return sections


# Clasificación en familias para el rollup: (nombre, regex sobre título, regex sobre cuerpo).
# Se evalúan en orden; la primera que matchea gana. 'body' ayuda cuando el título
# de una OS (ej "APSOT (prepaga):") no delata que es cobertura.
_BUCKETS = [
    ("Obras sociales / cobertura", re.compile(r"OBRA|COBERTURA|COSEGURO|PREPAGA|AFILIAD", re.I),
     re.compile(r"cubierto|coseguro|preautoriza|carencia|obra social", re.I)),
    ("Flujos F1–F10", re.compile(r"\bF\d+|FLUJO|CAMINO\s+\d", re.I), None),
    ("Pasos / M0–M6", re.compile(r"\bPASO\s+\d|\bM\d\b|SECUENCIA", re.I), None),
    ("Identidad / tono", re.compile(r"IDENTIDAD|TONO|PERSONALIDAD|VOSEO", re.I), None),
    ("Reglas primordiales", re.compile(r"REGLA|PROHIBID|OBLIGATOR|GATE|CRÍTIC", re.I), None),
    ("Urgencia / triage", re.compile(r"URGENCIA|TRIAGE|DOLOR|EMERGENC", re.I), None),
    ("Ortodoncia / cirugía / implante", re.compile(r"ORTODONCIA|CIRUG|IMPLANTE|PRÓTESIS|PROTESIS", re.I), None),
    ("FAQs / conocimiento", re.compile(r"\bFAQ|PREGUNTAS FRECUENTES|CONOCIMIENTO", re.I), None),
    ("Pagos / seña / facturación", re.compile(r"PAGO|SEÑA|SENA|COMPROBANTE|TRANSFER|FACTURA|BANC", re.I), None),
    ("Adjuntos / multimedia", re.compile(r"ADJUNTO|IMAGEN|MULTIMEDIA|VISUAL|DOCUMENTO", re.I), None),
    ("Agenda / disponibilidad", re.compile(r"AGENDA|DISPONIBIL|TURNO|HORARIO|SEDE|FECHA", re.I), None),
]


def _bucket(title: str, body: str) -> str:
    for name, tre, bre in _BUCKETS:
        if tre.search(title):
            return name
        if bre and bre.search(body):
            return name
    return "· Otros"


async def main() -> int:
    ap = argparse.ArgumentParser(description="Desglose de tokens del prompt")
    ap.add_argument("--tenant", type=int, default=int(os.getenv("EVAL_TENANT_ID", "1")))
    ap.add_argument("--status", default="new_lead", help="new_lead | patient_no_appointment | patient_with_appointment")
    ap.add_argument("--top", type=int, default=25)
    args = ap.parse_args()

    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not dsn or asyncpg is None:
        print("ERROR: falta POSTGRES_DSN (o asyncpg).", file=sys.stderr)
        return 2

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    try:
        inputs = await load_prompt_inputs(pool, args.tenant)
        prompt = build_eval_prompt(inputs, patient_status=args.status)
    finally:
        await pool.close()

    enc = _encoder()
    total = _count(enc, prompt)
    secs = _split_sections(prompt)
    rows = sorted(((t, _count(enc, body)) for t, body in secs), key=lambda r: -r[1])

    # Rollup por familia: agrupa las 300+ secciones en ~12 buckets para ver
    # qué familia pesa más (las 17 OS repartidas suman mucho aunque cada una sea chica).
    buckets: dict[str, list] = {}
    for title, body in secs:
        b = _bucket(title, body)
        buckets.setdefault(b, [0, 0])
        buckets[b][0] += _count(enc, body)
        buckets[b][1] += 1
    bucket_rows = sorted(buckets.items(), key=lambda r: -r[1][0])

    print("=" * 72)
    print(f"DESGLOSE DE TOKENS DEL PROMPT — tenant {args.tenant} — estado {args.status}")
    print(f"TOTAL: {total:,} tokens  ({'tiktoken' if enc else 'estimado ~char/4'})  |  {len(secs)} secciones")
    print("=" * 72)
    print("ROLLUP POR FAMILIA (dónde está la grasa):")
    print(f"{'TOKENS':>8}  {'%':>5}  {'SECC':>4}  FAMILIA")
    for name, (tk, cnt) in bucket_rows:
        pct = (tk / total * 100) if total else 0
        print(f"{tk:>8,}  {pct:4.1f}%  {cnt:>4}  {name}")
    print("=" * 72)
    print(f"TOP {args.top} SECCIONES INDIVIDUALES:")
    print(f"{'TOKENS':>8}  {'%':>5}  SECCIÓN")
    for t, n in rows[: args.top]:
        pct = (n / total * 100) if total else 0
        print(f"{n:>8,}  {pct:4.1f}%  {t}")
    shown = sum(n for _, n in rows[: args.top])
    print("-" * 72)
    print(f"(top {args.top} secciones = {shown:,} tokens, {shown / total * 100:.0f}% del total)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
