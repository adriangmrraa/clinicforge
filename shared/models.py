from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field


# Tool response estándar
class ToolError(BaseModel):
    code: str = Field(..., description="Error code, e.g., TN_RATE_LIMIT, TN_TIMEOUT, etc.")
    message: str
    retryable: bool
    details: Optional[Dict[str, Any]] = None


class ToolResponse(BaseModel):
    ok: bool
    data: Optional[Any] = None
    error: Optional[ToolError] = None
    meta: Optional[Dict[str, Any]] = None


# Webhook models (N8N envelope)
class InboundWebhookEnvelope(BaseModel):
    headers: Dict[str, str]
    body: Dict[str, Any]


class YCloudInboundMessage(BaseModel):
    id: str
    wamid: Optional[str] = None
    from_field: str = Field(..., alias="from")
    customerProfile: Dict[str, Any]
    type: str
    text: Optional[Dict[str, str]] = None
    audio: Optional[Dict[str, Any]] = None


class YCloudEvent(BaseModel):
    id: str
    type: str
    apiVersion: str
    createTime: str
    whatsappInboundMessage: YCloudInboundMessage


# Modelo para el forward al orquestador
class InboundChatEvent(BaseModel):
    provider: str
    event_id: str
    provider_message_id: str
    from_number: str
    text: str
    customer_name: Optional[str] = None
    event_type: str
    correlation_id: str


# Respuesta del orquestador al whatsapp_service
class OrchestratorResult(BaseModel):
    status: Literal["ok", "duplicate", "ignored", "error"]
    send: bool
    text: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None
