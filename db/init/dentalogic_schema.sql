-- ==================================================================================
-- DENTALOGIC - SCHEMA UNIFICADO
-- ==================================================================================
-- Sistema de gestión dental con IA para Dentalogic
-- Versión: 1.0 (Unificado 2026-02-05)
-- ==================================================================================

-- ==================== CORE TABLES - MESSAGES & CHAT ====================

-- Table for inbound messages (dedupe/idempotency from WhatsApp)
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
);

CREATE INDEX IF NOT EXISTS idx_inbound_messages_from_number_received_at ON inbound_messages (from_number, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_inbound_messages_status ON inbound_messages (status);

-- Table for chat messages (source-of-truth)
CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGSERIAL PRIMARY KEY,
    from_number TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    correlation_id TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_from_number_created_at ON chat_messages (from_number, created_at DESC);

-- ==================== TENANT & CONFIGURATION ====================

-- Tabla de configuración de la clínica (simplificada - single tenant)
CREATE TABLE IF NOT EXISTS tenants (
    id SERIAL PRIMARY KEY,
    clinic_name TEXT NOT NULL DEFAULT 'Clínica Dental',
    bot_phone_number TEXT UNIQUE NOT NULL,
    owner_email TEXT,
    clinic_location TEXT,
    clinic_website TEXT,
    system_prompt_template TEXT, -- Prompt del agente IA
    
    -- Usage Stats
    total_tokens_used BIGINT DEFAULT 0,
    total_tool_calls BIGINT DEFAULT 0,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Credentials Table (Secrets Management)
CREATE TABLE IF NOT EXISTS credentials (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    value TEXT NOT NULL,
    category TEXT,
    scope TEXT DEFAULT 'global',
    tenant_id INTEGER REFERENCES tenants(id) ON DELETE CASCADE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- System Events (For monitoring and debugging)
CREATE TABLE IF NOT EXISTS system_events (
    id BIGSERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT DEFAULT 'info',
    message TEXT,
    payload JSONB,
    occurred_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert Default Tenant (Dentalogic)
INSERT INTO tenants (
    clinic_name, 
    bot_phone_number, 
    clinic_location
) VALUES (
    'Clínica Dental',
    '5491100000000',
    'Argentina'
) ON CONFLICT (bot_phone_number) DO NOTHING;

-- ==================== TABLA DE USUARIOS (RBAC) ====================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('ceo', 'professional', 'secretary')),
    status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'suspended')),
    professional_id INTEGER NULL, -- Se vincula si el rol es professional
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- ==================== TABLA DE PROFESIONALES ====================

CREATE TABLE IF NOT EXISTS professionals (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL, -- Vínculo a la tabla de usuarios
    
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255),
    phone_number VARCHAR(20),
    specialty VARCHAR(100),
    registration_id VARCHAR(50), -- Matrícula
    
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);


CREATE INDEX IF NOT EXISTS idx_professionals_tenant ON professionals(tenant_id);
CREATE INDEX IF NOT EXISTS idx_professionals_active ON professionals(is_active);
CREATE INDEX IF NOT EXISTS idx_professionals_user_id ON professionals(user_id);

-- ==================== TABLA DE PACIENTES ====================

CREATE TABLE IF NOT EXISTS patients (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Identidad del Paciente
    phone_number VARCHAR(20) NOT NULL,
    dni VARCHAR(15),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100),
    birth_date DATE,
    gender VARCHAR(10),
    
    -- Obra Social (Insurance)
    insurance_provider VARCHAR(100),
    insurance_id VARCHAR(50),
    insurance_valid_until DATE,
    
    -- Anamnesis (JSONB: Historial Médico)
    medical_history JSONB DEFAULT '{}',
    
    -- Datos de Contacto
    email VARCHAR(255),
    alternative_phone VARCHAR(20),
    
    -- Estado del Paciente
    status VARCHAR(20) DEFAULT 'active',
    preferred_schedule VARCHAR(50),
    notes TEXT,
    
    -- Human Handoff Support (Chat Management)
    human_handoff_requested BOOLEAN DEFAULT FALSE,
    human_override_until TIMESTAMPTZ DEFAULT NULL,
    last_derivhumano_at TIMESTAMPTZ DEFAULT NULL,
    
    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_visit TIMESTAMPTZ,
    
    -- Constraints
    UNIQUE (tenant_id, phone_number),
    UNIQUE (tenant_id, dni)
);

