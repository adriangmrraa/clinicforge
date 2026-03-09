#!/usr/bin/env python3
"""
Google OAuth Migration for ClinicForge
Adapted from CRM Ventas implementation
"""
import asyncio
import sys
import os
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import get_pool

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GOOGLE_MIGRATION_SQL = """
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
"""

async def run_migration():
    """Run the Google OAuth migration"""
    try:
        pool = get_pool()
        
        logger.info("🚀 Starting Google OAuth migration for ClinicForge...")
        
        # Execute migration SQL
        await pool.execute(GOOGLE_MIGRATION_SQL)
        
        logger.info("✅ Google OAuth migration completed successfully!")
        logger.info("   - Created google_oauth_tokens table")
        logger.info("   - Created google_ads_accounts table")
        logger.info("   - Created google_ads_metrics_cache table")
        logger.info("   - Added Google credential placeholders")
        
        # Verify migration
        tables = await pool.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'google_%'
        """)
        
        logger.info(f"📊 Google tables created: {[t['table_name'] for t in tables]}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

async def check_status():
    """Check migration status"""
    try:
        pool = get_pool()
        
        logger.info("🔍 Checking Google OAuth migration status...")
        
        # Check tables
        tables = await pool.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('google_oauth_tokens', 'google_ads_accounts', 'google_ads_metrics_cache')
        """)
        
        table_names = [t['table_name'] for t in tables]
        
        if len(table_names) == 3:
            logger.info("✅ All Google tables exist:")
            for table in table_names:
                logger.info(f"   - {table}")
            
            # Check row counts
            for table in table_names:
                count = await pool.fetchval(f"SELECT COUNT(*) FROM {table}")
                logger.info(f"   - {table}: {count} rows")
            
            return True
        else:
            logger.warning(f"⚠️  Missing tables. Found: {table_names}")
            logger.info("Expected: google_oauth_tokens, google_ads_accounts, google_ads_metrics_cache")
            return False
            
    except Exception as e:
        logger.error(f"❌ Status check failed: {e}")
        return False

async def rollback_migration():
    """Rollback the migration (for testing)"""
    try:
        pool = get_pool()
        
        logger.warning("🔄 Rolling back Google OAuth migration...")
        
        # Drop tables in reverse order (due to foreign keys)
        await pool.execute("DROP TABLE IF EXISTS google_ads_metrics_cache CASCADE")
        await pool.execute("DROP TABLE IF EXISTS google_ads_accounts CASCADE")
        await pool.execute("DROP TABLE IF EXISTS google_oauth_tokens CASCADE")
        
        # Remove Google credentials
        await pool.execute("DELETE FROM credentials WHERE name LIKE 'GOOGLE_%'")
        
        logger.info("✅ Rollback completed")
        return True
        
    except Exception as e:
        logger.error(f"❌ Rollback failed: {e}")
        return False

def main():
    """CLI entry point"""
    if len(sys.argv) < 2:
        print("Usage: python run_google_migration.py [run|status|rollback]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "run":
        success = asyncio.run(run_migration())
        sys.exit(0 if success else 1)
    
    elif command == "status":
        success = asyncio.run(check_status())
        sys.exit(0 if success else 1)
    
    elif command == "rollback":
        confirm = input("Are you sure you want to rollback Google migration? (yes/no): ")
        if confirm.lower() == "yes":
            success = asyncio.run(rollback_migration())
            sys.exit(0 if success else 1)
        else:
            print("Rollback cancelled")
            sys.exit(0)
    
    else:
        print(f"Unknown command: {command}")
        print("Usage: python run_google_migration.py [run|status|rollback]")
        sys.exit(1)

if __name__ == "__main__":
    main()