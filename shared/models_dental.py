"""
MODELOS PYDANTIC - FASE 1: Dental Platform DTOs

Extensión de shared/models.py con tipos para pacientes, turnos, historias clínicas
y transacciones. Estos DTOs se usan en:
- Solicitudes API (FastAPI request/response)
- Validación de datos
- Serialización JSON

Estos modelos son agnósticos a la base de datos (no usan SQLAlchemy).
"""

from typing import Any, Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field, EmailStr, validator
from datetime import datetime, date
from decimal import Decimal


# ==================== PACIENTES ====================

class PatientMedicalHistory(BaseModel):
    """Anamnesis del paciente"""
    allergies: List[str] = Field(default=[], description="Alergias conocidas")
    medical_conditions: List[str] = Field(default=[], description="Condiciones médicas")
    medications: List[str] = Field(default=[], description="Medicamentos actuales")
    past_treatments: List[str] = Field(default=[], description="Tratamientos previos")
    systemic_diseases: bool = Field(default=False, description="¿Enfermedades sistémicas?")
    last_checkup: Optional[str] = Field(default=None, description="Última revisión (ISO date)")
    notes: Optional[str] = Field(default=None)
    
    class Config:
        schema_extra = {
            "example": {
                "allergies": ["Penicilina", "Ibuprofeno"],
                "medical_conditions": ["Diabetes Tipo 2", "Hipertensión"],
                "medications": ["Metformina 1000mg", "Losartán 50mg"],
                "systemic_diseases": True,
                "last_checkup": "2024-10-15"
            }
        }


class PatientCreate(BaseModel):
    """Crear un nuevo paciente"""
    phone_number: str = Field(..., description="Número de WhatsApp")
    dni: str = Field(..., description="Documento Nacional de Identidad")
    first_name: str
    last_name: str
    birth_date: Optional[date] = None
    gender: Optional[Literal["M", "F", "Other"]] = None
    email: Optional[str] = None
    alternative_phone: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    insurance_valid_until: Optional[date] = None
    medical_history: Optional[PatientMedicalHistory] = None
    preferred_schedule: Optional[str] = None
    notes: Optional[str] = None
    # Meta Ads Attribution (Complete)
    acquisition_source: Optional[str] = "ORGANIC"
    meta_campaign_id: Optional[str] = None
    meta_campaign_name: Optional[str] = None
    meta_adset_id: Optional[str] = None
    meta_adset_name: Optional[str] = None
    meta_ad_id: Optional[str] = None
    meta_ad_name: Optional[str] = None
    meta_ad_headline: Optional[str] = None
    meta_ad_body: Optional[str] = None


