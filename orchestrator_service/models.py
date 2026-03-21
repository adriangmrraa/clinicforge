from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Text,
    BigInteger, DECIMAL, Date, Float, CheckConstraint, UniqueConstraint,
    ForeignKeyConstraint, Index, Numeric
)
from sqlalchemy.dialects.postgresql import JSONB, UUID, ARRAY, TIMESTAMP
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


# =============================================================================
# CORE TABLES - MESSAGES & CHAT
# =============================================================================

class InboundMessage(Base):
    __tablename__ = 'inbound_messages'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    provider = Column(Text, nullable=False)
    provider_message_id = Column(Text, nullable=False)
    event_id = Column(Text)
    from_number = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False)
    status = Column(Text, nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True))
    error = Column(Text)
    correlation_id = Column(Text)

    __table_args__ = (
        UniqueConstraint('provider', 'provider_message_id', name='inbound_messages_provider_provider_message_id_key'),
        CheckConstraint("status IN ('received', 'processing', 'done', 'failed')", name='inbound_messages_status_check'),
        Index('idx_inbound_messages_from_number_received_at', 'from_number', received_at.desc()),
        Index('idx_inbound_messages_status', 'status'),
    )


class ChatMessage(Base):
    __tablename__ = 'chat_messages'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), default=1)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('chat_conversations.id', ondelete='SET NULL'))
    from_number = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    content_attributes = Column(JSONB, default=[])
    platform_metadata = Column(JSONB, default={})
    platform_message_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    correlation_id = Column(Text)

    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')", name='chat_messages_role_check'),
        Index('idx_chat_messages_from_number_created_at', 'from_number', created_at.desc()),
        Index('idx_chat_messages_tenant_id', 'tenant_id'),
        Index('idx_chat_messages_conversation_id', 'conversation_id', postgresql_where=(conversation_id != None)),
        Index('idx_chat_messages_tenant_from_created', 'tenant_id', 'from_number', created_at.desc()),
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

    __table_args__ = (
        Index('idx_chat_conv_tenant', 'tenant_id'),
        Index('idx_chat_conv_tenant_channel', 'tenant_id', 'channel'),
        Index('idx_chat_conv_tenant_channel_user', 'tenant_id', 'channel', 'external_user_id', unique=True),
        Index('idx_chat_conv_last_derivhumano', 'last_derivhumano_at'),
    )


# =============================================================================
# TENANT & CONFIGURATION
# =============================================================================

class Tenant(Base):
    __tablename__ = 'tenants'

    id = Column(Integer, primary_key=True)
    clinic_name = Column(Text, nullable=False, default='Clinica Dental')
    bot_phone_number = Column(Text, unique=True, nullable=False)
    owner_email = Column(Text)
    clinic_location = Column(Text)
    clinic_website = Column(Text)
    system_prompt_template = Column(Text)
    config = Column(JSONB, default={})
    timezone = Column(String(100), default='America/Argentina/Buenos_Aires')
    address = Column(Text)
    google_maps_url = Column(Text)
    working_hours = Column(JSONB, default={})
    total_tokens_used = Column(BigInteger, default=0)
    total_tool_calls = Column(BigInteger, default=0)
    consultation_price = Column(DECIMAL(12, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Credential(Base):
    __tablename__ = 'credentials'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    value = Column(Text)
    category = Column(Text)
    scope = Column(Text, default='global')
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'name', name='idx_credentials_tenant_name_unique'),
        Index('idx_credentials_tenant', 'tenant_id'),
    )


class SystemEvent(Base):
    __tablename__ = 'system_events'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type = Column(Text, nullable=False)
    severity = Column(Text, default='info')
    message = Column(Text)
    payload = Column(JSONB)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# USERS & RBAC
# =============================================================================

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

    __table_args__ = (
        CheckConstraint("role IN ('ceo', 'professional', 'secretary')", name='users_role_check'),
        CheckConstraint("status IN ('pending', 'active', 'suspended')", name='users_status_check'),
        Index('idx_users_email', 'email'),
        Index('idx_users_status', 'status'),
    )


