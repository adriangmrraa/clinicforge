"""
process_buffer_task: invoca agente IA y envía respuesta por Chatwoot (o YCloud).
CLINICASV1.0 - integrado con chat_conversations; usa get_agent_executable_for_tenant (Vault).
"""
import logging
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
        # (This happens because main.py inserts user message BEFORE buffering)
        if db_history_dicts and messages:
            last_db_msg = db_history_dicts[-1]['content']
            first_buffer_msg = messages[0]
            if last_db_msg.strip() == first_buffer_msg.strip():
                # We want to avoid the agent seeing the same message twice.
                # Since 'messages' (buffer) contains the user input we want to react to,
                # we remove it from 'chat_history' so it doesn't appear as "already said".
                db_history_dicts.pop()

        chat_history = []
        for msg in db_history_dicts:
            if msg['role'] == 'user':
                chat_history.append(HumanMessage(content=msg['content']))
            else:
                chat_history.append(AIMessage(content=msg['content']))

        # Append buffered messages as ONE block (or separate? Plan said unified input)
        # Usually we join them to simulate a single long message
        user_input = "\n".join(messages)
        
        # Spec 23: Inyección de Contexto Visual (Multimodalidad diferida)
        # Busamos descripciones de imágenes recientes (últimos 5 min) para dar contexto al bot
        try:
             # Using uuid cast for conversation_id
             img_rows = await pool.fetch(
                 """
                 SELECT content_attributes 
                 FROM chat_messages 
                 WHERE conversation_id = $1 
                   AND role = 'user' 
                   AND created_at > NOW() - INTERVAL '5 minutes'
                   AND content_attributes IS NOT NULL
                 ORDER BY created_at ASC
                 """,
                 conversation_id 
             )
             
             vision_context_str = ""
             seen_desc = set()
             
             import json
             for r in img_rows:
                 if not r["content_attributes"]: continue
                 try:
                     attrs = r["content_attributes"]
                     if isinstance(attrs, str):
                         attrs = json.loads(attrs)
                     
                     if isinstance(attrs, list):
                         for att in attrs:
                             desc = att.get("description")
                             if desc and desc not in seen_desc:
                                 vision_context_str += f"\n[IMAGEN: {desc}]"
                                 seen_desc.add(desc)
                 except Exception:
                     pass

             if vision_context_str:
                 logger.info(f"👁️ Inyectando contexto visual: {len(vision_context_str)} chars")
                 user_input += f"\n\nCONTEXTO VISUAL (Imágenes recientes):{vision_context_str}"

        except Exception as vision_err:
             logger.warning(f"⚠️ Error leyendo contexto visual: {vision_err}")

        executor = await get_agent_executable_for_tenant(tenant_id)
        response = await executor.ainvoke({
            "input": user_input,
            "chat_history": chat_history,
            "system_prompt": system_prompt,
        })
        response_text = response.get("output", "") or "[Sin respuesta]"
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
                    await client.send_text_message(account_id, cw_conv_id, response_text)
                    logger.info(f"✅ Message sent to Chatwoot successfully: {response_text[:30]}...")

                    await pool.execute(
                        """
                        INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number)
                        VALUES ($1, $2, 'assistant', $3, $4)
                        """,
                        tenant_id, conversation_id, response_text, external_user_id or "chatwoot",
                    )
                except Exception as send_err:
                    logger.exception(f"❌ Failed sending to Chatwoot: {send_err}")
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
