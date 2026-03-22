from typing import List, Dict, Any
import logging
from .base import ChannelAdapter
from .types import CanonicalMessage, MediaItem, MediaType

logger = logging.getLogger(__name__)


class MetaDirectAdapter(ChannelAdapter):
    """
    Adapter for normalizing SimpleEvents from the meta_service (The Meta Diplomat).
    Converts Meta Graph API webhook payloads (already normalized to SimpleEvent format)
    into CanonicalMessage for the unified processing pipeline.
    """

    async def normalize_payload(self, payload: Dict[str, Any], tenant_id: int) -> List[CanonicalMessage]:
        if payload.get("provider") != "meta":
            return []

        platform = payload.get("platform", "facebook")
        event_type = payload.get("event_type")

        if event_type != "message":
            return []

        inner = payload.get("payload", {})
        text = inner.get("text")
        media_url = inner.get("media_url")
        msg_type = inner.get("type", "text")

        if not text and not media_url:
            return []

        media = []
        if media_url:
            type_map = {
                "image": MediaType.IMAGE,
                "video": MediaType.VIDEO,
                "audio": MediaType.AUDIO,
                "document": MediaType.DOCUMENT,
            }
            media.append(MediaItem(
                type=type_map.get(msg_type, MediaType.IMAGE),
                url=media_url,
                file_name="attachment"
            ))

        sender_id = payload.get("sender_id", "")
        sender_name = payload.get("sender_name")

        canonical = CanonicalMessage(
            provider="meta_direct",
            original_channel=platform,
            external_user_id=sender_id,
            display_name=sender_name if sender_name and sender_name != "User" else None,
            tenant_id=tenant_id,
            content=text,
            media=media,
            is_agent=False,
            raw_payload=payload,
            sender={
                "id": sender_id,
                "name": sender_name,
            }
        )

        self._log_normalization("meta_direct", 1, [platform])
        return [canonical]
