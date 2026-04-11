from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    BigInteger,
    DECIMAL,
    Date,
    Float,
    CheckConstraint,
    UniqueConstraint,
    ForeignKeyConstraint,
    Index,
    Numeric,
    text,
    Time,
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
    __tablename__ = "inbound_messages"

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
        UniqueConstraint(
            "provider",
            "provider_message_id",
            name="inbound_messages_provider_provider_message_id_key",
        ),
        CheckConstraint(
            "status IN ('received', 'processing', 'done', 'failed')",
            name="inbound_messages_status_check",
        ),
        Index(
            "idx_inbound_messages_from_number_received_at",
            "from_number",
            received_at.desc(),
        ),
        Index("idx_inbound_messages_status", "status"),
    )


# =============================================================================
# WHATSAPP MESSAGE SYNC (ycloud-sync)
# =============================================================================


class WhatsAppMessage(Base):
    """WhatsApp messages synced from YCloud API for full message history."""

    __tablename__ = "whatsapp_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    external_id = Column(String(64), nullable=True)  # YCloud message ID
    wamid = Column(String(64), nullable=True)  # WhatsApp message ID
    from_number = Column(String(32), nullable=False)
    to_number = Column(String(32), nullable=False)
    direction = Column(String(16), nullable=False)
    message_type = Column(String(32), nullable=False)
    content = Column(Text, nullable=True)
    media_url = Column(String(512), nullable=True)
    media_id = Column(String(128), nullable=True)
    media_mime_type = Column(String(64), nullable=True)
    media_filename = Column(String(256), nullable=True)
    status = Column(String(16), nullable=False, server_default="synced")
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("chat_conversations.id"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), nullable=False)
    synced_at = Column(DateTime(timezone=True), server_default=func.now())
    error_message = Column(String(512), nullable=True)

    __table_args__ = (
        UniqueConstraint("external_id", name="whatsapp_messages_external_id_key"),
        Index("idx_whatsapp_messages_wamid", "wamid"),
        Index("idx_whatsapp_messages_from_number", "from_number"),
        Index("idx_whatsapp_messages_tenant_created", "tenant_id", "created_at"),
        Index("idx_whatsapp_messages_direction", "direction"),
        Index("idx_whatsapp_messages_tenant_sync", "tenant_id", "synced_at"),
        CheckConstraint(
            "direction IN ('inbound', 'outbound')",
            name="whatsapp_messages_direction_check",
        ),
        CheckConstraint(
            "status IN ('pending', 'syncing', 'synced', 'failed')",
            name="whatsapp_messages_status_check",
        ),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), default=1)
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("chat_conversations.id", ondelete="SET NULL")
    )
    from_number = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    content_attributes = Column(JSONB, default=[])
    platform_metadata = Column(JSONB, default={})
    platform_message_id = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    correlation_id = Column(Text)

    __table_args__ = (
        CheckConstraint(
            "role IN ('user', 'assistant', 'system', 'tool')",
            name="chat_messages_role_check",
        ),
        Index(
            "idx_chat_messages_from_number_created_at", "from_number", created_at.desc()
        ),
        Index("idx_chat_messages_tenant_id", "tenant_id"),
        Index(
            "idx_chat_messages_conversation_id",
            "conversation_id",
            postgresql_where=(conversation_id != None),
        ),
        Index(
            "idx_chat_messages_tenant_from_created",
            "tenant_id",
            "from_number",
            created_at.desc(),
        ),
    )


class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    channel = Column(String(50), nullable=False, default="whatsapp")
    channel_source = Column(String(32), default="whatsapp")
    provider = Column(String(32), nullable=False, default="ycloud")
    external_user_id = Column(String(255), nullable=False)
    external_chatwoot_id = Column(Integer)
    external_account_id = Column(Integer)
    display_name = Column(String(255))
    status = Column(String(20), default="open")
    human_override_until = Column(DateTime(timezone=True))
    meta = Column(JSONB, default={})
    last_message_at = Column(DateTime(timezone=True))
    last_message_preview = Column(String(255))
    last_read_at = Column(
        DateTime(timezone=True), server_default="1970-01-01 00:00:00+00"
    )
    last_user_message_at = Column(DateTime(timezone=True))
    last_derivhumano_at = Column(DateTime(timezone=True))
    no_followup = Column(Boolean, nullable=False, server_default="false")
    recovery_touch_count = Column(Integer, nullable=False, server_default="0")
    last_recovery_at = Column(DateTime(timezone=True), nullable=True)
    # Meta Direct enrichment
    source_entity_id = Column(Text, nullable=True)
    platform_origin = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_chat_conv_tenant", "tenant_id"),
        Index("idx_chat_conv_tenant_channel", "tenant_id", "channel"),
        Index(
            "idx_chat_conv_tenant_channel_user",
            "tenant_id",
            "channel",
            "external_user_id",
            unique=True,
        ),
        Index("idx_chat_conv_last_derivhumano", "last_derivhumano_at"),
    )


