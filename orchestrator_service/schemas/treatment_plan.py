"""
Treatment Plan Billing System - Pydantic Schemas
=================================================
Modelos Pydantic para validación de request/response en los endpoints
de gestión de planes de tratamiento y facturación.

Change: treatment-plan-billing
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# ENUMS
# =============================================================================


class PlanStatus(str, Enum):
    """Estado del plan de tratamiento"""

    DRAFT = "draft"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ItemStatus(str, Enum):
    """Estado del ítem dentro de un plan"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentMethod(str, Enum):
    """Método de pago"""

    CASH = "cash"
    TRANSFER = "transfer"
    CARD = "card"
    INSURANCE = "insurance"


class InstallmentStatus(str, Enum):
    """Estado de una cuota"""

    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"  # computed at read time, never stored


# =============================================================================
# REQUEST MODELS
# =============================================================================


class TreatmentPlanItemCreate(BaseModel):
    """Modelo base para crear un ítem de plan"""

    treatment_type_code: str = Field(..., description="Código del tipo de tratamiento")
    custom_description: Optional[str] = Field(
        None,
        description="Descripción personalizada si es diferente al tratamiento estándar",
    )
    estimated_price: Optional[Decimal] = Field(
        None,
        description="Precio estimado (opcional, se usa base_price de treatment_types si no se provee)",
    )
    sort_order: Optional[int] = Field(None, description="Orden del ítem en el plan")


class CreateTreatmentPlanBody(BaseModel):
    """Cuerpo para crear un nuevo plan de tratamiento"""

    professional_id: Optional[int] = Field(None, description="ID del profesional principal")
    name: str = Field(..., max_length=255, description="Nombre del plan")
    notes: Optional[str] = Field(None, description="Notas u observaciones")
    items: Optional[List[TreatmentPlanItemCreate]] = Field(
        default_factory=list, description="Ítems iniciales del plan"
    )

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("El nombre del plan no puede estar vacío")
        return v.strip()


class UpdateTreatmentPlanBody(BaseModel):
    """Cuerpo para actualizar un plan de tratamiento"""

    name: Optional[str] = Field(None, max_length=255, description="Nombre del plan")
    notes: Optional[str] = Field(None, description="Notas u observaciones")
    status: Optional[PlanStatus] = Field(None, description="Nuevo estado del plan")
    approved_total: Optional[Decimal] = Field(
        None, description="Monto total aprobado (solo para aprobación)"
    )
    approved_by: Optional[int] = Field(None, description="ID del usuario que aprueba")

    # Campos de auditoría (calculados automáticamente)
    approved_at: Optional[datetime] = Field(None, description="Fecha de aprobación")


class AddPlanItemBody(BaseModel):
    """Cuerpo para agregar un ítem a un plan existente"""

    treatment_type_code: Optional[str] = Field(None, description="Código del tipo de tratamiento")
    custom_description: Optional[str] = Field(
        None, description="Descripción personalizada"
    )
    estimated_price: Optional[Decimal] = Field(None, description="Precio estimado")
    approved_price: Optional[float] = Field(None, description="Precio final aprobado")


class UpdatePlanItemBody(BaseModel):
    """Cuerpo para actualizar un ítem de plan"""

    treatment_type_code: Optional[str] = Field(
        None, description="Código del tipo de tratamiento"
    )
    custom_description: Optional[str] = Field(
        None, description="Descripción personalizada"
    )
    estimated_price: Optional[Decimal] = Field(None, description="Precio estimado")
    approved_price: Optional[Decimal] = Field(None, description="Precio aprobado")
    status: Optional[ItemStatus] = Field(None, description="Estado del ítem")
    sort_order: Optional[int] = Field(None, description="Orden del ítem")


class RegisterPaymentBody(BaseModel):
    """Cuerpo para registrar un pago contra un plan"""

    amount: Decimal = Field(..., gt=0, description="Monto del pago")
    payment_method: PaymentMethod = Field(..., description="Método de pago")
    payment_date: Optional[date] = Field(None, description="Fecha del pago (default: hoy)")
    appointment_id: Optional[str] = Field(
        None, description="ID del turno asociado (opcional)"
    )
    receipt_data: Optional[dict] = Field(None, description="Datos del comprobante")
    notes: Optional[str] = Field(None, description="Notas del pago")
    recorded_by: Optional[str] = Field(None, description="Email del usuario que registra (se extrae del JWT si no se envía)")
    installment_id: Optional[str] = Field(None, description="ID de la cuota a pagar (opcional)")

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        return v


class LinkPlanItemBody(BaseModel):
    """Cuerpo para vincular/desvincular un turno a un ítem de plan"""

    plan_item_id: Optional[str] = Field(
        None, description="ID del ítem de plan (null para desvincular)"
    )


