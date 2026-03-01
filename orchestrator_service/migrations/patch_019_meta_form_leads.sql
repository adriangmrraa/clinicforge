-- Migration Patch 019: Meta Form Leads System for ClinicForge
-- Creates tables for Meta Lead Forms management and attribution

BEGIN;

-- ==================== META FORM LEADS TABLE ====================
CREATE TABLE IF NOT EXISTS meta_form_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Meta Ads Attribution Data
    form_id VARCHAR(255),
    page_id VARCHAR(255),
    ad_id VARCHAR(255),
    adset_id VARCHAR(255),
    campaign_id VARCHAR(255),
    
    -- Meta Ads Human-readable Names
    ad_name TEXT,
    adset_name TEXT,
    campaign_name TEXT,
    page_name TEXT,
    
    -- Lead Information from Form
    full_name TEXT,
    email VARCHAR(255),
    phone_number VARCHAR(50),
    custom_questions JSONB DEFAULT '{}',
    
    -- Lead Status and Management
    status VARCHAR(50) DEFAULT 'new' CHECK (status IN ('new', 'contacted', 'consultation_scheduled', 'treatment_planned', 'converted', 'not_interested', 'spam')),
    assigned_to UUID REFERENCES users(id),
    notes TEXT,
    
    -- Medical Context (Clinic-specific)
    medical_interest TEXT,
    preferred_specialty TEXT,
    insurance_provider TEXT,
    preferred_date DATE,
    preferred_time TIME,
    
    -- Attribution Metadata
    lead_source VARCHAR(100) DEFAULT 'meta_form',
    attribution_data JSONB DEFAULT '{}',
    webhook_payload JSONB DEFAULT '{}',
    
    -- Conversion Tracking
    converted_to_patient_id UUID REFERENCES patients(id),
    converted_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for Performance
    CONSTRAINT idx_meta_form_leads_tenant UNIQUE NULLS NOT DISTINCT (tenant_id, id)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_meta_form_leads_tenant_status ON meta_form_leads(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_meta_form_leads_campaign ON meta_form_leads(campaign_id);
CREATE INDEX IF NOT EXISTS idx_meta_form_leads_ad ON meta_form_leads(ad_id);
CREATE INDEX IF NOT EXISTS idx_meta_form_leads_created ON meta_form_leads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_meta_form_leads_assigned ON meta_form_leads(assigned_to);
CREATE INDEX IF NOT EXISTS idx_meta_form_leads_phone ON meta_form_leads(phone_number);
CREATE INDEX IF NOT EXISTS idx_meta_form_leads_converted ON meta_form_leads(converted_to_patient_id) WHERE converted_to_patient_id IS NOT NULL;

-- ==================== LEAD STATUS HISTORY TABLE ====================
CREATE TABLE IF NOT EXISTS lead_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES meta_form_leads(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Status Change
    old_status VARCHAR(50),
    new_status VARCHAR(50) NOT NULL,
    
    -- Change Metadata
    changed_by UUID REFERENCES users(id),
    change_reason TEXT,
    notes TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lead_status_history_lead ON lead_status_history(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_status_history_tenant ON lead_status_history(tenant_id);
CREATE INDEX IF NOT EXISTS idx_lead_status_history_created ON lead_status_history(created_at DESC);

-- ==================== LEAD NOTES TABLE ====================
CREATE TABLE IF NOT EXISTS lead_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID NOT NULL REFERENCES meta_form_leads(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Note Content
    content TEXT NOT NULL,
    created_by UUID REFERENCES users(id),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_lead_notes_lead ON lead_notes(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_notes_tenant ON lead_notes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_lead_notes_created ON lead_notes(created_at DESC);

-- ==================== INSERT DEFAULT STATUSES ====================
INSERT INTO lead_statuses (tenant_id, name, code, description, category, color, icon, is_initial, is_final, sort_order) VALUES
    (1, 'Nuevo', 'new', 'Lead recién recibido del formulario', 'incoming', '#3B82F6', 'circle', true, false, 10),
    (1, 'Contactado', 'contacted', 'Se ha contactado al lead', 'active', '#10B981', 'phone', false, false, 20),
    (1, 'Consulta Agendada', 'consultation_scheduled', 'Se agendó una consulta', 'active', '#8B5CF6', 'calendar', false, false, 30),
    (1, 'Tratamiento Planificado', 'treatment_planned', 'Se planificó un tratamiento', 'active', '#F59E0B', 'clipboard-list', false, false, 40),
    (1, 'Convertido a Paciente', 'converted', 'Lead convertido a paciente activo', 'converted', '#10B981', 'check-circle', false, true, 50),
    (1, 'No Interesado', 'not_interested', 'Lead no está interesado', 'lost', '#EF4444', 'x-circle', false, true, 60),
    (1, 'Spam', 'spam', 'Lead identificado como spam', 'lost', '#6B7280', 'ban', false, true, 70)
ON CONFLICT (tenant_id, code) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    color = EXCLUDED.color,
    icon = EXCLUDED.icon,
    sort_order = EXCLUDED.sort_order;

-- ==================== UPDATE DEPLOYMENT CONFIG FOR WEBHOOK URL ====================
-- Add webhook URL to deployment config for easy access
DO $$
BEGIN
    -- Check if deployment_config table exists
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'deployment_config') THEN
        -- Add webhook_url column if it doesn't exist
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='deployment_config' AND column_name='meta_leads_webhook_url') THEN
            ALTER TABLE deployment_config ADD COLUMN meta_leads_webhook_url TEXT;
        END IF;
        
        -- Update existing configs with webhook URL
        UPDATE deployment_config 
        SET meta_leads_webhook_url = CONCAT(base_url, '/api/webhooks/meta')
        WHERE meta_leads_webhook_url IS NULL;
    END IF;
END $$;

COMMIT;

-- ==================== MIGRATION COMPLETE MESSAGE ====================
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 019: Meta Form Leads System created successfully';
    RAISE NOTICE '   • Created meta_form_leads table with full attribution tracking';
    RAISE NOTICE '   • Created lead_status_history table for audit trail';
    RAISE NOTICE '   • Created lead_notes table for communication tracking';
    RAISE NOTICE '   • Added default lead statuses for clinic workflow';
    RAISE NOTICE '   • Updated deployment_config with webhook URL';
END $$;