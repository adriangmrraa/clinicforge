import { useState, useEffect } from 'react';
import { Megaphone, RefreshCw, ExternalLink } from 'lucide-react';
import api from '../api/axios';
import PageHeader from '../components/PageHeader';
import { useTranslation } from '../context/LanguageContext';
import MarketingPerformanceCard from '../components/MarketingPerformanceCard';
import MetaConnectionWizard from '../components/integrations/MetaConnectionWizard';
import { getCurrentTenantId } from '../api/axios';
import { useSearchParams } from 'react-router-dom';

export default function MarketingHubView() {
    const { t } = useTranslation();
    const [searchParams, setSearchParams] = useSearchParams();
    const [stats, setStats] = useState<any>(null);
    const [isMetaConnected, setIsMetaConnected] = useState(false);
    const [isWizardOpen, setIsWizardOpen] = useState(false);
    const [timeRange, setTimeRange] = useState('last_30d');

    useEffect(() => {
        loadStats();

        // Manejo de errores de Meta OAuth
        const error = searchParams.get('error');
        if (error) {
            const errorMessages: Record<string, string> = {
                'missing_tenant': 'Error de seguridad: No se pudo identificar la clínica. Reintenta desde el panel.',
                'auth_failed': 'La autenticación con Meta falló o fue cancelada.',
                'token_exchange_failed': 'Error al canjear el token permanente. Reintenta la conexión.'
            };
            alert(errorMessages[error] || `Error en la conexión con Meta: ${error}`);
            const newParams = new URLSearchParams(searchParams);
            newParams.delete('error');
            setSearchParams(newParams);
        }

        // Detectar si venimos de un login exitoso de Meta
        if (searchParams.get('success') === 'connected') {
            setIsWizardOpen(true);
            // Limpiar el parámetro de la URL
            const newParams = new URLSearchParams(searchParams);
            newParams.delete('success');
            setSearchParams(newParams);
        }

        // Detectar si queremos iniciar reconexión automática desde el banner
        if (searchParams.get('reconnect') === 'true') {
            handleConnectMeta();
            const newParams = new URLSearchParams(searchParams);
            newParams.delete('reconnect');
            setSearchParams(newParams);
        }
    }, [searchParams, timeRange]);

    const loadStats = async () => {
        try {
            const { data } = await api.get(`/admin/marketing/stats?range=${timeRange}`);
            console.log("[MarketingHub] Stats data loaded:", data);
            setStats(data);
            setIsMetaConnected(data?.is_connected || false);
        } catch (error) {
            console.error("Error loading marketing stats:", error);
        }
    };

    const handleConnectMeta = async () => {
        try {
            const tenantId = getCurrentTenantId();
            // Solicitamos la URL de OAuth al backend, pasando el tenant en el state para seguridad
            const { data } = await api.get(`/admin/marketing/meta-auth/url?state=tenant_${tenantId}`);
            if (data?.url) {
                // Redirigir a la página de OAuth de Meta
                window.location.href = data.url;
            }
        } catch (error) {
            console.error("Error initiating Meta OAuth:", error);
            alert("Error al iniciar la conexión con Meta Ads. Revisa la consola.");
        }
    };

    return (
        <div className="p-6 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <PageHeader
                    title={t('nav.marketing')}
                    subtitle="Control panel for Meta Ads campaigns and real ROI tracking."
                    icon={<Megaphone size={24} />}
                />

                <div className="flex items-center gap-3 bg-white p-1.5 rounded-2xl border border-gray-200 shadow-sm self-start">
                    {[
                        { id: 'last_30d', label: '30 Días' },
                        { id: 'last_90d', label: '3 Meses' },
                        { id: 'this_year', label: 'Este Año' },
                        { id: 'lifetime', label: 'Todo' }
                    ].map(range => (
                        <button
                            key={range.id}
                            onClick={() => setTimeRange(range.id)}
                            className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${timeRange === range.id
                                ? 'bg-gray-900 text-white shadow-lg'
                                : 'text-gray-500 hover:bg-gray-50'
                                }`}
                        >
                            {range.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Real ROI Card - Main Metric */}
                <div className="lg:col-span-2">
                    <MarketingPerformanceCard stats={stats?.roi} loading={!stats} />
                </div>

                {/* Connection Status Card */}
                <div className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm flex flex-col justify-between">
                    <div>
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="font-bold text-gray-900 flex items-center gap-2">
                                <RefreshCw size={18} className={isMetaConnected ? "text-blue-500" : "text-gray-400"} /> Meta Connection
                            </h3>
                            <span className={`px-3 py-1 text-xs font-bold rounded-full ${isMetaConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                {isMetaConnected ? 'ACTIVE' : 'DISCONNECTED'}
                            </span>
                        </div>
                        <p className="text-sm text-gray-500 mb-6">
                            {isMetaConnected
                                ? "Tu cuenta de anuncios está sincronizada y extrayendo datos reales."
                                : "Conecta tu cuenta de Meta Ads para empezar a medir el ROI real de tus campañas."}
                        </p>
                    </div>

                    <button
                        onClick={handleConnectMeta}
                        className={`w-full py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all ${isMetaConnected
                            ? "bg-gray-100 text-gray-900 hover:bg-gray-200"
                            : "bg-gray-900 text-white hover:bg-black"
                            }`}
                    >
                        <ExternalLink size={18} /> {isMetaConnected ? 'Reconnect Meta Account' : 'Connect Meta Ads'}
                    </button>
                </div>
            </div>

            {/* Campaign Table */}
            <div className="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden mb-12">
                <div className="p-6 border-b border-gray-100 flex justify-between items-center">
                    <h3 className="font-bold text-gray-900">Active Campaigns</h3>
                    <div className="flex gap-2">
                        <span className="text-sm text-gray-500 mr-2 capitalize">Period: {timeRange.replace('_', ' ')}</span>
                    </div>
                </div>

                <div className="overflow-x-auto max-h-[800px] overflow-y-auto scrollbar-thin scrollbar-thumb-gray-200">
                    <table className="w-full text-left border-separate border-spacing-0">
                        <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider sticky top-0 z-10 shadow-sm">
                            <tr>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100">Campaign / Ad</th>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100">Spend</th>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100">Leads</th>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100">Appts</th>
                                <th className="px-6 py-4 font-semibold text-indigo-600 border-b border-gray-100">ROI Real</th>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {stats?.campaigns?.map((c: any) => (
                                <tr key={c.ad_id} className="hover:bg-blue-50/30 transition-colors group">
                                    <td className="px-6 py-4">
                                        <div className="font-bold text-gray-900 group-hover:text-blue-700 transition-colors">{c.ad_name}</div>
                                        <div className="text-xs text-gray-400 font-medium">{c.campaign_name}</div>
                                    </td>
                                    <td className="px-6 py-4 font-bold text-gray-700">
                                        {stats.currency === 'ARS' ? 'ARS' : '$'} {c.spend.toLocaleString()}
                                    </td>
                                    <td className="px-6 py-4 font-medium text-gray-600">{c.leads}</td>
                                    <td className="px-6 py-4">
                                        <span className="font-bold text-green-600 bg-green-50 px-2.5 py-1 rounded-lg">
                                            {c.appointments}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className={`px-2.5 py-1 rounded-lg font-bold border ${c.roi >= 0
                                            ? 'bg-indigo-50 text-indigo-700 border-indigo-100'
                                            : 'bg-rose-50 text-rose-700 border-rose-100'}`}>
                                            {c.roi > 0 ? '+' : ''}{Math.round(c.roi * 100)}%
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className={`flex items-center gap-1.5 text-sm font-bold ${c.status === 'active' ? 'text-green-600' : 'text-gray-400'}`}>
                                            <div className={`w-2 h-2 rounded-full ${c.status === 'active' ? 'bg-green-500 animate-pulse' : 'bg-gray-300'}`}></div>
                                            {c.status === 'active' ? 'Active' : 'Paused/Other'}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                            {!stats?.campaigns?.length && (
                                <tr>
                                    <td colSpan={6} className="px-6 py-20 text-center text-gray-400 italic">
                                        <Megaphone className="w-10 h-10 mx-auto mb-4 opacity-20" />
                                        No active campaigns found for this account.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <div className="h-20" /> {/* Spacer for extra breathing room at the bottom */}

            <MetaConnectionWizard
                isOpen={isWizardOpen}
                onClose={() => setIsWizardOpen(false)}
                onSuccess={loadStats}
            />
        </div>
    );
}
