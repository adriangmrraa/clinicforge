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
            CLINIC_NAME,
            CLINIC_HOURS_START,
            CLINIC_HOURS_END,
            db,  # Import db wrapper for get_chat_history
        )
        tenant_row = await pool.fetchrow("SELECT clinic_name FROM tenants WHERE id = $1", tenant_id)
        clinic_name = (tenant_row["clinic_name"] or CLINIC_NAME) if tenant_row else CLINIC_NAME
        
        # Spec 24 / Spec 06: Ad Context Logic (Parity)
        # Fetch patient data to detect Ad Context
        patient_row = await pool.fetchrow(
            "SELECT meta_ad_headline, acquisition_source FROM patients WHERE tenant_id = $1 AND phone_number = $2",
            tenant_id, external_user_id
        )
        ad_context = ""
        if patient_row:
            meta_headline = patient_row.get("meta_ad_headline") or ""
            meta_source = patient_row.get("acquisition_source") or ""
            if meta_source and meta_source != "ORGANIC" and meta_headline:
                urgency_ad_keywords = ["urgencia", "dolor", "emergencia", "trauma", "emergency", "pain", "urgent"]
                is_urgency_ad = any(kw in meta_headline.lower() for kw in urgency_ad_keywords)
                if is_urgency_ad:
                    ad_context = (
                        f"• EL PACIENTE VIENE DE UN ANUNCIO DE URGENCIA: \"{meta_headline}\".\n"
                        f"• PRIORIZA EL TRIAJE CLÍNICO sobre la captura de datos administrativos.\n"
                        f"• Preguntá inmediatamente por el dolor/síntoma y usá 'triage_urgency' cuanto antes.\n"
                        f"• Recién después del triaje, procedé con datos (nombre, DNI, obra social)."
                    )
                else:
                    ad_context = (
                        f"• El paciente llegó desde un anuncio de Meta Ads: \"{meta_headline}\".\n"
                        f"• Podés personalizar el saludo mencionando el tema del anuncio de forma natural."
                    )

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
        )

        # Spec 24: Fetch DB Metadata History (Fix Amnesia)
        # Fetch last 10 messages from DB to give context
        db_history_dicts = await db.get_chat_history(external_user_id, limit=10, tenant_id=tenant_id)
        
        # Deduplication: If the last message in DB matches the first in Buffer, remove it from history
        if db_history_dicts and messages:
            last_db_msg = db_history_dicts[-1]['content']
            first_buffer_msg = messages[0]
            if last_db_msg.strip() == first_buffer_msg.strip():
                db_history_dicts.pop()

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

        for msg in db_history_dicts:
            role = msg['role']
            content = msg['content']
            attrs = msg.get('content_attributes')
            
            # Extract context from history
            extract_multimodal(attrs)
            
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

        executor = await get_agent_executable_for_tenant(tenant_id)
        logger.info(f"🧠 Invoking Agent for {external_user_id}...")
        response = await executor.ainvoke({
            "input": user_input,
            "chat_history": chat_history,
            "system_prompt": system_prompt,
        })
        response_text = response.get("output", "") or "[Sin respuesta]"
        logger.info(f"🤖 Agent Response: {response_text[:50]}...")
    except Exception as e:
        logger.exception("process_buffer_task_agent_error", error=str(e))
        response_text = "[Error al procesar. Intente de nuevo.]"

    # --- SEND RESPONSE ---
    if provider == "chatwoot":
        account_id = row["external_account_id"]
        cw_conv_id = row["external_chatwoot_id"]
        
        if account_id and cw_conv_id:
            from core.credentials import get_tenant_credential, CHATWOOT_API_TOKEN, CHATWOOT_BASE_URL
            token = await get_tenant_credential(tenant_id, CHATWOOT_API_TOKEN)
            base_url = await get_tenant_credential(tenant_id, CHATWOOT_BASE_URL) or "https://app.chatwoot.com"
            
            if token:
                try:
                    from chatwoot_client import ChatwootClient
                    client = ChatwootClient(base_url, token)
                    resp_data = await client.send_text_message(account_id, cw_conv_id, response_text)
                    cw_msg_id = resp_data.get("id")
                    logger.info(f"✅ Message sent to Chatwoot/Meta successfully: {response_text[:30]}... ID: {cw_msg_id}")

                    # Spec 34: Guardar provider_message_id para deduplicación robusta
                    meta_json = json.dumps({
                        "provider": "chatwoot", 
                        "provider_message_id": str(cw_msg_id) if cw_msg_id else None
                    })

                    await pool.execute(
                        """
                        INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata)
                        VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)
                        """,
                        tenant_id, conversation_id, response_text, external_user_id or "chatwoot", meta_json
                    )
                except Exception as send_err:
                    logger.exception(f"❌ Failed sending to Chatwoot/Meta: {send_err}")
            else:
                 logger.error(f"❌ Missing Chatwoot Token for tenant {tenant_id}")
        else:
            logger.warning("process_buffer_task_chatwoot_missing_ids", conv_id=conversation_id)

    elif provider == "ycloud":
        logger.info(f"🚀 Sending YCloud Response | tenant={tenant_id} to={external_user_id}")
        try:
            from core.credentials import get_tenant_credential, YCLOUD_API_KEY, YCLOUD_WHATSAPP_NUMBER
            api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
            sender_number = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)
            
            if api_key and sender_number:
                from ycloud_client import YCloudClient
                client = YCloudClient(api_key, sender_number)
                await client.send_whatsapp_text(external_user_id, response_text)
                logger.info(f"✅ Message sent to YCloud successfully: {response_text[:30]}...")
                
                await pool.execute(
                    """
                    INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number)
                    VALUES ($1, $2, 'assistant', $3, $4)
                    """,
                    tenant_id, conversation_id, response_text, external_user_id,
                )
            else:
                logger.error(f"❌ Missing YCloud Credentials for tenant {tenant_id}")
        except Exception as send_err:
             logger.error(f"❌ Failed sending to YCloud: {send_err}")

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
