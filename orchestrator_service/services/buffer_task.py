"""
process_buffer_task: invoca agente IA y envía respuesta por Chatwoot (o YCloud).
CLINICASV1.0 - integrado con chat_conversations; usa get_agent_executable_for_tenant (Vault).
"""

import logging
import json
import os
from typing import List

from db import get_pool
from langchain_core.messages import HumanMessage, AIMessage

try:
    from services.vision_service import analyze_attachments_batch, MAX_IMAGES, MAX_PDFS
except ImportError:
    analyze_attachments_batch = None
    MAX_IMAGES = 10
    MAX_PDFS = 5
try:
    from services.image_classifier import classify_message
except ImportError:
    classify_message = None
try:
    from services.attachment_summary import generate_attachment_summary
except ImportError:
    generate_attachment_summary = None

# Date validator for Bug #1 - post-LLM date validation
try:
    from services.date_validator import validate_dates_in_response
except ImportError:
    validate_dates_in_response = None

# Conversation state for Bug #4 - state machine
try:
    from services.conversation_state import get_state, set_state, reset, VALID_STATES
except ImportError:
    get_state = None
    set_state = None
    reset = None
    VALID_STATES = []

# State guard constants for Bug #4
MAX_STATE_RETRIES = 1

# Regex patterns for intent detection (Bug #4 Phase C)
_SELECTION_INTENT_PATTERN = None
_RESEARCH_INTENT_PATTERN = None

logger = logging.getLogger(__name__)


def compute_social_context(channel_type: str, tenant_row: dict) -> dict:
    """Compute social channel context for TurnContext.extra.

    Pure function — no I/O. Called from the engine dispatch point in
    _run_ai_for_phone to populate the 5 social keys before passing ctx to the
    engine router (multi path) or build_system_prompt (solo path).

    Args:
        channel_type: "instagram" | "facebook" | "whatsapp" | "chatwoot" | None
        tenant_row: asyncpg Record or dict from the tenants SELECT query.
                    Expected keys: social_ig_active, social_landings,
                    instagram_handle, facebook_page_id.  Missing keys default
                    to falsy values (backward compat).

    Returns:
        dict with keys: channel, is_social_channel, social_landings,
        instagram_handle, facebook_page_id.
    """
    effective_channel = channel_type or "whatsapp"
    is_social = (
        effective_channel in ("instagram", "facebook")
        and bool(tenant_row.get("social_ig_active", False))
    )

    # JSONB gotcha from CLAUDE.md: asyncpg may return JSONB columns as raw strings.
    # Parse defensively so callers always receive a dict or None.
    social_landings = tenant_row.get("social_landings") if is_social else None
    if isinstance(social_landings, str):
        try:
            social_landings = json.loads(social_landings)
        except (json.JSONDecodeError, ValueError):
            social_landings = None

    # Build wa.me link for social channels so the agent can send it post-booking
    bot_phone = tenant_row.get("bot_phone_number") or ""
    # Normalize: strip non-digits, ensure no leading +
    bot_phone_clean = re.sub(r"\D", "", bot_phone)
    whatsapp_link = f"https://wa.me/{bot_phone_clean}" if bot_phone_clean else None

    return {
        "channel": effective_channel,
        "is_social_channel": is_social,
        "social_landings": social_landings,
        "instagram_handle": tenant_row.get("instagram_handle") if is_social else None,
        "facebook_page_id": tenant_row.get("facebook_page_id") if is_social else None,
        "whatsapp_link": whatsapp_link if is_social else None,
    }


def _detect_selection_intent(msg: str) -> bool:
    """
    Detect if user message indicates they want to SELECT one of the offered slots.
    Used for Bug #4 Phase C - Input-side state guard.
    """
    import re

    global _SELECTION_INTENT_PATTERN
    if _SELECTION_INTENT_PATTERN is None:
        # Patterns for selecting an offered slot
        patterns = [
            # Numeric ordinals: "el 1", "el 1ro", "el 1°", "el 2do", "el 3er", etc.
            r"\bel\s+[0-9]+(?:ro|do|er|°)?\b",
            # Spanish ordinal words
            r"\bel\s+primero\b",   # "el primero"
            r"\bla\s+primera\b",   # "la primera"
            r"\bel\s+segundo\b",   # "el segundo"
            r"\bla\s+segunda\b",   # "la segunda"
            r"\bel\s+tercero\b",   # "el tercero"
            r"\bla\s+tercera\b",   # "la tercera"
            r"\bconfirmo\b",       # "confirmo", "confirmar"
            # "si" / "sí" as standalone affirmation (NOT as conjunction meaning "if")
            # Only match at start of short messages to avoid "si atienden" false positives
            r"^s[ií]$",            # exactly "si" or "sí"
            r"^s[ií]\b",           # "si," or "si!" or "sí," at start
            r"\bsí\b",             # accented "sí" anywhere (rarer as conjunction)
            r"\bquiero\s+ese\b",   # "quiero ese"
            r"\bagéndame\s+ese\b", # "agéndame ese"
            r"\breservar\b",       # "reservar"
            r"\b\d{1,2}\s*(de\s+)?(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)",  # "12 de mayo"
            r"\bde\s+la\s+tarde\b",   # "el de la tarde"
            r"\bde\s+la\s+ma[ñn]ana\b",  # "el de la mañana"
        ]
        combined = "|".join(patterns)
        _SELECTION_INTENT_PATTERN = re.compile(combined, re.IGNORECASE)

    text = msg.strip()
    return _SELECTION_INTENT_PATTERN.search(text) is not None


def _detect_research_intent(msg: str) -> bool:
    """
    Detect if user wants to SEARCH AGAIN / look for different slots.
    Used for Bug #4 Phase C - Input-side state guard.
    """
    import re

    global _RESEARCH_INTENT_PATTERN
    if _RESEARCH_INTENT_PATTERN is None:
        # Patterns for searching for different slots
        patterns = [
            r"\botra\s+fecha\b",  # "otra fecha"
            r"\botro\s+día\b",  # "otro día"
            r"\botra\s+hora\b",  # "otra hora"
            r"\botro\s+turno\b",  # "otro turno"
            r"\bbuscá\s+en\s+otra\b",  # "buscá en otra semana"
            r"\bno\s+me\s+sirve\b",  # "no me sirve"
            r"\bOTRO\b",  # "otro" (uppercase)
            r"\bCAMBIAR\b",  # "cambiar" (uppercase)
            r"\bOTRA\b",  # "otra" (uppercase)
            r"\bdiferente\b",  # "diferente"
        ]
        combined = "|".join(patterns)
        _RESEARCH_INTENT_PATTERN = re.compile(combined, re.IGNORECASE)

    text = msg.lower().strip()
    return _RESEARCH_INTENT_PATTERN.search(text) is not None


def classify_intent(messages: list) -> set:
    """
    Classify patient message intent via keyword detection (<1ms, no LLM).
    Returns a set of tags used to conditionally inject prompt sections.

    Tags: 'implant', 'media', 'payment'
    If no tags match, returns empty set — caller should inject all sections (safe default).
    """
    text = " ".join(messages).lower()
    tags = set()

    # Implant/prosthetics keywords
    implant_kw = [
        "implante",
        "prótesis",
        "protesis",
        "dentadura",
        "sin hueso",
        "no tengo hueso",
        "me rechazaron",
        "diente postizo",
        "dientes faltantes",
        "perdí un diente",
        "perdi un diente",
        "perdí varios",
        "perdi varios",
        "quiero algo fijo",
        "no tengo dientes",
        "se me cayeron",
    ]
    if any(kw in text for kw in implant_kw):
        tags.add("implant")

    # Media/attachment keywords (supplement has_recent_media flag from buffer_task)
    media_kw = [
        "foto",
        "imagen",
        "adjunto",
        "archivo",
        "radiografía",
        "radiografia",
        "tomografía",
        "tomografia",
        "estudio",
        "panorámica",
        "panoramica",
    ]
    if any(kw in text for kw in media_kw):
        tags.add("media")

    # Payment keywords
    payment_kw = [
        "pagar",
        "pago",
        "seña",
        "sena",
        "transferencia",
        "comprobante",
        "cuánto debo",
        "cuanto debo",
        "saldo",
        "cuota",
        "deuda",
        "factura",
        "recibo",
        "abonar",
    ]
    if any(kw in text for kw in payment_kw):
        tags.add("payment")

    return tags