# =============================================================================
# PROFESSIONALS
# =============================================================================

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

    __table_args__ = (
        Index('idx_professionals_tenant', 'tenant_id'),
        Index('idx_professionals_active', 'is_active'),
        Index('idx_professionals_user_id', 'user_id'),
    )


# =============================================================================
# PATIENTS (with full first-touch / last-touch attribution)
# =============================================================================

class Patient(Base):
    __tablename__ = 'patients'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)

    # Identity
    phone_number = Column(String(20), nullable=False)
    dni = Column(String(15))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    birth_date = Column(Date)
    gender = Column(String(10))

    # Insurance
    insurance_provider = Column(String(100))
    insurance_id = Column(String(50))
    insurance_valid_until = Column(Date)

    # Medical
    medical_history = Column(JSONB, default={})

    # Contact
    email = Column(String(255))
    alternative_phone = Column(String(20))
    preferred_schedule = Column(Text)
    notes = Column(Text)

    # Status
    status = Column(String(20), default='active')

    # Urgency (AI triage)
    urgency_level = Column(String(20), default='normal')
    urgency_reason = Column(Text)

    # Human Handoff
    human_handoff_requested = Column(Boolean, default=False)
    human_override_until = Column(DateTime(timezone=True))
    last_derivhumano_at = Column(DateTime(timezone=True))

    # First-Touch Attribution (renamed from meta_ad_* in patch_020)
    first_touch_source = Column(String(50), server_default='ORGANIC')
    first_touch_ad_id = Column(String(255))
    first_touch_campaign_id = Column(String(255))
    first_touch_ad_name = Column(Text)
    first_touch_campaign_name = Column(Text)
    first_touch_adset_id = Column(String(255))
    first_touch_adset_name = Column(Text)
    first_touch_ad_headline = Column(Text)
    first_touch_ad_body = Column(Text)

    # Last-Touch Attribution (patch_020)
    last_touch_source = Column(String(50))
    last_touch_ad_id = Column(String(255))
    last_touch_campaign_id = Column(String(255))
    last_touch_ad_name = Column(Text)
    last_touch_campaign_name = Column(Text)
    last_touch_timestamp = Column(DateTime)

    # Location
    city = Column(String(100))

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_visit = Column(DateTime(timezone=True))
    anamnesis_token = Column(UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'phone_number', name='patients_tenant_id_phone_number_key'),
        UniqueConstraint('tenant_id', 'dni', name='patients_tenant_id_dni_key'),
        Index('idx_patients_tenant_phone', 'tenant_id', 'phone_number'),
        Index('idx_patients_tenant_dni', 'tenant_id', 'dni'),
        Index('idx_patients_status', 'status'),
        Index('idx_patients_insurance', 'insurance_provider'),
        Index('idx_patients_handoff', 'human_handoff_requested', postgresql_where=(human_handoff_requested == True)),
        Index('idx_patients_first_touch_source', 'first_touch_source'),
        Index('idx_patients_first_touch_ad_id', 'first_touch_ad_id'),
        Index('idx_patients_first_touch_campaign_id', 'first_touch_campaign_id'),
        Index('idx_patients_first_touch_adset_id', 'first_touch_adset_id'),
        Index('idx_patients_city', 'city'),
        Index('idx_patients_anamnesis_token', 'anamnesis_token', unique=True, postgresql_where=(anamnesis_token != None)),
    )


# =============================================================================
# CLINICAL RECORDS
# =============================================================================

class ClinicalRecord(Base):
    __tablename__ = 'clinical_records'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    patient_id = Column(Integer, ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    professional_id = Column(Integer, ForeignKey('professionals.id', ondelete='SET NULL'))
    record_date = Column(Date, nullable=False, default=func.current_date())
    odontogram = Column(JSONB, default={})
    odontogram_data = Column(JSONB, default={})
    diagnosis = Column(Text)
    treatments = Column(JSONB, default=[])
    radiographs = Column(JSONB, default=[])
    treatment_plan = Column(JSONB, default={})
    clinical_notes = Column(Text)
    recommendations = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_clinical_records_patient', 'patient_id'),
        Index('idx_clinical_records_tenant', 'tenant_id'),
        Index('idx_clinical_records_date', record_date.desc()),
        Index('idx_clinical_records_professional', 'professional_id'),
    )


