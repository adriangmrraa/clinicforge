-- Patch 021: Google Ads Integration for ClinicForge
-- Created: 2026-03-03
-- Description: Adds Google OAuth and Google Ads API integration tables

-- Google OAuth Tokens Table
CREATE TABLE IF NOT EXISTS google_oauth_tokens (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL DEFAULT 'ads',  -- 'ads' or 'login'
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    scopes TEXT[],
    email VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, platform)
);

-- Google Ads Accounts Table
CREATE TABLE IF NOT EXISTS google_ads_accounts (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id VARCHAR(50) NOT NULL,  -- Google Ads Customer ID
    descriptive_name VARCHAR(255),
    currency_code VARCHAR(10),
    time_zone VARCHAR(50),
    manager BOOLEAN DEFAULT FALSE,
    test_account BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, customer_id)
);

-- Google Ads Campaign Metrics Cache
CREATE TABLE IF NOT EXISTS google_ads_metrics_cache (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    customer_id VARCHAR(50) NOT NULL,
    campaign_id VARCHAR(50) NOT NULL,
    campaign_name VARCHAR(255),
    date DATE NOT NULL,
    impressions BIGINT DEFAULT 0,
    clicks BIGINT DEFAULT 0,
    cost_micros BIGINT DEFAULT 0,  -- Micros (divide by 1,000,000 for currency)
    conversions DOUBLE PRECISION DEFAULT 0,
    conversions_value DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(tenant_id, customer_id, campaign_id, date)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_google_oauth_tokens_tenant ON google_oauth_tokens(tenant_id);
CREATE INDEX IF NOT EXISTS idx_google_oauth_tokens_expires ON google_oauth_tokens(expires_at);
CREATE INDEX IF NOT EXISTS idx_google_ads_accounts_tenant ON google_ads_accounts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_google_ads_metrics_cache_tenant_date ON google_ads_metrics_cache(tenant_id, date);
CREATE INDEX IF NOT EXISTS idx_google_ads_metrics_cache_campaign ON google_ads_metrics_cache(campaign_id, date);

-- Add Google credentials to credentials table types
INSERT INTO credentials (tenant_id, name, value, category, updated_at)
SELECT DISTINCT tenant_id, 'GOOGLE_CLIENT_ID', '', 'google', NOW()
FROM tenants
WHERE NOT EXISTS (
    SELECT 1 FROM credentials c 
    WHERE c.tenant_id = tenants.id AND c.name = 'GOOGLE_CLIENT_ID'
)
ON CONFLICT DO NOTHING;

INSERT INTO credentials (tenant_id, name, value, category, updated_at)
SELECT DISTINCT tenant_id, 'GOOGLE_CLIENT_SECRET', '', 'google', NOW()
FROM tenants
WHERE NOT EXISTS (
    SELECT 1 FROM credentials c 
    WHERE c.tenant_id = tenants.id AND c.name = 'GOOGLE_CLIENT_SECRET'
)
ON CONFLICT DO NOTHING;

INSERT INTO credentials (tenant_id, name, value, category, updated_at)
SELECT DISTINCT tenant_id, 'GOOGLE_DEVELOPER_TOKEN', '', 'google', NOW()
FROM tenants
WHERE NOT EXISTS (
    SELECT 1 FROM credentials c 
    WHERE c.tenant_id = tenants.id AND c.name = 'GOOGLE_DEVELOPER_TOKEN'
)
ON CONFLICT DO NOTHING;

INSERT INTO credentials (tenant_id, name, value, category, updated_at)
SELECT DISTINCT tenant_id, 'GOOGLE_REDIRECT_URI', '', 'google', NOW()
FROM tenants
WHERE NOT EXISTS (
    SELECT 1 FROM credentials c 
    WHERE c.tenant_id = tenants.id AND c.name = 'GOOGLE_REDIRECT_URI'
)
ON CONFLICT DO NOTHING;

INSERT INTO credentials (tenant_id, name, value, category, updated_at)
SELECT DISTINCT tenant_id, 'GOOGLE_LOGIN_REDIRECT_URI', '', 'google', NOW()
FROM tenants
WHERE NOT EXISTS (
    SELECT 1 FROM credentials c 
    WHERE c.tenant_id = tenants.id AND c.name = 'GOOGLE_LOGIN_REDIRECT_URI'
)
ON CONFLICT DO NOTHING;

-- Add GOOGLE_ADS_API_VERSION as a global credential (not per-tenant)
INSERT INTO credentials (tenant_id, name, value, category, updated_at)
VALUES (0, 'GOOGLE_ADS_API_VERSION', 'v16', 'google', NOW())
ON CONFLICT (tenant_id, name) DO UPDATE SET 
    value = EXCLUDED.value,
    category = EXCLUDED.category,
    updated_at = EXCLUDED.updated_at;

-- Migration log entry
INSERT INTO migration_log (patch_name, applied_at, success) 
VALUES ('patch_021_google_ads_integration.sql', NOW(), true)
ON CONFLICT DO NOTHING;

COMMENT ON TABLE google_oauth_tokens IS 'Stores Google OAuth 2.0 tokens for Google Ads and Google Login';
COMMENT ON TABLE google_ads_accounts IS 'Google Ads customer accounts accessible to each tenant';
COMMENT ON TABLE google_ads_metrics_cache IS 'Cached Google Ads campaign metrics for performance';