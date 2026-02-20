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

    useEffect(() => {
        loadStats();

        // Detectar si venimos de un login exitoso de Meta
        if (searchParams.get('success') === 'connected') {
            setIsWizardOpen(true);
            // Limpiar el parámetro de la URL
            searchParams.delete('success');
            setSearchParams(searchParams);
        }
    }, []);

    const loadStats = async () => {
        try {
            const { data } = await api.get('/admin/marketing/stats');
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
            <PageHeader
                title={t('nav.marketing')}
                subtitle="Control panel for Meta Ads campaigns and real ROI tracking."
                icon={<Megaphone size={24} />}
            />

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {/* Real ROI Card - Main Metric */}
                <div className="lg:col-span-2">
                    <MarketingPerformanceCard />
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
            <div className="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden">
                <div className="p-6 border-b border-gray-100 flex justify-between items-center">
                    <h3 className="font-bold text-gray-900">Active Campaigns</h3>
                    <div className="flex gap-2">
                        <span className="text-sm text-gray-500 mr-2">Default: Last 30 Days</span>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    <table className="w-full text-left">
                        <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider">
                            <tr>
                                <th className="px-6 py-4 font-semibold">Campaign / Ad</th>
                                <th className="px-6 py-4 font-semibold">Spend</th>
                                <th className="px-6 py-4 font-semibold">Leads</th>
                                <th className="px-6 py-4 font-semibold">Appts</th>
                                <th className="px-6 py-4 font-semibold text-indigo-600">ROI Real</th>
                                <th className="px-6 py-4 font-semibold">Status</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {stats?.campaigns?.map((c: any) => (
                                <tr key={c.ad_id} className="hover:bg-gray-50/50 transition-colors">
                                    <td className="px-6 py-4">
                                        <div className="font-medium text-gray-900">{c.ad_name}</div>
                                        <div className="text-xs text-gray-400">{c.campaign_name}</div>
                                    </td>
                                    <td className="px-6 py-4 font-medium">${c.spend}</td>
                                    <td className="px-6 py-4">{c.leads}</td>
                                    <td className="px-6 py-4 font-semibold text-green-600">{c.appointments}</td>
                                    <td className="px-6 py-4">
                                        <span className={`px-2.5 py-1 rounded-lg font-bold ${c.roi >= 0 ? 'bg-indigo-50 text-indigo-700' : 'bg-rose-50 text-rose-700'}`}>
                                            {c.roi > 0 ? '+' : ''}{Math.round(c.roi * 100)}%
                                        </span>
                                    </td>
                                    <td className="px-6 py-4">
                                        <span className="flex items-center gap-1.5 text-green-600 text-sm font-medium">
                                            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div> Active
                                        </span>
                                    </td>
                                </tr>
                            ))}
                            {!stats?.campaigns?.length && (
                                <tr>
                                    <td colSpan={6} className="px-6 py-12 text-center text-gray-400 italic">
                                        No active campaigns found for this period.
                                    </td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <MetaConnectionWizard
                isOpen={isWizardOpen}
                onClose={() => setIsWizardOpen(false)}
                onSuccess={loadStats}
            />
        </div>
    );
}