# =============================================================================
# APPOINTMENTS
# =============================================================================

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
    cancellation_reason = Column(Text)
    cancellation_by = Column(String(50))
    source = Column(String(20), default='ai')
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime(timezone=True))
    feedback_sent = Column(Boolean, default=False)
    followup_sent = Column(Boolean, default=False)
    followup_sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index('idx_appointments_patient', 'patient_id'),
        Index('idx_appointments_tenant', 'tenant_id'),
        Index('idx_appointments_datetime', 'appointment_datetime'),
        Index('idx_appointments_chair', 'chair_id'),
        Index('idx_appointments_professional', 'professional_id'),
        Index('idx_appointments_status', 'status'),
        Index('idx_appointments_urgency', 'urgency_level'),
        Index('idx_appointments_google_sync', 'google_calendar_sync_status'),
        Index('idx_appointments_source', 'source'),
    )


# =============================================================================
# ACCOUNTING
# =============================================================================

class AccountingTransaction(Base):
    __tablename__ = 'accounting_transactions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    patient_id = Column(Integer, ForeignKey('patients.id', ondelete='SET NULL'))
    appointment_id = Column(UUID(as_uuid=True), ForeignKey('appointments.id', ondelete='SET NULL'))
    transaction_type = Column(String(50), nullable=False)
    transaction_date = Column(Date, nullable=False, default=func.current_date())
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default='ARS')
    payment_method = Column(String(50))
    description = Column(Text)
    insurance_claim_id = Column(String(100))
    insurance_covered_amount = Column(Numeric(12, 2), default=0)
    patient_paid_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(20), default='completed')
    recorded_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_accounting_tenant', 'tenant_id'),
        Index('idx_accounting_patient', 'patient_id'),
        Index('idx_accounting_date', transaction_date.desc()),
        Index('idx_accounting_type', 'transaction_type'),
        Index('idx_accounting_status', 'status'),
    )


class DailyCashFlow(Base):
    __tablename__ = 'daily_cash_flow'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    cash_date = Column(Date, nullable=False)
    total_cash_received = Column(Numeric(12, 2), default=0)
    total_card_received = Column(Numeric(12, 2), default=0)
    total_insurance_claimed = Column(Numeric(12, 2), default=0)
    total_expenses = Column(Numeric(12, 2), default=0)
    net_balance = Column(Numeric(12, 2), default=0)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    recorded_by = Column(String(100))
    notes = Column(Text)

    __table_args__ = (
        UniqueConstraint('tenant_id', 'cash_date', name='daily_cash_flow_tenant_id_cash_date_key'),
        Index('idx_daily_cash_flow_tenant', 'tenant_id'),
        Index('idx_daily_cash_flow_date', 'cash_date'),
    )


# =============================================================================
# GOOGLE CALENDAR INTEGRATION
# =============================================================================

class GoogleCalendarBlock(Base):
    __tablename__ = 'google_calendar_blocks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    google_event_id = Column(String(255), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)
    all_day = Column(Boolean, default=False)
    professional_id = Column(Integer, ForeignKey('professionals.id', ondelete='CASCADE'))
    sync_status = Column(String(20), default='synced')
    last_sync_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_gcalendar_blocks_tenant', 'tenant_id'),
        Index('idx_gcalendar_blocks_datetime', 'start_datetime', 'end_datetime'),
        Index('idx_gcalendar_blocks_professional', 'professional_id'),
        Index('idx_gcalendar_blocks_sync_status', 'sync_status'),
    )


