"""
Schemas package for ClinicForge API
"""

from schemas.treatment_plan import (
    # Enums
    PlanStatus,
    ItemStatus,
    PaymentMethod,
    InstallmentStatus,
    # Request models
    TreatmentPlanItemCreate,
    CreateTreatmentPlanBody,
    UpdateTreatmentPlanBody,
    AddPlanItemBody,
    UpdatePlanItemBody,
    RegisterPaymentBody,
    LinkPlanItemBody,
    GenerateInstallmentsBody,
    UpdateInstallmentBody,
    # Response models
    TreatmentPlanResponse,
    TreatmentPlanDetailResponse,
    TreatmentPlanItemResponse,
    TreatmentPlanPaymentResponse,
    InstallmentResponse,
    # Helper models
    PlanSummary,
    PaymentWithReceiptResponse,
)

__all__ = [
    # Enums
    "PlanStatus",
    "ItemStatus",
    "PaymentMethod",
    "InstallmentStatus",
    # Request models
    "TreatmentPlanItemCreate",
    "CreateTreatmentPlanBody",
    "UpdateTreatmentPlanBody",
    "AddPlanItemBody",
    "UpdatePlanItemBody",
    "RegisterPaymentBody",
    "LinkPlanItemBody",
    "GenerateInstallmentsBody",
    "UpdateInstallmentBody",
    # Response models
    "TreatmentPlanResponse",
    "TreatmentPlanDetailResponse",
    "TreatmentPlanItemResponse",
    "TreatmentPlanPaymentResponse",
    "InstallmentResponse",
    # Helper models
    "PlanSummary",
    "PaymentWithReceiptResponse",
]
