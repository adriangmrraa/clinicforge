"""Simulador E2E del agente — "banco de agendado" (v1).

A DIFERENCIA del banco (eval/run.py), que solo arma el prompt y usa un juez IA,
este simulador ejecuta las HERRAMIENTAS REALES (book_appointment, check_availability)
contra la BASE DE DATOS, y revisa el RESULTADO real — no solo lo que el bot dice.

Es lo que el banco NO puede: cazar los bugs de AGENDADO (que un hijo se pueda agendar,
que no se bloquee como "duplicado", que no aparezca un falso "se ocupó").

⚠️ SEGURIDAD:
  - Usa un TELÉFONO DE PRUEBA falso (TEST_PHONE) que no existe como paciente real.
  - Limpia SIEMPRE al terminar (borra el paciente de prueba, sus turnos y su estado).
  - La limpieza toca EXCLUSIVAMENTE ese teléfono y sus variantes -M (nunca un LIKE amplio).
  - Corre contra la base de PRUEBAS. NUNCA apuntarlo a producción.

CÓMO CORRERLO (dentro del contenedor de PRUEBAS):
    docker cp orchestrator_service/eval <cont>:/app/eval   # si no está deployado
    docker exec -it <cont> python -m eval.e2e

Requisitos de entorno (ya presentes en el contenedor): POSTGRES_DSN, REDIS_URL.

ESTADO: v1 — prueba el candado del hijo-duplicado (fix #3) de forma determinista y el
corto-circuito del "[DADOS]". Los casos "quiere-antes" (#1) y "se-ocupó" (#2) necesitan
sembrar un turno de prueba y se suman en v2.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Teléfono de prueba: número imposible de que sea un paciente real. La limpieza solo
# toca este teléfono y sus menores (TEST_PHONE-M1, -M2, ...).
TEST_PHONE = os.getenv("EVAL_E2E_PHONE", "+5490000000001")
TEST_TENANT = int(os.getenv("EVAL_E2E_TENANT", "1"))

# Marcadores garbage que el mini a veces devuelve (espejo de buffer_task.py). Si esta
# lista cambia allá, actualizarla acá.
_GARBAGE_PLACEHOLDERS = ("[DADOS]", "[DATOS]", "[DATA]", "[DADO]", "[...]", "[]", "[N/A]")


async def _invoke_tool(tool, **kwargs):
    """Llama la función REAL detrás de una @tool de LangChain (async o sync)."""
    fn = getattr(tool, "coroutine", None)
    if fn is not None:
        return await fn(**kwargs)
    fn = getattr(tool, "func", None)
    if fn is not None:
        res = fn(**kwargs)
        return await res if asyncio.iscoroutine(res) else res
    return await tool.ainvoke(kwargs)


async def _cleanup(db):
    """Borra TODO lo del teléfono de prueba: turnos, paciente(s) (incluye menores -M) y estado."""
    try:
        from services.conversation_state import reset as _reset
        await _reset(TEST_TENANT, TEST_PHONE)
    except Exception:
        pass
    try:
        rows = await db.pool.fetch(
            "SELECT id FROM patients WHERE tenant_id = $1 "
            "AND (phone_number = $2 OR phone_number LIKE $2 || '-M%')",
            TEST_TENANT, TEST_PHONE,
        )
        ids = [r["id"] for r in rows]
        if ids:
            await db.pool.execute("DELETE FROM appointments WHERE patient_id = ANY($1::int[])", ids)
            await db.pool.execute("DELETE FROM patients WHERE id = ANY($1::int[])", ids)
    except Exception as e:
        print(f"   ⚠️  limpieza parcial (revisar a mano el teléfono {TEST_PHONE}): {e}")


# ----------------------------------------------------------------------------
# ESCENARIO A — Fix #3: el hijo NO se bloquea como "duplicado"; el self SÍ.
# ----------------------------------------------------------------------------
async def scenario_hijo_no_duplicado(db, book_appointment, set_ctx):
    """La madre ya se agendó a sí misma (estado BOOKED). Ahora pide turno para su hijo.
    ANTES: el guard anti-duplicado bloqueaba al hijo. AHORA: lo deja pasar (fix #3),
    y sigue bloqueando un re-agendamiento de la PROPIA madre."""
    from services.conversation_state import set_state, reset

    results = []
    await reset(TEST_TENANT, TEST_PHONE)
    set_ctx(TEST_TENANT, TEST_PHONE)

    # Simular "la madre ya tiene un turno confirmado en esta charla".
    await set_state(TEST_TENANT, TEST_PHONE, "BOOKED", last_booked_appointment_id=999999999)

    # A.1 — HIJO: debe PASAR el guard (fecha inválida a propósito → falla después, sin crear nada).
    r_minor = await _invoke_tool(
        book_appointment,
        date_time="__fecha_invalida_e2e__",
        treatment_reason="consulta",
        is_minor=True,
        first_name="TestHijoE2E",
    )
    passed_minor = "DUPLICATE_BOOKING" not in str(r_minor)
    results.append((
        "hijo NO se bloquea como duplicado (fix #3)",
        passed_minor,
        f"respuesta: {str(r_minor)[:120]}",
    ))

    # A.2 — SELF (control): re-agendarse la madre SÍ debe seguir bloqueado.
    await set_state(TEST_TENANT, TEST_PHONE, "BOOKED", last_booked_appointment_id=999999999)
    r_self = await _invoke_tool(
        book_appointment,
        date_time="__fecha_invalida_e2e__",
        treatment_reason="consulta",
    )
    passed_self = "DUPLICATE_BOOKING" in str(r_self)
    results.append((
        "self (madre) SÍ se bloquea si intenta re-agendarse (control)",
        passed_self,
        f"respuesta: {str(r_self)[:120]}",
    ))

    await reset(TEST_TENANT, TEST_PHONE)
    return results


# ----------------------------------------------------------------------------
# ESCENARIO C — [DADOS]: la lógica de archivos-sin-texto y la red anti-basura.
# (Espejo de la lógica de buffer_task.py — determinista, sin BD.)
# ----------------------------------------------------------------------------
async def scenario_dados(db, book_appointment, set_ctx):
    def _is_files_only(raw_text: str, has_media: bool) -> bool:
        return bool(has_media) and len((raw_text or "").strip()) < 3

    def _is_garbage(text: str) -> bool:
        return (text or "").strip().upper() in _GARBAGE_PLACEHOLDERS

    results = [
        ("archivos sin texto → corto-circuito (no invoca al modelo)",
         _is_files_only("", True) is True, "msg vacío + media"),
        ("archivo CON texto real → NO corto-circuito (va al modelo)",
         _is_files_only("hola quiero un turno", True) is False, "media + texto"),
        ("'[DADOS]' → lo caza la red de seguridad",
         _is_garbage("[DADOS]") is True, "placeholder basura"),
        ("respuesta real ('Hola!') → NO la toca la red",
         _is_garbage("Hola!") is False, "texto legítimo"),
        ("'[SILENCIO]' (marcador legítimo) → NO lo toca la red",
         _is_garbage("[SILENCIO]") is False, "no debe suprimirse"),
    ]
    return results


SCENARIOS = {
    "hijo": scenario_hijo_no_duplicado,
    "dados": scenario_dados,
}


async def main() -> int:
    ap = argparse.ArgumentParser(description="Simulador E2E del agente (banco de agendado)")
    ap.add_argument("--scenario", default=None, help="Correr uno solo: hijo | dados")
    args = ap.parse_args()

    if TEST_TENANT != 1:
        print(f"ℹ️  Tenant de prueba: {TEST_TENANT}")
    dsn = os.getenv("POSTGRES_DSN") or os.getenv("DATABASE_URL")
    if not dsn:
        print("ERROR: falta POSTGRES_DSN en el entorno.", file=sys.stderr)
        return 2

    # Importar el módulo real (esto arma DENTAL_TOOLS y las herramientas).
    try:
        from db import db
        from main import book_appointment, current_tenant_id, current_customer_phone
    except Exception as e:
        print(f"ERROR importando el agente real: {e}", file=sys.stderr)
        return 2

    def set_ctx(tid, phone):
        current_tenant_id.set(tid)
        current_customer_phone.set(phone)

    await db.connect()
    if db.pool is None:
        print("ERROR: no se pudo conectar a la base (db.pool is None).", file=sys.stderr)
        return 2

    print("=" * 72)
    print(f"SIMULADOR E2E (banco de agendado) — tenant {TEST_TENANT} — teléfono de prueba {TEST_PHONE}")
    print("=" * 72)

    to_run = SCENARIOS if not args.scenario else {args.scenario: SCENARIOS[args.scenario]}
    all_results = []
    try:
        for name, fn in to_run.items():
            print(f"\n▶ Escenario: {name}")
            try:
                res = await fn(db, book_appointment, set_ctx)
            except Exception as e:
                import traceback
                print(f"   💥 el escenario reventó: {e}")
                print(traceback.format_exc())
                res = [(f"escenario {name}", False, f"excepción: {e}")]
            for titulo, ok, detalle in res:
                mark = "PASA " if ok else "FALLA"
                print(f"   [{mark}] {titulo}")
                if not ok:
                    print(f"          → {detalle}")
                all_results.append(ok)
    finally:
        await _cleanup(db)
        await db.disconnect()

    passed = sum(1 for r in all_results if r)
    total = len(all_results)
    print("\n" + "=" * 72)
    print(f"RESULTADO E2E: {passed}/{total} chequeos PASAN")
    print("=" * 72)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
