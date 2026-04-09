import React, { useState, useEffect, lazy, Suspense } from 'react';
import { Settings, Globe, Loader2, CheckCircle2, Copy, Trash2, Edit2, Zap, MessageCircle, Key, User, Plus, Info, Database, AlertTriangle, Clock, MessageSquare, AlertCircle, Facebook, Image, Upload, Stethoscope, Send } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';
import { useAuth } from '../context/AuthContext';
import { Modal } from '../components/Modal';

// Lazy load integration tabs
const LeadsFormsTab = lazy(() => import('../components/integrations/LeadsFormsTab'));
const MetaConnectionTab = lazy(() => import('../components/integrations/MetaConnectionTab'));
const TelegramConfigTab = lazy(() => import('../components/TelegramConfigTab'));

type UiLanguage = 'es' | 'en' | 'fr';

interface ClinicSettings {
    name: string;
    ui_language: UiLanguage;
    ai_engine_mode?: 'solo' | 'multi';
    social_ig_active?: boolean;
    social_landings?: { main?: string; blanqueamiento?: string } | null;
    instagram_handle?: string | null;
    facebook_page_id?: string | null;
    sena_expiration_hours?: number | null;
    max_unpaid_appointments?: number | null;
}

const LANGUAGE_OPTIONS: { value: UiLanguage; labelKey: string }[] = [
    { value: 'es', labelKey: 'config.language_es' },
    { value: 'en', labelKey: 'config.language_en' },
    { value: 'fr', labelKey: 'config.language_fr' },
];

const ACCEPTED_FILE_TYPES = '.png,.jpg,.jpeg,.svg,.webp,.ico';
const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2 MB

interface Tenant {
    id: number;
    clinic_name: string; // From /chat/tenants endpoint structure
}

interface Credential {
    id?: number;
    name: string;
    value: string;
    category: string;
    description: string;
    scope: 'global' | 'tenant';
    tenant_id?: number | null;
    updated_at?: string;
}

interface IntegrationConfig {
    provider: 'ycloud' | 'chatwoot';
    // Chatwoot
    chatwoot_base_url?: string;
    chatwoot_api_token?: string;
    chatwoot_account_id?: string;
    full_webhook_url?: string;
    access_token?: string; // Webhook token
    webhook_path?: string;
    api_base?: string;
    // YCloud
    ycloud_api_key?: string;
    ycloud_webhook_secret?: string;
    ycloud_webhook_url?: string; // Usually from deployment config
    tenant_id: number | null;
}

