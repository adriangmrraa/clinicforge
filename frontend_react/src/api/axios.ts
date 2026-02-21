import axios, { type AxiosInstance, type AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios';
import { getEnv } from '../utils/env';

const API_URL = getEnv('VITE_API_URL') || 'http://localhost:8000';
export const BACKEND_URL = API_URL;
const MAX_RETRIES = 3;
const BASE_DELAY = 1000;

// ============================================
// MULTI-TENANCY: Tenant ID Management
// ============================================

// Get current tenant ID from storage or context
export const getCurrentTenantId = (): string | null => {
  // Try to get from localStorage (X-Tenant-ID is preferred, tenant_id is legacy/fallback)
  const storedTenant = localStorage.getItem('X-Tenant-ID') || localStorage.getItem('tenant_id');
  if (storedTenant) return storedTenant;

  // Try to get from session storage
  const sessionTenant = sessionStorage.getItem('X-Tenant-ID') || sessionStorage.getItem('tenant_id');
  if (sessionTenant) return sessionTenant;

  // Default tenant for development
  return getEnv('VITE_DEFAULT_TENANT_ID') || '1';
};

// Set tenant ID for the session
export const setTenantId = (tenantId: string, persist = true): void => {
  if (persist) {
    localStorage.setItem('X-Tenant-ID', tenantId);
  } else {
    sessionStorage.setItem('X-Tenant-ID', tenantId);
  }
};

// Clear tenant ID
export const clearTenantId = (): void => {
  localStorage.removeItem('X-Tenant-ID');
  sessionStorage.removeItem('X-Tenant-ID');
};

// ============================================
// AXIOS INSTANCE
// ============================================

// Utility para delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Utility para calcular delay exponencial con jitter
const calculateExponentialDelay = (attempt: number): number => {
  const exponentialDelay = BASE_DELAY * Math.pow(2, attempt);
  const jitter = Math.random() * 0.3 * exponentialDelay;
  return Math.min(exponentialDelay + jitter, 10000);
};

interface CustomAxiosConfig extends AxiosRequestConfig {
  _retryCount?: number;
}

// Crear instancia de axios
const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
  withCredentials: true, // Nexus Security: Permitir HttpOnly Cookies
});

// Request interceptor: agregar token y X-Tenant-ID
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 1. Get Infrastructure token from localStorage
    let adminToken = localStorage.getItem('ADMIN_TOKEN');

    // Self-healing: clear polluted storage from previous versions
    if (adminToken === 'RUNTIME_REPLACE') {
      import.meta.env.DEV && console.warn('🚨 Corrupt ADMIN_TOKEN detected in localStorage. Clearing...');
      localStorage.removeItem('ADMIN_TOKEN');
      adminToken = null;
    }

    // Auto-init for Admin Token (Compatibility)
    if (!adminToken || adminToken === 'RUNTIME_REPLACE') {
      const envToken = getEnv('VITE_ADMIN_TOKEN');
      if (envToken && envToken !== 'RUNTIME_REPLACE') {
        localStorage.setItem('ADMIN_TOKEN', envToken);
        adminToken = envToken;
      } else if (envToken === 'RUNTIME_REPLACE') {
        console.error('🚨 VITE_ADMIN_TOKEN is still "RUNTIME_REPLACE" in the environment! Check your deployment configuration.');
        adminToken = null; // NEVER send RUNTIME_REPLACE
      }
    }

    if (config.headers) {
      // Layer 1: Infrastructure Security (Static)
      if (adminToken && adminToken !== 'RUNTIME_REPLACE') {
        config.headers['X-Admin-Token'] = adminToken;
      } else if (adminToken === 'RUNTIME_REPLACE') {
        console.error('🚫 Blocked request with "RUNTIME_REPLACE" token');
        return Promise.reject(new Error('Auth blocked: Corrupt token detected'));
      }

      // Layer 2: Identity Security (Nexus v7.6)
      // El JWT se envía automáticamente vía Cookies HttpOnly gracias a withCredentials: true.
      // Se RESTAURA fallback a cabecera Bearer para entornos donde las cookies sean bloqueadas o el backend sea strict.
      const jwtToken = localStorage.getItem('access_token');
      if (jwtToken) {
        config.headers['Authorization'] = `Bearer ${jwtToken}`;
      }
    }

    // 2. Get and set X-Tenant-ID header
    const tenantId = getCurrentTenantId();
    if (tenantId && config.headers) {
      config.headers['X-Tenant-ID'] = tenantId;
    }

    // Log request
    console.log(`[API] ${config.method?.toUpperCase()} ${config.url} [Tenant: ${tenantId}]`);

    // Agregar retry count metadata
    (config as any).metadata = { retryCount: 0 };

    return config;
  },
  (error: AxiosError) => {
    console.error('[API] Request error:', error.message);
    return Promise.reject(error);
  }
);

