"""
Cliente para enviar mensajes a YCloud (WhatsApp).
CLINICASV1.0 - paridad con Version Estable.
"""

import logging
import re
import os
import asyncio
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

# Max media size to download (10MB)
MAX_MEDIA_SIZE_BYTES = 10 * 1024 * 1024


def normalize_phone_e164(phone: str) -> str:
    """
    Normalize phone number to E.164 format.
    Handles Argentina numbers (549 + area + number) and international formats.

    Examples:
        "5491144445555" -> "+5491144445555"
        "+54 9 11 4444 5555" -> "+5491144445555"
        "01144445555" -> "+5491144445555"  (assuming Argentina)
    """
    # Remove all non-digit characters
    digits = re.sub(r"\D", "", phone)

    # Handle Argentina numbers: 549 + area + number
    if len(digits) == 10 and digits.startswith("11"):
        # Buenos Aires area code 11 without prefix
        return f"+54{digits}"
    elif len(digits) == 11 and digits.startswith("54"):
        # Already has country code
        return f"+{digits}"
    elif len(digits) == 10:
        # Assume Argentina local number without country code
        return f"+54{digits}"
    elif len(digits) >= 12 and digits.startswith("549"):
        # Already in 549 format
        return f"+{digits}"
    elif phone.startswith("+"):
        # Already has + prefix, just digits
        return f"+{digits}"

    # Fallback: just add +
    return f"+{digits}" if digits else phone


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
        payload = {"to": to, "type": "text", "text": {"body": text}}
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
                logger.error(
                    f"ycloud_send_failed: to={to} status={e.response.status_code} body={e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"ycloud_send_error: to={to} error={str(e)}")
                raise

    async def send_image(
        self,
        to: str,
        url: str,
        correlation_id: Optional[str] = None,
        from_number: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Envía una imagen a través de YCloud.
        """
        endpoint = f"{self.base_url}/whatsapp/messages/sendDirectly"
        sender = from_number or self.business_number
        payload = {"to": to, "type": "image", "image": {"link": url}}
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
                logger.error(
                    f"ycloud_send_image_failed: to={to} status={e.response.status_code} body={e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"ycloud_send_image_error: to={to} error={str(e)}")
                raise

    async def upload_media(self, file_path: str) -> str:
        """
        Sube un archivo a YCloud Media API y devuelve el media_id.
        
        Args:
            file_path: Ruta local al archivo a subir.
        
        Returns:
            Media ID (string) para usar en send_document_by_media_id.
        """
        import mimetypes
        endpoint = f"{self.base_url}/whatsapp/media"
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = "application/octet-stream"

        upload_headers = {
            "X-API-Key": self.api_key,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient() as client:
            try:
                with open(file_path, "rb") as f:
                    file_content = f.read()
                files = {
                    "file": (os.path.basename(file_path), file_content, mime_type),
                    "messaging_product": (None, "whatsapp"),
                }
                response = await client.post(
                    endpoint, files=files, headers=upload_headers, timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                media_id = data.get("id") or data.get("media_id", "")
                logger.info(f"✅ YCloud media uploaded: {media_id} ({file_path})")
                return media_id
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"ycloud_upload_media_failed: file={file_path} status={e.response.status_code} body={e.response.text[:300]}"
                )
                raise
            except Exception as e:
                logger.error(f"ycloud_upload_media_error: file={file_path} error={str(e)}")
                raise

    async def send_document_by_media_id(
        self,
        to_number: str,
        media_id: str,
        filename: str,
        caption: Optional[str] = None,
        from_number: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Envía un documento PDF/file a través de YCloud usando un media_id previamente subido.
        """
        endpoint = f"{self.base_url}/whatsapp/messages/sendDirectly"
        sender = from_number or self.business_number
        payload = {
            "to": to_number,
            "type": "document",
            "document": {
                "id": media_id,
                "filename": filename
            }
        }
        if caption:
            payload["document"]["caption"] = caption
        if sender:
            payload["from"] = sender

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    endpoint, json=payload, headers=self.headers, timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"✅ YCloud document sent to {to_number} via media_id: {data.get('id')}")
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"ycloud_send_document_failed: to={to_number} status={e.response.status_code} body={e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"ycloud_send_document_error: to={to_number} error={str(e)}")
                raise

    async def send_document(
        self,
        to_number: str,
        document_url: str,
        filename: str,
        caption: Optional[str] = None,
        from_number: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Envía un documento PDF/file a través de YCloud usando URL pública.
        """
        endpoint = f"{self.base_url}/whatsapp/messages/sendDirectly"
        sender = from_number or self.business_number
        payload = {
            "to": to_number,
            "type": "document",
            "document": {
                "link": document_url,
                "filename": filename
            }
        }
        if caption:
            payload["document"]["caption"] = caption
        if sender:
            payload["from"] = sender

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    endpoint, json=payload, headers=self.headers, timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"✅ YCloud document sent to {to_number}: {data.get('id')}")
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"ycloud_send_document_failed: to={to_number} status={e.response.status_code} body={e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"ycloud_send_document_error: to={to_number} error={str(e)}")
                raise

    async def send_audio(
        self,
        to: str,
        url: str,
        from_number: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Envía un audio a través de YCloud.
        """
        endpoint = f"{self.base_url}/whatsapp/messages/sendDirectly"
        sender = from_number or self.business_number
        payload = {"to": to, "type": "audio", "audio": {"link": url}}
        if sender:
            payload["from"] = sender

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    endpoint, json=payload, headers=self.headers, timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"✅ YCloud audio sent to {to}: {data.get('id')}")
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"ycloud_send_audio_failed: to={to} status={e.response.status_code} body={e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"ycloud_send_audio_error: to={to} error={str(e)}")
                raise

    async def send_template(
        self,
        to: str,
        template_name: str,
        language_code: str = "es",
        components: Optional[list] = None,
        from_number: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Envía un mensaje HSM (plantilla aprobada) a través de YCloud.
        components: lista de componentes con variables, e.g.
        [{"type": "body", "parameters": [{"type": "text", "text": "Juan"}]}]
        """
        url = f"{self.base_url}/whatsapp/messages/sendDirectly"
        sender = from_number or self.business_number
        payload: dict[str, Any] = {
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {
                    "code": language_code,
                },
            },
        }
        if components:
            payload["template"]["components"] = components
        if sender:
            payload["from"] = sender

        import json as _json
        logger.info(f"📤 TEMPLATE PAYLOAD: {_json.dumps(payload, ensure_ascii=False)[:500]}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    url, json=payload, headers=self.headers, timeout=15.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(
                    f"✅ YCloud HSM template '{template_name}' sent to {to}: {data.get('id')}"
                )
                return data
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"ycloud_send_template_failed: to={to} template={template_name} "
                    f"status={e.response.status_code} body={e.response.text}"
                )
                raise
            except Exception as e:
                logger.error(
                    f"ycloud_send_template_error: to={to} template={template_name} error={str(e)}"
                )
                raise

    async def fetch_messages(
        self,
        cursor: Optional[str] = None,
        limit: int = 100,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Fetch messages from YCloud API with cursor-based pagination.

        Args:
            cursor: Pagination cursor from previous response
            limit: Number of messages per page (max 100)
            from_date: Filter from date (ISO 8601)
            to_date: Filter to date (ISO 8601)

        Returns:
            dict with 'messages' (list), 'next_cursor' (str or None), 'has_more' (bool)
        """
        url = f"{self.base_url}/whatsapp/messages"

        # YCloud v2 API parameter names:
        # - page.size (not limit)
        # - page.after (cursor-based pagination)
        # - filter.createTime.gte / filter.createTime.lte (not fromDate/toDate)
        params: dict[str, Any] = {"page.size": min(limit, 100)}
        if cursor:
            params["page.after"] = cursor
        if from_date:
            params["filter.createTime.gte"] = from_date
        if to_date:
            params["filter.createTime.lte"] = to_date

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, headers=self.headers, params=params, timeout=30.0
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise RateLimitError(
                        f"Rate limited. Retry after {retry_after}s",
                        retry_after=retry_after,
                    )

                response.raise_for_status()
                data = response.json()

                # YCloud v2 returns messages in "items" key with cursor-based pagination
                messages = (
                    data.get("items")
                    or data.get("messages")
                    or data.get("data")
                    or data.get("results")
                    or (data if isinstance(data, list) else [])
                )

                # YCloud v2 cursor-based pagination: nextPageToken or page.after
                next_cursor = (
                    data.get("nextPageToken")
                    or data.get("nextCursor")
                    or data.get("next_cursor")
                )
                # Fallback: if no explicit cursor but we got a full page, use
                # the last item's ID as cursor (YCloud page.after accepts item IDs)
                if not next_cursor and len(messages) >= limit:
                    last_id = messages[-1].get("id") if messages else None
                    if last_id:
                        next_cursor = last_id

                page_length = data.get("length", len(messages))

                logger.info(
                    f"ycloud_fetch_messages: status={response.status_code} "
                    f"keys={list(data.keys()) if isinstance(data, dict) else 'list'} "
                    f"messages_count={len(messages)} has_next={bool(next_cursor)}"
                )

                # Log sample if first page and empty
                if not messages and not cursor:
                    logger.warning(
                        f"ycloud_fetch_messages: EMPTY response. Raw keys: "
                        f"{list(data.keys()) if isinstance(data, dict) else 'N/A'}. "
                        f"Raw body (first 500 chars): {str(data)[:500]}"
                    )

                return {
                    "messages": messages,
                    "next_cursor": next_cursor,
                    "has_more": bool(next_cursor),
                    "total": data.get("total", len(messages)),
                    "offset": data.get("offset", 0),
                    "length": page_length,
                }

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"ycloud_fetch_messages_failed: status={e.response.status_code} body={e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"ycloud_fetch_messages_error: {str(e)}")
                raise

    async def get_contacts(self, limit: int = 100, offset: int = 0) -> list:
        """Fetch WhatsApp contacts from YCloud API. Returns list of contacts with phone + name."""
        url = f"{self.base_url}/whatsapp/phoneNumbers"
        params = {"limit": min(limit, 100), "offset": offset}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=self.headers, params=params, timeout=30.0)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("items") or data.get("phoneNumbers") or data.get("data") or []
                else:
                    logger.warning(f"ycloud_get_contacts: status={response.status_code}")
                    return []
        except Exception as e:
            logger.warning(f"ycloud_get_contacts failed: {e}")
            return []

    async def get_contact_profile(self, phone_number: str) -> Optional[str]:
        """Get WhatsApp profile name for a phone number. Returns name or None."""
        # Try multiple YCloud endpoints for contact name
        endpoints = [
            f"{self.base_url}/whatsapp/phoneNumbers/{phone_number}",
            f"{self.base_url}/whatsapp/contacts/{phone_number}",
        ]
        for url in endpoints:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, headers=self.headers, timeout=10.0)
                    if response.status_code == 200:
                        data = response.json()
                        name = (
                            data.get("waName")
                            or data.get("name")
                            or data.get("profileName")
                            or data.get("pushName")
                            or data.get("displayName")
                            or data.get("display_name")
                        )
                        if name:
                            logger.info(f"ycloud_contact_profile: {phone_number} → {name} (from {url})")
                            return name
                    elif response.status_code != 404:
                        logger.debug(f"ycloud_contact_profile: {url} returned {response.status_code}: {response.text[:200]}")
            except Exception as e:
                logger.debug(f"ycloud_contact_profile failed for {url}: {e}")
        return None

    async def get_media_url(self, media_id: str) -> dict[str, Any]:
        """
        Get media URL from YCloud API.

        Args:
            media_id: The media ID from the message

        Returns:
            dict with 'url', 'mime_type', 'filename' (optional)
        """
        url = f"{self.base_url}/whatsapp/media/{media_id}"

        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(url, headers=self.headers, timeout=15.0)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise RateLimitError(
                        f"Rate limited. Retry after {retry_after}s",
                        retry_after=retry_after,
                    )

                response.raise_for_status()
                data = response.json()

                return {
                    "url": data.get("url"),
                    "mime_type": data.get("mimeType") or data.get("mime_type"),
                    "filename": data.get("filename"),
                }

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"ycloud_get_media_url_failed: media_id={media_id} status={e.response.status_code}"
                )
                raise
            except Exception as e:
                logger.error(
                    f"ycloud_get_media_url_error: media_id={media_id} error={str(e)}"
                )
                raise

    async def download_media(
        self,
        url: str,
        timeout: int = 30,
    ) -> bytes:
        """
        Download media content from URL.

        Args:
            url: The media URL to download
            timeout: Download timeout in seconds

        Returns:
            bytes of the media content
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    url, timeout=float(timeout), follow_redirects=True
                )
                response.raise_for_status()

                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_MEDIA_SIZE_BYTES:
                    raise MediaSizeError(
                        f"Media too large: {content_length} bytes (max {MAX_MEDIA_SIZE_BYTES})"
                    )

                return response.content

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"ycloud_download_media_failed: url={url} status={e.response.status_code}"
                )
                raise
            except Exception as e:
                logger.error(f"ycloud_download_media_error: url={url} error={str(e)}")
                raise


class RateLimitError(Exception):
    """Raised when YCloud API returns 429 rate limit."""

    def __init__(self, message: str, retry_after: int = 60):
        super().__init__(message)
        self.retry_after = retry_after


class MediaSizeError(Exception):
    """Raised when media exceeds max size."""

    def __init__(self, message: str):
        super().__init__(message)