class GenerateInstallmentsBody(BaseModel):
    """Cuerpo para generar cuotas en un plan de tratamiento"""

    count: int = Field(..., ge=1, le=24, description="Cantidad de cuotas")
    start_date: date = Field(..., description="Fecha de la primera cuota")
    frequency: str = Field(
        ...,
        pattern="^(monthly|biweekly|weekly|custom)$",
        description="Frecuencia: monthly | biweekly | weekly | custom",
    )
    custom_amounts: Optional[List[Decimal]] = Field(
        None, description="Montos personalizados por cuota (deben sumar el total aprobado)"
    )


class UpdateInstallmentBody(BaseModel):
    """Cuerpo para editar una cuota (solo campos permitidos)"""

    due_date: Optional[date] = Field(None, description="Nueva fecha de vencimiento")
    amount: Optional[Decimal] = Field(None, gt=0, description="Nuevo monto")


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class TreatmentPlanItemResponse(BaseModel):
    """Respuesta para un ítem individual del plan"""

    id: str
    plan_id: str
    tenant_id: int
    treatment_type_code: str
    custom_description: Optional[str]
    estimated_price: Optional[Decimal]
    approved_price: Optional[Decimal]
    status: ItemStatus
    sort_order: int
    # Campos calculados
    appointments_count: int = Field(
        default=0, description="Cantidad de turnos vinculados"
    )
    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InstallmentResponse(BaseModel):
    """Respuesta para una cuota de plan de tratamiento"""

    id: str
    plan_id: str
    tenant_id: int
    installment_number: int
    amount: Decimal
    due_date: date
    status: str  # pending | paid | overdue (overdue computed at read time, never stored)
    paid_at: Optional[datetime] = None
    payment_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TreatmentPlanPaymentResponse(BaseModel):
    """Respuesta para un pago registrado"""

    id: str
    plan_id: str
    tenant_id: int
    amount: Decimal
    payment_method: PaymentMethod
    payment_date: date
    recorded_by: int
    appointment_id: Optional[str]
    receipt_data: Optional[dict]
    notes: Optional[str]
    # Campos de cuota vinculada
    installment_id: Optional[str] = None
    installment_number: Optional[int] = None
    # Timestamps
    created_at: datetime

    class Config:
        from_attributes = True


class TreatmentPlanResponse(BaseModel):
    """Respuesta para lista de planes (resumen)"""

    id: str
    tenant_id: int
    patient_id: int
    professional_id: int
    name: str
    status: PlanStatus
    estimated_total: Optional[Decimal]
    approved_total: Optional[Decimal]
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    notes: Optional[str]
    # Campos calculados agregados
    items_count: int = Field(default=0, description="Cantidad de ítems en el plan")
    paid_total: Decimal = Field(default=Decimal("0"), description="Total pagado")
    pending_total: Decimal = Field(default=Decimal("0"), description="Saldo pendiente")
    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TreatmentPlanDetailResponse(BaseModel):
    """Respuesta detallada de un plan con todos sus ítems y pagos"""

    id: str
    tenant_id: int
    patient_id: int
    professional_id: int
    name: str
    status: PlanStatus
    estimated_total: Optional[Decimal]
    approved_total: Optional[Decimal]
    approved_by: Optional[int]
    approved_at: Optional[datetime]
    notes: Optional[str]
    # Arrays completos
    items: List[TreatmentPlanItemResponse] = Field(default_factory=list)
    payments: List[TreatmentPlanPaymentResponse] = Field(default_factory=list)
    installments: List[InstallmentResponse] = Field(default_factory=list)
    # Campos calculados
    paid_total: Decimal = Field(default=Decimal("0"), description="Total pagado")
    pending_total: Decimal = Field(default=Decimal("0"), description="Saldo pendiente")
    paid_percentage: float = Field(default=0.0, description="Porcentaje pagado")
    completed_items_count: int = Field(default=0, description="Ítems completados")
    installments_count: int = Field(default=0, description="Total de cuotas generadas")
    installments_paid_count: int = Field(default=0, description="Cuotas ya pagadas")
    next_due_date: Optional[date] = Field(None, description="Próxima fecha de vencimiento pendiente/vencida")
    # Timestamps
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# HELPER MODELS (para respuestas específicas)
# =============================================================================


class PlanSummary(BaseModel):
    """Resumen rápido de un plan para listados"""

    id: str
    name: str
    status: PlanStatus
    estimated_total: Optional[Decimal]
    approved_total: Optional[Decimal]
    items_count: int
    paid_total: Decimal
    pending_total: Decimal


class PaymentWithReceiptResponse(BaseModel):
    """Pago con datos del comprobante verificado"""

    id: str
    plan_id: str
    tenant_id: int
    amount: Decimal
    payment_method: PaymentMethod
    payment_date: date
    recorded_by: int
    appointment_id: Optional[str]
    receipt_data: Optional[dict]
    notes: Optional[str]
    verified: bool = Field(
        default=False, description="Si el comprobante fue verificado"
    )
    verification_notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True
