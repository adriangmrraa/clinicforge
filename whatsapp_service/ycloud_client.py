import os
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import structlog

logger = structlog.get_logger()

class YCloudClient:
    BASE_URL = "https://api.ycloud.com/v2"

    def __init__(self, api_key: str, business_number: str):
        self.api_key = api_key
        self.business_number = business_number
        self.headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json"
        }

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type(httpx.HTTPError)
    )
    async def _post(self, endpoint: str, json_data: dict, correlation_id: str):
        async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
            url = f"{self.BASE_URL}{endpoint}"
            response = await client.post(url, json=json_data, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def send_text(self, to: str, text: str, correlation_id: str):
        payload = {
            "from": self.business_number,
            "to": to,
            "type": "text",
            "text": {"body": text, "preview_url": True}
        }
        logger.info("ycloud_send_text", to=to, from_number=self.business_number, text_preview=text[:30], correlation_id=correlation_id)
        return await self._post("/whatsapp/messages/sendDirectly", payload, correlation_id)

    async def send_image(self, to: str, image_url: str, correlation_id: str):
        payload = {
            "from": self.business_number,
            "to": to,
            "type": "image",
            "image": {"link": image_url}
        }
        logger.info("ycloud_send_image", to=to, image_url=image_url, correlation_id=correlation_id)
        return await self._post("/whatsapp/messages/sendDirectly", payload, correlation_id)

    async def mark_as_read(self, inbound_id: str, correlation_id: str):
        logger.info("ycloud_mark_as_read", inbound_id=inbound_id, correlation_id=correlation_id)
        return await self._post(f"/whatsapp/inboundMessages/{inbound_id}/markAsRead", {}, correlation_id)

    async def typing_indicator(self, inbound_id: str, correlation_id: str):
        # The node "marcar_leido" in n8n calls typingIndicator
        logger.info("ycloud_typing_indicator", inbound_id=inbound_id, correlation_id=correlation_id)
        return await self._post(f"/whatsapp/inboundMessages/{inbound_id}/typingIndicator", {}, correlation_id)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(httpx.HTTPStatusError)
    )
    async def send_template(self, to: str, template_name: str, language_code: str, components: list, correlation_id: str):
        """
        Sends a WhatsApp template message (HSM).
        Retry logic handles transient errors like rate limits (429).
        """
        payload = {
            "from": self.business_number,
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code},
                "components": components
            }
        }
        logger.info("ycloud_send_template", to=to, template=template_name, correlation_id=correlation_id)
        return await self._post("/whatsapp/messages/sendDirectly", payload, correlation_id)
