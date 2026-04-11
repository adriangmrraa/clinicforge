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
import GlassCard, { CARD_IMAGES } from '../components/GlassCard';

type Platform = 'meta' | 'google' | 'combined';
type TimeRange = 'last_30d' | 'last_90d' | 'this_year' | 'lifetime' | 'all';

export default function MarketingHubView() {
    const { t } = useTranslation();
    const [searchParams, setSearchParams] = useSearchParams();

    // State for all platforms
    const [activePlatform, setActivePlatform] = useState<Platform>('meta');
    const [timeRange, setTimeRange] = useState<TimeRange>('all');

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
            // Load all platform stats simultaneously
            await Promise.allSettled([
                loadMetaStats(),
                loadGoogleStats(),
                loadCombinedStats()
            ]);

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
                window.open(data.url, '_blank', 'noopener,noreferrer,width=600,height=700');
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
                    <div className="mb-4 rounded-lg bg-green-500/10 px-3 py-2 border border-green-500/20">
                        <div className="flex items-center">
                            <Megaphone className="h-4 w-4 text-green-400 shrink-0" />
                            <span className="ml-2 text-xs font-medium text-green-400">{t('marketing.connected_active')}</span>
                            <button
                                onClick={() => setIsMetaWizardOpen(true)}
                                className="ml-auto text-xs font-medium text-green-400 hover:text-green-300"
                            >
                                {t('marketing.reconnect')}
                            </button>
                        </div>
                    </div>
                );
            } else {
                return (
                    <div className="mb-4 rounded-lg bg-yellow-500/10 px-3 py-2 border border-yellow-500/20">
                        <div className="flex items-center">
                            <Megaphone className="h-4 w-4 text-yellow-400 shrink-0" />
                            <span className="ml-2 text-xs font-medium text-yellow-400">{t('marketing.connected_disconnected')}</span>
                            <button
                                onClick={() => setIsMetaWizardOpen(true)}
                                className="ml-auto inline-flex items-center rounded-md bg-yellow-500 px-2 py-1 text-xs font-semibold text-[#0a0e1a] hover:bg-yellow-400"
                            >
                                {t('marketing.connect')}
                            </button>
                        </div>
                    </div>
                );
            }
        } else if (activePlatform === 'google') {
            if (isGoogleConnected) {
                return (
                    <div className="mb-4 rounded-lg bg-blue-500/10 px-3 py-2 border border-blue-500/20">
                        <div className="flex items-center flex-wrap gap-1">
                            <Globe className="h-4 w-4 text-blue-400 shrink-0" />
                            <span className="ml-1 text-xs font-medium text-blue-400">{t('marketing_google.connected_active')}</span>
                            {googleStats?.is_demo && (
                                <span className="text-[10px] font-medium text-blue-400/60 ml-1">({t('marketing_google.demo_data_notice')})</span>
                            )}
                            <div className="ml-auto flex space-x-2">
                                <button
                                    onClick={handleSyncGoogleData}
                                    className="text-xs font-medium text-blue-400 hover:text-blue-300"
                                >
                                    {t('marketing_google.sync.button')}
                                </button>
                                <button
                                    onClick={() => setIsGoogleWizardOpen(true)}
                                    className="text-xs font-medium text-blue-400 hover:text-blue-300"
                                >
                                    {t('marketing_google.reconnect')}
                                </button>
                            </div>
                        </div>
                    </div>
                );
            } else {
                return (
                    <div className="mb-4 rounded-lg bg-yellow-500/10 px-3 py-2 border border-yellow-500/20">
                        <div className="flex items-center">
                            <Globe className="h-4 w-4 text-yellow-400 shrink-0" />
                            <span className="ml-2 text-xs font-medium text-yellow-400">{t('marketing_google.connected_disconnected')}</span>
                            <button
                                onClick={() => setIsGoogleWizardOpen(true)}
                                className="ml-auto inline-flex items-center rounded-md bg-yellow-500 px-2 py-1 text-xs font-semibold text-[#0a0e1a] hover:bg-yellow-400"
                            >
                                {t('marketing_google.connect')}
                            </button>
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
                    <div className="mb-4 rounded-lg bg-purple-500/10 px-3 py-2 border border-purple-500/20">
                        <div className="flex items-center">
                            <BarChart3 className="h-4 w-4 text-purple-400 shrink-0" />
                            <span className="ml-2 text-xs font-medium text-purple-400">
                                {t('marketing_google.combined_stats.title')} — {connectedPlatforms.join(', ')}
                            </span>
                        </div>
                    </div>
                );
            } else {
                return (
                    <div className="mb-4 rounded-lg bg-white/[0.02] px-3 py-2 border border-white/[0.06]">
                        <div className="flex items-center">
                            <BarChart3 className="h-4 w-4 text-white/60 shrink-0" />
                            <span className="ml-2 text-xs font-medium text-white">
                                {t('marketing_google.combined_stats.title')} — Conecta al menos una plataforma
                            </span>
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

                        {/* Sub-tabs: Campanas / Creativos */}
                        <GlassCard image={CARD_IMAGES.marketing} hoverScale={false} className="overflow-hidden">
                            {/* Tab bar */}
                            <div className="border-b border-white/[0.06] px-4">
                                <nav className="-mb-px flex space-x-6">
                                    <button
                                        onClick={() => setActiveTab('campaigns')}
                                        className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === 'campaigns'
                                            ? 'border-blue-500 text-blue-400'
                                            : 'border-transparent text-white/40 hover:text-white/60 hover:border-white/[0.1]'
                                            }`}
                                    >
                                        📢 {t('marketing.tabs.campaigns')}
                                    </button>
                                    <button
                                        onClick={() => setActiveTab('ads')}
                                        className={`py-3 px-1 border-b-2 font-medium text-sm transition-colors ${activeTab === 'ads'
                                            ? 'border-blue-500 text-blue-400'
                                            : 'border-transparent text-white/40 hover:text-white/60 hover:border-white/[0.1]'
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
                                        <p className="text-xs text-white/30 mb-3">{t('marketing.sorted_by_leads')}</p>
                                        {metaStats?.campaigns?.campaigns?.length > 0 ? (
                                            <div className="space-y-3">
                                                {[...(metaStats?.campaigns?.campaigns || [])]
                                                    .sort((a: any, b: any) => (b.leads || 0) - (a.leads || 0))
                                                    .map((campaign: any, index: number) => (
                                                        <div key={index} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3 sm:p-4 hover:border-blue-500/30 transition-colors">
                                                            <div className="flex items-start justify-between gap-2 mb-3">
                                                                <div className="min-w-0 flex-1">
                                                                    <h4 className="text-sm font-semibold text-white truncate">{campaign.campaign_name || campaign.ad_name || '—'}</h4>
                                                                    <p className="text-xs text-white/30 mt-0.5">${campaign.spend?.toLocaleString('es-AR', { minimumFractionDigits: 0 }) || '0'} invertidos</p>
                                                                </div>
                                                                <span className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${campaign.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : campaign.status === 'paused' ? 'bg-amber-500/10 text-amber-400' : 'bg-white/[0.04] text-white/60'}`}>
                                                                    {campaign.status === 'active' ? '● Activo' : campaign.status === 'paused' ? '⏸ Pausado' : campaign.status || '—'}
                                                                </span>
                                                            </div>
                                                            <div className="grid grid-cols-3 gap-2">
                                                                <div className="text-center bg-blue-500/10 rounded-lg py-2">
                                                                    <p className="text-lg sm:text-xl font-bold text-blue-400">{campaign.leads || 0}</p>
                                                                    <p className="text-[10px] text-blue-400/60 font-medium">Leads</p>
                                                                </div>
                                                                <div className="text-center bg-emerald-500/10 rounded-lg py-2">
                                                                    <p className="text-lg sm:text-xl font-bold text-emerald-400">{campaign.patients_converted || 0}</p>
                                                                    <p className="text-[10px] text-emerald-400/60 font-medium">Pacientes</p>
                                                                </div>
                                                                <div className="text-center bg-white/[0.04] rounded-lg py-2">
                                                                    <p className="text-lg sm:text-xl font-bold text-white/60">{campaign.roi ? `${campaign.roi.toFixed(0)}%` : '0%'}</p>
                                                                    <p className="text-[10px] text-white/40 font-medium">ROI</p>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ))}
                                            </div>
                                        ) : (
                                            <p className="text-white/40 text-center py-8">{t('marketing.no_campaigns')}</p>
                                        )}
                                    </>
                                ) : (
                                    <>
                                        <p className="text-xs text-white/30 mb-3">{t('marketing.sorted_by_leads')}</p>
                                        {metaStats?.campaigns?.creatives?.length > 0 ? (
                                            <div className="space-y-3">
                                                {[...(metaStats?.campaigns?.creatives || [])]
                                                    .sort((a: any, b: any) => (b.leads || 0) - (a.leads || 0))
                                                    .map((ad: any, index: number) => (
                                                        <div key={index} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-3 sm:p-4 hover:border-blue-500/30 transition-colors">
                                                            <div className="flex items-start justify-between gap-2 mb-3">
                                                                <div className="min-w-0 flex-1">
                                                                    <h4 className="text-sm font-semibold text-white truncate">{ad.ad_name || '—'}</h4>
                                                                    <p className="text-[11px] text-white/30 truncate mt-0.5">{ad.campaign_name || '—'}</p>
                                                                    <p className="text-xs text-white/40 mt-0.5">${ad.spend?.toLocaleString('es-AR', { minimumFractionDigits: 0 }) || '0'} invertidos</p>
                                                                </div>
                                                                <span className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${ad.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : ad.status === 'paused' ? 'bg-amber-500/10 text-amber-400' : 'bg-white/[0.04] text-white/60'}`}>
                                                                    {ad.status === 'active' ? '● Activo' : ad.status === 'paused' ? '⏸ Pausado' : ad.status || '—'}
                                                                </span>
                                                            </div>
                                                            <div className="grid grid-cols-3 gap-2">
                                                                <div className="text-center bg-blue-500/10 rounded-lg py-2">
                                                                    <p className="text-lg sm:text-xl font-bold text-blue-400">{ad.leads || 0}</p>
                                                                    <p className="text-[10px] text-blue-400/60 font-medium">Leads</p>
                                                                </div>
                                                                <div className="text-center bg-emerald-500/10 rounded-lg py-2">
                                                                    <p className="text-lg sm:text-xl font-bold text-emerald-400">{ad.patients_converted || 0}</p>
                                                                    <p className="text-[10px] text-emerald-400/60 font-medium">Pacientes</p>
                                                                </div>
                                                                <div className="text-center bg-white/[0.04] rounded-lg py-2">
                                                                    <p className="text-lg sm:text-xl font-bold text-white/60">{ad.roi ? `${ad.roi.toFixed(0)}%` : '0%'}</p>
                                                                    <p className="text-[10px] text-white/40 font-medium">ROI</p>
                                                                </div>
                                                            </div>
                                                        </div>
                                                    ))}
                                            </div>
                                        ) : (
                                            <p className="text-white/40 text-center py-8">{t('marketing.no_data')}</p>
                                        )}
                                    </>
                                )}
                            </div>
                        </GlassCard>
                    </div>
                );

            case 'google':
                return (
                    <div className="space-y-4">
                        {/* Google KPIs — same card style as Meta */}
                        {googleStats && (
                            <GlassCard image={CARD_IMAGES.marketing} hoverScale={false}>
                                <div className="p-4 sm:p-6">
                                    <div className="grid grid-cols-2 gap-3 mb-4">
                                        <div className="bg-blue-500/10 rounded-xl p-3 text-center">
                                            <p className="text-lg sm:text-2xl font-bold text-blue-400">{GoogleAdsApi.formatNumber(googleStats.impressions || 0)}</p>
                                            <p className="text-[10px] text-blue-400/60 font-semibold uppercase">Impresiones</p>
                                        </div>
                                        <div className="bg-indigo-500/10 rounded-xl p-3 text-center">
                                            <p className="text-lg sm:text-2xl font-bold text-indigo-400">{GoogleAdsApi.formatNumber(googleStats.clicks || 0)}</p>
                                            <p className="text-[10px] text-indigo-400/60 font-semibold uppercase">Clicks</p>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="bg-amber-500/10 rounded-xl p-3 text-center">
                                            <p className="text-lg sm:text-2xl font-bold text-amber-400">{GoogleAdsApi.formatCurrency(googleStats.cost || 0, googleStats.currency)}</p>
                                            <p className="text-[10px] text-amber-400/60 font-semibold uppercase">Costo</p>
                                        </div>
                                        <div className="bg-emerald-500/10 rounded-xl p-3 text-center">
                                            <p className="text-lg sm:text-2xl font-bold text-emerald-400">{GoogleAdsApi.formatNumber(googleStats.conversions || 0)}</p>
                                            <p className="text-[10px] text-emerald-400/60 font-semibold uppercase">Conversiones</p>
                                        </div>
                                    </div>
                                </div>
                            </GlassCard>
                        )}

                        {/* Google campaigns as cards */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider px-1">{t('marketing_google.active_campaigns')}</h3>
                            {googleStats?.campaigns?.length > 0 ? (
                                googleStats.campaigns.map((c: any, i: number) => (
                                    <GlassCard key={i} image={CARD_IMAGES.marketing}>
                                        <div className="p-3 sm:p-4">
                                            <div className="flex items-start justify-between gap-2 mb-3">
                                                <div className="min-w-0 flex-1">
                                                    <h4 className="text-sm font-semibold text-white truncate">{c.name || c.campaign_name || '—'}</h4>
                                                    <p className="text-xs text-white/30 mt-0.5">{c.type || 'Campaña'} · {GoogleAdsApi.formatCurrency(c.cost || c.spend || 0, googleStats.currency)}</p>
                                                </div>
                                                <span className={`shrink-0 inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${c.status === 'ENABLED' || c.status === 'active' ? 'bg-emerald-500/10 text-emerald-400' : 'bg-white/[0.04] text-white/60'}`}>
                                                    {c.status === 'ENABLED' || c.status === 'active' ? '● Activo' : c.status || '—'}
                                                </span>
                                            </div>
                                            <div className="grid grid-cols-3 gap-2">
                                                <div className="text-center bg-blue-500/10 rounded-lg py-2">
                                                    <p className="text-lg font-bold text-blue-400">{GoogleAdsApi.formatNumber(c.clicks || 0)}</p>
                                                    <p className="text-[10px] text-blue-400/60 font-medium">Clicks</p>
                                                </div>
                                                <div className="text-center bg-emerald-500/10 rounded-lg py-2">
                                                    <p className="text-lg font-bold text-emerald-400">{GoogleAdsApi.formatNumber(c.conversions || 0)}</p>
                                                    <p className="text-[10px] text-emerald-400/60 font-medium">Conversiones</p>
                                                </div>
                                                <div className="text-center bg-white/[0.04] rounded-lg py-2">
                                                    <p className="text-lg font-bold text-white/60">{c.roas?.toFixed(1) || '0.0'}</p>
                                                    <p className="text-[10px] text-white/40 font-medium">ROAS</p>
                                                </div>
                                            </div>
                                        </div>
                                    </GlassCard>
                                ))
                            ) : (
                                <p className="text-white/30 text-center py-6 text-sm">{t('marketing_google.no_campaigns')}</p>
                            )}
                        </div>
                    </div>
                );

            case 'combined':
                return (
                    <div className="space-y-4">
                        {/* Combined KPIs */}
                        {combinedStats && (
                            <GlassCard image={CARD_IMAGES.marketing} hoverScale={false}>
                                <div className="p-4 sm:p-6">
                                    <div className="grid grid-cols-2 gap-3 mb-3">
                                        <div className="bg-blue-500/10 rounded-xl p-3 text-center">
                                            <p className="text-lg sm:text-2xl font-bold text-blue-400">{GoogleAdsApi.formatNumber(combinedStats.combined?.total_impressions || 0)}</p>
                                            <p className="text-[10px] text-blue-400/60 font-semibold uppercase">Impresiones</p>
                                        </div>
                                        <div className="bg-indigo-500/10 rounded-xl p-3 text-center">
                                            <p className="text-lg sm:text-2xl font-bold text-indigo-400">{GoogleAdsApi.formatNumber(combinedStats.combined?.total_clicks || 0)}</p>
                                            <p className="text-[10px] text-indigo-400/60 font-semibold uppercase">Clicks</p>
                                        </div>
                                    </div>
                                    <div className="grid grid-cols-3 gap-2">
                                        <div className="bg-amber-500/10 rounded-xl p-2.5 text-center">
                                            <p className="text-base sm:text-lg font-bold text-amber-400">{GoogleAdsApi.formatCurrency(combinedStats.combined?.total_cost || 0, 'ARS')}</p>
                                            <p className="text-[10px] text-amber-400/60 font-semibold uppercase">Costo</p>
                                        </div>
                                        <div className="bg-emerald-500/10 rounded-xl p-2.5 text-center">
                                            <p className="text-base sm:text-lg font-bold text-emerald-400">{GoogleAdsApi.formatNumber(combinedStats.combined?.total_conversions || 0)}</p>
                                            <p className="text-[10px] text-emerald-400/60 font-semibold uppercase">Conversiones</p>
                                        </div>
                                        <div className="bg-violet-500/10 rounded-xl p-2.5 text-center">
                                            <p className="text-base sm:text-lg font-bold text-violet-400">{GoogleAdsApi.formatCurrency(combinedStats.combined?.total_conversions_value || 0, 'ARS')}</p>
                                            <p className="text-[10px] text-violet-400/60 font-semibold uppercase">Ingresos</p>
                                        </div>
                                    </div>
                                </div>
                            </GlassCard>
                        )}

                        {/* Platform comparison as cards (not table) */}
                        <div className="space-y-3">
                            <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider px-1">Comparación de Plataformas</h3>

                            {/* Meta Ads card */}
                            <GlassCard image={CARD_IMAGES.marketing}>
                                <div className="p-3 sm:p-4">
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-2">
                                            <Megaphone size={16} className="text-blue-400" />
                                            <span className="text-sm font-semibold text-white">Meta Ads</span>
                                        </div>
                                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${isMetaConnected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-white/[0.04] text-white/40'}`}>
                                            {isMetaConnected ? '● Conectado' : 'Desconectado'}
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-3 gap-2">
                                        <div className="text-center bg-blue-500/10 rounded-lg py-2">
                                            <p className="text-lg font-bold text-blue-400">${metaStats?.roi?.total_spend?.toLocaleString('es-AR', { maximumFractionDigits: 0 }) || '0'}</p>
                                            <p className="text-[10px] text-blue-400/60 font-medium">Inversión</p>
                                        </div>
                                        <div className="text-center bg-emerald-500/10 rounded-lg py-2">
                                            <p className="text-lg font-bold text-emerald-400">${metaStats?.roi?.total_revenue?.toLocaleString('es-AR', { maximumFractionDigits: 0 }) || '0'}</p>
                                            <p className="text-[10px] text-emerald-400/60 font-medium">Ingresos</p>
                                        </div>
                                        <div className="text-center bg-white/[0.04] rounded-lg py-2">
                                            <p className="text-lg font-bold text-white/60">{metaStats?.roi?.total_spend > 0 ? `${((metaStats.roi.total_revenue / metaStats.roi.total_spend) * 100).toFixed(0)}%` : '0%'}</p>
                                            <p className="text-[10px] text-white/40 font-medium">ROI</p>
                                        </div>
                                    </div>
                                </div>
                            </GlassCard>

                            {/* Google Ads card */}
                            <GlassCard image={CARD_IMAGES.tech}>
                                <div className="p-3 sm:p-4">
                                    <div className="flex items-center justify-between mb-3">
                                        <div className="flex items-center gap-2">
                                            <Globe size={16} className="text-red-400" />
                                            <span className="text-sm font-semibold text-white">Google Ads</span>
                                        </div>
                                        <span className={`inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${isGoogleConnected ? 'bg-emerald-500/10 text-emerald-400' : 'bg-white/[0.04] text-white/40'}`}>
                                            {isGoogleConnected ? '● Conectado' : 'Desconectado'}
                                        </span>
                                    </div>
                                    <div className="grid grid-cols-3 gap-2">
                                        <div className="text-center bg-blue-500/10 rounded-lg py-2">
                                            <p className="text-lg font-bold text-blue-400">{GoogleAdsApi.formatCurrency(googleStats?.cost || 0, googleStats?.currency)}</p>
                                            <p className="text-[10px] text-blue-400/60 font-medium">Inversión</p>
                                        </div>
                                        <div className="text-center bg-emerald-500/10 rounded-lg py-2">
                                            <p className="text-lg font-bold text-emerald-400">{GoogleAdsApi.formatCurrency(googleStats?.conversions_value || 0, googleStats?.currency)}</p>
                                            <p className="text-[10px] text-emerald-400/60 font-medium">Ingresos</p>
                                        </div>
                                        <div className="text-center bg-white/[0.04] rounded-lg py-2">
                                            <p className="text-lg font-bold text-white/60">{googleStats?.roas ? `${googleStats.roas.toFixed(1)}x` : '0x'}</p>
                                            <p className="text-[10px] text-white/40 font-medium">ROAS</p>
                                        </div>
                                    </div>
                                </div>
                            </GlassCard>
                        </div>
                    </div>
                );

            default:
                return null;
        }
    };

    return (
        <div className="h-screen flex flex-col overflow-hidden">
            {/* Compact Header */}
            <div className="shrink-0 border-b border-white/[0.06] px-4 pt-4 pb-0">
                <h1 className="text-lg font-bold text-white mb-1">Marketing Hub</h1>

                {/* Platform Tabs */}
                <nav className="flex gap-4 -mb-px">
                    {([
                        { key: 'meta' as Platform, icon: Megaphone, label: 'Meta Ads' },
                        { key: 'google' as Platform, icon: Globe, label: 'Google Ads' },
                        { key: 'combined' as Platform, icon: BarChart3, label: 'Combinado' },
                    ] as const).map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setActivePlatform(tab.key)}
                            className={`flex items-center gap-1.5 py-2.5 px-1 border-b-2 text-xs sm:text-sm font-medium transition-colors ${activePlatform === tab.key
                                ? 'border-blue-500 text-blue-400'
                                : 'border-transparent text-white/30 hover:text-white/60'
                                }`}
                        >
                            <tab.icon size={14} />
                            {tab.label}
                        </button>
                    ))}
                </nav>
            </div>

            {/* Scrollable Content */}
            <div className="flex-1 min-h-0 overflow-y-auto">
            <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-4">

                {/* Time range selector */}
                <div className="mb-6 flex justify-between items-center">
                    <div className="flex space-x-1 sm:space-x-2">
                        <button
                            onClick={() => setTimeRange('last_30d')}
                            className={`px-2 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm rounded-md ${timeRange === 'last_30d'
                                ? 'bg-blue-500/10 text-blue-400 font-medium'
                                : 'bg-white/[0.04] text-white/60 hover:bg-white/[0.08]'
                                }`}
                        >
                            {t('marketing.range_30d')}
                        </button>
                        <button
                            onClick={() => setTimeRange('last_90d')}
                            className={`px-2 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm rounded-md ${timeRange === 'last_90d'
                                ? 'bg-blue-500/10 text-blue-400 font-medium'
                                : 'bg-white/[0.04] text-white/60 hover:bg-white/[0.08]'
                                }`}
                        >
                            {t('marketing.range_90d')}
                        </button>
                        <button
                            onClick={() => setTimeRange('this_year')}
                            className={`px-2 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm rounded-md ${timeRange === 'this_year'
                                ? 'bg-blue-500/10 text-blue-400 font-medium'
                                : 'bg-white/[0.04] text-white/60 hover:bg-white/[0.08]'
                                }`}
                        >
                            {t('marketing.range_year')}
                        </button>
                        <button
                            onClick={() => setTimeRange('all')}
                            className={`px-2 sm:px-4 py-1.5 sm:py-2 text-xs sm:text-sm rounded-md ${timeRange === 'all'
                                ? 'bg-blue-500/10 text-blue-400 font-medium'
                                : 'bg-white/[0.04] text-white/60 hover:bg-white/[0.08]'
                                }`}
                        >
                            {t('marketing.range_all')}
                        </button>
                    </div>

                    <button
                        onClick={loadAllStats}
                        disabled={isLoading}
                        className="inline-flex items-center px-3 py-1 border border-white/[0.08] text-sm leading-4 font-medium rounded-md text-white bg-white/[0.04] hover:bg-white/[0.08] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
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
        </div>
    );
}
