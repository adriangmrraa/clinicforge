import api from './axios';

export interface GoogleCampaign {
  id: string;
  name: string;
  status: string;
  type: string;
  budget: number;
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  conversions_value: number;
  ctr: number;
  cpc: number;
  conversion_rate: number;
  roas: number;
  start_date: string;
  end_date: string | null;
  currency_code: string;
}

export interface GoogleMetrics {
  impressions: number;
  clicks: number;
  cost: number;
  conversions: number;
  conversions_value: number;
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

export interface GoogleConnectionStatus {
  success: boolean;
  message: string;
  oauth_status: {
    connected: boolean;
    platform: string;
    email?: string;
    expires_at?: string;
    is_valid?: boolean;
    scopes?: string[];
  };
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
    message?: string;
  };
  combined: {
    total_impressions: number;
    total_clicks: number;
    total_cost: number;
    total_conversions: number;
    total_conversions_value: number;
    platforms: string[];
  };
  time_range: string;
}

class GoogleAdsApi {
  // Campaigns
  static async getCampaigns(timeRange: string = 'last_30d'): Promise<GoogleCampaign[]> {
    try {
      const { data } = await api.get(`/admin/marketing/google/campaigns?time_range=${timeRange}`);
      return data.campaigns || [];
    } catch (error) {
      console.error('Failed to fetch Google campaigns:', error);
      return [];
    }
  }

  // Metrics
  static async getMetrics(timeRange: string = 'last_30d'): Promise<GoogleMetrics | null> {
    try {
      const { data } = await api.get(`/admin/marketing/google/metrics?time_range=${timeRange}`);
      return data.metrics || null;
    } catch (error) {
      console.error('Failed to fetch Google metrics:', error);
      return null;
    }
  }

  // Customers
  static async getCustomers(): Promise<GoogleCustomer[]> {
    try {
      const { data } = await api.get('/admin/marketing/google/customers');
      return data.customers || [];
    } catch (error) {
      console.error('Failed to fetch Google customers:', error);
      return [];
    }
  }

  // Connection status
  static async getConnectionStatus(): Promise<GoogleConnectionStatus | null> {
    try {
      const { data } = await api.get('/admin/marketing/google/connection-status');
      return data.connection_status || null;
    } catch (error) {
      console.error('Failed to fetch Google connection status:', error);
      return null;
    }
  }

  // Test connection
  static async testConnection(): Promise<GoogleConnectionStatus | null> {
    try {
      const { data } = await api.get('/admin/auth/google/ads/test-connection');
      return data.status || null;
    } catch (error) {
      console.error('Failed to test Google connection:', error);
      return null;
    }
  }

  // Sync data
  static async syncData(): Promise<{ success: boolean; message: string; synced_items: number }> {
    try {
      const { data } = await api.post('/admin/marketing/google/sync');
      return data.sync_result || { success: false, message: 'Unknown error', synced_items: 0 };
    } catch (error: any) {
      console.error('Failed to sync Google data:', error);
      return {
        success: false,
        message: error.response?.data?.detail || 'Failed to sync data',
        synced_items: 0
      };
    }
  }

  // Get combined stats
  static async getCombinedStats(timeRange: string = 'last_30d'): Promise<CombinedStats | null> {
    try {
      const { data } = await api.get(`/admin/marketing/google/combined-stats?time_range=${timeRange}`);
      return data.stats || null;
    } catch (error) {
      console.error('Failed to fetch combined stats:', error);
      return null;
    }
  }

  // Get config debug
  static async getConfig(): Promise<GoogleConfig | null> {
    try {
      const { data } = await api.get('/admin/marketing/google/debug/config');
      return data.config || null;
    } catch (error) {
      console.error('Failed to fetch Google config:', error);
      return null;
    }
  }

  // Get OAuth URL
  static async getOAuthUrl(): Promise<string | null> {
    try {
      const { data } = await api.get('/admin/auth/google/ads/url');
      return data.url || null;
    } catch (error) {
      console.error('Failed to get Google OAuth URL:', error);
      return null;
    }
  }

  // Disconnect
  static async disconnect(): Promise<boolean> {
    try {
      const { data } = await api.post('/admin/auth/google/ads/disconnect');
      return data.success || false;
    } catch (error) {
      console.error('Failed to disconnect Google:', error);
      return false;
    }
  }

  // Refresh token
  static async refreshToken(): Promise<boolean> {
    try {
      const { data } = await api.get('/admin/auth/google/ads/refresh');
      return data.success || false;
    } catch (error) {
      console.error('Failed to refresh Google token:', error);
      return false;
    }
  }

  // Debug token
  static async debugToken(): Promise<any> {
    try {
      const { data } = await api.get('/admin/auth/google/ads/debug/token');
      return data;
    } catch (error) {
      console.error('Failed to debug Google token:', error);
      return null;
    }
  }

  // Format currency
  static formatCurrency(amount: number, currency: string = 'ARS'): string {
    if (currency === 'ARS') {
      return `$${amount.toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency
    }).format(amount);
  }

  // Format micros (Google Ads uses micros for currency)
  static formatMicros(micros: number, currency: string = 'ARS'): string {
    const amount = micros / 1000000;
    return this.formatCurrency(amount, currency);
  }

  // Format percentage
  static formatPercentage(value: number): string {
    return `${value.toFixed(2)}%`;
  }

  // Format number with commas
  static formatNumber(num: number): string {
    return num.toLocaleString('es-AR');
  }

  // Calculate ROI
  static calculateROI(revenue: number, cost: number): number {
    if (cost === 0) return 0;
    return (revenue / cost) * 100;
  }

  // Get status color
  static getStatusColor(status: string): string {
    switch (status?.toLowerCase()) {
      case 'enabled':
        return 'text-green-600 bg-green-100';
      case 'paused':
        return 'text-yellow-600 bg-yellow-100';
      case 'removed':
      case 'archived':
        return 'text-red-600 bg-red-100';
      default:
        return 'text-gray-600 bg-gray-100';
    }
  }

  // Get status text
  static getStatusText(status: string): string {
    switch (status?.toLowerCase()) {
      case 'enabled':
        return 'Activo';
      case 'paused':
        return 'Pausado';
      case 'removed':
        return 'Eliminado';
      case 'archived':
        return 'Archivado';
      default:
        return status || 'Desconocido';
    }
  }

  // Get campaign type text
  static getCampaignType(type: string): string {
    switch (type?.toLowerCase()) {
      case 'search':
        return 'Búsqueda';
      case 'display':
        return 'Display';
      case 'video':
        return 'Video';
      case 'shopping':
        return 'Shopping';
      case 'performance_max':
        return 'Performance Max';
      default:
        return type || 'Otro';
    }
  }
}

export default GoogleAdsApi;