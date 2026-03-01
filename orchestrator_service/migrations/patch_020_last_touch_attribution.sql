-- Migration Patch 020: Last-Touch Attribution System for ClinicForge
-- Adds last-touch tracking and attribution history for complete ROI metrics

BEGIN;

-- ==================== ADD LAST-TOUCH FIELDS TO PATIENTS ====================
-- Add last-touch attribution fields to patients table
DO $$
BEGIN
    -- Last-touch attribution (most recent Meta Ads interaction)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='last_touch_source') THEN
        ALTER TABLE patients ADD COLUMN last_touch_source VARCHAR(50);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='last_touch_ad_id') THEN
        ALTER TABLE patients ADD COLUMN last_touch_ad_id VARCHAR(255);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='last_touch_campaign_id') THEN
        ALTER TABLE patients ADD COLUMN last_touch_campaign_id VARCHAR(255);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='last_touch_ad_name') THEN
        ALTER TABLE patients ADD COLUMN last_touch_ad_name TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='last_touch_campaign_name') THEN
        ALTER TABLE patients ADD COLUMN last_touch_campaign_name TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='last_touch_timestamp') THEN
        ALTER TABLE patients ADD COLUMN last_touch_timestamp TIMESTAMP;
    END IF;
    
    -- Rename existing fields to be clear they're first-touch
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='acquisition_source') THEN
        ALTER TABLE patients RENAME COLUMN acquisition_source TO first_touch_source;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_ad_id') THEN
        ALTER TABLE patients RENAME COLUMN meta_ad_id TO first_touch_ad_id;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_campaign_id') THEN
        ALTER TABLE patients RENAME COLUMN meta_campaign_id TO first_touch_campaign_id;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_ad_name') THEN
        ALTER TABLE patients RENAME COLUMN meta_ad_name TO first_touch_ad_name;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_campaign_name') THEN
        ALTER TABLE patients RENAME COLUMN meta_campaign_name TO first_touch_campaign_name;
    END IF;
    
    -- Add other first-touch fields for consistency
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_ad_headline') THEN
        ALTER TABLE patients RENAME COLUMN meta_ad_headline TO first_touch_ad_headline;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_ad_body') THEN
        ALTER TABLE patients RENAME COLUMN meta_ad_body TO first_touch_ad_body;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_adset_id') THEN
        ALTER TABLE patients RENAME COLUMN meta_adset_id TO first_touch_adset_id;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_adset_name') THEN
        ALTER TABLE patients RENAME COLUMN meta_adset_name TO first_touch_adset_name;
    END IF;
END $$;

-- ==================== PATIENT ATTRIBUTION HISTORY TABLE ====================
-- Create table to track all attribution events (both first and last touch)
CREATE TABLE IF NOT EXISTS patient_attribution_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Attribution Type
    attribution_type VARCHAR(20) NOT NULL CHECK (attribution_type IN ('first_touch', 'last_touch', 'conversion')),
    
    -- Source Information
    source VARCHAR(50) NOT NULL,
    source_detail VARCHAR(100),
    
    -- Meta Ads Attribution (if applicable)
    ad_id VARCHAR(255),
    ad_name TEXT,
    campaign_id VARCHAR(255),
    campaign_name TEXT,
    adset_id VARCHAR(255),
    adset_name TEXT,
    headline TEXT,
    body TEXT,
    
    -- Lead Form Attribution (if applicable)
    lead_id UUID REFERENCES meta_form_leads(id),
    
    -- Event Metadata
    event_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    event_description TEXT,
    
    -- Indexes
    CONSTRAINT idx_patient_attribution_patient UNIQUE NULLS NOT DISTINCT (patient_id, id)
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_patient_attribution_patient_tenant ON patient_attribution_history(patient_id, tenant_id);
CREATE INDEX IF NOT EXISTS idx_patient_attribution_type ON patient_attribution_history(attribution_type);
CREATE INDEX IF NOT EXISTS idx_patient_attribution_source ON patient_attribution_history(source);
CREATE INDEX IF NOT EXISTS idx_patient_attribution_ad ON patient_attribution_history(ad_id);
CREATE INDEX IF NOT EXISTS idx_patient_attribution_campaign ON patient_attribution_history(campaign_id);
CREATE INDEX IF NOT EXISTS idx_patient_attribution_timestamp ON patient_attribution_history(event_timestamp DESC);

-- ==================== UPDATE EXISTING DATA ====================
-- Migrate existing first-touch data to attribution history
DO $$
BEGIN
    -- Insert existing first-touch data into history
    INSERT INTO patient_attribution_history (
        patient_id, tenant_id, attribution_type, source,
        ad_id, ad_name, campaign_id, campaign_name,
        adset_id, adset_name, headline, body,
        event_timestamp, event_description
    )
    SELECT 
        p.id, p.tenant_id, 'first_touch',
        COALESCE(p.first_touch_source, 'ORGANIC'),
        p.first_touch_ad_id, p.first_touch_ad_name,
        p.first_touch_campaign_id, p.first_touch_campaign_name,
        p.first_touch_adset_id, p.first_touch_adset_name,
        p.first_touch_ad_headline, p.first_touch_ad_body,
        p.created_at, 'Migrated from existing first-touch attribution'
    FROM patients p
    WHERE p.first_touch_ad_id IS NOT NULL OR p.first_touch_source IS NOT NULL;
    
    RAISE NOTICE '✅ Migrated % existing first-touch attributions to history', (SELECT COUNT(*) FROM patient_attribution_history);
END $$;

-- ==================== CREATE ATTRIBUTION VIEW FOR METRICS ====================
-- View that combines first and last touch for easy querying
CREATE OR REPLACE VIEW patient_attribution_complete AS
SELECT 
    p.id as patient_id,
    p.tenant_id,
    p.full_name,
    p.phone_number,
    p.email,
    
    -- First Touch Attribution
    p.first_touch_source,
    p.first_touch_ad_id,
    p.first_touch_ad_name,
    p.first_touch_campaign_id,
    p.first_touch_campaign_name,
    p.first_touch_adset_id,
    p.first_touch_adset_name,
    p.first_touch_ad_headline,
    p.first_touch_ad_body,
    
    -- Last Touch Attribution
    p.last_touch_source,
    p.last_touch_ad_id,
    p.last_touch_ad_name,
    p.last_touch_campaign_id,
    p.last_touch_campaign_name,
    p.last_touch_timestamp,
    
    -- Conversion Attribution (from leads forms)
    mfl.id as lead_id,
    mfl.ad_id as conversion_ad_id,
    mfl.ad_name as conversion_ad_name,
    mfl.campaign_id as conversion_campaign_id,
    mfl.campaign_name as conversion_campaign_name,
    mfl.converted_at as conversion_timestamp,
    
    -- Timestamps
    p.created_at as patient_created_at,
    p.updated_at as patient_updated_at
    
FROM patients p
LEFT JOIN meta_form_leads mfl ON p.id = mfl.converted_to_patient_id AND p.tenant_id = mfl.tenant_id;

-- ==================== MIGRATION COMPLETE MESSAGE ====================
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 020: Last-Touch Attribution System created successfully';
    RAISE NOTICE '   • Added last-touch fields to patients table';
    RAISE NOTICE '   • Renamed first-touch fields for clarity';
    RAISE NOTICE '   • Created patient_attribution_history table for complete audit trail';
    RAISE NOTICE '   • Created patient_attribution_complete view for unified metrics';
    RAISE NOTICE '   • Migrated existing first-touch data to history';
END $$;

COMMIT;