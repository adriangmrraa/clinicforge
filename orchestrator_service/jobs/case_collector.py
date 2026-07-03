"""
Colector de Casos a Revisar — job diario (jobs/case_collector.py).

Detecta por SENALES DETERMINISTAS (sin IA, cero tokens) las conversaciones donde
el bot fallo o quedo trabado, las persiste en cases_to_review (idempotente por
dia) y manda un resumen por mail al equipo (dueno del producto). NO agrega nada
visible al panel de la clinica: el cliente no lo ve.

Senales de la fase 1:
  - agent_error : chat_conversations.last_agent_error_at  (el bot se cayo)
  - derivation  : chat_conversations.last_derivhumano_at  (el bot derivo a humano)
  - loop        : el asistente repitio el MISMO mensaje 3+ veces en 24h

Programacion: diario a las 08:00 ART (CASE_COLLECTOR_HOUR). Con
CASE_COLLECTOR_RUN_ON_START=1 corre una vez ~30s despues de arrancar, util para
probar en pruebas sin esperar a la hora.

Fase 2 (futura): sumar clasificacion con IA sobre los candidatos para casos
sutiles (frustracion, obra social mal resuelta, confusion).
"""
import os
import html as _html
import asyncio
import logging
from datetime import datetime, time, timedelta

logger = logging.getLogger("case_collector")

try:
    from zoneinfo import ZoneInfo

    ARG_TZ = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:  # pragma: no cover
    from datetime import timezone

    ARG_TZ = timezone(timedelta(hours=-3))

REPORT_EMAIL = os.getenv("COLLECTOR_REPORT_EMAIL", "contact@codexyoficial.com")
RUN_HOUR = int(os.getenv("CASE_COLLECTOR_HOUR", "8"))

CATEGORY_LABELS = {
    "agent_error": "El bot se cayó / no pudo responder",
    "derivation": "El bot derivó a un humano",
    "loop": "El bot repitió el mismo mensaje (loop)",
}
SEVERITY_COLORS = {"high": "#f87171", "medium": "#fbbf24", "low": "#9ca3af"}


# ---------------------------------------------------------------------------
# Loop / scheduling
# ---------------------------------------------------------------------------


async def case_collector_loop(pool):
    """Loop diario: espera hasta la hora objetivo (ART), corre el colector, repite."""
    # Diagnóstico de arranque: dice en UNA línea si el mail puede salir (SMTP configurado)
    # y a qué casilla va, para no tener que bucear en logs cuando "no llega el mail".
    _smtp_ok = bool(os.getenv("SMTP_HOST")) and bool(os.getenv("SMTP_USER"))
    logger.info(
        "case_collector: destino=%s | SMTP %s"
        % (
            REPORT_EMAIL,
            "CONFIGURADO ✅"
            if _smtp_ok
            else "FALTA ❌ — agregá SMTP_HOST/SMTP_USER/SMTP_PASS/SMTP_SENDER al servicio orchestrator",
        )
    )

    # Mail de MUESTRA (datos ficticios): valida SMTP + formato sin esperar un caso real.
    if os.getenv("CASE_COLLECTOR_TEST_EMAIL") in ("1", "true", "True", "TRUE"):
        await asyncio.sleep(20)
        try:
            await _send_test_report()
        except Exception as e:
            logger.error(f"case_collector_test_email_error: {e}")

    if os.getenv("CASE_COLLECTOR_RUN_ON_START") in ("1", "true", "True"):
        await asyncio.sleep(30)
        try:
            await run_case_collector_once(pool)
        except Exception as e:
            logger.error(f"case_collector_run_on_start_error: {e}")

    while True:
        try:
            secs = _seconds_until(RUN_HOUR)
            logger.info(f"case_collector: próxima corrida en {secs / 3600:.1f} h")
            await asyncio.sleep(secs)
            await run_case_collector_once(pool)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"case_collector_loop_error: {e}")
            await asyncio.sleep(3600)  # reintenta en 1h ante error inesperado


def _seconds_until(hour: int) -> float:
    now = datetime.now(ARG_TZ)
    target = datetime.combine(now.date(), time(hour, 0, 0), tzinfo=ARG_TZ)
    if now >= target:
        target = target + timedelta(days=1)
    return (target - now).total_seconds()


# ---------------------------------------------------------------------------
# Colecta
# ---------------------------------------------------------------------------


async def run_case_collector_once(pool) -> int:
    """Una pasada: detecta + persiste + manda el mail. Devuelve # de casos nuevos."""
    tenants = await pool.fetch("SELECT id, clinic_name FROM tenants ORDER BY id ASC")
    new_by_clinic = {}  # clinic_name -> list[case dict]
    total_new = 0
    for t in tenants:
        tid = t["id"]
        try:
            new_cases = await _collect_tenant(pool, tid)
        except Exception as e:
            logger.error(f"case_collector_tenant_{tid}_error: {e}")
            continue
        if new_cases:
            new_by_clinic[t["clinic_name"] or f"Clínica {tid}"] = new_cases
            total_new += len(new_cases)

    if total_new == 0:
        logger.info("case_collector: sin casos nuevos, no se manda mail.")
        return 0

    try:
        await _send_report(new_by_clinic, total_new)
    except Exception as e:
        logger.error(f"case_collector_report_error: {e}")
    return total_new


