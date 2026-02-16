/**
 * Runtime Environment Helper
 * 
 * Reads environment variables from:
 * 1. window.__ENV__ (injected at runtime by docker-entrypoint.sh in production)
 * 2. import.meta.env (injected at build time by Vite in development)
 * 
 * This ensures the app works both locally (vite dev) and in Docker/EasyPanel.
 */

interface RuntimeEnv {
    VITE_API_URL?: string;
    VITE_API_BASE_URL?: string;
    VITE_BFF_URL?: string;
    VITE_WS_URL?: string;
    VITE_ADMIN_TOKEN?: string;
    VITE_APP_NAME?: string;
    VITE_DEFAULT_TENANT_ID?: string;
}

declare global {
    interface Window {
        __ENV__?: RuntimeEnv;
    }
}

/**
 * Get an environment variable, checking runtime injection first, then Vite build-time.
 */
export function getEnv(key: keyof RuntimeEnv): string {
    // 1. Runtime injection (Docker/EasyPanel)
    const runtimeVal = window.__ENV__?.[key];
    if (runtimeVal && !runtimeVal.startsWith('__VITE_')) {
        return runtimeVal;
    }

    // 2. Vite build-time injection (local dev)
    const viteVal = (import.meta.env as Record<string, string>)?.[key];
    if (viteVal && !viteVal.startsWith('__VITE_')) {
        return viteVal;
    }

    return '';
}
