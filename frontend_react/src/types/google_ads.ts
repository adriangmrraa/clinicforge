export interface GoogleCampaign {
  id: string;
  name: string;
  status: 'ENABLED' | 'PAUSED' | 'REMOVED' | 'ARCHIVED';
  type: 'SEARCH' | 'DISPLAY' | 'VIDEO' | 'SHOPPING' | 'PERFORMANCE_MAX' | string;
  budget: number; // Micros
  impressions: number;
  clicks: number;
  cost: number; // Micros
  conversions: number;
  conversions_value: number; // Micros
  ctr: number;
  cpc: number; // Micros
  conversion_rate: number;
  roas: number;
  start_date: string;
  end_date: string | null;
  currency_code: string;
}

export interface GoogleMetrics {
  impressions: number;
  clicks: number;
  cost: number; // Already in currency (not micros)
  conversions: number;
  conversions_value: number; // Already in currency (not micros)
  ctr: number;
  cpc: number;
  conversion_rate: number;
  roas: number;
  campaign_count: number;
  active_campaigns: number;
  currency: string;
  time_range: string;
  is_connected: boolean;
  is_demo?: boolean;
}

export interface GoogleCustomer {
  customer_id: string;
  descriptive_name: string;
  currency_code: string;
  time_zone: string;
  manager: boolean;
  test_account: boolean;
}

export interface GoogleOAuthStatus {
  connected: boolean;
  platform: string;
  email?: string;
  expires_at?: string;
  is_valid?: boolean;
  scopes?: string[];
  message?: string;
}

export interface GoogleConnectionStatus {
  success: boolean;
  message: string;
  oauth_status: GoogleOAuthStatus;
  customers_count?: number;
  developer_token_configured: boolean;
  timestamp: string;
  error?: string;
}

export interface GoogleConfig {
  tenant_id: number;
  google_client_id: boolean;
  google_client_secret: boolean;
  google_developer_token: boolean;
  google_redirect_uri: string | null;
  google_login_redirect_uri: string | null;
  env_google_client_id: boolean;
  env_google_client_secret: boolean;
  env_google_developer_token: boolean;
  env_google_redirect_uri: string | null;
  env_google_login_redirect_uri: string | null;
  frontend_url: string | null;
  platform_url: string | null;
}

export interface CombinedStats {
  google: GoogleMetrics;
  meta: {
    is_connected: boolean;
    spend?: number;
    revenue?: number;
    leads?: number;
    patients_converted?: number;
    cpa?: number;
    currency?: string;
    message?: string;
  };
  combined: {
    total_impressions: number;
    total_clicks: number;
    total_cost: number;
    total_conversions: number;
    total_conversions_value: number;
    platforms: string[];
    total_spend?: number;
    total_revenue?: number;
    total_leads?: number;
    roi_percentage?: number;
  };
  time_range: string;
}

export interface MultiPlatformCampaign {
  id: string;
  name: string;
  platform: 'meta' | 'google';
  status: string;
  spend: number;
  leads: number;
  appointments: number;
  roi: number;
  impressions?: number;
  clicks?: number;
  ctr?: number;
  conversion_rate?: number;
  cpc?: number;
}

export interface MultiPlatformCampaignsResponse {
  campaigns: MultiPlatformCampaign[];
  meta_count: number;
  google_count: number;
  total_count: number;
  time_range: string;
}

export interface PlatformStatus {
  meta: {
    connected: boolean;
    has_token: boolean;
    has_account: boolean;
    account_id?: string;
  };
  google: {
    connected: boolean;
    has_token: boolean;
    has_developer_token: boolean;
    email?: string;
    expires_at?: string;
  };
}

export interface GoogleSyncResult {
  success: boolean;
  message: string;
  synced_items: number;
  campaigns_synced?: number;
  metrics_synced?: number;
  timestamp?: string;
}

// Wizard types
export interface GoogleWizardStep {
  id: 'welcome' | 'configure' | 'authorize' | 'complete' | 'error';
  title: string;
  description: string;
}

// Campaign performance metrics
export interface CampaignPerformance {
  campaign_id: string;
  campaign_name: string;
  platform: 'meta' | 'google';
  date: string;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  conversions_value: number;
  ctr: number;
  cpc: number;
  conversion_rate: number;
  roas: number;
}

// Time range options
export type TimeRange = 
  | 'today'
  | 'yesterday'
  | 'last_7d'
  | 'last_14d'
  | 'last_30d'
  | 'last_90d'
  | 'this_month'
  | 'last_month'
  | 'this_year'
  | 'last_year'
  | 'lifetime'
  | 'all';

// Chart data interfaces
export interface MetricChartData {
  date: string;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  conversions_value: number;
}

export interface PlatformComparisonData {
  platform: 'meta' | 'google';
  spend: number;
  revenue: number;
  leads: number;
  roi: number;
  cpa: number;
  ctr: number;
  conversion_rate: number;
}

// Google Ads API error types
export interface GoogleApiError {
  error: {
    code: number;
    message: string;
    status: string;
    details?: Array<{
      '@type': string;
      [key: string]: any;
    }>;
  };
}

// OAuth token response
export interface GoogleTokenResponse {
  access_token: string;
  expires_in: number;
  refresh_token?: string;
  scope: string;
  token_type: string;
  id_token?: string;
}

// User info response
export interface GoogleUserInfo {
  sub: string;
  email: string;
  email_verified: boolean;
  name?: string;
  picture?: string;
  given_name?: string;
  family_name?: string;
  locale?: string;
}

// Utility types for form handling
export interface GoogleConnectionFormData {
  client_id: string;
  client_secret: string;
  developer_token: string;
  redirect_uri: string;
  login_redirect_uri: string;
}

// Settings/configuration types
export interface GoogleAdsSettings {
  auto_sync: boolean;
  sync_frequency: 'hourly' | 'daily' | 'weekly';
  default_time_range: TimeRange;
  currency: string;
  time_zone: string;
  notifications: {
    on_sync_complete: boolean;
    on_error: boolean;
    on_budget_exceeded: boolean;
  };
}