class PatientUpdate(BaseModel):
    """Actualizar datos de paciente"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[Literal["M", "F", "Other"]] = None
    email: Optional[str] = None
    alternative_phone: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    insurance_valid_until: Optional[date] = None
    medical_history: Optional[PatientMedicalHistory] = None
    preferred_schedule: Optional[str] = None
    notes: Optional[str] = None
    # Meta Ads Attribution (Complete)
    acquisition_source: Optional[str] = None
    meta_campaign_id: Optional[str] = None
    meta_campaign_name: Optional[str] = None
    meta_adset_id: Optional[str] = None
    meta_adset_name: Optional[str] = None
    meta_ad_id: Optional[str] = None
    meta_ad_name: Optional[str] = None
    meta_ad_headline: Optional[str] = None
    meta_ad_body: Optional[str] = None
    status: Optional[Literal["active", "inactive", "archived"]] = None


class PatientResponse(BaseModel):
    """Respuesta GET paciente"""
    id: int
    tenant_id: int
    phone_number: str
    dni: str
    first_name: str
    last_name: str
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    email: Optional[str] = None
    alternative_phone: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_id: Optional[str] = None
    insurance_valid_until: Optional[date] = None
    # Meta Ads Attribution (Complete)
    acquisition_source: Optional[str] = None
    meta_campaign_id: Optional[str] = None
    meta_campaign_name: Optional[str] = None
    meta_adset_id: Optional[str] = None
    meta_adset_name: Optional[str] = None
    meta_ad_id: Optional[str] = None
    meta_ad_name: Optional[str] = None
    meta_ad_headline: Optional[str] = None
    meta_ad_body: Optional[str] = None
    medical_history: Dict[str, Any] = {}
    preferred_schedule: Optional[str] = None
    notes: Optional[str] = None
    status: str
    last_visit: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== PROFESIONALES ====================

class WorkingHourSlot(BaseModel):
    """Un intervalo de tiempo (ej. 09:00 a 13:00)"""
    start: str
    end: str

class DayWorkingHours(BaseModel):
    """Configuración de horarios para un día específico"""
    enabled: bool = True
    slots: List[WorkingHourSlot] = []

class ProfessionalWorkingHours(BaseModel):
    """Horarios semanales completos del profesional (Formato Nexus v7.6)"""
    monday: DayWorkingHours = Field(default_factory=DayWorkingHours)
    tuesday: DayWorkingHours = Field(default_factory=DayWorkingHours)
    wednesday: DayWorkingHours = Field(default_factory=DayWorkingHours)
    thursday: DayWorkingHours = Field(default_factory=DayWorkingHours)
    friday: DayWorkingHours = Field(default_factory=DayWorkingHours)
    saturday: DayWorkingHours = Field(default_factory=DayWorkingHours)
    sunday: DayWorkingHours = Field(default_factory=DayWorkingHours)

class ProfessionalCreate(BaseModel):
    """Crear un profesional"""
    first_name: str
    last_name: str
    license_number: str = Field(..., description="Matrícula profesional")
    specialization: Optional[str] = Field(None, example="Endodoncia")
    email: Optional[str] = None
    phone: Optional[str] = None
    schedule_json: Optional[ProfessionalSchedule] = None
    working_hours: Optional[ProfessionalWorkingHours] = None


class ProfessionalResponse(BaseModel):
    """Respuesta GET profesional"""
    id: int
    tenant_id: int
    first_name: str
    last_name: str
    license_number: str
    specialization: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    is_active: bool
    schedule_json: Dict[str, Any]
    working_hours: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== ODONTOGRAMA (Tooth Data) ====================

class ToothSurface(BaseModel):
    """Estado de una superficie del diente"""
    occlusal: Optional[Literal["healthy", "caries", "treated"]] = "healthy"
    mesial: Optional[Literal["healthy", "caries", "treated"]] = "healthy"
    distal: Optional[Literal["healthy", "caries", "treated"]] = "healthy"
    buccal: Optional[Literal["healthy", "caries", "treated"]] = "healthy"
    lingual: Optional[Literal["healthy", "caries", "treated"]] = "healthy"


class ToothData(BaseModel):
    """Datos de un diente en el odontograma"""
    number: int = Field(..., description="Número FDI del diente (11-48)")
    tooth_type: Optional[Literal["incisor", "canine", "premolar", "molar"]] = None
    status: Literal["healthy", "caries", "missing", "implant", "crowned", "extracted", "root_canal"] = "healthy"
    surfaces: Optional[ToothSurface] = None
    color_code: Optional[str] = Field(None, description="Código de color para visualización")
    notes: Optional[str] = None
    treatment_date: Optional[date] = None


# ==================== HISTORIAS CLÍNICAS ====================

class ClinicalTreatment(BaseModel):
    """Un tratamiento realizado"""
    date: date
    type: Literal["cleaning", "filling", "extraction", "root_canal", "crown", "whitening", "scaling", "other"]
    description: str
    teeth: List[int] = Field(..., description="Números FDI de dientes tratados")
    duration_minutes: Optional[int] = None
    cost: Optional[Decimal] = None
    currency: Optional[str] = "ARS"
    insurance_covered: Optional[bool] = None
    professional_id: Optional[int] = None
    notes: Optional[str] = None


class Radiograph(BaseModel):
    """Una radiografía"""
    date: date
    type: Literal["panoramic", "intraoral", "bitewing", "periapical", "cephalometric"]
    storage_url: str = Field(..., description="URL de almacenamiento (S3, etc.)")
    preview_url: Optional[str] = None
    notes: Optional[str] = None


class TreatmentPlan(BaseModel):
    """Plan de tratamiento futuro"""
    created_date: Optional[date] = None
    estimated_sessions: Optional[int] = None
    planned_treatments: List[Dict[str, Any]] = Field(default=[])
    total_estimated_cost: Optional[Decimal] = None
    priority: Optional[Literal["low", "medium", "high"]] = None
    notes: Optional[str] = None


class ClinicalRecordCreate(BaseModel):
    """Crear historia clínica"""
    patient_id: int
    record_date: date
    professional_id: Optional[int] = None
    diagnosis: str
    clinical_notes: Optional[str] = None
    recommendations: Optional[str] = None
    odontogram: Optional[Dict[int, ToothData]] = None
    treatments: Optional[List[ClinicalTreatment]] = None
    radiographs: Optional[List[Radiograph]] = None
    treatment_plan: Optional[TreatmentPlan] = None


class ClinicalRecordResponse(BaseModel):
    """Respuesta GET historia clínica"""
    id: str
    tenant_id: int
    patient_id: int
    record_date: date
    professional_id: Optional[int]
    diagnosis: str
    clinical_notes: Optional[str]
    recommendations: Optional[str]
    odontogram: Dict[str, Any]
    treatments: List[Dict[str, Any]]
    radiographs: List[Dict[str, Any]]
    treatment_plan: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ==================== TURNOS / CITAS ====================

class AppointmentCreate(BaseModel):
    """Agendar un turno"""
    patient_id: int
    appointment_datetime: datetime
    duration_minutes: int = 60
    professional_id: Optional[int] = None
    chair_id: Optional[int] = None
    appointment_type: Literal["checkup", "cleaning", "treatment", "emergency", "followup"]
    notes: Optional[str] = None


class AppointmentUpdate(BaseModel):
    """Actualizar turno"""
    appointment_datetime: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    professional_id: Optional[int] = None
    chair_id: Optional[int] = None
    appointment_type: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[Literal["scheduled", "confirmed", "in-progress", "completed", "cancelled", "no-show"]] = None
    cancellation_reason: Optional[str] = None
    cancellation_by: Optional[str] = None


class AppointmentResponse(BaseModel):
    """Respuesta GET turno"""
    id: str
    tenant_id: int
    patient_id: int
    appointment_datetime: datetime
    duration_minutes: int
    professional_id: Optional[int]
    chair_id: Optional[int]
    appointment_type: str
    notes: Optional[str]
    google_calendar_event_id: Optional[str]
    google_calendar_sync_status: str
    urgency_level: str
    urgency_reason: Optional[str]
    status: str
    cancellation_reason: Optional[str]
    cancellation_by: Optional[str]
    reminder_sent: bool
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


# ==================== HERRAMIENTAS (TOOLS RESPONSES) ====================

class AvailabilitySlot(BaseModel):
    """Un slot disponible"""
    datetime: datetime
    professional_id: Optional[int] = None
    chair_id: Optional[int] = None
    duration_minutes: int = 60


class CheckAvailabilityRequest(BaseModel):
    """Solicitud check_availability()"""
    date_str: str = Field(..., description="Fecha ISO: 2025-02-15")
    duration_minutes: int = 60
    professional_id: Optional[int] = None


class CheckAvailabilityResponse(BaseModel):
    """Respuesta check_availability()"""
    status: Literal["ok", "error"]
    available_slots: List[AvailabilitySlot] = []
    next_available: Optional[datetime] = None
    message: Optional[str] = None


class BookAppointmentRequest(BaseModel):
    """Solicitud book_appointment()"""
    patient_phone: str
    professional_id: int
    datetime_str: str = Field(..., description="ISO datetime: 2025-02-15T09:00:00")
    appointment_type: Literal["checkup", "cleaning", "treatment", "emergency", "followup"] = "checkup"
    duration_minutes: int = 60
    notes: Optional[str] = None


class BookAppointmentResponse(BaseModel):
    """Respuesta book_appointment()"""
    success: bool
    appointment_id: Optional[str] = None
    google_event_id: Optional[str] = None
    confirmation_message: str
    error: Optional[str] = None


class TriageUrgencyRequest(BaseModel):
    """Solicitud triage_urgency()"""
    user_message: str
    patient_id: Optional[int] = None


class TriageUrgencyResponse(BaseModel):
    """Respuesta triage_urgency()"""
    urgency_level: Literal["low", "normal", "high", "emergency"]
    reason: str
    recommended_action: str
    should_escalate: bool = False


# ==================== TRANSACCIONES ====================

class AccountingTransactionCreate(BaseModel):
    """Registrar una transacción contable"""
    patient_id: Optional[int] = None
    appointment_id: Optional[str] = None
    transaction_type: Literal["payment", "insurance_claim", "expense", "refund"]
    transaction_date: date
    amount: Decimal
    currency: str = "ARS"
    payment_method: Optional[str] = None
    description: Optional[str] = None
    insurance_claim_id: Optional[str] = None
    insurance_covered_amount: Decimal = Decimal("0")
    patient_paid_amount: Decimal = Decimal("0")
    recorded_by: Optional[str] = None


class AccountingTransactionResponse(BaseModel):
    """Respuesta GET transacción"""
    id: str
    tenant_id: int
    patient_id: Optional[int]
    appointment_id: Optional[str]
    transaction_type: str
    transaction_date: date
    amount: Decimal
    currency: str
    payment_method: Optional[str]
    description: Optional[str]
    status: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class DailyCashFlowResponse(BaseModel):
    """Reporte de caja diaria"""
    id: int
    tenant_id: int
    cash_date: date
    total_cash_received: Decimal
    total_card_received: Decimal
    total_insurance_claimed: Decimal
    total_expenses: Decimal
    net_balance: Decimal
    recorded_by: Optional[str]
    notes: Optional[str]
    recorded_at: datetime
    
    class Config:
        from_attributes = True


# ==================== RESPUESTAS GENÉRICAS ====================

class ErrorResponse(BaseModel):
    """Respuesta de error"""
    error: str
    code: str
    details: Optional[Dict[str, Any]] = None


class SuccessResponse(BaseModel):
    """Respuesta genérica de éxito"""
    success: bool = True
    message: str
    data: Optional[Dict[str, Any]] = None