CREATE INDEX IF NOT EXISTS idx_patients_tenant_phone ON patients(tenant_id, phone_number);
CREATE INDEX IF NOT EXISTS idx_patients_tenant_dni ON patients(tenant_id, dni);
CREATE INDEX IF NOT EXISTS idx_patients_status ON patients(status);
CREATE INDEX IF NOT EXISTS idx_patients_insurance ON patients(insurance_provider);
CREATE INDEX IF NOT EXISTS idx_patients_handoff ON patients(human_handoff_requested) WHERE human_handoff_requested = TRUE;

COMMENT ON COLUMN patients.human_handoff_requested IS 'Indica si el paciente solicitó hablar con un humano (derivhumano activado)';
COMMENT ON COLUMN patients.human_override_until IS 'Timestamp hasta el cual la IA debe permanecer silenciada (24hs por defecto)';
COMMENT ON COLUMN patients.last_derivhumano_at IS 'Timestamp de la última vez que se activó derivhumano para este paciente';

-- ==================== TABLA DE HISTORIAS CLÍNICAS ====================

CREATE TABLE IF NOT EXISTS clinical_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    
    -- Metadata del Registro
    record_date DATE NOT NULL DEFAULT CURRENT_DATE,
    professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,
    
    -- Odontograma (JSONB: Representación gráfica de dientes)
    odontogram JSONB DEFAULT '{}',
    
    -- Diagnósticos Principales
    diagnosis TEXT,
    
    -- Tratamientos Realizados
    treatments JSONB DEFAULT '[]',
    
    -- Radiografías & Documentación
    radiographs JSONB DEFAULT '[]',
    
    -- Plan de Tratamiento Futuro
    treatment_plan JSONB DEFAULT '{}',
    
    -- Observaciones Clínicas
    clinical_notes TEXT,
    recommendations TEXT,
    
    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_clinical_records_patient ON clinical_records(patient_id);
CREATE INDEX IF NOT EXISTS idx_clinical_records_tenant ON clinical_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_clinical_records_date ON clinical_records(record_date DESC);
CREATE INDEX IF NOT EXISTS idx_clinical_records_professional ON clinical_records(professional_id);

-- ==================== TABLA DE TURNOS / CITAS ====================

CREATE TABLE IF NOT EXISTS appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    
    -- Datos del Turno
    appointment_datetime TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER DEFAULT 60,
    
    -- Asignación de Recursos
    chair_id INTEGER,
    professional_id INTEGER REFERENCES professionals(id) ON DELETE SET NULL,
    
    -- Tipo de Cita
    appointment_type VARCHAR(50) NOT NULL,
    notes TEXT,
    
    -- Sincronización con Google Calendar
    google_calendar_event_id VARCHAR(255),
    google_calendar_sync_status VARCHAR(20) DEFAULT 'pending',
    
    -- Urgencia (detectada por AI triage)
    urgency_level VARCHAR(20) DEFAULT 'normal',
    urgency_reason TEXT,
    
    -- Estado del Turno
    status VARCHAR(20) DEFAULT 'scheduled',
    cancellation_reason TEXT,
    cancellation_by VARCHAR(50),
    
    -- Source: AI vs Manual booking
    source VARCHAR(20) DEFAULT 'ai',
    
    -- Recordatorio
    reminder_sent BOOLEAN DEFAULT FALSE,
    reminder_sent_at TIMESTAMPTZ,
    
    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_tenant ON appointments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_appointments_datetime ON appointments(appointment_datetime);
CREATE INDEX IF NOT EXISTS idx_appointments_chair ON appointments(chair_id);
CREATE INDEX IF NOT EXISTS idx_appointments_professional ON appointments(professional_id);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON appointments(status);
CREATE INDEX IF NOT EXISTS idx_appointments_urgency ON appointments(urgency_level);
CREATE INDEX IF NOT EXISTS idx_appointments_google_sync ON appointments(google_calendar_sync_status);
CREATE INDEX IF NOT EXISTS idx_appointments_source ON appointments(source);

-- ==================== TABLA DE TRANSACCIONES CONTABLES ====================

