"""Multi-agent graph wiring + `run_turn` entry point for MultiAgentEngine (C3 F3).

Minimal implementation without a hard dependency on the `langgraph` package:
- Supervisor decides which specialized agent handles the turn.
- Selected agent runs, sets `agent_output`, and terminates.
- Audit row written to `agent_turn_log` (best-effort).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import text

from .specialists import AGENTS
from .state import AgentState
from .supervisor import SupervisorAgent

if TYPE_CHECKING:
    from services.engine_router import ProbeResult, TurnContext, TurnResult

logger = logging.getLogger(__name__)

MAX_HOPS = 5
TURN_TIMEOUT_S = 45

_supervisor = SupervisorAgent()


# ── Conversation State Injection Block Builder ──────────────────────────────
# Mirrors buffer_task.py lines 1898-2036 — anti-loop booking context for specialists.


def _build_convstate_injection_block(cs_data: dict) -> str:
    """
    Build a prompt block with all anti-loop booking fields from conversation_state.
    Must match the logic in buffer_task.py:1898-2036 exactly.
    Returns an empty string when cs_data is empty/minimal (IDLE state).
    """
    if not cs_data or cs_data.get("state") == "IDLE":
        return ""

    lines: list[str] = []

    # Failed slots blacklist
    failed = cs_data.get("failed_slots") or []
    if failed:
        failed_dates = sorted(set(f["date"] for f in failed if f.get("date")))
        lines.append("SLOTS FALLIDOS (PROHIBIDO re-ofrecer):")
        for f in failed:
            lines.append(
                f"  • {f['date']} {f.get('time', '??:??')} — {f.get('code', 'UNAVAILABLE')}"
            )
        lines.append(
            "REGLA: NO ofrezcas ninguno de estos slots al paciente. "
            "Si check_availability los incluye, filtralos antes de presentar."
        )
        lines.append("")

    # Patient exclusions
    exd = cs_data.get("excluded_days") or []
    exdt = cs_data.get("excluded_dates") or []
    if exd or exdt:
        excl_lines = []
        if exd:
            excl_lines.append(f"DÍAS EXCLUIDOS: {', '.join(exd)}")
        if exdt:
            excl_lines.append(f"FECHAS EXCLUIDAS: {', '.join(exdt)}")
        excl_lines.append(
            "REGLA: NO ofrezcas turnos en estos días/fechas. El paciente los rechazó explícitamente."
        )
        lines.extend(["EXCLUSIONES DEL PACIENTE:"] + excl_lines + [""])

    # Booking attempts warning
    batt = cs_data.get("booking_attempts") or 0
    if batt > 0:
        batt_remaining = max(0, 3 - batt)
        batt_word = "intento" if batt_remaining == 1 else "intentos"
        lines.append(
            f"⚠️ INTENTOS DE AGENDAMIENTO FALLIDOS: {batt} de 3."
            f" Te queda{'n' if batt_remaining != 1 else ''} {batt_remaining} {batt_word}."
            f" Al llegar a 3 fallos → llamá derivhumano inmediatamente."
        )
        lines.append("")

    # Anchor date propagation
    anc = cs_data.get("anchor_date")
    if anc:
        lines.append(
            f"📅 ANCHOR_DATE: {anc}"
            " — Usá esta fecha en confirm_slot y book_appointment. NO recalcules fechas relativas."
        )
        lines.append("")

    # Correction awareness (has_correction flag — set by buffer_task when patient corrects info)
    if cs_data.get("has_correction"):
        lines.append(
            "⚠️ EL PACIENTE CORRIGIÓ INFORMACIÓN PREVIA en su último mensaje."
            " Revisá los datos del paciente ANTES de continuar con el agendamiento."
            " Usá los NUEVOS datos que dio, no los anteriores."
        )
        lines.append("")

    # Anchor date cross-validation: day-of-week mismatch warning
    if anc:
        # day_mismatch logic from buffer_task.py:1955-1973
        pass  # deferred — requires message context not available here

    # Error history context injection (last 3 errors)
    err_history = cs_data.get("error_history") or []
    if err_history:
        lines.append("⚠️ ERRORES PREVIOS EN ESTA CONVERSACIÓN:")
        for err in err_history[-3:]:
            cat = err.get("category", "UNKNOWN")
            msg = err.get("message", "")
            turn = err.get("turn_number", "?")
            lines.append(f"  • [{cat}] turno {turn}: {msg}")
        lines.append("REGLA: NO repitas el mismo error. Si fue RECOVERABLE, intentá un slot diferente.")
        lines.append("")

    # Frustration detection injection
    frust_count = cs_data.get("frustration_count") or 0
    frust_mode = cs_data.get("frustration_mode") or False
    if frust_count >= 2 and frust_count < 4:
        lines.append(
            f"[FRUSTRATION_DETECTED: modo conciliación — disculparse UNA vez y ofrecer opciones concretas. "
            f"El paciente mostró {frust_count} señales de frustración.]"
        )
        lines.append("")
    if frust_count >= 4:
        lines.append(
            "[FRUSTRATION_ESCALATED: derivar a humano inmediatamente. "
            "Usá la herramienta derivhumano con motivo 'Paciente frustrado después de múltiples intentos'."
        )
        lines.append("")

    # Multi-booking context injection
    btargets = cs_data.get("booking_targets") or []
    btarget_idx = cs_data.get("current_booking_target_index") or 0
    if len(btargets) > 1:
        current = btargets[btarget_idx] if btarget_idx < len(btargets) else btargets[-1]
        pending = [t for t in btargets if t.get("status") == "pending"]
        booked = [t for t in btargets if t.get("status") == "booked"]
        ctx_lines = [
            f"MULTI_BOOKING: Hay {len(btargets)} personas para agendar.",
            f"Ya agendados: {len(booked)}. Pendientes: {len(pending)}.",
            f"ACTUAL: Agendando para {current.get('type', 'self')} ({current.get('relationship', 'el paciente')})",
            "REGLA: Agendá UNA persona a la vez. Después de confirmar el turno actual, continuá con la siguiente.",
        ]
        lines.extend(ctx_lines + [""])

    # Single-target minor booking context injection
    if len(btargets) == 1:
        bt = btargets[0]
        if bt.get("is_minor") or bt.get("relationship") in ("hijo/a", "hijo", "hija", "menor"):
            minor_name = f"{bt.get('first_name', '')} {bt.get('last_name', '')}".strip()
            minor_dni = bt.get("dni", "")
            minor_lines = [
                "MINOR BOOKING IN PROGRESS: El turno que se está gestionando es para un MENOR.",
                f"Nombre del menor: {minor_name or 'pendiente'}",
            ]
            if minor_dni:
                minor_lines.append(f"DNI del menor: {minor_dni}")
            minor_lines.extend([
                "REGLAS:",
                "- Usá is_minor=true en book_appointment.",
                "- NO le pidas teléfono del menor al paciente.",
                "- La vinculación con el padre/madre es automática.",
            ])
            lines.extend(minor_lines + [""])

    if not lines:
        return ""

    return "\n".join(lines).strip()


async def _write_convstate_outcomes(state: AgentState, cs_data: dict) -> None:
    """
    Inspect state["tools_called"] after agent.run() and write outcomes back to conversation_state.
    Best-effort — all writes wrapped in try/except, non-blocking.
    Mirrors buffer_task.py WRITE hooks after tool execution.
    """
    from services.conversation_state import (
        append_failed_slot,
        add_exclusion,
        increment_booking_attempts,
        reset_booking_attempts,
        increment_frustration,
        set_anchor_date,
        mark_target_booked,
        mark_booking_target_index,
        append_error_history,
    )

    tenant_id = state.get("tenant_id")
    phone_number = state.get("phone_number")
    if not tenant_id or not phone_number:
        return

    tools_called = state.get("tools_called", []) or []
    user_msg = (state.get("user_message") or "").lower()

    try:
        # ── Detect frustration signals ──────────────────────────────────────
        _frustration_keywords = [
            "ya te dije", "ya te dije lo mismo", "no me escuchas",
            "ya lo dije", "ya te lo dije", "no me entendés", "no me estás escuchando",
            "otra vez lo mismo", "cuántas veces tengo que decirte", "no hacés caso",
            "frustrado", "frustrada", "enojado", "enojada", "estoy harto",
            "qué difícil es", "esto es imposible", "nunca me pueden ayudar",
        ]
        if any(kw in user_msg for kw in _frustration_keywords):
            try:
                await increment_frustration(tenant_id, phone_number)
            except Exception as e:
                logger.warning(f"_write_convstate_outcomes: increment_frustration failed: {e}")

        # ── Anchor date detection from user confirming a specific date ─────
        # E.g. patient says "perfecto, el miércoles 25"
        _date_confirm_patterns = [
            r"\del\s+\d{1,2}", r"\dal\s+\d{1,2}", r"\d{1,2}\s+de\s+\w+",
            r"confirmo", r"dale\s+el", r"perfecto.*\d", r"si.*\d{4}-\d{2}-\d{2}",
        ]
        import re
        anc = cs_data.get("anchor_date")
        for pat in _date_confirm_patterns:
            m = re.search(pat, user_msg)
            if m and not anc:
                # Try to extract a date from the message to set as anchor
                date_match = re.search(r"\d{4}-\d{2}-\d{2}", user_msg)
                if date_match:
                    try:
                        await set_anchor_date(tenant_id, phone_number, date_match.group())
                    except Exception as e:
                        logger.warning(f"_write_convstate_outcomes: set_anchor_date failed: {e}")
                break

        # ── Patient rejection of a date (explicit exclusion) ───────────────
        _rejection_patterns = [
            "no puedo el", "no me sirve el", "no va el", "ese día no",
            "esa fecha no", "no me sirve para nada", "cancelá", "olvitalo",
            "ni idea", "cualquier otro día", "cambia el día", "otra fecha",
        ]
        if any(pat in user_msg for pat in _rejection_patterns):
            # Try to extract a date to exclude
            date_match = re.search(r"\d{4}-\d{2}-\d{2}", user_msg)
            if date_match:
                try:
                    await add_exclusion(tenant_id, phone_number, {"dates": [date_match.group()]})
                except Exception as e:
                    logger.warning(f"_write_convstate_outcomes: add_exclusion failed: {e}")

        # ── Inspect tools_called for outcomes ────────────────────────────────
        for tc in tools_called:
            tool_name = tc.get("tool", "") if isinstance(tc, dict) else str(tc)
            tool_args = tc.get("args", {}) if isinstance(tc, dict) else {}

            # check_availability with empty/unavailable → append_failed_slot
            if tool_name == "check_availability":
                result = tool_args.get("result") or (tc.get("result") if isinstance(tc, dict) else None)
                if result is not None:
                    slots = result.get("slots", []) if isinstance(result, dict) else []
                    if not slots or result.get("status") == "no_availability":
                        # Record the date/time that was offered but unavailable
                        date = tool_args.get("date") or tc.get("date", "")
                        time = tool_args.get("time") or tc.get("time", "")
                        code = result.get("code", "UNAVAILABLE") if isinstance(result, dict) else "UNAVAILABLE"
                        if date:
                            try:
                                await append_failed_slot(
                                    tenant_id, phone_number,
                                    {"date": date, "time": time, "code": code}
                                )
                            except Exception as e:
                                logger.warning(f"_write_convstate_outcomes: append_failed_slot failed: {e}")

            # book_appointment failure
            if tool_name == "book_appointment":
                result = tool_args.get("result") or (tc.get("result") if isinstance(tc, dict) else None)
                success = False
                if isinstance(result, dict):
                    success = result.get("success", False)
                if not success:
                    try:
                        new_count = await increment_booking_attempts(tenant_id, phone_number)
                    except Exception as e:
                        logger.warning(f"_write_convstate_outcomes: increment_booking_attempts failed: {e}")

                    # Append to error history
                    err_entry = {
                        "category": "book_appointment_failure",
                        "message": str(result.get("error", "unknown")) if isinstance(result, dict) else str(result),
                        "turn_number": state.get("hop_count", 0),
                    }
                    try:
                        await append_error_history(tenant_id, phone_number, err_entry)
                    except Exception as e:
                        logger.warning(f"_write_convstate_outcomes: append_error_history failed: {e}")

                    # Frustration on booking failure (additional increment)
                    try:
                        await increment_frustration(tenant_id, phone_number)
                    except Exception as e:
                        logger.warning(f"_write_convstate_outcomes: booking-failure frustration increment failed: {e}")

                    # If attempts >= 3, also set frustration_mode
                    if new_count >= 3:
                        try:
                            from services.conversation_state import set_frustration_mode
                            await set_frustration_mode(tenant_id, phone_number, True)
                        except Exception as e:
                            logger.warning(f"_write_convstate_outcomes: set_frustration_mode failed: {e}")
                else:
                    # book_appointment success → reset attempts, mark target booked, advance index
                    try:
                        await reset_booking_attempts(tenant_id, phone_number)
                    except Exception as e:
                        logger.warning(f"_write_convstate_outcomes: reset_booking_attempts failed: {e}")

                    # Clear error history on success
                    try:
                        from services.conversation_state import clear_error_history
                        await clear_error_history(tenant_id, phone_number)
                    except Exception as e:
                        logger.warning(f"_write_convstate_outcomes: clear_error_history failed: {e}")

                    # Multi-booking: mark current target as booked and advance index
                    cs = cs_data or {}
                    btargets = cs.get("booking_targets") or []
                    btarget_idx = cs.get("current_booking_target_index") or 0
                    if len(btargets) > 1:
                        try:
                            await mark_target_booked(tenant_id, phone_number, btarget_idx)
                        except Exception as e:
                            logger.warning(f"_write_convstate_outcomes: mark_target_booked failed: {e}")
                        next_idx = btarget_idx + 1
                        if next_idx < len(btargets):
                            try:
                                await mark_booking_target_index(tenant_id, phone_number, next_idx)
                            except Exception as e:
                                logger.warning(f"_write_convstate_outcomes: mark_booking_target_index failed: {e}")

    except Exception as e:
        logger.warning(f"_write_convstate_outcomes: top-level exception: {e}")


async def _load_patient_context(tenant_id: int, phone_number: str, family_patient_ids: Optional[list[int]] = None) -> tuple[dict, list[dict]]:
    """Load minimal patient profile and chat history for the turn."""
    from services.patient_context import PatientContext
    ctx = await PatientContext.load(tenant_id, phone_number, family_patient_ids=family_patient_ids)
    p = ctx.profile
    profile_dict = {
        "name": p.name,
        "dni": p.dni,
        "email": p.email,
        "is_new_lead": p.is_new_lead,
        "human_override_until": p.human_override_until.isoformat() if p.human_override_until else None,
        "medical_history": p.medical_history,
        "future_appointments": p.future_appointments,
        # Phase 1 — CRITICAL
        "phone_number": p.phone_number,
        "assigned_professional": p.assigned_professional,
        "next_appointment": p.next_appointment,
        "last_appointment": p.last_appointment,
        "treatment_plan": p.treatment_plan,
        "family_members": p.family_members,
        "patient_memories": p.patient_memories,
        # Phase 2 — HIGH
        "children_dependents": p.children_dependents,
        "visit_count": p.visit_count,
        "anamnesis_status": p.anamnesis_status,
        # Phase 3 — MEDIUM
        "birth_date": p.birth_date,
        "insurance_provider": p.insurance_provider,
        "urgency_level": p.urgency_level,
    }
    return profile_dict, p.recent_turns


async def _log_turn(state: AgentState, agent_name: str, duration_ms: int, model: str, handoff_to: str = None) -> None:
    """Insert a row in agent_turn_log. Best-effort — failure is logged and swallowed."""
    try:
        from main import AsyncSessionLocal  # type: ignore
    except Exception as e:
        logger.debug(f"_log_turn: AsyncSessionLocal unavailable: {e}")
        return

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(
                text("""
                    INSERT INTO agent_turn_log
                        (tenant_id, phone_number, turn_id, agent_name,
                         tools_called, handoff_to, duration_ms, model)
                    VALUES
                        (:tenant_id, :phone, :turn_id, :agent,
                         CAST(:tools AS JSONB), :handoff, :dur, :model)
                """),
                {
                    "tenant_id": state["tenant_id"],
                    "phone": state["phone_number"],
                    "turn_id": state["turn_id"],
                    "agent": agent_name,
                    "tools": json.dumps(state.get("tools_called", []), default=str),
                    "handoff": handoff_to,
                    "dur": duration_ms,
                    "model": model,
                },
            )
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to write agent_turn_log: {e}")


async def run_turn(ctx: "TurnContext") -> "TurnResult":
    """Entry point invoked by MultiAgentEngine.process_turn.

    1. Load patient context (profile + history)
    2. Build initial AgentState
    3. Supervisor routes
    4. Specialized agent runs
    5. Audit log + return TurnResult
    """
    from services.engine_router import TurnResult  # lazy — avoid circular
    start = time.perf_counter()
    turn_id = str(uuid.uuid4())

    try:
        profile, chat_history = await _load_patient_context(
            ctx.tenant_id, ctx.phone_number,
            family_patient_ids=ctx.extra.get("family_patient_ids") if hasattr(ctx, "extra") and ctx.extra else None,
        )
    except Exception:
        logger.exception("Failed to load patient context")
        profile = {
            "name": None, "dni": None, "email": None, "is_new_lead": True,
            "human_override_until": None, "medical_history": {}, "future_appointments": [],
            "phone_number": None, "assigned_professional": None, "next_appointment": None,
            "last_appointment": None, "treatment_plan": None, "family_members": [],
            "patient_memories": None, "children_dependents": [], "visit_count": None,
            "anamnesis_status": None, "birth_date": None, "urgency_level": None,
        }
        chat_history = []

    # Resolve the tenant's configured model ONCE per turn from system_config.OPENAI_MODEL
    # (single source of truth — same as SoloEngine / TORA legacy). NEVER hardcoded.
    try:
        from .model_resolver import resolve_tenant_model
        model_config = await resolve_tenant_model(ctx.tenant_id)
    except Exception:
        logger.exception("Failed to resolve tenant model, using default")
        from .model_resolver import get_default_model_config
        model_config = get_default_model_config()

    # Build tenant-configured context blocks ONCE per turn (multi-agent parity
    # with TORA solo — spec: multi-agent-tenant-context-parity REQ-3).
    # All specialists in this turn read from the same dict via
    # select_blocks_for_specialist(). Failure is non-fatal: empty dict falls
    # through to bare prompts so the multi-agent still runs.
    tenant_context: dict = {}
    try:
        from db import db  # lazy — avoid circular
        from .tenant_context import build_tenant_context_blocks

        # Defensive intent classification (REQ-3.1) — safe default on failure.
        try:
            from services.buffer_task import classify_intent  # type: ignore
            intent_tags = classify_intent([{"role": "user", "content": ctx.user_message}])
        except Exception:
            intent_tags = set()

        tenant_context = await build_tenant_context_blocks(
            db.pool,
            ctx.tenant_id,
            user_message_text=ctx.user_message or "",
            intent_tags=intent_tags,
        )
    except Exception:
        logger.exception("build_tenant_context_blocks failed — continuing with empty context")
        tenant_context = {}

    state: AgentState = {
        "tenant_id": ctx.tenant_id,
        "phone_number": ctx.phone_number,
        "thread_id": ctx.thread_id,
        "turn_id": turn_id,
        "user_message": ctx.user_message,
        "patient_profile": profile,
        "chat_history": chat_history,
        "working_state": {},
        "model_config": model_config,
        "tenant_context": tenant_context,
        "active_agent": "supervisor",
        "hop_count": 0,
        "max_hops": MAX_HOPS,
        "agent_output": "",
        "tools_called": [],
        "handoff_reason": None,
        "start_time": start,
        # Social channel context (Instagram/Facebook agent — phase 5).
        # Populated from ctx.extra which is set by buffer_task.compute_social_context.
        # Safe defaults ensure backward compat with callers that don't set extra.
        "channel": ctx.extra.get("channel", "whatsapp"),
        "is_social_channel": ctx.extra.get("is_social_channel", False),
        "social_landings": ctx.extra.get("social_landings"),
        "instagram_handle": ctx.extra.get("instagram_handle"),
        "facebook_page_id": ctx.extra.get("facebook_page_id"),
        "whatsapp_link": ctx.extra.get("whatsapp_link"),
        "lead_context": None,
    }

    # Operational rules injection (temporary/strategic rules from DB)
    try:
        from db import db as _db_mod
        op_rows = await _db_mod.pool.fetch(
            """SELECT rule_name, rule_type, prompt_injection, valid_until
               FROM clinic_operational_rules
               WHERE tenant_id = $1 AND is_active = true
                 AND (valid_from IS NULL OR valid_from <= NOW())
                 AND (valid_until IS NULL OR valid_until >= NOW())
                 AND ('all' = ANY(applies_to) OR 'multi' = ANY(applies_to))
               ORDER BY priority_order ASC, id ASC""",
            ctx.tenant_id,
        )
        if op_rows:
            parts = ["⚠️ REGLAS OPERATIVAS VIGENTES:"]
            for opr in op_rows:
                until = f" (hasta {opr['valid_until'].strftime('%d/%m/%Y')})" if opr.get("valid_until") else ""
                parts.append(f"[{opr['rule_type'].upper()}]{until}: {opr['prompt_injection']}")
            state["operational_rules_block"] = "\n".join(parts)
    except Exception:
        pass

    # -----------------------------------------------------------------------
    # Multimodal wait & dedup (multi-agent parity — GAP 9)
    # -----------------------------------------------------------------------
    # When the patient sends an audio message, wait for transcription to be
    # available before continuing (the buffer_task async pipeline may still be
    # transcribing). This duplicates the solo engine wait logic from main.py.
    _message_text = (ctx.user_message or "").strip()
    if _message_text and len(_message_text) < 20:
        try:
            from services.buffer_task import _wait_for_audio_transcription  # type: ignore
            _transcribed = await _wait_for_audio_transcription(
                ctx.tenant_id, ctx.thread_id, chat_history, max_wait=30
            )
            if _transcribed and _transcribed != _message_text:
                logger.info(f"multi-agent: audio transcription resolved for turn {turn_id}")
                state["user_message"] = _transcribed
        except Exception:
            pass

    # Dedup: skip processing if the exact same message was handled recently
    try:
        from db import db as _dedup_db
        _recent = await _dedup_db.pool.fetchrow(
            """SELECT 1 FROM agent_turn_log
               WHERE tenant_id = $1 AND phone_number = $2
                 AND created_at > NOW() - INTERVAL '5 seconds'
                 AND tools_called->>0 IS NOT NULL
               LIMIT 1""",
            ctx.tenant_id, ctx.phone_number,
        )
        if _recent:
            logger.info(f"multi-agent: dedup skip for turn {turn_id} — recent turn exists")
            duration_ms = int((time.perf_counter() - start) * 1000)
            return TurnResult(
                output="",
                agent_used="dedup",
                duration_ms=duration_ms,
                metadata={"reason": "dedup_recent_turn", "turn_id": turn_id},
            )
    except Exception:
        pass

    # Lead context injection: for leads not yet in the DB, load accumulated data
    if profile.get("is_new_lead"):
        try:
            from services.lead_context import get as lead_ctx_get
            _lead_data = await lead_ctx_get(ctx.tenant_id, ctx.phone_number)
            if _lead_data:
                state["lead_context"] = _lead_data
        except Exception:
            pass

    # No-interest detection — mark lead as not wanting follow-up before routing.
    # Done at graph level (earliest point with tenant_id + phone + user_message)
    # so it fires regardless of which specialist handles the turn.
    _NO_INTEREST_PATTERNS = [
        "no me interesa",
        "no gracias",
        "ya tengo dentista",
        "no quiero más mensajes",
        "paren de escribirme",
        "no me escriban",
        "dejen de escribirme",
    ]
    _user_text_lower = (ctx.user_message or "").lower()
    if any(pat in _user_text_lower for pat in _NO_INTEREST_PATTERNS):
        try:
            from db import db as _db  # lazy — avoid circular
            await _db.pool.execute(
                "UPDATE chat_conversations SET no_followup = true WHERE tenant_id = $1 AND external_user_id = $2",
                ctx.tenant_id,
                ctx.phone_number,
            )
            try:
                from services.telegram_notifier import fire_telegram_notification
                _channel = ctx.extra.get("channel", "whatsapp") if hasattr(ctx, "extra") else "whatsapp"
                fire_telegram_notification(
                    "LEAD_RECOVERY_NOT_INTERESTED",
                    {
                        "tenant_id": ctx.tenant_id,
                        "lead_name": ctx.phone_number,
                        "phone": ctx.phone_number,
                        "channel": _channel,
                    },
                    ctx.tenant_id,
                )
            except Exception:
                pass
        except Exception:
            logger.warning("No-interest detection: failed to update chat_conversations")

    # Human override silence window → empty output, agent_used=handoff
    if state["patient_profile"].get("human_override_until"):
        duration_ms = int((time.perf_counter() - start) * 1000)
        return TurnResult(
            output="",
            agent_used="handoff",
            duration_ms=duration_ms,
            metadata={"reason": "human_override_silence", "turn_id": turn_id},
        )

    next_agent_name = "reception"

    # ── Phase 1: READ conversation_state anti-loop context ─────────────────
    # Mirror buffer_task.py:1898-2036. Cached in cs_data local var to avoid
    # double Redis GET (supervisor.route also calls get_state internally).
    cs_data: dict = {}
    try:
        from services.conversation_state import get_state as cs_get_state
        cs_data = await cs_get_state(ctx.tenant_id, ctx.phone_number)
        state["conversation_state_block"] = _build_convstate_injection_block(cs_data)
    except Exception as e:
        logger.debug(f"convstate READ skipped (non-fatal): {e}")
        state["conversation_state_block"] = ""

    try:
        async with asyncio.timeout(TURN_TIMEOUT_S):
            next_agent_name = await _supervisor.route(state)
            state["active_agent"] = next_agent_name
            state["hop_count"] = state.get("hop_count", 0) + 1

            agent = AGENTS.get(next_agent_name)
            if agent is None:
                next_agent_name = "reception"
                agent = AGENTS["reception"]

            # Track tokens via LangChain callback
            _cb = None
            try:
                from langchain_community.callbacks import get_openai_callback
                _cb = get_openai_callback()
                _cb.__enter__()
            except Exception:
                _cb = None

            state = await agent.run(state)

            # ── Phase 3: WRITE conversation_state outcomes ──────────────────
            # Best-effort, non-blocking — mirrors buffer_task.py WRITE hooks.
            try:
                await _write_convstate_outcomes(state, cs_data)
            except Exception as e:
                logger.warning(f"convstate WRITE hook failed (non-fatal): {e}")

            # Record token usage
            if _cb:
                try:
                    _cb.__exit__(None, None, None)
                    if _cb.total_tokens > 0:
                        from dashboard.token_tracker import track_service_usage
                        from db import db as _db
                        _m = (state.get("model_config") or {}).get("model", "unknown")
                        await track_service_usage(
                            _db.pool, state.get("tenant_id", 0), _m,
                            _cb.prompt_tokens, _cb.completion_tokens,
                            source=f"multi_agent/{next_agent_name}",
                            phone=state.get("phone_number", "system")
                        )
                except Exception:
                    pass
    except asyncio.TimeoutError:
        logger.error(f"Multi-agent turn timed out after {TURN_TIMEOUT_S}s")
        state["agent_output"] = "Disculpá, estoy tardando más de lo esperado. ¿Podés reformular tu mensaje?"
        next_agent_name = "timeout"
    except Exception:
        logger.exception("Multi-agent graph failed")
        state["agent_output"] = "Tuve un problema procesando tu mensaje. Te conecto con el equipo."
        next_agent_name = "error"

    duration_ms = int((time.perf_counter() - start) * 1000)

    # Best-effort audit log — use the REAL model that was configured for the tenant
    # (from state["model_config"]), not a hardcoded per-agent default
    model_used = (state.get("model_config") or {}).get("model") or "unknown"
    await _log_turn(state, next_agent_name, duration_ms, model_used)

    return TurnResult(
        output=state.get("agent_output", "") or "",
        agent_used=next_agent_name,
        duration_ms=duration_ms,
        metadata={
            "turn_id": turn_id,
            "hop_count": state.get("hop_count", 0),
            "tools_called": [t.get("tool") for t in state.get("tools_called", [])],
        },
    )


async def probe() -> "ProbeResult":
    """Health probe for the multi-agent graph.

    Runs supervisor routing on a fake minimal state with no LLM call
    (deterministic rules cover the greeting path). Pure code-path validation.
    """
    from services.engine_router import ProbeResult  # lazy — avoid circular
    start = time.perf_counter()

    try:
        from .model_resolver import get_default_model_config
        fake_state: AgentState = {
            "tenant_id": 0,
            "phone_number": "probe",
            "thread_id": "probe",
            "turn_id": "probe",
            "user_message": "hola",
            "patient_profile": {"human_override_until": None, "is_new_lead": True},
            "chat_history": [],
            "working_state": {},
            "model_config": get_default_model_config(),
            "active_agent": "supervisor",
            "hop_count": 0,
            "max_hops": MAX_HOPS,
            "agent_output": "",
            "tools_called": [],
            "handoff_reason": None,
            "start_time": start,
        }

        next_agent = await asyncio.wait_for(_supervisor.route(fake_state), timeout=5.0)
        latency_ms = int((time.perf_counter() - start) * 1000)

        if next_agent in AGENTS:
            return ProbeResult(
                ok=True,
                latency_ms=latency_ms,
                detail=f"Multi-agent graph healthy. Supervisor routed probe to '{next_agent}' in {latency_ms}ms.",
            )
        return ProbeResult(
            ok=False,
            latency_ms=latency_ms,
            error="Invalid routing",
            detail=f"Supervisor returned unknown agent '{next_agent}'",
        )
    except asyncio.TimeoutError:
        latency_ms = int((time.perf_counter() - start) * 1000)
        return ProbeResult(ok=False, latency_ms=latency_ms, error="Timeout", detail="Supervisor probe timed out after 5s")
    except Exception as e:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.exception("Multi-agent probe failed")
        return ProbeResult(ok=False, latency_ms=latency_ms, error=str(e), detail=f"Probe failed: {type(e).__name__}")
