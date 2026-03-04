import { useState, useEffect } from 'react';
import { Megaphone, RefreshCw, ExternalLink, Globe, BarChart3 } from 'lucide-react';
import api from '../api/axios';
import PageHeader from '../components/PageHeader';
import { useTranslation } from '../context/LanguageContext';
import MarketingPerformanceCard from '../components/MarketingPerformanceCard';
import MetaConnectionWizard from '../components/integrations/MetaConnectionWizard';
import GoogleConnectionWizard from '../components/integrations/GoogleConnectionWizard';
import { getCurrentTenantId } from '../api/axios';
import { useSearchParams } from 'react-router-dom';
import GoogleAdsApi from '../api/google_ads';

type Platform = 'meta' | 'google' | 'combined';
type TimeRange = 'last_30d' | 'last_90d' | 'this_year' | 'lifetime' | 'all';

export default function MarketingHubView() {
    const { t } = useTranslation();
    const [searchParams, setSearchParams] = useSearchParams();

    // State for all platforms
    const [activePlatform, setActivePlatform] = useState<Platform>('meta');
    const [timeRange, setTimeRange] = useState<TimeRange>('last_30d');

    // Meta state
    const [metaStats, setMetaStats] = useState<any>(null);
    const [isMetaConnected, setIsMetaConnected] = useState(false);
    const [isMetaWizardOpen, setIsMetaWizardOpen] = useState(false);

    // Google state
    const [googleStats, setGoogleStats] = useState<any>(null);
    const [isGoogleConnected, setIsGoogleConnected] = useState(false);
    const [isGoogleWizardOpen, setIsGoogleWizardOpen] = useState(false);

    // Combined state
    const [combinedStats, setCombinedStats] = useState<any>(null);

    // UI state
    const [activeTab, setActiveTab] = useState<'campaigns' | 'ads'>('campaigns');
    const [deploymentConfig, setDeploymentConfig] = useState<any>(null);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        loadAllStats();

        // Handle OAuth errors and successes from URL parameters
        const error = searchParams.get('error');
        const success = searchParams.get('success');
        const platform = searchParams.get('platform');

        if (error) {
            const errorMessages: Record<string, string> = {
                'missing_tenant': t('marketing.errors.missing_tenant'),
                'auth_failed': t('marketing.errors.auth_failed'),
                'token_exchange_failed': t('marketing.errors.token_exchange_failed'),
                'google_auth_failed': t('marketing_google.errors.auth_failed'),
                'google_token_exchange_failed': t('marketing_google.errors.token_exchange_failed'),
                'google_auth_error': t('marketing_google.errors.init_failed')
            };
            alert(errorMessages[error] || `${t('common.error')}: ${error}`);
            const newParams = new URLSearchParams(searchParams);
            newParams.delete('error');
            setSearchParams(newParams);
        }

        if (success === 'connected' && platform === 'meta') {
            setIsMetaWizardOpen(true);
            const newParams = new URLSearchParams(searchParams);
            newParams.delete('success');
            newParams.delete('platform');
            setSearchParams(newParams);
        }

        if (success === 'google_connected') {
            setIsGoogleWizardOpen(true);
            const newParams = new URLSearchParams(searchParams);
            newParams.delete('success');
            newParams.delete('platform');
            setSearchParams(newParams);
        }

        // Auto-reconnect from banner
        if (searchParams.get('reconnect') === 'true') {
            handleConnectMeta();
            const newParams = new URLSearchParams(searchParams);
            newParams.delete('reconnect');
            setSearchParams(newParams);
        }
    }, [searchParams, timeRange]);

    const loadAllStats = async () => {
        setIsLoading(true);
        try {
            // Load Meta stats
            await loadMetaStats();

            // Load Google stats
            await loadGoogleStats();

            // Load combined stats
            await loadCombinedStats();

            // Load deployment config
            try {
                const configResponse = await api.get('/admin/config/deployment');
                setDeploymentConfig(configResponse.data);
            } catch (configError) {
                console.warn("[MarketingHub] Could not load deployment config:", configError);
            }
        } catch (error) {
            console.error("Error loading marketing stats:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const loadMetaStats = async () => {
        try {
            const { data } = await api.get(`/admin/marketing/stats?range=${timeRange}`);
            console.log("[MarketingHub] Meta stats loaded:", data);
            setMetaStats(data);
            setIsMetaConnected(data?.is_connected || false);
        } catch (error) {
            console.error("Error loading Meta stats:", error);
            setMetaStats(null);
            setIsMetaConnected(false);
        }
    };

    const loadGoogleStats = async () => {
        try {
            const metrics = await GoogleAdsApi.getMetrics(timeRange);
            console.log("[MarketingHub] Google stats loaded:", metrics);
            setGoogleStats(metrics);
            setIsGoogleConnected(metrics?.is_connected || false);
        } catch (error) {
            console.error("Error loading Google stats:", error);
            setGoogleStats(null);
            setIsGoogleConnected(false);
        }
    };

    const loadCombinedStats = async () => {
        try {
            const stats = await GoogleAdsApi.getCombinedStats(timeRange);
            console.log("[MarketingHub] Combined stats loaded:", stats);
            setCombinedStats(stats);
        } catch (error) {
            console.error("Error loading combined stats:", error);
            setCombinedStats(null);
        }
    };

    const handleConnectMeta = async () => {
        try {
            const tenantId = getCurrentTenantId();
            const { data } = await api.get(`/admin/marketing/meta-auth/url?state=tenant_${tenantId}`);
            if (data?.url) {
                window.location.href = data.url;
            }
        } catch (error) {
            console.error("Error initiating Meta OAuth:", error);
            alert(t('marketing.errors.init_failed'));
        }
    };

    const handleConnectGoogle = async () => {
        try {
            const tenantId = getCurrentTenantId();
            const { data } = await api.get(`/admin/auth/google/ads/url?state=tenant_${tenantId}_ads`);
            if (data?.url) {
                window.open(data.url, '_blank', 'width=600,height=700');
            } else {
                throw new Error(t('marketing_google.errors.no_auth_url'));
            }
        } catch (error: any) {
            console.error("Error initiating Google OAuth:", error);
            alert(error.response?.data?.detail || error.message || t('common.error'));
        }
    };

    const handleSyncGoogleData = async () => {
        try {
            const result = await GoogleAdsApi.syncData();
            if (result.success) {
                alert(t('marketing_google.sync.success'));
                await loadGoogleStats();
                await loadCombinedStats();
            } else {
                alert(`${t('marketing_google.sync.error')}: ${result.message}`);
            }
        } catch (error) {
            console.error("Error syncing Google data:", error);
            alert(t('marketing_google.sync.error'));
        }
    };

    const renderConnectionBanner = () => {
        if (activePlatform === 'meta') {
            if (isMetaConnected) {
                return (
                    <div className="mb-6 rounded-lg bg-green-50 p-4 border border-green-200">
                        <div className="flex items-center">
                            <div className="flex-shrink-0">
                                <Megaphone className="h-5 w-5 text-green-600" />
                            </div>
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-green-800">
                                    {t('marketing.connected_active')}
                                </h3>
                                <div className="mt-1 text-sm text-green-700">
                                    <p>{t('marketing.connected_desc')}</p>
                                </div>
                            </div>
                            <div className="ml-auto">
                                <button
                                    onClick={() => setIsMetaWizardOpen(true)}
                                    className="text-sm font-medium text-green-700 hover:text-green-600"
                                >
                                    {t('marketing.reconnect')}
                                </button>
                            </div>
                        </div>
                    </div>
                );
            } else {
                return (
                    <div className="mb-6 rounded-lg bg-yellow-50 p-4 border border-yellow-200">
                        <div className="flex items-center">
                            <div className="flex-shrink-0">
                                <Megaphone className="h-5 w-5 text-yellow-600" />
                            </div>
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-yellow-800">
                                    {t('marketing.connected_disconnected')}
                                </h3>
                                <div className="mt-1 text-sm text-yellow-700">
                                    <p>{t('marketing.disconnected_desc')}</p>
                                </div>
                            </div>
                            <div className="ml-auto">
                                <button
                                    onClick={() => setIsMetaWizardOpen(true)}
                                    className="inline-flex items-center rounded-md bg-yellow-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-yellow-500"
                                >
                                    {t('marketing.connect')}
                                </button>
                            </div>
                        </div>
                    </div>
                );
            }
        } else if (activePlatform === 'google') {
            if (isGoogleConnected) {
                return (
                    <div className="mb-6 rounded-lg bg-blue-50 p-4 border border-blue-200">
                        <div className="flex items-center">
                            <div className="flex-shrink-0">
                                <Globe className="h-5 w-5 text-blue-600" />
                            </div>
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-blue-800">
                                    {t('marketing_google.connected_active')}
                                </h3>
                                <div className="mt-1 text-sm text-blue-700">
                                    <p>{t('marketing_google.connected_desc')}</p>
                                    {googleStats?.is_demo && (
                                        <p className="mt-1 font-medium">
                                            {t('marketing_google.demo_data_notice')}
                                        </p>
                                    )}
                                </div>
                            </div>
                            <div className="ml-auto flex space-x-2">
                                <button
                                    onClick={handleSyncGoogleData}
                                    className="text-sm font-medium text-blue-700 hover:text-blue-600"
                                >
                                    {t('marketing_google.sync.button')}
                                </button>
                                <button
                                    onClick={() => setIsGoogleWizardOpen(true)}
                                    className="text-sm font-medium text-blue-700 hover:text-blue-600"
                                >
                                    {t('marketing_google.reconnect')}
                                </button>
                            </div>
                        </div>
                    </div>
                );
            } else {
                return (
                    <div className="mb-6 rounded-lg bg-yellow-50 p-4 border border-yellow-200">
                        <div className="flex items-center">
                            <div className="flex-shrink-0">
                                <Globe className="h-5 w-5 text-yellow-600" />
                            </div>
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-yellow-800">
                                    {t('marketing_google.connected_disconnected')}
                                </h3>
                                <div className="mt-1 text-sm text-yellow-700">
                                    <p>{t('marketing_google.disconnected_desc')}</p>
                                </div>
                            </div>
                            <div className="ml-auto">
                                <button
                                    onClick={() => setIsGoogleWizardOpen(true)}
                                    className="inline-flex items-center rounded-md bg-yellow-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-yellow-500"
                                >
                                    {t('marketing_google.connect')}
                                </button>
                            </div>
                        </div>
                    </div>
                );
            }
        } else if (activePlatform === 'combined') {
            const hasAnyConnection = isMetaConnected || isGoogleConnected;

            if (hasAnyConnection) {
                const connectedPlatforms = [];
                if (isMetaConnected) connectedPlatforms.push('Meta Ads');
                if (isGoogleConnected) connectedPlatforms.push('Google Ads');

                return (
                    <div className="mb-6 rounded-lg bg-purple-50 p-4 border border-purple-200">
                        <div className="flex items-center">
                            <div className="flex-shrink-0">
                                <BarChart3 className="h-5 w-5 text-purple-600" />
                            </div>
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-purple-800">
                                    {t('marketing_google.combined_stats.title')}
                                </h3>
                                <div className="mt-1 text-sm text-purple-700">
                                    <p>
                                        {t('marketing_google.combined_stats.description')} -
                                        Conectado a: {connectedPlatforms.join(', ')}
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            } else {
                return (
                    <div className="mb-6 rounded-lg bg-gray-50 p-4 border border-gray-200">
                        <div className="flex items-center">
                            <div className="flex-shrink-0">
                                <BarChart3 className="h-5 w-5 text-gray-600" />
                            </div>
                            <div className="ml-3">
                                <h3 className="text-sm font-medium text-gray-800">
                                    {t('marketing_google.combined_stats.title')}
                                </h3>
                                <div className="mt-1 text-sm text-gray-700">
                                    <p>{t('marketing_google.combined_stats.description')}</p>
                                    <p className="mt-1">Conecta al menos una plataforma para ver estadísticas combinadas.</p>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            }
        }
    };

    const renderPlatformContent = () => {
        switch (activePlatform) {
            case 'meta':
                return (
                    <div className="space-y-6">
                        {metaStats && (
                            <MarketingPerformanceCard
                                investment={metaStats.roi?.total_spend || 0}
                                return={metaStats.roi?.total_revenue || 0}
                                patients={metaStats.roi?.patients_converted || 0}
                                currency={metaStats.roi?.currency || 'ARS'}
                                timeRange={timeRange}
                            />
                        )}

                        {/* Sub-tabs: Campañas / Creativos */}
                        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
                            {/* Tab bar */}
                            <div className="border-b border-gray-200 px-4">
                                <nav className="-mb-px flex space-x-6">
                                    <button
                                        onClick={() => setActiveTab('campaigns')}
                                        className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === 'campaigns'
                                                ? 'border-blue-500 text-blue-600'
                                                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                            }`}
                                    >
                                        📢 {t('marketing.tabs.campaigns')}
                                    </button>
                                    <button
                                        onClick={() => setActiveTab('ads')}
                                        className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === 'ads'
                                                ? 'border-blue-500 text-blue-600'
                                                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                            }`}
                                    >
                                        🎨 {t('marketing.tabs.creatives')}
                                    </button>
                                </nav>
                            </div>

                            {/* Tab content */}
                            <div className="p-4">
                                {activeTab === 'campaigns' ? (
                                    <>
                                        <p className="text-xs text-gray-400 mb-3">{t('marketing.sorted_by_leads')}</p>
                                        {metaStats?.campaigns?.length > 0 ? (
                                            <div className="overflow-x-auto">
                                                <table className="min-w-full divide-y divide-gray-200">
                                                    <thead className="bg-gray-50">
                                                        <tr>
                                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_campaign_ad')}</th>
                                                            <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_spend')}</th>
                                                            <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_leads')}</th>
                                                            <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_patients')}</th>
                                                            <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_appts')}</th>
                                                            <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_roi')}</th>
                                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_status')}</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody className="divide-y divide-gray-200">
                                                        {[...metaStats.campaigns]
                                                            .sort((a: any, b: any) => (b.leads || 0) - (a.leads || 0))
                                                            .map((campaign: any, index: number) => (
                                                                <tr key={index} className="hover:bg-gray-50">
                                                                    <td className="px-3 py-4 text-sm font-medium text-gray-900 max-w-xs">
                                                                        <div className="truncate">{campaign.campaign_name || campaign.ad_name || '—'}</div>
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-700 text-right">
                                                                        ${campaign.spend?.toLocaleString('es-AR', { minimumFractionDigits: 2 }) || '0.00'}
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap text-right">
                                                                        <span className={`inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 rounded-full text-xs font-bold ${(campaign.leads || 0) > 0 ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-500'
                                                                            }`}>
                                                                            {campaign.leads || 0}
                                                                        </span>
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap text-right">
                                                                        <span className={`inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 rounded-full text-xs font-bold ${(campaign.patients_converted || 0) > 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-500'
                                                                            }`}>
                                                                            {campaign.patients_converted || 0}
                                                                        </span>
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-700 text-right">{campaign.appointments || 0}</td>
                                                                    <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-700 text-right">
                                                                        {campaign.roi ? `${campaign.roi.toFixed(2)}%` : '0.00%'}
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap">
                                                                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${campaign.status === 'active' ? 'bg-green-100 text-green-800' :
                                                                                campaign.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
                                                                                    'bg-gray-100 text-gray-800'
                                                                            }`}>
                                                                            {campaign.status === 'active' ? 'Activo' :
                                                                                campaign.status === 'paused' ? 'Pausado' :
                                                                                    campaign.status || 'Desconocido'}
                                                                        </span>
                                                                    </td>
                                                                </tr>
                                                            ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        ) : (
                                            <p className="text-gray-500 text-center py-8">{t('marketing.no_campaigns')}</p>
                                        )}
                                    </>
                                ) : (
                                    <>
                                        <p className="text-xs text-gray-400 mb-3">{t('marketing.sorted_by_leads')}</p>
                                        {metaStats?.ads?.length > 0 ? (
                                            <div className="overflow-x-auto">
                                                <table className="min-w-full divide-y divide-gray-200">
                                                    <thead className="bg-gray-50">
                                                        <tr>
                                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_ad')}</th>
                                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_campaign_name')}</th>
                                                            <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_spend')}</th>
                                                            <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_leads')}</th>
                                                            <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_patients')}</th>
                                                            <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_roi')}</th>
                                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">{t('marketing.table_status')}</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody className="divide-y divide-gray-200">
                                                        {[...metaStats.ads]
                                                            .sort((a: any, b: any) => (b.leads || 0) - (a.leads || 0))
                                                            .map((ad: any, index: number) => (
                                                                <tr key={index} className="hover:bg-gray-50">
                                                                    <td className="px-3 py-4 text-sm font-medium text-gray-900 max-w-[200px]">
                                                                        <div className="truncate">{ad.ad_name || '—'}</div>
                                                                    </td>
                                                                    <td className="px-3 py-4 text-sm text-gray-500 max-w-[160px]">
                                                                        <div className="truncate">{ad.campaign_name || '—'}</div>
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-700 text-right">
                                                                        ${ad.spend?.toLocaleString('es-AR', { minimumFractionDigits: 2 }) || '0.00'}
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap text-right">
                                                                        <span className={`inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 rounded-full text-xs font-bold ${(ad.leads || 0) > 0 ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-500'
                                                                            }`}>
                                                                            {ad.leads || 0}
                                                                        </span>
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap text-right">
                                                                        <span className={`inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 rounded-full text-xs font-bold ${(ad.patients_converted || 0) > 0 ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-100 text-gray-500'
                                                                            }`}>
                                                                            {ad.patients_converted || 0}
                                                                        </span>
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-700 text-right">
                                                                        {ad.roi ? `${ad.roi.toFixed(2)}%` : '0.00%'}
                                                                    </td>
                                                                    <td className="px-3 py-4 whitespace-nowrap">
                                                                        <span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${ad.status === 'active' ? 'bg-green-100 text-green-800' :
                                                                                ad.status === 'paused' ? 'bg-yellow-100 text-yellow-800' :
                                                                                    'bg-gray-100 text-gray-800'
                                                                            }`}>
                                                                            {ad.status === 'active' ? 'Activo' :
                                                                                ad.status === 'paused' ? 'Pausado' :
                                                                                    ad.status || 'Desconocido'}
                                                                        </span>
                                                                    </td>
                                                                </tr>
                                                            ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        ) : (
                                            <p className="text-gray-500 text-center py-8">{t('marketing.no_data')}</p>
                                        )}
                                    </>
                                )}
                            </div>
                        </div>
                    </div>
                );

            case 'google':
                return (
                    <div className="space-y-6">
                        {googleStats && (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.impressions')}
                                    </h4>
                                    <p className="mt-2 text-2xl font-semibold text-gray-900">
                                        {GoogleAdsApi.formatNumber(googleStats.impressions || 0)}
                                    </p>
                                </div>
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.clicks')}
                                    </h4>
                                    <p className="mt-2 text-2xl font-semibold text-gray-900">
                                        {GoogleAdsApi.formatNumber(googleStats.clicks || 0)}
                                    </p>
                                </div>
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.cost')}
                                    </h4>
                                    <p className="mt-2 text-2xl font-semibold text-gray-900">
                                        {GoogleAdsApi.formatCurrency(googleStats.cost || 0, googleStats.currency)}
                                    </p>
                                </div>
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.conversions')}
                                    </h4>
                                    <p className="mt-2 text-2xl font-semibold text-gray-900">
                                        {GoogleAdsApi.formatNumber(googleStats.conversions || 0)}
                                    </p>
                                </div>
                            </div>
                        )}

                        {/* Google campaigns table would go here */}
                        <div className="rounded-lg border border-gray-200 bg-white p-4">
                            <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                {t('marketing_google.active_campaigns')}
                            </h3>
                            {googleStats?.campaign_count > 0 ? (
                                <div className="overflow-x-auto">
                                    <table className="min-w-full divide-y divide-gray-200">
                                        <thead>
                                            <tr>
                                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {t('marketing_google.table_campaign')}
                                                </th>
                                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {t('marketing_google.table_type')}
                                                </th>
                                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {t('marketing_google.table_status')}
                                                </th>
                                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {t('marketing_google.table_cost')}
                                                </th>
                                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {t('marketing_google.table_conversions')}
                                                </th>
                                                <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                    {t('marketing_google.table_roas')}
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-gray-200">
                                            {/* Demo campaigns - in real implementation, fetch from API */}
                                            <tr>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    Clínica Dental - Búsqueda Branded
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    {t('marketing_google.type.search')}
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap">
                                                    <span className="inline-flex rounded-full px-2 text-xs font-semibold leading-5 bg-green-100 text-green-800">
                                                        {t('marketing_google.status.enabled')}
                                                    </span>
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    $42.00
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    12
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    5.71
                                                </td>
                                            </tr>
                                            <tr>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    Ortodoncia - Display Remarketing
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    {t('marketing_google.type.display')}
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap">
                                                    <span className="inline-flex rounded-full px-2 text-xs font-semibold leading-5 bg-green-100 text-green-800">
                                                        {t('marketing_google.status.enabled')}
                                                    </span>
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    $28.00
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    8
                                                </td>
                                                <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                    5.71
                                                </td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            ) : (
                                <p className="text-gray-500 text-center py-4">
                                    {t('marketing_google.no_campaigns')}
                                </p>
                            )}
                        </div>
                    </div>
                );

            case 'combined':
                return (
                    <div className="space-y-6">
                        {combinedStats && (
                            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.combined_stats.total_impressions')}
                                    </h4>
                                    <p className="mt-2 text-2xl font-semibold text-gray-900">
                                        {GoogleAdsApi.formatNumber(combinedStats.combined?.total_impressions || 0)}
                                    </p>
                                </div>
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.combined_stats.total_clicks')}
                                    </h4>
                                    <p className="mt-2 text-2xl font-semibold text-gray-900">
                                        {GoogleAdsApi.formatNumber(combinedStats.combined?.total_clicks || 0)}
                                    </p>
                                </div>
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.combined_stats.total_cost')}
                                    </h4>
                                    <p className="mt-2 text-2xl font-semibold text-gray-900">
                                        {GoogleAdsApi.formatCurrency(combinedStats.combined?.total_cost || 0, 'ARS')}
                                    </p>
                                </div>
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.combined_stats.total_conversions')}
                                    </h4>
                                    <p className="mt-2 text-2xl font-semibold text-gray-900">
                                        {GoogleAdsApi.formatNumber(combinedStats.combined?.total_conversions || 0)}
                                    </p>
                                </div>
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.combined_stats.total_revenue')}
                                    </h4>
                                    <p className="mt-2 text-2xl font-semibold text-gray-900">
                                        {GoogleAdsApi.formatCurrency(combinedStats.combined?.total_conversions_value || 0, 'ARS')}
                                    </p>
                                </div>
                                <div className="rounded-lg border border-gray-200 bg-white p-4">
                                    <h4 className="text-sm font-medium text-gray-900">
                                        {t('marketing_google.combined_stats.platform_distribution')}
                                    </h4>
                                    <p className="mt-2 text-lg font-semibold text-gray-900">
                                        {combinedStats.combined?.platforms?.join(', ') || 'Ninguna'}
                                    </p>
                                </div>
                            </div>
                        )}

                        <div className="rounded-lg border border-gray-200 bg-white p-4">
                            <h3 className="text-lg font-semibold text-gray-900 mb-4">
                                Comparación de Plataformas
                            </h3>
                            <div className="overflow-x-auto">
                                <table className="min-w-full divide-y divide-gray-200">
                                    <thead>
                                        <tr>
                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Plataforma
                                            </th>
                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Estado
                                            </th>
                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Inversión
                                            </th>
                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                Ingresos
                                            </th>
                                            <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                                                ROI
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-gray-200">
                                        <tr>
                                            <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                <div className="flex items-center">
                                                    <Megaphone className="h-4 w-4 mr-2 text-blue-600" />
                                                    Meta Ads
                                                </div>
                                            </td>
                                            <td className="px-3 py-4 whitespace-nowrap">
                                                <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${isMetaConnected ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                                    }`}>
                                                    {isMetaConnected ? 'Conectado' : 'Desconectado'}
                                                </span>
                                            </td>
                                            <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                ${metaStats?.roi?.total_spend?.toLocaleString('es-AR', { minimumFractionDigits: 2 }) || '0.00'}
                                            </td>
                                            <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                ${metaStats?.roi?.total_revenue?.toLocaleString('es-AR', { minimumFractionDigits: 2 }) || '0.00'}
                                            </td>
                                            <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                {metaStats?.roi?.total_spend > 0
                                                    ? `${((metaStats.roi.total_revenue / metaStats.roi.total_spend) * 100).toFixed(2)}%`
                                                    : '0.00%'}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                <div className="flex items-center">
                                                    <Globe className="h-4 w-4 mr-2 text-red-600" />
                                                    Google Ads
                                                </div>
                                            </td>
                                            <td className="px-3 py-4 whitespace-nowrap">
                                                <span className={`inline-flex rounded-full px-2 text-xs font-semibold leading-5 ${isGoogleConnected ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                                                    }`}>
                                                    {isGoogleConnected ? 'Conectado' : 'Desconectado'}
                                                </span>
                                            </td>
                                            <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                {GoogleAdsApi.formatCurrency(googleStats?.cost || 0, googleStats?.currency)}
                                            </td>
                                            <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                {GoogleAdsApi.formatCurrency(googleStats?.conversions_value || 0, googleStats?.currency)}
                                            </td>
                                            <td className="px-3 py-4 whitespace-nowrap text-sm text-gray-900">
                                                {googleStats?.roas ? `${googleStats.roas.toFixed(2)}` : '0.00'}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="min-h-screen bg-gray-50">
            <PageHeader
                title={activePlatform === 'combined'
                    ? t('marketing_google.combined_stats.title')
                    : activePlatform === 'google'
                        ? t('marketing_google.title')
                        : t('nav.marketing')}
                subtitle={activePlatform === 'combined'
                    ? t('marketing_google.combined_stats.description')
                    : activePlatform === 'google'
                        ? t('marketing_google.subtitle')
                        : t('marketing.subtitle')}
                icon={activePlatform === 'combined' ? <BarChart3 className="w-6 h-6" /> : activePlatform === 'google' ? <Globe className="w-6 h-6" /> : <Megaphone className="w-6 h-6" />}
            />

            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6">
                {/* Platform selector */}
                <div className="mb-6">
                    <div className="border-b border-gray-200">
                        <nav className="-mb-px flex space-x-8">
                            <button
                                onClick={() => setActivePlatform('meta')}
                                className={`py-2 px-1 border-b-2 font-medium text-sm ${activePlatform === 'meta'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                    }`}
                            >
                                <div className="flex items-center">
                                    <Megaphone className="h-4 w-4 mr-2" />
                                    {t('marketing_google.platform_tabs.meta')}
                                </div>
                            </button>
                            <button
                                onClick={() => setActivePlatform('google')}
                                className={`py-2 px-1 border-b-2 font-medium text-sm ${activePlatform === 'google'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                    }`}
                            >
                                <div className="flex items-center">
                                    <Globe className="h-4 w-4 mr-2" />
                                    {t('marketing_google.platform_tabs.google')}
                                </div>
                            </button>
                            <button
                                onClick={() => setActivePlatform('combined')}
                                className={`py-2 px-1 border-b-2 font-medium text-sm ${activePlatform === 'combined'
                                    ? 'border-blue-500 text-blue-600'
                                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                                    }`}
                            >
                                <div className="flex items-center">
                                    <BarChart3 className="h-4 w-4 mr-2" />
                                    {t('marketing_google.platform_tabs.combined')}
                                </div>
                            </button>
                        </nav>
                    </div>
                </div>

                {/* Time range selector */}
                <div className="mb-6 flex justify-between items-center">
                    <div className="flex space-x-2">
                        <button
                            onClick={() => setTimeRange('last_30d')}
                            className={`px-3 py-1 text-sm rounded-md ${timeRange === 'last_30d'
                                ? 'bg-blue-100 text-blue-700 font-medium'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            {t('marketing.range_30d')}
                        </button>
                        <button
                            onClick={() => setTimeRange('last_90d')}
                            className={`px-3 py-1 text-sm rounded-md ${timeRange === 'last_90d'
                                ? 'bg-blue-100 text-blue-700 font-medium'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            {t('marketing.range_90d')}
                        </button>
                        <button
                            onClick={() => setTimeRange('this_year')}
                            className={`px-3 py-1 text-sm rounded-md ${timeRange === 'this_year'
                                ? 'bg-blue-100 text-blue-700 font-medium'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            {t('marketing.range_year')}
                        </button>
                        <button
                            onClick={() => setTimeRange('all')}
                            className={`px-3 py-1 text-sm rounded-md ${timeRange === 'all'
                                ? 'bg-blue-100 text-blue-700 font-medium'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            {t('marketing.range_all')}
                        </button>
                    </div>

                    <button
                        onClick={loadAllStats}
                        disabled={isLoading}
                        className="inline-flex items-center px-3 py-1 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                    >
                        <RefreshCw className={`h-4 w-4 mr-1 ${isLoading ? 'animate-spin' : ''}`} />
                        {isLoading ? t('common.loading') : 'Actualizar'}
                    </button>
                </div>

                {/* Connection banner */}
                {renderConnectionBanner()}

                {/* Platform content */}
                {renderPlatformContent()}

                {/* Wizards */}
                <MetaConnectionWizard
                    isOpen={isMetaWizardOpen}
                    onClose={() => setIsMetaWizardOpen(false)}
                    onConnected={() => {
                        loadMetaStats();
                        loadCombinedStats();
                    }}
                />

                <GoogleConnectionWizard
                    isOpen={isGoogleWizardOpen}
                    onClose={() => setIsGoogleWizardOpen(false)}
                    onConnected={() => {
                        loadGoogleStats();
                        loadCombinedStats();
                    }}
                />
            </div>
        </div>
    );
}