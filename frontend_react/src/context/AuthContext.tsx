import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';

interface User {
    id: string;
    email: string;
    role: 'ceo' | 'professional' | 'secretary';
    tenant_id?: number;
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

export const AuthProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const initializeAuth = async () => {
            const savedUser = localStorage.getItem('USER_PROFILE');
            // Nota: El token ya no se lee de localStorage (HttpOnly Cookie)
            if (savedUser) {
                try {
                    setUser(JSON.parse(savedUser));
                } catch (e) {
                    console.error("Error parsing user profile:", e);
                    logout();
                }
            }
            setIsLoading(false);
        };
        initializeAuth();
    }, []);

    const login = (_newToken: string, profile: User) => {
        // El token viene en la respuesta pero se guarda automáticamente en la Cookie HttpOnly
        localStorage.setItem('USER_PROFILE', JSON.stringify(profile));

        // Save tenant_id as a top-level key for axios/direct-access needs
        const tid = profile.tenant_id?.toString() || '1';
        localStorage.setItem('X-Tenant-ID', tid);

        setUser(profile);
    };

    const logout = () => {
        localStorage.removeItem('USER_PROFILE');
        localStorage.removeItem('X-Tenant-ID');
        setUser(null);
        // El backend debería tener una ruta para borrar la cookie, 
        // pero por ahora limpiamos el estado local.
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
