"""Full baseline - complete ClinicForge schema (consolidated from 58 migrations)

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-03-17 (updated 2026-04-23)

This migration represents the complete production schema consolidated from
migrations 001 through 058 plus out-of-band columns.
For existing databases: run 'alembic stamp head' to mark as current.
For fresh databases: run 'alembic upgrade head' to create everything.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =====================================================================
    # EXTENSIONS — installed by start.sh BEFORE alembic runs (requires autocommit)
    # =====================================================================

    # =====================================================================
    # TENANTS (must be first - many FKs reference it)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS tenants (
        id SERIAL PRIMARY KEY,
        clinic_name TEXT NOT NULL DEFAULT 'Clinica Dental',
        bot_phone_number TEXT UNIQUE NOT NULL,
        owner_email TEXT,
        clinic_location TEXT,
        clinic_website TEXT,
        system_prompt_template TEXT,
        config JSONB DEFAULT '{}',
        timezone VARCHAR(100) DEFAULT 'America/Argentina/Buenos_Aires',
        address TEXT,
        google_maps_url TEXT,
        working_hours JSONB DEFAULT '{}',
        total_tokens_used BIGINT DEFAULT 0,
        total_tool_calls BIGINT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        -- 003: consultation price
        consultation_price DECIMAL(12,2) DEFAULT NULL,
        -- 006: billing & bank
        bank_cbu TEXT,
        bank_alias TEXT,
        bank_holder_name TEXT,
        derivation_email TEXT,
        -- 007: logo
        logo_url TEXT,
        -- 008: chairs
        max_chairs INTEGER DEFAULT 2,
        -- 010: country code
        country_code VARCHAR(2) NOT NULL DEFAULT 'AR',
        -- 031: dual-engine
        ai_engine_mode TEXT NOT NULL DEFAULT 'solo' CHECK (ai_engine_mode IN ('solo', 'multi')),
        -- 033: bot name
        bot_name VARCHAR(50),
        -- 035: payment & financing
        payment_methods JSONB,
        financing_available BOOLEAN DEFAULT FALSE,
        max_installments INTEGER,
        installments_interest_free BOOLEAN DEFAULT TRUE,
        financing_provider TEXT,
        financing_notes TEXT,
        cash_discount_percent NUMERIC(5,2),
        accepts_crypto BOOLEAN DEFAULT FALSE,
        -- 036: special conditions
        accepts_pregnant_patients BOOLEAN NOT NULL DEFAULT TRUE,
        pregnancy_restricted_treatments JSONB DEFAULT '[]'::jsonb,
        pregnancy_notes TEXT,
        accepts_pediatric BOOLEAN NOT NULL DEFAULT TRUE,
        min_pediatric_age_years INTEGER,
        pediatric_notes TEXT,
        high_risk_protocols JSONB DEFAULT '{}'::jsonb,
        requires_anamnesis_before_booking BOOLEAN NOT NULL DEFAULT FALSE,
        -- 039: support/complaints
        complaint_escalation_email TEXT,
        complaint_escalation_phone TEXT,
        expected_wait_time_minutes INTEGER,
        revision_policy TEXT,
        review_platforms JSONB,
        complaint_handling_protocol JSONB,
        auto_send_review_link_after_followup BOOLEAN NOT NULL DEFAULT FALSE,
        -- 040: social IG/FB
        social_ig_active BOOLEAN NOT NULL DEFAULT FALSE,
        social_landings JSONB,
        instagram_handle VARCHAR(100),
        facebook_page_id VARCHAR(100),
        -- 042: sena guardrails
        sena_expiration_hours INTEGER DEFAULT 24,
        max_unpaid_appointments INTEGER DEFAULT 1,
        -- 035 constraints (inline CHECK)
        CONSTRAINT ck_tenants_max_installments_range CHECK (max_installments IS NULL OR (max_installments >= 1 AND max_installments <= 24)),
        CONSTRAINT ck_tenants_cash_discount_range CHECK (cash_discount_percent IS NULL OR (cash_discount_percent >= 0 AND cash_discount_percent <= 100))
    )
    """)

    # Default tenant
    op.execute("""
    INSERT INTO tenants (clinic_name, bot_phone_number, clinic_location, country_code)
    VALUES ('Clinica Dental', '5491100000000', 'Argentina', 'AR')
    ON CONFLICT (bot_phone_number) DO NOTHING
    """)

    # =====================================================================
    # CREDENTIALS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS credentials (
        id SERIAL PRIMARY KEY,
        name VARCHAR(255) NOT NULL,
        value TEXT,
        category TEXT,
        scope TEXT DEFAULT 'global',
        tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
        description TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_credentials_tenant_name_unique ON credentials(tenant_id, name)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_credentials_tenant ON credentials(tenant_id)")

    # =====================================================================
    # SYSTEM EVENTS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS system_events (
        id BIGSERIAL PRIMARY KEY,
        event_type TEXT NOT NULL,
        severity TEXT DEFAULT 'info',
        message TEXT,
        payload JSONB,
        occurred_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)

    # =====================================================================
    # INBOUND MESSAGES
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS inbound_messages (
        id BIGSERIAL PRIMARY KEY,
        provider TEXT NOT NULL,
        provider_message_id TEXT NOT NULL,
        event_id TEXT NULL,
        from_number TEXT NOT NULL,
        payload JSONB NOT NULL,
        status TEXT NOT NULL CHECK (status IN ('received', 'processing', 'done', 'failed')),
        received_at TIMESTAMPTZ DEFAULT NOW(),
        processed_at TIMESTAMPTZ NULL,
        error TEXT NULL,
        correlation_id TEXT NULL,
        UNIQUE (provider, provider_message_id)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_inbound_messages_from_number_received_at ON inbound_messages(from_number, received_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_inbound_messages_status ON inbound_messages(status)")

    # =====================================================================
    # USERS (RBAC)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email VARCHAR(255) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        role VARCHAR(50) NOT NULL CHECK (role IN ('ceo', 'professional', 'secretary')),
        status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'suspended')),
        first_name VARCHAR(100),
        last_name VARCHAR(100),
        professional_id INTEGER NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")

    # =====================================================================
    # PROFESSIONALS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS professionals (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100) NOT NULL,
        email VARCHAR(255),
        phone_number VARCHAR(20),
        specialty VARCHAR(100),
        registration_id VARCHAR(50),
        google_calendar_id VARCHAR(255),
        working_hours JSONB DEFAULT '{}',
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        -- 006: per-professional consultation price override
        consultation_price DECIMAL(12, 2),
        -- 011: priority professional flag
        is_priority_professional BOOLEAN NOT NULL DEFAULT FALSE
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_professionals_tenant ON professionals(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_professionals_active ON professionals(is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_professionals_user_id ON professionals(user_id)")

    # =====================================================================
    # PATIENTS (full attribution + meta columns)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS patients (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        phone_number VARCHAR(20) NOT NULL,
        dni VARCHAR(15),
        first_name VARCHAR(100) NOT NULL,
        last_name VARCHAR(100),
        birth_date DATE,
        gender VARCHAR(10),
        insurance_provider VARCHAR(100),
        insurance_id VARCHAR(50),
        insurance_valid_until DATE,
        medical_history JSONB DEFAULT '{}',
        email VARCHAR(255),
        alternative_phone VARCHAR(20),
        preferred_schedule TEXT,
        notes TEXT,
        status VARCHAR(20) DEFAULT 'active',
        urgency_level VARCHAR(20) DEFAULT 'normal',
        urgency_reason TEXT,
        human_handoff_requested BOOLEAN DEFAULT FALSE,
        human_override_until TIMESTAMPTZ DEFAULT NULL,
        last_derivhumano_at TIMESTAMPTZ DEFAULT NULL,
        first_touch_source VARCHAR(50) DEFAULT 'ORGANIC',
        first_touch_ad_id VARCHAR(255),
        first_touch_campaign_id VARCHAR(255),
        first_touch_ad_name TEXT,
        first_touch_campaign_name TEXT,
        first_touch_adset_id VARCHAR(255),
        first_touch_adset_name TEXT,
        first_touch_ad_headline TEXT,
        first_touch_ad_body TEXT,
        last_touch_source VARCHAR(50),
        last_touch_ad_id VARCHAR(255),
        last_touch_campaign_id VARCHAR(255),
        last_touch_ad_name TEXT,
        last_touch_campaign_name TEXT,
        last_touch_timestamp TIMESTAMP,
        city VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        last_visit TIMESTAMPTZ,
        -- 003: anamnesis token
        anamnesis_token UUID DEFAULT NULL,
        -- 004: guardian phone for minors
        guardian_phone VARCHAR(20) DEFAULT NULL,
        -- 005: Meta PSIDs
        instagram_psid TEXT,
        facebook_psid TEXT,
        -- 024: assigned professional
        assigned_professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,
        -- 046: external IDs (Instagram, Facebook, Chatwoot, etc.)
        external_ids JSONB DEFAULT '{}'::jsonb,
        -- 047: automation cooldown
        last_automation_message_at TIMESTAMPTZ,
        -- 057: patient source
        patient_source VARCHAR(20) NOT NULL DEFAULT 'regular',
        -- Out-of-band Meta attribution columns
        acquisition_source TEXT,
        meta_ad_id TEXT,
        meta_ad_name TEXT,
        meta_ad_headline TEXT,
        meta_ad_body TEXT,
        meta_adset_id TEXT,
        meta_adset_name TEXT,
        meta_campaign_id TEXT,
        meta_campaign_name TEXT,
        UNIQUE (tenant_id, phone_number),
        UNIQUE (tenant_id, dni)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_tenant_phone ON patients(tenant_id, phone_number)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_tenant_dni ON patients(tenant_id, dni)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_status ON patients(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_insurance ON patients(insurance_provider)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_handoff ON patients(human_handoff_requested) WHERE human_handoff_requested = TRUE")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_first_touch_source ON patients(first_touch_source)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_first_touch_ad_id ON patients(first_touch_ad_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_first_touch_campaign_id ON patients(first_touch_campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_first_touch_adset_id ON patients(first_touch_adset_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_city ON patients(city)")
    # 003: anamnesis token unique index
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_patients_anamnesis_token ON patients(anamnesis_token) WHERE anamnesis_token IS NOT NULL")
    # 004: guardian phone index
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_guardian ON patients(guardian_phone) WHERE guardian_phone IS NOT NULL")
    # 005: Meta PSIDs indexes
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_ig_psid ON patients(tenant_id, instagram_psid)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_fb_psid ON patients(tenant_id, facebook_psid)")
    # 024: assigned professional partial index
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_assigned_professional ON patients(tenant_id, assigned_professional_id) WHERE assigned_professional_id IS NOT NULL")
    # 055: pg_trgm trigram indexes — created by start.sh after extensions are installed
    # 057: patient source partial index
    op.execute("CREATE INDEX IF NOT EXISTS idx_patients_source ON patients(patient_source) WHERE patient_source != 'regular'")

    # =====================================================================
    # CLINICAL RECORDS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS clinical_records (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        record_date DATE NOT NULL DEFAULT CURRENT_DATE,
        professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,
        odontogram JSONB DEFAULT '{}',
        odontogram_data JSONB DEFAULT '{}',
        diagnosis TEXT,
        treatments JSONB DEFAULT '[]',
        radiographs JSONB DEFAULT '[]',
        treatment_plan JSONB DEFAULT '{}',
        clinical_notes TEXT,
        recommendations TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_clinical_records_patient ON clinical_records(patient_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_clinical_records_tenant ON clinical_records(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_clinical_records_date ON clinical_records(record_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_clinical_records_professional ON clinical_records(professional_id)")
    # 017: GIN index on odontogram_data
    op.execute("CREATE INDEX IF NOT EXISTS idx_clinical_records_odontogram_gin ON clinical_records USING GIN (odontogram_data)")

    # =====================================================================
    # APPOINTMENTS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS appointments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        appointment_datetime TIMESTAMPTZ NOT NULL,
        duration_minutes INTEGER DEFAULT 60,
        chair_id INTEGER,
        professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,
        appointment_type VARCHAR(50) NOT NULL,
        notes TEXT,
        google_calendar_event_id VARCHAR(255),
        google_calendar_sync_status VARCHAR(20) DEFAULT 'pending',
        urgency_level VARCHAR(20) DEFAULT 'normal',
        urgency_reason TEXT,
        status VARCHAR(20) DEFAULT 'scheduled',
        cancellation_reason TEXT,
        cancellation_by VARCHAR(50),
        source VARCHAR(20) DEFAULT 'ai',
        reminder_sent BOOLEAN DEFAULT FALSE,
        reminder_sent_at TIMESTAMPTZ,
        feedback_sent BOOLEAN DEFAULT FALSE,
        followup_sent BOOLEAN DEFAULT FALSE,
        followup_sent_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        -- 006: billing fields
        billing_amount DECIMAL(12, 2),
        billing_installments INTEGER,
        billing_notes TEXT,
        payment_status VARCHAR(20) DEFAULT 'pending',
        payment_receipt_data JSONB,
        -- 018: treatment plan link
        plan_item_id UUID,
        -- 042: sena guardrails
        sena_expires_at TIMESTAMPTZ,
        sena_amount NUMERIC(12, 2)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_tenant ON appointments(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_datetime ON appointments(appointment_datetime)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_chair ON appointments(chair_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_professional ON appointments(professional_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_urgency ON appointments(urgency_level)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_google_sync ON appointments(google_calendar_sync_status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_source ON appointments(source)")
    # 006: payment status index
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_payment_status ON appointments(payment_status)")
    # 018/019: plan_item_id partial index (renamed in 019)
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointments_plan_item_id ON appointments(plan_item_id) WHERE plan_item_id IS NOT NULL")
    # 027: double-booking prevention partial unique index
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS idx_appointments_no_double_booking
        ON appointments (professional_id, appointment_datetime)
        WHERE status IN ('scheduled', 'confirmed') AND professional_id IS NOT NULL""")
    # 042: sena expiry partial index
    op.execute("""CREATE INDEX IF NOT EXISTS idx_appointments_sena_expiry
        ON appointments (sena_expires_at)
        WHERE sena_expires_at IS NOT NULL AND payment_status = 'pending' AND status IN ('scheduled', 'confirmed')""")

    # =====================================================================
    # ACCOUNTING TRANSACTIONS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS accounting_transactions (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
        appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
        transaction_type VARCHAR(50) NOT NULL,
        transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
        amount NUMERIC(12, 2) NOT NULL,
        currency VARCHAR(3) DEFAULT 'ARS',
        payment_method VARCHAR(50),
        description TEXT,
        insurance_claim_id VARCHAR(100),
        insurance_covered_amount NUMERIC(12, 2) DEFAULT 0,
        patient_paid_amount NUMERIC(12, 2) DEFAULT 0,
        status VARCHAR(20) DEFAULT 'completed',
        recorded_by VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounting_tenant ON accounting_transactions(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounting_patient ON accounting_transactions(patient_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounting_date ON accounting_transactions(transaction_date DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounting_type ON accounting_transactions(transaction_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_accounting_status ON accounting_transactions(status)")

    # =====================================================================
    # DAILY CASH FLOW
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS daily_cash_flow (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        cash_date DATE NOT NULL,
        total_cash_received NUMERIC(12, 2) DEFAULT 0,
        total_card_received NUMERIC(12, 2) DEFAULT 0,
        total_insurance_claimed NUMERIC(12, 2) DEFAULT 0,
        total_expenses NUMERIC(12, 2) DEFAULT 0,
        net_balance NUMERIC(12, 2) DEFAULT 0,
        recorded_at TIMESTAMPTZ DEFAULT NOW(),
        recorded_by VARCHAR(100),
        notes TEXT,
        UNIQUE (tenant_id, cash_date)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_daily_cash_flow_tenant ON daily_cash_flow(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_daily_cash_flow_date ON daily_cash_flow(cash_date)")

    # =====================================================================
    # GOOGLE CALENDAR BLOCKS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS google_calendar_blocks (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        google_event_id VARCHAR(255) UNIQUE NOT NULL,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        start_datetime TIMESTAMPTZ NOT NULL,
        end_datetime TIMESTAMPTZ NOT NULL,
        all_day BOOLEAN DEFAULT FALSE,
        professional_id INTEGER REFERENCES professionals(id) ON DELETE CASCADE,
        sync_status VARCHAR(20) DEFAULT 'synced',
        last_sync_at TIMESTAMPTZ DEFAULT NOW(),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_gcalendar_blocks_tenant ON google_calendar_blocks(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_gcalendar_blocks_datetime ON google_calendar_blocks(start_datetime, end_datetime)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_gcalendar_blocks_professional ON google_calendar_blocks(professional_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_gcalendar_blocks_sync_status ON google_calendar_blocks(sync_status)")

    # =====================================================================
    # CALENDAR SYNC LOG
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS calendar_sync_log (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        sync_type VARCHAR(50) NOT NULL,
        direction VARCHAR(20) NOT NULL,
        events_processed INTEGER DEFAULT 0,
        events_created INTEGER DEFAULT 0,
        events_updated INTEGER DEFAULT 0,
        events_deleted INTEGER DEFAULT 0,
        errors_count INTEGER DEFAULT 0,
        started_at TIMESTAMPTZ DEFAULT NOW(),
        completed_at TIMESTAMPTZ,
        error_message TEXT
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_calendar_sync_log_tenant ON calendar_sync_log(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_calendar_sync_log_date ON calendar_sync_log(started_at DESC)")

    # =====================================================================
    # TREATMENT TYPES (with all columns from 011, 012, 022, 037, 041, 045, 047)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS treatment_types (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        code VARCHAR(50) NOT NULL,
        name VARCHAR(100) NOT NULL,
        description TEXT,
        default_duration_minutes INTEGER NOT NULL DEFAULT 30,
        min_duration_minutes INTEGER NOT NULL DEFAULT 15,
        max_duration_minutes INTEGER NOT NULL DEFAULT 120,
        complexity_level VARCHAR(20) DEFAULT 'medium',
        category VARCHAR(50),
        requires_multiple_sessions BOOLEAN DEFAULT FALSE,
        session_gap_days INTEGER DEFAULT 0,
        base_price DECIMAL(12,2) DEFAULT 0,
        is_active BOOLEAN DEFAULT TRUE,
        is_available_for_booking BOOLEAN DEFAULT TRUE,
        internal_notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        -- 011: priority field
        priority VARCHAR(20) NOT NULL DEFAULT 'medium',
        -- 012: instructions (pre as JSONB after 037 migration)
        pre_instructions JSONB,
        post_instructions JSONB,
        followup_template JSONB,
        -- 022/045: patient display name
        patient_display_name TEXT,
        -- 041: high-ticket consultation fields
        is_high_ticket BOOLEAN NOT NULL DEFAULT FALSE,
        consultation_duration_minutes INTEGER DEFAULT 30,
        consultation_requirements TEXT,
        consultation_notes TEXT,
        -- 045: AI response template
        ai_response_template TEXT,
        -- 047: post-treatment HSM template
        post_treatment_hsm_template TEXT,
        CONSTRAINT ck_treatment_types_priority CHECK (priority IN ('high', 'medium-high', 'medium', 'low'))
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_types_tenant ON treatment_types(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_types_code ON treatment_types(code)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_types_category ON treatment_types(category)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_types_active ON treatment_types(is_active, is_available_for_booking)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_treatment_types_tenant_code ON treatment_types(tenant_id, code)")

    # Default treatment types
    for code, name, desc, dur, min_d, max_d, comp, cat, multi, gap in [
        ('checkup', 'Control/Checkup', 'Revision general y evaluacion de salud bucodental', 20, 15, 30, 'low', 'prevention', False, 0),
        ('cleaning', 'Limpieza Dental', 'Profilaxis y limpieza profesional', 30, 20, 45, 'low', 'prevention', False, 0),
        ('emergency', 'Consulta Urgente', 'Atencion de urgencia odontologica', 15, 10, 30, 'emergency', 'emergency', False, 0),
        ('extraction', 'Extraccion Dental', 'Extraccion simple o quirurgica de pieza dental', 30, 20, 60, 'medium', 'surgical', False, 0),
        ('root_canal', 'Endodoncia', 'Tratamiento de conducto', 60, 45, 90, 'high', 'restorative', False, 0),
        ('restoration', 'Restauracion/Obturacion', 'Empastes y reconstrucciones', 30, 20, 45, 'medium', 'restorative', False, 0),
        ('orthodontics', 'Ortodoncia', 'Colocacion de aparato de ortodoncia', 45, 30, 60, 'high', 'orthodontics', True, 7),
        ('consultation', 'Consulta General', 'Primera consulta o evaluacion', 30, 15, 45, 'low', 'prevention', False, 0),
    ]:
        op.execute(f"""
        INSERT INTO treatment_types (tenant_id, code, name, description, default_duration_minutes,
            min_duration_minutes, max_duration_minutes, complexity_level, category,
            requires_multiple_sessions, session_gap_days, is_active, is_available_for_booking)
        SELECT t.id, '{code}', '{name}', '{desc}', {dur}, {min_d}, {max_d}, '{comp}', '{cat}',
            {str(multi).upper()}, {gap}, TRUE, TRUE
        FROM tenants t
        WHERE NOT EXISTS (SELECT 1 FROM treatment_types tt WHERE tt.tenant_id = t.id AND tt.code = '{code}')
        """)

    # =====================================================================
    # TREATMENT IMAGES
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS treatment_images (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL,
        treatment_code VARCHAR(50) NOT NULL,
        filename VARCHAR(255) NOT NULL,
        file_path VARCHAR(1000) NOT NULL,
        mime_type VARCHAR(100),
        file_size INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        FOREIGN KEY (tenant_id, treatment_code) REFERENCES treatment_types(tenant_id, code) ON DELETE CASCADE
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_images_tenant_code ON treatment_images(tenant_id, treatment_code)")

    # =====================================================================
    # TREATMENT TYPE PROFESSIONALS (002)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS treatment_type_professionals (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        treatment_type_id INTEGER NOT NULL REFERENCES treatment_types(id) ON DELETE CASCADE,
        professional_id INTEGER NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(tenant_id, treatment_type_id, professional_id)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_ttp_tenant ON treatment_type_professionals(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ttp_treatment ON treatment_type_professionals(treatment_type_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ttp_professional ON treatment_type_professionals(professional_id)")

    # =====================================================================
    # CHAT CONVERSATIONS (with 005, 043, 054 columns)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS chat_conversations (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        channel VARCHAR(50) NOT NULL DEFAULT 'whatsapp',
        channel_source VARCHAR(32) DEFAULT 'whatsapp',
        provider VARCHAR(32) NOT NULL DEFAULT 'ycloud',
        external_user_id VARCHAR(255) NOT NULL,
        external_chatwoot_id INTEGER,
        external_account_id INTEGER,
        display_name VARCHAR(255),
        status VARCHAR(20) DEFAULT 'open',
        human_override_until TIMESTAMPTZ,
        meta JSONB DEFAULT '{}',
        last_message_at TIMESTAMPTZ,
        last_message_preview VARCHAR(255),
        last_read_at TIMESTAMPTZ DEFAULT '1970-01-01 00:00:00+00',
        last_user_message_at TIMESTAMPTZ,
        last_derivhumano_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        -- 005: enrichment columns
        source_entity_id TEXT,
        platform_origin TEXT,
        -- 043: lead recovery v2 fields
        no_followup BOOLEAN NOT NULL DEFAULT FALSE,
        recovery_touch_count INTEGER NOT NULL DEFAULT 0,
        last_recovery_at TIMESTAMPTZ,
        -- 054: linked patient
        linked_patient_id INTEGER,
        linked_at TIMESTAMPTZ
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conv_tenant ON chat_conversations(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conv_tenant_channel ON chat_conversations(tenant_id, channel)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_conv_tenant_channel_user ON chat_conversations(tenant_id, channel, external_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conv_last_derivhumano ON chat_conversations(last_derivhumano_at)")
    # 043: lead recovery index
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conv_recovery ON chat_conversations(tenant_id, last_user_message_at, recovery_touch_count, no_followup)")
    # 054: linked patient partial index
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conv_linked_patient ON chat_conversations(linked_patient_id) WHERE linked_patient_id IS NOT NULL")

    # =====================================================================
    # CHAT MESSAGES (with 030 unique index, 052 role constraint, 056 delivery_status)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id BIGSERIAL PRIMARY KEY,
        tenant_id INTEGER DEFAULT 1 REFERENCES tenants(id) ON DELETE CASCADE,
        conversation_id UUID REFERENCES chat_conversations(id) ON DELETE SET NULL,
        from_number TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool', 'human_supervisor')),
        content TEXT NOT NULL,
        content_attributes JSONB DEFAULT '[]',
        platform_metadata JSONB DEFAULT '{}',
        platform_message_id VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        correlation_id TEXT,
        -- 056: delivery status tracking
        delivery_status VARCHAR(20) NOT NULL DEFAULT 'delivered'
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_from_number_created_at ON chat_messages(from_number, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_id ON chat_messages(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id) WHERE conversation_id IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_from_created ON chat_messages(tenant_id, from_number, created_at DESC)")
    # 030: provider message unique index
    op.execute("""CREATE UNIQUE INDEX IF NOT EXISTS uniq_chat_messages_conv_provider_msg_id
        ON chat_messages (conversation_id, (platform_metadata->>'provider_message_id'))
        WHERE platform_metadata->>'provider_message_id' IS NOT NULL
          AND platform_metadata->>'provider_message_id' <> ''""")

    # =====================================================================
    # PATIENT DOCUMENTS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS patient_documents (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        file_name VARCHAR(255) NOT NULL,
        file_path VARCHAR(500) NOT NULL,
        file_size INTEGER,
        mime_type VARCHAR(100),
        document_type VARCHAR(50) DEFAULT 'clinical',
        uploaded_by UUID REFERENCES users(id),
        source VARCHAR(50) DEFAULT 'manual',
        source_details JSONB DEFAULT '{}',
        uploaded_at TIMESTAMPTZ DEFAULT NOW(),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (tenant_id, patient_id, file_name)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_patient_documents_tenant ON patient_documents(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patient_documents_patient ON patient_documents(patient_id)")

    # =====================================================================
    # CHANNEL CONFIGS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS channel_configs (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        provider VARCHAR(50) NOT NULL,
        channel VARCHAR(50),
        config JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (tenant_id, provider, channel)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_channel_configs_tenant ON channel_configs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_channel_configs_provider ON channel_configs(provider)")

    # =====================================================================
    # AUTOMATION RULES (legacy — kept for backward compat, replaced by playbooks)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS automation_rules (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        is_system BOOLEAN DEFAULT FALSE,
        trigger_type TEXT NOT NULL,
        condition_json JSONB DEFAULT '{}',
        message_type TEXT NOT NULL DEFAULT 'free_text',
        free_text_message TEXT,
        ycloud_template_name TEXT,
        ycloud_template_lang TEXT DEFAULT 'es',
        ycloud_template_vars JSONB DEFAULT '{}',
        channels TEXT[] DEFAULT ARRAY['whatsapp'],
        send_hour_min INTEGER DEFAULT 8,
        send_hour_max INTEGER DEFAULT 20,
        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_automation_rules_tenant_active ON automation_rules(tenant_id, is_active, trigger_type)")

    # =====================================================================
    # AUTOMATION LOGS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS automation_logs (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
        automation_rule_id INTEGER REFERENCES automation_rules(id) ON DELETE SET NULL,
        trigger_type VARCHAR(50) NOT NULL,
        target_id VARCHAR(100),
        status VARCHAR(20) DEFAULT 'pending',
        meta JSONB DEFAULT '{}',
        error_details TEXT,
        rule_name TEXT,
        patient_name TEXT,
        phone_number TEXT,
        channel TEXT DEFAULT 'whatsapp',
        message_type TEXT,
        message_preview TEXT,
        template_name TEXT,
        skip_reason TEXT,
        ycloud_message_id TEXT,
        sent_at TIMESTAMPTZ,
        delivered_at TIMESTAMPTZ,
        triggered_at TIMESTAMPTZ DEFAULT NOW(),
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_auto_logs_trigger ON automation_logs(trigger_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_auto_logs_tenant ON automation_logs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_auto_logs_target ON automation_logs(target_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_automation_logs_tenant_date ON automation_logs(tenant_id, triggered_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_automation_logs_rule ON automation_logs(automation_rule_id)")

    # =====================================================================
    # META FORM LEADS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS meta_form_leads (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        form_id VARCHAR(255),
        page_id VARCHAR(255),
        ad_id VARCHAR(255),
        adset_id VARCHAR(255),
        campaign_id VARCHAR(255),
        ad_name TEXT,
        adset_name TEXT,
        campaign_name TEXT,
        page_name TEXT,
        full_name TEXT,
        email VARCHAR(255),
        phone_number VARCHAR(50),
        custom_questions JSONB DEFAULT '{}',
        status VARCHAR(50) DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'consultation_scheduled', 'treatment_planned', 'converted', 'not_interested', 'spam')),
        assigned_to UUID REFERENCES users(id),
        notes TEXT,
        medical_interest TEXT,
        preferred_specialty TEXT,
        insurance_provider TEXT,
        preferred_date DATE,
        preferred_time TIMESTAMPTZ,
        lead_source VARCHAR(100) DEFAULT 'meta_form',
        attribution_data JSONB DEFAULT '{}',
        webhook_payload JSONB DEFAULT '{}',
        converted_to_patient_id INTEGER REFERENCES patients(id),
        converted_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_meta_form_leads_tenant_status ON meta_form_leads(tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meta_form_leads_campaign ON meta_form_leads(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meta_form_leads_ad ON meta_form_leads(ad_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meta_form_leads_created ON meta_form_leads(created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meta_form_leads_assigned ON meta_form_leads(assigned_to)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meta_form_leads_phone ON meta_form_leads(phone_number)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_meta_form_leads_converted ON meta_form_leads(converted_to_patient_id) WHERE converted_to_patient_id IS NOT NULL")

    # =====================================================================
    # LEAD STATUS HISTORY
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS lead_status_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        lead_id UUID NOT NULL REFERENCES meta_form_leads(id) ON DELETE CASCADE,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        old_status VARCHAR(50),
        new_status VARCHAR(50) NOT NULL,
        changed_by UUID REFERENCES users(id),
        change_reason TEXT,
        notes TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_lead_status_history_lead ON lead_status_history(lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lead_status_history_tenant ON lead_status_history(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lead_status_history_created ON lead_status_history(created_at DESC)")

    # =====================================================================
    # LEAD NOTES
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS lead_notes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        lead_id UUID NOT NULL REFERENCES meta_form_leads(id) ON DELETE CASCADE,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        created_by UUID REFERENCES users(id),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_lead_notes_lead ON lead_notes(lead_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lead_notes_tenant ON lead_notes(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_lead_notes_created ON lead_notes(created_at DESC)")

    # =====================================================================
    # PATIENT ATTRIBUTION HISTORY
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS patient_attribution_history (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        attribution_type VARCHAR(20) NOT NULL CHECK (attribution_type IN ('first_touch', 'last_touch', 'conversion')),
        source VARCHAR(50) NOT NULL,
        source_detail VARCHAR(100),
        ad_id VARCHAR(255),
        ad_name TEXT,
        campaign_id VARCHAR(255),
        campaign_name TEXT,
        adset_id VARCHAR(255),
        adset_name TEXT,
        headline TEXT,
        body TEXT,
        lead_id UUID REFERENCES meta_form_leads(id),
        event_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        event_description TEXT
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_patient_attribution_patient_tenant ON patient_attribution_history(patient_id, tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patient_attribution_type ON patient_attribution_history(attribution_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patient_attribution_source ON patient_attribution_history(source)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patient_attribution_ad ON patient_attribution_history(ad_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patient_attribution_campaign ON patient_attribution_history(campaign_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_patient_attribution_timestamp ON patient_attribution_history(event_timestamp DESC)")

    # =====================================================================
    # GOOGLE OAUTH TOKENS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS google_oauth_tokens (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        platform VARCHAR(50) NOT NULL DEFAULT 'ads',
        access_token TEXT NOT NULL,
        refresh_token TEXT,
        expires_at TIMESTAMPTZ NOT NULL,
        scopes TEXT[],
        email VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(tenant_id, platform)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_google_oauth_tokens_tenant ON google_oauth_tokens(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_google_oauth_tokens_expires ON google_oauth_tokens(expires_at)")

    # =====================================================================
    # GOOGLE ADS ACCOUNTS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS google_ads_accounts (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        customer_id VARCHAR(50) NOT NULL,
        descriptive_name VARCHAR(255),
        currency_code VARCHAR(10),
        time_zone VARCHAR(50),
        manager BOOLEAN DEFAULT FALSE,
        test_account BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(tenant_id, customer_id)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_google_ads_accounts_tenant ON google_ads_accounts(tenant_id)")

    # =====================================================================
    # GOOGLE ADS METRICS CACHE
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS google_ads_metrics_cache (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        customer_id VARCHAR(50) NOT NULL,
        campaign_id VARCHAR(50) NOT NULL,
        campaign_name VARCHAR(255),
        date DATE NOT NULL,
        impressions BIGINT DEFAULT 0,
        clicks BIGINT DEFAULT 0,
        cost_micros BIGINT DEFAULT 0,
        conversions DOUBLE PRECISION DEFAULT 0,
        conversions_value DOUBLE PRECISION DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE(tenant_id, customer_id, campaign_id, date)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_google_ads_metrics_cache_tenant_date ON google_ads_metrics_cache(tenant_id, date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_google_ads_metrics_cache_campaign ON google_ads_metrics_cache(campaign_id, date)")

    # =====================================================================
    # DAILY ANALYTICS METRICS (tenant_id is UUID here, not INTEGER)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS daily_analytics_metrics (
        id SERIAL PRIMARY KEY,
        tenant_id UUID NOT NULL,
        metric_date DATE NOT NULL,
        metric_type VARCHAR(50) NOT NULL,
        metric_value JSONB DEFAULT '0',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tenant_id, metric_date, metric_type)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_analytics_tenant_date ON daily_analytics_metrics(tenant_id, metric_date)")

    # =====================================================================
    # CLINIC FAQS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS clinic_faqs (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        category VARCHAR(100) NOT NULL DEFAULT 'General',
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        sort_order INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_clinic_faqs_tenant ON clinic_faqs(tenant_id)")

    # =====================================================================
    # BUSINESS ASSETS (005: Meta Direct support)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS business_assets (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
        asset_type TEXT NOT NULL,
        content JSONB NOT NULL,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_business_assets_tenant ON business_assets(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_business_assets_content_id ON business_assets((content->>'id'))")

    # =====================================================================
    # FAQ EMBEDDINGS (009, fixed in 025)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS faq_embeddings (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        faq_id INTEGER NOT NULL UNIQUE REFERENCES clinic_faqs(id) ON DELETE CASCADE,
        content TEXT NOT NULL,
        embedding BYTEA NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_faq_embeddings_tenant ON faq_embeddings(tenant_id)")
    # pgvector ALTER + ivfflat indexes — created by start.sh after extensions are installed

    # =====================================================================
    # DOCUMENT EMBEDDINGS (009, fixed in 025)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS document_embeddings (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        source_type VARCHAR(50) NOT NULL,
        source_id INTEGER NOT NULL,
        content TEXT NOT NULL,
        embedding BYTEA NOT NULL,
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (source_type, source_id)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_doc_embeddings_tenant ON document_embeddings(tenant_id)")
    # pgvector ALTER + ivfflat indexes — created by start.sh after extensions are installed

    # =====================================================================
    # TENANT HOLIDAYS (010, 014)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS tenant_holidays (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        date DATE NOT NULL,
        name TEXT NOT NULL,
        holiday_type VARCHAR(20) NOT NULL CHECK (holiday_type IN ('closure', 'override_open')),
        is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        -- 014: custom hours
        custom_hours_start TIME,
        custom_hours_end TIME,
        UNIQUE (tenant_id, date, holiday_type)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_tenant_holidays_tenant_date ON tenant_holidays(tenant_id, date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tenant_holidays_recurring ON tenant_holidays(tenant_id, is_recurring) WHERE is_recurring = true")

    # =====================================================================
    # TENANT INSURANCE PROVIDERS (012, 034)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS tenant_insurance_providers (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        provider_name VARCHAR(100) NOT NULL,
        status VARCHAR(20) NOT NULL CHECK (status IN ('accepted', 'restricted', 'external_derivation', 'rejected')),
        external_target TEXT,
        requires_copay BOOLEAN NOT NULL DEFAULT TRUE,
        copay_notes TEXT,
        ai_response_template TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        -- 034: structured coverage (replaces legacy 'restrictions' column)
        coverage_by_treatment JSONB NOT NULL DEFAULT '{}'::jsonb,
        is_prepaid BOOLEAN NOT NULL DEFAULT FALSE,
        employee_discount_percent NUMERIC(5,2),
        default_copay_percent NUMERIC(5,2),
        UNIQUE (tenant_id, provider_name)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_tenant_insurance_providers_tenant ON tenant_insurance_providers(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tenant_insurance_providers_tenant_active ON tenant_insurance_providers(tenant_id, is_active)")

    # =====================================================================
    # PROFESSIONAL DERIVATION RULES (012, 038)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS professional_derivation_rules (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        rule_name VARCHAR(100) NOT NULL,
        patient_condition VARCHAR(30) NOT NULL CHECK (patient_condition IN ('new_patient', 'existing_patient', 'any')),
        treatment_categories TEXT[] NOT NULL DEFAULT '{}',
        target_type VARCHAR(30) NOT NULL CHECK (target_type IN ('specific_professional', 'priority_professional', 'team')),
        target_professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,
        priority_order INTEGER NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        description TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        -- 038: escalation fallback fields
        enable_escalation BOOLEAN NOT NULL DEFAULT FALSE,
        fallback_professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,
        fallback_team_mode BOOLEAN NOT NULL DEFAULT FALSE,
        max_wait_days_before_escalation INTEGER NOT NULL DEFAULT 7,
        escalation_message_template TEXT,
        criteria_custom JSONB
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_professional_derivation_rules_tenant ON professional_derivation_rules(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_professional_derivation_rules_tenant_active ON professional_derivation_rules(tenant_id, is_active)")

    # =====================================================================
    # PATIENT DIGITAL RECORDS (013)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS patient_digital_records (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,
        template_type VARCHAR(50) NOT NULL CHECK (template_type IN ('clinical_report', 'post_surgery', 'odontogram_art', 'authorization_request')),
        title VARCHAR(255) NOT NULL,
        html_content TEXT NOT NULL DEFAULT '',
        pdf_path VARCHAR(500),
        pdf_generated_at TIMESTAMPTZ,
        source_data JSONB NOT NULL DEFAULT '{}',
        generation_metadata JSONB DEFAULT '{}',
        status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'final', 'sent')),
        sent_to_email VARCHAR(255),
        sent_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pdr_tenant_patient ON patient_digital_records(tenant_id, patient_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pdr_tenant ON patient_digital_records(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pdr_status ON patient_digital_records(tenant_id, status)")

    # =====================================================================
    # CLINICAL RECORD SUMMARIES (016)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS clinical_record_summaries (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        conversation_id VARCHAR(100),
        summary_text TEXT NOT NULL,
        attachments_count INTEGER NOT NULL DEFAULT 0,
        attachments_types JSONB NOT NULL DEFAULT '[]',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (tenant_id, patient_id, conversation_id)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_summaries_tenant_patient ON clinical_record_summaries(tenant_id, patient_id)")

    # =====================================================================
    # TREATMENT PLANS (018, 019)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS treatment_plans (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,
        name VARCHAR(200) NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'approved', 'in_progress', 'completed', 'cancelled')),
        estimated_total NUMERIC(12,2) NOT NULL DEFAULT 0,
        approved_total NUMERIC(12,2),
        approved_by VARCHAR(100),
        approved_at TIMESTAMPTZ,
        notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_tp_estimated_total CHECK (estimated_total >= 0),
        CONSTRAINT chk_tp_approved_total CHECK (approved_total IS NULL OR approved_total >= 0),
        CONSTRAINT chk_tp_approved_consistency CHECK (
            (approved_by IS NULL AND approved_at IS NULL) OR
            (approved_by IS NOT NULL AND approved_at IS NOT NULL)
        )
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plans_tenant_patient ON treatment_plans(tenant_id, patient_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plans_tenant_status ON treatment_plans(tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plans_tenant_professional ON treatment_plans(tenant_id, professional_id)")

    # =====================================================================
    # TREATMENT PLAN ITEMS (018, 019)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS treatment_plan_items (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        plan_id UUID NOT NULL REFERENCES treatment_plans(id) ON DELETE CASCADE,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        treatment_type_code VARCHAR(50),
        custom_description TEXT,
        estimated_price NUMERIC(12,2) NOT NULL DEFAULT 0,
        approved_price NUMERIC(12,2),
        status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'cancelled')),
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT chk_tpi_estimated_price CHECK (estimated_price >= 0),
        CONSTRAINT chk_tpi_approved_price CHECK (approved_price IS NULL OR approved_price >= 0)
    )
    """)
    # Index names use _id suffix per 019 rename
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plan_items_plan_id ON treatment_plan_items(plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plan_items_tenant_plan ON treatment_plan_items(tenant_id, plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plan_items_tenant_code ON treatment_plan_items(tenant_id, treatment_type_code)")

    # =====================================================================
    # TREATMENT PLAN PAYMENTS (018, 019, 058)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS treatment_plan_payments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        plan_id UUID NOT NULL REFERENCES treatment_plans(id) ON DELETE CASCADE,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
        payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('cash', 'transfer', 'card', 'insurance')),
        payment_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        recorded_by VARCHAR(100),
        appointment_id UUID,
        receipt_data JSONB,
        notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        -- 018: accounting transaction link
        accounting_transaction_id UUID REFERENCES accounting_transactions(id) ON DELETE SET NULL,
        -- 058: installment link
        installment_id UUID
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plan_payments_plan_id ON treatment_plan_payments(plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plan_payments_tenant_plan ON treatment_plan_payments(tenant_id, plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plan_payments_tenant_date ON treatment_plan_payments(tenant_id, payment_date)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_treatment_plan_payments_appointment ON treatment_plan_payments(appointment_id)")

    # Now add the FK for appointments.plan_item_id (deferred since treatment_plan_items exists now)
    op.execute("""
    DO $$ BEGIN
        ALTER TABLE appointments ADD CONSTRAINT fk_appointments_plan_item_id
            FOREIGN KEY (plan_item_id) REFERENCES treatment_plan_items(id) ON DELETE SET NULL;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$
    """)

    # =====================================================================
    # TREATMENT PLAN INSTALLMENTS (058)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS treatment_plan_installments (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        plan_id UUID NOT NULL REFERENCES treatment_plans(id) ON DELETE CASCADE,
        installment_number INTEGER NOT NULL CHECK (installment_number > 0),
        amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
        due_date DATE NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'paid')),
        paid_at TIMESTAMPTZ,
        payment_id UUID REFERENCES treatment_plan_payments(id) ON DELETE SET NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (plan_id, installment_number)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_installments_tenant_plan ON treatment_plan_installments(tenant_id, plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_installments_status ON treatment_plan_installments(tenant_id, status)")

    # FK: treatment_plan_payments.installment_id -> treatment_plan_installments
    op.execute("""
    DO $$ BEGIN
        ALTER TABLE treatment_plan_payments ADD CONSTRAINT fk_payments_installment_id
            FOREIGN KEY (installment_id) REFERENCES treatment_plan_installments(id) ON DELETE SET NULL;
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$
    """)

    # =====================================================================
    # PROFESSIONAL COMMISSIONS (020)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS professional_commissions (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        professional_id INTEGER NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
        commission_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
        treatment_code VARCHAR(100),
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_prof_comm ON professional_commissions(tenant_id, professional_id, COALESCE(treatment_code, '__default__'))")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prof_comm_tenant_professional ON professional_commissions(tenant_id, professional_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_prof_comm_tenant ON professional_commissions(tenant_id)")

    # =====================================================================
    # LIQUIDATION RECORDS (020)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS liquidation_records (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        professional_id INTEGER NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
        period_start DATE NOT NULL,
        period_end DATE NOT NULL,
        total_billed NUMERIC(12,2) NOT NULL DEFAULT 0,
        total_paid NUMERIC(12,2) NOT NULL DEFAULT 0,
        total_pending NUMERIC(12,2) NOT NULL DEFAULT 0,
        commission_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
        commission_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        payout_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
        status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'generated', 'approved', 'paid')),
        generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        approved_at TIMESTAMPTZ,
        paid_at TIMESTAMPTZ,
        generated_by VARCHAR(255),
        notes JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (tenant_id, professional_id, period_start, period_end)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_liquidation_tenant_status ON liquidation_records(tenant_id, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_liquidation_tenant_professional_period ON liquidation_records(tenant_id, professional_id, period_start, period_end)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_liquidation_tenant_period ON liquidation_records(tenant_id, period_start, period_end)")

    # =====================================================================
    # PROFESSIONAL PAYOUTS (020)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS professional_payouts (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        liquidation_record_id INTEGER NOT NULL REFERENCES liquidation_records(id) ON DELETE CASCADE,
        professional_id INTEGER NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
        amount NUMERIC(12,2) NOT NULL,
        payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('transfer', 'cash', 'check')),
        payment_date DATE NOT NULL,
        reference_number VARCHAR(100),
        notes TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_payout_tenant_liquidation ON professional_payouts(tenant_id, liquidation_record_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payout_tenant_professional ON professional_payouts(tenant_id, professional_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_payout_tenant_payment_date ON professional_payouts(tenant_id, payment_date)")

    # =====================================================================
    # TELEGRAM AUTHORIZED USERS (021)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS telegram_authorized_users (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        telegram_chat_id TEXT NOT NULL,
        display_name VARCHAR(255) NOT NULL,
        user_role VARCHAR(50) NOT NULL DEFAULT 'ceo',
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_telegram_auth_tenant_chatid ON telegram_authorized_users(tenant_id, telegram_chat_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_telegram_auth_active ON telegram_authorized_users(tenant_id, is_active)")

    # =====================================================================
    # NOVA MEMORIES (023)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS nova_memories (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        type VARCHAR(50) NOT NULL DEFAULT 'general',
        title VARCHAR(255) NOT NULL,
        content TEXT NOT NULL,
        topic_key VARCHAR(255),
        created_by VARCHAR(100),
        source_channel VARCHAR(50) NOT NULL DEFAULT 'unknown',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_nova_memories_tenant ON nova_memories(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_nova_memories_type ON nova_memories(tenant_id, type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_nova_memories_topic_key ON nova_memories(tenant_id, topic_key)")

    # =====================================================================
    # APPOINTMENT AUDIT LOG (028)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS appointment_audit_log (
        id BIGSERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
        action VARCHAR(32) NOT NULL CHECK (action IN ('created','rescheduled','cancelled','status_changed','payment_updated')),
        actor_type VARCHAR(16) NOT NULL CHECK (actor_type IN ('ai_agent','staff_user','patient_self','system')),
        actor_id VARCHAR(128),
        before_values JSONB,
        after_values JSONB,
        source_channel VARCHAR(32) CHECK (source_channel IS NULL OR source_channel IN
            ('whatsapp','instagram','facebook','web_admin','nova_voice','api','system')),
        reason TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointment_audit_tenant_apt_time ON appointment_audit_log(tenant_id, appointment_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_appointment_audit_tenant_time ON appointment_audit_log(tenant_id, created_at DESC)")

    # =====================================================================
    # PATIENT CONTEXT SNAPSHOTS (032 — multi-agent)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS patient_context_snapshots (
        id BIGSERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        phone_number TEXT NOT NULL,
        thread_id TEXT NOT NULL,
        state JSONB NOT NULL,
        active_agent TEXT,
        hop_count INTEGER DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (tenant_id, phone_number, thread_id)
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pcs_tenant_phone ON patient_context_snapshots(tenant_id, phone_number)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pcs_thread ON patient_context_snapshots(thread_id)")

    # =====================================================================
    # AGENT TURN LOG (032 — multi-agent audit)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS agent_turn_log (
        id BIGSERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        phone_number TEXT NOT NULL,
        turn_id TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        tools_called JSONB,
        handoff_to TEXT,
        duration_ms INTEGER,
        model TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_atl_tenant_phone ON agent_turn_log(tenant_id, phone_number)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_atl_turn ON agent_turn_log(turn_id)")
    # 055: composite index for per-tenant time-ordered queries
    op.execute("CREATE INDEX IF NOT EXISTS idx_agent_turn_log_tenant_created ON agent_turn_log(tenant_id, created_at DESC)")

    # =====================================================================
    # WHATSAPP MESSAGES (044, widened in 050)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS whatsapp_messages (
        id BIGSERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        external_id VARCHAR(256),
        wamid VARCHAR(256),
        from_number VARCHAR(64) NOT NULL,
        to_number VARCHAR(64) NOT NULL,
        direction VARCHAR(16) NOT NULL CHECK (direction IN ('inbound', 'outbound')),
        message_type VARCHAR(32) NOT NULL,
        content TEXT,
        media_url VARCHAR(1024),
        media_id VARCHAR(256),
        media_mime_type VARCHAR(64),
        media_filename VARCHAR(256),
        status VARCHAR(16) NOT NULL DEFAULT 'synced' CHECK (status IN ('pending', 'syncing', 'synced', 'failed')),
        patient_id INTEGER REFERENCES patients(id),
        conversation_id UUID REFERENCES chat_conversations(id),
        created_at TIMESTAMPTZ NOT NULL,
        synced_at TIMESTAMPTZ DEFAULT NOW(),
        error_message VARCHAR(512)
    )
    """)
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_whatsapp_messages_external_id ON whatsapp_messages(external_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_wamid ON whatsapp_messages(wamid)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_from_number ON whatsapp_messages(from_number)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_tenant_created ON whatsapp_messages(tenant_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_direction ON whatsapp_messages(direction)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_tenant_sync ON whatsapp_messages(tenant_id, synced_at)")
    # 055: patient_id index (missing FK index)
    op.execute("CREATE INDEX IF NOT EXISTS idx_whatsapp_messages_patient_id ON whatsapp_messages(patient_id)")

    # =====================================================================
    # AUTOMATION PLAYBOOKS (047)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS automation_playbooks (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        description TEXT,
        icon TEXT DEFAULT '📋',
        category TEXT NOT NULL DEFAULT 'custom',
        trigger_type TEXT NOT NULL,
        trigger_config JSONB NOT NULL DEFAULT '{}',
        conditions JSONB NOT NULL DEFAULT '{}',
        is_active BOOLEAN NOT NULL DEFAULT FALSE,
        is_system BOOLEAN NOT NULL DEFAULT FALSE,
        max_messages_per_day INTEGER NOT NULL DEFAULT 2,
        frequency_cap_hours INTEGER DEFAULT 24,
        schedule_hour_min INTEGER NOT NULL DEFAULT 9,
        schedule_hour_max INTEGER NOT NULL DEFAULT 20,
        abort_on_booking BOOLEAN NOT NULL DEFAULT TRUE,
        abort_on_human BOOLEAN NOT NULL DEFAULT TRUE,
        abort_on_optout BOOLEAN NOT NULL DEFAULT TRUE,
        stats_cache JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_playbooks_tenant_active ON automation_playbooks(tenant_id, is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_playbooks_trigger ON automation_playbooks(trigger_type)")

    # =====================================================================
    # AUTOMATION STEPS (047)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS automation_steps (
        id SERIAL PRIMARY KEY,
        playbook_id INTEGER NOT NULL REFERENCES automation_playbooks(id) ON DELETE CASCADE,
        step_order INTEGER NOT NULL DEFAULT 0,
        step_label TEXT,
        action_type TEXT NOT NULL,
        delay_minutes INTEGER NOT NULL DEFAULT 0,
        schedule_hour_min INTEGER,
        schedule_hour_max INTEGER,
        template_name TEXT,
        template_lang TEXT DEFAULT 'es',
        template_vars JSONB DEFAULT '{}',
        message_text TEXT,
        instruction_source TEXT DEFAULT 'from_treatment',
        custom_instructions TEXT,
        notify_channel TEXT DEFAULT 'telegram',
        notify_message TEXT,
        update_field TEXT,
        update_value TEXT,
        wait_timeout_minutes INTEGER DEFAULT 120,
        response_rules JSONB DEFAULT '[]',
        on_no_response TEXT DEFAULT 'continue',
        on_unclassified TEXT DEFAULT 'pass_to_ai',
        on_response_next_step INTEGER,
        on_no_response_next_step INTEGER,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_steps_playbook ON automation_steps(playbook_id, step_order)")

    # =====================================================================
    # AUTOMATION EXECUTIONS (047)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS automation_executions (
        id SERIAL PRIMARY KEY,
        playbook_id INTEGER NOT NULL REFERENCES automation_playbooks(id) ON DELETE CASCADE,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
        phone_number TEXT NOT NULL,
        appointment_id TEXT,
        current_step_order INTEGER NOT NULL DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'running',
        pause_reason TEXT,
        started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        next_step_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        messages_sent INTEGER NOT NULL DEFAULT 0,
        messages_sent_today INTEGER NOT NULL DEFAULT 0,
        last_message_at TIMESTAMPTZ,
        last_response_at TIMESTAMPTZ,
        context JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("""CREATE INDEX IF NOT EXISTS idx_executions_pending ON automation_executions(next_step_at)
        WHERE status IN ('running', 'waiting_response')""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_executions_patient ON automation_executions(tenant_id, phone_number, status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_executions_playbook ON automation_executions(playbook_id, status)")

    # =====================================================================
    # AUTOMATION EVENTS (047)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS automation_events (
        id SERIAL PRIMARY KEY,
        execution_id INTEGER NOT NULL REFERENCES automation_executions(id) ON DELETE CASCADE,
        step_id INTEGER REFERENCES automation_steps(id) ON DELETE SET NULL,
        event_type TEXT NOT NULL,
        event_data JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_execution ON automation_events(execution_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON automation_events(event_type)")

    # =====================================================================
    # CLINIC OPERATIONAL RULES (053)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS clinic_operational_rules (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        rule_name VARCHAR(150) NOT NULL,
        rule_type VARCHAR(30) NOT NULL,
        description TEXT,
        prompt_injection TEXT NOT NULL,
        applies_to TEXT[] NOT NULL DEFAULT '{}',
        valid_from TIMESTAMPTZ,
        valid_until TIMESTAMPTZ,
        priority_order INTEGER NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        created_by VARCHAR(100),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_operational_rules_tenant ON clinic_operational_rules(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_operational_rules_tenant_active ON clinic_operational_rules(tenant_id, is_active)")

    # =====================================================================
    # FUNCTION: get_treatment_duration
    # =====================================================================
    op.execute("""
    CREATE OR REPLACE FUNCTION get_treatment_duration(
        p_treatment_code VARCHAR,
        p_tenant_id INTEGER,
        p_urgency_level VARCHAR DEFAULT 'normal'
    ) RETURNS INTEGER AS $$
    DECLARE
        v_duration INTEGER;
        v_min_duration INTEGER;
        v_max_duration INTEGER;
    BEGIN
        SELECT default_duration_minutes, min_duration_minutes, max_duration_minutes
        INTO v_duration, v_min_duration, v_max_duration
        FROM treatment_types
        WHERE code = p_treatment_code
          AND tenant_id = p_tenant_id
          AND is_active = TRUE
          AND is_available_for_booking = TRUE;

        IF v_duration IS NULL THEN
            RETURN 30;
        END IF;

        IF p_urgency_level = 'emergency' THEN
            RETURN LEAST(v_min_duration, v_duration);
        ELSIF p_urgency_level IN ('high', 'normal') THEN
            RETURN v_duration;
        ELSE
            RETURN GREATEST(v_duration, v_max_duration);
        END IF;
    END;
    $$ LANGUAGE plpgsql
    """)

    # =====================================================================
    # VIEW: patient_attribution_complete
    # =====================================================================
    op.execute("""
    CREATE OR REPLACE VIEW patient_attribution_complete AS
    SELECT
        p.id as patient_id,
        p.tenant_id,
        (p.first_name || ' ' || COALESCE(p.last_name, '')) as full_name,
        p.phone_number,
        p.email,
        p.first_touch_source,
        p.first_touch_ad_id,
        p.first_touch_ad_name,
        p.first_touch_campaign_id,
        p.first_touch_campaign_name,
        p.first_touch_adset_id,
        p.first_touch_adset_name,
        p.first_touch_ad_headline,
        p.first_touch_ad_body,
        p.last_touch_source,
        p.last_touch_ad_id,
        p.last_touch_ad_name,
        p.last_touch_campaign_id,
        p.last_touch_campaign_name,
        p.last_touch_timestamp,
        mfl.id as lead_id,
        mfl.ad_id as conversion_ad_id,
        mfl.ad_name as conversion_ad_name,
        mfl.campaign_id as conversion_campaign_id,
        mfl.campaign_name as conversion_campaign_name,
        mfl.converted_at as conversion_timestamp,
        p.created_at as patient_created_at,
        p.updated_at as patient_updated_at
    FROM patients p
    LEFT JOIN meta_form_leads mfl ON p.id = mfl.converted_to_patient_id AND p.tenant_id = mfl.tenant_id
    """)


def downgrade() -> None:
    # Drop in reverse order of creation
    op.execute("DROP VIEW IF EXISTS patient_attribution_complete")
    op.execute("DROP FUNCTION IF EXISTS get_treatment_duration(VARCHAR, INTEGER, VARCHAR)")
    op.execute("DROP TABLE IF EXISTS clinic_operational_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS automation_events CASCADE")
    op.execute("DROP TABLE IF EXISTS automation_executions CASCADE")
    op.execute("DROP TABLE IF EXISTS automation_steps CASCADE")
    op.execute("DROP TABLE IF EXISTS automation_playbooks CASCADE")
    op.execute("DROP TABLE IF EXISTS whatsapp_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS agent_turn_log CASCADE")
    op.execute("DROP TABLE IF EXISTS patient_context_snapshots CASCADE")
    op.execute("DROP TABLE IF EXISTS appointment_audit_log CASCADE")
    op.execute("DROP TABLE IF EXISTS nova_memories CASCADE")
    op.execute("DROP TABLE IF EXISTS telegram_authorized_users CASCADE")
    op.execute("DROP TABLE IF EXISTS professional_payouts CASCADE")
    op.execute("DROP TABLE IF EXISTS liquidation_records CASCADE")
    op.execute("DROP TABLE IF EXISTS professional_commissions CASCADE")
    op.execute("DROP TABLE IF EXISTS treatment_plan_installments CASCADE")
    op.execute("DROP TABLE IF EXISTS treatment_plan_payments CASCADE")
    op.execute("DROP TABLE IF EXISTS treatment_plan_items CASCADE")
    op.execute("DROP TABLE IF EXISTS treatment_plans CASCADE")
    op.execute("DROP TABLE IF EXISTS clinical_record_summaries CASCADE")
    op.execute("DROP TABLE IF EXISTS patient_digital_records CASCADE")
    op.execute("DROP TABLE IF EXISTS professional_derivation_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS tenant_insurance_providers CASCADE")
    op.execute("DROP TABLE IF EXISTS tenant_holidays CASCADE")
    op.execute("DROP TABLE IF EXISTS document_embeddings CASCADE")
    op.execute("DROP TABLE IF EXISTS faq_embeddings CASCADE")
    op.execute("DROP TABLE IF EXISTS business_assets CASCADE")
    op.execute("DROP TABLE IF EXISTS clinic_faqs CASCADE")
    op.execute("DROP TABLE IF EXISTS daily_analytics_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS google_ads_metrics_cache CASCADE")
    op.execute("DROP TABLE IF EXISTS google_ads_accounts CASCADE")
    op.execute("DROP TABLE IF EXISTS google_oauth_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS patient_attribution_history CASCADE")
    op.execute("DROP TABLE IF EXISTS lead_notes CASCADE")
    op.execute("DROP TABLE IF EXISTS lead_status_history CASCADE")
    op.execute("DROP TABLE IF EXISTS meta_form_leads CASCADE")
    op.execute("DROP TABLE IF EXISTS automation_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS automation_rules CASCADE")
    op.execute("DROP TABLE IF EXISTS channel_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS patient_documents CASCADE")
    op.execute("DROP TABLE IF EXISTS chat_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS chat_conversations CASCADE")
    op.execute("DROP TABLE IF EXISTS treatment_type_professionals CASCADE")
    op.execute("DROP TABLE IF EXISTS treatment_images CASCADE")
    op.execute("DROP TABLE IF EXISTS treatment_types CASCADE")
    op.execute("DROP TABLE IF EXISTS calendar_sync_log CASCADE")
    op.execute("DROP TABLE IF EXISTS google_calendar_blocks CASCADE")
    op.execute("DROP TABLE IF EXISTS daily_cash_flow CASCADE")
    op.execute("DROP TABLE IF EXISTS accounting_transactions CASCADE")
    op.execute("DROP TABLE IF EXISTS appointments CASCADE")
    op.execute("DROP TABLE IF EXISTS clinical_records CASCADE")
    op.execute("DROP TABLE IF EXISTS patients CASCADE")
    op.execute("DROP TABLE IF EXISTS professionals CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")
    op.execute("DROP TABLE IF EXISTS system_events CASCADE")
    op.execute("DROP TABLE IF EXISTS credentials CASCADE")
    op.execute("DROP TABLE IF EXISTS inbound_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS tenants CASCADE")
    try:
        op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    except Exception:
        pass
    try:
        op.execute("DROP EXTENSION IF EXISTS vector")
    except Exception:
        pass
