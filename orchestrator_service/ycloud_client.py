"""
Cliente para enviar mensajes a YCloud (WhatsApp).
CLINICASV1.0 - paridad con Version Estable.
"""
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

class YCloudClient:
    def __init__(self, api_key: str, business_number: Optional[str] = None):
        self.api_key = api_key
        self.business_number = business_number
        self.base_url = "https://api.ycloud.com/v2"
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
        """
        url = f"{self.base_url}/whatsapp/messages/sendDirectly"
        sender = from_number or self.business_number
        payload = {
            "to": to,
            "type": "text",
            "text": {"body": text}
        }
        if sender:
            payload["from"] = sender

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
                logger.error(f"ycloud_send_failed: to={to} status={e.response.status_code} body={e.response.text[:200]}")
                raise
            except Exception as e:
                logger.error(f"ycloud_send_error: to={to} error={str(e)}")
                raise

    async def send_image(
        self, to: str, url: str, correlation_id: Optional[str] = None, from_number: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Envía una imagen a través de YCloud.
        """
        endpoint = f"{self.base_url}/whatsapp/messages/sendDirectly"
        sender = from_number or self.business_number
        payload = {
            "to": to,
            "type": "image",
            "image": {"link": url}
        }
        if sender:
            payload["from"] = sender

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    endpoint, json=payload, headers=self.headers, timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"✅ YCloud image sent to {to}: {data.get('id')}")
                return data
            except httpx.HTTPStatusError as e:
                logger.error(f"ycloud_send_image_failed: to={to} status={e.response.status_code} body={e.response.text[:200]}")
                raise
            except Exception as e:
                logger.error(f"ycloud_send_image_error: to={to} error={str(e)}")
                raise
