from typing import List, Dict, Any, Optional
import json
import logging
from .base import ChannelAdapter
from .types import CanonicalMessage, MediaItem, MediaType

logger = logging.getLogger(__name__)

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
        
        sender = payload.get("sender", {})
        sender_id = str(sender.get("id"))
        
        # Extraer metadatos ricos del sender
        sender_data = {
            "id": sender.get("id"),
            "name": sender.get("name"),
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
        
        # 4. Construir Canonical
        canonical = CanonicalMessage(
            provider="chatwoot",
            original_channel=nexus_channel,
            external_user_id=sender_id, # ID interno de CW, Service resolverá el real
            display_name=sender_data["name"],
            tenant_id=tenant_id,
            content=content,
            media=media_items,
            is_agent=(msg_type == "outgoing"),
            raw_payload=payload,
            sender=sender_data # Nuevo campo rico
        )
        
        self._log_normalization("Chatwoot", 1, [str(m.type) for m in media_items])
        return [canonical]

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
