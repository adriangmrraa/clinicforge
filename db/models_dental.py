"""
FASE 1: Modelos SQLAlchemy para Plataforma Dental

Este módulo contiene los modelos ORM que extienden la infraestructura Nexus v3
para soportar la lógica de clínica dental: pacientes, turnos, historias clínicas,
contabilidad y profesionales.

Integración con la estructura existente:
- Mantiene multi-tenancy (tenant_id en todas las tablas)
- Extiende la clase Base de la DB existente
- Compatible con las migraciones automáticas del lifespan
- Usa JSONB para datos médicos complejos (anamnesis, odontogramas)
- Preserva la infraestructura de WhatsApp y memoria (RedisChatMessageHistory)
"""

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, ForeignKey, 
    JSON, JSONB, BigInteger, Numeric, Enum, Index, UniqueConstraint, Date
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, date
import uuid

# Base is assumed to be imported from db.py in orchestrator_service
# from db import Base

# Para este archivo, definimos la estructura SQL que debe migrarse
DENTAL_MIGRATION_SQL = """

-- ==================== FASE 1: PACIENTES ====================

CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Identidad del Paciente
    phone_number VARCHAR(20) NOT NULL,  -- WhatsApp primary key
    dni VARCHAR(15) NOT NULL,            -- Documento Nacional de Identidad (única validación)
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    birth_date DATE,
    gender VARCHAR(10),                  -- 'M', 'F', 'Other'
    
    -- Obra Social (Insurance)
    insurance_provider VARCHAR(100),     -- Ej: "OSDE", "SWISS", "Sanatorio Allende"
    insurance_id VARCHAR(50),            -- Número de afiliado
    insurance_valid_until DATE,          -- Vencimiento de cobertura
    
    -- Anamnesis (JSONB: Historial Médico)
    medical_history JSONB DEFAULT '{}',  -- {
                                         --   "allergies": ["Penicilina", "Ibuprofeno"],
                                         --   "medical_conditions": ["Diabetes", "Hipertensión"],
                                         --   "medications": ["Metformina 1000mg"],
                                         --   "past_treatments": ["Blanqueamiento 2023"],
                                         --   "systemic_diseases": true,
                                         --   "last_checkup": "2024-01-15"
                                         -- }
    
    -- Datos de Contacto
    email VARCHAR(255),
    alternative_phone VARCHAR(20),
    
    -- Estado del Paciente
    status VARCHAR(20) DEFAULT 'active',  -- 'active', 'inactive', 'archived'
    preferred_schedule VARCHAR(50),       -- Ej: "Mañana", "Tarde", "Fin de semana"
    notes TEXT,
    
    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_visit TIMESTAMPTZ,
    
    -- Constraints
    UNIQUE (tenant_id, phone_number),
    UNIQUE (tenant_id, dni)
);

CREATE INDEX idx_patients_tenant_phone ON patients(tenant_id, phone_number);
CREATE INDEX idx_patients_tenant_dni ON patients(tenant_id, dni);
CREATE INDEX idx_patients_status ON patients(status);
CREATE INDEX idx_patients_insurance ON patients(insurance_provider);

-- ==================== FASE 1: HISTORIAS CLÍNICAS ====================

CREATE TABLE IF NOT EXISTS clinical_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    
    -- Metadata del Registro
    record_date DATE NOT NULL DEFAULT CURRENT_DATE,
    professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,  -- Odontólogo responsable
    
    -- Odontograma (JSONB: Representación gráfica de dientes)
    odontogram JSONB DEFAULT '{}',  -- {
                                    --   "tooth_32": {
                                    --     "number": 32,
                                    --     "quadrant": 3,
                                    --     "tooth_type": "molar",
                                    --     "status": "healthy",           -- 'healthy', 'caries', 'missing', 'implant', 'crowned'
                                    --     "surfaces": {
                                    --       "occlusal": "caries",
                                    --       "mesial": "healthy",
                                    --       "distal": "healthy",
                                    --       "buccal": "healthy",
                                    --       "lingual": "healthy"
                                    --     },
                                    --     "notes": "Caries inicial en superficie oclusal"
                                    --   },
                                    --   ...
                                    -- }
    
    -- Diagnósticos Principales
    diagnosis TEXT,                  -- Texto libre: Ej "Caries múltiples, gingivitis moderada"
    
    -- Tratamientos Realizados
    treatments JSONB DEFAULT '[]',   -- [
                                     --   {
                                     --     "date": "2025-01-15",
                                     --     "type": "cleaning",
                                     --     "description": "Profilaxis con fluoruro",
                                     --     "teeth": [11, 12, 13],
                                     --     "cost": 500,
                                     --     "insurance_covered": true
                                     --   },
                                     --   ...
                                     -- ]
    
    -- Radiografías & Documentación
    radiographs JSONB DEFAULT '[]',  -- [
                                     --   {
                                     --     "date": "2025-01-15",
                                     --     "type": "panoramic",
                                     --     "storage_url": "s3://bucket/x-ray-123.jpg",
                                     --     "notes": "Radiografía de seguimiento"
                                     --   },
                                     --   ...
                                     -- ]
    
    -- Plan de Tratamiento Futuro
    treatment_plan JSONB DEFAULT '{}',  -- {
                                        --   "estimated_sessions": 5,
                                        --   "planned_treatments": ["Endodoncia 11", "Corona 12"],
                                        --   "estimated_cost": 15000,
                                        --   "priority": "medium"
                                        -- }
    
    -- Observaciones Clínicas
    clinical_notes TEXT,
    recommendations TEXT,
    
    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_clinical_records_patient ON clinical_records(patient_id);
CREATE INDEX idx_clinical_records_tenant ON clinical_records(tenant_id);
CREATE INDEX idx_clinical_records_date ON clinical_records(record_date DESC);
CREATE INDEX idx_clinical_records_professional ON clinical_records(professional_id);

-- ==================== FASE 1: TURNOS (APPOINTMENTS) ====================

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    
    -- Datos del Turno
    appointment_datetime TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    
    -- Asignación de Recursos
    chair_id INTEGER,                 -- Sillón/Box número
    professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,  -- Odontólogo asignado
    
    -- Tipo de Cita
    appointment_type VARCHAR(50) NOT NULL,  -- 'checkup', 'cleaning', 'treatment', 'emergency', 'followup'
    notes TEXT,
    
    -- Sincronización con Google Calendar
    google_calendar_event_id VARCHAR(255),
    google_calendar_sync_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'synced', 'failed'
    
    -- Urgencia (detectada por AI triage)
    urgency_level VARCHAR(20) DEFAULT 'normal',  -- 'low', 'normal', 'high', 'emergency'
    urgency_reason TEXT,                        -- Ej: "Dolor agudo en molar"
    
    -- Estado del Turno
    status VARCHAR(20) DEFAULT 'scheduled',  -- 'scheduled', 'confirmed', 'in-progress', 'completed', 'cancelled', 'no-show'
    cancellation_reason TEXT,
    cancellation_by VARCHAR(50),              -- 'patient', 'clinic', 'system'
    
    -- Recordatorio
    reminder_sent BOOLEAN DEFAULT FALSE,
    reminder_sent_at TIMESTAMPTZ,
    
    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_appointments_patient ON appointments(patient_id);
CREATE INDEX idx_appointments_tenant ON appointments(tenant_id);
CREATE INDEX idx_appointments_datetime ON appointments(appointment_datetime);
CREATE INDEX idx_appointments_chair ON appointments(chair_id);
CREATE INDEX idx_appointments_professional ON appointments(professional_id);
CREATE INDEX idx_appointments_status ON appointments(status);
CREATE INDEX idx_appointments_urgency ON appointments(urgency_level);
CREATE INDEX idx_appointments_google_sync ON appointments(google_calendar_sync_status);

-- ==================== FASE 1: PROFESIONALES ====================

CREATE TABLE IF NOT EXISTS professionals (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Identidad
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    license_number VARCHAR(100) UNIQUE,  -- Matrícula profesional
    specialization VARCHAR(100),          -- Ej: "Endodoncia", "Ortodoncia"
    
    -- Disponibilidad
    is_active BOOLEAN DEFAULT TRUE,
    schedule_json JSONB DEFAULT '{}',     -- {
                                          --   "monday": ["09:00-13:00", "14:00-18:00"],
                                          --   "tuesday": ["09:00-13:00", "14:00-18:00"],
                                          --   ...
                                          -- }
    
    -- Contacto
    email VARCHAR(255),
    phone VARCHAR(20),
    
    -- Configuración Avanzada
    working_hours JSONB DEFAULT '{}',     -- { "monday": { "enabled": true, "slots": [...] }, ... }
    
    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_professionals_tenant ON professionals(tenant_id);
CREATE INDEX idx_professionals_active ON professionals(is_active);

-- ==================== FASE 1: CONTABILIDAD ====================

CREATE TABLE IF NOT EXISTS accounting_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    
    -- Tipo de Transacción
    transaction_type VARCHAR(50) NOT NULL,  -- 'payment', 'insurance_claim', 'expense', 'refund'
    transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Monto
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ARS',
    
    -- Detalles del Pago
    payment_method VARCHAR(50),             -- 'cash', 'card', 'transfer', 'insurance'
    description TEXT,
    
    -- Obra Social / Insurance
    insurance_claim_id VARCHAR(100),        -- Para rastreo OSDE, etc.
    insurance_covered_amount NUMERIC(12, 2) DEFAULT 0,
    patient_paid_amount NUMERIC(12, 2) DEFAULT 0,
    
    -- Estado
    status VARCHAR(20) DEFAULT 'completed',  -- 'pending', 'completed', 'failed'
    
    -- Auditoría
    recorded_by VARCHAR(100),                -- Usuario que registró
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_accounting_tenant ON accounting_transactions(tenant_id);
CREATE INDEX idx_accounting_patient ON accounting_transactions(patient_id);
CREATE INDEX idx_accounting_date ON accounting_transactions(transaction_date DESC);
CREATE INDEX idx_accounting_type ON accounting_transactions(transaction_type);
CREATE INDEX idx_accounting_status ON accounting_transactions(status);

-- ==================== FASE 1: REPORTE DE CAJA DIARIA ====================

CREATE TABLE IF NOT EXISTS daily_cash_flow (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Fecha
    cash_date DATE NOT NULL,
    
    -- Totales
    total_cash_received NUMERIC(12, 2) DEFAULT 0,
    total_card_received NUMERIC(12, 2) DEFAULT 0,
    total_insurance_claimed NUMERIC(12, 2) DEFAULT 0,
    total_expenses NUMERIC(12, 2) DEFAULT 0,
    
    -- Saldo
    net_balance NUMERIC(12, 2) DEFAULT 0,
    
    -- Registro
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    recorded_by VARCHAR(100),
    notes TEXT,
    
    -- Constraint: Una sola entrada por fecha/tenant
    UNIQUE (tenant_id, cash_date)
);

CREATE INDEX idx_daily_cash_flow_tenant ON daily_cash_flow(tenant_id);
CREATE INDEX idx_daily_cash_flow_date ON daily_cash_flow(cash_date);

"""

