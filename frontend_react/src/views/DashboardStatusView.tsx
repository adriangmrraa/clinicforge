/**
 * Vista que carga el Dashboard CEO (tokens, métricas) del backend.
 * El backend sirve HTML en /dashboard/status; lo mostramos en iframe
 * para que la autenticación (cookies/headers) funcione correctamente.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { BACKEND_URL } from '../api/axios';
import { RefreshCw } from 'lucide-react';

export default function DashboardStatusView() {
  const { user, isLoading } = useAuth();
  const navigate = useNavigate();
  const [iframeKey, setIframeKey] = useState(0);
  const dashboardUrl = `${BACKEND_URL.replace(/\/$/, '')}/dashboard/status`;

  useEffect(() => {
    if (!isLoading && !user) {
      navigate('/login');
    }
  }, [user, isLoading, navigate]);

  if (isLoading || !user) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500" />
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-slate-50">
      <div className="flex-shrink-0 flex items-center justify-between px-4 py-3 bg-white border-b border-slate-200">
        <div>
          <h1 className="text-lg font-bold text-slate-800">Dashboard de Tokens y Métricas</h1>
          <p className="text-xs text-slate-500">Estado del agente IA, uso de tokens y configuración</p>
        </div>
        <button
          onClick={() => setIframeKey((k) => k + 1)}
          className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <RefreshCw size={16} />
          Recargar
        </button>
      </div>
      <div className="flex-1 min-h-0 p-4">
        <iframe
          key={iframeKey}
          src={dashboardUrl}
          title="Dashboard CEO - Tokens y métricas"
          className="w-full h-full rounded-xl border border-slate-200 bg-white shadow-sm"
          sandbox="allow-scripts allow-same-origin allow-forms"
          referrerPolicy="same-origin"
        />
      </div>
    </div>
  );
}