// Response interceptor con exponential backoff y retry automático
api.interceptors.response.use(
  (response) => {
    console.log(`[API] ✅ ${response.config.method?.toUpperCase()} ${response.config.url} - ${response.status}`);
    return response;
  },
  async (error: AxiosError) => {
    const originalConfig = error.config as CustomAxiosConfig | undefined;

    if (!originalConfig || originalConfig._retryCount === undefined) {
      return Promise.reject(error);
    }

    const retryCount = (originalConfig._retryCount || 0) + 1;

    // Solo hacer retry para errores 5xx o pérdida de conexión
    const status = error.response?.status;
    const shouldRetry =
      status && (status >= 500 || error.code === 'ECONNABORTED') &&
      retryCount <= MAX_RETRIES;

    if (shouldRetry) {
      originalConfig._retryCount = retryCount;
      const delayMs = calculateExponentialDelay(retryCount - 1);

      console.log(`[API] ⏳ Retry ${retryCount}/${MAX_RETRIES} para ${originalConfig.url} en ${Math.round(delayMs)}ms`);

      await delay(delayMs);
      return api(originalConfig);
    }

    // Manejo específico de errores
    if (status === 401) {
      console.warn('[API] ⚠️ Unauthorized - Limpiando token');
      localStorage.removeItem('ADMIN_TOKEN');

      // No redirigir si estamos en una página pública legal (Spec Meta Review)
      const publicRoutes = ['/privacy', '/terms', '/demo'];
      const isPublicRoute = publicRoutes.some(route => window.location.pathname.startsWith(route));

      if (!window.location.pathname.includes('/login') && !isPublicRoute) {
        window.location.href = '/login';
      }
    } else if (status === 403) {
      console.warn('[API] ⚠️ Forbidden - Posible error de tenant');
      // Trigger event for tenant-related errors
      window.dispatchEvent(new CustomEvent('tenant:error', { detail: error }));
    } else if (status === 404) {
      console.error('[API] ❌ Recurso no encontrado:', originalConfig?.url);
    } else if (status && status >= 500) {
      console.error('[API] 🔥 Error del servidor:', status, originalConfig?.url);
    } else if (error.code === 'ECONNABORTED') {
      console.error('[API] ⏰ Timeout:', originalConfig?.url);
    } else if (!error.response) {
      console.error('[API] 🌐 Sin conexión:', error.message);
    }

    return Promise.reject(error);
  }
);

// ============================================
// API HELPERS
// ============================================

// Helper para GET con cache opcional
export const apiGet = async <T>(url: string, useCache = false): Promise<T> => {
  const cacheKey = `cache_${url}`;

  if (useCache) {
    const cached = localStorage.getItem(cacheKey);
    if (cached) {
      try {
        const { data, timestamp } = JSON.parse(cached);
        const age = Date.now() - timestamp;
        if (age < 60000) {
          console.log(`[API] 📦 Cache hit: ${url}`);
          return data;
        }
      } catch (e) {
        // Invalid cache, continue
      }
    }
  }

  const response = await api.get<T>(url);

  if (useCache) {
    localStorage.setItem(cacheKey, JSON.stringify({
      data: response.data,
      timestamp: Date.now()
    }));
  }

  return response.data;
};

// Helper para POST sin cache
export const apiPost = <T>(url: string, data?: any): Promise<T> =>
  api.post<T>(url, data).then(res => res.data);

// Helper para PUT
export const apiPut = <T>(url: string, data?: any): Promise<T> =>
  api.put<T>(url, data).then(res => res.data);

// Helper para DELETE
export const apiDelete = <T>(url: string): Promise<T> =>
  api.delete<T>(url).then(res => res.data);

export { api };
export default api;
