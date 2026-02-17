from typing import List, Dict, Any, Optional
import logging
from .types import CanonicalMessage
from .chatwoot import ChatwootAdapter
from .ycloud import YCloudAdapter

logger = logging.getLogger(__name__)

class ChannelService:
    """
    Fachada para normalización de canales.
    Routea el payload al adaptador correcto y retorna mensajes canónicos.
    """
    
    _adapters = {
        "chatwoot": ChatwootAdapter(),
        "ycloud": YCloudAdapter()
    }

    @classmethod
    async def normalize_webhook(cls, provider: str, payload: Dict[str, Any], tenant_id: int) -> List[CanonicalMessage]:
        """
        Ingesta y normaliza un webhook raw.
        
        Args:
            provider: 'chatwoot' | 'ycloud'
            payload: Dict con el body del request
            tenant_id: ID del tenant (resolución previa)
            
        Returns:
            List[CanonicalMessage]: Lista de mensajes estandarizados listos para procesar.
        """
        adapter = cls._adapters.get(provider)
        if not adapter:
            logger.error(f"❌ ChannelService: Unknown provider '{provider}'")
            return []
            
        try:
            canonical_msgs = await adapter.normalize_payload(payload, tenant_id)
            if canonical_msgs:
                logger.info(f"✅ ChannelService: Normalized {len(canonical_msgs)} msgs from {provider}")
                
                # Download Media Logic
                from services.media_downloader import download_media
                for msg in canonical_msgs:
                    for m_item in msg.media:
                        try:
                            # Descargar y actualizar URL a path local
                            local_path = await download_media(m_item.url, tenant_id, m_item.type.value)
                            m_item.local_path = local_path
                            m_item.url = local_path # Update URL for DB persistence
                        except Exception as e:
                            logger.error(f"Failed to download media {m_item.url}: {e}")
                            
            return canonical_msgs
        except Exception as e:
            logger.exception(f"❌ ChannelService Error normalizing {provider}: {e}")
            return []
