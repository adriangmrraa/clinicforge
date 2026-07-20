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


async def _complete(client, model, messages, temperature, tools=None):
    """chat.completions.create robusto ante modelos que no aceptan temperature."""
    kwargs = {"model": model, "messages": messages}
    if tools:
        kwargs["tools"] = tools
    try:
        return await client.chat.completions.create(temperature=temperature, **kwargs)
    except Exception as e:
        if "temperature" in str(e).lower():
            return await client.chat.completions.create(**kwargs)
        raise


async def _run_agent_turn(client, model, messages, temperature, tools, show_tools=False):
    """T1: mini-loop de agente con herramientas SIMULADAS (eval/mock_tools).

    Espeja el AgentExecutor de prod (max_iterations=4): el modelo puede llamar
    herramientas de juguete deterministas y recién después responder. Devuelve
    (respuesta_final, prompt_tokens, completion_tokens, [llamadas]).
    """
    from eval.mock_tools import execute_tool_call

    pt = ct = 0
    calls: list[str] = []
    msgs = list(messages)
    for _ in range(5):
        resp = await _complete(client, model, msgs, temperature, tools=tools)
        if getattr(resp, "usage", None):
            pt += resp.usage.prompt_tokens or 0
            ct += resp.usage.completion_tokens or 0
        msg = resp.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None)
        if not tool_calls:
            return (msg.content or ""), pt, ct, calls
        # Registrar la respuesta del asistente CON sus tool_calls y ejecutar mocks
        msgs.append(
            {
                "role": "assistant",
                "content": msg.content or None,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )
        for tc in tool_calls:
            result = execute_tool_call(tc)
            calls.append(f"{tc.function.name}({(tc.function.arguments or '')[:80]})")
            if show_tools:
                print(f"      🔧 {tc.function.name} -> {result[:110]}")
            msgs.append({"role": "tool", "tool_call_id": tc.id, "content": result})
    return "", pt, ct, calls  # se quedó sin iteraciones


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
    ap.add_argument("--categoria", default=None, help="Filtrar por categoría (o varias separadas por coma)")
    ap.add_argument("--case", default=None, help="Correr un solo caso por id")
    ap.add_argument("--cases-file", default=str(Path(__file__).parent / "cases.jsonl"))
    # temperature=0 para ESPEJAR PRODUCCIÓN (main.py crea el LLM con temperature=0):
    # con 0.3 el banco tenía varianza artificial que prod NO tiene — casos que
    # pasaban/fallaban al azar entre corridas con el MISMO prompt (flip-flops).
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--show-response", action="store_true", help="Imprimir la respuesta completa")
    ap.add_argument("--show-prompt", action="store_true", help="Volcar el system prompt y salir")
    # T1.b (2026-07-12): herramientas SIMULADAS por caso (opt-in con "tools":
    # true en cases.jsonl). La v1 default-ON duplicó el costo (cada iteración
    # re-envía el prompt de ~54k tokens) y derrumbó la nota a 51% en casos que
    # nunca necesitaron herramientas. --tools-all fuerza ON global (experimentos);
    # --no-tools fuerza OFF global.
    ap.add_argument("--no-tools", action="store_true", help="Forzar SIN herramientas en todos los casos")
    ap.add_argument("--tools-all", action="store_true", help="Forzar herramientas en TODOS los casos (caro)")
    ap.add_argument("--show-tools", action="store_true", help="Imprimir cada llamada a herramienta simulada")
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

        def prompt_for(status: str, patient_context: str = "", tags: set | None = None) -> str:
            key = f"{status}||{patient_context}||{sorted(tags) if tags else []}"
            if key not in prompt_cache:
                prompt_cache[key] = build_eval_prompt(
                    inputs, patient_status=status, patient_context=patient_context,
                    intent_tags=tags,
                )
            return prompt_cache[key]

        if args.show_prompt:
            print(prompt_for("new_lead"))
            return 0

        # Clasificador REAL de producción (ronda 2 de grasa): cada caso se corre con
        # los tags que ese paciente tendría en prod → el banco prueba el MISMO prompt
        # gateado que producción. Sin esto, probaría el prompt inject-all que prod
        # casi nunca corre para mensajes con intención detectada.
        from services.buffer_task import classify_intent

        mc = await _resolve_model(pool, args.tenant, args.model)
        if not mc["api_key"]:
            print("ERROR: falta OPENAI_API_KEY (o DEEPSEEK_API_KEY) en el entorno.", file=sys.stderr)
            return 2
        client = AsyncOpenAI(api_key=mc["api_key"], base_url=mc["base_url"])

        cases = _load_cases(Path(args.cases_file))
        if args.categoria:
            _cats = {x.strip() for x in args.categoria.split(",") if x.strip()}
            cases = [c for c in cases if c.get("categoria") in _cats]
        if args.case:
            cases = [c for c in cases if c.get("id") == args.case]
        if not cases:
            print("No hay casos que coincidan con el filtro.", file=sys.stderr)
            return 1

        from eval.mock_tools import tool_schemas

        _schemas = tool_schemas()

        def tools_for(case: dict):
            if args.no_tools:
                return None
            if args.tools_all or case.get("tools"):
                return _schemas
            return None

        n_tool_cases = sum(1 for c in cases if tools_for(c))
        print("=" * 72)
        print(f"BANCO DE PRUEBAS — clínica: {inputs['clinic_name']} (tenant {args.tenant})")
        print(f"Modelo bajo prueba: {mc['model']}   |   Juez: {args.judge_model}   |   Casos: {len(cases)}")
        print(f"Herramientas simuladas: {n_tool_cases}/{len(cases)} casos (opt-in por caso)")
        print("=" * 72)

        results = []
        tot_pt = tot_ct = 0
        for c in cases:
            status = c.get("patient_status", "new_lead")
            # Tags como en prod: texto del paciente (user actual + historial rol user)
            # + suplemento de payment desde el contexto (espeja buffer_task ~2298).
            _case_texts = [c.get("user", "")] + [
                (h.get("content") or h.get("texto") or "")
                for h in (c.get("history") or [])
                if (h.get("role") or ("assistant" if h.get("de") in ("bot", "asistente") else "user")) == "user"
            ]
            case_tags = classify_intent([t for t in _case_texts if t])
            _ctx_low = (c.get("patient_context") or "").lower()
            if "payment_status" in _ctx_low or "pendiente" in _ctx_low:
                case_tags.add("payment")
            # INYECCIONES FRESCAS (espejo de buffer_task): el banco corre el MISMO
            # contexto fresco que prod. Funciones puras compartidas — no hay copia.
            from services.inyecciones_frescas import aplicar_inyecciones

            _last_bot_hist = next(
                (
                    (h.get("content") or h.get("texto") or "")
                    for h in reversed(c.get("history") or [])
                    if (h.get("role") or ("assistant" if h.get("de") in ("bot", "asistente") else "user")) == "assistant"
                ),
                "",
            )
            # Nivel 2 del coseguro: cuántas veces el bot YA lo explicó (en prod es una
            # query a chat_messages; en el banco se cuenta en el history del caso).
            # 'depende del/de tu plan' cuenta aunque el bot haya variado la palabra.
            _cos_hist_count = sum(
                1
                for h in (c.get("history") or [])
                if (h.get("role") or ("assistant" if h.get("de") in ("bot", "asistente") else "user")) == "assistant"
                and any(
                    k in ((h.get("content") or h.get("texto") or "").lower())
                    for k in ("coseguro", "depende del plan", "depende de tu plan")
                )
            )
            # Semáforo: el caso declara os_delayed={"name","delay_days"} y acá se
            # computa la primera fecha por cobertura (hoy+N, igual que prod).
            _os_delayed_param = None
            if c.get("os_delayed"):
                from datetime import date as _qa_d, timedelta as _qa_t
                _os_dd = int((c["os_delayed"].get("delay_days") or 0))
                _os_delayed_param = {
                    "name": c["os_delayed"].get("name", ""),
                    "delay_days": _os_dd,
                    "min_date": (_qa_d.today() + _qa_t(days=_os_dd)).strftime("%d/%m"),
                }
            _ctx_con_iny = (c.get("patient_context", "") or "") + aplicar_inyecciones(
                c.get("user", ""),
                user_texts=[t for t in _case_texts if t],
                last_bot=_last_bot_hist,
                coseguro_ya_explicado=_cos_hist_count,
                os_delayed=_os_delayed_param,
            )
            # Gate A1 de cobertura (espejo de buffer_task, texto compartido): dispara
            # cuando el caso NO trae la cobertura resuelta en su contexto — igual que
            # prod para un lead sin cobertura conocida.
            import re as _re_a1
            from services.inyecciones_frescas import iny_gate_cobertura
            _a1_ctx_low = (c.get("patient_context") or "").lower()
            _a1_minor = "internal_booking_context" in _a1_ctx_low or "hijo/a menor" in _a1_ctx_low
            _a1_conocida = bool(
                _re_a1.search(
                    r"obra social registrada|\bissn\b|particular|cobertura\s+[a-záéíóú]+",
                    _a1_ctx_low,
                )
            )
            _a1_txt = iny_gate_cobertura(_a1_minor, _a1_conocida)
            if _a1_txt:
                _ctx_con_iny = (_ctx_con_iny + "\n" + _a1_txt) if _ctx_con_iny else _a1_txt
            messages = [{"role": "system", "content": prompt_for(status, _ctx_con_iny, case_tags)}]
            messages += _history_to_messages(c.get("history"))
            messages.append({"role": "user", "content": c.get("user", "")})

            tool_trace: list[str] = []
            tools = tools_for(c)
            try:
                if tools:
                    # Contexto por-caso para las herramientas simuladas (ej:
                    # mock_availability_days para reproducir "sin turno cercano").
                    from eval import mock_tools as _mt
                    _mt.set_context({
                        "avail_days": c.get("mock_availability_days"),
                        "book_fails": c.get("mock_book_fails"),
                        "my_appointments": c.get("mock_my_appointments"),
                        "patient_status": c.get("patient_status"),
                        # Gate de cobertura (espejo del real, opt-in por caso): la 1ª
                        # check_availability sin insurance_provider devuelve
                        # COBERTURA_DESCONOCIDA y el bot debe preguntar primero.
                        "cov_gate": bool(c.get("cov_gate")),
                    })
                    answer, _pt, _ct, tool_trace = await _run_agent_turn(
                        client, mc["model"], messages, args.temperature, tools,
                        show_tools=args.show_tools,
                    )
                    tot_pt += _pt
                    tot_ct += _ct
                else:
                    resp = await _complete(client, mc["model"], messages, args.temperature)
                    answer = resp.choices[0].message.content or ""
                    if getattr(resp, "usage", None):
                        tot_pt += resp.usage.prompt_tokens or 0
                        tot_ct += resp.usage.completion_tokens or 0
            except Exception as e:
                answer = ""
                print(f"\n[{c.get('id')}] ERROR llamando al modelo: {e}")

            # CADENA COMPLETA DE CANDADOS DE SALIDA (espejo de buffer_task, 2026-07-18):
            # en prod la respuesta pasa por TODOS los candados deterministas antes de
            # llegar al paciente. El banco juzga lo que el paciente VE — aplicamos la
            # cadena entera en el MISMO orden que buffer_task:
            #   recurrente/continuidad → precio-no-repetir → cierre → oferta → coseguro
            from eval.test_candado_salida import candado_salida as _c_salida
            from eval.test_candado_cobertura_chat import (
                candado_cobertura_chat as _c_cov_chat,
                candado_reintegro as _c_reintegro,
            )
            from eval.test_candado_gate_precio import candado_gate_precio as _c_gate
            from eval.test_candado_radar_turno import (
                candado_post_booking as _c_postbook,
                candado_reserva_fantasma as _c_reserva,
            )
            from eval.test_candado_precio import candado_precio as _c_precio
            from eval.test_candado_cierre import candado_cierre as _c_cierre
            from eval.test_candado_oferta_coseguro import (
                candado_oferta as _c_oferta,
                candado_coseguro as _c_coseguro,
            )
            _pre_candado = answer
            answer = _c_salida(answer, c.get("patient_context", ""), c.get("user", ""))
            answer = _c_cov_chat(answer, c.get("user", ""))
            answer = _c_reintegro(answer, c.get("patient_context", ""), c.get("user", ""))
            answer = _c_postbook(answer, c.get("patient_context", ""), c.get("user", ""))
            _tool_names_turn = [t.split("(")[0] for t in (tool_trace or [])]
            answer = _c_reserva(answer, _tool_names_turn, "")
            answer = _c_gate(answer, c.get("patient_context", ""), c.get("user", ""))
            # precio ya-dicho: en el banco, "ya se envió" = algún mensaje previo del
            # bot en el history del caso contiene el párrafo del valor.
            _already_priced = any(
                "tiene un valor" in (h.get("content") or h.get("texto") or "")
                for h in (c.get("history") or [])
                if (h.get("role") or ("assistant" if h.get("de") in ("bot", "asistente") else "user")) == "assistant"
            )
            answer = _c_precio(answer, _already_priced)
            answer = _c_cierre(answer)
            answer = _c_oferta(answer)
            answer = _c_coseguro(answer)
            # Candados nuevos (banco v2/v3): compartidos con buffer_task, sin espejo a mano.
            from services.inyecciones_frescas import (
                candado_avance as _c_avance,
                candado_encuadre_valor as _c_encuadre,
                candado_mencion_coseguro as _c_mencos,
                candado_multi_turno as _c_multiturno,
            )
            from services.inyecciones_frescas import candado_compactar_cimo as _c_cimo
            from services.inyecciones_frescas import candado_dia_sin_consultar as _c_dsc
            answer = _c_cimo(answer)
            answer = _c_dsc(answer, _tool_names_turn)
            answer = _c_mencos(answer, c.get("user", ""), c.get("patient_context", ""))
            answer = _c_encuadre(answer, c.get("user", ""))
            answer = _c_avance(answer, c.get("user", ""), _tool_names_turn)
            if c.get("mock_my_appointments") == "two":
                from eval.mock_tools import fechas_futuras_two as _f2
                answer = _c_multiturno(answer, _f2())
            # Salida del quiere-antes: misma activación que buffer_task (la inyección
            # quiere-antes disparó este turno → la oferta debe recordar la vía particular).
            if _os_delayed_param:
                from services.inyecciones_frescas import (
                    candado_quiere_antes_salida as _c_qas,
                    quiere_antes_matchea as _qam,
                )
                if _qam(c.get("user", "")):
                    answer = _c_qas(answer)
            # Legibilidad (casos manuales 1/3/6/7/8 del 2026-07-20) — mismo orden que buffer_task:
            # coseguro-frío → particular-incoherente → formato (el formato SIEMPRE al final).
            from services.inyecciones_frescas import (
                candado_coseguro_frio as _c_cfrio,
                candado_formato as _c_fmt,
                candado_particular_incoherente as _c_pinc,
            )
            answer = _c_cfrio(answer)
            answer = _c_pinc(answer)
            answer = _c_fmt(answer)
            if _pre_candado != answer:
                print(f"    [candados] la cadena recortó/reagrupó ({len(_pre_candado)}->{len(answer)} chars)")

            # [SILENCIO] = el agente decidió no responder (anti-loop de cortesía).
            # No lo mandamos al juez: lo evaluamos según lo que el caso espera.
            if (answer or "").strip().upper().startswith("[SILENCIO]"):
                if c.get("espera_silencio"):
                    verdict = {"pasa": True, "criterios": [{"criterio": "silencio esperado ante un simple agradecimiento", "pasa": True, "razon": "el bot se quedó en silencio ([SILENCIO]) — correcto"}], "error": None}
                else:
                    verdict = {"pasa": False, "criterios": [{"criterio": "no debía quedarse en silencio", "pasa": False, "razon": "el bot devolvió [SILENCIO] cuando debía responder"}], "error": None}
            else:
                verdict = await judge_case(client, args.judge_model, c, answer, tool_trace=tool_trace)
            results.append((c, verdict, answer))

            mark = "PASA " if verdict["pasa"] else "FALLA"
            _tags_str = f"  tags={sorted(case_tags)}" if case_tags else ""
            print(f"\n[{mark}] {c.get('id')}  ({c.get('categoria', '-')}){_tags_str}")
            print(f"    paciente: {c.get('user','')[:90]}")
            for cr in verdict["criterios"]:
                if not cr["pasa"]:
                    print(f"      X  {cr['criterio']}  ->  {cr['razon']}")
            if args.show_response or not verdict["pasa"]:
                print(f"    respuesta: {answer[:300]}")
                if tool_trace:
                    print(f"    herramientas: {', '.join(tool_trace)}")

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
