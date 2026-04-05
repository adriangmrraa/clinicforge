"""
telegram_notifier.py — Send WebSocket event notifications to Telegram authorized users.

Every sio.emit event gets mirrored as a Telegram notification to all
authorized users of the tenant. This runs fire-and-forget (never blocks
the main flow).
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Event → human-readable format mapping
EVENT_FORMATS = {
    "NEW_APPOINTMENT": {
        "emoji": "📅",
        "title": "Nuevo turno",
        "fields": lambda d: [
            f"Paciente: {d.get('patient_name', d.get('patient_first_name', '?'))} {d.get('patient_last_name', '')}".strip(),
            f"Fecha: {d.get('appointment_datetime', d.get('date', '?'))}",
            f"Tipo: {d.get('appointment_type', d.get('treatment_type', '?'))}",
            f"Profesional: {d.get('professional_name', '?')}" if d.get('professional_name') else None,
        ],
    },
    "APPOINTMENT_UPDATED": {
        "emoji": "🔄",
        "title": "Turno actualizado",
        "fields": lambda d: [
            f"Paciente: {d.get('patient_name', d.get('patient_first_name', '?'))} {d.get('patient_last_name', '')}".strip(),
            f"Fecha: {d.get('appointment_datetime', d.get('date', '?'))}",
            f"Estado: {d.get('status', '?')}",
        ],
    },
    "APPOINTMENT_DELETED": {
        "emoji": "❌",
        "title": "Turno cancelado",
        "fields": lambda d: [f"ID: {d}" if isinstance(d, str) else f"Turno eliminado"],
    },
    "PAYMENT_CONFIRMED": {
        "emoji": "💰",
        "title": "Pago confirmado",
        "fields": lambda d: [
            f"Paciente: {d.get('patient_name', '?')}",
            f"Monto: ${d.get('billing_amount', d.get('amount', '?'))}",
            f"Estado: {d.get('payment_status', 'paid')}",
        ],
    },
    "NEW_MESSAGE": {
        "emoji": "💬",
        "title": "Nuevo mensaje",
        "fields": lambda d: [
            f"De: {d.get('sender_name', d.get('phone', '?'))}",
            f"Canal: {d.get('channel', '?')}",
            f"Mensaje: {str(d.get('content', d.get('text', '')))[:100]}",
        ],
    },
    "PATIENT_UPDATED": {
        "emoji": "👤",
        "title": "Paciente actualizado",
        "fields": lambda d: [
            f"Paciente: {d.get('first_name', '?')} {d.get('last_name', '')}".strip(),
            f"Campo: {d.get('field', '?')}" if d.get('field') else None,
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
    "DIGITAL_RECORD_CREATED": {
        "emoji": "📄",
        "title": "Ficha digital generada",
        "fields": lambda d: [
            f"Tipo: {d.get('template_type', '?')}",
            f"Título: {d.get('title', '?')}",
        ],
    },
    "DIGITAL_RECORD_SENT": {
        "emoji": "📧",
        "title": "Ficha enviada por email",
        "fields": lambda d: [
            f"Título: {d.get('title', '?')}",
            f"Email: {d.get('email', '?')}",
        ],
    },
    "ODONTOGRAM_UPDATED": {
        "emoji": "🦷",
        "title": "Odontograma actualizado",
        "fields": lambda d: [
            f"Paciente ID: {d.get('patient_id', '?')}",
        ],
    },
    "BUDGET_CREATED": {
        "emoji": "📋",
        "title": "Presupuesto creado",
        "fields": lambda d: [
            f"Paciente: {d.get('patient_name', '?')}",
            f"Total: ${d.get('total', '?')}" if d.get('total') else None,
        ],
    },
    "BUDGET_UPDATED": {
        "emoji": "📋",
        "title": "Presupuesto actualizado",
        "fields": lambda d: [
            f"Estado: {d.get('status', '?')}",
        ],
    },
}

# Events to SKIP sending to Telegram (too noisy / internal)
SKIP_EVENTS = {
    "NOVA_TOOL_EXECUTED",  # Internal Nova tool tracking
    "connect",
    "disconnect",
}


def _format_event(event: str, data: Any) -> Optional[str]:
    """Format a WebSocket event as a human-readable Telegram notification."""
    if event in SKIP_EVENTS:
        return None

    # Handle string-only data (e.g., APPOINTMENT_DELETED sends just the ID)
    if isinstance(data, str):
        data_dict = {"id": data}
    elif isinstance(data, dict):
        data_dict = data
    else:
        data_dict = {}

    fmt = EVENT_FORMATS.get(event)
    if fmt:
        emoji = fmt["emoji"]
        title = fmt["title"]
        try:
            fields = [f for f in fmt["fields"](data_dict if isinstance(data, dict) else data) if f]
        except Exception:
            fields = [f"Datos: {json.dumps(data_dict, default=str)[:200]}"]
    else:
        # Unknown event — generic format
        emoji = "🔔"
        title = event.replace("_", " ").title()
        fields = []
        if data_dict:
            for k, v in list(data_dict.items())[:5]:
                if k not in ("tenant_id",) and v is not None:
                    fields.append(f"{k}: {str(v)[:100]}")

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
        # Skip noisy events
        if event in SKIP_EVENTS:
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
