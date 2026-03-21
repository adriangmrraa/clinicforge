"""
process_buffer_task: invoca agente IA y envía respuesta por Chatwoot (o YCloud).
CLINICASV1.0 - integrado con chat_conversations; usa get_agent_executable_for_tenant (Vault).
"""
import logging
import json
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
    channel: str = None
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
        logger.warning("process_buffer_task_conversation_not_found", conv_id=conversation_id)
        return
    provider = row["provider"] or "chatwoot"
    logger.info(f"🦾 Processing Buffer Task | tenant={tenant_id} conv={conversation_id} user={external_user_id} provider={provider} msgs={len(messages)}")

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
            logger.info(f"🔇 Buffer task silenced by Human Override until {override_until} for {external_user_id}")
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
            current_patient_id
        )
        
        # ✅ FIX: Establecer ContextVars para que las tools (book_appointment, etc) 
        # puedan identificar al paciente en la tarea background
        current_customer_phone.set(external_user_id)
        current_tenant_id.set(tenant_id)
        
        tenant_row = await pool.fetchrow(
            "SELECT clinic_name, address, google_maps_url, working_hours, consultation_price FROM tenants WHERE id = $1", tenant_id
        )
        clinic_name = (tenant_row["clinic_name"] or CLINIC_NAME) if tenant_row else CLINIC_NAME
        clinic_address = (tenant_row["address"] or "") if tenant_row else ""
        clinic_maps_url = (tenant_row["google_maps_url"] or "") if tenant_row else ""
        consultation_price = float(tenant_row["consultation_price"]) if tenant_row and tenant_row.get("consultation_price") else None
        clinic_working_hours = None
        if tenant_row and tenant_row.get("working_hours"):
            wh = tenant_row["working_hours"]
            clinic_working_hours = json.loads(wh) if isinstance(wh, str) else wh

        # Fetch FAQs for this tenant
        faq_rows = await pool.fetch(
            "SELECT category, question, answer FROM clinic_faqs WHERE tenant_id = $1 ORDER BY sort_order ASC, id ASC LIMIT 20",
            tenant_id
        )
        faqs = [dict(r) for r in faq_rows] if faq_rows else []
        
        # Spec 24 / Spec 06 / v7.6: Patient Identity & Appointment Context
        # Fetch patient data (normalized phone for consistency with tools)
        phone_digits = normalize_phone_digits(external_user_id)
        patient_row = await pool.fetchrow(
            """SELECT id, first_name, last_name, dni, acquisition_source, anamnesis_token, medical_history FROM patients
               WHERE tenant_id = $1 AND REGEXP_REPLACE(phone_number, '[^0-9]', '', 'g') = $2""",
            tenant_id, phone_digits
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
                identity_lines.append(f"• Nombre registrado: {p_first} {p_last}".strip())
            if p_dni:
                identity_lines.append(f"• DNI registrado: {p_dni}")
            
            # 2. Building Ad Context (Spec 06)
            meta_headline = "" # Already in patient_row if we joined or updated, checking current db state
            # Acquisition source check
            meta_source = patient_row.get("acquisition_source") or ""
            
            # Quick check for meta headline if not in main row (some schemas store it differently)
            # For simplicity, we assume attributes might have it or use what's in 'patients'
            
            # 3. Fetching Next Appointment Context
            next_apt = await pool.fetchrow("""
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
            """, tenant_id, p_id)
            
            if next_apt:
                dt = next_apt['appointment_datetime']
                from main import ARG_TZ
                if hasattr(dt, 'astimezone'): dt = dt.astimezone(ARG_TZ)
                dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
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
                identity_lines.append(f"• PRÓXIMO TURNO: Tiene un turno de {next_apt['treatment_name'] or 'Consulta'} con el/la Dr/a. {next_apt['professional_name']} el {dt_str}.")
                identity_lines.append(f"• FECHA EXACTA DEL TURNO: {dt.strftime('%d/%m/%Y')} a las {dt.strftime('%H:%M')}. {time_until}.")
            
            # Determine patient_status
            if next_apt:
                patient_status = "patient_with_appointment"
                # Resolve sede for appointment day
                if clinic_working_hours:
                    days_en = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                    apt_day_en = days_en[dt.weekday()]
                    apt_day_cfg = clinic_working_hours.get(apt_day_en, {})
                    if apt_day_cfg.get("location"):
                        identity_lines.append(f"• SEDE DEL TURNO: {apt_day_cfg['location']}")
                        if apt_day_cfg.get("address"):
                            identity_lines.append(f"• DIRECCIÓN SEDE: {apt_day_cfg['address']}")
                        if apt_day_cfg.get("maps_url"):
                            identity_lines.append(f"• MAPS SEDE: {apt_day_cfg['maps_url']}")
            else:
                patient_status = "patient_no_appointment"

            # Generate anamnesis URL (always — patient may need to update)
            import os, uuid as uuid_mod
            anamnesis_token = patient_row.get("anamnesis_token") if patient_row else None
            if not anamnesis_token:
                anamnesis_token = str(uuid_mod.uuid4())
                await pool.execute(
                    "UPDATE patients SET anamnesis_token = $1 WHERE id = $2 AND tenant_id = $3",
                    anamnesis_token, p_id, tenant_id
                )
            frontend_url = os.getenv("FRONTEND_URL", "http://localhost:4173").split(",")[0].strip().rstrip("/")
            anamnesis_url = f"{frontend_url}/anamnesis/{tenant_id}/{anamnesis_token}"

            # Check if anamnesis is already completed
            mh = patient_row.get("medical_history")
            if isinstance(mh, str):
                mh = json.loads(mh) if mh else {}
            anamnesis_completed = bool(mh and isinstance(mh, dict) and mh.get("anamnesis_completed_at"))
            if anamnesis_completed:
                identity_lines.append("• ANAMNESIS: Ya completó su ficha médica (NO enviar link automáticamente al agendar, SOLO si el paciente pide actualizar).")

            # Load linked minor patients (children) via guardian_phone
            minor_rows = await pool.fetch(
                "SELECT id, first_name, last_name, dni, phone_number, anamnesis_token FROM patients WHERE tenant_id = $1 AND guardian_phone = $2",
                tenant_id, external_user_id
            )
            if minor_rows:
                identity_lines.append("• HIJOS/MENORES VINCULADOS:")
                for minor in minor_rows:
                    m_name = f"{minor['first_name']} {minor.get('last_name', '')}".strip()
                    m_token = minor.get('anamnesis_token')
                    if not m_token:
                        m_token = str(uuid_mod.uuid4())
                        await pool.execute("UPDATE patients SET anamnesis_token = $1 WHERE id = $2", m_token, minor['id'])
                    m_anamnesis = f"{frontend_url}/anamnesis/{tenant_id}/{m_token}"
                    identity_lines.append(f"  - {m_name} (DNI: {minor.get('dni', 'N/A')}, phone_interno: {minor['phone_number']}, link ficha: {m_anamnesis})")
                    # Check minor's next appointment
                    minor_apt = await pool.fetchrow("""
                        SELECT a.appointment_datetime, tt.name as treatment_name, prof.first_name as professional_name
                        FROM appointments a
                        LEFT JOIN treatment_types tt ON a.appointment_type = tt.code
                        LEFT JOIN professionals prof ON a.professional_id = prof.id
                        WHERE a.tenant_id = $1 AND a.patient_id = $2 AND a.appointment_datetime >= NOW() AND a.status IN ('scheduled', 'confirmed')
                        ORDER BY a.appointment_datetime ASC LIMIT 1
                    """, tenant_id, minor['id'])
                    if minor_apt:
                        mdt = minor_apt['appointment_datetime']
                        if hasattr(mdt, 'astimezone'): mdt = mdt.astimezone(ARG_TZ)
                        identity_lines.append(f"    Próximo turno: {minor_apt['treatment_name'] or 'Consulta'} el {dias_semana[mdt.weekday()]} {mdt.strftime('%d/%m')} a las {mdt.strftime('%H:%M')}")

            if identity_lines:
                patient_context = "\n".join(identity_lines)

        now = get_now_arg()
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        current_time_str = f"{dias[now.weekday()]} {now.strftime('%d/%m/%Y %H:%M')}"
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
            faqs=faqs,
            patient_status=patient_status,
            consultation_price=consultation_price,
            anamnesis_url=anamnesis_url,
        )

        chat_history = []
        vision_context_str = ""
        audio_context_str = ""
        seen_multimodal = set()

        def extract_multimodal(msg_attrs):
            nonlocal vision_context_str, audio_context_str
            if not msg_attrs: return
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
            except Exception: pass

        # 4. Fetching Recent History (Spec 23)
        # We fetch the last 20 messages to ensure the agent has enough context
        db_history_dicts = await db.get_chat_history(external_user_id, limit=20, tenant_id=tenant_id)

        # --- EXTRACT CONTEXT BEFORE DEDUPLICATION (VISION FIX) ---
        for msg in db_history_dicts:
            extract_multimodal(msg.get('content_attributes'))

        # Deduplication: If the last message in DB matches the first in Buffer, remove it from history
        if db_history_dicts and messages:
            last_db_msg = db_history_dicts[-1]['content']
            first_buffer_msg = messages[0]
            if last_db_msg.strip() == first_buffer_msg.strip():
                db_history_dicts.pop()

        for msg in db_history_dicts:
            role = msg['role']
            content = msg['content']
            
            if role == 'user':
                chat_history.append(HumanMessage(content=content))
            else:
                chat_history.append(AIMessage(content=content))

        # Append buffered messages as ONE block
        user_input = "\n".join(messages)
        
        if vision_context_str:
            logger.info(f"👁️ Inyectando contexto visual: {len(vision_context_str)} chars")
            user_input += f"\n\nCONTEXTO VISUAL (Imágenes recientes):{vision_context_str}"
        
        if audio_context_str:
            logger.info(f"🎙️ Inyectando contexto de audio: {len(audio_context_str)} chars")
            user_input += f"\n\nCONTEXTO DE AUDIO (Transcripciones recientes):{audio_context_str}"

        # --- DETECCIÓN DE CONTEXTO ESPECIAL ---
        # Verificar si hay contexto especial (multimedia, seguimientos, etc.)
        has_recent_media = False
        is_followup_response = False
        media_types = []
        channel_type = "whatsapp"  # Default
        followup_context = ""
        
        try:
            # Obtener el último mensaje del usuario y el último del asistente
            context_rows = await pool.fetch("""
                SELECT cm.role, cm.content, cm.content_attributes, cc.channel 
                FROM chat_messages cm
                JOIN chat_conversations cc ON cm.conversation_id = cc.id
                WHERE cm.conversation_id = $1 
                ORDER BY cm.created_at DESC 
                LIMIT 2
            """, conversation_id)
            
            if context_rows:
                for row in context_rows:
                    if row["role"] == "user":
                        # Verificar archivos multimedia en mensaje del usuario
                        attrs = row["content_attributes"]
                        channel_type = row["channel"] or "whatsapp"
                        
                        if attrs:
                            if isinstance(attrs, str):
                                attrs = json.loads(attrs)

                            if isinstance(attrs, list):
                                for att in attrs:
                                    media_type = att.get("type", "")
                                    if media_type in ["image", "document"]:
                                        has_recent_media = True
                                        media_types.append(media_type)

                    elif row["role"] == "assistant":
                        # Verificar si el último mensaje del asistente fue un seguimiento
                        attrs = row["content_attributes"]
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
                                logger.info(f"🔍 Detectada respuesta a seguimiento post-atención")
                            
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
                minor_count = await pool.fetchval(
                    "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND guardian_phone = $2",
                    tenant_id, external_user_id
                ) or 0
            except Exception:
                minor_count = 0

            if minor_count > 0:
                media_context += (
                    "IMPORTANTE: Este paciente tiene hijos/menores vinculados. "
                    "ANTES de confirmar que guardaste el archivo, PREGUNTÁ: 'Este archivo es para tu ficha o para la de [nombre del hijo/a]?' "
                    "Si es para un menor, usá la tool 'reassign_document' con el phone_interno del menor (ej: +549...-M1) "
                    "que aparece en el contexto de HIJOS/MENORES VINCULADOS. "
                    "Si es para el interlocutor, no hagas nada extra, ya está guardado."
                )
            else:
                media_context += "Responde confirmando que recibiste el archivo y que ya lo guardaste en su ficha médica para que la Dra. lo vea. Usa un tono amable y profesional."

            special_context.append(media_context)
        
        # Contexto de respuesta a seguimiento post-atención
        if is_followup_response and followup_context:
            special_context.append(followup_context)
            logger.info("✅ Contexto de seguimiento post-atención inyectado")
        
        # Aplicar todos los contextos especiales
        if special_context:
            context_block = "\n\n".join(special_context)
            user_input = f"{context_block}\n\nMensaje del paciente: {user_input}"
        
        # --- Retry Logic con Exponential Backoff ---
        response_text = ""
        media_urls = []
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = await executor.ainvoke({
                    "input": user_input,
                    "chat_history": chat_history,
                    "system_prompt": system_prompt,
                })
                response_text = response.get("output", "") or "[Sin respuesta]"
                logger.info(f"🤖 Agent Response: {response_text[:50]}...")
                break
            except Exception as e:
                logger.warning(f"⚠️ process_buffer_task_agent_error (intento {attempt + 1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
                else:
                    logger.exception("process_buffer_task_agent_error_final", exc_info=e)
                    response_text = "Disculpas, estoy experimentando intermitencias técnicas. Consultame de nuevo en unos minutos."
                    
        # --- Extracción Multimedia Oculta ---
        if "[LOCAL_IMAGE:" in response_text:
            import re
            img_pattern = r'\[LOCAL_IMAGE:(.*?)\]'
            media_urls = re.findall(img_pattern, response_text)
            response_text = re.sub(img_pattern, '', response_text).strip()
            # Limpiar posible basura arrastrada por el tag markdown
            response_text = response_text.replace('¡IMPORTANTE PARA LA IA! El tratamiento cuenta con imágenes. Agrega obligatoriamente el siguiente texto (invisible para el usuario) en tu respuesta para que el sistema le envíe las imágenes:', '').strip()
            
    except Exception as e:
        logger.exception("process_buffer_task_fatal_error", exc_info=e)
        response_text = "Disculpas, estoy experimentando intermitencias. Consultame de nuevo en unos minutos."
        media_urls = []

    # --- SEND RESPONSE ---
    from response_sender import ResponseSender
    
    if provider == "chatwoot":
        account_id = row["external_account_id"]
        cw_conv_id = row["external_chatwoot_id"]
        
        if account_id and cw_conv_id:
            logger.info(f"🚀 Sending Chatwoot Response | tenant={tenant_id} to={external_user_id} media={len(media_urls)}")
            await ResponseSender.send_sequence(
                tenant_id=tenant_id,
                external_user_id=external_user_id,
                conversation_id=conversation_id,
                provider=provider,
                channel=row.get("channel") or "chatwoot",
                account_id=account_id,
                cw_conv_id=cw_conv_id,
                messages_text=response_text,
                media_urls=media_urls
            )
        else:
            logger.warning("process_buffer_task_chatwoot_missing_ids", conv_id=conversation_id)

    elif provider == "ycloud":
        logger.info(f"🚀 Sending YCloud Response | tenant={tenant_id} to={external_user_id} media={len(media_urls)}")
        await ResponseSender.send_sequence(
                tenant_id=tenant_id,
                external_user_id=external_user_id,
                conversation_id=conversation_id,
                provider=provider,
                channel="whatsapp",
                account_id="", # Irrelevant for ycloud
                cw_conv_id="", 
                messages_text=response_text,
                media_urls=media_urls
        )

    # --- Spec 14: Socket.IO Notification (Real-time AI Response) ---
    try:
        from main import app
        sio = getattr(app.state, "sio", None)
        to_json_safe = getattr(app.state, "to_json_safe", lambda x: x)
        
        if sio and response_text:
            await sio.emit('NEW_MESSAGE', to_json_safe({
                'phone_number': external_user_id,
                'tenant_id': tenant_id,
                'message': response_text,
                'attachments': [],
                'role': 'assistant',
                'channel': row.get("channel") or "whatsapp"
            }))
            logger.info(f"📡 Socket AI NEW_MESSAGE emitted for {external_user_id}")
            
            # Sincronizar conversación para el preview inmediato
            from db import db as db_inst
            await db_inst.sync_conversation(
                tenant_id=tenant_id,
                channel=row.get("channel") or "whatsapp",
                external_user_id=external_user_id,
                last_message=response_text,
                is_user=False
            )
    except Exception as sio_err:
        logger.error(f"⚠️ Error emitting SocketIO response: {sio_err}")