async def _collect_tenant(pool, tenant_id):
    """Detecta señales para un tenant, persiste con idempotencia y devuelve los NUEVOS."""
    candidates = []

    async with pool.acquire() as conn:
        # 1) agent_error — la conversación quedó marcada por un fallo del bot
        rows = await conn.fetch(
            """SELECT id, external_user_id, display_name, agent_error_reason
               FROM chat_conversations
               WHERE tenant_id = $1
                 AND last_agent_error_at >= NOW() - INTERVAL '24 hours'""",
            tenant_id,
        )
        for r in rows:
            candidates.append(
                {
                    "conversation_id": r["id"],
                    "phone": r["external_user_id"],
                    "name": r["display_name"],
                    "category": "agent_error",
                    "reason": (
                        r["agent_error_reason"]
                        or "El asistente tuvo un error técnico y no pudo responder."
                    )[:500],
                    "severity": "high",
                }
            )

        # 2) derivation — el bot derivó a un humano
        rows = await conn.fetch(
            """SELECT id, external_user_id, display_name
               FROM chat_conversations
               WHERE tenant_id = $1
                 AND last_derivhumano_at >= NOW() - INTERVAL '24 hours'""",
            tenant_id,
        )
        for r in rows:
            candidates.append(
                {
                    "conversation_id": r["id"],
                    "phone": r["external_user_id"],
                    "name": r["display_name"],
                    "category": "derivation",
                    "reason": "El bot derivó la conversación a un humano.",
                    "severity": "medium",
                }
            )

        # 3) loop — el asistente repitió el MISMO mensaje 3+ veces en 24h
        rows = await conn.fetch(
            """SELECT cm.conversation_id, cc.external_user_id, cc.display_name,
                      COUNT(*) AS n
               FROM chat_messages cm
               JOIN chat_conversations cc ON cc.id = cm.conversation_id
               WHERE cm.tenant_id = $1 AND cm.role = 'assistant'
                 AND cm.created_at >= NOW() - INTERVAL '24 hours'
                 AND cm.conversation_id IS NOT NULL
                 AND cm.content IS NOT NULL AND length(trim(cm.content)) > 0
               GROUP BY cm.conversation_id, cc.external_user_id, cc.display_name, cm.content
               HAVING COUNT(*) >= 3
               ORDER BY COUNT(*) DESC""",
            tenant_id,
        )
        for r in rows:
            candidates.append(
                {
                    "conversation_id": r["conversation_id"],
                    "phone": r["external_user_id"],
                    "name": r["display_name"],
                    "category": "loop",
                    "reason": f"El asistente repitió el mismo mensaje {r['n']} veces.",
                    "severity": "medium",
                }
            )

        # Persistir (idempotente por día) y quedarse con los realmente NUEVOS
        inserted = []
        for c in candidates:
            row = await conn.fetchrow(
                """INSERT INTO cases_to_review
                     (tenant_id, conversation_id, phone_number, patient_name,
                      category, reason, severity)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (tenant_id, conversation_id, category, incident_date)
                   DO NOTHING
                   RETURNING id""",
                tenant_id,
                c["conversation_id"],
                c["phone"],
                c["name"],
                c["category"],
                c["reason"],
                c["severity"],
            )
            if not row:
                continue  # ya existía un caso igual hoy (idempotencia)
            c["id"] = row["id"]
            c["snippet"] = await _fetch_snippet(conn, tenant_id, c["conversation_id"])
            if c["snippet"]:
                await conn.execute(
                    "UPDATE cases_to_review SET snippet = $1 WHERE id = $2",
                    c["snippet"],
                    c["id"],
                )
            inserted.append(c)

    return inserted


