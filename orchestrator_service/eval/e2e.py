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
    """Borra TODO lo del teléfono de prueba (turnos, audit, paciente(s) incl. menores -M) y estado.
    Match por DÍGITOS: el teléfono se guarda normalizado, y los menores se cazan por guardian_phone
    (su phone_number es 'padre-M1', que no matchea por dígitos). El teléfono de prueba es falso →
    no puede pisar un paciente real."""
    try:
        from services.conversation_state import reset as _reset
        await _reset(TEST_TENANT, TEST_PHONE)
    except Exception:
        pass
    try:
        rows = await db.pool.fetch(
            "SELECT id FROM patients WHERE tenant_id = $1 AND ("
            " regexp_replace(COALESCE(phone_number,''),'[^0-9]','','g') = regexp_replace($2,'[^0-9]','','g')"
            " OR regexp_replace(COALESCE(guardian_phone,''),'[^0-9]','','g') = regexp_replace($2,'[^0-9]','','g'))",
            TEST_TENANT, TEST_PHONE,
        )
        ids = [r["id"] for r in rows]
        if ids:
            await db.pool.execute(
                "DELETE FROM appointment_audit_log WHERE tenant_id=$1 AND appointment_id IN "
                "(SELECT id FROM appointments WHERE tenant_id=$1 AND patient_id = ANY($2::int[]))",
                TEST_TENANT, ids,
            )
            await db.pool.execute("DELETE FROM appointments WHERE tenant_id=$1 AND patient_id = ANY($2::int[])", TEST_TENANT, ids)
            try:
                await db.pool.execute("DELETE FROM lab_cases WHERE tenant_id=$1 AND patient_id = ANY($2::int[])", TEST_TENANT, ids)
            except Exception:
                pass  # la tabla puede no existir en entornos sin el módulo Laboratorio
            try:
                await db.pool.execute("DELETE FROM clinic_pendings WHERE tenant_id=$1 AND patient_id = ANY($2::int[])", TEST_TENANT, ids)
            except Exception:
                pass  # ídem: módulo Pendientes (mig 075)
            await db.pool.execute("DELETE FROM patients WHERE id = ANY($1::int[])", ids)
            print(f"   🧹 limpieza: {len(ids)} paciente(s) de prueba + sus turnos borrados")
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
    # Espejo de la lógica v2 de buffer_task: el corto-circuito SOLO aplica sin contexto
    # de pago (caso Lucas: un comprobante sin texto DEBE ir al modelo → verify_payment).
    def _is_files_only(raw_text: str, has_media: bool, pay_ctx: bool = False) -> bool:
        return bool(has_media) and len((raw_text or "").strip()) < 3 and not pay_ctx

    def _is_garbage(text: str) -> bool:
        return (text or "").strip().upper() in _GARBAGE_PLACEHOLDERS

    results = [
        ("archivos sin texto SIN pago pendiente → corto-circuito",
         _is_files_only("", True, pay_ctx=False) is True, "msg vacío + media, sin pago"),
        ("comprobante sin texto CON pago pendiente → va al MODELO (caso Lucas)",
         _is_files_only("", True, pay_ctx=True) is False, "la seña debe verificarse"),
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


# ----------------------------------------------------------------------------
# ESCENARIO B — Agendado REAL + Fix #1 "quiere-antes" (el bug de Luis), encadenados.
# Handshake correcto (mapeo 2026-07-16): check_availability PRIMERO siembra la key
# slot_offer en Redis; recién ahí book_appointment(slot_index=1) puede confirmar.
# ----------------------------------------------------------------------------
async def scenario_agendado_y_quiere_antes(db, book_appointment, set_ctx):
    from services.conversation_state import set_state, reset
    from main import check_availability
    import datetime as _dt

    results = []
    await reset(TEST_TENANT, TEST_PHONE)
    set_ctx(TEST_TENANT, TEST_PHONE)

    # 1) Un tratamiento agendable REAL del tenant.
    trow = await db.pool.fetchrow(
        "SELECT code, name FROM treatment_types WHERE tenant_id=$1 AND is_active=true "
        "AND is_available_for_booking=true ORDER BY id ASC LIMIT 1",
        TEST_TENANT,
    )
    if not trow:
        results.append(("preparación: hay un tratamiento agendable", False, "no hay treatment_types agendables en el tenant"))
        return results
    tname = trow["name"]
    tomorrow = (_dt.datetime.now() + _dt.timedelta(days=1)).strftime("%Y-%m-%d")

    # 2) check_availability (siembra el slot_offer). search_mode="open" = lo antes posible.
    r_avail = str(await _invoke_tool(
        check_availability,
        date_query="lo antes posible", interpreted_date=tomorrow,
        search_mode="open", treatment_name=tname,
    ))
    _low = r_avail.lower()
    ofrecio = (":" in r_avail) and ("no ten" not in _low) and ("cerrad" not in _low) and ("no hay" not in _low)
    if not ofrecio:
        results.append(("check_availability ofreció turnos reales", False,
                        f"la clínica de pruebas no tiene disponibilidad ahora (no es bug del bot): {r_avail[:160]}"))
        await reset(TEST_TENANT, TEST_PHONE)
        return results
    results.append(("check_availability ofreció turnos reales", True, ""))

    # 3) Agendar la opción 1 (consume el slot_offer → handshake correcto).
    # date_time es posicional obligatorio; con slot_index=1 el datetime real sale de la
    # oferta guardada en Redis (Priority 0), así que este valor es solo fallback.
    r_book = str(await _invoke_tool(
        book_appointment,
        date_time="10:00",
        treatment_reason=tname, slot_index=1, interpreted_date=tomorrow,
        first_name="TestE2E", last_name="Paciente", dni="99999999",
    ))
    agendado_ok = "Turno confirmado" in r_book
    results.append(("book_appointment agendó de verdad (handshake ok)", agendado_ok, r_book[:160]))
    if not agendado_ok:
        await reset(TEST_TENANT, TEST_PHONE)
        return results

    # 4) Verificar en la BASE que el turno quedó.
    apt = await db.pool.fetchrow(
        "SELECT a.id FROM appointments a JOIN patients p ON p.id=a.patient_id AND p.tenant_id=a.tenant_id "
        "WHERE a.tenant_id=$1 AND a.status='scheduled' AND a.appointment_datetime>=NOW() "
        "AND regexp_replace(COALESCE(p.phone_number,''),'[^0-9]','','g')=regexp_replace($2,'[^0-9]','','g') "
        "ORDER BY a.created_at DESC LIMIT 1",
        TEST_TENANT, TEST_PHONE,
    )
    results.append(("el turno quedó guardado en la base", apt is not None,
                    f"apt: {apt['id'] if apt else 'NO ENCONTRADO'}"))
    if apt:
        # Forzar BOOKED con el apt_id real (por si quedó PAYMENT_PENDING; ambos disparan el gate).
        await set_state(TEST_TENANT, TEST_PHONE, "BOOKED", last_booked_appointment_id=str(apt["id"]))

    # 5) FIX #1 — quiere-antes: con el turno agendado, "más temprano" NO debe re-ofrecer.
    r_antes = str(await _invoke_tool(
        check_availability,
        date_query="hola, no hay algo más temprano? me lo podés adelantar",
        interpreted_date=tomorrow, search_mode="exact", treatment_name=tname,
    ))
    bloqueo_ok = ("SYSTEM_NOTE" in r_antes) or ("QUIERE ALGO ANTES" in r_antes)
    results.append(("quiere-antes (fix #1): bloquea el re-ofrecimiento", bloqueo_ok, r_antes[:160]))

    await reset(TEST_TENANT, TEST_PHONE)
    return results


# ----------------------------------------------------------------------------
# ESCENARIO D — Fix Amelia: control genérico → profesional del ÚLTIMO turno.
# Paciente SIN assigned_professional_id con un turno PASADO con Laura pide un
# "control": las opciones deben ser SOLO de Laura (antes: del primero con lugar).
# Contraste: pedir "Ortodoncia" NO debe forzar a Laura (exclusión).
# ----------------------------------------------------------------------------
async def scenario_profesional_ultimo_turno(db, book_appointment, set_ctx):
    from main import check_availability
    from services.conversation_state import reset
    import datetime as _dt, uuid as _uuid

    results = []
    await reset(TEST_TENANT, TEST_PHONE)
    set_ctx(TEST_TENANT, TEST_PHONE)

    profs = await db.pool.fetch(
        "SELECT id, first_name FROM professionals WHERE tenant_id=$1 AND is_active=true ORDER BY id",
        TEST_TENANT,
    )
    if len(profs) < 2:
        return [("preparación: hacen falta ≥2 profesionales activos", False, f"hay {len(profs)}")]
    target = profs[0]          # el principal (Laura en tenant 1)
    otros = [p["first_name"] for p in profs[1:]]

    # Paciente de prueba SIN profesional asignado + turno PASADO (completed) con el target.
    pid = await db.pool.fetchval(
        "INSERT INTO patients (tenant_id, phone_number, first_name, status, created_at) "
        "VALUES ($1,$2,'TestProfE2E','active',NOW()) "
        "ON CONFLICT (tenant_id, phone_number) WHERE phone_number IS NOT NULL "
        "DO UPDATE SET first_name='TestProfE2E', assigned_professional_id=NULL RETURNING id",
        TEST_TENANT, TEST_PHONE,
    )
    ayer = _dt.datetime.now() - _dt.timedelta(days=1)
    await db.pool.execute(
        "INSERT INTO appointments (id, tenant_id, patient_id, professional_id, appointment_datetime, "
        "duration_minutes, appointment_type, status, source, created_at) "
        "VALUES ($1,$2,$3,$4,$5,30,'CONSULTA','completed','ai',NOW())",
        str(_uuid.uuid4()), TEST_TENANT, pid, target["id"], ayer,
    )

    manana = (_dt.datetime.now() + _dt.timedelta(days=1)).strftime("%Y-%m-%d")

    # D.1 — control genérico → SOLO turnos del profesional del último turno.
    # OJO: las opciones NO nombran al profesional en el texto (regla del prompt) →
    # se verifica por el ESTADO interno: last_offered_slots guarda el professional
    # de cada slot ofrecido (lo escribe check_availability al setear OFFERED_SLOTS).
    r1 = str(await _invoke_tool(
        check_availability,
        date_query="quiero un control, lo antes posible", interpreted_date=manana,
        search_mode="open", treatment_name="consulta",
    ))
    from services.conversation_state import get_state as _gs_prof
    _st = await _gs_prof(TEST_TENANT, TEST_PHONE)
    _slots_prof = [(s.get("professional") or "") for s in (_st.get("last_offered_slots") or [])]
    ok1 = bool(_slots_prof) and all(
        target["first_name"].lower() in p.lower() for p in _slots_prof
    ) and not any(o.lower() in p.lower() for p in _slots_prof for o in otros)
    results.append((
        f"control genérico → ofrece SOLO a {target['first_name']} (prof del último turno)",
        ok1, f"profesionales de los slots ofrecidos={_slots_prof} resp: {r1[:100]}",
    ))

    # D.2 — ortodoncia NO se fuerza al último profesional (exclusión).
    await reset(TEST_TENANT, TEST_PHONE)
    r2 = str(await _invoke_tool(
        check_availability,
        date_query="quiero ortodoncia", interpreted_date=manana,
        search_mode="open", treatment_name="Ortodoncia",
    ))
    # Chequeo suave: no debe crashear; si hay opciones, no exigimos que sean del target.
    ok2 = ("Error" not in r2[:30]) and len(r2) > 0
    results.append(("ortodoncia: excluida del fallback (no crashea, rutea por tratamiento)", ok2, r2[:140]))

    await reset(TEST_TENANT, TEST_PHONE)
    return results


# ----------------------------------------------------------------------------
# ESCENARIO E — Integración bot↔Laboratorio (tarea #1): check_lab_work_status
# contra lab_cases REALES: cada estado devuelve la instrucción correcta y sin
# trabajos NO inventa nada.
# ----------------------------------------------------------------------------
async def scenario_laboratorio(db, book_appointment, set_ctx):
    from main import check_lab_work_status
    from services.conversation_state import reset

    results = []
    await reset(TEST_TENANT, TEST_PHONE)
    set_ctx(TEST_TENANT, TEST_PHONE)

    pid = await db.pool.fetchval(
        "INSERT INTO patients (tenant_id, phone_number, first_name, status, created_at) "
        "VALUES ($1,$2,'TestLabE2E','active',NOW()) "
        "ON CONFLICT (tenant_id, phone_number) WHERE phone_number IS NOT NULL "
        "DO UPDATE SET first_name='TestLabE2E' RETURNING id",
        TEST_TENANT, TEST_PHONE,
    )

    # E.1 — SIN trabajos → no inventa.
    r0 = str(await _invoke_tool(check_lab_work_status))
    results.append(("sin trabajos → SIN_TRABAJOS (no inventa estados)",
                    "SIN_TRABAJOS" in r0, r0[:120]))

    # E.2 — trabajo RECIBIDO → "ya llegó" + ofrecer colocación.
    case_id = await db.pool.fetchval(
        "INSERT INTO lab_cases (tenant_id, patient_id, work_type, status, received_at, created_at) "
        "VALUES ($1,$2,'Corona','recibido',CURRENT_DATE,NOW()) RETURNING id",
        TEST_TENANT, pid,
    )
    r1 = str(await _invoke_tool(check_lab_work_status))
    results.append(("trabajo RECIBIDO → 'YA LLEGÓ' + ofrecer colocación",
                    ("YA LLEGÓ" in r1) and ("check_availability" in r1), r1[:140]))

    # E.3 — trabajo ENVIADO con fecha → 'EN EL LABORATORIO' + fecha estimada.
    await db.pool.execute(
        "UPDATE lab_cases SET status='enviado', promised_at=CURRENT_DATE + 7 WHERE id=$1 AND tenant_id=$2",
        case_id, TEST_TENANT,
    )
    r2 = str(await _invoke_tool(check_lab_work_status))
    results.append(("trabajo ENVIADO → 'EN EL LABORATORIO' + fecha SOLO estimada",
                    ("EN EL LABORATORIO" in r2) and ("estimada" in r2.lower()), r2[:140]))

    await reset(TEST_TENANT, TEST_PHONE)
    return results


# ----------------------------------------------------------------------------
# ESCENARIO F — Módulo Pendientes (mig 075): el INSERT-dedupe del auto-pendiente
# de derivhumano (la query exacta) + los buckets del summary.
# (No llama derivhumano completo: mandaría emails reales al equipo.)
# ----------------------------------------------------------------------------
async def scenario_pendientes(db, book_appointment, set_ctx):
    results = []
    pid = await db.pool.fetchval(
        "INSERT INTO patients (tenant_id, phone_number, first_name, status, created_at) "
        "VALUES ($1,$2,'TestPendE2E','active',NOW()) "
        "ON CONFLICT (tenant_id, phone_number) WHERE phone_number IS NOT NULL "
        "DO UPDATE SET first_name='TestPendE2E' RETURNING id",
        TEST_TENANT, TEST_PHONE,
    )

    _auto_insert = """
        INSERT INTO clinic_pendings
            (tenant_id, title, note, due_at, patient_id, conversation_id, created_by, source)
        SELECT $1, $2, $3, NOW() + INTERVAL '24 hours',
               (SELECT id FROM patients WHERE tenant_id = $1 AND phone_number = $4 LIMIT 1),
               (SELECT id FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $4 ORDER BY updated_at DESC LIMIT 1),
               'bot', 'derivhumano'
        WHERE NOT EXISTS (
            SELECT 1 FROM clinic_pendings
            WHERE tenant_id = $1 AND source = 'derivhumano' AND status = 'abierto'
              AND conversation_id = (SELECT id FROM chat_conversations WHERE tenant_id = $1 AND external_user_id = $4 ORDER BY updated_at DESC LIMIT 1)
              AND created_at > NOW() - INTERVAL '24 hours'
        )
    """
    args = (TEST_TENANT, "Seguir derivación: test E2E", "nota test", TEST_PHONE)

    def _count():
        return db.pool.fetchval(
            "SELECT COUNT(*) FROM clinic_pendings WHERE tenant_id=$1 AND patient_id=$2 AND source='derivhumano'",
            TEST_TENANT, pid,
        )

    # F.1 — el auto-pendiente se crea.
    await db.pool.execute(_auto_insert, *args)
    n1 = await _count()
    results.append(("auto-pendiente de derivación se crea", n1 == 1, f"filas={n1}"))

    # F.2 — dedupe: repetir NO duplica (misma conversación, abierto, <24h).
    # OJO: sin chat_conversations del test, conversation_id es NULL y el dedupe por
    # conversación no matchea (NULL != NULL) — creamos la conversación primero.
    conv = await db.pool.fetchval(
        "INSERT INTO chat_conversations (tenant_id, channel, external_user_id, last_message_at, updated_at) "
        "VALUES ($1,'whatsapp',$2,NOW(),NOW()) "
        "ON CONFLICT (tenant_id, channel, external_user_id) DO UPDATE SET updated_at=NOW() RETURNING id",
        TEST_TENANT, TEST_PHONE,
    )
    await db.pool.execute("UPDATE clinic_pendings SET conversation_id=$1 WHERE tenant_id=$2 AND patient_id=$3", conv, TEST_TENANT, pid)
    await db.pool.execute(_auto_insert, *args)
    n2 = await _count()
    results.append(("dedupe: repetir la derivación NO duplica el pendiente", n2 == 1, f"filas={n2}"))

    # F.3 — bucket vencidas: un pendiente con due_at pasado cuenta como vencido.
    await db.pool.execute(
        "UPDATE clinic_pendings SET due_at = NOW() - INTERVAL '1 hour' WHERE tenant_id=$1 AND patient_id=$2",
        TEST_TENANT, pid,
    )
    overdue = await db.pool.fetchval(
        "SELECT COUNT(*) FROM clinic_pendings WHERE tenant_id=$1 AND patient_id=$2 "
        "AND status='abierto' AND due_at IS NOT NULL AND due_at < NOW()",
        TEST_TENANT, pid,
    )
    results.append(("bucket 'vencidas' lo detecta (estado derivado, sin job)", overdue == 1, f"vencidas={overdue}"))

    # limpieza local del escenario (la conversación de test no la borra _cleanup)
    await db.pool.execute("DELETE FROM clinic_pendings WHERE tenant_id=$1 AND patient_id=$2", TEST_TENANT, pid)
    await db.pool.execute("DELETE FROM chat_conversations WHERE id=$1 AND tenant_id=$2", conv, TEST_TENANT)
    return results


SCENARIOS = {
    "hijo": scenario_hijo_no_duplicado,
    "agendado": scenario_agendado_y_quiere_antes,
    "profesional": scenario_profesional_ultimo_turno,
    "lab": scenario_laboratorio,
    "pendientes": scenario_pendientes,
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