# =============================================================================
# TENANT & CONFIGURATION
# =============================================================================


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    clinic_name = Column(Text, nullable=False, default="Clinica Dental")
    bot_phone_number = Column(Text, unique=True, nullable=False)
    owner_email = Column(Text)
    clinic_location = Column(Text)
    clinic_website = Column(Text)
    system_prompt_template = Column(Text)
    config = Column(JSONB, default={})
    timezone = Column(String(100), default="America/Argentina/Buenos_Aires")
    address = Column(Text)
    google_maps_url = Column(Text)
    logo_url = Column(Text, nullable=True)
    working_hours = Column(JSONB, default={})
    total_tokens_used = Column(BigInteger, default=0)
    total_tool_calls = Column(BigInteger, default=0)
    consultation_price = Column(DECIMAL(12, 2), nullable=True)
    bank_cbu = Column(Text)
    bank_alias = Column(Text)
    bank_holder_name = Column(Text)
    derivation_email = Column(Text)
    max_chairs = Column(Integer, default=2)
    country_code = Column(String(2), nullable=False, default="US", server_default="US")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Dual-engine: 'solo' = TORA monolithic, 'multi' = LangGraph multi-agent
    ai_engine_mode = Column(
        String(10), nullable=False, default="solo", server_default="solo"
    )
    # Editable bot display name (migration 033). NULL → fallback to "TORA".
    bot_name = Column(String(50), nullable=True)

    # --- Support / complaints / review config (migration 039) ---
    complaint_escalation_email = Column(Text, nullable=True)
    complaint_escalation_phone = Column(Text, nullable=True)
    expected_wait_time_minutes = Column(Integer, nullable=True)
    revision_policy = Column(Text, nullable=True)
    review_platforms = Column(JSONB, nullable=True)
    complaint_handling_protocol = Column(JSONB, nullable=True)
    auto_send_review_link_after_followup = Column(
        Boolean, nullable=False, server_default="false"
    )

    # Payment & financing configuration (migration 035)
    payment_methods = Column(JSONB, nullable=True)
    financing_available = Column(Boolean, nullable=True, server_default="false")
    max_installments = Column(Integer, nullable=True)
    installments_interest_free = Column(Boolean, nullable=True, server_default="true")
    financing_provider = Column(Text, nullable=True)
    financing_notes = Column(Text, nullable=True)
    cash_discount_percent = Column(Numeric(5, 2), nullable=True)
    accepts_crypto = Column(Boolean, nullable=True, server_default="false")

    # Social agent: Instagram / Facebook channels (migration 040)
    social_ig_active = Column(Boolean, nullable=False, server_default="false")
    social_landings = Column(JSONB, nullable=True)
    instagram_handle = Column(String(100), nullable=True)
    facebook_page_id = Column(String(100), nullable=True)
    # Migration 042: seña guardrails
    sena_expiration_hours = Column(Integer, nullable=True, server_default="24")
    max_unpaid_appointments = Column(Integer, nullable=True, server_default="1")

    # Clinic special conditions (migration 036)
    accepts_pregnant_patients = Column(
        Boolean, nullable=False, server_default="true", default=True
    )
    pregnancy_restricted_treatments = Column(JSONB, nullable=True, default=list)
    pregnancy_notes = Column(Text, nullable=True)
    accepts_pediatric = Column(
        Boolean, nullable=False, server_default="true", default=True
    )
    min_pediatric_age_years = Column(Integer, nullable=True)
    pediatric_notes = Column(Text, nullable=True)
    high_risk_protocols = Column(JSONB, nullable=True, default=dict)
    requires_anamnesis_before_booking = Column(
        Boolean, nullable=False, server_default="false", default=False
    )


class TenantInsuranceProvider(Base):
    __tablename__ = "tenant_insurance_providers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    provider_name = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False)
    # Structured coverage per treatment code (migration 034). Keyed by
    # treatment_types.code. Each entry carries copay_percent, pre-auth
    # requirements, waiting period, annual cap, and notes. Defaults to {}.
    coverage_by_treatment = Column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    # True for prepagas (OSDE Prepaga, Swiss Medical, etc.) to distinguish
    # from obras sociales tradicionales at prompt-render time.
    is_prepaid = Column(Boolean, nullable=False, server_default=text("false"))
    # Optional discount for employees of affiliated companies (0-100).
    employee_discount_percent = Column(DECIMAL(5, 2), nullable=True)
    # Fallback copay percentage applied when a treatment has no entry in
    # coverage_by_treatment. NULL = no default.
    default_copay_percent = Column(DECIMAL(5, 2), nullable=True)
    external_target = Column(Text, nullable=True)
    requires_copay = Column(Boolean, nullable=False, server_default="true")
    copay_notes = Column(Text, nullable=True)
    ai_response_template = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('accepted', 'restricted', 'external_derivation', 'rejected')",
            name="ck_tenant_insurance_providers_status",
        ),
        UniqueConstraint(
            "tenant_id",
            "provider_name",
            name="uq_tenant_insurance_providers_tenant_name",
        ),
        Index("idx_tenant_insurance_providers_tenant", "tenant_id"),
        Index("idx_tenant_insurance_providers_tenant_active", "tenant_id", "is_active"),
    )


