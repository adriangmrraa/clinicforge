"""Runner del banco de pruebas del agente.

Corre los casos de eval/cases.jsonl contra el prompt REAL del tenant, sin
herramientas, y usa un juez IA para marcar cada respuesta. Imprime un reporte
con % de aprobación, tokens y (si se conoce el precio) costo estimado.

Ejemplos:
    python -m eval.run
    python -m eval.run --model deepseek-chat
    python -m eval.run --categoria cobertura
    python -m eval.run --case cobertura-precio-sin-os --show-response
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

try:
    import asyncpg
except ImportError:  # pragma: no cover
    asyncpg = None

from openai import AsyncOpenAI

from eval.fixture import build_eval_prompt, load_prompt_inputs
from eval.judge import judge_case

DEFAULT_MODEL = os.getenv("DEFAULT_OPENAI_MODEL", "gpt-5.4-mini")
DEEPSEEK_MODELS = {"deepseek-chat", "deepseek-reasoner"}
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Precio aproximado por 1M de tokens (USD) — solo para estimar. Actualizar según tarifas.
PRICE_PER_1M = {
    "gpt-5.4-mini": (0.15, 0.60),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.0),
    "deepseek-chat": (0.27, 1.10),
}


async def _resolve_model(pool, tenant_id: int, override: str | None) -> dict:
    """Mirror mínimo de agents/model_resolver.resolve_tenant_model (sin credenciales de tenant)."""
    model = override
    if not model:
        try:
            row = await pool.fetchrow(
                "SELECT value FROM system_config WHERE key = $1 AND tenant_id = $2",
                "OPENAI_MODEL",
                tenant_id,
            )
            if row and row.get("value"):
                model = str(row["value"]).strip()
        except Exception:
            pass
    if not model or model == "gpt-3.5-turbo":
        model = DEFAULT_MODEL

    if model in DEEPSEEK_MODELS:
        return {
            "model": model,
            "api_key": os.getenv("DEEPSEEK_API_KEY", "") or os.getenv("OPENAI_API_KEY", ""),
            "base_url": DEEPSEEK_BASE_URL,
        }
    return {"model": model, "api_key": os.getenv("OPENAI_API_KEY", ""), "base_url": None}


async def _complete(client, model, messages, temperature):
    """chat.completions.create robusto ante modelos que no aceptan temperature."""
    try:
        return await client.chat.completions.create(
            model=model, messages=messages, temperature=temperature
        )
    except Exception as e:
        if "temperature" in str(e).lower():
            return await client.chat.completions.create(model=model, messages=messages)
        raise


def _load_cases(cases_file: Path) -> list[dict]:
    cases = []
    with open(cases_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("#"):
                continue
            cases.append(json.loads(line))
    return cases


def _history_to_messages(history: list[dict]) -> list[dict]:
    msgs = []
    for h in history or []:
        role = h.get("role") or ("assistant" if h.get("de") in ("bot", "asistente") else "user")
        msgs.append({"role": role, "content": h.get("content") or h.get("texto") or ""})
    return msgs


async def main() -> int:
    ap = argparse.ArgumentParser(description="Banco de pruebas del agente (offline)")
    ap.add_argument("--tenant", type=int, default=int(os.getenv("EVAL_TENANT_ID", "1")))
    ap.add_argument("--model", default=None, help="Forzar un modelo (ej. deepseek-chat) para comparar")
    ap.add_argument("--judge-model", default=os.getenv("EVAL_JUDGE_MODEL", "gpt-5.4-mini"))
    ap.add_argument("--categoria", default=None, help="Filtrar por categoría")
    ap.add_argument("--case", default=None, help="Correr un solo caso por id")
    ap.add_argument("--cases-file", default=str(Path(__file__).parent / "cases.jsonl"))
    ap.add_argument("--temperature", type=float, default=0.3)
    ap.add_argument("--show-response", action="store_true", help="Imprimir la respuesta completa")
    ap.add_argument("--show-prompt", action="store_true", help="Volcar el system prompt y salir")
    args = ap.parse_args()

    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not dsn or asyncpg is None:
        print("ERROR: falta POSTGRES_DSN en el entorno (o asyncpg no instalado).", file=sys.stderr)
        return 2

    pool = await asyncpg.create_pool(dsn=dsn, min_size=1, max_size=2)
    try:
        inputs = await load_prompt_inputs(pool, args.tenant)

        # Cache del prompt por patient_status (mismo prefijo estático para todos los casos)
        prompt_cache: dict[str, str] = {}

        def prompt_for(status: str, patient_context: str = "") -> str:
            key = f"{status}||{patient_context}"
            if key not in prompt_cache:
                prompt_cache[key] = build_eval_prompt(
                    inputs, patient_status=status, patient_context=patient_context
                )
            return prompt_cache[key]

        if args.show_prompt:
            print(prompt_for("new_lead"))
            return 0

        mc = await _resolve_model(pool, args.tenant, args.model)
        if not mc["api_key"]:
            print("ERROR: falta OPENAI_API_KEY (o DEEPSEEK_API_KEY) en el entorno.", file=sys.stderr)
            return 2
        client = AsyncOpenAI(api_key=mc["api_key"], base_url=mc["base_url"])

        cases = _load_cases(Path(args.cases_file))
        if args.categoria:
            cases = [c for c in cases if c.get("categoria") == args.categoria]
        if args.case:
            cases = [c for c in cases if c.get("id") == args.case]
        if not cases:
            print("No hay casos que coincidan con el filtro.", file=sys.stderr)
            return 1

        print("=" * 72)
        print(f"BANCO DE PRUEBAS — clínica: {inputs['clinic_name']} (tenant {args.tenant})")
        print(f"Modelo bajo prueba: {mc['model']}   |   Juez: {args.judge_model}   |   Casos: {len(cases)}")
        print("=" * 72)

        results = []
        tot_pt = tot_ct = 0
        for c in cases:
            status = c.get("patient_status", "new_lead")
            messages = [{"role": "system", "content": prompt_for(status, c.get("patient_context", ""))}]
            messages += _history_to_messages(c.get("history"))
            messages.append({"role": "user", "content": c.get("user", "")})

            try:
                resp = await _complete(client, mc["model"], messages, args.temperature)
                answer = resp.choices[0].message.content or ""
                if getattr(resp, "usage", None):
                    tot_pt += resp.usage.prompt_tokens or 0
                    tot_ct += resp.usage.completion_tokens or 0
            except Exception as e:
                answer = ""
                print(f"\n[{c.get('id')}] ERROR llamando al modelo: {e}")

            verdict = await judge_case(client, args.judge_model, c, answer)
            results.append((c, verdict, answer))

            mark = "PASA " if verdict["pasa"] else "FALLA"
            print(f"\n[{mark}] {c.get('id')}  ({c.get('categoria', '-')})")
            print(f"    paciente: {c.get('user','')[:90]}")
            for cr in verdict["criterios"]:
                if not cr["pasa"]:
                    print(f"      X  {cr['criterio']}  ->  {cr['razon']}")
            if args.show_response or not verdict["pasa"]:
                print(f"    respuesta: {answer[:300]}")

        # ---- Resumen ----
        passed = sum(1 for _, v, _ in results if v["pasa"])
        total = len(results)
        rate = (passed / total * 100) if total else 0.0
        print("\n" + "=" * 72)
        print(f"RESULTADO: {passed}/{total} casos PASAN  ({rate:.0f}%)")
        by_cat: dict[str, list[int]] = {}
        for c, v, _ in results:
            cat = c.get("categoria", "-")
            agg = by_cat.setdefault(cat, [0, 0])
            agg[0] += 1 if v["pasa"] else 0
            agg[1] += 1
        for cat, (p, t) in sorted(by_cat.items()):
            print(f"   - {cat}: {p}/{t}")

        price = PRICE_PER_1M.get(mc["model"])
        cost_str = ""
        if price:
            cost = tot_pt / 1_000_000 * price[0] + tot_ct / 1_000_000 * price[1]
            cost_str = f"   |   costo estimado: US$ {cost:.4f}"
        print(f"TOKENS: prompt={tot_pt:,}  respuesta={tot_ct:,}  total={tot_pt + tot_ct:,}{cost_str}")
        print("=" * 72)
        return 0 if passed == total else 1
    finally:
        await pool.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
