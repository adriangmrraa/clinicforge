from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .types import CanonicalMessage, ChannelException
import logging

logger = logging.getLogger(__name__)

class ChannelAdapter(ABC):
    """
    Clase base para adaptadores de canales (Chatwoot, YCloud, etc).
    Convierte payloads raw a CanonicalMessage.
    """
    
    @abstractmethod
    async def normalize_payload(self, payload: Dict[str, Any], tenant_id: int) -> List[CanonicalMessage]:
        """
        Recibe el payload raw del webhook y retorna una lista de mensajes canónicos.
        Puede retornar lista vacía si el evento no es relevante (ej: status update).
        """
        pass

    def _log_normalization(self, provider: str, raw_count: int, canonical_types: List[str]):
        logger.info(f"🔄 [ChannelService] {provider}: Normalized {raw_count} events -> Types: {canonical_types}")