class CalendarSyncLog(Base):
    __tablename__ = 'calendar_sync_log'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    sync_type = Column(String(50), nullable=False)
    direction = Column(String(20), nullable=False)
    events_processed = Column(Integer, default=0)
    events_created = Column(Integer, default=0)
    events_updated = Column(Integer, default=0)
    events_deleted = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True))
    error_message = Column(Text)

    __table_args__ = (
        Index('idx_calendar_sync_log_tenant', 'tenant_id'),
        Index('idx_calendar_sync_log_date', started_at.desc()),
    )


# =============================================================================
# TREATMENT TYPES & IMAGES
# =============================================================================

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
    requires_multiple_sessions = Column(Boolean, default=False)
    session_gap_days = Column(Integer, default=0)
    base_price = Column(DECIMAL(12, 2), default=0)
    is_active = Column(Boolean, default=True)
    is_available_for_booking = Column(Boolean, default=True)
    internal_notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'code', name='treatment_types_tenant_id_code_key'),
        Index('idx_treatment_types_tenant', 'tenant_id'),
        Index('idx_treatment_types_code', 'code'),
        Index('idx_treatment_types_category', 'category'),
        Index('idx_treatment_types_active', 'is_active', 'is_available_for_booking'),
    )


class TreatmentTypeProfessional(Base):
    __tablename__ = 'treatment_type_professionals'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    treatment_type_id = Column(Integer, ForeignKey('treatment_types.id', ondelete='CASCADE'), nullable=False)
    professional_id = Column(Integer, ForeignKey('professionals.id', ondelete='CASCADE'), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'treatment_type_id', 'professional_id', name='ttp_tenant_treatment_professional_key'),
        Index('idx_ttp_tenant', 'tenant_id'),
        Index('idx_ttp_treatment', 'treatment_type_id'),
        Index('idx_ttp_professional', 'professional_id'),
    )


class TreatmentImage(Base):
    __tablename__ = 'treatment_images'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(Integer, nullable=False)
    treatment_code = Column(String(50), nullable=False)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(1000), nullable=False)
    mime_type = Column(String(100))
    file_size = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        ForeignKeyConstraint(
            ['tenant_id', 'treatment_code'],
            ['treatment_types.tenant_id', 'treatment_types.code'],
            ondelete='CASCADE'
        ),
        Index('idx_treatment_images_tenant_code', 'tenant_id', 'treatment_code'),
    )


# =============================================================================
# PATIENT DOCUMENTS
# =============================================================================

class PatientDocument(Base):
    __tablename__ = 'patient_documents'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    patient_id = Column(Integer, ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    document_type = Column(String(50), server_default='clinical')
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    source = Column(String(50), server_default='manual')
    source_details = Column(JSONB, default={})
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'patient_id', 'file_name', name='patient_documents_tenant_patient_filename_key'),
        Index('idx_patient_documents_tenant', 'tenant_id'),
        Index('idx_patient_documents_patient', 'patient_id'),
    )


# =============================================================================
# CHANNEL CONFIG & AUTOMATION
# =============================================================================

class ChannelConfig(Base):
    __tablename__ = 'channel_configs'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    provider = Column(String(50), nullable=False)
    channel = Column(String(50))
    config = Column(JSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'provider', 'channel', name='channel_configs_tenant_provider_channel_key'),
        Index('idx_channel_configs_tenant', 'tenant_id'),
        Index('idx_channel_configs_provider', 'provider'),
    )


class AutomationRule(Base):
    __tablename__ = 'automation_rules'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    name = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    trigger_type = Column(Text, nullable=False)
    condition_json = Column(JSONB, default={})
    message_type = Column(Text, nullable=False, server_default='free_text')
    free_text_message = Column(Text)
    ycloud_template_name = Column(Text)
    ycloud_template_lang = Column(Text, server_default='es')
    ycloud_template_vars = Column(JSONB, default={})
    channels = Column(ARRAY(Text), server_default='{whatsapp}')
    send_hour_min = Column(Integer, default=8)
    send_hour_max = Column(Integer, default=20)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_automation_rules_tenant_active', 'tenant_id', 'is_active', 'trigger_type'),
    )


