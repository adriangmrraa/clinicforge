import hmac
import hashlib
import structlog
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException

logger = structlog.get_logger()


class MetaWebhookService:
    """
    Validates and Normalizes Meta Webhook Events.
    Supports: Messenger, Instagram Direct, WhatsApp Cloud API.
    """

    def __init__(self, verify_token: str, app_secret: str):
        self.verify_token = verify_token
        self.app_secret = app_secret

    def verify_challenge(self, mode: str, token: str, challenge: str):
        """Handles the GET /webhook verification challenge."""
        if mode == "subscribe" and token == self.verify_token:
            # Meta sends numeric challenges, but return as plain text to be safe
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(content=challenge)
        raise HTTPException(status_code=403, detail="Verification failed")

    async def verify_signature(self, request: Request):
        """Validates X-Hub-Signature-256 header."""
        signature = request.headers.get("X-Hub-Signature-256")
        if not signature:
            if not self.app_secret:
                return
            raise HTTPException(status_code=403, detail="Missing signature")

        body = await request.body()
        expected = hmac.new(
            self.app_secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(f"sha256={expected}", signature):
            raise HTTPException(status_code=403, detail="Invalid signature")

    def normalize_payload(self, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Main routing logic to parse the incoming webhook object.
        Returns a normalized 'SimpleEvent' dict or None if ignored.
        """
        object_type = body.get("object")
        entry = body.get("entry", [])

        if not entry:
            return None

        platform = "unknown"
        if object_type == "page":
            platform = "facebook"
        elif object_type == "instagram":
            platform = "instagram"
        elif object_type == "whatsapp_business_account":
            platform = "whatsapp"

        change = entry[0]

        if platform == "whatsapp":
            return self._normalize_whatsapp(change)
        elif platform == "facebook":
            messaging = change.get("messaging", [])
            if messaging:
                return self._normalize_messenger(messaging[0], "facebook")
            return None
        elif platform == "instagram":
            messaging = change.get("messaging", [])
            if messaging:
                return self._normalize_messenger(messaging[0], "instagram")

        return None

    def _normalize_whatsapp(self, change: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Normalizes WhatsApp Cloud API Payload."""
        value = change.get("changes", [{}])[0].get("value", {})
        messages = value.get("messages", [])

        if not messages:
            return None

        msg = messages[0]
        contact = value.get("contacts", [{}])[0]
        metadata = value.get("metadata", {})

        return {
            "provider": "meta",
            "platform": "whatsapp",
            "tenant_identifier": metadata.get("display_phone_number"),
            "event_type": "message",
            "timestamp": msg.get("timestamp"),
            "recipient_id": metadata.get("display_phone_number") or metadata.get("phone_number_id"),
            "sender_id": msg.get("from"),
            "sender_name": contact.get("profile", {}).get("name"),
            "payload": {
                "id": msg.get("id"),
                "type": msg.get("type"),
                "text": msg.get("text", {}).get("body") if msg.get("type") == "text" else None,
                "media_url": None
            }
        }

    def _normalize_messenger(self, messaging: Dict[str, Any], platform: str) -> Optional[Dict[str, Any]]:
        """Normalizes Messenger / Instagram Direct Payload."""
        sender_id = messaging.get("sender", {}).get("id")
        recipient_id = messaging.get("recipient", {}).get("id")
        timestamp = messaging.get("timestamp")

        message = messaging.get("message", {})
        if not message:
            return None

        # CRITICAL: Filter echo messages to prevent infinite loops
        if message.get("is_echo"):
            logger.info("echo_filtered", platform=platform, sender=sender_id)
            return None

        return {
            "provider": "meta",
            "platform": platform,
            "tenant_identifier": recipient_id,
            "event_type": "message",
            "timestamp": timestamp,
            "recipient_id": recipient_id,
            "sender_id": sender_id,
            "sender_name": "User",
            "payload": {
                "id": message.get("mid"),
                "type": "text" if message.get("text") else "image",
                "text": message.get("text"),
                "media_url": (
                    message.get("attachments", [{}])[0].get("payload", {}).get("url")
                    if message.get("attachments") else None
                )
            }
        }