class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    value = Column(Text)
    category = Column(Text)
    scope = Column(Text, default="global")
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"))
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "name", name="idx_credentials_tenant_name_unique"
        ),
        Index("idx_credentials_tenant", "tenant_id"),
    )


class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_type = Column(Text, nullable=False)
    severity = Column(Text, default="info")
    message = Column(Text)
    payload = Column(JSONB)
    occurred_at = Column(DateTime(timezone=True), server_default=func.now())


# =============================================================================
# USERS & RBAC
# =============================================================================


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    first_name = Column(String(100))
    last_name = Column(String(100))
    professional_id = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "role IN ('ceo', 'professional', 'secretary')", name="users_role_check"
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'suspended')", name="users_status_check"
        ),
        Index("idx_users_email", "email"),
        Index("idx_users_status", "status"),
    )


# =============================================================================
# PROFESSIONALS
# =============================================================================


class Professional(Base):
    __tablename__ = "professionals"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255))
    phone_number = Column(String(20))
    specialty = Column(String(100))
    registration_id = Column(String(50))
    google_calendar_id = Column(String(255))
    working_hours = Column(JSONB, default={})
    consultation_price = Column(DECIMAL(12, 2), nullable=True)
    is_priority_professional = Column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_professionals_tenant", "tenant_id"),
        Index("idx_professionals_active", "is_active"),
        Index("idx_professionals_user_id", "user_id"),
    )


class ProfessionalDerivationRule(Base):
    __tablename__ = "professional_derivation_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    rule_name = Column(String(100), nullable=False)
    patient_condition = Column(String(30), nullable=False)
    treatment_categories = Column(ARRAY(String), nullable=False, server_default="{}")
    target_type = Column(String(30), nullable=False)
    target_professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="SET NULL"), nullable=True
    )
    priority_order = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    description = Column(Text, nullable=True)
    # --- Escalation fallback fields (migration 038) ---
    enable_escalation = Column(Boolean, nullable=False, server_default="false")
    fallback_professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="SET NULL"), nullable=True
    )
    fallback_team_mode = Column(Boolean, nullable=False, server_default="false")
    max_wait_days_before_escalation = Column(
        Integer, nullable=False, server_default="7"
    )
    escalation_message_template = Column(Text, nullable=True)
    criteria_custom = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "patient_condition IN ('new_patient', 'existing_patient', 'any')",
            name="ck_professional_derivation_rules_patient_condition",
        ),
        CheckConstraint(
            "target_type IN ('specific_professional', 'priority_professional', 'team')",
            name="ck_professional_derivation_rules_target_type",
        ),
        Index("idx_professional_derivation_rules_tenant", "tenant_id"),
        Index(
            "idx_professional_derivation_rules_tenant_active", "tenant_id", "is_active"
        ),
    )


# =============================================================================
# PATIENTS (with full first-touch / last-touch attribution)
# =============================================================================


class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )

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
    status = Column(String(20), default="active")

    # Urgency (AI triage)
    urgency_level = Column(String(20), default="normal")
    urgency_reason = Column(Text)

    # Human Handoff
    human_handoff_requested = Column(Boolean, default=False)
    human_override_until = Column(DateTime(timezone=True))
    last_derivhumano_at = Column(DateTime(timezone=True))

    # First-Touch Attribution (renamed from meta_ad_* in patch_020)
    first_touch_source = Column(String(50), server_default="ORGANIC")
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

    # Guardian (for minors — links to parent/mother phone)
    guardian_phone = Column(String(20), nullable=True)

    # Meta Direct PSIDs (for IG/FB identity linkage)
    instagram_psid = Column(Text, nullable=True)
    facebook_psid = Column(Text, nullable=True)

    # External IDs (Instagram, Facebook, ChatWot, etc.)
    external_ids = Column(JSONB, nullable=True, server_default=text("'{}'::jsonb"))

    # Location
    city = Column(String(100))

    # Audit
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_visit = Column(DateTime(timezone=True))
    anamnesis_token = Column(UUID(as_uuid=True), nullable=True)

    # Assigned professional (persistent patient→professional relationship)
    assigned_professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "phone_number", name="patients_tenant_id_phone_number_key"
        ),
        UniqueConstraint("tenant_id", "dni", name="patients_tenant_id_dni_key"),
        Index("idx_patients_tenant_phone", "tenant_id", "phone_number"),
        Index("idx_patients_tenant_dni", "tenant_id", "dni"),
        Index("idx_patients_status", "status"),
        Index("idx_patients_insurance", "insurance_provider"),
        Index(
            "idx_patients_handoff",
            "human_handoff_requested",
            postgresql_where=(human_handoff_requested == True),
        ),
        Index("idx_patients_first_touch_source", "first_touch_source"),
        Index("idx_patients_first_touch_ad_id", "first_touch_ad_id"),
        Index("idx_patients_first_touch_campaign_id", "first_touch_campaign_id"),
        Index("idx_patients_first_touch_adset_id", "first_touch_adset_id"),
        Index("idx_patients_city", "city"),
        Index(
            "idx_patients_guardian",
            "guardian_phone",
            postgresql_where=(guardian_phone != None),
        ),
        Index("idx_patients_ig_psid", "tenant_id", "instagram_psid"),
        Index("idx_patients_fb_psid", "tenant_id", "facebook_psid"),
        Index(
            "idx_patients_anamnesis_token",
            "anamnesis_token",
            unique=True,
            postgresql_where=(anamnesis_token != None),
        ),
    )


