-- [MIGRATION] 007_analytics_metrics.sql
-- Goal: Store aggregated metrics for Dentalogic Analytics Dashboard
-- Partitions data by tenant_id for Sovereign isolation.

CREATE TABLE IF NOT EXISTS daily_analytics_metrics (
    id SERIAL PRIMARY KEY,
    tenant_id UUID NOT NULL,
    metric_date DATE NOT NULL,
    metric_type VARCHAR(50) NOT NULL, -- 'revenue', 'conversion', 'wait_time', 'chair_occupancy'
    metric_value JSONB DEFAULT '0',   -- Store complex values or lists
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(tenant_id, metric_date, metric_type)
);

-- Optimization Index for Dashboard queries
CREATE INDEX IF NOT EXISTS idx_analytics_tenant_date ON daily_analytics_metrics(tenant_id, metric_date);

COMMENT ON TABLE daily_analytics_metrics IS 'Table for storing multi-tenant analytics metrics, optimized for Sovereign dashboards.';
