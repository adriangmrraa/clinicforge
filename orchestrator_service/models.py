from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, BigInteger, DECIMAL, Date, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

# --- TABLAS DE INFRAESTRUCTURA ---

class InboundMessage(Base):
    __tablename__ = 'inbound_messages'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(Text, nullable=False)
    provider_message_id = Column(Text, nullable=False)
    event_id = Column(Text)
    from_number = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(Text, nullable=False) # received, processing, done, failed
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    error = Column(Text)
    correlation_id = Column(Text)

    __table_args__ = (
        CheckConstraint("status IN ('received', 'processing', 'done', 'failed')", name='inbound_messages_status_check'),
    )

class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), default=1)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('chat_conversations.id', ondelete='SET NULL'))
    from_number = Column(Text, nullable=False)
    role = Column(Text, nullable=False) # user, assistant, system, tool
    content = Column(Text, nullable=False)
    content_attributes = Column(JSONB, default=[])
    platform_metadata = Column(JSONB, default={})
    platform_message_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    correlation_id = Column(Text)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')", name='chat_messages_role_check'),
    )

class ChatConversation(Base):
    __tablename__ = 'chat_conversations'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    channel = Column(String(50), nullable=False, default='whatsapp')
    channel_source = Column(String(32), default='whatsapp')
    provider = Column(String(32), nullable=False, default='ycloud')
    external_user_id = Column(String(255), nullable=False)
    external_chatwoot_id = Column(Integer)
    external_account_id = Column(Integer)
    display_name = Column(String(255))
    status = Column(String(20), default='open')
    human_override_until = Column(DateTime(timezone=True))
    meta = Column(JSONB, default={})
    last_message_at = Column(DateTime(timezone=True))
    last_message_preview = Column(String(255))
    last_read_at = Column(DateTime(timezone=True), server_default='1970-01-01 00:00:00+00')
    last_user_message_at = Column(DateTime(timezone=True))
    last_derivhumano_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# --- TABLAS DE NEGOCIO ---

class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(Integer, primary_key=True)
    clinic_name = Column(Text, nullable=False, default='Clínica Dental')
    bot_phone_number = Column(Text, unique=True, nullable=False)
    owner_email = Column(Text)
    clinic_location = Column(Text)
    clinic_website = Column(Text)
    system_prompt_template = Column(Text)
    config = Column(JSONB, default={})
    timezone = Column(String(100), default='America/Argentina/Buenos_Aires')
    total_tokens_used = Column(BigInteger, default=0)
    total_tool_calls = Column(BigInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class User(Base):
    __tablename__ = 'users'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default='pending')
    first_name = Column(String(100))
    last_name = Column(String(100))
    professional_id = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Professional(Base):
    __tablename__ = 'professionals'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255))
    phone_number = Column(String(20))
    specialty = Column(String(100))
    registration_id = Column(String(50))
    google_calendar_id = Column(String(255))
    working_hours = Column(JSONB, default={})
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Patient(Base):
    __tablename__ = 'patients'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    phone_number = Column(String(20), nullable=False)
    dni = Column(String(15))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    birth_date = Column(Date)
    gender = Column(String(10))
    insurance_provider = Column(String(100))
    insurance_id = Column(String(50))
    medical_history = Column(JSONB, default={})
    email = Column(String(255))
    status = Column(String(20), default='active')
    notes = Column(Text)
    human_handoff_requested = Column(Boolean, default=False)
    human_override_until = Column(DateTime(timezone=True))
    last_derivhumano_at = Column(DateTime(timezone=True))
    acquisition_source = Column(String(50), default='ORGANIC')
    external_ids = Column(JSONB, default={})
    urgency_level = Column(String(20), default='normal')
    urgency_reason = Column(Text)
    last_visit = Column(DateTime(timezone=True))
    insurance_valid_until = Column(Date)
    preferred_schedule = Column(Text)
    alternative_phone = Column(String(20))
    meta_ad_id = Column(String(255))
    meta_ad_headline = Column(Text)
    meta_ad_body = Column(Text)
    meta_campaign_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Appointment(Base):
    __tablename__ = 'appointments'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    patient_id = Column(Integer, ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    appointment_datetime = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, default=60)
    chair_id = Column(Integer)
    professional_id = Column(Integer, ForeignKey('professionals.id', ondelete='SET NULL'))
    appointment_type = Column(String(50), nullable=False)
    notes = Column(Text)
    google_calendar_event_id = Column(String(255))
    google_calendar_sync_status = Column(String(20), default='pending')
    urgency_level = Column(String(20), default='normal')
    urgency_reason = Column(Text)
    status = Column(String(20), default='scheduled')
    source = Column(String(20), default='ai')
    feedback_sent = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True))
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime(timezone=True))
    cancellation_reason = Column(Text)
    cancellation_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class ClinicalRecord(Base):
    __tablename__ = 'clinical_records'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    patient_id = Column(Integer, ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    professional_id = Column(Integer, ForeignKey('professionals.id', ondelete='SET NULL'))
    record_date = Column(Date, nullable=False, default=func.current_date())
    odontogram = Column(JSONB, default={})
    diagnosis = Column(Text)
    treatments = Column(JSONB, default=[])
    radiographs = Column(JSONB, default=[])
    treatment_plan = Column(JSONB, default={})
    clinical_notes = Column(Text)
    recommendations = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class TreatmentType(Base):
    __tablename__ = 'treatment_types'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    default_duration_minutes = Column(Integer, nullable=False, default=30)
    min_duration_minutes = Column(Integer, nullable=False, default=15)
    max_duration_minutes = Column(Integer, nullable=False, default=120)
    complexity_level = Column(String(20), default='medium')
    category = Column(String(50))
    base_price = Column(DECIMAL(12, 2), default=0)
    is_active = Column(Boolean, default=True)
    is_available_for_booking = Column(Boolean, default=True)
    internal_notes = Column(Text)
    requires_multiple_sessions = Column(Boolean, default=False)
    session_gap_days = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
