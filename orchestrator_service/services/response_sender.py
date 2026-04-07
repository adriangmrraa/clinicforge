import asyncio
import logging
import re
from typing import List
from db import get_pool
from buffer_manager import BufferManager

logger = logging.getLogger(__name__)

# Patrón interno: [INTERNAL_NOMBRE:valor] — usado por tools como check_availability
# para pasar metadata al LLM sin que el paciente la vea.
# NUNCA tocar el output que va de vuelta al LLM (intermediate_steps).
# Solo stripear en la salida final al canal de mensajería.
_INTERNAL_MARKER_RE = re.compile(r'\[INTERNAL_[A-Z_]+:[^\]]*\]')


def _strip_internal_markers(text: str) -> str:
    """Elimina marcadores internos [INTERNAL_*:*] del texto saliente al paciente."""
    return _INTERNAL_MARKER_RE.sub('', text).strip()


class ResponseSender:
    """Clase unificada para enviar respuestas al usuario mediante burbujas (Bubble-by-bubble)."""
    
    @classmethod
    async def send_sequence(cls, tenant_id: int, external_user_id: str, conversation_id: str, 
                            provider: str, channel: str, account_id: str, cw_conv_id: str, 
                            messages_text: str, media_urls: List[str] = None):
        """
        Envía una secuencia de mensajes (texto fragmentado en burbujas) y archivos multimedia previos.
        Aplica los retrasos (BUBBLE_DELAY_SECONDS) y typing indicators de forma robusta.
        """
        if media_urls is None:
            media_urls = []

        # Eliminar marcadores internos antes de enviar al paciente
        messages_text = _strip_internal_markers(messages_text)

        pool = get_pool()
        delay = await BufferManager.get_config(pool, provider, channel, tenant_id, "bubble_delay", 3)
        typing_enabled = await BufferManager.get_config(pool, provider, channel, tenant_id, "typing_indicator", True)

        # Fragmentar el texto en burbujas con un splitter mejorado (por párrafos o puntuación larga)
        max_len = await BufferManager.get_config(pool, provider, channel, tenant_id, "max_message_length", 350)
        bot_bubbles = cls._split_into_bubbles(messages_text, max_len)
        
        # Resolver physical paths for Chatwoot attachments
        path_mapping = {}
        if media_urls:
            for url in media_urls:
                try:
                    img_id = url.split('/')[-1]
                    # This relies on UUID format, handles exception if it's not
                    row = await pool.fetchrow("SELECT file_path FROM treatment_images WHERE id::text = $1", img_id)
                    if row:
                        path_mapping[url] = row['file_path']
                except Exception as e:
                    logger.error(f"Error resolving media path for {url}: {e}")

        
        from core.credentials import get_tenant_credential
        
        if provider == "chatwoot":
            from core.credentials import CHATWOOT_API_TOKEN, CHATWOOT_BASE_URL
            token = await get_tenant_credential(tenant_id, CHATWOOT_API_TOKEN)
            base_url = await get_tenant_credential(tenant_id, CHATWOOT_BASE_URL) or "https://app.chatwoot.com"
            if not token:
                logger.error(f"❌ Missing Chatwoot Token for tenant {tenant_id}")
                return
            
            from chatwoot_client import ChatwootClient
            client = ChatwootClient(base_url, token)
            
            # --- Enviar Imágenes/Media primero ---
            for url in media_urls:
                file_path = path_mapping.get(url)
                if file_path:
                    try:
                        await client.send_attachment(account_id, cw_conv_id, file_path)
                        await asyncio.sleep(delay)
                    except Exception as e:
                        logger.error(f"❌ Error sending Chatwoot attachment: {e}")
            
            # --- Enviar Texto Fragmentado ---
            for bubble in bot_bubbles:
                if typing_enabled:
                    try:
                        # Typing On
                        await client.send_action(account_id, cw_conv_id, "typing_on")
                    except Exception as e:
                        logger.warning(f"Typing indicator failed for chatwoot: {e}")
                
                await asyncio.sleep(delay)
                
                try:
                    resp_data = await client.send_text_message(account_id, cw_conv_id, bubble)
                    cw_msg_id = resp_data.get("id")
                    
                    # Log en BD local
                    import json
                    meta_json = json.dumps({"provider": "chatwoot", "provider_message_id": str(cw_msg_id) if cw_msg_id else None})
                    await pool.execute(
                        "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                        tenant_id, conversation_id, bubble, external_user_id or "chatwoot", meta_json
                    )
                except Exception as e:
                    logger.error(f"❌ Error sending chatwoot bubble: {e}")
                    
                if typing_enabled:
                    try:
                        # Typing Off al terminar de mandar burbuja
                        await client.send_action(account_id, cw_conv_id, "typing_off")
                    except Exception: pass
                    
        elif provider == "ycloud":
            from core.credentials import YCLOUD_API_KEY, YCLOUD_WHATSAPP_NUMBER
            api_key = await get_tenant_credential(tenant_id, YCLOUD_API_KEY)
            sender_number = await pool.fetchval("SELECT bot_phone_number FROM tenants WHERE id = $1", tenant_id)
            if not sender_number:
                sender_number = await get_tenant_credential(tenant_id, YCLOUD_WHATSAPP_NUMBER)
            
            if not api_key or not sender_number:
                logger.error(f"❌ Missing YCloud Credentials for tenant {tenant_id}")
                return
                
            from ycloud_client import YCloudClient # Asume que está importable en orchestrator, si no, se moverá o aislará.
            client = YCloudClient(api_key)
            
            import uuid
            # --- Enviar Imágenes/Media primero ---
            for url in media_urls:
                try:
                    await client.send_image(external_user_id, url, correlation_id=str(uuid.uuid4()))
                    await asyncio.sleep(delay)
                except Exception as e:
                    logger.error(f"❌ Error sending YCloud image: {e}")
                    
            # --- Enviar Texto Fragmentado ---
            for bubble in bot_bubbles:
                # typing indicator
                # (ycloud lo maneja diferente o se ignorará si no hay método en YCloudClient del core, pero se intenta)
                # En main de whatsapp_service el typing recibe inbound_id. Si no lo tenemos, pasamos de largo el typing.
                
                await asyncio.sleep(delay)
                
                try:
                    yc_resp = await client.send_text_message(to=external_user_id, text=bubble, from_number=sender_number)
                    yc_msg_id = yc_resp.get("id") if isinstance(yc_resp, dict) else None
                    
                    import json
                    meta_json = json.dumps({"provider": "ycloud", "provider_message_id": str(yc_msg_id) if yc_msg_id else None})
                    await pool.execute(
                        "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                        tenant_id, conversation_id, bubble, external_user_id, meta_json
                    )
                except Exception as e:
                    logger.error(f"❌ Error sending ycloud bubble: {e}")

        elif provider == "meta_direct":
            import httpx
            import json
            page_token = await get_tenant_credential(tenant_id, "meta_page_token")
            if not page_token:
                logger.error(f"Missing meta_page_token for tenant {tenant_id}")
                return

            async with httpx.AsyncClient(timeout=10.0) as http_client:
                if channel == "whatsapp":
                    # Find phone_number_id from business_assets
                    wa_asset = await pool.fetchrow(
                        "SELECT content FROM business_assets WHERE tenant_id = $1 AND asset_type = 'whatsapp_waba' AND is_active = true LIMIT 1",
                        tenant_id
                    )
                    phone_number_id = None
                    wa_token = page_token
                    if wa_asset:
                        wa_content = wa_asset["content"] if isinstance(wa_asset["content"], dict) else json.loads(wa_asset["content"])
                        phones = wa_content.get("phone_numbers", [])
                        if phones:
                            phone_number_id = phones[0].get("id")
                        waba_token = await get_tenant_credential(tenant_id, f"META_WA_TOKEN_{wa_content.get('id')}")
                        if waba_token:
                            wa_token = waba_token

                    if not phone_number_id:
                        logger.error(f"Missing WA phone_number_id for tenant {tenant_id}")
                        return

                    for bubble in bot_bubbles:
                        await asyncio.sleep(delay)
                        try:
                            resp = await http_client.post(
                                f"https://graph.facebook.com/v22.0/{phone_number_id}/messages",
                                headers={"Authorization": f"Bearer {wa_token}", "Content-Type": "application/json"},
                                json={
                                    "messaging_product": "whatsapp",
                                    "recipient_type": "individual",
                                    "to": external_user_id,
                                    "type": "text",
                                    "text": {"body": bubble}
                                }
                            )
                            meta_json = json.dumps({"provider": "meta_direct", "status": resp.status_code})
                            await pool.execute(
                                "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                                tenant_id, conversation_id, bubble, external_user_id, meta_json
                            )
                        except Exception as e:
                            logger.error(f"Error sending meta_direct WA bubble: {e}")
                else:
                    # Facebook Messenger / Instagram DM
                    for bubble in bot_bubbles:
                        await asyncio.sleep(delay)
                        try:
                            resp = await http_client.post(
                                "https://graph.facebook.com/v22.0/me/messages",
                                params={"access_token": page_token},
                                json={
                                    "recipient": {"id": external_user_id},
                                    "message": {"text": bubble},
                                    "messaging_type": "RESPONSE"
                                }
                            )
                            meta_json = json.dumps({"provider": "meta_direct", "status": resp.status_code})
                            await pool.execute(
                                "INSERT INTO chat_messages (tenant_id, conversation_id, role, content, from_number, platform_metadata) VALUES ($1, $2, 'assistant', $3, $4, $5::jsonb)",
                                tenant_id, conversation_id, bubble, external_user_id, meta_json
                            )
                        except Exception as e:
                            logger.error(f"Error sending meta_direct IG/FB bubble: {e}")

            logger.info(f"Meta Direct response sent: channel={channel} to={external_user_id} bubbles={len(bot_bubbles)}")

    @staticmethod
    def _split_into_bubbles(text: str, max_length: int = 400) -> List[str]:
        """Fragmenta inteligentemente un mensaje basado en saltos de línea y puntuación final."""
        if not text:
             return []
        
        # Primero intentar separar por dobles saltos de línea (párrafos)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        result = []
        
        for p in paragraphs:
            if len(p) <= max_length:
                result.append(p)
            else:
                # Si el párrafo es muy largo, cortarlo por puntuaciones (. ? !)
                # Usamos una regex que capture el delimitador y lo deje anexado al string
                sentences = re.split(r'(?<=[.!?])\s+', p)
                current_bubble = ""
                for sentence in sentences:
                    if not sentence: continue
                    if len(current_bubble) + len(sentence) + 1 <= max_length:
                        current_bubble += (" " + sentence if current_bubble else sentence)
                    else:
                        if current_bubble: result.append(current_bubble)
                        current_bubble = sentence
                if current_bubble:
                    result.append(current_bubble)
                    
        return result
