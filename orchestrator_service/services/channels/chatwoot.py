from typing import List, Dict, Any, Optional
import json
import logging
from .base import ChannelAdapter
from .types import CanonicalMessage, MediaItem, MediaType
import sys
import os
import uuid
import structlog

# Ensure services path is available
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from buffer_manager import BufferManager

# Configurar db_pool
from db import db

logger = structlog.get_logger(__name__)

class ChatwootAdapter(ChannelAdapter):
    """
    Adapter para normalizar webhooks de Chatwoot.
    Maneja canales: Instagram, Facebook, WhatsApp (vía CW), Website.
    """

    async def normalize_payload(self, payload: Dict[str, Any], tenant_id: int) -> List[CanonicalMessage]:
        if payload.get("event") != "message_created":
            return []
            
        if payload.get("private", False):
            return []

        # 1. Resolver Canal
        conversation = payload.get("conversation", {})
        cw_channel = conversation.get("channel", "").lower()
        
        nexus_channel = "chatwoot"
        if "whatsapp" in cw_channel: nexus_channel = "whatsapp"
        elif "instagram" in cw_channel: nexus_channel = "instagram"
        elif "facebook" in cw_channel: nexus_channel = "facebook"
        
        # 2. Resolver Contenido y Sender
        msg_type = payload.get("message_type", "incoming")
        content = payload.get("content") or ""
        
        sender = payload.get("sender") or {}
        if not sender:
            # Some Chatwoot events (system, status) have no sender — skip
            return []
        sender_id = str(sender.get("id", ""))
        
        # Extraer metadatos ricos del sender
        import re
        raw_name = sender.get("name") or "Visitante"
        # Limpiar etiquetas de IG/FB como "| Contenido Orgánico"
        clean_name = re.sub(r'\s*\|\s*Contenido Orgánico.*', '', raw_name, flags=re.IGNORECASE).strip()

        sender_data = {
            "id": sender.get("id"),
            "name": clean_name,
            "avatar": sender.get("avatar_url") or sender.get("thumbnail"),
            "email": sender.get("email"),
            "phone": sender.get("phone_number"),
            "type": sender.get("type")  # "contact" or "user"
        }
        
        # Fallback: Si el nombre parece un ID o está vacío, intentar usar meta de conversación
        conversation_meta = conversation.get("meta", {}).get("sender", {})
        if not sender_data["name"] or str(sender_data["name"]) == sender_id:
            if conversation_meta.get("name"):
                sender_data["name"] = conversation_meta.get("name")
            if conversation_meta.get("thumbnail"):
                sender_data["avatar"] = conversation_meta.get("thumbnail")

        # 3. Procesar Adjuntos
        media_items = self._extract_media(payload)
        
        # 3. Determinar external_user_id (Priorizar username para IG/FB si existe en meta)
        # Spec 30: Usamos handles si están disponibles para evitar duplicados en DB
        target_external_id = sender_id

        # FIX: Si es outgoing (agente), el sender_id es del agente, pero necesitamos el del contacto.
        # Intentamos obtenerlo de meta.sender
        is_outgoing = (msg_type == "outgoing")
        
        if is_outgoing:
             # En outgoing, confiamos en conversation.meta validados.
             contact_meta = conversation.get("meta", {}).get("sender", {})
             contact_eff_id = str(contact_meta.get("id"))
             
             # Si nexus_channel es ig/fb, intentamos username primero
             if nexus_channel in ["instagram", "facebook"]:
                 username = contact_meta.get("username")
                 if username:
                     target_external_id = str(username).strip().lower()
                 elif contact_eff_id and contact_eff_id != "None":
                     target_external_id = contact_eff_id
             else:
                 # WhatsApp / Web: Usar ID numérico del contacto si existe
                 if contact_eff_id and contact_eff_id != "None":
                      target_external_id = contact_eff_id
                 # Fallback: source_id
                 elif conversation.get("contact_inbox", {}).get("source_id"):
                      target_external_id = conversation.get("contact_inbox", {}).get("source_id")

        else:
            # Incoming: Sender ES el contacto
            if nexus_channel in ["instagram", "facebook"]:
                username = conversation.get("meta", {}).get("sender", {}).get("username")
                if username:
                    # Normalizar: lowercase y strip para evitar duplicados por casing (Spec 31)
                    target_external_id = str(username).strip().lower()
                    logger.info(f"🆔 Using normalized username '{target_external_id}' as external_id for {nexus_channel}")

        # 4. Procesar Adjuntos
        media_items = self._extract_media(payload)
        
        # 5. Construir Canonical
        canonical = CanonicalMessage(
            provider="chatwoot",
            original_channel=nexus_channel,
            external_user_id=target_external_id,
            display_name=sender_data["name"],
            tenant_id=tenant_id,
            content=content,
            media=media_items,
            is_agent=(msg_type == "outgoing"),
            raw_payload=payload,
            sender=sender_data
        )
        
        # 6. Encolar en BufferManager (Nuevo Flujo Robusto)
        # Spec 32: Devolvemos lista vacía al llamador original porque el 
        #   BufferManager procesará la ráfaga de forma asíncrona.
        if not is_outgoing:
            try:
                # Obtener pool
                pool = getattr(db, "pool", None)
                
                # Transformar media_items
                media_dicts = [{"type": m.type.value, "url": m.url, "mime_type": m.mime_type, "file_name": m.file_name} for m in media_items]
                correlation_id = payload.get("id", str(uuid.uuid4()))
                message_data = {
                    "text": content,
                    "provider": "chatwoot",
                    "channel": nexus_channel,
                    "business_info": {
                        "account_id": payload.get("account", {}).get("id"),
                        "conversation_id": conversation.get("id"),
                        "inbox_id": payload.get("inbox", {}).get("id")
                    },
                    "correlation_id": correlation_id,
                    "media": media_dicts
                }
                
                from ..redis_client import get_redis
                redis_client = get_redis()
                
                import asyncio
                asyncio.create_task(
                    BufferManager.enqueue_message(
                        redis_client=redis_client,
                        db_pool=pool,
                        provider="chatwoot",
                        channel=nexus_channel,
                        tenant_id=tenant_id,
                        external_user_id=target_external_id,
                        message_data=message_data
                    )
                )
                self._log_normalization("Chatwoot", 1, [str(m.type) for m in media_items])
                
            except Exception as e:
                logger.error("chatwoot_buffer_enqueue_error", error=str(e), tenant_id=tenant_id)
        
        return [] # Se procesará asíncronamente en batch

    def _extract_media(self, payload: Dict[str, Any]) -> List[MediaItem]:
        items = []
        attachments = payload.get("attachments", [])
        
        for att in attachments:
            url = att.get("data_url") or att.get("source_url")
            if not url: continue
            
            # Detectar tipo
            file_type = att.get("file_type") or "file"
            mime_type = self._guess_mime(url, att.get("file_type"))
            
            # Fix Audio Meta: Muchas veces Meta manda audio como content-type application/octet-stream o video/mp4
            # Si el file_type dice "audio" O la extensión es de audio
            final_type = MediaType.DOCUMENT
            
            if file_type == "image":
                final_type = MediaType.IMAGE
            elif file_type == "audio":
                final_type = MediaType.AUDIO
            elif file_type == "video":
                final_type = MediaType.VIDEO
                # Check fake video (audio only)
                if mime_type and "audio" in mime_type:
                    final_type = MediaType.AUDIO
            else:
                # Fallback por extension
                lower_url = url.lower()
                if any(x in lower_url for x in [".mp3", ".ogg", ".wav", ".m4a", ".aac"]):
                    final_type = MediaType.AUDIO
                elif any(x in lower_url for x in [".jpg", ".jpeg", ".png", ".webp", ".gif"]):
                    final_type = MediaType.IMAGE
                elif any(x in lower_url for x in [".mp4", ".mov"]):
                    final_type = MediaType.VIDEO
            
            items.append(MediaItem(
                type=final_type,
                url=url,
                file_name=att.get("file_name") or "attachment",
                mime_type=mime_type,
                file_size=att.get("file_size")
            ))
            
        return items

    def _guess_mime(self, url: str, provided_type: Optional[str]) -> Optional[str]:
        # Simple helper
        if provided_type and "/" in provided_type: return provided_type
        import mimetypes
        guess, _ = mimetypes.guess_type(url)
        return guess