# =============================================================================
# CLINICAL RECORDS
# =============================================================================


class ClinicalRecord(Base):
    __tablename__ = "clinical_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    patient_id = Column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="SET NULL")
    )
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
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_clinical_records_patient", "patient_id"),
        Index("idx_clinical_records_tenant", "tenant_id"),
        Index("idx_clinical_records_date", record_date.desc()),
        Index("idx_clinical_records_professional", "professional_id"),
    )


# =============================================================================
# APPOINTMENTS
# =============================================================================


class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    patient_id = Column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    appointment_datetime = Column(DateTime(timezone=True), nullable=False)
    duration_minutes = Column(Integer, default=60)
    chair_id = Column(Integer)
    professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="SET NULL")
    )
    appointment_type = Column(String(50), nullable=False)
    notes = Column(Text)
    google_calendar_event_id = Column(String(255))
    google_calendar_sync_status = Column(String(20), default="pending")
    urgency_level = Column(String(20), default="normal")
    urgency_reason = Column(Text)
    status = Column(String(20), default="scheduled")
    cancellation_reason = Column(Text)
    cancellation_by = Column(String(50))
    source = Column(String(20), default="ai")
    reminder_sent = Column(Boolean, default=False)
    reminder_sent_at = Column(DateTime(timezone=True))
    feedback_sent = Column(Boolean, default=False)
    followup_sent = Column(Boolean, default=False)
    followup_sent_at = Column(DateTime(timezone=True))
    billing_amount = Column(DECIMAL(12, 2), nullable=True)
    billing_installments = Column(Integer, nullable=True)
    billing_notes = Column(Text)
    payment_status = Column(String(20), default="pending")
    payment_receipt_data = Column(JSONB, nullable=True)
    # Migration 042: seña guardrails
    sena_expires_at = Column(DateTime(timezone=True), nullable=True)
    sena_amount = Column(DECIMAL(12, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("idx_appointments_patient", "patient_id"),
        Index("idx_appointments_tenant", "tenant_id"),
        Index("idx_appointments_datetime", "appointment_datetime"),
        Index("idx_appointments_chair", "chair_id"),
        Index("idx_appointments_professional", "professional_id"),
        Index("idx_appointments_status", "status"),
        Index("idx_appointments_urgency", "urgency_level"),
        Index("idx_appointments_google_sync", "google_calendar_sync_status"),
        Index("idx_appointments_source", "source"),
        Index("idx_appointments_payment_status", "payment_status"),
    )


# =============================================================================
# ACCOUNTING
# =============================================================================


class AccountingTransaction(Base):
    __tablename__ = "accounting_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"))
    appointment_id = Column(
        UUID(as_uuid=True), ForeignKey("appointments.id", ondelete="SET NULL")
    )
    transaction_type = Column(String(50), nullable=False)
    transaction_date = Column(Date, nullable=False, default=func.current_date())
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), default="ARS")
    payment_method = Column(String(50))
    description = Column(Text)
    insurance_claim_id = Column(String(100))
    insurance_covered_amount = Column(Numeric(12, 2), default=0)
    patient_paid_amount = Column(Numeric(12, 2), default=0)
    status = Column(String(20), default="completed")
    recorded_by = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_accounting_tenant", "tenant_id"),
        Index("idx_accounting_patient", "patient_id"),
        Index("idx_accounting_date", transaction_date.desc()),
        Index("idx_accounting_type", "transaction_type"),
        Index("idx_accounting_status", "status"),
    )


class DailyCashFlow(Base):
    __tablename__ = "daily_cash_flow"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
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
        UniqueConstraint(
            "tenant_id", "cash_date", name="daily_cash_flow_tenant_id_cash_date_key"
        ),
        Index("idx_daily_cash_flow_tenant", "tenant_id"),
        Index("idx_daily_cash_flow_date", "cash_date"),
    )


# =============================================================================
# GOOGLE CALENDAR INTEGRATION
# =============================================================================


