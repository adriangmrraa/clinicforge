
import os
import uuid
import httpx
import logging
import mimetypes
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

async def download_media(url: str, tenant_id: int, media_type: str = "document") -> str:
    """Descarga un archivo de media y lo guarda localmente (Spec 19/22).
    
    Args:
        url: URL externa del archivo (YCloud, Chatwoot, etc.)
        tenant_id: ID del tenant para separación de directorios
        media_type: Tipo de media ('audio', 'image', 'document') para extensión default
    
    Returns:
        Path local (/media/{tenant_id}/{filename}) o URL original si falla
    """
    if not url or url.startswith("/media/"):
        return url  # Ya es local, no descargar
    
    logger.info(f"📥 Descargando media: {url[:80]}... (tenant={tenant_id}, type={media_type})")
    
    # Headers con autenticación para YCloud si disponible
    headers = {}
    ycloud_key = os.getenv("YCLOUD_API_KEY")
    if ycloud_key and "ycloud" in url.lower():
        headers["X-API-Key"] = ycloud_key
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0, headers=headers) as client:
        try:
            res = await client.get(url)
            res.raise_for_status()
            
            # Validar contenido no vacío
            if len(res.content) == 0:
                logger.warning(f"⚠️ Media descargada vacía: {url[:80]}")
                return url
            
            # Determinar extensión: prioridad URL > Content-Type > default por tipo
            content_type = res.headers.get("content-type", "")
            
            # 1. Intentar extensión de la URL
            parsed_url = urlparse(url)
            url_path = parsed_url.path
            ext = None
            for e in [".png", ".jpg", ".jpeg", ".mp4", ".ogg", ".opus", ".pdf", ".mp3", ".webp", ".gif", ".wav"]:
                if url_path.lower().endswith(e):
                    ext = e
                    break
            
            # 2. Intentar Content-Type
            if not ext:
                # Mapeo manual para tipos comunes que mimetypes no resuelve bien
                ct_map = {
                    "audio/ogg": ".ogg",
                    "audio/opus": ".ogg",
                    "audio/mpeg": ".mp3",
                    "audio/mp4": ".m4a",
                    "audio/amr": ".amr",
                    "image/jpeg": ".jpg",
                    "image/png": ".png",
                    "image/webp": ".webp",
                    "application/pdf": ".pdf",
                    "video/mp4": ".mp4",
                }
                # Limpiar content-type (quitar parámetros como "; codecs=opus")
                ct_clean = content_type.split(";")[0].strip().lower()
                ext = ct_map.get(ct_clean) or mimetypes.guess_extension(ct_clean) or None
            
            # 3. Default por tipo de media
            if not ext:
                type_defaults = {"audio": ".ogg", "image": ".jpg", "document": ".pdf"}
                ext = type_defaults.get(media_type, ".bin")
            
            filename = f"{uuid.uuid4()}{ext}"
            # Asegurar directorio de media
            media_dir = os.path.join(os.getcwd(), "media", str(tenant_id))
            os.makedirs(media_dir, exist_ok=True)
            
            local_path = os.path.join(media_dir, filename)
            with open(local_path, "wb") as f:
                f.write(res.content)
            
            logger.info(f"✅ Media guardada: {local_path} ({len(res.content)} bytes, ext={ext})")
            return f"/media/{tenant_id}/{filename}"
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Media download HTTP error {e.response.status_code}: {url[:80]}")
            return url  # Fallback a la URL original si falla  
        except httpx.TimeoutException:
            logger.error(f"❌ Media download timeout (>30s): {url[:80]}")
            return url
        except Exception as e:
            logger.error(f"❌ Error downloading media from {url[:80]}: {str(e)}")
            return url  # Fallback a la URL original si falla