class AutomationLog(Base):
    __tablename__ = 'automation_logs'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    patient_id = Column(Integer, ForeignKey('patients.id', ondelete='SET NULL'))
    automation_rule_id = Column(Integer, ForeignKey('automation_rules.id', ondelete='SET NULL'))
    trigger_type = Column(String(50), nullable=False)
    target_id = Column(String(100))
    status = Column(String(20), server_default='pending')
    meta = Column(JSONB, default={})
    error_details = Column(Text)
    rule_name = Column(Text)
    patient_name = Column(Text)
    phone_number = Column(Text)
    channel = Column(Text, server_default='whatsapp')
    message_type = Column(Text)
    message_preview = Column(Text)
    template_name = Column(Text)
    skip_reason = Column(Text)
    ycloud_message_id = Column(Text)
    sent_at = Column(DateTime(timezone=True))
    delivered_at = Column(DateTime(timezone=True))
    triggered_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_auto_logs_trigger', 'trigger_type'),
        Index('idx_auto_logs_tenant', 'tenant_id'),
        Index('idx_auto_logs_target', 'target_id'),
        Index('idx_automation_logs_tenant_date', 'tenant_id', triggered_at.desc()),
        Index('idx_automation_logs_rule', 'automation_rule_id'),
    )


# =============================================================================
# META ADS LEADS & ATTRIBUTION
# =============================================================================

class MetaFormLead(Base):
    __tablename__ = 'meta_form_leads'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    form_id = Column(String(255))
    page_id = Column(String(255))
    ad_id = Column(String(255))
    adset_id = Column(String(255))
    campaign_id = Column(String(255))
    ad_name = Column(Text)
    adset_name = Column(Text)
    campaign_name = Column(Text)
    page_name = Column(Text)
    full_name = Column(Text)
    email = Column(String(255))
    phone_number = Column(String(50))
    custom_questions = Column(JSONB, default={})
    status = Column(String(50), server_default='new')
    assigned_to = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    notes = Column(Text)
    medical_interest = Column(Text)
    preferred_specialty = Column(Text)
    insurance_provider = Column(Text)
    preferred_date = Column(Date)
    preferred_time = Column(DateTime(timezone=True))
    lead_source = Column(String(100), server_default='meta_form')
    attribution_data = Column(JSONB, default={})
    webhook_payload = Column(JSONB, default={})
    converted_to_patient_id = Column(Integer, ForeignKey('patients.id'))
    converted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'contacted', 'consultation_scheduled', 'treatment_planned', 'converted', 'not_interested', 'spam')",
            name='meta_form_leads_status_check'
        ),
        Index('idx_meta_form_leads_tenant_status', 'tenant_id', 'status'),
        Index('idx_meta_form_leads_phone', 'phone_number'),
        Index('idx_meta_form_leads_created', created_at.desc()),
        Index('idx_meta_form_leads_campaign', 'campaign_id'),
        Index('idx_meta_form_leads_assigned', 'assigned_to'),
        Index('idx_meta_form_leads_ad', 'ad_id'),
        Index('idx_meta_form_leads_converted', 'converted_to_patient_id',
              postgresql_where=(converted_to_patient_id != None)),
    )


class LeadStatusHistory(Base):
    __tablename__ = 'lead_status_history'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    lead_id = Column(UUID(as_uuid=True), ForeignKey('meta_form_leads.id', ondelete='CASCADE'), nullable=False)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    old_status = Column(String(50))
    new_status = Column(String(50), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    change_reason = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_lead_status_history_tenant', 'tenant_id'),
        Index('idx_lead_status_history_lead', 'lead_id'),
        Index('idx_lead_status_history_created', created_at.desc()),
    )


class LeadNote(Base):
    __tablename__ = 'lead_notes'

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    lead_id = Column(UUID(as_uuid=True), ForeignKey('meta_form_leads.id', ondelete='CASCADE'), nullable=False)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    content = Column(Text, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_lead_notes_tenant', 'tenant_id'),
        Index('idx_lead_notes_lead', 'lead_id'),
        Index('idx_lead_notes_created', created_at.desc()),
    )