async def process_buffer_task(
    tenant_id: int,
    conversation_id: str,
    external_user_id: str,
    messages: List[str],
    provider: str = None,
    channel: str = None,
) -> None:
    pool = get_pool()
    row = await pool.fetchrow(
        """
        SELECT provider, external_chatwoot_id, external_account_id, channel
        FROM chat_conversations
        WHERE id = $1 AND tenant_id = $2
        """,
        conversation_id,
        tenant_id,
    )
    if not row:
        logger.warning(
            "process_buffer_task_conversation_not_found", conv_id=conversation_id
        )
        return
    provider = row["provider"] or "chatwoot"
    logger.info(
        f"🦾 Processing Buffer Task | tenant={tenant_id} conv={conversation_id} user={external_user_id} provider={provider} msgs={len(messages)}"
    )

    if not messages:
        return

    # Spec 24: Human Override Check (Parity)
    # Check if human took control during buffer wait
    override_row = await pool.fetchrow(
        "SELECT human_override_until FROM chat_conversations WHERE id = $1",
        conversation_id,
    )
    if override_row and override_row["human_override_until"]:
        from datetime import datetime, timezone

        now_utc = datetime.now(timezone.utc)
        override_until = override_row["human_override_until"]
        if override_until.tzinfo is None:
            override_until = override_until.replace(tzinfo=timezone.utc)
        else:
            override_until = override_until.astimezone(timezone.utc)

        if override_until > now_utc:
            logger.info(
                f"🔇 Buffer task silenced by Human Override until {override_until} for {external_user_id}"
            )
            return

    # Invocar agente con clave por tenant (Vault)
    try:
        from main import (
            get_agent_executable_for_tenant,
            build_system_prompt,
            get_now_arg,
            normalize_phone_digits,
            CLINIC_NAME,
            CLINIC_HOURS_START,
            CLINIC_HOURS_END,
            db,  # Import db wrapper for get_chat_history
            current_customer_phone,
            current_tenant_id,
            current_patient_id,
            current_source_channel,
            current_tenant_tz,
        )

        # C3: Engine router for dual-engine system (solo/multi)
        from services.engine_router import get_engine_for_tenant

        # ✅ FIX: Establecer ContextVars para que las tools (book_appointment, etc)
        # puedan identificar al paciente en la tarea background
        current_customer_phone.set(external_user_id)
        current_tenant_id.set(tenant_id)
        current_source_channel.set(channel or "whatsapp")

        # TIER 3 cap.1 — resolve tenant timezone once per request and bind it.
        # All datetime constructors via get_active_tz() / get_now_arg() will honor it.
        try:
            from services.tz_resolver import get_tenant_tz as _get_tz

            _resolved_tz = await _get_tz(tenant_id)
            current_tenant_tz.set(_resolved_tz)
        except Exception as _tz_err:
            # Never block the booking flow on tz resolution failure — fallback to ARG_TZ.
            import logging as _lg

            _lg.getLogger("buffer_task").warning(
                f"tz_resolver: failed for tenant {tenant_id}, falling back to ARG_TZ: {_tz_err}"
            )

        tenant_row = await pool.fetchrow(
            """SELECT clinic_name, address, google_maps_url, working_hours,
                      consultation_price, bank_cbu, bank_alias, bank_holder_name,
                      system_prompt_template, bot_name,
                      payment_methods, financing_available, max_installments,
                      installments_interest_free, financing_provider, financing_notes,
                      cash_discount_percent, accepts_crypto,
                      accepts_pregnant_patients, pregnancy_restricted_treatments,
                      pregnancy_notes, accepts_pediatric, min_pediatric_age_years,
                      pediatric_notes, high_risk_protocols, requires_anamnesis_before_booking,
                      complaint_escalation_email, complaint_escalation_phone,
                      expected_wait_time_minutes, revision_policy, review_platforms,
                      complaint_handling_protocol, auto_send_review_link_after_followup,
                      social_ig_active, social_landings, instagram_handle, facebook_page_id,
                      bot_phone_number
               FROM tenants WHERE id = $1""",
            tenant_id,
        )
        clinic_name = (
            (tenant_row["clinic_name"] or CLINIC_NAME) if tenant_row else CLINIC_NAME
        )
        # Editable bot display name (migration 033). NULL or empty → fallback to "TORA".
        bot_name = (
            (tenant_row.get("bot_name") or "TORA") if tenant_row else "TORA"
        )
        clinic_address = (tenant_row["address"] or "") if tenant_row else ""
        clinic_maps_url = (tenant_row["google_maps_url"] or "") if tenant_row else ""
        consultation_price = (
            float(tenant_row["consultation_price"])
            if tenant_row and tenant_row.get("consultation_price")
            else None
        )
        bank_cbu = (tenant_row["bank_cbu"] or "") if tenant_row else ""
        bank_alias = (tenant_row["bank_alias"] or "") if tenant_row else ""
        bank_holder_name = (tenant_row["bank_holder_name"] or "") if tenant_row else ""

        # Payment & financing (migración 035). asyncpg puede devolver JSONB como
        # string en algunas versiones → parse defensivo idéntico al de working_hours.
        _pm_raw = tenant_row.get("payment_methods") if tenant_row else None
        if isinstance(_pm_raw, str):
            try:
                _pm_raw = json.loads(_pm_raw)
            except (json.JSONDecodeError, TypeError):
                _pm_raw = []
        payment_methods = _pm_raw if isinstance(_pm_raw, list) else []
        financing_available = bool(
            tenant_row.get("financing_available") if tenant_row else False
        )
        max_installments = (
            tenant_row.get("max_installments") if tenant_row else None
        )
        _iif = (
            tenant_row.get("installments_interest_free") if tenant_row else None
        )
        installments_interest_free = bool(_iif) if _iif is not None else True
        financing_provider = (
            (tenant_row.get("financing_provider") or "") if tenant_row else ""
        )
        financing_notes = (
            (tenant_row.get("financing_notes") or "") if tenant_row else ""
        )
        _cdp = tenant_row.get("cash_discount_percent") if tenant_row else None
        try:
            cash_discount_percent = float(_cdp) if _cdp is not None else None
        except (TypeError, ValueError):
            cash_discount_percent = None
        accepts_crypto = bool(
            tenant_row.get("accepts_crypto") if tenant_row else False
        )

        # --- Clinic special conditions (migración 036) ---
        # Computamos el bloque pre-formateado acá para que build_system_prompt
        # sólo reciba un string (wiring simple, testeable y non-fatal).
        special_conditions_block = ""
        try:
            if tenant_row:
                # Resolver treatment_name_map para mostrar nombres amigables
                treatment_name_map: dict = {}
                try:
                    _tt_rows = await pool.fetch(
                        "SELECT code, COALESCE(patient_display_name, name) AS display_name "
                        "FROM treatment_types WHERE tenant_id = $1 AND is_active = true",
                        tenant_id,
                    )
                    treatment_name_map = {
                        r["code"]: r["display_name"] for r in _tt_rows
                    }
                except Exception:
                    treatment_name_map = {}

                from main import _format_special_conditions

                special_conditions_block = _format_special_conditions(
                    dict(tenant_row),
                    treatment_name_map=treatment_name_map,
                )
        except Exception as _sc_err:
            logger.debug(
                f"_format_special_conditions skipped (non-fatal): {_sc_err}"
            )
            special_conditions_block = ""

        # --- Clinic support / complaints / review config (migration 039) ---
        support_policy_block = ""
        try:
            if tenant_row:
                from main import _format_support_policy

                support_policy_block = _format_support_policy(dict(tenant_row))
        except Exception as _sp_err:
            logger.debug(
                f"_format_support_policy skipped (non-fatal): {_sp_err}"
            )
            support_policy_block = ""

        system_prompt_template = (
            (tenant_row.get("system_prompt_template") or "") if tenant_row else ""
        )
        # Normalize whitespace in the tenant-configured greeting/specialty pitch.
        # The UI textarea may save it with hard line-breaks and leading spaces
        # (Python triple-quoted style), which then leak into the WhatsApp/IG/FB
        # message as visible indented broken lines. We collapse single newlines
        # into spaces, preserve intentional double-newlines as paragraph breaks,
        # and strip per-line leading/trailing whitespace.
        if system_prompt_template:
            import re as _re

            _paragraphs = _re.split(r"\n\s*\n", system_prompt_template)
            _clean_paragraphs = []
            for _p in _paragraphs:
                # Join wrapped lines into a single line, collapse repeated spaces
                _flat = " ".join(
                    line.strip() for line in _p.splitlines() if line.strip()
                )
                _flat = _re.sub(r"[ \t]{2,}", " ", _flat).strip()
                if _flat:
                    _clean_paragraphs.append(_flat)
            system_prompt_template = "\n\n".join(_clean_paragraphs)
        clinic_working_hours = None
        if tenant_row and tenant_row.get("working_hours"):
            wh = tenant_row["working_hours"]
            clinic_working_hours = json.loads(wh) if isinstance(wh, str) else wh

        # Resolve lead professional name for prompt positioning
        lead_professional_name = ""
        try:
            prof_row = await pool.fetchrow(
                "SELECT first_name, last_name FROM professionals WHERE tenant_id = $1 AND is_active = true ORDER BY id ASC LIMIT 1",
                tenant_id,
            )
            if prof_row:
                lead_professional_name = f"{prof_row['first_name']} {prof_row.get('last_name', '') or ''}".strip()
        except Exception:
            pass

        # Fetch FAQs for this tenant (no limit — RAG will select relevant ones)
        faq_rows = await pool.fetch(
            "SELECT category, question, answer FROM clinic_faqs WHERE tenant_id = $1 ORDER BY sort_order ASC, id ASC",
            tenant_id,
        )
        faqs = [dict(r) for r in faq_rows] if faq_rows else []

        # Fetch insurance providers for this tenant (migration 034 shape)
        insurance_providers = []
        try:
            ins_rows = await pool.fetch(
                """
                SELECT id, provider_name, status, coverage_by_treatment, is_prepaid,
                       employee_discount_percent, default_copay_percent, external_target,
                       requires_copay, copay_notes, ai_response_template
                FROM tenant_insurance_providers
                WHERE tenant_id = $1 AND is_active = true
                ORDER BY sort_order, provider_name
                """,
                tenant_id,
            )
            insurance_providers = []
            for r in ins_rows or []:
                d = dict(r)
                # asyncpg may return JSONB as a string in some versions
                if isinstance(d.get("coverage_by_treatment"), str):
                    try:
                        import json as _json_cov
                        d["coverage_by_treatment"] = _json_cov.loads(
                            d["coverage_by_treatment"]
                        )
                    except (ValueError, TypeError):
                        d["coverage_by_treatment"] = {}
                insurance_providers.append(d)
        except Exception as ins_err:
            logger.debug(f"Insurance providers fetch (non-fatal): {ins_err}")

        # Fetch active treatment types for treatment_display_map in the prompt
        # (used by _format_insurance_providers to render human-readable names).
        treatment_types_list = []
        try:
            tt_rows = await pool.fetch(
                """
                SELECT code, name, patient_display_name
                FROM treatment_types
                WHERE tenant_id = $1 AND is_active = true
                ORDER BY name
                """,
                tenant_id,
            )
            treatment_types_list = [dict(r) for r in tt_rows] if tt_rows else []
        except Exception as tt_err:
            logger.debug(f"Treatment types fetch (non-fatal): {tt_err}")

        # Fetch derivation rules for this tenant (migration 038: includes
        # escalation fallback fields and enriches with fallback_professional_name
        # via a second LEFT JOIN so the prompt formatter can render the
        # full escalation block).
        derivation_rules = []
        try:
            der_rows = await pool.fetch(
                """
                SELECT dr.id, dr.rule_name, dr.patient_condition, dr.treatment_categories,
                       dr.target_type, dr.target_professional_id, dr.priority_order,
                       dr.enable_escalation, dr.fallback_professional_id,
                       dr.fallback_team_mode, dr.max_wait_days_before_escalation,
                       dr.escalation_message_template,
                       p.first_name AS target_professional_name,
                       fp.first_name AS fallback_professional_name
                FROM professional_derivation_rules dr
                LEFT JOIN professionals p ON dr.target_professional_id = p.id
                LEFT JOIN professionals fp ON dr.fallback_professional_id = fp.id
                WHERE dr.tenant_id = $1 AND dr.is_active = true
                ORDER BY dr.priority_order ASC, dr.id ASC
                """,
                tenant_id,
            )
            derivation_rules = [dict(r) for r in der_rows] if der_rows else []
        except Exception as der_err:
            logger.debug(f"Derivation rules fetch (non-fatal): {der_err}")

        # --- PATIENT MEMORY SYSTEM: Ensure table exists (first call only) ---
        try:
            from services.patient_memory import (
                ensure_memory_table,
                format_memories_for_prompt,
                extract_and_store_memories,
            )

            await ensure_memory_table(pool)
        except Exception as mem_init_err:
            logger.warning(f"⚠️ Patient memory init (non-fatal): {mem_init_err}")

        # Spec 24 / Spec 06 / v7.6: Patient Identity & Appointment Context
        # Fetch patient data — search by phone (WhatsApp) or PSID (Instagram/Facebook)
        phone_digits = normalize_phone_digits(external_user_id)
        patient_row = await pool.fetchrow(
            """SELECT id, first_name, last_name, dni, email, phone_number, acquisition_source, anamnesis_token, medical_history, assigned_professional_id FROM patients
               WHERE tenant_id = $1 AND (
                   REGEXP_REPLACE(phone_number, '[^0-9]', '', 'g') = $2
                   OR instagram_psid = $3
                   OR facebook_psid = $3
               )""",
            tenant_id,
            phone_digits,
            external_user_id,
        )

        patient_context = ""
        ad_context = ""
        patient_status = "new_lead"
        anamnesis_url = ""

        if patient_row:
            p_id = patient_row["id"]
            p_first = patient_row["first_name"] or ""
            p_last = patient_row["last_name"] or ""
            p_dni = patient_row["dni"] or ""

            # 1. Building Identity Context
            identity_lines = []
            if p_first or p_last:
                identity_lines.append(
                    f"• Nombre registrado: {p_first} {p_last}".strip()
                )
            if p_dni:
                identity_lines.append(f"• DNI registrado: {p_dni}")

            # Phone — check if patient has a real phone number in DB
            p_phone = patient_row.get("phone_number") or ""
            p_phone_is_real = p_phone and not p_phone.startswith("SIN-TEL")
            if p_phone_is_real:
                identity_lines.append(f"• Teléfono registrado: {p_phone}")

            # Email
            p_email = patient_row.get("email") or ""
            if p_email:
                identity_lines.append(f"• Email registrado: {p_email}")

            # Assigned Professional (persistent patient→professional relationship)
            assigned_prof_id = patient_row.get("assigned_professional_id")
            if assigned_prof_id:
                try:
                    assigned_prof = await pool.fetchrow(
                        "SELECT first_name, last_name FROM professionals WHERE id = $1 AND tenant_id = $2 AND is_active = true",
                        assigned_prof_id,
                        tenant_id,
                    )
                    if assigned_prof:
                        assigned_name = f"{assigned_prof['first_name']} {assigned_prof.get('last_name', '') or ''}".strip()
                        identity_lines.append(
                            f"• PROFESIONAL ASIGNADO: Dr/a. {assigned_name} — Este paciente es paciente habitual de este profesional. "
                            f"PRIORIDAD ALTA por ser paciente propio (independientemente de la complejidad del tratamiento). "
                            f"Si menciona DOLOR → prioridad inmediata/urgencia. Sin dolor → prioridad media. "
                            f"SIEMPRE ofrecer turnos con este profesional primero. Si no hay disponibilidad, "
                            f"mencionar que es su profesional habitual y ofrecer la próxima fecha disponible."
                        )
                except Exception:
                    pass

            # 2. Building Ad Context (Spec 06)
            meta_headline = ""  # Already in patient_row if we joined or updated, checking current db state
            # Acquisition source check
            meta_source = patient_row.get("acquisition_source") or ""

            # Quick check for meta headline if not in main row (some schemas store it differently)
            # For simplicity, we assume attributes might have it or use what's in 'patients'

            # 3. Fetching Next Appointment Context
            next_apt = await pool.fetchrow(
                """
                SELECT a.appointment_datetime, tt.name as treatment_name, 
                       prof.first_name as professional_name
                FROM appointments a
                LEFT JOIN treatment_types tt ON a.appointment_type = tt.code
                LEFT JOIN professionals prof ON a.professional_id = prof.id
                WHERE a.tenant_id = $1 AND a.patient_id = $2 
                AND a.appointment_datetime >= NOW()
                AND a.status IN ('scheduled', 'confirmed')
                ORDER BY a.appointment_datetime ASC
                LIMIT 1
            """,
                tenant_id,
                p_id,
            )

            if next_apt:
                dt = next_apt["appointment_datetime"]
                from main import get_active_tz

                if hasattr(dt, "astimezone"):
                    dt = dt.astimezone(get_active_tz())
                dias_semana = [
                    "Lunes",
                    "Martes",
                    "Miércoles",
                    "Jueves",
                    "Viernes",
                    "Sábado",
                    "Domingo",
                ]
                dia_nombre = dias_semana[dt.weekday()]
                dt_str = f"{dia_nombre} {dt.strftime('%d/%m/%Y')} a las {dt.strftime('%H:%M')}"
                # Tiempo hasta turno para saludo proactivo
                now_arg = get_now_arg()
                delta = dt - now_arg
                total_hours = delta.total_seconds() / 3600.0
                if total_hours < 0.5:
                    time_until = "menos de 30 minutos"
                elif total_hours < 1:
                    time_until = "menos de 1 hora"
                elif total_hours < 24:
                    h = int(total_hours)
                    time_until = f"faltan {h} {'hora' if h == 1 else 'horas'}"
                elif total_hours < 48:
                    time_until = f"mañana a las {dt.strftime('%H:%M')}"
                else:
                    time_until = f"el {dt_str}"
                identity_lines.append(
                    f"• PRÓXIMO TURNO: Tiene un turno de {next_apt['treatment_name'] or 'Consulta'} con el/la Dr/a. {next_apt['professional_name']} el {dt_str}."
                )
                identity_lines.append(
                    f"• FECHA EXACTA DEL TURNO: {dt.strftime('%d/%m/%Y')} a las {dt.strftime('%H:%M')}. {time_until}."
                )

            # 3b. Fetch LAST completed appointment (for post-treatment follow-up)
            last_apt = await pool.fetchrow(
                """
                SELECT a.appointment_datetime, tt.name as treatment_name,
                       prof.first_name as professional_name, a.status
                FROM appointments a
                LEFT JOIN treatment_types tt ON a.appointment_type = tt.code
                LEFT JOIN professionals prof ON a.professional_id = prof.id
                WHERE a.tenant_id = $1 AND a.patient_id = $2
                AND a.appointment_datetime < NOW()
                AND a.status IN ('completed', 'confirmed', 'scheduled')
                ORDER BY a.appointment_datetime DESC
                LIMIT 1
            """,
                tenant_id,
                p_id,
            )

            if last_apt:
                ldt = last_apt["appointment_datetime"]
                if hasattr(ldt, "astimezone"):
                    from main import get_active_tz as _get_tz

                    ldt = ldt.astimezone(_get_tz())
                ldias = [
                    "Lunes",
                    "Martes",
                    "Miércoles",
                    "Jueves",
                    "Viernes",
                    "Sábado",
                    "Domingo",
                ]
                ldt_str = f"{ldias[ldt.weekday()]} {ldt.strftime('%d/%m/%Y')} a las {ldt.strftime('%H:%M')}"
                days_since = (
                    (now_arg - ldt).days
                    if "now_arg" in dir()
                    else (get_now_arg() - ldt).days
                )
                identity_lines.append(
                    f"• ÚLTIMO TURNO: {last_apt['treatment_name'] or 'Consulta'} con Dr/a. {last_apt['professional_name']} el {ldt_str} (hace {days_since} días). Estado: {last_apt['status']}."
                )
                if days_since <= 7:
                    identity_lines.append(
                        f"• SEGUIMIENTO POST-TRATAMIENTO: El paciente tuvo un turno hace {days_since} días. Si escribe, preguntale cómo se siente después del tratamiento."
                    )

            # 3c. Count total visits (recurrent vs first-timer)
            visit_count = await pool.fetchval(
                """
                SELECT COUNT(*) FROM appointments
                WHERE tenant_id = $1 AND patient_id = $2
                AND status IN ('completed', 'confirmed', 'scheduled')
            """,
                tenant_id,
                p_id,
            )
            if visit_count and visit_count > 1:
                identity_lines.append(
                    f"• HISTORIAL: Paciente recurrente ({visit_count} turnos registrados)."
                )
            elif visit_count == 1:
                identity_lines.append("• HISTORIAL: Primera visita del paciente.")

            # Determine patient_status
            if next_apt:
                patient_status = "patient_with_appointment"
                # Resolve sede for appointment day
                if clinic_working_hours:
                    days_en = [
                        "monday",
                        "tuesday",
                        "wednesday",
                        "thursday",
                        "friday",
                        "saturday",
                        "sunday",
                    ]
                    apt_day_en = days_en[dt.weekday()]
                    apt_day_cfg = clinic_working_hours.get(apt_day_en, {})
                    if apt_day_cfg.get("location"):
                        identity_lines.append(
                            f"• SEDE DEL TURNO: {apt_day_cfg['location']}"
                        )
                        if apt_day_cfg.get("address"):
                            identity_lines.append(
                                f"• DIRECCIÓN SEDE: {apt_day_cfg['address']}"
                            )
                        if apt_day_cfg.get("maps_url"):
                            identity_lines.append(
                                f"• MAPS SEDE: {apt_day_cfg['maps_url']}"
                            )
            else:
                patient_status = "patient_no_appointment"

            # Generate anamnesis URL (always — patient may need to update)
            import uuid as uuid_mod

            anamnesis_token = (
                patient_row.get("anamnesis_token") if patient_row else None
            )
            if not anamnesis_token:
                anamnesis_token = str(uuid_mod.uuid4())
                await pool.execute(
                    "UPDATE patients SET anamnesis_token = $1 WHERE id = $2 AND tenant_id = $3",
                    anamnesis_token,
                    p_id,
                    tenant_id,
                )
            frontend_url = (
                os.getenv("FRONTEND_URL", "http://localhost:4173")
                .split(",")[0]
                .strip()
                .rstrip("/")
            )
            anamnesis_url = f"{frontend_url}/anamnesis/{tenant_id}/{anamnesis_token}"

            # Check if anamnesis is already completed
            mh = patient_row.get("medical_history")
            if isinstance(mh, str):
                mh = json.loads(mh) if mh else {}
            anamnesis_completed = bool(
                mh and isinstance(mh, dict) and mh.get("anamnesis_completed_at")
            )
            if anamnesis_completed:
                identity_lines.append(
                    "• ANAMNESIS: Ya completó su ficha médica (NO enviar link automáticamente al agendar, SOLO si el paciente pide actualizar)."
                )

            # Load linked minor patients (children) via guardian_phone
            minor_rows = await pool.fetch(
                "SELECT id, first_name, last_name, dni, phone_number, anamnesis_token FROM patients WHERE tenant_id = $1 AND guardian_phone = $2",
                tenant_id,
                external_user_id,
            )
            if minor_rows:
                identity_lines.append("• HIJOS/MENORES VINCULADOS:")
                for minor in minor_rows:
                    m_name = (
                        f"{minor['first_name']} {minor.get('last_name', '')}".strip()
                    )
                    m_token = minor.get("anamnesis_token")
                    if not m_token:
                        m_token = str(uuid_mod.uuid4())
                        await pool.execute(
                            "UPDATE patients SET anamnesis_token = $1 WHERE id = $2",
                            m_token,
                            minor["id"],
                        )
                    m_anamnesis = f"{frontend_url}/anamnesis/{tenant_id}/{m_token}"
                    identity_lines.append(
                        f"  - {m_name} (DNI: {minor.get('dni', 'N/A')}, phone_interno: {minor['phone_number']}, link ficha: {m_anamnesis})"
                    )
                    # Check minor's next appointment
                    minor_apt = await pool.fetchrow(
                        """
                        SELECT a.appointment_datetime, tt.name as treatment_name, prof.first_name as professional_name
                        FROM appointments a
                        LEFT JOIN treatment_types tt ON a.appointment_type = tt.code
                        LEFT JOIN professionals prof ON a.professional_id = prof.id
                        WHERE a.tenant_id = $1 AND a.patient_id = $2 AND a.appointment_datetime >= NOW() AND a.status IN ('scheduled', 'confirmed')
                        ORDER BY a.appointment_datetime ASC LIMIT 1
                    """,
                        tenant_id,
                        minor["id"],
                    )
                    if minor_apt:
                        mdt = minor_apt["appointment_datetime"]
                        if hasattr(mdt, "astimezone"):
                            from main import get_active_tz as _get_tz

                            mdt = mdt.astimezone(_get_tz())
                        identity_lines.append(
                            f"    Próximo turno: {minor_apt['treatment_name'] or 'Consulta'} el {dias_semana[mdt.weekday()]} {mdt.strftime('%d/%m')} a las {mdt.strftime('%H:%M')}"
                        )

            # --- TREATMENT PLAN / BUDGET CONTEXT ---
            try:
                plan_row = await pool.fetchrow(
                    """
                    SELECT tp.id, tp.name, tp.status, tp.estimated_total, tp.approved_total,
                           tp.notes,
                           COALESCE(SUM(tpp.amount), 0) AS total_paid
                    FROM treatment_plans tp
                    LEFT JOIN treatment_plan_payments tpp ON tpp.plan_id = tp.id AND tpp.tenant_id = tp.tenant_id
                    WHERE tp.tenant_id = $1 AND tp.patient_id = $2
                      AND tp.status IN ('draft', 'approved', 'in_progress')
                    GROUP BY tp.id
                    ORDER BY tp.created_at DESC
                    LIMIT 1
                    """,
                    tenant_id,
                    p_id,
                )
                if plan_row:
                    approved = float(
                        plan_row["approved_total"] or plan_row["estimated_total"] or 0
                    )
                    paid = float(plan_row["total_paid"] or 0)
                    pending = round(approved - paid, 2)

                    # Parse budget config from notes JSON
                    budget_cfg = {}
                    if plan_row["notes"]:
                        try:
                            budget_cfg = (
                                json.loads(plan_row["notes"])
                                if isinstance(plan_row["notes"], str)
                                else plan_row["notes"]
                            )
                        except Exception:
                            budget_cfg = {}

                    installments = int(budget_cfg.get("installments") or 1)
                    per_installment = (
                        round(pending / installments, 2)
                        if installments > 0 and pending > 0
                        else 0
                    )

                    identity_lines.append("")
                    identity_lines.append("PRESUPUESTO ACTIVO:")
                    identity_lines.append(f"  Plan: {plan_row['name']}")
                    identity_lines.append(f"  Estado: {plan_row['status']}")
                    identity_lines.append(
                        f"  Total aprobado: ${approved:,.0f}".replace(",", ".")
                    )
                    identity_lines.append(f"  Pagado: ${paid:,.0f}".replace(",", "."))
                    identity_lines.append(
                        f"  Pendiente: ${pending:,.0f}".replace(",", ".")
                    )
                    if installments > 1:
                        identity_lines.append(
                            f"  Cuotas: {installments} (${per_installment:,.0f}/cuota)".replace(
                                ",", "."
                            )
                        )
                    discount_pct = float(budget_cfg.get("discount_pct") or 0)
                    discount_amt = float(budget_cfg.get("discount_amount") or 0)
                    if discount_pct > 0:
                        identity_lines.append(f"  Descuento: {discount_pct}%")
                    if discount_amt > 0:
                        identity_lines.append(
                            f"  Descuento fijo: ${discount_amt:,.0f}".replace(",", ".")
                        )
                    conditions = budget_cfg.get("payment_conditions")
                    if conditions:
                        identity_lines.append(f"  Condiciones: {conditions}")
                    logger.info(
                        f"💰 Treatment plan context injected for patient {p_id}"
                    )
            except Exception as plan_err:
                logger.warning(f"⚠️ Treatment plan context (non-fatal): {plan_err}")

            # --- PATIENT MEMORY: Retrieve persistent memories ---
            try:
                memory_query = " ".join(messages) if messages else ""
                memory_text = await format_memories_for_prompt(
                    pool, external_user_id, tenant_id, query=memory_query
                )
                if memory_text:
                    identity_lines.append("")
                    identity_lines.append(memory_text)
                    logger.info(f"🧠 Patient memories injected for {external_user_id}")
            except Exception as mem_err:
                logger.warning(f"⚠️ Memory retrieval (non-fatal): {mem_err}")

            if identity_lines:
                patient_context = "\n".join(identity_lines)

        now = get_now_arg()
        dias = [
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado",
            "Domingo",
        ]
        current_time_str = f"{dias[now.weekday()]} {now.strftime('%d/%m/%Y %H:%M')}"

        # RAG: Unified semantic search across FAQs, insurance, derivation, instructions
        rag_faqs_section = ""
        rag_insurance_section = ""
        rag_derivation_section = ""
        rag_instructions_section = ""
        try:
            from services.embedding_service import format_all_context_with_rag

            user_text_for_rag = " ".join(messages) if messages else ""
            rag_context = await format_all_context_with_rag(
                tenant_id, user_text_for_rag, faqs
            )
            rag_faqs_section = rag_context.get("faqs_section", "")
            rag_insurance_section = rag_context.get("insurance_section", "")
            rag_derivation_section = rag_context.get("derivation_section", "")
            rag_instructions_section = rag_context.get("instructions_section", "")
        except Exception as rag_err:
            logger.debug(f"RAG context fallback (non-fatal): {rag_err}")
            # Fallback to old FAQ-only RAG
            try:
                from services.embedding_service import format_faqs_with_rag

                user_text_for_rag = " ".join(messages) if messages else ""
                rag_faqs_section = await format_faqs_with_rag(
                    tenant_id, user_text_for_rag, faqs
                )
            except Exception:
                pass

        # Obtener feriados próximos para inyectar en el prompt
        _upcoming_holidays = []
        try:
            from services.holiday_service import get_upcoming_holidays

            _upcoming_holidays = await get_upcoming_holidays(
                db.pool, tenant_id, days_ahead=30
            )
        except Exception as hol_err:
            logger.debug(f"Holiday fetch fallback (non-fatal): {hol_err}")

        # Classify intent for conditional prompt injection (keyword-based, <1ms)
        intent_tags = classify_intent(messages)
        # Supplement with pending payment context from patient data
        if patient_context and (
            "payment_status" in patient_context.lower()
            or "pendiente" in patient_context.lower()
        ):
            intent_tags.add("payment")

        # Bug #8: Check greeting state to avoid repeating institutional greeting
        is_greeting_pending = True
        try:
            from services.greeting_state import has_greeted

            is_greeting_pending = not await has_greeted(tenant_id, external_user_id)
        except Exception:
            pass  # Conservative fallback: greet if check fails

        system_prompt = build_system_prompt(
            clinic_name=clinic_name,
            current_time=current_time_str,
            response_language="es",
            hours_start=CLINIC_HOURS_START,
            hours_end=CLINIC_HOURS_END,
            ad_context=ad_context,
            patient_context=patient_context,
            clinic_address=clinic_address,
            clinic_maps_url=clinic_maps_url,
            clinic_working_hours=clinic_working_hours,
            faqs=faqs if not rag_faqs_section else None,
            patient_status=patient_status,
            consultation_price=consultation_price,
            anamnesis_url=anamnesis_url,
            bank_cbu=bank_cbu,
            bank_alias=bank_alias,
            bank_holder_name=bank_holder_name,
            upcoming_holidays=_upcoming_holidays,
            insurance_providers=insurance_providers
            if not rag_insurance_section
            else None,
            derivation_rules=derivation_rules if not rag_derivation_section else None,
            specialty_pitch=system_prompt_template,
            professional_name=lead_professional_name,
            bot_name=bot_name,
            intent_tags=intent_tags,
            is_greeting_pending=is_greeting_pending,
            treatment_types=treatment_types_list,
            # Payment & financing (migración 035)
            payment_methods=payment_methods,
            financing_available=financing_available,
            max_installments=max_installments,
            installments_interest_free=installments_interest_free,
            financing_provider=financing_provider,
            financing_notes=financing_notes,
            cash_discount_percent=cash_discount_percent,
            accepts_crypto=accepts_crypto,
            # Clinic special conditions (migración 036)
            special_conditions_block=special_conditions_block,
            support_policy_block=support_policy_block,
        )

        # Inject RAG context sections if available
        rag_sections = [
            s
            for s in [
                rag_faqs_section,
                rag_insurance_section,
                rag_derivation_section,
                rag_instructions_section,
            ]
            if s
        ]
        if rag_sections:
            system_prompt += "\n\n" + "\n\n".join(rag_sections)

        chat_history = []
        vision_context_str = ""
        audio_context_str = ""
        seen_multimodal = set()

        # --- Wait for pending audio transcriptions before processing ---
        # Check if recent messages have audio without transcription and wait up to 15s
        try:
            pending_audio = await pool.fetch(
                """
                SELECT id, content_attributes FROM chat_messages
                WHERE conversation_id = $1 AND tenant_id = $2
                AND content_attributes::text LIKE '%audio%'
                AND content_attributes::text NOT LIKE '%transcription%'
                ORDER BY created_at DESC LIMIT 3
            """,
                conversation_id,
                tenant_id,
            )
            if pending_audio:
                import asyncio as _asyncio

                logger.info(
                    f"🎙️ Esperando transcripción de {len(pending_audio)} audio(s)..."
                )
                for attempt in range(6):  # Max 15 seconds (6 x 2.5s)
                    await _asyncio.sleep(2.5)
                    # Re-check if transcriptions are now available
                    still_pending = await pool.fetchval(
                        """
                        SELECT COUNT(*) FROM chat_messages
                        WHERE id = ANY($1) AND content_attributes::text NOT LIKE '%transcription%'
                    """,
                        [r["id"] for r in pending_audio],
                    )
                    if not still_pending or still_pending == 0:
                        logger.info(
                            f"✅ Transcripciones completadas tras {(attempt + 1) * 2.5}s"
                        )
                        break
                else:
                    logger.warning(
                        f"⚠️ Timeout esperando transcripciones. Procesando sin audio."
                    )
        except Exception as audio_wait_err:
            logger.warning(f"⚠️ Error checking pending transcriptions: {audio_wait_err}")

        def extract_multimodal(msg_attrs):
            nonlocal vision_context_str, audio_context_str
            if not msg_attrs:
                return
            try:
                attrs = msg_attrs
                if isinstance(attrs, str):
                    import json

                    attrs = json.loads(attrs)
                if isinstance(attrs, list):
                    for att in attrs:
                        # Vision
                        desc = att.get("description")
                        if desc and desc not in seen_multimodal:
                            vision_context_str += f"\n[IMAGEN: {desc}]"
                            seen_multimodal.add(desc)
                        # Audio (Spec 21/28)
                        trans = att.get("transcription")
                        if trans and trans not in seen_multimodal:
                            audio_context_str += f"\n[AUDIO: {trans}]"
                            seen_multimodal.add(trans)
            except Exception:
                pass

        # 4. Fetching Recent History (Spec 23)
        # Re-fetch AFTER transcription wait to get updated content_attributes
        db_history_dicts = await db.get_chat_history(
            external_user_id, limit=20, tenant_id=tenant_id
        )

        # --- WAIT FOR VISION if recent images lack description ---
        import asyncio

        try:
            pending_vision = await pool.fetchval(
                """
                SELECT COUNT(*) FROM chat_messages
                WHERE conversation_id = $1 AND tenant_id = $2
                AND content_attributes::text LIKE '%image%'
                AND content_attributes::text NOT LIKE '%description%'
                AND created_at > NOW() - INTERVAL '30 seconds'
            """,
                conversation_id,
                tenant_id,
            )
            if pending_vision and pending_vision > 0:
                logger.info(
                    f"👁️ Waiting for vision analysis ({pending_vision} pending)..."
                )
                for attempt in range(6):  # Wait up to 15s
                    await asyncio.sleep(2.5)
                    still_pending = await pool.fetchval(
                        """
                        SELECT COUNT(*) FROM chat_messages
                        WHERE conversation_id = $1 AND tenant_id = $2
                        AND content_attributes::text LIKE '%image%'
                        AND content_attributes::text NOT LIKE '%description%'
                        AND created_at > NOW() - INTERVAL '30 seconds'
                    """,
                        conversation_id,
                        tenant_id,
                    )
                    if not still_pending or still_pending == 0:
                        logger.info(
                            f"✅ Vision analysis completed after {(attempt + 1) * 2.5}s"
                        )
                        break
                else:
                    logger.warning(
                        "⚠️ Timeout waiting for vision. Proceeding without image description."
                    )
                # Re-fetch history with updated descriptions
                db_history_dicts = await db.get_chat_history(
                    external_user_id, limit=20, tenant_id=tenant_id
                )
        except Exception as vision_wait_err:
            logger.warning(f"⚠️ Error checking pending vision: {vision_wait_err}")

        # --- EXTRACT CONTEXT BEFORE DEDUPLICATION (VISION FIX) ---
        for msg in db_history_dicts:
            extract_multimodal(msg.get("content_attributes"))

        # Deduplication: If the last message in DB matches the first in Buffer, remove it from history
        if db_history_dicts and messages:
            last_db_msg = db_history_dicts[-1]["content"]
            first_buffer_msg = messages[0]
            if last_db_msg.strip() == first_buffer_msg.strip():
                db_history_dicts.pop()

        # CONTEXT COMPRESSION: Keep last 6 messages full, compress older ones
        if len(db_history_dicts) > 6:
            # Compress older messages into a summary line each (save ~60% tokens)
            old_msgs = db_history_dicts[:-6]
            recent_msgs = db_history_dicts[-6:]
            for msg in old_msgs:
                role = msg["role"]
                content = msg["content"]
                # Truncate old messages to 80 chars max
                truncated = content[:80] + "..." if len(content) > 80 else content
                if role == "user":
                    chat_history.append(HumanMessage(content=truncated))
                else:
                    chat_history.append(AIMessage(content=truncated))
            for msg in recent_msgs:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    chat_history.append(HumanMessage(content=content))
                else:
                    chat_history.append(AIMessage(content=content))
        else:
            for msg in db_history_dicts:
                role = msg["role"]
                content = msg["content"]
                if role == "user":
                    chat_history.append(HumanMessage(content=content))
                else:
                    chat_history.append(AIMessage(content=content))

        # Append buffered messages as ONE block
        user_input = "\n".join(messages)

        if vision_context_str:
            logger.info(
                f"👁️ Inyectando contexto visual: {len(vision_context_str)} chars"
            )
            user_input += (
                f"\n\nCONTEXTO VISUAL (Imágenes recientes):{vision_context_str}"
            )

        if audio_context_str:
            logger.info(
                f"🎙️ Inyectando contexto de audio: {len(audio_context_str)} chars"
            )
            user_input += (
                f"\n\nCONTEXTO DE AUDIO (Transcripciones recientes):{audio_context_str}"
            )

        # --- Bug #4 Phase C: Input-side state guard ---
        # Check previous conversation state and inject hint if needed
        state_hint = ""
        if get_state is not None and current_customer_phone is not None:
            try:
                phone = current_customer_phone.get()
                if phone:
                    prev_state = await get_state(tenant_id, phone)
                    prev_state_str = (
                        prev_state.get("state", "IDLE")
                        if isinstance(prev_state, dict)
                        else "IDLE"
                    )

                    # If previous state was OFFERED_SLOTS and user is selecting a slot
                    if prev_state_str == "OFFERED_SLOTS":
                        user_msg = "\n".join(messages)
                        if _detect_selection_intent(user_msg):
                            state_hint = (
                                "\n\n[STATE_HINT: El paciente ya tiene opciones de turnosOFFERED_SLOTS. "
                                "El paciente está SELECCIONANDO uno de los turnos ofrecidos. "
                                "DEBES ir a 'confirm_slot' para confirmar la selección, NO a 'check_availability'. "
                                "Usa 'confirm_slot' con los datos del turno que el paciente seleccionó.]"
                            )
                            logger.info(
                                f"🔒 STATE_GUARD: Injecting hint for slot selection. prev_state={prev_state_str}"
                            )
                        elif _detect_research_intent(user_msg):
                            # User wants to search again - this is OK, no hint needed
                            logger.info(
                                f"🔒 STATE_GUARD: Re-search intent detected, no hint needed. prev_state={prev_state_str}"
                            )
                        else:
                            # Neither selection nor research intent - log for debugging
                            logger.info(
                                f"🔒 STATE_GUARD: No clear intent detected. prev_state={prev_state_str}, user_msg={user_msg[:50]}..."
                            )
            except Exception as state_err:
                logger.warning(f"[STATE_GUARD] Failed to get state: {state_err}")

        if state_hint:
            user_input += state_hint

        # --- DETECCIÓN DE CONTEXTO ESPECIAL ---
        # Verificar si hay contexto especial (multimedia, seguimientos, etc.)
        has_recent_media = False
        is_followup_response = False
        media_types = []
        channel_type = "whatsapp"  # Default
        followup_context = ""

        try:
            # Obtener el último mensaje del usuario y el último del asistente
            context_rows = await pool.fetch(
                """
                SELECT cm.role, cm.content, cm.content_attributes, cc.channel 
                FROM chat_messages cm
                JOIN chat_conversations cc ON cm.conversation_id = cc.id
                WHERE cm.conversation_id = $1 
                ORDER BY cm.created_at DESC 
                LIMIT 2
            """,
                conversation_id,
            )

            if context_rows:
                for ctx_row in context_rows:
                    if ctx_row["role"] == "user":
                        # Verificar archivos multimedia en mensaje del usuario
                        attrs = ctx_row["content_attributes"]
                        channel_type = ctx_row["channel"] or "whatsapp"

                        if attrs:
                            if isinstance(attrs, str):
                                attrs = json.loads(attrs)

                            if isinstance(attrs, list):
                                for att in attrs:
                                    media_type = att.get("type", "")
                                    if media_type in ["image", "document"]:
                                        has_recent_media = True
                                        media_types.append(media_type)

                    elif ctx_row["role"] == "assistant":
                        # Verificar si el último mensaje del asistente fue un seguimiento
                        attrs = ctx_row["content_attributes"]
                        if attrs:
                            if isinstance(attrs, str):
                                attrs = json.loads(attrs)

                            # Buscar metadata de seguimiento
                            if isinstance(attrs, dict) and attrs.get("is_followup"):
                                is_followup_response = True
                                followup_context = (
                                    "⚠️ ATENCIÓN: El paciente está respondiendo a un mensaje de "
                                    "seguimiento post-atención. DEBÉS evaluar síntomas con 'triage_urgency' "
                                    "y aplicar las 6 reglas maxilofaciales de urgencia."
                                )
                                logger.info(
                                    f"🔍 Detectada respuesta a seguimiento post-atención"
                                )

        except Exception as e:
            logger.warning(f"Error al verificar contexto especial: {e}")

        # Late supplement: if media detected after prompt build, inject adjuntos section
        if has_recent_media and "media" not in intent_tags:
            intent_tags.add("media")
            from main import _get_adjuntos_section

            system_prompt += "\n\n" + _get_adjuntos_section()

        # --- Social channel context (phase 6) ---
        # channel_type is now resolved from the DB JOIN above (line ~1361).
        # compute_social_context is a pure function so this is always fast.
        _social_ctx = compute_social_context(channel_type, dict(tenant_row) if tenant_row else {})

        # SOLO path: prepend social preamble to system_prompt when IG/FB active.
        # This path calls build_system_prompt before channel_type is known, so
        # we inject the preamble here after both are available.
        if _social_ctx["is_social_channel"]:
            try:
                from services.social_prompt import build_social_preamble
                from services.social_routes import CTA_ROUTES

                _social_preamble = build_social_preamble(
                    tenant_id=tenant_id,
                    channel=_social_ctx["channel"],
                    social_landings=_social_ctx["social_landings"],
                    instagram_handle=_social_ctx["instagram_handle"],
                    facebook_page_id=_social_ctx["facebook_page_id"],
                    cta_routes=CTA_ROUTES,
                    whatsapp_link=_social_ctx.get("whatsapp_link"),
                )
                system_prompt = _social_preamble + "\n\n---\n\n" + system_prompt
                logger.info(
                    f"📱 Social preamble injected for tenant {tenant_id} "
                    f"channel={_social_ctx['channel']}"
                )
            except Exception as _social_err:
                logger.warning(f"⚠️ Social preamble injection failed (non-fatal): {_social_err}")

        executor = await get_agent_executable_for_tenant(tenant_id)
        logger.info(f"🧠 Invoking Agent for {external_user_id}...")

        # C3: Check engine mode and log which engine is being used.
        # MULTI path: populate ctx.extra with social context so graph.run_turn
        # can wire it into AgentState (phase 5 wiring via ctx.extra).
        try:
            from services.engine_router import get_engine_for_tenant

            engine = await get_engine_for_tenant(tenant_id)
            logger.info(f"🎛️ Engine mode for tenant {tenant_id}: {engine.name}")
            # When multi-agent engine is active, ctx.extra must carry social context.
            # The TurnContext is created per-dispatch so we store it on the engine
            # via a thread-local is not feasible. Instead, the social_ctx dict is
            # already available and will be passed when TurnContext dispatch is
            # fully wired (phase 9 integration wiring — currently buffer_task
            # still dispatches through executor.ainvoke for both paths).
        except Exception as eng_err:
            logger.warning(f"⚠️ Engine router check failed, using default: {eng_err}")

        # Inyectar contexto especial si es necesario
        special_context = []

        # Contexto de archivos multimedia
        if has_recent_media:
            channel_name = "WhatsApp"
            if channel_type == "instagram":
                channel_name = "Instagram"
            elif channel_type == "facebook":
                channel_name = "Facebook"
            elif channel_type == "chatwoot":
                channel_name = "el chat"

            # =======================================================
            # MULTI-ATTACHMENT PROCESSING (Fase 2)
            # =======================================================
            all_attachments = []  # each item: {url, mime_type, type, description, index}
            try:
                # Fetch all media attachments from this conversation (last 20 messages)
                rows = await pool.fetch(
                    """
                    SELECT id, content_attributes
                    FROM chat_messages
                    WHERE conversation_id = $1 AND tenant_id = $2
                      AND content_attributes IS NOT NULL
                      AND (content_attributes::text LIKE '%"type":"image"%' OR content_attributes::text LIKE '%"type":"document"%')
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    conversation_id,
                    tenant_id,
                )
                index = 0
                for row in rows:
                    attrs = row["content_attributes"]
                    if isinstance(attrs, str):
                        attrs = json.loads(attrs)
                    if isinstance(attrs, list):
                        for att in attrs:
                            media_type = att.get("type")
                            if media_type not in ("image", "document"):
                                continue
                            url = att.get("url")
                            if not url:
                                continue
                            mime_type = att.get("mime_type", "")
                            description = att.get("description")
                            all_attachments.append(
                                {
                                    "url": url,
                                    "mime_type": mime_type,
                                    "type": media_type,
                                    "description": description,
                                    "index": index,
                                }
                            )
                            index += 1
                # Deduplicate by URL (keep first occurrence)
                seen_urls = set()
                unique_attachments = []
                for att in all_attachments:
                    if att["url"] not in seen_urls:
                        seen_urls.add(att["url"])
                        unique_attachments.append(att)
                all_attachments = unique_attachments
                # Apply limits
                images = [
                    a for a in all_attachments if a["mime_type"].startswith("image/")
                ]
                pdfs = [
                    a for a in all_attachments if a["mime_type"] == "application/pdf"
                ]
                if len(images) > MAX_IMAGES or len(pdfs) > MAX_PDFS:
                    logger.warning(
                        f"超越MAX_ATTACHMENTS, truncating (images={len(images)} pdfs={len(pdfs)})"
                    )
                    # Truncate: keep first MAX_IMAGES images and first MAX_PDFS PDFs
                    images = images[:MAX_IMAGES]
                    pdfs = pdfs[:MAX_PDFS]
                    # Recombine preserving order? Simpler: keep all attachments but skip extra ones.
                    # We'll just keep the first MAX_IMAGES images and MAX_PDFS PDFs.
                    # Since order may be mixed, we'll just truncate all_attachments to first MAX_IMAGES+MAX_PDFS.
                    # For simplicity, we'll just keep first MAX_IMAGES+MAX_PDFS attachments.
                    all_attachments = all_attachments[: MAX_IMAGES + MAX_PDFS]
                # Batch analyze attachments missing descriptions
                attachments_to_analyze = [
                    a for a in all_attachments if not a.get("description")
                ]
                if attachments_to_analyze and analyze_attachments_batch:
                    logger.info(
                        f"🔄 Batch analyzing {len(attachments_to_analyze)} attachments"
                    )
                    analyses = await analyze_attachments_batch(
                        attachments=[
                            {
                                "url": a["url"],
                                "mime_type": a["mime_type"],
                                "index": a["index"],
                            }
                            for a in attachments_to_analyze
                        ],
                        tenant_id=tenant_id,
                    )
                    # Update descriptions in all_attachments based on analyses
                    for analysis in analyses:
                        idx = analysis.get("index")
                        if idx is not None and idx < len(all_attachments):
                            all_attachments[idx]["description"] = analysis.get(
                                "vision_description"
                            )
                # Classify each attachment and save to patient_documents if patient exists
                if patient_row and classify_message:
                    patient_id = patient_row["id"]
                    for att in all_attachments:
                        classification = await classify_message(
                            text="",
                            tenant_id=tenant_id,
                            vision_description=att.get("description"),
                        )
                        is_payment = classification.get("is_payment", False)
                        document_type = "payment_receipt" if is_payment else "clinical"
                        # Prepare source_details JSONB
                        source_details = {
                            "vision_description": att.get("description"),
                            "attachment_index": att["index"],
                            "mime_type": att["mime_type"],
                        }
                        # Determine file_name from URL
                        file_name = (
                            att["url"].split("/")[-1] or f"attachment_{att['index']}"
                        )
                        # Insert into patient_documents (ignore duplicate on unique constraint)
                        try:
                            await pool.execute(
                                """
                                INSERT INTO patient_documents
                                (tenant_id, patient_id, file_name, file_path, mime_type, document_type, source, source_details)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
                                ON CONFLICT (tenant_id, patient_id, file_name) DO NOTHING
                                """,
                                tenant_id,
                                patient_id,
                                file_name,
                                att["url"],  # file_path = URL for now
                                att["mime_type"],
                                document_type,
                                "whatsapp",
                                json.dumps(source_details),
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to save attachment to patient_documents: {e}"
                            )
                # Generate LLM summary if we have attachments and patient
                if patient_row and generate_attachment_summary and all_attachments:
                    summary = await generate_attachment_summary(
                        tenant_id=tenant_id,
                        patient_id=patient_row["id"],
                        attachments=all_attachments,
                    )
                    if summary:
                        # Save to clinical_record_summaries
                        try:
                            await pool.execute(
                                """
                                INSERT INTO clinical_record_summaries
                                (tenant_id, patient_id, conversation_id, summary_text, attachments_count, attachments_types)
                                VALUES ($1, $2, $3, $4, $5, $6::jsonb)
                                ON CONFLICT (tenant_id, patient_id, conversation_id) DO UPDATE
                                SET summary_text = EXCLUDED.summary_text,
                                    attachments_count = EXCLUDED.attachments_count,
                                    attachments_types = EXCLUDED.attachments_types
                                """,
                                tenant_id,
                                patient_row["id"],
                                conversation_id,
                                summary,
                                len(all_attachments),
                                json.dumps([a["type"] for a in all_attachments]),
                            )
                        except Exception as e:
                            logger.warning(
                                f"Failed to save clinical_record_summaries: {e}"
                            )
            except Exception as e:
                logger.warning(f"Multi-attachment processing error (non-fatal): {e}")
                # Continue with single-attachment context

            # =======================================================
            # END MULTI-ATTACHMENT PROCESSING
            # =======================================================

            media_context = "IMPORTANTE: El paciente acaba de enviar "
            if "image" in media_types and "document" in media_types:
                media_context += "imágenes y documentos"
            elif "image" in media_types:
                media_context += "una imagen"
            elif "document" in media_types:
                media_context += "un documento"

            media_context += f" por {channel_name}. "

            # Check if interlocutor has linked minors — if so, ask who the file belongs to
            try:
                minor_count = (
                    await pool.fetchval(
                        "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND guardian_phone = $2",
                        tenant_id,
                        external_user_id,
                    )
                    or 0
                )
            except Exception:
                minor_count = 0

            # Check if patient exists before mentioning medical record
            has_patient = False
            try:
                clean_ext = (
                    external_user_id.replace("+", "") if external_user_id else ""
                )
                patient_exists = await pool.fetchval(
                    """
                    SELECT id FROM patients WHERE tenant_id = $1 AND (
                        phone_number = $2 OR phone_number = $3 OR
                        instagram_psid = $2 OR facebook_psid = $2
                    ) LIMIT 1
                """,
                    tenant_id,
                    external_user_id,
                    clean_ext,
                )
                has_patient = patient_exists is not None
            except Exception:
                has_patient = False

            if has_patient and minor_count > 0:
                media_context += (
                    "IMPORTANTE: Este paciente tiene hijos/menores vinculados. "
                    "ANTES de confirmar que guardaste el archivo, PREGUNTÁ: 'Este archivo es para tu ficha o para la de [nombre del hijo/a]?' "
                    "Si es para un menor, usá la tool 'reassign_document' con el phone_interno del menor (ej: +549...-M1) "
                    "que aparece en el contexto de HIJOS/MENORES VINCULADOS. "
                    "Si es para el interlocutor, no hagas nada extra, ya está guardado."
                )
            elif has_patient:
                # Check if patient has a pending payment (seña) — if so, the image is likely a payment receipt
                has_pending_payment = False
                payment_on_cooldown = False

                # Check cooldown first - if payment verification was recently attempted, skip re-triggering
                try:
                    from services.payment_cooldown import check_payment_cooldown

                    payment_on_cooldown = await check_payment_cooldown(
                        tenant_id, external_user_id
                    )
                except Exception as cooldown_err:
                    logger.warning(f"Error checking payment cooldown: {cooldown_err}")

                # Fase 2 - Task 2.3: Integrate image classifier
                # If cooldown is active, skip payment verification context
                if payment_on_cooldown:
                    media_context += "Confirmo que recibí tu archivo. Lo guardamos en tu ficha médica."
                else:
                    # Classify the image using Vision context and message text
                    classification_result = {
                        "classification": "neutral",
                        "is_payment": False,
                        "is_medical": False,
                    }
                    try:
                        from services.image_classifier import classify_message

                        # Combine text messages and vision context for classification
                        text_for_classification = messages[-1] if messages else ""
                        classification_result = await classify_message(
                            text=text_for_classification,
                            tenant_id=tenant_id,
                            vision_description=vision_context_str
                            if vision_context_str
                            else None,
                        )
                        logger.info(
                            f"🖼️ Image classification: {classification_result.get('classification')} "
                            f"(payment={classification_result.get('is_payment')}, "
                            f"medical={classification_result.get('is_medical')})"
                        )
                    except Exception as clf_err:
                        logger.warning(f"Error in image classification: {clf_err}")
                        # Continue with default behavior (treat as potentially payment if pending)

                    # If classified as MEDICAL, override payment detection
                    is_classified_medical = classification_result.get(
                        "is_medical", False
                    )
                    is_classified_payment = classification_result.get(
                        "is_payment", False
                    )
                    try:
                        clean_ext_pay = (
                            external_user_id.replace("+", "")
                            if external_user_id
                            else ""
                        )
                        pending_apt = await pool.fetchval(
                            """
                            SELECT a.id FROM appointments a
                            JOIN patients p ON p.id = a.patient_id
                            WHERE a.tenant_id = $1
                              AND (p.phone_number = $2 OR p.phone_number = $3
                                   OR REGEXP_REPLACE(p.phone_number, '[^0-9]', '', 'g') = REGEXP_REPLACE($2, '[^0-9]', '', 'g'))
                              AND a.status IN ('scheduled', 'confirmed')
                              AND (a.payment_status IS NULL OR a.payment_status = 'pending' OR a.payment_status = 'partial')
                            ORDER BY a.appointment_datetime ASC LIMIT 1
                        """,
                            tenant_id,
                            external_user_id,
                            clean_ext_pay,
                        )
                        has_pending_payment = pending_apt is not None
                    except Exception as pay_check_err:
                        logger.warning(
                            f"Error checking pending payment: {pay_check_err}"
                        )

                    # --- Fallback: check treatment plan pending balance ---
                    has_pending_plan = False
                    if not has_pending_payment:
                        try:
                            pending_plan = await pool.fetchval(
                                """
                                SELECT tp.id FROM treatment_plans tp
                                LEFT JOIN (
                                    SELECT plan_id, SUM(amount) as total_paid
                                    FROM treatment_plan_payments WHERE tenant_id = $1
                                    GROUP BY plan_id
                                ) pay ON pay.plan_id = tp.id
                                WHERE tp.tenant_id = $1 AND tp.patient_id = $2
                                  AND tp.status IN ('approved', 'in_progress')
                                  AND tp.approved_total > COALESCE(pay.total_paid, 0)
                                LIMIT 1
                                """,
                                tenant_id,
                                patient_row["id"],
                            )
                            if pending_plan:
                                has_pending_payment = True
                                has_pending_plan = True
                                logger.info(
                                    f"💰 buffer_task: patient has pending treatment plan balance, "
                                    f"activating payment receipt context (plan_id={pending_plan})"
                                )
                        except Exception as plan_check_err:
                            logger.warning(
                                f"Error checking plan pending: {plan_check_err}"
                            )

                    if has_pending_payment:
                        # Fase 2 - Task 2.3: Override payment context if classified as medical
                        # Medical documents take priority over payment verification
                        if is_classified_medical:
                            logger.info(
                                f"🖼️ Image classified as MEDICAL, overriding payment context"
                            )
                            media_context += "Responde confirmando que recibiste el archivo y que ya lo guardaste en su ficha médica para que la Dra. lo vea. Usa un tono amable y profesional."
                        elif is_classified_payment:
                            # Explicitly classified as payment - inject payment verification context
                            if has_pending_plan:
                                media_context += (
                                    "PROBABLE COMPROBANTE DE PAGO: El paciente tiene un plan de tratamiento con saldo pendiente y acaba de enviar una imagen/documento. "
                                    "Es MUY probable que sea un comprobante de transferencia bancaria para abonar una cuota del plan. "
                                    "ACCIÓN OBLIGATORIA: Usá 'verify_payment_receipt' para verificar el comprobante. "
                                    "Pasá la descripción de la imagen del CONTEXTO VISUAL como 'receipt_description' y el monto que detectes como 'amount_detected'. "
                                    "NO digas 'ya lo guardé en tu ficha'. Decí 'Recibí tu comprobante, voy a verificarlo' y ejecutá la tool. "
                                    "Si la verificación es exitosa → confirmá el pago al plan. Si falla → explicá qué falló."
                                )
                            else:
                                media_context += (
                                    "PROBABLE COMPROBANTE DE PAGO: El paciente tiene un turno con seña pendiente y acaba de enviar una imagen/documento. "
                                    "Es MUY probable que sea un comprobante de transferencia bancaria. "
                                    "ACCIÓN OBLIGATORIA: Usá 'verify_payment_receipt' para verificar el comprobante. "
                                    "Pasá la descripción de la imagen del CONTEXTO VISUAL como 'receipt_description' y el monto que detectes como 'amount_detected'. "
                                    "NO digas 'ya lo guardé en tu ficha'. Decí 'Recibí tu comprobante, voy a verificarlo' y ejecutá la tool. "
                                    "Si la verificación es exitosa → confirmá el pago. Si falla → explicá qué falló."
                                )
                        else:
                            # Not classified - use legacy behavior with pending payment check
                            if has_pending_plan:
                                media_context += (
                                    "PROBABLE COMPROBANTE DE PAGO: El paciente tiene un plan de tratamiento con saldo pendiente y acaba de enviar una imagen/documento. "
                                    "Es MUY probable que sea un comprobante de transferencia bancaria para abonar una cuota del plan. "
                                    "ACCIÓN OBLIGATORIA: Usá 'verify_payment_receipt' para verificar el comprobante. "
                                    "Pasá la descripción de la imagen del CONTEXTO VISUAL como 'receipt_description' y el monto que detectes como 'amount_detected'. "
                                    "NO digas 'ya lo guardé en tu ficha'. Decí 'Recibí tu comprobante, voy a verificarlo' y ejecutá la tool. "
                                    "Si la verificación es exitosa → confirmá el pago al plan. Si falla → explicá qué falló."
                                )
                            else:
                                media_context += (
                                    "PROBABLE COMPROBANTE DE PAGO: El paciente tiene un turno con seña pendiente y acaba de enviar una imagen/documento. "
                                    "Es MUY probable que sea un comprobante de transferencia bancaria. "
                                    "ACCIÓN OBLIGATORIA: Usá 'verify_payment_receipt' para verificar el comprobante. "
                                    "Pasá la descripción de la imagen del CONTEXTO VISUAL como 'receipt_description' y el monto que detectes como 'amount_detected'. "
                                    "NO digas 'ya lo guardé en tu ficha'. Decí 'Recibí tu comprobante, voy a verificarlo' y ejecutá la tool. "
                                    "Si la verificación es exitosa → confirmá el pago. Si falla → explicá qué falló."
                                )
                    else:
                        # No pending payment - treat as medical document
                        media_context += "Responde confirmando que recibiste el archivo y que ya lo guardaste en su ficha médica para que la Dra. lo vea. Usa un tono amable y profesional."
            else:
                media_context += (
                    "NOTA: Este contacto AUN NO tiene ficha de paciente registrada. "
                    "NO digas que guardaste el archivo en su ficha porque no existe. "
                    "Si hay CONTEXTO VISUAL disponible, usalo para responder sobre la imagen. "
                    "Si el contacto necesita agendar un turno, pedile sus datos (nombre, telefono, DNI) primero."
                )

            special_context.append(media_context)

        # Contexto de respuesta a seguimiento post-atención
        if is_followup_response and followup_context:
            special_context.append(followup_context)
            logger.info("✅ Contexto de seguimiento post-atención inyectado")

        # Meta Direct channel rule: only ask phone if patient doesn't have one
        if channel_type in ("instagram", "facebook"):
            # Check if this patient already has a real phone number in DB
            patient_has_phone = False
            if patient_row:
                existing_phone = patient_row.get("phone_number") or ""
                patient_has_phone = bool(
                    existing_phone
                ) and not existing_phone.startswith("SIN-TEL")

            if patient_has_phone:
                special_context.append(
                    f"REGLA CANAL ({channel_type.upper()}): El paciente escribe por {channel_type.capitalize()} "
                    f"pero YA tiene teléfono registrado ({patient_row.get('phone_number')}). "
                    "NO le pidas teléfono, ya lo tenés. Podés usar todas las herramientas normalmente."
                )
                logger.info(
                    f"IG/FB patient already has phone, skipping phone-request rule"
                )
            else:
                special_context.append(
                    f"REGLA CANAL ({channel_type.upper()}): El paciente escribe por {channel_type.capitalize()}. "
                    "En este canal NO tenemos su numero de telefono. "
                    "ANTES de poder agendar un turno, registrar datos o buscar turnos, DEBES pedirle su numero de telefono con codigo de area. "
                    "Sin telefono no podes usar ninguna herramienta de gestion de pacientes. "
                    'Ejemplo: "Para poder ayudarte con turnos, necesito tu numero de telefono con codigo de area. Me lo compartes?"'
                )
                logger.info(
                    f"Injected Meta Direct phone-request rule for {channel_type}"
                )

        # INYECCIÓN FORZADA: Si el paciente ya existe, meter sus datos en el input
        # para que sea IMPOSIBLE que el agente los ignore y los pida de nuevo
        if patient_row and (
            patient_row.get("first_name") or patient_row.get("last_name")
        ):
            p_fn = patient_row.get("first_name") or ""
            p_ln = patient_row.get("last_name") or ""
            p_dn = patient_row.get("dni") or ""
            p_em = patient_row.get("email") or ""
            forced_context = (
                f"[DATOS DEL PACIENTE - YA REGISTRADO EN EL SISTEMA - NO PEDIR ESTOS DATOS]\n"
                f"Nombre: {p_fn} {p_ln}\n"
            )
            if p_dn:
                forced_context += f"DNI: {p_dn}\n"
            if p_em:
                forced_context += f"Email: {p_em}\n"
            forced_context += "INSTRUCCIÓN: Este paciente YA ESTÁ en la base de datos. NO le pidas nombre, apellido ni DNI. Usá estos datos directamente para agendar.\n"
            special_context.insert(0, forced_context)
            logger.info(
                f"💉 Forced patient context injected: {p_fn} {p_ln} (DNI: {p_dn})"
            )

        # Aplicar todos los contextos especiales
        if special_context:
            context_block = "\n\n".join(special_context)
            user_input = f"{context_block}\n\nMensaje del paciente: {user_input}"

        # --- Retry Logic con Exponential Backoff ---
        response_text = ""
        media_urls = []
        max_retries = 3
        token_cb = None

        # Import callback (non-fatal if unavailable)
        _get_cb = None
        try:
            from langchain_community.callbacks import get_openai_callback as _get_cb_fn

            _get_cb = _get_cb_fn
        except ImportError:
            logger.warning(
                "⚠️ get_openai_callback not available, tokens will be estimated"
            )

        for attempt in range(max_retries):
            try:
                if _get_cb:
                    with _get_cb() as cb:
                        response = await executor.ainvoke(
                            {
                                "input": user_input,
                                "chat_history": chat_history,
                                "system_prompt": system_prompt,
                            }
                        )
                        token_cb = cb
                else:
                    response = await executor.ainvoke(
                        {
                            "input": user_input,
                            "chat_history": chat_history,
                            "system_prompt": system_prompt,
                        }
                    )
                response_text = response.get("output", "") or "[Sin respuesta]"
                # Bug #9: Extract intermediate_steps to know if a tool was actually called
                intermediate_steps = response.get("intermediate_steps", [])
                tool_was_called = len(intermediate_steps) > 0
                cb_tokens = token_cb.total_tokens if token_cb else 0
                logger.info(
                    f"🤖 Agent Response: {response_text[:50]}... | cb_tokens={cb_tokens} | tools_called={tool_was_called}"
                )

                # --- Bug #4 Phase D: Output-side state guard ---
                # Check if LLM called check_availability when it should have called confirm_slot
                state_retry_count = 0
                if get_state is not None and current_customer_phone is not None:
                    try:
                        phone = current_customer_phone.get()
                        if phone:
                            prev_state = await get_state(tenant_id, phone)
                            prev_state_str = (
                                prev_state.get("state", "IDLE")
                                if isinstance(prev_state, dict)
                                else "IDLE"
                            )

                            # If previous state was OFFERED_SLOTS and LLM called check_availability
                            if prev_state_str == "OFFERED_SLOTS":
                                intermediate_steps = response.get(
                                    "intermediate_steps", []
                                )
                                tools_called = []
                                for step in intermediate_steps:
                                    if isinstance(step, tuple) and len(step) > 0:
                                        tool_name = (
                                            step[0].get("name", "")
                                            if hasattr(step[0], "get")
                                            else str(step[0])
                                        )
                                        tools_called.append(tool_name)

                                user_msg = "\n".join(messages)
                                has_research_intent = _detect_research_intent(user_msg)

                                # If check_availability was called without research intent, retry
                                if (
                                    "check_availability" in tools_called
                                    and not has_research_intent
                                    and state_retry_count < MAX_STATE_RETRIES
                                ):
                                    logger.warning(
                                        f"🔒 STATE_GUARD: LLM called check_availability in OFFERED_SLOTS state. "
                                        f"tenant_id={tenant_id} phone={phone} prev_state={prev_state_str} "
                                        f"tools_called={tools_called} user_msg={user_msg[:50]}..."
                                    )
                                    state_retry_count += 1

                                    # Retry with stronger nudge
                                    nudge_input = f"{user_input}\n\n[SISTEMA: IMPORTANTE - El paciente YA tiene opciones de turnos ofrecidas. "
                                    f"Si el paciente quiere SELECCIONAR un turno, usa 'confirm_slot', NO 'check_availability'. "
                                    f"Ve a 'confirm_slot' directamente.]"

                                    if _get_cb:
                                        with _get_cb() as cb3:
                                            response3 = await executor.ainvoke(
                                                {
                                                    "input": nudge_input,
                                                    "chat_history": chat_history,
                                                    "system_prompt": system_prompt,
                                                }
                                            )
                                    else:
                                        response3 = await executor.ainvoke(
                                            {
                                                "input": nudge_input,
                                                "chat_history": chat_history,
                                                "system_prompt": system_prompt,
                                            }
                                        )
                                    retry_text = response3.get("output", "")
                                    if retry_text and len(retry_text) > len(
                                        response_text
                                    ):
                                        response_text = retry_text
                                        logger.info(f"🔒 STATE_GUARD: Retry successful")
                                    else:
                                        logger.warning(
                                            f"🔒 STATE_GUARD: Retry failed, degrading gracefully"
                                        )
                    except Exception as state_guard_err:
                        logger.warning(
                            f"[STATE_GUARD] Output guard failed: {state_guard_err}"
                        )

                # SAFETY NET: Detect "un momento" / "voy a buscar" dead-end responses
                # If agent said it will do something but didn't actually execute a tool,
                # re-invoke with a nudge to actually complete the action.
                # Bug #9: Only trigger if NO tool was called. If a tool ran, the response
                # is a presentation issue, not a dead-end — re-invoking would duplicate side effects.
                dead_end_phrases = [
                    "un momento",
                    "un instante",
                    "dejame buscar",
                    "voy a buscar",
                    "voy a verificar",
                    "voy a consultar",
                    "voy a agendar",
                    "voy a proceder",
                    "ya verifico",
                    "ya busco",
                    "permití",
                    "dame un segundo",
                ]
                response_lower = response_text.lower()
                is_dead_end = any(
                    phrase in response_lower for phrase in dead_end_phrases
                )
                # Only trigger if the response is short (< 200 chars) — real results are longer
                # Bug #9: and NOT tool_was_called — if a tool ran, don't re-invoke
                if (
                    is_dead_end
                    and not tool_was_called
                    and len(response_text) < 200
                    and attempt < max_retries - 1
                ):
                    logger.warning(
                        f"⚠️ Dead-end response detected: '{response_text[:80]}...' — re-invoking agent"
                    )
                    # Re-invoke with the same input + nudge
                    nudge_input = f"{user_input}\n\n[SISTEMA: Ejecutá la tool ahora y respondé con el resultado. NO digas 'un momento'.]"
                    try:
                        if _get_cb:
                            with _get_cb() as cb2:
                                response2 = await executor.ainvoke(
                                    {
                                        "input": nudge_input,
                                        "chat_history": chat_history,
                                        "system_prompt": system_prompt,
                                    }
                                )
                                token_cb = cb2
                        else:
                            response2 = await executor.ainvoke(
                                {
                                    "input": nudge_input,
                                    "chat_history": chat_history,
                                    "system_prompt": system_prompt,
                                }
                            )
                        retry_text = response2.get("output", "")
                        if retry_text and len(retry_text) > len(response_text):
                            response_text = retry_text
                            logger.info(
                                f"🔄 Dead-end recovery successful: {response_text[:50]}..."
                            )
                    except Exception as e2:
                        logger.warning(f"⚠️ Dead-end recovery failed: {e2}")

                break
            except Exception as e:
                logger.warning(
                    f"⚠️ process_buffer_task_agent_error (intento {attempt + 1}/{max_retries}): {str(e)}"
                )
                if attempt < max_retries - 1:
                    import asyncio

                    await asyncio.sleep(2**attempt)
                else:
                    logger.exception(
                        "process_buffer_task_agent_error_final", exc_info=e
                    )
                    response_text = "Disculpas, estoy experimentando intermitencias técnicas. Consultame de nuevo en unos minutos."

        # --- PATIENT MEMORY: Extract and store new memories from this conversation ---
        if response_text and patient_row:
            try:
                import asyncio as _mem_asyncio

                _mem_asyncio.create_task(
                    extract_and_store_memories(
                        pool,
                        external_user_id,
                        tenant_id,
                        user_input,
                        response_text,
                        patient_name=f"{patient_row.get('first_name', '')} {patient_row.get('last_name', '')}".strip(),
                    )
                )
                logger.info(f"🧠 Memory extraction queued for {external_user_id}")
            except Exception as mem_store_err:
                logger.warning(f"⚠️ Memory extraction (non-fatal): {mem_store_err}")

        # --- Token Tracking (dual: callback or estimate) ---
        if (
            response_text
            and response_text
            != "Disculpas, estoy experimentando intermitencias técnicas. Consultame de nuevo en unos minutos."
        ):
            try:
                from dashboard.token_tracker import token_tracker, TokenUsage
                from datetime import datetime, timezone as tz

                if token_tracker:
                    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

                    # Use callback tokens if available, otherwise estimate
                    if token_cb and token_cb.total_tokens > 0:
                        input_t = token_cb.prompt_tokens
                        output_t = token_cb.completion_tokens
                        total_t = token_cb.total_tokens
                        logger.info(
                            f"📊 Token source: callback | in={input_t} out={output_t} total={total_t}"
                        )
                    else:
                        # Estimate: ~1 token per 4 chars (conservative for Spanish)
                        input_text = (system_prompt or "") + (user_input or "")
                        input_t = max(len(input_text) // 4, 100)
                        output_t = max(len(response_text) // 4, 20)
                        total_t = input_t + output_t
                        logger.info(
                            f"📊 Token source: estimate | in={input_t} out={output_t} total={total_t}"
                        )

                    usage = TokenUsage(
                        conversation_id=conversation_id,
                        patient_phone=external_user_id,
                        model=model_name,
                        input_tokens=input_t,
                        output_tokens=output_t,
                        total_tokens=total_t,
                        cost_usd=token_tracker.calculate_cost(
                            model_name, input_t, output_t
                        ),
                        timestamp=datetime.now(tz.utc),
                        tenant_id=tenant_id,
                    )
                    await token_tracker.track_usage(usage)
                    # Update tenant totals
                    await pool.execute(
                        "UPDATE tenants SET total_tokens_used = COALESCE(total_tokens_used, 0) + $1, total_tool_calls = COALESCE(total_tool_calls, 0) + 1 WHERE id = $2",
                        total_t,
                        tenant_id,
                    )
                    logger.info(
                        f"📊 Tokens tracked: {total_t} | cost: ${usage.cost_usd}"
                    )
                else:
                    logger.warning("⚠️ token_tracker is None, skipping tracking")
            except Exception as tk_err:
                logger.warning(f"⚠️ Token tracking error (non-fatal): {tk_err}")

        # --- Extracción Multimedia Oculta ---
        if "[LOCAL_IMAGE:" in response_text:
            import re

            img_pattern = r"\[LOCAL_IMAGE:(.*?)\]"
            media_urls = re.findall(img_pattern, response_text)
            response_text = re.sub(img_pattern, "", response_text).strip()
            # Limpiar posible basura arrastrada por el tag markdown
            response_text = response_text.replace(
                "¡IMPORTANTE PARA LA IA! El tratamiento cuenta con imágenes. Agrega obligatoriamente el siguiente texto (invisible para el usuario) en tu respuesta para que el sistema le envíe las imágenes:",
                "",
            ).strip()

        # --- DATE VALIDATOR (Bug #1) ---
        # Validate dates in response against canonical dates from tool outputs
        # Fixes DD↔MM swap issue in LLM response text
        if validate_dates_in_response and response.get("intermediate_steps"):
            try:
                response_text = validate_dates_in_response(
                    response_text, response.get("intermediate_steps", [])
                )
            except Exception as dv_err:
                logger.warning(f"⚠️ Date validator error (non-fatal): {dv_err}")

    except Exception as e:
        logger.exception("process_buffer_task_fatal_error", exc_info=e)
        response_text = "Disculpas, estoy experimentando intermitencias. Consultame de nuevo en unos minutos."
        media_urls = []

    # --- SEND RESPONSE ---
    from response_sender import ResponseSender

    if provider == "chatwoot":
        account_id = row.get("external_account_id")
        cw_conv_id = row.get("external_chatwoot_id")
        logger.info(
            f"📋 Chatwoot delivery check | conv={conversation_id} | account_id={account_id} | cw_conv_id={cw_conv_id} | row_keys={list(row.keys()) if row else 'None'}"
        )

        if account_id and cw_conv_id:
            logger.info(
                f"🚀 Sending Chatwoot Response | tenant={tenant_id} to={external_user_id} media={len(media_urls)}"
            )
            await ResponseSender.send_sequence(
                tenant_id=tenant_id,
                external_user_id=external_user_id,
                conversation_id=conversation_id,
                provider=provider,
                channel=row.get("channel") or "chatwoot",
                account_id=account_id,
                cw_conv_id=cw_conv_id,
                messages_text=response_text,
                media_urls=media_urls,
            )
        else:
            logger.warning(
                f"Chatwoot IDs missing for conv {conversation_id}. Persisting response locally only."
            )
            # Persist the agent response in DB even if we can't send via Chatwoot
            await pool.execute(
                "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number) VALUES ($1, $2, 'assistant', $3, $4)",
                tenant_id,
                conversation_id,
                response_text,
                external_user_id,
            )

    elif provider == "ycloud":
        logger.info(
            f"🚀 Sending YCloud Response | tenant={tenant_id} to={external_user_id} media={len(media_urls)}"
        )
        await ResponseSender.send_sequence(
            tenant_id=tenant_id,
            external_user_id=external_user_id,
            conversation_id=conversation_id,
            provider=provider,
            channel="whatsapp",
            account_id="",  # Irrelevant for ycloud
            cw_conv_id="",
            messages_text=response_text,
            media_urls=media_urls,
        )

    elif provider == "meta_direct":
        logger.info(
            f"🚀 Sending Meta Direct Response | tenant={tenant_id} to={external_user_id} channel={row.get('channel')} media={len(media_urls)}"
        )
        await ResponseSender.send_sequence(
            tenant_id=tenant_id,
            external_user_id=external_user_id,
            conversation_id=conversation_id,
            provider=provider,
            channel=row.get("channel") or "facebook",
            account_id="",
            cw_conv_id="",
            messages_text=response_text,
            media_urls=media_urls,
        )

    # Bug #8: Mark greeting as sent after successful response delivery
    if is_greeting_pending:
        try:
            from services.greeting_state import mark_greeted

            await mark_greeted(tenant_id, external_user_id)
        except Exception:
            pass  # Non-critical — worst case greeting repeats next message

    # --- Spec 14: Socket.IO Notification (Real-time AI Response) ---
    try:
        from main import app

        sio = getattr(app.state, "sio", None)
        to_json_safe = getattr(app.state, "to_json_safe", lambda x: x)

        if sio and response_text:
            await sio.emit(
                "NEW_MESSAGE",
                to_json_safe(
                    {
                        "phone_number": external_user_id,
                        "tenant_id": tenant_id,
                        "message": response_text,
                        "attachments": [],
                        "role": "assistant",
                        "channel": row.get("channel") or "whatsapp",
                    }
                ),
            )
            logger.info(f"📡 Socket AI NEW_MESSAGE emitted for {external_user_id}")

            # Sincronizar conversación para el preview inmediato
            from db import db as db_inst

            await db_inst.sync_conversation(
                tenant_id=tenant_id,
                channel=row.get("channel") or "whatsapp",
                external_user_id=external_user_id,
                last_message=response_text,
                is_user=False,
            )
    except Exception as sio_err:
        logger.error(f"⚠️ Error emitting SocketIO response: {sio_err}")
