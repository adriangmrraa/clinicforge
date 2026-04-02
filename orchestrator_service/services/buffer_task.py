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

logger = logging.getLogger(__name__)


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
        )

        # ✅ FIX: Establecer ContextVars para que las tools (book_appointment, etc)
        # puedan identificar al paciente en la tarea background
        current_customer_phone.set(external_user_id)
        current_tenant_id.set(tenant_id)

        tenant_row = await pool.fetchrow(
            "SELECT clinic_name, address, google_maps_url, working_hours, consultation_price, bank_cbu, bank_alias, bank_holder_name FROM tenants WHERE id = $1",
            tenant_id,
        )
        clinic_name = (
            (tenant_row["clinic_name"] or CLINIC_NAME) if tenant_row else CLINIC_NAME
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
        clinic_working_hours = None
        if tenant_row and tenant_row.get("working_hours"):
            wh = tenant_row["working_hours"]
            clinic_working_hours = json.loads(wh) if isinstance(wh, str) else wh

        # Fetch FAQs for this tenant (no limit — RAG will select relevant ones)
        faq_rows = await pool.fetch(
            "SELECT category, question, answer FROM clinic_faqs WHERE tenant_id = $1 ORDER BY sort_order ASC, id ASC",
            tenant_id,
        )
        faqs = [dict(r) for r in faq_rows] if faq_rows else []

        # Fetch insurance providers for this tenant
        insurance_providers = []
        try:
            ins_rows = await pool.fetch(
                "SELECT id, provider_name, status, restrictions, external_target, requires_copay, copay_notes, ai_response_template FROM tenant_insurance_providers WHERE tenant_id = $1 AND is_active = true ORDER BY sort_order, provider_name",
                tenant_id,
            )
            insurance_providers = [dict(r) for r in ins_rows] if ins_rows else []
        except Exception as ins_err:
            logger.debug(f"Insurance providers fetch (non-fatal): {ins_err}")

        # Fetch derivation rules for this tenant
        derivation_rules = []
        try:
            der_rows = await pool.fetch(
                """
                SELECT dr.id, dr.rule_name, dr.patient_condition, dr.treatment_categories,
                       dr.target_type, dr.target_professional_id, dr.priority_order,
                       p.first_name as target_professional_name
                FROM professional_derivation_rules dr
                LEFT JOIN professionals p ON dr.target_professional_id = p.id
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
            """SELECT id, first_name, last_name, dni, email, phone_number, acquisition_source, anamnesis_token, medical_history FROM patients
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
                from main import ARG_TZ

                if hasattr(dt, "astimezone"):
                    dt = dt.astimezone(ARG_TZ)
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
                    ldt = ldt.astimezone(ARG_TZ)
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
                            mdt = mdt.astimezone(ARG_TZ)
                        identity_lines.append(
                            f"    Próximo turno: {minor_apt['treatment_name'] or 'Consulta'} el {dias_semana[mdt.weekday()]} {mdt.strftime('%d/%m')} a las {mdt.strftime('%H:%M')}"
                        )

            # --- PATIENT MEMORY: Retrieve persistent memories ---
            try:
                memory_text = await format_memories_for_prompt(
                    pool, external_user_id, tenant_id
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

        executor = await get_agent_executable_for_tenant(tenant_id)
        logger.info(f"🧠 Invoking Agent for {external_user_id}...")

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

        # Try to import callback (non-fatal if unavailable)
        _get_cb = None
        try:
            from langchain_community.callbacks import get_openai_callback as _get_cb_fn

            _get_cb = _get_cb_fn
        except ImportError:
            try:
                from langchain.callbacks import get_openai_callback as _get_cb_fn

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
                cb_tokens = token_cb.total_tokens if token_cb else 0
                logger.info(
                    f"🤖 Agent Response: {response_text[:50]}... | cb_tokens={cb_tokens}"
                )

                # SAFETY NET: Detect "un momento" / "voy a buscar" dead-end responses
                # If agent said it will do something but didn't actually execute a tool,
                # re-invoke with a nudge to actually complete the action
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
                if (
                    is_dead_end
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
