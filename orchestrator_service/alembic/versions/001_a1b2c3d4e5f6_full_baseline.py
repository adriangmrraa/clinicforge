"""Full baseline - complete ClinicForge schema

Revision ID: a1b2c3d4e5f6
Revises: None
Create Date: 2026-03-17

This migration represents the complete production schema.
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
        total_tokens_used BIGINT DEFAULT 0,
        total_tool_calls BIGINT DEFAULT 0,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)

    # Default tenant
    op.execute("""
    INSERT INTO tenants (clinic_name, bot_phone_number, clinic_location)
    VALUES ('Clinica Dental', '5491100000000', 'Argentina')
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
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_professionals_tenant ON professionals(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_professionals_active ON professionals(is_active)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_professionals_user_id ON professionals(user_id)")

    # =====================================================================
    # PATIENTS (full attribution)
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
        completed_at TIMESTAMPTZ
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
    # TREATMENT TYPES
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
        updated_at TIMESTAMPTZ DEFAULT NOW()
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
    # CHAT CONVERSATIONS
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
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conv_tenant ON chat_conversations(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conv_tenant_channel ON chat_conversations(tenant_id, channel)")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chat_conv_tenant_channel_user ON chat_conversations(tenant_id, channel, external_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_conv_last_derivhumano ON chat_conversations(last_derivhumano_at)")

    # =====================================================================
    # CHAT MESSAGES (depends on chat_conversations)
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS chat_messages (
        id BIGSERIAL PRIMARY KEY,
        tenant_id INTEGER DEFAULT 1 REFERENCES tenants(id) ON DELETE CASCADE,
        conversation_id UUID REFERENCES chat_conversations(id) ON DELETE SET NULL,
        from_number TEXT NOT NULL,
        role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
        content TEXT NOT NULL,
        content_attributes JSONB DEFAULT '[]',
        platform_metadata JSONB DEFAULT '{}',
        platform_message_id VARCHAR(255),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        correlation_id TEXT
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_from_number_created_at ON chat_messages(from_number, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_id ON chat_messages(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id) WHERE conversation_id IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_tenant_from_created ON chat_messages(tenant_id, from_number, created_at DESC)")

    # =====================================================================
    # PATIENT DOCUMENTS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS patient_documents (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
        filename VARCHAR(255) NOT NULL,
        file_path VARCHAR(500) NOT NULL,
        file_size INTEGER,
        mime_type VARCHAR(100),
        document_type VARCHAR(50) DEFAULT 'clinical',
        uploaded_by UUID REFERENCES users(id),
        created_at TIMESTAMPTZ DEFAULT NOW(),
        UNIQUE (tenant_id, patient_id, filename)
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
    # AUTOMATION LOGS
    # =====================================================================
    op.execute("""
    CREATE TABLE IF NOT EXISTS automation_logs (
        id SERIAL PRIMARY KEY,
        tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
        patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
        trigger_type VARCHAR(50) NOT NULL,
        target_id VARCHAR(100),
        status VARCHAR(20) DEFAULT 'pending',
        meta JSONB DEFAULT '{}',
        error_details TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_auto_logs_trigger ON automation_logs(trigger_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_auto_logs_tenant ON automation_logs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_auto_logs_target ON automation_logs(target_id)")

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
    op.execute("DROP TABLE IF EXISTS daily_analytics_metrics CASCADE")
    op.execute("DROP TABLE IF EXISTS google_ads_metrics_cache CASCADE")
    op.execute("DROP TABLE IF EXISTS google_ads_accounts CASCADE")
    op.execute("DROP TABLE IF EXISTS google_oauth_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS patient_attribution_history CASCADE")
    op.execute("DROP TABLE IF EXISTS lead_notes CASCADE")
    op.execute("DROP TABLE IF EXISTS lead_status_history CASCADE")
    op.execute("DROP TABLE IF EXISTS meta_form_leads CASCADE")
    op.execute("DROP TABLE IF EXISTS automation_logs CASCADE")
    op.execute("DROP TABLE IF EXISTS channel_configs CASCADE")
    op.execute("DROP TABLE IF EXISTS patient_documents CASCADE")
    op.execute("DROP TABLE IF EXISTS chat_messages CASCADE")
    op.execute("DROP TABLE IF EXISTS chat_conversations CASCADE")
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
