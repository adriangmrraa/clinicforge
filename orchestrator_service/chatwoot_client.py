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
                raise
            except Exception as e:
                logger.error(
                    "chatwoot_send_error",
                    account_id=account_id,
                    conv_id=conversation_id,
                    error=str(e),
                )
                raise

    async def send_attachment(
        self, account_id: int, conversation_id: int, file_path: str, message: str = ""
    ) -> dict[str, Any]:
        """Envía un archivo adjunto a una conversación Chatwoot."""
        import os
        
        url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
        
        if not os.path.exists(file_path):
             raise FileNotFoundError(f"Attachment not found: {file_path}")

        file_name = os.path.basename(file_path)
        # Determinar MIME type básico
        import mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
             mime_type = "application/octet-stream"
             
        # Chatwoot espera multipart/form-data
        # 'content': mensaje opcional
        # 'attachments[]': archivo(s)
        # 'message_type': 'outgoing'
        
        data = {
            "content": message,
            "message_type": "outgoing"
        }
        
        files = {
            "attachments[]": (file_name, open(file_path, "rb"), mime_type)
        }
        
        # Ojo: headers no debe tener Content-Type para multipart (httpx lo pone automático con boundary)
        headers_multipart = {
            "api_access_token": self.headers["api_access_token"]
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, data=data, files=files, headers=headers_multipart, timeout=30.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "chatwoot_attachment_failed",
                    account_id=account_id,
                    conv_id=conversation_id,
                    status=e.response.status_code,
                    body=e.response.text[:200],
                )
                raise
            except Exception as e:
                logger.error(
                    "chatwoot_attachment_error",
                    account_id=account_id,
                    conv_id=conversation_id,
                    error=str(e),
                )
                raise
