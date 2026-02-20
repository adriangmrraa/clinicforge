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
    const [timeRange, setTimeRange] = useState('all');
    const [activeTab, setActiveTab] = useState<'campaigns' | 'ads'>('campaigns');

    useEffect(() => {
        loadStats();

        // Manejo de errores de Meta OAuth
        const error = searchParams.get('error');
        if (error) {
            const errorMessages: Record<string, string> = {
                'missing_tenant': t('marketing.errors.missing_tenant'),
                'auth_failed': t('marketing.errors.auth_failed'),
                'token_exchange_failed': t('marketing.errors.token_exchange_failed')
            };
            alert(errorMessages[error] || `${t('common.error')}: ${error}`);
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
            alert(t('marketing.errors.init_failed'));
        }
    };

    return (
        <div className="p-4 sm:p-6 pb-24 max-w-7xl mx-auto space-y-8 animate-in fade-in duration-500">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <PageHeader
                    title={t('nav.marketing')}
                    subtitle={t('marketing.subtitle')}
                    icon={<Megaphone size={24} />}
                />

                <div className="flex flex-wrap items-center gap-3 bg-white p-1.5 rounded-2xl border border-gray-200 shadow-sm">
                    {[
                        { id: 'last_30d', label: t('marketing.range_30d') },
                        { id: 'last_90d', label: t('marketing.range_90d') },
                        { id: 'this_year', label: t('marketing.range_year') },
                        { id: 'all', label: t('marketing.range_all') }
                    ].map(range => (
                        <button
                            key={range.id}
                            onClick={() => setTimeRange(range.id)}
                            className={`flex-1 sm:flex-none px-3 sm:px-4 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all ${timeRange === range.id
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
                    <MarketingPerformanceCard stats={stats?.roi} loading={!stats} timeRange={timeRange} />
                </div>

                {/* Connection Status Card */}
                <div className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm flex flex-col justify-between">
                    <div>
                        <div className="flex items-center justify-between mb-6">
                            <h3 className="font-bold text-gray-900 flex items-center gap-2">
                                <RefreshCw size={18} className={isMetaConnected ? "text-blue-500" : "text-gray-400"} /> {t('marketing.meta_connection')}
                            </h3>
                            <span className={`px-3 py-1 text-xs font-bold rounded-full ${isMetaConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                                {isMetaConnected ? t('marketing.connected_active') : t('marketing.connected_disconnected')}
                            </span>
                        </div>
                        <p className="text-sm text-gray-500 mb-6">
                            {isMetaConnected
                                ? t('marketing.connected_desc')
                                : t('marketing.disconnected_desc')}
                        </p>
                    </div>

                    <button
                        onClick={handleConnectMeta}
                        className={`w-full py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all ${isMetaConnected
                            ? "bg-gray-100 text-gray-900 hover:bg-gray-200"
                            : "bg-gray-900 text-white hover:bg-black"
                            }`}
                    >
                        <ExternalLink size={18} /> {isMetaConnected ? t('marketing.reconnect') : t('marketing.connect')}
                    </button>
                </div>
            </div>

            {/* Campaign/Ad Table with Tabs */}
            <div className="bg-white border border-gray-200 rounded-3xl shadow-sm overflow-hidden mb-12">
                <div className="p-6 border-b border-gray-100 flex flex-col sm:flex-row justify-between items-center gap-4">
                    <div className="flex bg-gray-100 p-1 rounded-xl">
                        <button
                            onClick={() => setActiveTab('campaigns')}
                            className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'campaigns'
                                ? 'bg-white text-gray-900 shadow-sm'
                                : 'text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            {t('marketing.tabs.campaigns')}
                        </button>
                        <button
                            onClick={() => setActiveTab('ads')}
                            className={`px-6 py-2 rounded-lg text-sm font-bold transition-all ${activeTab === 'ads'
                                ? 'bg-white text-gray-900 shadow-sm'
                                : 'text-gray-500 hover:text-gray-700'
                                }`}
                        >
                            {t('marketing.tabs.creatives')}
                        </button>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500 mr-2 capitalize">{t('marketing.period_label')}: {timeRange.replace('_', ' ')}</span>
                    </div>
                </div>

                <div className="overflow-x-auto">
                    {/* Desktop Table View */}
                    <table className="hidden lg:table w-full text-left border-separate border-spacing-0">
                        <thead className="bg-gray-50 text-gray-500 text-xs uppercase tracking-wider sticky top-0 z-10 shadow-sm">
                            <tr>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100 w-1/3">
                                    {activeTab === 'campaigns' ? t('marketing.table_campaign_ad') : t('marketing.table_ad')}
                                </th>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100">{t('marketing.table_spend')}</th>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100">{t('marketing.table_leads')}</th>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100">{t('marketing.table_appts')}</th>
                                <th className="px-6 py-4 font-semibold text-indigo-600 border-b border-gray-100">{t('marketing.table_roi')}</th>
                                <th className="px-6 py-4 font-semibold border-b border-gray-100">{t('marketing.table_status')}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {(activeTab === 'campaigns' ? stats?.campaigns?.campaigns : stats?.campaigns?.creatives)?.map((c: any) => (
                                <tr key={c.ad_id} className="hover:bg-blue-50/30 transition-colors group">
                                    <td className="px-6 py-4">
                                        <div className="font-bold text-gray-900 group-hover:text-blue-700 transition-colors">{c.ad_name}</div>
                                        <div className="text-xs text-gray-400 font-medium">{c.campaign_name}</div>
                                    </td>
                                    <td className="px-6 py-4 font-bold text-gray-700">
                                        {stats.currency === 'ARS' ? 'ARS' : '$'} {Number(c.spend || 0).toLocaleString()}
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
                                        <span className={`flex items-center gap-1.5 text-sm font-bold ${c.status === 'active' ? 'text-green-600' : (c.status === 'paused' || c.status === 'archived') ? 'text-amber-600' : 'text-gray-400'}`}>
                                            <div className={`w-2 h-2 rounded-full ${c.status === 'active' ? 'bg-green-500 animate-pulse' : (c.status === 'paused' || c.status === 'archived') ? 'bg-amber-500' : 'bg-gray-300'}`}></div>
                                            <span className="capitalize">{c.status || 'Unknown'}</span>
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {/* Mobile Cards View (Stacking Pattern) */}
                    <div className="lg:hidden divide-y divide-gray-100">
                        {(activeTab === 'campaigns' ? stats?.campaigns?.campaigns : stats?.campaigns?.creatives)?.map((c: any) => (
                            <div key={c.ad_id} className="p-5 space-y-4 hover:bg-gray-50 transition-colors">
                                <div className="flex justify-between items-start">
                                    <div className="flex-1 min-w-0 pr-4">
                                        <div className="font-black text-gray-900 leading-tight mb-1">{c.ad_name}</div>
                                        <div className="text-[10px] text-gray-400 font-bold uppercase tracking-wider">{c.campaign_name}</div>
                                    </div>
                                    <span className={`flex items-center gap-1 text-[10px] font-black uppercase px-2 py-1 rounded-full border ${c.status === 'active' ? 'bg-green-50 text-green-600 border-green-100' : 'bg-gray-100 text-gray-500 border-gray-200'}`}>
                                        <div className={`w-1.5 h-1.5 rounded-full ${c.status === 'active' ? 'bg-green-500' : 'bg-gray-300'}`}></div>
                                        {c.status}
                                    </span>
                                </div>

                                <div className="grid grid-cols-2 gap-4 pt-2">
                                    <div>
                                        <div className="text-[10px] text-gray-400 font-bold uppercase mb-1">{t('marketing.table_spend')}</div>
                                        <div className="font-black text-gray-800">{stats.currency === 'ARS' ? 'ARS' : '$'}{Number(c.spend || 0).toLocaleString()}</div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-indigo-400 font-bold uppercase mb-1">{t('marketing.table_roi')}</div>
                                        <div className={`font-black ${c.roi >= 0 ? 'text-indigo-600' : 'text-rose-600'}`}>
                                            {c.roi > 0 ? '+' : ''}{Math.round(c.roi * 100)}%
                                        </div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-gray-400 font-bold uppercase mb-1">{t('marketing.table_leads')}</div>
                                        <div className="font-bold text-gray-700">{c.leads}</div>
                                    </div>
                                    <div>
                                        <div className="text-[10px] text-green-500 font-bold uppercase mb-1">{t('marketing.table_appts')}</div>
                                        <div className="font-black text-green-600">{c.appointments}</div>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Empty State */}
                    {!(activeTab === 'campaigns' ? stats?.campaigns?.campaigns : stats?.campaigns?.creatives)?.length && (
                        <div className="px-6 py-20 text-center text-gray-400 italic">
                            <Megaphone className="w-10 h-10 mx-auto mb-4 opacity-20" />
                            {t('marketing.no_data')}
                        </div>
                    )}
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