class GoogleCalendarBlock(Base):
    __tablename__ = "google_calendar_blocks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    google_event_id = Column(String(255), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    start_datetime = Column(DateTime(timezone=True), nullable=False)
    end_datetime = Column(DateTime(timezone=True), nullable=False)
    all_day = Column(Boolean, default=False)
    professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="CASCADE")
    )
    sync_status = Column(String(20), default="synced")
    last_sync_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_gcalendar_blocks_tenant", "tenant_id"),
        Index("idx_gcalendar_blocks_datetime", "start_datetime", "end_datetime"),
        Index("idx_gcalendar_blocks_professional", "professional_id"),
        Index("idx_gcalendar_blocks_sync_status", "sync_status"),
    )


class CalendarSyncLog(Base):
    __tablename__ = "calendar_sync_log"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
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
        Index("idx_calendar_sync_log_tenant", "tenant_id"),
        Index("idx_calendar_sync_log_date", started_at.desc()),
    )


# =============================================================================
# TREATMENT TYPES & IMAGES
# =============================================================================


class TreatmentType(Base):
    __tablename__ = "treatment_types"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    default_duration_minutes = Column(Integer, nullable=False, default=30)
    min_duration_minutes = Column(Integer, nullable=False, default=15)
    max_duration_minutes = Column(Integer, nullable=False, default=120)
    complexity_level = Column(String(20), default="medium")
    priority = Column(String(20), nullable=False, server_default="medium")
    category = Column(String(50))
    requires_multiple_sessions = Column(Boolean, default=False)
    session_gap_days = Column(Integer, default=0)
    base_price = Column(DECIMAL(12, 2), default=0)
    is_active = Column(Boolean, default=True)
    is_available_for_booking = Column(Boolean, default=True)
    internal_notes = Column(Text)
    # Migration 036: pre_instructions promoted from TEXT to JSONB.
    # Legacy text is wrapped as {"general_notes": "<original>"}.
    # New structured shape: PreInstructions Pydantic model.
    pre_instructions = Column(JSONB, nullable=True)
    # Migration 036: post_instructions still JSONB but now accepts both
    # the legacy list-of-timed-entries shape (wrapped via general_notes)
    # and the new PostInstructions recovery protocol dict shape.
    post_instructions = Column(JSONB, nullable=True)
    followup_template = Column(JSONB, nullable=True)
    patient_display_name = Column(Text, nullable=True)
    # Migration 041: consultation fields for high-ticket treatments
    is_high_ticket = Column(Boolean, nullable=False, server_default="false")
    consultation_duration_minutes = Column(Integer, nullable=True, server_default="30")
    consultation_requirements = Column(Text, nullable=True)
    consultation_notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "code", name="treatment_types_tenant_id_code_key"
        ),
        Index("idx_treatment_types_tenant", "tenant_id"),
        Index("idx_treatment_types_code", "code"),
        Index("idx_treatment_types_category", "category"),
        Index("idx_treatment_types_active", "is_active", "is_available_for_booking"),
    )


class TreatmentTypeProfessional(Base):
    __tablename__ = "treatment_type_professionals"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    treatment_type_id = Column(
        Integer, ForeignKey("treatment_types.id", ondelete="CASCADE"), nullable=False
    )
    professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "treatment_type_id",
            "professional_id",
            name="ttp_tenant_treatment_professional_key",
        ),
        Index("idx_ttp_tenant", "tenant_id"),
        Index("idx_ttp_treatment", "treatment_type_id"),
        Index("idx_ttp_professional", "professional_id"),
    )


class TreatmentImage(Base):
    __tablename__ = "treatment_images"

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
            ["tenant_id", "treatment_code"],
            ["treatment_types.tenant_id", "treatment_types.code"],
            ondelete="CASCADE",
        ),
        Index("idx_treatment_images_tenant_code", "tenant_id", "treatment_code"),
    )


# =============================================================================
# PATIENT DOCUMENTS
# =============================================================================


class PatientDocument(Base):
    __tablename__ = "patient_documents"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    patient_id = Column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    document_type = Column(String(50), server_default="clinical")
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    source = Column(String(50), server_default="manual")
    source_details = Column(JSONB, default={})
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "patient_id",
            "file_name",
            name="patient_documents_tenant_patient_filename_key",
        ),
        Index("idx_patient_documents_tenant", "tenant_id"),
        Index("idx_patient_documents_patient", "patient_id"),
    )


# =============================================================================
# CHANNEL CONFIG & AUTOMATION
# =============================================================================


class ChannelConfig(Base):
    __tablename__ = "channel_configs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    provider = Column(String(50), nullable=False)
    channel = Column(String(50))
    config = Column(JSONB, nullable=False, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "channel",
            name="channel_configs_tenant_provider_channel_key",
        ),
        Index("idx_channel_configs_tenant", "tenant_id"),
        Index("idx_channel_configs_provider", "provider"),
    )


