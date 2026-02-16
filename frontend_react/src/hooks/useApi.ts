import { useState, useCallback } from 'react';

const API_BASE = import.meta.env.VITE_API_BASE_URL || detectApiBase();
const ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN || "";

function detectApiBase() {
    if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
        return 'http://localhost:8000';
    }
    let hostname = window.location.hostname;
    if (hostname.includes('platform-ui')) {
        return window.location.protocol + '//' + hostname.replace('platform-ui', 'orchestrator-service');
    }
    // Fallback for EasyPanel
    if (hostname.includes('frontend-react')) {
        return window.location.protocol + '//' + hostname.replace('frontend-react', 'bff-service').replace('5173', '3000');
    }
    // Default to relative for BFF
    return '/api';
}

interface FetchOptions {
    method?: string;
    body?: any;
    headers?: Record<string, string>;
}

export function useApi() {
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchApi = useCallback(async (endpoint: string, options: FetchOptions = {}) => {
        setLoading(true);
        setError(null);
        try {
            const headers: Record<string, string> = {
                'Content-Type': 'application/json',
                'x-admin-token': ADMIN_TOKEN,
                ...options.headers
            };

            // Handle BFF proxying if we use relative paths
            const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint}`;

            const response = await fetch(url, {
                method: options.method || 'GET',
                headers,
                body: options.body ? JSON.stringify(options.body) : undefined,
            });

            if (!response.ok) {
                const errorData = await response.text();
                throw new Error(errorData || `HTTP ${response.status}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            return await response.text();

        } catch (err: any) {
            setError(err.message);
            throw err;
        } finally {
            setLoading(false);
        }
    }, []);

    return { fetchApi, loading, error };
}
