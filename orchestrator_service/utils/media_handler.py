"""
Media download and storage utilities.

Handles downloading media files from external providers (YCloud, Chatwoot)
and serving them locally to avoid URL expiration issues.
"""

import httpx
import uuid
import mimetypes
from pathlib import Path
from urllib.parse import urlparse
import structlog

logger = structlog.get_logger()

async def download_and_save_media(
    media_url: str,
    tenant_id: int,
    media_type: str,
    correlation_id: str
) -> str | None:
    """
    Download media from external URL (YCloud, Chatwoot) and save locally.
    
    Args:
        media_url: External URL to download from
        tenant_id: Tenant ID for path separation (/media/{tenant_id}/)
        media_type: Type hint - 'audio', 'image', or 'document'
        correlation_id: For logging context
        
    Returns:
        Local filename (UUID.ext) if successful, None if download fails
        
    Example:
        >>> filename = await download_and_save_media(
        ...     "https://ycloud.com/media/audio.ogg",
        ...     tenant_id=1,
        ...     media_type="audio",
        ...     correlation_id="abc-123"
        ... )
        >>> print(filename)
        'd17c7320-7b1c-4237-91f7-8508bc0b7bda.ogg'
    """
    try:
        # Determine file extension
        ext_map = {
            "audio": ".ogg",
            "image": ".jpg",
            "document": ".pdf"
        }
        default_ext = ext_map.get(media_type, ".bin")
        
        # Try to extract extension from URL path
        parsed = urlparse(media_url)
        url_ext = Path(parsed.path).suffix
        extension = url_ext if url_ext else default_ext
        
       # Generate unique filename
        filename = f"{uuid.uuid4()}{extension}"
        
        # Ensure directory exists (with parents for multi-tenant structure)
        media_dir = Path("/app/media") / str(tenant_id)
        media_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = media_dir / filename
        
        # Download file with timeout
        logger.info(
            "📥 Downloading media",
            url=media_url[:60] + "..." if len(media_url) > 60 else media_url,
            filename=filename,
            tenant_id=tenant_id,
            correlation_id=correlation_id
        )
        
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            response = await client.get(media_url, follow_redirects=True)
            response.raise_for_status()
            
            # Validate content
            if len(response.content) == 0:
                logger.warning(
                    "⚠️ Empty media file",
                    url=media_url,
                    correlation_id=correlation_id
                )
                return None
            
            # Save to disk
            with open(file_path, "wb") as f:
                f.write(response.content)
            
            logger.info(
                "✅ Media saved",
                path=str(file_path),
                size_bytes=len(response.content),
                correlation_id=correlation_id
            )
            
            return filename
            
    except httpx.HTTPStatusError as e:
        logger.warning(
            "⚠️ Media download HTTP error",
            status=e.response.status_code,
            url=media_url[:60] + "..." if len(media_url) > 60 else media_url,
            correlation_id=correlation_id
        )
        return None
        
    except httpx.TimeoutException:
        logger.warning(
            "⚠️ Media download timeout (>30s)",
            url=media_url[:60] + "..." if len(media_url) > 60 else media_url,
            correlation_id=correlation_id
        )
        return None
        
    except Exception as e:
        logger.error(
            "❌ Media download failed",
            error=str(e),
            error_type=type(e).__name__,
            url=media_url[:60] + "..." if len(media_url) > 60 else media_url,
            correlation_id=correlation_id
        )
        return None
