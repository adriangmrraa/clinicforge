import React, { useState, useEffect } from 'react';
import { AlertTriangle, RefreshCw, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import api from '../api/axios';
import { useAuth } from '../context/AuthContext';

export default function MetaTokenBanner() {
    const [status, setStatus] = useState<{ days_left: number; needs_reconnect: boolean } | null>(null);
    const [dismissed, setDismissed] = useState(false);
    const { user } = useAuth();
    const navigate = useNavigate();

    useEffect(() => {
        // Solo para CEO
        if (user?.role !== 'ceo') return;

        const checkToken = async () => {
            try {
                const { data } = await api.get('/admin/marketing/token-status');
                if (data.needs_reconnect || (data.days_left !== null && data.days_left <= 7)) {
                    setStatus(data);
                }
            } catch (error) {
                console.error("Error checking Meta token status:", error);
            }
        };

        checkToken();
        // Check once an hour
        const interval = setInterval(checkToken, 3600000);
        return () => clearInterval(interval);
    }, [user]);

    if (!status || dismissed) return null;

    const isExpiringSoon = status.days_left !== null && status.days_left <= 7;
    const isExpired = status.needs_reconnect;

    if (!isExpiringSoon && !isExpired) return null;

    return (
        <div className={`w-full py-3 px-6 flex items-center justify-between animate-in slide-in-from-top duration-500 shadow-md z-50 ${isExpired ? 'bg-rose-600 text-white' : 'bg-amber-500 text-white'
            }`}>
            <div className="flex items-center gap-3">
                <AlertTriangle size={20} className="animate-pulse" />
                <p className="text-sm font-bold">
                    {isExpired
                        ? "⚠️ Tu conexión con Meta Ads ha expirado. Reconecta ahora para no perder datos."
                        : `⚠️ Tu conexión con Meta Ads expira en ${status.days_left} días. Reconecta para evitar interrupciones.`
                    }
                </p>
            </div>

            <div className="flex items-center gap-3">
                <button
                    onClick={() => navigate('/marketing')}
                    className="bg-white/20 hover:bg-white/30 backdrop-blur-md px-4 py-1.5 rounded-xl text-xs font-black uppercase transition-all flex items-center gap-2 border border-white/30"
                >
                    <RefreshCw size={14} /> Reconectar Ahora
                </button>
                <button onClick={() => setDismissed(true)} className="hover:bg-black/10 p-1 rounded-lg transition-colors">
                    <X size={18} />
                </button>
            </div>
        </div>
    );
}