# ==================== DEFINICIÓN DE MODELOS SQLALCHEMY ====================
# (Estos sirven como referencia; la migración se ejecuta vía SQL)

from sqlalchemy.orm import declarative_base
Base = declarative_base()

class Patient(Base):
    """Modelo ORM para Pacientes"""
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    phone_number = Column(String(20), nullable=False, index=True)
    dni = Column(String(15), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    birth_date = Column(Date)
    gender = Column(String(10))
    insurance_provider = Column(String(100))
    insurance_id = Column(String(50))
    insurance_valid_until = Column(Date)
    medical_history = Column(JSON, default={})
    email = Column(String(255))
    alternative_phone = Column(String(20))
    status = Column(String(20), default="active", index=True)
    preferred_schedule = Column(String(50))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_visit = Column(DateTime)
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'phone_number', name='uq_patient_tenant_phone'),
        UniqueConstraint('tenant_id', 'dni', name='uq_patient_tenant_dni'),
    )


class ClinicalRecord(Base):
    """Modelo ORM para Historias Clínicas"""
    __tablename__ = "clinical_records"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    record_date = Column(Date, nullable=False, default=date.today, index=True)
    professional_id = Column(Integer, ForeignKey("professionals.id", ondelete="SET NULL"))
    odontogram = Column(JSON, default={})
    diagnosis = Column(Text)
    treatments = Column(JSON, default=[])
    radiographs = Column(JSON, default=[])
    treatment_plan = Column(JSON, default={})
    clinical_notes = Column(Text)
    recommendations = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Appointment(Base):
    """Modelo ORM para Turnos/Citas"""
    __tablename__ = "appointments"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_datetime = Column(DateTime, nullable=False, index=True)
    duration_minutes = Column(Integer, default=60)
    chair_id = Column(Integer)
    professional_id = Column(Integer, ForeignKey("professionals.id", ondelete="SET NULL"))
    appointment_type = Column(String(50), nullable=False)
    notes = Column(Text)
    google_calendar_event_id = Column(String(255))
    google_calendar_sync_status = Column(String(20), default="pending", index=True)
    urgency_level = Column(String(20), default="normal", index=True)
    urgency_reason = Column(Text)
    status = Column(String(20), default="scheduled", index=True)
    cancellation_reason = Column(Text)
    cancellation_by = Column(String(50))
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime)