class AutomationRule(Base):
    __tablename__ = "automation_rules"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    trigger_type = Column(Text, nullable=False)
    condition_json = Column(JSONB, default={})
    message_type = Column(Text, nullable=False, server_default="free_text")
    free_text_message = Column(Text)
    ycloud_template_name = Column(Text)
    ycloud_template_lang = Column(Text, server_default="es")
    ycloud_template_vars = Column(JSONB, default={})
    channels = Column(ARRAY(Text), server_default="{whatsapp}")
    send_hour_min = Column(Integer, default=8)
    send_hour_max = Column(Integer, default=20)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index(
            "idx_automation_rules_tenant_active",
            "tenant_id",
            "is_active",
            "trigger_type",
        ),
    )


class AutomationLog(Base):
    __tablename__ = "automation_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="SET NULL"))
    automation_rule_id = Column(
        Integer, ForeignKey("automation_rules.id", ondelete="SET NULL")
    )
    trigger_type = Column(String(50), nullable=False)
    target_id = Column(String(100))
    status = Column(String(20), server_default="pending")
    meta = Column(JSONB, default={})
    error_details = Column(Text)
    rule_name = Column(Text)
    patient_name = Column(Text)
    phone_number = Column(Text)
    channel = Column(Text, server_default="whatsapp")
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
        Index("idx_auto_logs_trigger", "trigger_type"),
        Index("idx_auto_logs_tenant", "tenant_id"),
        Index("idx_auto_logs_target", "target_id"),
        Index("idx_automation_logs_tenant_date", "tenant_id", triggered_at.desc()),
        Index("idx_automation_logs_rule", "automation_rule_id"),
    )


# =============================================================================
# META ADS LEADS & ATTRIBUTION
# =============================================================================


class MetaFormLead(Base):
    __tablename__ = "meta_form_leads"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
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
    status = Column(String(50), server_default="new")
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    notes = Column(Text)
    medical_interest = Column(Text)
    preferred_specialty = Column(Text)
    insurance_provider = Column(Text)
    preferred_date = Column(Date)
    preferred_time = Column(DateTime(timezone=True))
    lead_source = Column(String(100), server_default="meta_form")
    attribution_data = Column(JSONB, default={})
    webhook_payload = Column(JSONB, default={})
    converted_to_patient_id = Column(Integer, ForeignKey("patients.id"))
    converted_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('new', 'contacted', 'consultation_scheduled', 'treatment_planned', 'converted', 'not_interested', 'spam')",
            name="meta_form_leads_status_check",
        ),
        Index("idx_meta_form_leads_tenant_status", "tenant_id", "status"),
        Index("idx_meta_form_leads_phone", "phone_number"),
        Index("idx_meta_form_leads_created", created_at.desc()),
        Index("idx_meta_form_leads_campaign", "campaign_id"),
        Index("idx_meta_form_leads_assigned", "assigned_to"),
        Index("idx_meta_form_leads_ad", "ad_id"),
        Index(
            "idx_meta_form_leads_converted",
            "converted_to_patient_id",
            postgresql_where=(converted_to_patient_id != None),
        ),
    )


class LeadStatusHistory(Base):
    __tablename__ = "lead_status_history"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meta_form_leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    old_status = Column(String(50))
    new_status = Column(String(50), nullable=False)
    changed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    change_reason = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_lead_status_history_tenant", "tenant_id"),
        Index("idx_lead_status_history_lead", "lead_id"),
        Index("idx_lead_status_history_created", created_at.desc()),
    )


class LeadNote(Base):
    __tablename__ = "lead_notes"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("meta_form_leads.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    content = Column(Text, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_lead_notes_tenant", "tenant_id"),
        Index("idx_lead_notes_lead", "lead_id"),
        Index("idx_lead_notes_created", created_at.desc()),
    )


class PatientAttributionHistory(Base):
    __tablename__ = "patient_attribution_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id = Column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
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
    lead_id = Column(UUID(as_uuid=True), ForeignKey("meta_form_leads.id"))
    event_timestamp = Column(DateTime, nullable=False, server_default=func.now())
    event_description = Column(Text)

    __table_args__ = (
        CheckConstraint(
            "attribution_type IN ('first_touch', 'last_touch', 'conversion')",
            name="patient_attribution_history_type_check",
        ),
        Index("idx_patient_attribution_patient_tenant", "patient_id", "tenant_id"),
        Index("idx_patient_attribution_type", "attribution_type"),
        Index("idx_patient_attribution_source", "source"),
        Index("idx_patient_attribution_ad", "ad_id"),
        Index("idx_patient_attribution_campaign", "campaign_id"),
        Index("idx_patient_attribution_timestamp", event_timestamp.desc()),
    )


# =============================================================================
# GOOGLE ADS INTEGRATION
# =============================================================================


