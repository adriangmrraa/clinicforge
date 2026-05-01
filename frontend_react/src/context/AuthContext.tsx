import React, { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { updateSocketToken } from '../services/socket';

interface User {
    id: string;
    email: string;
    role: 'ceo' | 'professional' | 'secretary';
    tenant_id?: number;
    professional_id?: number;
}

interface AuthContextType {
    user: User | null;
    token: string | null;
    login: (token: string, user: User) => void;
    logout: () => void;
    isAuthenticated: boolean;
    isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

/** H2: Parse JWT exp claim without external dependency (manual base64 decode). */
function getJwtExp(token: string): number | null {
    try {
        const parts = token.split('.');
        if (parts.length !== 3) return null;
        const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
        return typeof payload.exp === 'number' ? payload.exp : null;
    } catch {
        return null;
    }
}

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    /** H2: Schedule token refresh 5 minutes before JWT exp. */
    const scheduleTokenRefresh = (token: string) => {
        if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        const exp = getJwtExp(token);
        if (!exp) return;
        const expiresAt = exp * 1000;
        const delay = expiresAt - 5 * 60 * 1000 - Date.now();
        if (delay <= 0) return;
        refreshTimerRef.current = setTimeout(async () => {
            try {
                const res = await fetch('/auth/refresh', { method: 'POST', credentials: 'include' });
                if (res.ok) {
                    const data = await res.json();
                    if (data.access_token) {
                        localStorage.setItem('access_token', data.access_token);
                        scheduleTokenRefresh(data.access_token);
                        updateSocketToken();
                    }
                }
            } catch (e) {
                console.warn('[Auth] Token refresh failed:', e);
            }
        }, delay);
    };

    useEffect(() => {
        const initializeAuth = async () => {
            const savedUser = localStorage.getItem('USER_PROFILE');
            const savedToken = localStorage.getItem('access_token');

            if (savedUser && savedToken) {
                try {
                    setUser(JSON.parse(savedUser));
                    scheduleTokenRefresh(savedToken);
                } catch (e) {
                    console.error("Error parsing user profile:", e);
                    logout();
                }
            }
            setIsLoading(false);
        };
        initializeAuth();
        return () => {
            if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        };
    }, []);

    const login = (newToken: string, profile: User) => {
        // Guardar token JWT para enviar en Authorization header
        localStorage.setItem('access_token', newToken);

        // Guardar perfil de usuario
        localStorage.setItem('USER_PROFILE', JSON.stringify(profile));

        // Save tenant_id as a top-level key for axios/direct-access needs
        const tid = profile.tenant_id?.toString() || '1';
        localStorage.setItem('X-Tenant-ID', tid);

        setUser(profile);

        // H2: Schedule proactive refresh based on JWT exp
        scheduleTokenRefresh(newToken);

        // Update socket auth token so reconnections use the fresh JWT
        updateSocketToken();
    };

    const logout = () => {
        if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
        localStorage.removeItem('access_token');
        localStorage.removeItem('USER_PROFILE');
        localStorage.removeItem('X-Tenant-ID');
        setUser(null);
        // Notify backend to blacklist JTI and clear HttpOnly cookie
        fetch('/auth/logout', { method: 'POST', credentials: 'include' }).catch(() => {});
    };

    return (
        <AuthContext.Provider value={{
            user,
            token: null, // El token ya no es accesible por JS
            login,
            logout,
            isAuthenticated: !!user,
            isLoading
        }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider');
    }
    return context;
};
