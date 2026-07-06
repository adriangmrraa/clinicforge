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

    print("=" * 72)
    print(f"DESGLOSE DE TOKENS DEL PROMPT — tenant {args.tenant} — estado {args.status}")
    print(f"TOTAL: {total:,} tokens  ({'tiktoken' if enc else 'estimado ~char/4'})  |  {len(secs)} secciones")
    print("=" * 72)
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
