"""
Cliente para enviar mensajes a Chatwoot (salida).
CLINICASV1.0 - paridad con Version Estable.
"""
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class ChatwootClient:
    def __init__(self, base_url: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "api_access_token": api_token,
            "Content-Type": "application/json",
        }

    async def send_text_message(
        self, account_id: int, conversation_id: int, text: str
    ) -> dict[str, Any]:
        """Envía un mensaje de texto a una conversación Chatwoot."""
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
        payload = {"content": text, "message_type": "outgoing"}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self.headers, timeout=10.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "chatwoot_send_failed",
                    account_id=account_id,
                    conv_id=conversation_id,
                    status=e.response.status_code,
                    body=e.response.text[:200],
                )
                raise
            except Exception as e:
                logger.error(
                    "chatwoot_send_error",
                    account_id=account_id,
                    conv_id=conversation_id,
                    error=str(e),
                )
                raise