async def _fetch_snippet(conn, tenant_id, conversation_id, limit: int = 6) -> str:
    """Últimos N mensajes de la conversación, compactos, para incrustar en el mail."""
    if conversation_id is None:
        return ""
    rows = await conn.fetch(
        """SELECT role, content FROM chat_messages
           WHERE conversation_id = $1 AND tenant_id = $2
           ORDER BY created_at DESC LIMIT $3""",
        conversation_id,
        tenant_id,
        limit,
    )
    label = {
        "user": "PACIENTE",
        "assistant": "PAULA",
        "tool": "TOOL",
        "system": "SISTEMA",
    }
    lines = []
    for r in reversed(rows):
        who = label.get(r["role"], (r["role"] or "?").upper())
        content = (r["content"] or "").strip().replace("\n", " ")
        if len(content) > 200:
            content = content[:200] + "…"
        lines.append(f"{who}: {content}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Reporte por mail
# ---------------------------------------------------------------------------


async def _send_test_report():
    """Mail de MUESTRA con casos ficticios (para validar SMTP + formato en pruebas)."""
    sample = {
        "Clínica de PRUEBA (mail de ejemplo)": [
            {
                "category": "agent_error",
                "severity": "high",
                "name": "Paciente Ejemplo",
                "phone": "+5490000000000",
                "reason": "El asistente tuvo un error técnico y no pudo responder.",
                "snippet": "PACIENTE: hola, tengo un dolor fuerte\nPAULA: (sin respuesta por un error)",
            },
            {
                "category": "derivation",
                "severity": "medium",
                "name": "Otro Paciente",
                "phone": "+5490000000001",
                "reason": "El bot derivó la conversación a un humano.",
                "snippet": "PACIENTE: ¿llegó mi autorización?\nPAULA: Dejame que lo vea con el equipo y te confirmo.",
            },
            {
                "category": "loop",
                "severity": "medium",
                "name": "Paciente Repetido",
                "phone": "+5490000000002",
                "reason": "El asistente repitió el mismo mensaje 4 veces.",
                "snippet": "PAULA: ¿Para qué día querés el turno?\nPACIENTE: cualquiera\nPAULA: ¿Para qué día querés el turno?",
            },
        ]
    }
    total = sum(len(v) for v in sample.values())
    await _send_report(
        sample, total, subject="🧪 [PRUEBA] Colector de casos — mail de ejemplo"
    )
    logger.info("case_collector: mail de MUESTRA enviado (CASE_COLLECTOR_TEST_EMAIL).")


async def _send_report(new_by_clinic, total_new, subject=None):
    from email_service import EmailService

    today = datetime.now(ARG_TZ).strftime("%d/%m/%Y")
    if subject is None:
        subject = f"🔎 Casos a revisar ({total_new}) — {today}"
    html = _build_html(new_by_clinic, total_new, today)
    ok = await asyncio.to_thread(
        EmailService().send_html, REPORT_EMAIL, subject, html
    )
    if ok:
        logger.info(
            f"case_collector: mail enviado a {REPORT_EMAIL} con {total_new} caso(s)."
        )
    else:
        logger.warning("case_collector: no se pudo enviar el mail (¿SMTP configurado?).")


def _build_html(new_by_clinic, total_new, today) -> str:
    blocks = []
    for clinic, cases in new_by_clinic.items():
        rows_html = []
        for c in cases:
            color = SEVERITY_COLORS.get(c.get("severity", "medium"), "#9ca3af")
            cat = CATEGORY_LABELS.get(c["category"], c["category"])
            name = _html.escape(c.get("name") or "Sin nombre")
            phone = _html.escape(c.get("phone") or "—")
            reason = _html.escape(c.get("reason") or "")
            snippet = _html.escape(c.get("snippet") or "").replace("\n", "<br>")
            snippet_block = (
                f'<div style="background:#0d1117;border-radius:6px;padding:10px 12px;'
                f'margin-top:8px;font-family:monospace;font-size:12px;color:#8b949e;'
                f'white-space:pre-wrap;">{snippet}</div>'
                if snippet
                else ""
            )
            rows_html.append(
                f"""
              <div style="background:rgba(255,255,255,0.05);border-left:3px solid {color};
                          border-radius:8px;padding:14px 16px;margin-bottom:12px;">
                <div style="font-size:13px;color:{color};font-weight:bold;margin-bottom:4px;">{cat}</div>
                <div style="color:#e6edf3;font-size:14px;"><strong>{name}</strong>
                     <span style="color:#8b949e;">· {phone}</span></div>
                <div style="color:#c9d1d9;font-size:13px;margin-top:4px;">{reason}</div>
                {snippet_block}
              </div>"""
            )
        blocks.append(
            f"""
          <h2 style="color:#e6edf3;font-size:16px;margin:24px 0 12px;
                     border-bottom:1px solid #21262d;padding-bottom:6px;">
            🦷 {_html.escape(clinic)}
            <span style="color:#8b949e;font-weight:normal;">({len(cases)})</span>
          </h2>
          {''.join(rows_html)}"""
        )

    return f"""
    <div style="font-family:-apple-system,'Segoe UI',Roboto,sans-serif;max-width:640px;
                margin:0 auto;background:#161b22;color:#e6edf3;padding:24px;border-radius:12px;">
      <div style="text-align:center;margin-bottom:16px;">
        <h1 style="font-size:20px;margin:0;color:#fff;">🔎 Casos a revisar</h1>
        <p style="color:#8b949e;font-size:13px;margin:6px 0 0;">{today} · {total_new} caso(s) nuevo(s)</p>
      </div>
      {''.join(blocks)}
      <p style="color:#6b7280;font-size:11px;text-align:center;margin-top:24px;
                border-top:1px solid #21262d;padding-top:14px;">
        Reporte interno automático del colector de casos. No es visible para la clínica.
      </p>
    </div>"""