export default function ConfigView() {
    const { t, language, setLanguage } = useTranslation();
    const { user } = useAuth();
    const [activeTab, setActiveTab] = useState<'general' | 'ycloud' | 'chatwoot' | 'others' | 'maintenance' | 'leads' | 'meta' | 'branding' | 'telegram'>('general');

    // General Settings State
    const [settings, setSettings] = useState<ClinicSettings | null>(null);

    // Data State
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [credentials, setCredentials] = useState<Credential[]>([]);

    // Integration Form State
    const [intConfig, setIntConfig] = useState<IntegrationConfig>({ provider: 'ycloud', tenant_id: null });

    // "Others" Credential Form State
    const [credForm, setCredForm] = useState<Credential>({
        name: '', value: '', category: 'openai', description: '', scope: 'global', tenant_id: null
    });
    const [isCredModalOpen, setIsCredModalOpen] = useState(false);
    const [editingCred, setEditingCred] = useState<Credential | null>(null);

    // Status State
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Branding State
    const [brandingTenantId, setBrandingTenantId] = useState<number | null>(null);
    const [logoFile, setLogoFile] = useState<File | null>(null);
    const [logoPreview, setLogoPreview] = useState<string | null>(null);
    const [uploadingLogo, setUploadingLogo] = useState(false);
    const [logoError, setLogoError] = useState<string | null>(null);
    const [currentLogoUrl, setCurrentLogoUrl] = useState<string | null>(null);

    // AI Engine Mode State
    const [engineModalOpen, setEngineModalOpen] = useState(false);
    const [engineTargetMode, setEngineTargetMode] = useState<'solo' | 'multi' | null>(null);
    const [engineHealthChecking, setEngineHealthChecking] = useState(false);
    const [engineHealthResult, setEngineHealthResult] = useState<{ solo: any; multi: any } | null>(null);

    // Social IG/FB Agent State
    const [socialIgActive, setSocialIgActive] = useState(false);
    const [socialLandingMain, setSocialLandingMain] = useState('');
    const [socialLandingBlanq, setSocialLandingBlanq] = useState('');
    const [instagramHandle, setInstagramHandle] = useState('');
    const [facebookPageId, setFacebookPageId] = useState('');
    // Seña guardrails (migration 042)
    const [senaExpirationHours, setSenaExpirationHours] = useState(24);
    const [maxUnpaidAppointments, setMaxUnpaidAppointments] = useState(1);

    useEffect(() => {
        loadGeneralSettings();
        if (user?.role === 'ceo') {
            loadTenants();
            loadCredentials();
        }
    }, [user, activeTab]);

    // Re-load integration config when tab or tenant changes
    useEffect(() => {
        if ((activeTab === 'ycloud' || activeTab === 'chatwoot') && user?.role === 'ceo') {
            loadIntegrationConfig(activeTab, intConfig.tenant_id);
        }
    }, [activeTab, intConfig.tenant_id]);


    // --- LOADERS ---

    const loadGeneralSettings = async () => {
        try {
            setLoading(true);
            const res = await api.get<ClinicSettings>('/admin/settings/clinic');
            setSettings(res.data);
            // Populate social state
            setSocialIgActive(res.data.social_ig_active ?? false);
            setSocialLandingMain(res.data.social_landings?.main ?? '');
            setSocialLandingBlanq(res.data.social_landings?.blanqueamiento ?? '');
            setInstagramHandle(res.data.instagram_handle ?? '');
            setFacebookPageId(res.data.facebook_page_id ?? '');
            setSenaExpirationHours(res.data.sena_expiration_hours ?? 24);
            setMaxUnpaidAppointments(res.data.max_unpaid_appointments ?? 1);
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const loadTenants = async () => {
        try {
            const { data } = await api.get<Tenant[]>('/admin/chat/tenants');
            if (Array.isArray(data)) {
                setTenants(data);
                // Default tenant for integration forms if not set
                if (data.length > 0 && intConfig.tenant_id === null) {
                    setIntConfig(prev => ({ ...prev, tenant_id: data[0].id }));
                }
            }
        } catch (e) {
            console.error("Error loading tenants:", e);
        }
    };

    const loadCredentials = async () => {
        try {
            const { data } = await api.get('/admin/credentials');
            if (Array.isArray(data)) setCredentials(data);
        } catch (e) {
            console.error(e);
        }
    };

    const loadCurrentLogo = async (tenantId: number) => {
        try {
            const url = `/admin/public/tenant-logo/${tenantId}?t=${Date.now()}`;
            const response = await api.get(url, { responseType: 'blob' });
            const objectUrl = URL.createObjectURL(response.data);
            setCurrentLogoUrl(objectUrl);
        } catch (e) {
            setCurrentLogoUrl(null);
        }
    };

    const loadIntegrationConfig = async (provider: 'ycloud' | 'chatwoot', tenantId: number | null) => {
        try {
            setLoading(true);
            const query = tenantId ? `?tenant_id=${tenantId}` : '';
            const { data } = await api.get(`/admin/integrations/${provider}/config${query}`);

            setIntConfig(prev => ({
                ...prev,
                ...data,
                provider,
                tenant_id: tenantId
            }));

            // For YCloud, we might need deployment config for the webhook URL
            if (provider === 'ycloud' && !data.ycloud_webhook_url) {
                const depRes = await api.get('/admin/config/deployment');
                setIntConfig(prev => ({ ...prev, ycloud_webhook_url: depRes.data.webhook_ycloud_url }));
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const validateFile = (file: File): string | null => {
        const ext = file.name.split('.').pop()?.toLowerCase();
        const allowedExts = ['png', 'jpg', 'jpeg', 'svg', 'webp', 'ico'];
        if (!ext || !allowedExts.includes(ext)) {
            return t('branding.error_unsupported_format');
        }
        if (file.size > MAX_FILE_SIZE) {
            return t('branding.error_file_too_large');
        }
        return null;
    };

    const handleFileSelect = (file: File | null) => {
        setLogoError(null);
        if (!file) {
            setLogoFile(null);
            setLogoPreview(null);
            return;
        }
        const error = validateFile(file);
        if (error) {
            setLogoError(error);
            setLogoFile(null);
            setLogoPreview(null);
            return;
        }
        setLogoFile(file);
        const previewUrl = URL.createObjectURL(file);
        setLogoPreview(previewUrl);
    };

    const handleUpload = async () => {
        if (!logoFile || !brandingTenantId) return;
        setUploadingLogo(true);
        setLogoError(null);
        const formData = new FormData();
        formData.append('file', logoFile);
        try {
            await api.post(`/admin/tenants/${brandingTenantId}/logo`, formData, {
                headers: { 'Content-Type': 'multipart/form-data' },
            });
            // Refresh current logo preview
            await loadCurrentLogo(brandingTenantId);
            // Emit event for Sidebar
            window.dispatchEvent(new CustomEvent('tenant-logo-updated', { detail: { tenant_id: brandingTenantId } }));
            showSuccess(t('branding.upload_success'));
            // Reset file selection
            setLogoFile(null);
            setLogoPreview(null);
        } catch (err: any) {
            setLogoError(err.message || t('branding.upload_error'));
        } finally {
            setUploadingLogo(false);
        }
    };

    // --- HANDLERS ---

    const handleLanguageChange = async (value: UiLanguage) => {
        setSaving(true);
        try {
            await api.patch('/admin/settings/clinic', { ui_language: value });
            setSettings(prev => (prev ? { ...prev, ui_language: value } : null));
            setLanguage(value);
            showSuccess(t('config.saved'));
        } catch (err) {
            setError(t('config.save_error'));
        } finally {
            setSaving(false);
        }
    };

    // AI Engine Mode handlers
    const handleEngineModeSelect = async (mode: 'solo' | 'multi') => {
        setEngineTargetMode(mode);
        setEngineHealthChecking(true);
        setEngineHealthResult(null);

        try {
            const response = await api.get('/admin/ai-engine/health');
            setEngineHealthResult(response.data);
            setEngineModalOpen(true);
        } catch (err: any) {
            setError(t('config.engine_health_check_error'));
        } finally {
            setEngineHealthChecking(false);
        }
    };

    const handleEngineModeConfirm = async () => {
        if (!engineTargetMode || !engineHealthResult) return;

        const targetEngine = engineTargetMode === 'multi' ? 'multi' : 'solo';
        const targetStatus = engineTargetMode === 'multi' 
            ? engineHealthResult.multi?.ok 
            : engineHealthResult.solo?.ok;

        // Solo can always be enabled; multi needs health check pass
        if (engineTargetMode === 'multi' && !targetStatus) {
            setError(t('config.engine_target_unavailable'));
            return;
        }

        setSaving(true);
        try {
            await api.patch('/admin/settings/clinic', { ai_engine_mode: engineTargetMode });
            setSettings(prev => (prev ? { ...prev, ai_engine_mode: engineTargetMode } : null));
            showSuccess(t('config.engine_change_success'));
            setEngineModalOpen(false);
            setEngineTargetMode(null);
        } catch (err: any) {
            setError(err.response?.data?.detail || t('config.engine_change_error'));
        } finally {
            setSaving(false);
        }
    };

    const handleSaveSocialSettings = async () => {
        setSaving(true);
        try {
            const landings: Record<string, string> = {};
            if (socialLandingMain.trim()) landings.main = socialLandingMain.trim();
            if (socialLandingBlanq.trim()) landings.blanqueamiento = socialLandingBlanq.trim();
            await api.patch('/admin/settings/clinic', {
                social_ig_active: socialIgActive,
                social_landings: Object.keys(landings).length > 0 ? landings : null,
                instagram_handle: instagramHandle.trim() || null,
                facebook_page_id: facebookPageId.trim() || null,
            });
            showSuccess(t('config.saved'));
        } catch (err: any) {
            setError(err.response?.data?.detail || t('config.save_error'));
        } finally {
            setSaving(false);
        }
    };

    const handleSaveIntegration = async () => {
        setSaving(true);
        setError(null);
        try {
            await api.post(`/admin/integrations/${intConfig.provider}/config`, intConfig);
            showSuccess(t('config.saved_integration', { provider: intConfig.provider === 'ycloud' ? 'WhatsApp' : 'Chatwoot' }));
            loadCredentials(); // Refresh table
        } catch (err: any) {
            setError(err.message || t('config.save_integration_error'));
        } finally {
            setSaving(false);
        }
    };

    const handleSaveGenericCredential = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            if (editingCred?.id) {
                await api.put(`/admin/credentials/${editingCred.id}`, credForm);
            } else {
                await api.post('/admin/credentials', credForm);
            }
            setIsCredModalOpen(false);
            loadCredentials();
            showSuccess(t('config.credential_saved'));
        } catch (e: any) {
            alert(t('config.error_prefix') + e.message);
        }
    };

    const handleCleanMedia = async (days: number) => {
        if (!confirm(t('config.confirm_clean_media', { days }))) return;
        setSaving(true);
        try {
            const { data } = await api.post('/admin/maintenance/clean-media', { days });
            showSuccess(t('config.clean_media_success', { count: data.deleted }));
        } catch (err: any) {
            setError(err.message || t('config.clean_media_error'));
        } finally {
            setSaving(false);
        }
    };

    const handleDeleteCredential = async (id: number) => {
        if (!confirm(t('config.confirm_delete_credential'))) return;
        try {
            await api.delete(`/admin/credentials/${id}`);
            loadCredentials();
            showSuccess(t('config.credential_deleted'));
        } catch (e: any) {
            alert(t('config.error_prefix') + e.message);
        }
    };

    const showSuccess = (msg: string) => {
        setSuccess(msg);
        setTimeout(() => setSuccess(null), 3000);
    }

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        showSuccess(t('common.copied'));
    };

    // --- RENDER HELPERS ---

    const getTenantName = (id: number | null | undefined) => {
        if (!id) return t('config.scope_global');
        const tenant = tenants.find(ten => ten.id === id);
        return tenant ? tenant.clinic_name : `ID: ${id}`;
    }

    // --- TABS CONTENT ---

    const renderGeneralTab = () => (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Globe size={20} className="text-white/60" />
                    <h2 className="text-lg font-semibold text-white">{t('config.language_label')}</h2>
                </div>
                <p className="text-sm text-white/40 mb-4">{t('config.language_help')}</p>
                <div className="flex flex-wrap gap-3">
                    {LANGUAGE_OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            onClick={() => handleLanguageChange(opt.value)}
                            disabled={saving}
                            className={`px-4 py-2.5 rounded-xl font-medium transition-colors border-2 min-h-[44px] ${language === opt.value
                                ? 'border-blue-500 bg-blue-500/10 text-blue-400'
                                : 'border-white/[0.08] bg-white/[0.03] text-white/70 hover:border-white/[0.12] hover:bg-white/[0.04]'
                                }`}
                        >
                            {saving && language === opt.value ? <Loader2 className="w-5 h-5 animate-spin" /> : t(opt.labelKey)}
                        </button>
                    ))}
                </div>
                {settings && (
                    <p className="text-xs text-white/30 mt-3">
                        {t('config.current_clinic')}: <strong>{settings.name}</strong>
                    </p>
                )}
            </div>

            {/* AI Engine Mode Selector - CEO only */}
            {user?.role === 'ceo' && (
                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Zap size={20} className="text-white/60" />
                        <h2 className="text-lg font-semibold text-white">{t('config.ai_engine_label')}</h2>
                    </div>
                    <p className="text-sm text-white/40 mb-4">{t('config.ai_engine_helper')}</p>
                    <select
                        value={settings?.ai_engine_mode || 'solo'}
                        onChange={(e) => handleEngineModeSelect(e.target.value as 'solo' | 'multi')}
                        disabled={saving || engineHealthChecking}
                        className="w-full sm:w-auto px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-indigo-500 outline-none transition-all"
                    >
                        <option value="solo">{t('config.engine_solo')}</option>
                        <option value="multi">{t('config.engine_multi')}</option>
                    </select>
                    {engineHealthChecking && (
                        <p className="text-xs text-white/40 mt-2 flex items-center gap-1">
                            <Loader2 className="w-3 h-3 animate-spin" /> {t('config.engine_health_checking')}
                        </p>
                    )}
                </div>
            )}

            {/* Social Media Agent Config - CEO only */}
            {user?.role === 'ceo' && (
                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Facebook size={20} className="text-white/60" />
                        <h2 className="text-lg font-semibold text-white">{t('social_agent.section_title')}</h2>
                    </div>

                    {/* Toggle */}
                    <div className="flex items-center justify-between mb-4 p-3 bg-white/[0.02] border border-white/[0.06] rounded-xl">
                        <div>
                            <p className="text-sm font-medium text-white">{t('social_agent.active_label')}</p>
                            <p className="text-xs text-white/40 mt-0.5">{t('social_agent.active_description')}</p>
                        </div>
                        <button
                            type="button"
                            onClick={() => setSocialIgActive(v => !v)}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                socialIgActive ? 'bg-blue-600' : 'bg-white/10'
                            }`}
                        >
                            <span
                                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                    socialIgActive ? 'translate-x-6' : 'translate-x-1'
                                }`}
                            />
                        </button>
                    </div>

                    <div className="space-y-4">
                        {/* Instagram Handle */}
                        <div>
                            <label className="text-sm font-medium text-white/70 mb-1 block">
                                {t('social_agent.ig_handle')}
                            </label>
                            <input
                                type="text"
                                value={instagramHandle}
                                onChange={e => setInstagramHandle(e.target.value)}
                                placeholder={t('social_agent.ig_handle_placeholder')}
                                className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/30 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            />
                        </div>

                        {/* Facebook Page ID */}
                        <div>
                            <label className="text-sm font-medium text-white/70 mb-1 block">
                                {t('social_agent.fb_page_id')}
                            </label>
                            <input
                                type="text"
                                value={facebookPageId}
                                onChange={e => setFacebookPageId(e.target.value)}
                                placeholder={t('social_agent.fb_page_id_placeholder')}
                                className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/30 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                            />
                        </div>

                        {/* Landings */}
                        <div>
                            <p className="text-sm font-medium text-white/70 mb-2">{t('social_agent.landings_title')}</p>
                            <div className="space-y-3">
                                <div>
                                    <label className="text-xs text-white/50 mb-1 block">{t('social_agent.landing_main')}</label>
                                    <input
                                        type="text"
                                        value={socialLandingMain}
                                        onChange={e => setSocialLandingMain(e.target.value)}
                                        placeholder={t('social_agent.landing_main_placeholder')}
                                        className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/30 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs text-white/50 mb-1 block">{t('social_agent.landing_blanqueamiento')}</label>
                                    <input
                                        type="text"
                                        value={socialLandingBlanq}
                                        onChange={e => setSocialLandingBlanq(e.target.value)}
                                        placeholder={t('social_agent.landing_blanqueamiento_placeholder')}
                                        className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/30 focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                    />
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={handleSaveSocialSettings}
                            disabled={saving}
                            className="w-full py-3 bg-white text-[#0a0e1a] rounded-xl font-semibold transition-all flex justify-center items-center gap-2 hover:bg-white/90 disabled:opacity-50"
                        >
                            {saving ? <Loader2 className="animate-spin w-5 h-5" /> : t('common.save')}
                        </button>
                    </div>
                </div>
            )}

            {/* Seña / Appointment Guardrails */}
            {user?.role === 'ceo' && (
                <div className="bg-white/[0.04] border border-amber-500/20 rounded-2xl p-4 sm:p-6 space-y-5">
                    <div className="flex items-center gap-3">
                        <Clock className="w-5 h-5 text-amber-400" />
                        <h2 className="text-lg font-semibold text-white">{t('config.sena_guardrails_title')}</h2>
                    </div>
                    <p className="text-sm text-white/50">{t('config.sena_guardrails_desc')}</p>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <label className="block text-xs font-bold text-white/55 uppercase">{t('config.sena_expiration_hours')}</label>
                            <input
                                type="number"
                                min={0}
                                max={168}
                                value={senaExpirationHours}
                                onChange={(e) => setSenaExpirationHours(parseInt(e.target.value) || 0)}
                                className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.10] rounded-xl text-white focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500/30"
                            />
                            <p className="text-xs text-white/30">{t('config.sena_expiration_hint')}</p>
                        </div>
                        <div className="space-y-2">
                            <label className="block text-xs font-bold text-white/55 uppercase">{t('config.max_unpaid_label')}</label>
                            <input
                                type="number"
                                min={0}
                                max={10}
                                value={maxUnpaidAppointments}
                                onChange={(e) => setMaxUnpaidAppointments(parseInt(e.target.value) || 0)}
                                className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.10] rounded-xl text-white focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500/30"
                            />
                            <p className="text-xs text-white/30">{t('config.max_unpaid_hint')}</p>
                        </div>
                    </div>

                    <button
                        onClick={async () => {
                            setSaving(true);
                            try {
                                await api.patch('/admin/settings/clinic', {
                                    sena_expiration_hours: senaExpirationHours,
                                    max_unpaid_appointments: maxUnpaidAppointments,
                                });
                                showSuccess(t('config.saved'));
                            } catch (err: any) {
                                setError(err.response?.data?.detail || t('config.save_error'));
                            } finally {
                                setSaving(false);
                            }
                        }}
                        disabled={saving}
                        className="w-full py-3 bg-amber-600 text-white rounded-xl font-semibold transition-all flex justify-center items-center gap-2 hover:bg-amber-700 disabled:opacity-50"
                    >
                        {saving ? <Loader2 className="animate-spin w-5 h-5" /> : t('common.save')}
                    </button>
                </div>
            )}
        </div>
    );

    const renderYCloudTab = () => (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-300">
            {/* 1. Webhook Info */}
            <div className="bg-green-500/10 border border-green-500/20 rounded-2xl p-4 sm:p-6">
                <div className="flex items-center gap-2 mb-2 text-green-400">
                    <Zap className="w-5 h-5" />
                    <h3 className="font-semibold">{t('config.webhook_title_ycloud')}</h3>
                </div>
                <p className="text-sm text-green-400/80 mb-4">{t('config.webhook_hint_ycloud')}</p>
                <div className="flex flex-col sm:flex-row gap-2">
                    <input readOnly value={intConfig.ycloud_webhook_url || 'Cargando...'} className="flex-1 px-3 py-2 bg-white/[0.04] rounded-lg border border-green-500/20 text-sm font-mono text-white/60 focus:outline-none" />
                    <button onClick={() => copyToClipboard(intConfig.ycloud_webhook_url || '')} className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition flex items-center justify-center gap-2 font-medium">
                        <Copy size={16} /> <span className="sm:hidden">{t('config.copy_url')}</span>
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
                {/* 2. Form */}
                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                    <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                        <MessageCircle className="text-green-600" size={20} />
                        {t('config.configure_credential')}
                    </h2>

                    <div className="space-y-4">
                        <div>
                            <label className="text-sm font-medium text-white/70 mb-1 block">{t('config.field_tenant')}</label>
                            <select
                                className="w-full px-4 py-2 bg-white/[0.04] border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-green-500 outline-none transition-all"
                                value={intConfig.tenant_id === null ? '' : intConfig.tenant_id}
                                onChange={(e) => setIntConfig({ ...intConfig, tenant_id: e.target.value ? Number(e.target.value) : null })}
                            >
                                <option value="">{t('config.global_all_tenants')}</option>
                                {tenants.map(t => <option key={t.id} value={t.id}>{t.clinic_name}</option>)}
                            </select>
                        </div>

                        <div>
                            <label className="text-sm font-medium text-white/70 mb-1 block">YCloud API Key</label>
                            <input
                                type="password"
                                className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-green-500 outline-none transition-all"
                                placeholder="sk_..."
                                value={intConfig.ycloud_api_key || ''}
                                onChange={e => setIntConfig({ ...intConfig, ycloud_api_key: e.target.value })}
                            />
                        </div>

                        <div>
                            <label className="text-sm font-medium text-white/70 mb-1 block">Webhook Secret</label>
                            <input
                                type="password"
                                className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-green-500 outline-none transition-all"
                                placeholder="whsec_..."
                                value={intConfig.ycloud_webhook_secret || ''}
                                onChange={e => setIntConfig({ ...intConfig, ycloud_webhook_secret: e.target.value })}
                            />
                        </div>

                        <button
                            onClick={handleSaveIntegration}
                            disabled={saving}
                            className="w-full py-3 bg-green-600 hover:bg-green-700 text-white rounded-xl font-semibold shadow-lg shadow-green-600/20 transition-all flex justify-center items-center gap-2 mt-4"
                        >
                            {saving ? <Loader2 className="animate-spin" /> : <><CheckCircle2 size={18} /> {t('config.save_config')}</>}
                        </button>
                    </div>
                </div>

                {/* 3. Table */}
                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6 flex flex-col min-h-[400px] overflow-x-hidden">
                    <h2 className="text-lg font-semibold text-white mb-4">{t('config.active_credentials')}</h2>
                    <div className="overflow-x-auto flex-1">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-white/[0.04] text-white/40 uppercase text-xs tracking-wider">
                                <tr>
                                    <th className="px-4 py-3 rounded-l-lg font-semibold">{t('config.col_tenant')}</th>
                                    <th className="px-4 py-3 font-semibold">{t('config.col_status')}</th>
                                    <th className="px-4 py-3 rounded-r-lg text-right font-semibold">{t('config.col_actions')}</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/[0.06]">
                                {credentials.filter(c => c.category === 'ycloud' && c.name === 'YCLOUD_API_KEY').map(c => (
                                    <tr key={c.id} className="hover:bg-white/[0.04] transition-colors">
                                        <td className="px-4 py-4 font-medium text-white">{getTenantName(c.tenant_id)}</td>
                                        <td className="px-4 py-4">
                                            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-green-500/10 text-green-400 text-xs font-medium">
                                                <CheckCircle2 size={12} /> {t('config.status_active')}
                                            </span>
                                        </td>
                                        <td className="px-4 py-4 text-right">
                                            <div className="flex justify-end gap-2">
                                                <button
                                                    onClick={() => setIntConfig({ ...intConfig, tenant_id: c.tenant_id || null })}
                                                    className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors border border-transparent hover:border-indigo-100"
                                                    title={t('common.edit')}
                                                >
                                                    <Edit2 size={16} />
                                                </button>
                                                <button
                                                    onClick={() => handleDeleteCredential(c.id!)}
                                                    className="p-2 text-rose-600 hover:bg-rose-50 rounded-lg transition-colors border border-transparent hover:border-rose-100"
                                                    title={t('common.delete')}
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                {credentials.filter(c => c.category === 'ycloud').length === 0 && (
                                    <tr><td colSpan={3} className="px-4 py-12 text-center text-white/30 italic">{t('config.no_whatsapp_configured')}</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );

    const renderChatwootTab = () => (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-300">
            {/* 1. Webhook Info */}
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-2xl p-4 sm:p-6">
                <div className="flex items-center gap-2 mb-2 text-blue-400">
                    <MessageCircle className="w-5 h-5" />
                    <h3 className="font-semibold">{t('config.webhook_title_chatwoot')}</h3>
                </div>
                <p className="text-sm text-blue-400/80 mb-4">{t('config.webhook_hint_chatwoot')}</p>
                <div className="flex flex-col sm:flex-row gap-2">
                    <input readOnly value={intConfig.full_webhook_url || 'Cargando...'} className="flex-1 px-3 py-2 bg-white/[0.04] rounded-lg border border-blue-500/20 text-sm font-mono text-white/60 focus:outline-none" />
                    <button onClick={() => copyToClipboard(intConfig.full_webhook_url || '')} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition flex items-center justify-center gap-2 font-medium">
                        <Copy size={16} /> <span className="sm:hidden">{t('config.copy_url')}</span>
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
                {/* 2. Form */}
                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                    <h2 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
                        <User className="text-blue-600" size={20} />
                        {t('config.configure_credential')}
                    </h2>

                    <div className="space-y-4">
                        <div>
                            <label className="text-sm font-medium text-white/70 mb-1 block">{t('config.field_tenant')}</label>
                            <select
                                className="w-full px-4 py-2 bg-white/[0.04] border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                value={intConfig.tenant_id === null ? '' : intConfig.tenant_id}
                                onChange={(e) => setIntConfig({ ...intConfig, tenant_id: e.target.value ? Number(e.target.value) : null })}
                            >
                                <option value="">{t('config.global_all_tenants')}</option>
                                {tenants.map(t => <option key={t.id} value={t.id}>{t.clinic_name}</option>)}
                            </select>
                        </div>

                        <div>
                            <label className="text-sm font-medium text-white/70 mb-1 block">Chatwoot Base URL</label>
                            <input
                                className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                placeholder="https://app.chatwoot.com"
                                value={intConfig.chatwoot_base_url || ''}
                                onChange={e => setIntConfig({ ...intConfig, chatwoot_base_url: e.target.value })}
                            />
                        </div>

                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                            <div>
                                <label className="text-sm font-medium text-white/70 mb-1 block">Account ID</label>
                                <input
                                    className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                    placeholder="Ej: 1"
                                    value={intConfig.chatwoot_account_id || ''}
                                    onChange={e => setIntConfig({ ...intConfig, chatwoot_account_id: e.target.value })}
                                />
                            </div>
                        </div>

                        <div>
                            <label className="text-sm font-medium text-white/70 mb-1 block">User API Token</label>
                            <input
                                type="password"
                                className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                                placeholder="Token de administrador..."
                                value={intConfig.chatwoot_api_token || ''}
                                onChange={e => setIntConfig({ ...intConfig, chatwoot_api_token: e.target.value })}
                            />
                        </div>

                        <button
                            onClick={handleSaveIntegration}
                            disabled={saving}
                            className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-semibold shadow-lg shadow-blue-600/20 transition-all flex justify-center items-center gap-2 mt-4"
                        >
                            {saving ? <Loader2 className="animate-spin" /> : <><CheckCircle2 size={18} /> {t('config.save_config')}</>}
                        </button>
                    </div>
                </div>

                {/* 3. Table */}
                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6 flex flex-col min-h-[400px] overflow-x-hidden">
                    <h2 className="text-lg font-semibold text-white mb-4">{t('config.active_credentials')}</h2>
                    <div className="overflow-x-auto flex-1">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-white/[0.04] text-white/40 uppercase text-xs tracking-wider">
                                <tr>
                                    <th className="px-4 py-3 rounded-l-lg font-semibold">{t('config.col_tenant')}</th>
                                    <th className="px-4 py-3 font-semibold">Account ID</th>
                                    <th className="px-4 py-3 rounded-r-lg text-right font-semibold">{t('config.col_actions')}</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/[0.06]">
                                {credentials.filter(c => c.category === 'chatwoot' && c.name === 'CHATWOOT_ACCOUNT_ID').map(c => (
                                    <tr key={c.id} className="hover:bg-white/[0.04] transition-colors">
                                        <td className="px-4 py-4 font-medium text-white">{getTenantName(c.tenant_id)}</td>
                                        <td className="px-4 py-4 text-white/60 font-mono tracking-tight">{c.value}</td>
                                        <td className="px-4 py-4 text-right">
                                            <div className="flex justify-end gap-2">
                                                <button
                                                    onClick={() => setIntConfig({ ...intConfig, tenant_id: c.tenant_id || null })}
                                                    className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors border border-transparent hover:border-indigo-100"
                                                    title={t('common.edit')}
                                                >
                                                    <Edit2 size={16} />
                                                </button>
                                                <button
                                                    onClick={() => handleDeleteCredential(c.id!)}
                                                    className="p-2 text-rose-600 hover:bg-rose-50 rounded-lg transition-colors border border-transparent hover:border-rose-100"
                                                    title={t('common.delete')}
                                                >
                                                    <Trash2 size={16} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                {credentials.filter(c => c.category === 'chatwoot').length === 0 && (
                                    <tr><td colSpan={3} className="px-4 py-12 text-center text-white/30 italic">{t('config.no_chatwoot_configured')}</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    );


    const renderOthersTab = () => (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="flex justify-between items-center bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                <div>
                    <h2 className="text-lg font-semibold text-white">{t('config.other_integrations')}</h2>
                    <p className="text-sm text-white/40">{t('config.other_integrations_hint')}</p>
                </div>
                <button
                    onClick={() => { setEditingCred(null); setCredForm({ name: '', value: '', category: 'openai', description: '', scope: 'global', tenant_id: null }); setIsCredModalOpen(true); }}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 flex items-center gap-2 font-medium"
                >
                    <Plus size={18} /> {t('common.new')}
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {credentials.filter(c => !['ycloud', 'chatwoot'].includes(c.category)).map(cred => (
                    <div key={cred.id} className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-5 hover:bg-white/[0.05] transition-colors group relative overflow-hidden">
                        <div className={`absolute top-0 left-0 w-1 h-full rounded-l-2xl ${cred.scope === 'global' ? 'bg-indigo-500' : 'bg-emerald-500'}`}></div>
                        <div className="flex justify-between items-start mb-3 pl-2">
                            <div>
                                <h4 className="font-semibold text-white leading-tight">{cred.name}</h4>
                                <span className="inline-flex items-center gap-1.5 mt-1 px-2 py-0.5 rounded-md bg-white/[0.04] text-xs text-white/60 font-medium lowercase">
                                    {cred.category} • {cred.scope === 'global' ? t('config.scope_global') : getTenantName(cred.tenant_id)}
                                </span>
                            </div>
                            <div className="flex gap-1 group-hover:opacity-100 opacity-0 transition-opacity">
                                <button onClick={() => { setEditingCred(cred); setCredForm({ ...cred, value: '••••••••' }); setIsCredModalOpen(true); }} className="p-1.5 hover:bg-white/[0.04] rounded-lg text-white/40 hover:text-indigo-400">
                                    <Edit2 size={16} />
                                </button>
                                <button onClick={() => handleDeleteCredential(cred.id!)} className="p-1.5 hover:bg-rose-500/10 rounded-lg text-white/30 hover:text-rose-400">
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>
                        <div className="pl-2">
                            <div className="bg-white/[0.04] rounded-lg px-3 py-2 font-mono text-xs text-white/40 border border-white/[0.06] flex items-center gap-2">
                                <Key size={12} className="text-white/30" />
                                {cred.value.substring(0, 16)}...
                            </div>
                        </div>
                    </div>
                ))}
                {credentials.filter(c => !['ycloud', 'chatwoot'].includes(c.category)).length === 0 && (
                    <div className="col-span-full py-12 text-center text-white/30 bg-white/[0.02] rounded-2xl border border-dashed border-white/[0.08]">
                        {t('config.no_other_credentials')}
                    </div>
                )}
            </div>
        </div>
    );

    const renderMaintenanceTab = () => (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Database size={20} className="text-white/60" />
                    <h2 className="text-lg font-semibold text-white">{t('config.media_maintenance')}</h2>
                </div>
                <p className="text-sm text-white/40 mb-6">
                    {t('config.media_hint')}
                </p>

                <div className="space-y-6">
                    <div className="flex flex-col gap-4 p-4 bg-white/[0.02] rounded-xl border border-white/[0.06]">
                        <div className="flex items-center justify-between">
                            <div>
                                <h4 className="font-medium text-white flex items-center gap-2">
                                    <Clock size={16} className="text-white/40" /> {t('config.cleanup_title')}
                                </h4>
                                <p className="text-xs text-white/40">{t('config.cleanup_hint')}</p>
                            </div>
                            <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-white/70">{t('config.field_age')}</span>
                                <select
                                    className="px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white outline-none focus:ring-2 focus:ring-indigo-500"
                                    defaultValue="180"
                                    id="cleanup-days-select"
                                >
                                    <option value="30">{t('config.option_1month')}</option>
                                    <option value="90">{t('config.option_3months')}</option>
                                    <option value="180">{t('config.option_6months')}</option>
                                    <option value="365">{t('config.option_1year')}</option>
                                </select>
                            </div>
                        </div>
                        <div className="flex justify-end">
                            <button
                                onClick={() => {
                                    const select = document.getElementById('cleanup-days-select') as HTMLSelectElement;
                                    handleCleanMedia(parseInt(select.value));
                                }}
                                disabled={saving}
                                className="px-6 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-medium shadow-md transition-all flex items-center gap-2"
                            >
                                {saving ? <Loader2 className="animate-spin" size={18} /> : <><Trash2 size={18} /> {t('config.run_cleanup')}</>}
                            </button>
                        </div>
                    </div>

                    <div className="p-4 bg-blue-500/10 rounded-xl border border-blue-500/20 border-dashed">
                        <div className="flex gap-3">
                            <Info size={20} className="text-blue-400 shrink-0" />
                            <div>
                                <h4 className="text-sm font-semibold text-blue-400">{t('config.smart_storage_title')}</h4>
                                <p className="text-xs text-blue-400/80 leading-relaxed mt-1">
                                    {t('config.smart_storage_hint')}
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );

    const renderBrandingTab = () => (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-300">
            {/* 1. Tenant Selection */}
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Stethoscope size={20} className="text-white/60" />
                    <h2 className="text-lg font-semibold text-white">{t('branding.select_clinic')}</h2>
                </div>
                <p className="text-sm text-white/40 mb-4">{t('branding.select_clinic_hint')}</p>
                <select
                    className="w-full px-4 py-2 bg-white/[0.04] border-white/[0.06] rounded-xl text-white focus:ring-2 focus:ring-purple-500 outline-none transition-all"
                    value={brandingTenantId === null ? '' : brandingTenantId}
                    onChange={(e) => {
                        const tid = e.target.value ? Number(e.target.value) : null;
                        setBrandingTenantId(tid);
                        if (tid) loadCurrentLogo(tid);
                    }}
                >
                    <option value="">{t('config.select_placeholder')}</option>
                    {tenants.map(t => <option key={t.id} value={t.id}>{t.clinic_name}</option>)}
                </select>
            </div>

            {/* 2. Current Logo Preview */}
            {brandingTenantId && (
                <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Image size={20} className="text-white/60" />
                        <h2 className="text-lg font-semibold text-white">{t('branding.current_logo')}</h2>
                    </div>
                    <p className="text-sm text-white/40 mb-4">{t('branding.current_logo_hint')}</p>
                    <div className="flex items-center justify-center p-8 bg-white/[0.02] rounded-xl border border-dashed border-white/[0.06]">
                        {currentLogoUrl ? (
                            <img src={currentLogoUrl} alt={t('branding.current_logo')} className="max-h-32 max-w-full object-contain rounded-lg" />
                        ) : (
                            <div className="text-center text-white/30">
                                <Image size={48} className="mx-auto mb-2 opacity-30" />
                                <p className="text-sm">{t('branding.no_logo_uploaded')}</p>
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* 3. Upload Zone */}
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                <div className="flex items-center gap-2 mb-4">
                    <Upload size={20} className="text-white/60" />
                    <h2 className="text-lg font-semibold text-white">{t('branding.upload_new_logo')}</h2>
                </div>
                <p className="text-sm text-white/40 mb-4">{t('branding.upload_hint')}</p>

                {/* Drag‑and‑drop zone */}
                <div
                    className={`border-2 border-dashed rounded-2xl p-8 text-center transition-colors ${
                        logoError ? 'border-red-500/30 bg-red-500/5' : 'border-white/[0.08] hover:border-purple-500/40'
                    }`}
                    onDragOver={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                    }}
                    onDrop={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const file = e.dataTransfer.files[0];
                        handleFileSelect(file);
                    }}
                >
                    <Upload size={48} className="mx-auto mb-4 text-white/20" />
                    <p className="text-white/60 mb-2">{t('branding.dropzone_text')}</p>
                    <p className="text-xs text-white/30 mb-4">
                        {t('branding.formats')}: PNG, JPG, SVG, WebP, ICO • {t('branding.max_size')}: 2MB
                    </p>
                    <label className="inline-block px-6 py-2.5 bg-purple-600 hover:bg-purple-700 text-white rounded-xl font-medium cursor-pointer transition-colors">
                        {t('branding.browse_files')}
                        <input
                            type="file"
                            className="hidden"
                            accept={ACCEPTED_FILE_TYPES}
                            onChange={(e) => handleFileSelect(e.target.files?.[0] || null)}
                        />
                    </label>
                </div>

                {/* Selected file preview */}
                {logoPreview && (
                    <div className="mt-6 p-4 bg-white/[0.02] rounded-xl border border-white/[0.06]">
                        <h3 className="text-sm font-medium text-white/70 mb-2">{t('branding.selected_file')}</h3>
                        <div className="flex items-center gap-4">
                            <img src={logoPreview} alt={t('branding.preview')} className="w-16 h-16 object-cover rounded-lg" />
                            <div className="flex-1">
                                <p className="text-white font-mono text-sm truncate">{logoFile?.name}</p>
                                <p className="text-xs text-white/40">{logoFile && (logoFile.size / 1024).toFixed(0)} KB</p>
                            </div>
                            <button
                                onClick={() => handleFileSelect(null)}
                                className="p-2 text-white/40 hover:text-red-400 hover:bg-red-500/10 rounded-lg"
                                title={t('common.remove')}
                            >
                                <Trash2 size={16} />
                            </button>
                        </div>
                    </div>
                )}

                {/* Error message */}
                {logoError && (
                    <div className="mt-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm rounded-xl flex items-center gap-2">
                        <AlertCircle size={16} /> {logoError}
                    </div>
                )}

                {/* Upload button */}
                <button
                    onClick={handleUpload}
                    disabled={!logoFile || !brandingTenantId || uploadingLogo}
                    className="w-full py-3 mt-6 bg-purple-600 hover:bg-purple-700 disabled:bg-white/[0.06] disabled:text-white/30 text-white rounded-xl font-semibold shadow-lg shadow-purple-600/20 transition-all flex justify-center items-center gap-2"
                >
                    {uploadingLogo ? <Loader2 className="animate-spin" /> : <CheckCircle2 size={18} />}
                    {uploadingLogo ? t('branding.uploading') : t('branding.upload_logo')}
                </button>
            </div>
        </div>
    );

    if (loading && !settings) {
        return (
            <div className="p-4 sm:p-6 flex items-center justify-center min-h-[400px]">
                <Loader2 className="w-8 h-8 animate-spin text-white/30" />
            </div>
        );
    }

    return (
        <div className="h-screen flex flex-col bg-[#0a0e1a] overflow-hidden">
            {/* Header & Tabs Area (Fixed) */}
            <div className="flex-none p-4 sm:p-6 pb-0 max-w-6xl mx-auto w-full">
                <PageHeader
                    title={t('config.title')}
                    subtitle={t('config.main_subtitle')}
                    icon={<Settings size={22} />}
                />

                {/* Error/Success Messages */}
                {error && (
                    <div className="mb-4 p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2 animate-in fade-in zoom-in duration-300">
                        <AlertTriangle size={18} /> {error}
                    </div>
                )}
                {success && (
                    <div className="mb-4 p-4 rounded-xl bg-green-500/10 border border-green-500/20 text-green-400 text-sm flex items-center gap-2 animate-in fade-in zoom-in duration-300">
                        <CheckCircle2 size={18} /> {success}
                    </div>
                )}

                {/* Tabs Header */}
                <div className="flex flex-nowrap border-b border-white/[0.06] mb-0 overflow-x-auto bg-white/[0.02] backdrop-blur-sm rounded-t-2xl px-2 scrollbar-hide">
                    <button
                        onClick={() => setActiveTab('general')}
                        className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${activeTab === 'general' ? 'border-indigo-600 text-indigo-600 font-semibold' : 'border-transparent text-white/40 hover:text-white/60 hover:border-white/[0.1]'}`}
                    >
                        <Globe size={18} /> General
                    </button>
                    {user?.role === 'ceo' && (
                        <>
                            <button
                                onClick={() => setActiveTab('ycloud')}
                                className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${activeTab === 'ycloud' ? 'border-green-600 text-green-600 font-semibold' : 'border-transparent text-white/40 hover:text-green-400 hover:border-green-500/20'}`}
                            >
                                <Zap size={18} /> YCloud (WhatsApp)
                            </button>
                            <button
                                onClick={() => setActiveTab('chatwoot')}
                                className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${activeTab === 'chatwoot' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent text-white/40 hover:text-blue-400 hover:border-blue-500/20'}`}
                            >
                                <MessageCircle size={18} /> Chatwoot (Meta)
                            </button>
                            <button
                                onClick={() => setActiveTab('others')}
                                className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${activeTab === 'others' ? 'border-indigo-500 text-indigo-500 font-semibold' : 'border-transparent text-white/40 hover:text-indigo-400 hover:border-indigo-500/20'}`}
                            >
                                <Key size={18} /> Otras
                            </button>
                            <button
                                onClick={() => setActiveTab('maintenance')}
                                className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${activeTab === 'maintenance' ? 'border-amber-600 text-amber-600 font-semibold' : 'border-transparent text-white/40 hover:text-amber-400 hover:border-amber-500/20'}`}
                            >
                                <Database size={18} /> Mantenimiento
                            </button>
                            <button
                                onClick={() => setActiveTab('branding')}
                                className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${activeTab === 'branding' ? 'border-purple-600 text-purple-600 font-semibold' : 'border-transparent text-white/40 hover:text-purple-400 hover:border-purple-500/20'}`}
                            >
                                <Image size={18} /> {t('branding.tab_title')}
                            </button>
                            <button
                                onClick={() => setActiveTab('leads')}
                                className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${activeTab === 'leads' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent text-white/40 hover:text-blue-400 hover:border-blue-500/20'}`}
                            >
                                <MessageSquare size={18} /> Leads Forms
                            </button>
                            <button
                                onClick={() => setActiveTab('meta')}
                                className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${activeTab === 'meta' ? 'border-blue-600 text-blue-600 font-semibold' : 'border-transparent text-white/40 hover:text-blue-400 hover:border-blue-500/20'}`}
                            >
                                <Facebook size={18} /> Meta
                            </button>
                            <button
                                onClick={() => setActiveTab('telegram')}
                                className={`px-6 py-4 font-medium text-sm whitespace-nowrap border-b-2 transition-all flex items-center gap-2 ${activeTab === 'telegram' ? 'border-sky-500 text-sky-400 font-semibold' : 'border-transparent text-white/40 hover:text-sky-400 hover:border-sky-500/20'}`}
                            >
                                <Send size={18} /> {t('telegram.tab_title')}
                            </button>
                        </>
                    )}
                </div>
            </div>

            {/* Content Area (Scrollable) */}
            <div className="flex-1 overflow-y-auto bg-transparent scrollbar-thin scrollbar-thumb-white/10">
                <div className="p-4 sm:p-6 max-w-6xl mx-auto pb-32">
                    {activeTab === 'general' && renderGeneralTab()}
                    {activeTab === 'ycloud' && user?.role === 'ceo' && renderYCloudTab()}
                    {activeTab === 'chatwoot' && user?.role === 'ceo' && renderChatwootTab()}
                    {activeTab === 'others' && user?.role === 'ceo' && renderOthersTab()}
                    {activeTab === 'maintenance' && user?.role === 'ceo' && renderMaintenanceTab()}
                    {activeTab === 'branding' && user?.role === 'ceo' && renderBrandingTab()}
                    {activeTab === 'leads' && user?.role === 'ceo' && renderLeadsTab()}
                    {activeTab === 'meta' && user?.role === 'ceo' && (
                        <Suspense fallback={<div className="flex justify-center py-20"><Loader2 size={24} className="animate-spin text-blue-600" /></div>}>
                            <MetaConnectionTab />
                        </Suspense>
                    )}
                    {activeTab === 'telegram' && user?.role === 'ceo' && (
                        <Suspense fallback={<div className="flex justify-center py-20"><Loader2 size={24} className="animate-spin text-sky-400" /></div>}>
                            <TelegramConfigTab />
                        </Suspense>
                    )}
                </div>
            </div>

            {/* Others Generic Credential Modal */}
            <Modal isOpen={isCredModalOpen} onClose={() => setIsCredModalOpen(false)} title={editingCred ? t('config.modal_edit_credential') : t('config.modal_new_credential')}>
                <form onSubmit={handleSaveGenericCredential} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-white/60 mb-1">{t('config.field_name_identifier')}</label>
                        <input
                            required
                            className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-indigo-500 outline-none"
                            value={credForm.name}
                            onChange={e => setCredForm({ ...credForm, name: e.target.value })}
                            placeholder="Ej: OpenAI Key Principal"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-white/60 mb-1">{t('config.field_value')}</label>
                        <input
                            required
                            type="password"
                            className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-indigo-500 outline-none font-mono text-sm"
                            value={credForm.value}
                            onChange={e => setCredForm({ ...credForm, value: e.target.value })}
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-white/60 mb-1">{t('config.field_category')}</label>
                            <select
                                className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-indigo-500 outline-none"
                                value={credForm.category}
                                onChange={e => setCredForm({ ...credForm, category: e.target.value })}
                            >
                                <option value="openai">OpenAI</option>
                                <option value="tiendanube">Tienda Nube</option>
                                <option value="icloud">iCloud</option>
                                <option value="database">Database</option>
                                <option value="other">Otro</option>
                            </select>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-white/60 mb-1">{t('config.field_scope')}</label>
                            <select
                                className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-indigo-500 outline-none"
                                value={credForm.scope}
                                onChange={e => setCredForm({ ...credForm, scope: e.target.value as 'global' | 'tenant' })}
                            >
                                <option value="global">{t('config.scope_global')}</option>
                                <option value="tenant">{t('config.scope_tenant')}</option>
                            </select>
                        </div>
                    </div>
                    {credForm.scope === 'tenant' && (
                        <div>
                            <label className="block text-sm font-medium text-white/60 mb-1">{t('config.field_assign_tenant')}</label>
                            <select
                                required
                                className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-indigo-500 outline-none"
                                value={credForm.tenant_id?.toString() || ''}
                                onChange={e => setCredForm({ ...credForm, tenant_id: parseInt(e.target.value) })}
                            >
                                <option value="">{t('config.select_placeholder')}</option>
                                {tenants.map(t => <option key={t.id} value={t.id}>{t.clinic_name}</option>)}
                            </select>
                        </div>
                    )}
                    <div className="flex justify-end gap-3 pt-4">
                        <button type="button" onClick={() => setIsCredModalOpen(false)} className="px-4 py-2 text-white/70 bg-white/[0.06] rounded-xl">{t('common.cancel')}</button>
                        <button type="submit" className="px-6 py-2 bg-indigo-600 text-white rounded-xl">{t('common.save')}</button>
                    </div>
                </form>
            </Modal>

            {/* AI Engine Mode Confirmation Modal */}
            <Modal 
                isOpen={engineModalOpen} 
                onClose={() => setEngineModalOpen(false)} 
                title={t('config.engine_confirm_title')}
            >
                <div className="space-y-4">
                    <p className="text-sm text-white/70">
                        {t('config.engine_confirm_message', { mode: engineTargetMode === 'multi' ? t('config.engine_multi') : t('config.engine_solo') })}
                    </p>

                    {engineHealthResult && (
                        <div className="space-y-2 bg-white/[0.03] rounded-lg p-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-white/60">TORA-solo:</span>
                                <span className={`text-sm font-medium ${engineHealthResult.solo?.ok ? 'text-green-400' : 'text-red-400'}`}>
                                    {engineHealthResult.solo?.ok ? '✓ OK' : '✗ Fail'}
                                    {engineHealthResult.solo?.latency_ms && ` (${engineHealthResult.solo.latency_ms}ms)`}
                                </span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-white/60">Multi-Agente:</span>
                                <span className={`text-sm font-medium ${engineHealthResult.multi?.ok ? 'text-green-400' : 'text-red-400'}`}>
                                    {engineHealthResult.multi?.ok ? '✓ OK' : '✗ Fail'}
                                    {engineHealthResult.multi?.latency_ms && ` (${engineHealthResult.multi.latency_ms}ms)`}
                                </span>
                            </div>
                            {engineHealthResult.multi?.detail && (
                                <p className="text-xs text-white/40 mt-2">{engineHealthResult.multi.detail}</p>
                            )}
                        </div>
                    )}

                    <div className="flex justify-end gap-3 pt-4">
                        <button 
                            type="button" 
                            onClick={() => setEngineModalOpen(false)} 
                            className="px-4 py-2 text-white/70 bg-white/[0.06] rounded-xl"
                        >
                            {t('common.cancel')}
                        </button>
                        <button 
                            type="button"
                            onClick={handleEngineModeConfirm}
                            disabled={saving || (engineTargetMode === 'multi' && !engineHealthResult?.multi?.ok)}
                            className="px-6 py-2 bg-indigo-600 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : t('config.engine_confirm_button')}
                        </button>
                    </div>
                </div>
            </Modal>
        </div>
    );

    // Render Leads Forms Tab
    function renderLeadsTab() {
        return (
            <Suspense fallback={
                <div className="flex items-center justify-center p-12">
                    <Loader2 className="w-8 h-8 text-blue-500 animate-spin" />
                    <span className="ml-3 text-white/60">Loading Leads Forms...</span>
                </div>
            }>
                <LeadsFormsTab />
            </Suspense>
        );
    }
}