class GoogleOAuthToken(Base):
    __tablename__ = "google_oauth_tokens"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    platform = Column(String(50), nullable=False, default="ads")
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    scopes = Column(ARRAY(Text))
    email = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "platform", name="google_oauth_tokens_tenant_platform_key"
        ),
        Index("idx_google_oauth_tokens_tenant", "tenant_id"),
        Index("idx_google_oauth_tokens_expires", "expires_at"),
    )


class GoogleAdsAccount(Base):
    __tablename__ = "google_ads_accounts"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    customer_id = Column(String(50), nullable=False)
    descriptive_name = Column(String(255))
    currency_code = Column(String(10))
    time_zone = Column(String(50))
    manager = Column(Boolean, default=False)
    test_account = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "customer_id", name="google_ads_accounts_tenant_customer_key"
        ),
        Index("idx_google_ads_accounts_tenant", "tenant_id"),
    )


class GoogleAdsMetricsCache(Base):
    __tablename__ = "google_ads_metrics_cache"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
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
        UniqueConstraint(
            "tenant_id",
            "customer_id",
            "campaign_id",
            "date",
            name="google_ads_metrics_cache_unique_key",
        ),
        Index("idx_google_ads_metrics_cache_tenant_date", "tenant_id", "date"),
        Index("idx_google_ads_metrics_cache_campaign", "campaign_id", "date"),
    )


# =============================================================================
# ANALYTICS DASHBOARD
# =============================================================================


class DailyAnalyticsMetric(Base):
    __tablename__ = "daily_analytics_metrics"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(UUID(as_uuid=True), nullable=False)
    metric_date = Column(Date, nullable=False)
    metric_type = Column(String(50), nullable=False)
    metric_value = Column(JSONB, default="0")
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "metric_date",
            "metric_type",
            name="daily_analytics_metrics_tenant_date_type_key",
        ),
        Index("idx_analytics_tenant_date", "tenant_id", "metric_date"),
    )


# =============================================================================
# CLINIC FAQS
# =============================================================================


class ClinicFaq(Base):
    __tablename__ = "clinic_faqs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    category = Column(String(100), nullable=False, server_default="General")
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("idx_clinic_faqs_tenant", "tenant_id"),)


# =============================================================================
# TENANT HOLIDAYS
# =============================================================================


class TenantHoliday(Base):
    __tablename__ = "tenant_holidays"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    date = Column(Date, nullable=False)
    name = Column(Text, nullable=False)
    holiday_type = Column(String(20), nullable=False)
    is_recurring = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    custom_hours_start = Column(Time, nullable=True)
    custom_hours_end = Column(Time, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "date",
            "holiday_type",
            name="uq_tenant_holidays_tenant_date_type",
        ),
        CheckConstraint(
            "holiday_type IN ('closure', 'override_open')",
            name="ck_tenant_holidays_type",
        ),
        Index("idx_tenant_holidays_tenant_date", "tenant_id", "date"),
    )


# =============================================================================
# PATIENT DIGITAL RECORDS
# =============================================================================


class PatientDigitalRecord(Base):
    __tablename__ = "patient_digital_records"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    patient_id = Column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="SET NULL"), nullable=True
    )
    template_type = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    html_content = Column(Text, nullable=False, server_default="")
    pdf_path = Column(String(500), nullable=True)
    pdf_generated_at = Column(DateTime(timezone=True), nullable=True)
    source_data = Column(JSONB, nullable=False, server_default="{}")
    generation_metadata = Column(JSONB, nullable=True, server_default="{}")
    status = Column(String(20), nullable=False, server_default="draft")
    sent_to_email = Column(String(255), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'final', 'sent')",
            name="ck_patient_digital_records_status",
        ),
        CheckConstraint(
            "template_type IN ('clinical_report', 'post_surgery', 'odontogram_art', 'authorization_request')",
            name="ck_patient_digital_records_template_type",
        ),
        Index("idx_pdr_tenant_patient", "tenant_id", "patient_id"),
        Index("idx_pdr_tenant", "tenant_id"),
        Index("idx_pdr_status", "tenant_id", "status"),
    )


# =============================================================================
# TREATMENT PLAN BILLING (tables from migration 018)
# =============================================================================


class TreatmentPlan(Base):
    __tablename__ = "treatment_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    patient_id = Column(
        Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False
    )
    professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="SET NULL"), nullable=True
    )
    name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, server_default="draft")
    estimated_total = Column(Numeric(12, 2), server_default="0")
    approved_total = Column(Numeric(12, 2), nullable=True)
    paid_total = Column(Numeric(12, 2), server_default="0")
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    patient = relationship("Patient", backref="treatment_plans")
    professional = relationship("Professional")
    tenant = relationship("Tenant")
    items = relationship(
        "TreatmentPlanItem", back_populates="plan", cascade="all, delete-orphan"
    )
    payments = relationship(
        "TreatmentPlanPayment", back_populates="plan", cascade="all, delete-orphan"
    )