CREATE TABLE IF NOT EXISTS accounting_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
    appointment_id UUID REFERENCES appointments(id) ON DELETE SET NULL,
    
    -- Tipo de Transacción
    transaction_type VARCHAR(50) NOT NULL,
    transaction_date DATE NOT NULL DEFAULT CURRENT_DATE,
    
    -- Monto
    amount NUMERIC(12, 2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'ARS',
    
    -- Detalles del Pago
    payment_method VARCHAR(50),
    description TEXT,
    
    -- Obra Social / Insurance
    insurance_claim_id VARCHAR(100),
    insurance_covered_amount NUMERIC(12, 2) DEFAULT 0,
    patient_paid_amount NUMERIC(12, 2) DEFAULT 0,
    
    -- Estado
    status VARCHAR(20) DEFAULT 'completed',
    
    -- Auditoría
    recorded_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_accounting_tenant ON accounting_transactions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_accounting_patient ON accounting_transactions(patient_id);
CREATE INDEX IF NOT EXISTS idx_accounting_date ON accounting_transactions(transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_accounting_type ON accounting_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS idx_accounting_status ON accounting_transactions(status);

-- ==================== TABLA DE CAJA DIARIA ====================

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

CREATE INDEX IF NOT EXISTS idx_daily_cash_flow_tenant ON daily_cash_flow(tenant_id);
CREATE INDEX IF NOT EXISTS idx_daily_cash_flow_date ON daily_cash_flow(cash_date);

-- ==================== GOOGLE CALENDAR INTEGRATION ====================

CREATE TABLE IF NOT EXISTS google_calendar_blocks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Identificación del evento en GCalendar
    google_event_id VARCHAR(255) UNIQUE NOT NULL,
    
    -- Datos del bloqueo
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_datetime TIMESTAMPTZ NOT NULL,
    end_datetime TIMESTAMPTZ NOT NULL,
    all_day BOOLEAN DEFAULT FALSE,
    
    -- Recursos afectados (opcional)
    professional_id INTEGER REFERENCES professionals(id) ON DELETE CASCADE,
    
    -- Estado de sync
    sync_status VARCHAR(20) DEFAULT 'synced',
    last_sync_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_gcalendar_blocks_tenant ON google_calendar_blocks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_gcalendar_blocks_datetime ON google_calendar_blocks(start_datetime, end_datetime);
CREATE INDEX IF NOT EXISTS idx_gcalendar_blocks_professional ON google_calendar_blocks(professional_id);
CREATE INDEX IF NOT EXISTS idx_gcalendar_blocks_sync_status ON google_calendar_blocks(sync_status);

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
);

CREATE INDEX IF NOT EXISTS idx_calendar_sync_log_tenant ON calendar_sync_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_calendar_sync_log_date ON calendar_sync_log(started_at DESC);

-- ==================== CONFIGURACIÓN DE TRATAMIENTOS ====================

CREATE TABLE IF NOT EXISTS treatment_types (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Identificación del tratamiento
    code VARCHAR(50) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    
    -- Configuración de duración
    default_duration_minutes INTEGER NOT NULL DEFAULT 30,
    min_duration_minutes INTEGER NOT NULL DEFAULT 15,
    max_duration_minutes INTEGER NOT NULL DEFAULT 120,
    
    -- Complejidad del tratamiento
    complexity_level VARCHAR(20) DEFAULT 'medium',
    
    -- Categoría
    category VARCHAR(50),
    
    -- Configuración de agendamiento
    requires_multiple_sessions BOOLEAN DEFAULT FALSE,
    session_gap_days INTEGER DEFAULT 0,
    
    -- Estado
    is_active BOOLEAN DEFAULT TRUE,
    is_available_for_booking BOOLEAN DEFAULT TRUE,
    
    -- Notas internas
    internal_notes TEXT,
    
    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_treatment_types_tenant ON treatment_types(tenant_id);
CREATE INDEX IF NOT EXISTS idx_treatment_types_code ON treatment_types(code);
CREATE INDEX IF NOT EXISTS idx_treatment_types_category ON treatment_types(category);
CREATE INDEX IF NOT EXISTS idx_treatment_types_active ON treatment_types(is_active, is_available_for_booking);
CREATE UNIQUE INDEX IF NOT EXISTS idx_treatment_types_tenant_code ON treatment_types(tenant_id, code);

-- ==================== DATOS POR DEFECTO: TRATAMIENTOS DENTALES ====================

INSERT INTO treatment_types (
    tenant_id, code, name, description, default_duration_minutes, 
    min_duration_minutes, max_duration_minutes, complexity_level, category,
    requires_multiple_sessions, is_active, is_available_for_booking
)
SELECT 
    t.id, 'checkup', 'Control/Checkup', 'Revisión general y evaluación de salud bucodental',
    20, 15, 30, 'low', 'prevention', FALSE, TRUE, TRUE
FROM tenants t
WHERE NOT EXISTS (SELECT 1 FROM treatment_types tt WHERE tt.tenant_id = t.id AND tt.code = 'checkup');

INSERT INTO treatment_types (tenant_id, code, name, description, default_duration_minutes, min_duration_minutes, max_duration_minutes, complexity_level, category, requires_multiple_sessions, is_active, is_available_for_booking)
SELECT t.id, 'cleaning', 'Limpieza Dental', 'Profilaxis y limpieza profesional', 30, 20, 45, 'low', 'prevention', FALSE, TRUE, TRUE
FROM tenants t WHERE NOT EXISTS (SELECT 1 FROM treatment_types tt WHERE tt.tenant_id = t.id AND tt.code = 'cleaning');

INSERT INTO treatment_types (tenant_id, code, name, description, default_duration_minutes, min_duration_minutes, max_duration_minutes, complexity_level, category, requires_multiple_sessions, is_active, is_available_for_booking)
SELECT t.id, 'emergency', 'Consulta Urgente', 'Atención de urgencia odontológica', 15, 10, 30, 'emergency', 'emergency', FALSE, TRUE, TRUE
FROM tenants t WHERE NOT EXISTS (SELECT 1 FROM treatment_types tt WHERE tt.tenant_id = t.id AND tt.code = 'emergency');

INSERT INTO treatment_types (tenant_id, code, name, description, default_duration_minutes, min_duration_minutes, max_duration_minutes, complexity_level, category, requires_multiple_sessions, is_active, is_available_for_booking)
SELECT t.id, 'extraction', 'Extracción Dental', 'Extracción simple o quirúrgica de pieza dental', 30, 20, 60, 'medium', 'surgical', FALSE, TRUE, TRUE
FROM tenants t WHERE NOT EXISTS (SELECT 1 FROM treatment_types tt WHERE tt.tenant_id = t.id AND tt.code = 'extraction');

INSERT INTO treatment_types (tenant_id, code, name, description, default_duration_minutes, min_duration_minutes, max_duration_minutes, complexity_level, category, requires_multiple_sessions, is_active, is_available_for_booking)
SELECT t.id, 'root_canal', 'Endodoncia', 'Tratamiento de conducto', 60, 45, 90, 'high', 'restorative', FALSE, TRUE, TRUE
FROM tenants t WHERE NOT EXISTS (SELECT 1 FROM treatment_types tt WHERE tt.tenant_id = t.id AND tt.code = 'root_canal');

INSERT INTO treatment_types (tenant_id, code, name, description, default_duration_minutes, min_duration_minutes, max_duration_minutes, complexity_level, category, requires_multiple_sessions, is_active, is_available_for_booking)
SELECT t.id, 'restoration', 'Restauración/Obturación', 'Empastes y reconstrucciones', 30, 20, 45, 'medium', 'restorative', FALSE, TRUE, TRUE
FROM tenants t WHERE NOT EXISTS (SELECT 1 FROM treatment_types tt WHERE tt.tenant_id = t.id AND tt.code = 'restoration');

INSERT INTO treatment_types (tenant_id, code, name, description, default_duration_minutes, min_duration_minutes, max_duration_minutes, complexity_level, category, requires_multiple_sessions, session_gap_days, is_active, is_available_for_booking)
SELECT t.id, 'orthodontics', 'Ortodoncia', 'Colocación de aparato de ortodoncia', 45, 30, 60, 'high', 'orthodontics', TRUE, 7, TRUE, TRUE
FROM tenants t WHERE NOT EXISTS (SELECT 1 FROM treatment_types tt WHERE tt.tenant_id = t.id AND tt.code = 'orthodontics');

INSERT INTO treatment_types (tenant_id, code, name, description, default_duration_minutes, min_duration_minutes, max_duration_minutes, complexity_level, category, requires_multiple_sessions, is_active, is_available_for_booking)
SELECT t.id, 'consultation', 'Consulta General', 'Primera consulta o evaluación', 30, 15, 45, 'low', 'prevention', FALSE, TRUE, TRUE
FROM tenants t WHERE NOT EXISTS (SELECT 1 FROM treatment_types tt WHERE tt.tenant_id = t.id AND tt.code = 'consultation');

-- ==================== FUNCIÓN PARA OBTENER DURACIÓN ====================

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
$$ LANGUAGE plpgsql;
