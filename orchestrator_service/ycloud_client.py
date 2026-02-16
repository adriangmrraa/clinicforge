"""
Cliente para enviar mensajes a YCloud (WhatsApp).
CLINICASV1.0 - paridad con Version Estable.
"""
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

class YCloudClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.ycloud.com/v1"
        self.headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def send_text_message(
        self, to: str, text: str, from_number: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Envía un mensaje de texto libre a través de YCloud.
        Normalmente usado dentro de la ventana de 24h.
        """
        url = f"{self.base_url}/whatsapp/messages"
        payload = {
            "to": to,
            "type": "text",
            "text": {"body": text}
        }
        if from_number:
            payload["from"] = from_number

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self.headers, timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"✅ YCloud message sent to {to}: {data.get('id')}")
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    "ycloud_send_failed",
                    to=to,
                    status=e.response.status_code,
                    body=e.response.text[:200],
                )
                raise
            except Exception as e:
                logger.error(
                    "ycloud_send_error",
                    to=to,
                    error=str(e),
                )
                raise
