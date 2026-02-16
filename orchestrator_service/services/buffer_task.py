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
    # Invocar agente con clave por tenant (Vault)
    try:
        from main import (
            get_agent_executable_for_tenant,
            build_system_prompt,
            get_now_arg,
            CLINIC_NAME,
            CLINIC_HOURS_START,
            CLINIC_HOURS_END,
        )
        tenant_row = await pool.fetchrow("SELECT clinic_name FROM tenants WHERE id = $1", tenant_id)
        clinic_name = (tenant_row["clinic_name"] or CLINIC_NAME) if tenant_row else CLINIC_NAME
        now = get_now_arg()
        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        current_time_str = f"{dias[now.weekday()]} {now.strftime('%d/%m/%Y %H:%M')}"
        system_prompt = build_system_prompt(
            clinic_name=clinic_name,
            current_time=current_time_str,
            response_language="es",
            hours_start=CLINIC_HOURS_START,
            hours_end=CLINIC_HOURS_END,
        )
        chat_history = [HumanMessage(content=m) for m in messages[:-1]]
        user_input = messages[-1]
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
    if provider == "chatwoot":
        account_id = row["external_account_id"]
        cw_conv_id = row["external_chatwoot_id"]
        
        logger.info(f"🤖 Processing Chatwoot Response | tenant={tenant_id} conv={conversation_id} ext_acc={account_id} ext_conv={cw_conv_id}")

        if account_id and cw_conv_id:
            from core.credentials import get_tenant_credential, CHATWOOT_API_TOKEN, CHATWOOT_BASE_URL
            token = await get_tenant_credential(tenant_id, CHATWOOT_API_TOKEN)
            base_url = await get_tenant_credential(tenant_id, CHATWOOT_BASE_URL) or "https://app.chatwoot.com"
            
            # Sensitive Data Masking for Logs
            token_preview = f"{token[:4]}...{token[-4:]}" if token and len(token) > 8 else "INVALID/NONE"
            logger.info(f"🔑 Credentials loaded: URL={base_url} TOKEN={token_preview}")

            if token:
                try:
                    from chatwoot_client import ChatwootClient
                    client = ChatwootClient(base_url, token)
                    # account_id y cw_conv_id recuperados de la BD (chat_conversations)
                    await client.send_text_message(account_id, cw_conv_id, response_text)
                    logger.info(f"✅ Message sent to Chatwoot successfully: {response_text[:30]}...")

                    # from_number NOT NULL en CLINICASV1.0; usamos external_user_id como identificador de la conversación
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
        logger.info("process_buffer_task_ycloud_placeholder", conv_id=conversation_id)
