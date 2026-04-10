"""
lead_recovery.py — 3-Touch Intelligent Lead Recovery within 24h free window.

Runs every 15 minutes. For each active tenant with the lead_meta_no_booking
rule enabled, detects leads who showed interest but didn't book, and sends
up to 3 personalized follow-up messages.

Touch 1 (2h): OpenAI analyzes conversation → warm message with real slot
Touch 2 (10h): Brief/humor follow-up
Touch 3 (18h): Soft closing message

All messages are persisted in chat_messages (via ResponseSender) so the
LLM has full context if the lead replies.
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta, date, timezone
from typing import Dict, Any, Optional, List

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

from .scheduler import scheduler

logger = logging.getLogger(__name__)

# Trigger types for automation_logs
TRIGGER_TYPES = {
    1: "lead_recovery_touch1",
    2: "lead_recovery_touch2",
    3: "lead_recovery_touch3",
}


async def check_lead_recovery():
    """Main entry point — runs every 15 minutes."""
    try:
        from db import db
        if not db.pool:
            return

        # Load ALL active tenant configs in one query
        rules = await db.pool.fetch("""
            SELECT ar.tenant_id, ar.condition_json, ar.send_hour_min, ar.send_hour_max,
                   t.clinic_name, t.timezone
            FROM automation_rules ar
            JOIN tenants t ON t.id = ar.tenant_id
            WHERE ar.trigger_type = 'lead_meta_no_booking'
              AND ar.is_active = true
        """)

        if not rules:
            return

        for rule in rules:
            try:
                await _process_tenant(db.pool, dict(rule))
            except Exception as e:
                logger.error(f"Lead recovery error tenant {rule['tenant_id']}: {e}")

    except Exception as e:
        logger.error(f"check_lead_recovery global error: {e}")


async def _process_tenant(pool, rule: Dict[str, Any]):
    """Process all 3 touch levels for one tenant."""
    tenant_id = rule["tenant_id"]

    # Parse config
    config = rule.get("condition_json") or {}
    if isinstance(config, str):
        config = json.loads(config)

    delay_t1 = config.get("delay_touch1_minutes", 120)
    delay_t2 = config.get("delay_touch2_minutes", 480)
    delay_t3 = config.get("delay_touch3_minutes", 480)
    hour_min = rule.get("send_hour_min") or config.get("send_hour_min", 8)
    hour_max = rule.get("send_hour_max") or config.get("send_hour_max", 20)

    # Business hours gate (tenant timezone)
    tz_str = rule.get("timezone") or "America/Argentina/Buenos_Aires"
    try:
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = ZoneInfo("America/Argentina/Buenos_Aires")

    now_local = datetime.now(tz)
    if now_local.hour < hour_min or now_local.hour >= hour_max:
        return  # Outside business hours — retry next cycle

    now_utc = datetime.now(timezone.utc)

    # Process each touch level
    for touch_number, delay_minutes in [(1, delay_t1), (2, delay_t2), (3, delay_t3)]:
        try:
            candidates = await _get_candidates(pool, tenant_id, touch_number, delay_minutes, now_utc)

            # High-ticket leads first
            candidates = await _prioritize_high_ticket(pool, tenant_id, candidates)

            for cand in candidates:
                try:
                    await _process_candidate(pool, cand, touch_number, rule, now_utc)
                except Exception as e:
                    logger.error(
                        f"Lead recovery T{touch_number} error {cand.get('phone', '?')}: {e}"
                    )
        except Exception as e:
            logger.error(f"Lead recovery T{touch_number} query error tenant {tenant_id}: {e}")


async def _get_candidates(pool, tenant_id: int, touch_number: int, delay_minutes: int, now_utc) -> List[Dict]:
    """Get eligible candidates for the given touch level."""

    if touch_number == 1:
        # Touch 1: based on last_user_message_at, recovery_touch_count = 0
        rows = await pool.fetch("""
            SELECT
                c.id AS conversation_id,
                c.tenant_id,
                c.external_user_id AS phone,
                c.channel,
                c.provider,
                c.external_account_id,
                c.external_chatwoot_id,
                c.last_user_message_at,
                c.recovery_touch_count,
                c.last_recovery_at
            FROM chat_conversations c
            WHERE c.tenant_id = $1
              AND c.recovery_touch_count = 0
              AND c.no_followup = false
              AND c.last_user_message_at IS NOT NULL
              AND c.last_user_message_at <= $2 - INTERVAL '1 minute' * $3
              AND c.last_user_message_at >= $2 - INTERVAL '1 minute' * $3 - INTERVAL '30 minutes'
              AND (c.human_override_until IS NULL OR c.human_override_until < $2)
              AND $2 <= c.last_user_message_at + INTERVAL '23 hours 30 minutes'
              AND NOT EXISTS (
                  SELECT 1 FROM appointments a
                  JOIN patients p ON p.id = a.patient_id
                  WHERE p.phone_number = c.external_user_id
                    AND a.tenant_id = c.tenant_id
                    AND a.appointment_datetime > $2
              )
              AND NOT EXISTS (
                  SELECT 1 FROM automation_logs al
                  WHERE al.phone_number = c.external_user_id
                    AND al.tenant_id = c.tenant_id
                    AND al.trigger_type = 'lead_recovery_touch1'
                    AND al.triggered_at > $2 - INTERVAL '30 minutes'
              )
            ORDER BY c.last_user_message_at ASC
            LIMIT 20
        """, tenant_id, now_utc, delay_minutes)
    else:
        # Touch 2 and 3: based on last_recovery_at
        expected_touch_count = touch_number - 1
        trigger_type = TRIGGER_TYPES[touch_number]

        rows = await pool.fetch("""
            SELECT
                c.id AS conversation_id,
                c.tenant_id,
                c.external_user_id AS phone,
                c.channel,
                c.provider,
                c.external_account_id,
                c.external_chatwoot_id,
                c.last_user_message_at,
                c.recovery_touch_count,
                c.last_recovery_at
            FROM chat_conversations c
            WHERE c.tenant_id = $1
              AND c.recovery_touch_count = $4
              AND c.no_followup = false
              AND c.last_recovery_at IS NOT NULL
              AND c.last_recovery_at <= $2 - INTERVAL '1 minute' * $3
              AND (c.human_override_until IS NULL OR c.human_override_until < $2)
              AND $2 <= c.last_user_message_at + INTERVAL '23 hours 30 minutes'
              AND NOT EXISTS (
                  SELECT 1 FROM appointments a
                  JOIN patients p ON p.id = a.patient_id
                  WHERE p.phone_number = c.external_user_id
                    AND a.tenant_id = c.tenant_id
                    AND a.appointment_datetime > $2
              )
              AND NOT EXISTS (
                  SELECT 1 FROM automation_logs al
                  WHERE al.phone_number = c.external_user_id
                    AND al.tenant_id = c.tenant_id
                    AND al.trigger_type = $5
                    AND al.triggered_at > $2 - INTERVAL '30 minutes'
              )
            ORDER BY c.last_recovery_at ASC
            LIMIT 20
        """, tenant_id, now_utc, delay_minutes, expected_touch_count, trigger_type)

    return [dict(r) for r in rows]


async def _prioritize_high_ticket(pool, tenant_id: int, candidates: List[Dict]) -> List[Dict]:
    """Sort candidates so high-ticket leads come first.

    Reads the last 20 messages for each candidate, checks if any mentioned
    service matches a high-ticket treatment. This is a lightweight check.
    """
    if not candidates:
        return candidates

    # Get all high-ticket treatment names for this tenant
    ht_rows = await pool.fetch(
        "SELECT LOWER(name) as name FROM treatment_types WHERE tenant_id = $1 AND is_high_ticket = true",
        tenant_id,
    )
    if not ht_rows:
        return candidates  # No high-ticket treatments configured

    ht_names = [r["name"] for r in ht_rows]

    # For each candidate, check recent messages for high-ticket mentions
    for cand in candidates:
        cand["_is_high_ticket"] = False
        try:
            msgs = await pool.fetch(
                "SELECT content FROM chat_messages WHERE tenant_id = $1 AND phone_number = $2 ORDER BY created_at DESC LIMIT 20",
                tenant_id, cand["phone"],
            )
            all_text = " ".join(m["content"] or "" for m in msgs).lower()
            for ht_name in ht_names:
                if ht_name in all_text:
                    cand["_is_high_ticket"] = True
                    break
        except Exception:
            pass

    # Sort: high-ticket first
    candidates.sort(key=lambda c: (not c.get("_is_high_ticket", False)))
    return candidates


async def _process_candidate(pool, cand: Dict, touch_number: int, rule: Dict, now_utc):
    """Process a single candidate for the given touch."""
    tenant_id = cand["tenant_id"]
    phone = cand["phone"]
    trigger_type = TRIGGER_TYPES[touch_number]
    clinic_name = rule.get("clinic_name", "la clínica")

    # --- GATE 1: 24h window (re-check, NON-NEGOTIABLE) ---
    last_msg_at = cand["last_user_message_at"]
    if last_msg_at.tzinfo is None:
        last_msg_at = last_msg_at.replace(tzinfo=timezone.utc)
    window_end = last_msg_at + timedelta(hours=23, minutes=30)
    if now_utc > window_end:
        await _log_recovery(pool, tenant_id, phone, trigger_type, "skipped", skip_reason="24h_window_expired")
        return

    # --- GATE 2: Re-check no future appointment (race condition guard) ---
    has_appt = await pool.fetchval("""
        SELECT 1 FROM appointments a
        JOIN patients p ON p.id = a.patient_id
        WHERE p.phone_number = $1 AND a.tenant_id = $2 AND a.appointment_datetime > $3
        LIMIT 1
    """, phone, tenant_id, now_utc)
    if has_appt:
        await _log_recovery(pool, tenant_id, phone, trigger_type, "skipped", skip_reason="appointment_created")
        return

    # --- Pre-fetch lead context from Redis (best-effort) ---
    lead_ctx = {}
    try:
        from services.lead_context import get as lead_ctx_get
        lead_ctx = await lead_ctx_get(tenant_id, phone)
    except Exception:
        pass

    # --- Resolve lead name (lead_ctx first, then DB, then fallback) ---
    lead_name = await _get_lead_name(pool, tenant_id, phone, lead_ctx)

    if touch_number == 1:
        await _process_touch1(pool, cand, rule, lead_name, clinic_name, now_utc, window_end, lead_ctx)
    elif touch_number == 2:
        await _process_touch2(pool, cand, rule, lead_name, clinic_name, now_utc, lead_ctx)
    elif touch_number == 3:
        await _process_touch3(pool, cand, rule, lead_name, clinic_name, now_utc, lead_ctx)


async def _process_touch1(pool, cand, rule, lead_name, clinic_name, now_utc, window_end, lead_ctx=None):
    """Touch 1: Analyze conversation + generate message with real availability."""
    tenant_id = cand["tenant_id"]
    phone = cand["phone"]
    trigger_type = TRIGGER_TYPES[1]

    from services.lead_analysis import analyze_conversation, generate_recovery_message, get_real_availability

    # Fetch conversation history
    msg_rows = await pool.fetch(
        "SELECT role, content FROM chat_messages WHERE tenant_id = $1 AND phone_number = $2 ORDER BY created_at DESC LIMIT 20",
        tenant_id, phone,
    )
    messages = [{"role": r["role"], "content": r["content"]} for r in reversed(msg_rows)]

    if not messages:
        await _log_recovery(pool, tenant_id, phone, trigger_type, "skipped", skip_reason="no_messages")
        return

    # Lead context shortcut: skip LLM analysis when treatment is known
    analysis = None
    if lead_ctx and lead_ctx.get("treatment_name"):
        analysis = {
            "seguimiento": True,
            "servicio": lead_ctx["treatment_name"],
            "resumen": f"Interesado en {lead_ctx['treatment_name']} (from lead_ctx)",
        }
        logger.info(f"Lead recovery T1: using lead_ctx treatment={lead_ctx['treatment_name']} for {phone} (skipped LLM)")
    else:
        # Fallback: OpenAI analysis
        analysis = await analyze_conversation(pool, tenant_id, phone, messages)

    if not analysis.get("seguimiento"):
        await _log_recovery(pool, tenant_id, phone, trigger_type, "skipped", skip_reason="ai_no_seguimiento")
        return

    servicio = analysis.get("servicio", "")

    # Real availability
    avail_text = await get_real_availability(pool, tenant_id, servicio or None)

    # Generate message
    context = {
        "lead_name": lead_name,
        "servicio": servicio,
        "clinic_name": clinic_name,
        "availability_text": avail_text,
    }
    message = await generate_recovery_message(pool, tenant_id, 1, context)
    if not message:
        await _log_recovery(pool, tenant_id, phone, trigger_type, "failed", error_details="message_generation_failed")
        return

    # Send
    sent = await _send_recovery_message(pool, cand, message, tenant_id)
    if not sent:
        await _log_recovery(pool, tenant_id, phone, trigger_type, "failed", error_details="send_failed")
        return

    # Update state
    await pool.execute(
        "UPDATE chat_conversations SET recovery_touch_count = 1, last_recovery_at = NOW() WHERE id = $1",
        cand["conversation_id"],
    )

    # Log
    await _log_recovery(pool, tenant_id, phone, trigger_type, "sent", message_preview=message[:200])

    # Telegram notification
    tz_str = rule.get("timezone") or "America/Argentina/Buenos_Aires"
    try:
        tz = ZoneInfo(tz_str)
    except Exception:
        tz = ZoneInfo("America/Argentina/Buenos_Aires")

    from services.telegram_notifier import fire_telegram_notification
    fire_telegram_notification("LEAD_RECOVERY_TOUCH1", {
        "tenant_id": tenant_id,
        "lead_name": lead_name,
        "phone": phone,
        "channel": cand.get("channel", "whatsapp"),
        "servicio": servicio or "General",
        "message_preview": message,
        "window_end": window_end.astimezone(tz).strftime("%H:%M"),
        "is_high_ticket": cand.get("_is_high_ticket", False),
    }, tenant_id)

    logger.info(f"Lead recovery T1 sent: {phone} ({servicio or 'General'}) via {cand.get('channel', '?')}")


async def _process_touch2(pool, cand, rule, lead_name, clinic_name, now_utc, lead_ctx=None):
    """Touch 2: Brief follow-up with humor."""
    tenant_id = cand["tenant_id"]
    phone = cand["phone"]
    trigger_type = TRIGGER_TYPES[2]

    from services.lead_analysis import generate_recovery_message

    # Use lead context treatment if available, otherwise empty
    servicio = (lead_ctx or {}).get("treatment_name", "")

    context = {
        "lead_name": lead_name,
        "servicio": servicio,
        "clinic_name": clinic_name,
    }
    message = await generate_recovery_message(pool, tenant_id, 2, context)
    if not message:
        await _log_recovery(pool, tenant_id, phone, trigger_type, "failed", error_details="message_generation_failed")
        return

    sent = await _send_recovery_message(pool, cand, message, tenant_id)
    if not sent:
        await _log_recovery(pool, tenant_id, phone, trigger_type, "failed", error_details="send_failed")
        return

    await pool.execute(
        "UPDATE chat_conversations SET recovery_touch_count = 2, last_recovery_at = NOW() WHERE id = $1",
        cand["conversation_id"],
    )
    await _log_recovery(pool, tenant_id, phone, trigger_type, "sent", message_preview=message[:200])

    from services.telegram_notifier import fire_telegram_notification
    fire_telegram_notification("LEAD_RECOVERY_TOUCH2", {
        "tenant_id": tenant_id,
        "lead_name": lead_name,
        "phone": phone,
        "channel": cand.get("channel", "whatsapp"),
        "servicio": servicio or "General",
        "is_high_ticket": cand.get("_is_high_ticket", False),
    }, tenant_id)

    logger.info(f"Lead recovery T2 sent: {phone} via {cand.get('channel', '?')}")


async def _process_touch3(pool, cand, rule, lead_name, clinic_name, now_utc, lead_ctx=None):
    """Touch 3: Soft closing message."""
    tenant_id = cand["tenant_id"]
    phone = cand["phone"]
    trigger_type = TRIGGER_TYPES[3]

    from services.lead_analysis import generate_recovery_message

    servicio = (lead_ctx or {}).get("treatment_name", "")
    context = {
        "lead_name": lead_name,
        "servicio": servicio,
        "clinic_name": clinic_name,
    }
    message = await generate_recovery_message(pool, tenant_id, 3, context)
    if not message:
        await _log_recovery(pool, tenant_id, phone, trigger_type, "failed", error_details="message_generation_failed")
        return

    sent = await _send_recovery_message(pool, cand, message, tenant_id)
    if not sent:
        await _log_recovery(pool, tenant_id, phone, trigger_type, "failed", error_details="send_failed")
        return

    await pool.execute(
        "UPDATE chat_conversations SET recovery_touch_count = 3, last_recovery_at = NOW() WHERE id = $1",
        cand["conversation_id"],
    )
    await _log_recovery(pool, tenant_id, phone, trigger_type, "sent", message_preview=message[:200])

    from services.telegram_notifier import fire_telegram_notification
    fire_telegram_notification("LEAD_RECOVERY_TOUCH3", {
        "tenant_id": tenant_id,
        "lead_name": lead_name,
        "phone": phone,
        "channel": cand.get("channel", "whatsapp"),
    }, tenant_id)

    logger.info(f"Lead recovery T3 sent: {phone} via {cand.get('channel', '?')}")


async def _send_recovery_message(pool, cand: Dict, message: str, tenant_id: int) -> bool:
    """Send recovery message via the correct channel. Returns True on success."""
    provider = cand.get("provider", "ycloud")
    channel = cand.get("channel", "whatsapp")
    phone = cand["phone"]
    conv_id = str(cand["conversation_id"])

    # Validate Chatwoot fields for IG/FB
    if provider in ("chatwoot", "meta_direct"):
        if not cand.get("external_account_id") or not cand.get("external_chatwoot_id"):
            logger.warning(f"Chatwoot fields missing for {phone} — skipping send")
            return False

    try:
        from services.response_sender import ResponseSender

        await ResponseSender.send_sequence(
            tenant_id=tenant_id,
            external_user_id=phone,
            conversation_id=conv_id,
            provider=provider,
            channel=channel,
            account_id=str(cand.get("external_account_id") or ""),
            cw_conv_id=str(cand.get("external_chatwoot_id") or ""),
            messages_text=message,
        )
        return True
    except Exception as e:
        logger.error(f"Lead recovery send failed ({phone}, {channel}): {e}")
        return False


async def _get_lead_name(pool, tenant_id: int, phone: str, lead_ctx: dict = None) -> str:
    """Try to resolve the lead's name from lead context, patients table, or chat messages."""
    # Priority 0: lead context (accumulated from AI tool calls)
    if lead_ctx and lead_ctx.get("first_name"):
        name = lead_ctx["first_name"]
        if lead_ctx.get("last_name"):
            name += f" {lead_ctx['last_name']}"
        return name.strip()

    # Try patients table
    try:
        row = await pool.fetchrow(
            "SELECT first_name, last_name FROM patients WHERE tenant_id = $1 AND phone_number = $2 LIMIT 1",
            tenant_id, phone,
        )
        if row and row.get("first_name"):
            return f"{row['first_name']} {row.get('last_name') or ''}".strip()
    except Exception:
        pass

    # Fallback: extract from first user message
    try:
        first_msg = await pool.fetchval(
            "SELECT content FROM chat_messages WHERE tenant_id = $1 AND phone_number = $2 AND role = 'user' ORDER BY created_at ASC LIMIT 1",
            tenant_id, phone,
        )
        if first_msg and len(first_msg) < 50:
            return first_msg.split()[0]  # First word of first message (often a name/greeting)
    except Exception:
        pass

    return phone  # Fallback to phone number


async def _log_recovery(
    pool, tenant_id: int, phone: str, trigger_type: str, status: str,
    message_preview: str = None, skip_reason: str = None, error_details: str = None,
):
    """Insert a row into automation_logs."""
    try:
        await pool.execute("""
            INSERT INTO automation_logs (
                tenant_id, phone_number, trigger_type, status,
                rule_name, message_preview, skip_reason, error_details,
                channel, triggered_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
        """,
            tenant_id, phone, trigger_type, status,
            "Recuperación de Leads (Inteligente)",
            message_preview, skip_reason, error_details,
            "multi",  # multi-channel
        )
    except Exception as e:
        logger.warning(f"automation_log insert failed: {e}")


# Register job: every 15 minutes
scheduler.add_job(check_lead_recovery, interval_seconds=900, run_at_startup=False)
