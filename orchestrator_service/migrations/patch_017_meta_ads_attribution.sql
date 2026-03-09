-- Migration Patch 017: Extend Meta Ads Attribution for ClinicForge
-- Adds additional Meta Ads attribution columns to patients table
-- Enables complete attribution tracking similar to CRM Ventas

BEGIN;

-- Add extended Meta Ads attribution columns to patients table
DO $$ 
BEGIN 
    -- 1. meta_adset_id - For adset-level tracking
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_adset_id') THEN
        ALTER TABLE patients ADD COLUMN meta_adset_id VARCHAR(255);
    END IF;

    -- 2. meta_campaign_name - Human-readable campaign name
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_campaign_name') THEN
        ALTER TABLE patients ADD COLUMN meta_campaign_name TEXT;
    END IF;

    -- 3. meta_adset_name - Human-readable adset name
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_adset_name') THEN
        ALTER TABLE patients ADD COLUMN meta_adset_name TEXT;
    END IF;

    -- 4. meta_ad_name - Human-readable ad name
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_ad_name') THEN
        ALTER TABLE patients ADD COLUMN meta_ad_name TEXT;
    END IF;

    -- 5. Ensure existing columns exist (backward compatibility)
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='acquisition_source') THEN
        ALTER TABLE patients ADD COLUMN acquisition_source VARCHAR(50) DEFAULT 'ORGANIC';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_ad_id') THEN
        ALTER TABLE patients ADD COLUMN meta_ad_id VARCHAR(255);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_ad_headline') THEN
        ALTER TABLE patients ADD COLUMN meta_ad_headline TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_ad_body') THEN
        ALTER TABLE patients ADD COLUMN meta_ad_body TEXT;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='patients' AND column_name='meta_campaign_id') THEN
        ALTER TABLE patients ADD COLUMN meta_campaign_id VARCHAR(255);
    END IF;
END $$;

-- Create indexes for faster attribution queries
CREATE INDEX IF NOT EXISTS idx_patients_acquisition_source ON patients(acquisition_source);
CREATE INDEX IF NOT EXISTS idx_patients_meta_ad_id ON patients(meta_ad_id);
CREATE INDEX IF NOT EXISTS idx_patients_meta_campaign_id ON patients(meta_campaign_id);
CREATE INDEX IF NOT EXISTS idx_patients_meta_adset_id ON patients(meta_adset_id);

-- Add comment explaining the attribution system
COMMENT ON COLUMN patients.acquisition_source IS 'Source of patient acquisition: ORGANIC, META_ADS, REFERRAL, etc.';
COMMENT ON COLUMN patients.meta_ad_id IS 'Meta Ads Ad ID from referral/webhook';
COMMENT ON COLUMN patients.meta_ad_name IS 'Human-readable ad name from Meta API';
COMMENT ON COLUMN patients.meta_ad_headline IS 'Ad headline from referral object';
COMMENT ON COLUMN patients.meta_ad_body IS 'Ad body text from referral object';
COMMENT ON COLUMN patients.meta_adset_id IS 'Meta Ads Adset ID for granular tracking';
COMMENT ON COLUMN patients.meta_adset_name IS 'Human-readable adset name from Meta API';
COMMENT ON COLUMN patients.meta_campaign_id IS 'Meta Ads Campaign ID';
COMMENT ON COLUMN patients.meta_campaign_name IS 'Human-readable campaign name from Meta API';

COMMIT;

-- Migration verification
DO $$
BEGIN
    RAISE NOTICE '✅ Migration 017 applied successfully: Extended Meta Ads attribution columns';
    RAISE NOTICE '   - Added: meta_adset_id, meta_campaign_name, meta_adset_name, meta_ad_name';
    RAISE NOTICE '   - Ensured: acquisition_source, meta_ad_id, meta_ad_headline, meta_ad_body, meta_campaign_id';
    RAISE NOTICE '   - Created indexes for faster attribution queries';
END $$;