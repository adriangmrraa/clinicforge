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

        params = {"limit": min(limit, 100)}
        if cursor:
            params["pageAfter"] = cursor
        if from_date:
            params["fromDate"] = from_date
        if to_date:
            params["toDate"] = to_date

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

                messages = data.get("messages", [])
                next_cursor = data.get("nextCursor") or data.get("pageAfter")

                return {
                    "messages": messages,
                    "next_cursor": next_cursor,
                    "has_more": bool(next_cursor),
                    "total": data.get("total", len(messages)),
                }

            except httpx.HTTPStatusError as e:
                logger.error(
                    f"ycloud_fetch_messages_failed: status={e.response.status_code} body={e.response.text[:200]}"
                )
                raise
            except Exception as e:
                logger.error(f"ycloud_fetch_messages_error: {str(e)}")
                raise

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
