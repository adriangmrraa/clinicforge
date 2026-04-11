"""
telegram_notifier.py — Send WHITELISTED event notifications to Telegram authorized users.

Only high-value events (new appointments, cancellations, payments, handoffs)
reach the doctor's phone. Everything else (treatment plan updates, messages,
odontograms, etc.) is dropped to avoid notification spam.
Proactive messages (morning briefing, smart alerts) bypass the whitelist
via send_proactive_message().
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DIAS_SEMANA = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def _format_datetime(raw: Any) -> str:
    """Parse ISO datetime into a human-readable format like 'Mié 20/04 18:30'."""
    if not raw or raw == "?":
        return "?"
    try:
        if isinstance(raw, datetime):
            dt = raw
        else:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        dia = DIAS_SEMANA[dt.weekday()]
        return f"{dia} {dt.strftime('%d/%m %H:%M')}"
    except Exception:
        return str(raw)[:16]  # Fallback: truncate ISO


def _patient_name(d: dict) -> str:
    """Extract patient name from various possible keys."""
    name = d.get("patient_name", "")
    if not name or name.strip() == "?":
        first = d.get("patient_first_name", d.get("first_name", ""))
        last = d.get("patient_last_name", d.get("last_name", ""))
        name = f"{first} {last}".strip()
    return name or "Paciente desconocido"


# Event → human-readable format mapping
EVENT_FORMATS = {
    "NEW_APPOINTMENT": {
        "emoji": "📅",
        "title": "Nuevo turno",
        "fields": lambda d: [
            f"Paciente: {_patient_name(d)}",
            f"Fecha: {_format_datetime(d.get('appointment_datetime', d.get('date')))}",
            f"Tipo: {d.get('appointment_type', d.get('treatment_type', 'Consulta'))}" if d.get('appointment_type') or d.get('treatment_type') else None,
            f"Profesional: {d.get('professional_name')}" if d.get('professional_name') else None,
            f"Fuente: {'🤖 Bot IA' if d.get('source') == 'ai' else '👩‍💼 Manual'}" if d.get('source') else None,
        ],
    },
    "APPOINTMENT_UPDATED": {
        "emoji": "🔄",
        "title": "Turno actualizado",
        "fields": lambda d: [
            f"Paciente: {_patient_name(d)}",
            f"Fecha: {_format_datetime(d.get('appointment_datetime', d.get('date')))}",
            f"Estado: {d.get('status', '?')}",
        ],
    },
    "APPOINTMENT_DELETED": {
        "emoji": "❌",
        "title": "Turno cancelado",
        "fields": lambda d: [
            f"Paciente: {_patient_name(d)}" if isinstance(d, dict) and _patient_name(d) != "Paciente desconocido" else None,
            f"Fecha: {_format_datetime(d.get('appointment_datetime'))}" if isinstance(d, dict) and d.get('appointment_datetime') else None,
            f"Tipo: {d.get('appointment_type')}" if isinstance(d, dict) and d.get('appointment_type') else None,
        ],
    },
    "PAYMENT_CONFIRMED": {
        "emoji": "💰",
        "title": "Pago confirmado",
        "fields": lambda d: [
            f"Paciente: {_patient_name(d)}",
            f"Monto: ${d.get('billing_amount', d.get('amount', '?'))}",
            f"Estado: {d.get('payment_status', 'paid')}",
        ],
    },
    "HUMAN_HANDOFF": {
        "emoji": "🤝",
        "title": "Derivación a humano",
        "fields": lambda d: [
            f"Teléfono: {d.get('phone_number', '?')}",
            f"Motivo: {d.get('reason', '?')}",
        ],
    },
    "LEAD_RECOVERY_TOUCH1": {
        "emoji": "🎯",
        "title": "Recuperé un lead",
        "fields": lambda d: [
            f"👤 {d.get('lead_name', '?')} ({d.get('phone', '?')})",
            f"📱 Canal: {d.get('channel', '?')}",
            f"🦷 Interés: {d.get('servicio', 'General')}",
            f"💬 {d.get('message_preview', '')[:80]}..." if d.get('message_preview') else None,
            f"🕐 Ventana 24h expira: {d.get('window_end', '?')}",
            "💎 HIGH TICKET" if d.get('is_high_ticket') else None,
        ],
    },
    "LEAD_RECOVERY_TOUCH2": {
        "emoji": "📌",
        "title": "Segundo intento de recuperación",
        "fields": lambda d: [
            f"👤 {d.get('lead_name', '?')} ({d.get('phone', '?')})",
            f"📱 Canal: {d.get('channel', '?')}",
            f"🦷 Interés: {d.get('servicio', 'General')}",
            "📍 No respondió al primer mensaje",
            "💎 HIGH TICKET" if d.get('is_high_ticket') else None,
        ],
    },
    "LEAD_RECOVERY_TOUCH3": {
        "emoji": "👋",
        "title": "Último contacto enviado",
        "fields": lambda d: [
            f"👤 {d.get('lead_name', '?')} ({d.get('phone', '?')})",
            f"📱 Canal: {d.get('channel', '?')}",
            "⏱️ Ciclo completo: 3 intentos sin respuesta",
        ],
    },
    "LEAD_RECOVERY_CONVERSION": {
        "emoji": "✅",
        "title": "Lead convertido!",
        "fields": lambda d: [
            f"👤 {d.get('patient_name', '?')} ({d.get('phone', '?')})",
            f"📅 Turno: {d.get('appointment_datetime', '?')}",
            f"🦷 Tratamiento: {d.get('treatment_type', '?')}",
            f"📊 {d.get('recovery_touch_count', '?')} mensaje(s) de seguimiento antes de convertir",
            f"⏱️ Tiempo: {d.get('hours_to_convert', '?')}h desde primer contacto",
        ],
    },
    "LEAD_RECOVERY_NOT_INTERESTED": {
        "emoji": "🚫",
        "title": "Lead no interesado",
        "fields": lambda d: [
            f"👤 {d.get('lead_name', '?')} ({d.get('phone', '?')})",
            f"📱 Canal: {d.get('channel', '?')}",
            "🚫 no_followup activado — sin más seguimientos",
        ],
    },
}

# WHITELIST: Only these high-value events reach the doctor's Telegram.
# Everything else is silently dropped (no generic fallback).
ALLOWED_EVENTS = {
    "NEW_APPOINTMENT",
    "APPOINTMENT_DELETED",
    "PAYMENT_CONFIRMED",
    "HUMAN_HANDOFF",
    "LEAD_RECOVERY_TOUCH1",
    "LEAD_RECOVERY_TOUCH2",
    "LEAD_RECOVERY_TOUCH3",
    "LEAD_RECOVERY_CONVERSION",
    "LEAD_RECOVERY_NOT_INTERESTED",
}


def _format_event(event: str, data: Any) -> Optional[str]:
    """Format a WebSocket event as a human-readable Telegram notification.

    Only ALLOWED_EVENTS are formatted. Everything else returns None (dropped).
    No generic fallback — if it's not explicitly whitelisted, it doesn't reach
    the doctor's phone.
    """
    if event not in ALLOWED_EVENTS:
        return None

    # Handle string-only data (e.g., APPOINTMENT_DELETED sends just the ID)
    if isinstance(data, str):
        data_dict = {"id": data}
    elif isinstance(data, dict):
        data_dict = data
    else:
        data_dict = {}

    fmt = EVENT_FORMATS.get(event)
    if not fmt:
        return None  # Allowed but no format defined — skip

    emoji = fmt["emoji"]
    title = fmt["title"]
    try:
        fields = [f for f in fmt["fields"](data_dict if isinstance(data, dict) else data) if f]
    except Exception:
        fields = [f"Datos: {json.dumps(data_dict, default=str)[:200]}"]

    if not fields:
        fields = ["(sin detalles)"]

    lines = [f"{emoji} <b>{title}</b>", ""]
    for f in fields:
        lines.append(f"▸ {f}")

    return "\n".join(lines)


async def notify_telegram(event: str, data: Any, tenant_id: Optional[int] = None):
    """
    Send a WebSocket event as notification to all authorized Telegram users.

    Runs fire-and-forget — never raises, never blocks.
    """
    try:
        # Only allow whitelisted high-value events
        if event not in ALLOWED_EVENTS:
            return

        # Extract tenant_id from data if not provided
        if tenant_id is None and isinstance(data, dict):
            tenant_id = data.get("tenant_id")
        if tenant_id is None:
            return  # Can't send without tenant

        # Format the message
        message = _format_event(event, data)
        if not message:
            return

        # Get the bot for this tenant
        from services.telegram_bot import _bots
        app = _bots.get(tenant_id)
        if not app:
            return  # No Telegram bot running for this tenant

        # Get authorized users
        from services.telegram_bot import _verify_user
        from db import db

        rows = await db.fetch(
            "SELECT telegram_chat_id FROM telegram_authorized_users "
            "WHERE tenant_id = $1 AND is_active = true",
            tenant_id,
        )
        if not rows:
            return

        from core.credentials import decrypt_value
        from telegram.constants import ParseMode

        bot = app.bot
        for row in rows:
            try:
                chat_id = int(decrypt_value(row["telegram_chat_id"]))
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.debug(f"Telegram notify skip chat: {e}")

    except Exception as e:
        logger.debug(f"Telegram notify error ({event}): {e}")


def fire_telegram_notification(event: str, data: Any, tenant_id: Optional[int] = None):
    """Fire-and-forget wrapper — schedules notify_telegram without blocking."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(notify_telegram(event, data, tenant_id))
    except RuntimeError:
        pass  # No event loop — skip silently


async def send_proactive_message(tenant_id: int, html_text: str):
    """Send a proactive message to all authorized Telegram users of a tenant."""
    try:
        from services.telegram_bot import _bots
        app = _bots.get(tenant_id)
        if not app:
            return

        from db import db
        rows = await db.fetch(
            "SELECT telegram_chat_id FROM telegram_authorized_users "
            "WHERE tenant_id = $1 AND is_active = true",
            tenant_id,
        )
        if not rows:
            return

        from core.credentials import decrypt_value
        from telegram.constants import ParseMode

        bot = app.bot
        for row in rows:
            try:
                chat_id = int(decrypt_value(row["telegram_chat_id"]))
                await bot.send_message(
                    chat_id=chat_id,
                    text=html_text,
                    parse_mode=ParseMode.HTML,
                )
            except Exception as e:
                logger.debug(f"Proactive message skip chat: {e}")
    except Exception as e:
        logger.warning(f"send_proactive_message error: {e}")