class TreatmentPlanItem(Base):
    __tablename__ = "treatment_plan_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("treatment_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    treatment_type_code = Column(String(50), nullable=True)
    custom_description = Column(String(255), nullable=True)
    estimated_price = Column(Numeric(12, 2), nullable=False, server_default="0")
    approved_price = Column(Numeric(12, 2), nullable=True)
    quantity = Column(Integer, server_default="1")
    sort_order = Column(Integer, nullable=False, server_default="0")
    status = Column(String(20), server_default="pending")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    plan = relationship("TreatmentPlan", back_populates="items")
    tenant = relationship("Tenant")


class TreatmentPlanPayment(Base):
    __tablename__ = "treatment_plan_payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("treatment_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(20), nullable=False)
    payment_date = Column(Date, nullable=False, server_default=func.current_date())
    reference_number = Column(String(100), nullable=True)
    recorded_by = Column(String(100), nullable=True)
    appointment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("appointments.id", ondelete="SET NULL"),
        nullable=True,
    )
    receipt_data = Column(JSONB, nullable=True)
    notes = Column(Text, nullable=True)
    accounting_transaction_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounting_transactions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    plan = relationship("TreatmentPlan", back_populates="payments")
    tenant = relationship("Tenant")


# =============================================================================
# FINANCIAL COMMAND CENTER (tables from migration 020)
# =============================================================================


class ProfessionalCommission(Base):
    __tablename__ = "professional_commissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False
    )
    commission_pct = Column(Numeric(5, 2), nullable=False, server_default="0")
    treatment_code = Column(String(100), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "professional_id", "treatment_code", name="uq_prof_comm"
        ),
    )

    professional = relationship("Professional", backref="commission_configs")
    tenant = relationship("Tenant")


class LiquidationRecord(Base):
    __tablename__ = "liquidation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False
    )
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_billed = Column(Numeric(12, 2), nullable=False, server_default="0")
    total_paid = Column(Numeric(12, 2), nullable=False, server_default="0")
    total_pending = Column(Numeric(12, 2), nullable=False, server_default="0")
    commission_pct = Column(Numeric(5, 2), nullable=False, server_default="0")
    commission_amount = Column(Numeric(12, 2), nullable=False, server_default="0")
    payout_amount = Column(Numeric(12, 2), nullable=False, server_default="0")
    status = Column(String(20), nullable=False, server_default="draft")
    generated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    generated_by = Column(String(255), nullable=True)
    notes = Column(JSONB, server_default="{}")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    professional = relationship("Professional", backref="liquidation_records")
    tenant = relationship("Tenant")
    payouts = relationship("ProfessionalPayout", back_populates="liquidation_record")


class ProfessionalPayout(Base):
    __tablename__ = "professional_payouts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    liquidation_id = Column(
        Integer,
        ForeignKey("liquidation_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    professional_id = Column(
        Integer, ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False
    )
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(20), nullable=False, server_default="transfer")
    payment_date = Column(Date, nullable=False, server_default=func.current_date())
    reference_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    liquidation_record = relationship("LiquidationRecord", back_populates="payouts")
    professional = relationship("Professional", backref="payouts")
    tenant = relationship("Tenant")


# =============================================================================
# NOVA MEMORIES (Engram persistent memory — migration 023)
# =============================================================================


class NovaMemory(Base):
    __tablename__ = "nova_memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    type = Column(String(50), nullable=False, server_default="general")
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    topic_key = Column(String(255), nullable=True)
    created_by = Column(String(100), nullable=True)
    source_channel = Column(String(50), nullable=False, server_default="unknown")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        Index("idx_nova_memories_tenant", "tenant_id"),
        Index("idx_nova_memories_type", "tenant_id", "type"),
        Index("idx_nova_memories_topic_key", "tenant_id", "topic_key"),
    )


# =============================================================================
# MULTI-AGENT SYSTEM (migration 032)
# =============================================================================


class PatientContextSnapshot(Base):
    """LangGraph checkpoint storage for multi-agent conversations."""

    __tablename__ = "patient_context_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    phone_number = Column(Text, nullable=False)
    thread_id = Column(Text, nullable=False)
    state = Column(JSONB, nullable=False)
    active_agent = Column(String(50), nullable=True)
    hop_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "phone_number", "thread_id", name="uq_pcs_tenant_phone_thread"
        ),
        Index("idx_pcs_tenant_phone", "tenant_id", "phone_number"),
        Index("idx_pcs_thread", "thread_id"),
    )


class AgentTurnLog(Base):
    """Audit log for multi-agent system interactions."""

    __tablename__ = "agent_turn_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(
        Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    phone_number = Column(Text, nullable=False)
    turn_id = Column(Text, nullable=False)
    agent_name = Column(String(50), nullable=False)
    tools_called = Column(JSONB, nullable=True)
    handoff_to = Column(String(50), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    model = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_atl_tenant_phone", "tenant_id", "phone_number"),
        Index("idx_atl_turn", "turn_id"),
    )