class Professional(Base):
    """Modelo ORM para Profesionales (Odontólogos)"""
    __tablename__ = "professionals"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    license_number = Column(String(100), unique=True)
    specialization = Column(String(100))
    is_active = Column(Boolean, default=True, index=True)
    schedule_json = Column(JSON, default={})
    working_hours = Column(JSON, default={})
    email = Column(String(255))
    phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AccountingTransaction(Base):
    """Modelo ORM para Transacciones Contables"""
    __tablename__ = "accounting_transactions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"))
    appointment_id = Column(String(36), ForeignKey("appointments.id", ondelete="SET NULL"))
    transaction_type = Column(String(50), nullable=False, index=True)
    transaction_date = Column(Date, nullable=False, default=date.today, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="ARS")
    payment_method = Column(String(50))
    description = Column(Text)
    insurance_claim_id = Column(String(100))
    insurance_covered_amount = Column(Numeric(12, 2), default=0)
    patient_paid_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(20), default="completed", index=True)
    recorded_by = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)


class DailyCashFlow(Base):
    """Modelo ORM para Reporte de Caja Diaria"""
    __tablename__ = "daily_cash_flow"
    
    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    cash_date = Column(Date, nullable=False)
    total_cash_received = Column(Numeric(12, 2), default=0)
    total_card_received = Column(Numeric(12, 2), default=0)
    total_insurance_claimed = Column(Numeric(12, 2), default=0)
    total_expenses = Column(Numeric(12, 2), default=0)
    net_balance = Column(Numeric(12, 2), default=0)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    recorded_by = Column(String(100))
    notes = Column(Text)
    
    __table_args__ = (
        UniqueConstraint('tenant_id', 'cash_date', name='uq_daily_cash_flow'),
    )
