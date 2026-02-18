from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class MediaType(str, Enum):
    AUDIO = "audio"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "file"
    TEXT = "text"

class MediaItem(BaseModel):
    type: MediaType
    url: str
    local_path: Optional[str] = None
    file_name: Optional[str] = "attachment"
    mime_type: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    
    # Audios specific
    transcription: Optional[str] = None
    duration: Optional[int] = None

class CanonicalMessage(BaseModel):
    """
    Estructura estandarizada de un mensaje entrante (Input Agnostic).
    Listo para ser persistido por el Orchestrator.
    """
    # Identificadores Raw
    provider: str  # ycloud, chatwoot
    original_channel: str # whatsapp, instagram, facebook
    
    # Identificadores de Negocio (Resolver en Service)
    external_user_id: str
    display_name: Optional[str] = None
    tenant_id: Optional[int] = None # Puede venir del payload o resolverse después
    
    # Contenido
    content: Optional[str] = None
    media: List[MediaItem] = Field(default_factory=list)
    
    # Metadata
    is_agent: bool = False # Si es mensaje del propio sistema
    raw_payload: Dict[str, Any] = Field(default_factory=dict)
    sender: Dict[str, Any] = Field(default_factory=dict)

class ChannelException(Exception):
    pass