class PatientAttributionHistory(Base):
    __tablename__ = 'patient_attribution_history'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(Integer, ForeignKey('patients.id', ondelete='CASCADE'), nullable=False)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    attribution_type = Column(String(20), nullable=False)
    source = Column(String(50), nullable=False)
    source_detail = Column(String(100))
    ad_id = Column(String(255))
    ad_name = Column(Text)
    campaign_id = Column(String(255))
    campaign_name = Column(Text)
    adset_id = Column(String(255))
    adset_name = Column(Text)
    headline = Column(Text)
    body = Column(Text)
    lead_id = Column(UUID(as_uuid=True), ForeignKey('meta_form_leads.id'))
    event_timestamp = Column(DateTime, nullable=False, server_default=func.now())
    event_description = Column(Text)

    __table_args__ = (
        CheckConstraint(
            "attribution_type IN ('first_touch', 'last_touch', 'conversion')",
            name='patient_attribution_history_type_check'
        ),
        Index('idx_patient_attribution_patient_tenant', 'patient_id', 'tenant_id'),
        Index('idx_patient_attribution_type', 'attribution_type'),
        Index('idx_patient_attribution_source', 'source'),
        Index('idx_patient_attribution_ad', 'ad_id'),
        Index('idx_patient_attribution_campaign', 'campaign_id'),
        Index('idx_patient_attribution_timestamp', event_timestamp.desc()),
    )


# =============================================================================
# GOOGLE ADS INTEGRATION
# =============================================================================

class GoogleOAuthToken(Base):
    __tablename__ = 'google_oauth_tokens'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    platform = Column(String(50), nullable=False, default='ads')
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    scopes = Column(ARRAY(Text))
    email = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'platform', name='google_oauth_tokens_tenant_platform_key'),
        Index('idx_google_oauth_tokens_tenant', 'tenant_id'),
        Index('idx_google_oauth_tokens_expires', 'expires_at'),
    )


class GoogleAdsAccount(Base):
    __tablename__ = 'google_ads_accounts'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    customer_id = Column(String(50), nullable=False)
    descriptive_name = Column(String(255))
    currency_code = Column(String(10))
    time_zone = Column(String(50))
    manager = Column(Boolean, default=False)
    test_account = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'customer_id', name='google_ads_accounts_tenant_customer_key'),
        Index('idx_google_ads_accounts_tenant', 'tenant_id'),
    )


class GoogleAdsMetricsCache(Base):
    __tablename__ = 'google_ads_metrics_cache'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    customer_id = Column(String(50), nullable=False)
    campaign_id = Column(String(50), nullable=False)
    campaign_name = Column(String(255))
    date = Column(Date, nullable=False)
    impressions = Column(BigInteger, default=0)
    clicks = Column(BigInteger, default=0)
    cost_micros = Column(BigInteger, default=0)
    conversions = Column(Float, default=0)
    conversions_value = Column(Float, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'customer_id', 'campaign_id', 'date',
                         name='google_ads_metrics_cache_unique_key'),
        Index('idx_google_ads_metrics_cache_tenant_date', 'tenant_id', 'date'),
        Index('idx_google_ads_metrics_cache_campaign', 'campaign_id', 'date'),
    )


# =============================================================================
# ANALYTICS DASHBOARD
# =============================================================================

class DailyAnalyticsMetric(Base):
    __tablename__ = 'daily_analytics_metrics'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    metric_date = Column(Date, nullable=False)
    metric_type = Column(String(50), nullable=False)
    metric_value = Column(JSONB, default='0')
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('tenant_id', 'metric_date', 'metric_type',
                         name='daily_analytics_metrics_tenant_date_type_key'),
        Index('idx_analytics_tenant_date', 'tenant_id', 'metric_date'),
    )


# =============================================================================
# CLINIC FAQS
# =============================================================================

class ClinicFaq(Base):
    __tablename__ = 'clinic_faqs'

    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    category = Column(String(100), nullable=False, server_default='General')
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_clinic_faqs_tenant', 'tenant_id'),
    )
