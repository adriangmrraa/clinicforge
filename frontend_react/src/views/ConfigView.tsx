import React, { useState, useEffect } from 'react';
import { Settings, Globe, Loader2, CheckCircle2, Copy, MessageCircle, Key, Shield, Zap, User, Store, AlertTriangle, Trash2, Edit2, Link as LinkIcon, Plus } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';
import { useAuth } from '../context/AuthContext';
import { Modal } from '../components/Modal';

type UiLanguage = 'es' | 'en' | 'fr';

interface ClinicSettings {
    name: string;
    ui_language: UiLanguage;
}

const LANGUAGE_OPTIONS: { value: UiLanguage; labelKey: string }[] = [
    { value: 'es', labelKey: 'config.language_es' },
    { value: 'en', labelKey: 'config.language_en' },
    { value: 'fr', labelKey: 'config.language_fr' },
];

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
    const { t, setLanguage } = useTranslation();
    const { user } = useAuth();
    const [activeTab, setActiveTab] = useState<'general' | 'ycloud' | 'chatwoot' | 'others'>('general');

    // General Settings State
    const [settings, setSettings] = useState<ClinicSettings | null>(null);
    const [selectedLang, setSelectedLang] = useState<UiLanguage>('en');

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
            setSelectedLang((res.data.ui_language as UiLanguage) || 'en');
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

    const loadIntegrationConfig = async (provider: 'ycloud' | 'chatwoot', tenantId: number | null) => {
        try {
            setLoading(true);
            const query = tenantId ? `?tenant_id=${tenantId}` : '';
            const { data } = await api.get(`/admin/integrations/${provider}/config${query}`);

            setIntConfig(prev => ({
                ...prev,
                ...data, // This will overwrite fields like api_key, base_url etc.
                provider,
                tenant_id: tenantId // Request config for specific tenant, but keep current selection
            }));

            // For YCloud, we might need deployment config for the webhook URL if not returned by integration endpoint
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

    // --- HANDLERS ---

    const handleLanguageChange = async (value: UiLanguage) => {
        setSelectedLang(value);
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

    const handleSaveIntegration = async () => {
        setSaving(true);
        setError(null);
        try {
            await api.post(`/admin/integrations/${intConfig.provider}/config`, intConfig);
            showSuccess(`Configuración de ${intConfig.provider === 'ycloud' ? 'WhatsApp' : 'Chatwoot'} guardada.`);
            loadCredentials(); // Refresh table
        } catch (err: any) {
            setError(err.message || "Error al guardar integración.");
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
            showSuccess("Credencial guardada.");
        } catch (e: any) {
            alert('Error: ' + e.message);
        }
    };

    const handleDeleteCredential = async (id: number) => {
        if (!confirm('¿Eliminar esta credencial?')) return;
        try {
            await api.delete(`/admin/credentials/${id}`);
            loadCredentials();
            showSuccess("Credencial eliminada.");
        } catch (e: any) {
            alert('Error: ' + e.message);
        }
    };

    const showSuccess = (msg: string) => {
        setSuccess(msg);
        setTimeout(() => setSuccess(null), 3000);
    }

    const copyToClipboard = (text: string) => {
        navigator.clipboard.writeText(text);
        showSuccess('Copiado al portapapeles');
    };

    // --- RENDER HELPERS ---

    const getTenantName = (id: number | null | undefined) => {
        if (!id) return "Global";
        const t = tenants.find(t => t.id === id);
        return t ? t.clinic_name : `ID: ${id}`;
    }

    // --- TABS CONTENT ---

    const renderGeneralTab = () => (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
                <div className="flex items-center gap-2 mb-4">
                    <Globe size={20} className="text-gray-600" />
                    <h2 className="text-lg font-semibold text-gray-800">{t('config.language_label')}</h2>
                </div>
                <p className="text-sm text-gray-500 mb-4">{t('config.language_help')}</p>
                <div className="flex flex-wrap gap-3">
                    {LANGUAGE_OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            onClick={() => handleLanguageChange(opt.value)}
                            disabled={saving}
                            className={`px-4 py-2.5 rounded-xl font-medium transition-colors border-2 min-h-[44px] ${selectedLang === opt.value
                                ? 'border-blue-600 bg-blue-50 text-blue-700'
                                : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50'
                                }`}
                        >
                            {saving && selectedLang === opt.value ? <Loader2 className="w-5 h-5 animate-spin" /> : t(opt.labelKey)}
                        </button>
                    ))}
                </div>
                {settings && (
                    <p className="text-xs text-gray-400 mt-3">
                        {t('config.current_clinic')}: <strong>{settings.name}</strong>
                    </p>
                )}
            </div>
        </div>
    );

    const renderYCloudTab = () => (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-2 duration-300">
            {/* 1. Webhook Info */}
            <div className="bg-green-50 border border-green-200 rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-2 text-green-800">
                    <Zap className="w-5 h-5" />
                    <h3 className="font-semibold">Webhook para WhatsApp (YCloud)</h3>
                </div>
                <p className="text-sm text-green-700 mb-4">Configura este Webhook en tu consola de YCloud para recibir mensajes.</p>
                <div className="flex gap-2">
                    <input readOnly value={intConfig.ycloud_webhook_url || 'Cargando...'} className="flex-1 px-3 py-2 bg-white rounded-lg border border-green-200 text-sm font-mono text-gray-600" />
                    <button onClick={() => copyToClipboard(intConfig.ycloud_webhook_url || '')} className="px-3 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition">
                        <Copy size={16} />
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* 2. Form */}
                <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm h-fit">
                    <h2 className="text-lg font-semibold text-gray-900 mb-6 flex items-center gap-2">
                        <MessageCircle className="text-green-600" size={20} />
                        Configurar Credenciales
                    </h2>

                    <div className="space-y-4">
                        <div>
                            <label className="text-sm font-medium text-gray-700 mb-1 block">Sede (Tenant)</label>
                            <select
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 outline-none"
                                value={intConfig.tenant_id === null ? '' : intConfig.tenant_id}
                                onChange={(e) => setIntConfig({ ...intConfig, tenant_id: e.target.value ? Number(e.target.value) : null })}
                            >
                                <option value="">Global (Todas las Sedes)</option>
                                {tenants.map(t => <option key={t.id} value={t.id}>{t.clinic_name}</option>)}
                            </select>
                        </div>

                        <div>
                            <label className="text-sm font-medium text-gray-700 mb-1 block">YCloud API Key</label>
                            <input
                                type="password"
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 outline-none"
                                placeholder="sk_..."
                                value={intConfig.ycloud_api_key || ''}
                                onChange={e => setIntConfig({ ...intConfig, ycloud_api_key: e.target.value })}
                            />
                        </div>

                        <div>
                            <label className="text-sm font-medium text-gray-700 mb-1 block">Webhook Secret</label>
                            <input
                                type="password"
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-green-500 outline-none"
                                placeholder="whsec_..."
                                value={intConfig.ycloud_webhook_secret || ''}
                                onChange={e => setIntConfig({ ...intConfig, ycloud_webhook_secret: e.target.value })}
                            />
                        </div>

                        <button
                            onClick={handleSaveIntegration}
                            disabled={saving}
                            className="w-full py-2.5 bg-green-600 hover:bg-green-700 text-white rounded-xl font-medium shadow-lg shadow-green-600/20 transition-all flex justify-center items-center gap-2"
                        >
                            {saving ? <Loader2 className="animate-spin" /> : "Guardar Configuración"}
                        </button>
                    </div>
                </div>

                {/* 3. Table */}
                <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm overflow-hidden flex flex-col">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">Credenciales Activas</h2>
                    <div className="overflow-y-auto flex-1 min-h-[300px]">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-gray-50 text-gray-500">
                                <tr>
                                    <th className="px-4 py-3 rounded-l-lg">Sede</th>
                                    <th className="px-4 py-3">Estado</th>
                                    <th className="px-4 py-3 rounded-r-lg text-right">Acciones</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {credentials.filter(c => c.category === 'ycloud' && c.name === 'YCLOUD_API_KEY').map(c => (
                                    <tr key={c.id} className="hover:bg-gray-50/50">
                                        <td className="px-4 py-3 font-medium text-gray-900">{getTenantName(c.tenant_id)}</td>
                                        <td className="px-4 py-3 text-green-600 flex items-center gap-1">
                                            <CheckCircle2 size={14} /> Configurado
                                        </td>
                                        <td className="px-4 py-3 text-right">
                                            <button
                                                onClick={() => setIntConfig({ ...intConfig, tenant_id: c.tenant_id || null })}
                                                className="text-indigo-600 hover:bg-indigo-50 p-1.5 rounded-md transition"
                                            >
                                                <Edit2 size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                {credentials.filter(c => c.category === 'ycloud').length === 0 && (
                                    <tr><td colSpan={3} className="px-4 py-8 text-center text-gray-400">No hay credenciales configuradas.</td></tr>
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
            <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6">
                <div className="flex items-center gap-2 mb-2 text-blue-800">
                    <MessageCircle className="w-5 h-5" />
                    <h3 className="font-semibold">Webhook para Chatwoot (Meta)</h3>
                </div>
                <p className="text-sm text-blue-700 mb-4">Usa esta URL en la configuración de "Inbox" de Chatwoot para recibir mensajes de IG/FB.</p>
                <div className="flex gap-2">
                    <input readOnly value={intConfig.full_webhook_url || 'Cargando...'} className="flex-1 px-3 py-2 bg-white rounded-lg border border-blue-200 text-sm font-mono text-gray-600" />
                    <button onClick={() => copyToClipboard(intConfig.full_webhook_url || '')} className="px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">
                        <Copy size={16} />
                    </button>
                </div>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* 2. Form */}
                <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm h-fit">
                    <h2 className="text-lg font-semibold text-gray-900 mb-6 flex items-center gap-2">
                        <User className="text-blue-600" size={20} />
                        Configurar Credenciales
                    </h2>

                    <div className="space-y-4">
                        <div>
                            <label className="text-sm font-medium text-gray-700 mb-1 block">Sede (Tenant)</label>
                            <select
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                                value={intConfig.tenant_id === null ? '' : intConfig.tenant_id}
                                onChange={(e) => setIntConfig({ ...intConfig, tenant_id: e.target.value ? Number(e.target.value) : null })}
                            >
                                <option value="">Global (Todas las Sedes)</option>
                                {tenants.map(t => <option key={t.id} value={t.id}>{t.clinic_name}</option>)}
                            </select>
                        </div>

                        <div>
                            <label className="text-sm font-medium text-gray-700 mb-1 block">Chatwoot Base URL</label>
                            <input
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                                placeholder="https://app.chatwoot.com"
                                value={intConfig.chatwoot_base_url || ''}
                                onChange={e => setIntConfig({ ...intConfig, chatwoot_base_url: e.target.value })}
                            />
                        </div>

                        <div>
                            <label className="text-sm font-medium text-gray-700 mb-1 block">Account ID</label>
                            <input
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                                placeholder="Ej: 1"
                                value={intConfig.chatwoot_account_id || ''}
                                onChange={e => setIntConfig({ ...intConfig, chatwoot_account_id: e.target.value })}
                            />
                        </div>

                        <div>
                            <label className="text-sm font-medium text-gray-700 mb-1 block">User API Token</label>
                            <input
                                type="password"
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none"
                                placeholder="Token de administrador..."
                                value={intConfig.chatwoot_api_token || ''}
                                onChange={e => setIntConfig({ ...intConfig, chatwoot_api_token: e.target.value })}
                            />
                        </div>

                        <button
                            onClick={handleSaveIntegration}
                            disabled={saving}
                            className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium shadow-lg shadow-blue-600/20 transition-all flex justify-center items-center gap-2"
                        >
                            {saving ? <Loader2 className="animate-spin" /> : "Guardar Configuración"}
                        </button>
                    </div>
                </div>

                {/* 3. Table */}
                <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm overflow-hidden flex flex-col">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">Credenciales Activas</h2>
                    <div className="overflow-y-auto flex-1 min-h-[300px]">
                        <table className="w-full text-left text-sm">
                            <thead className="bg-gray-50 text-gray-500">
                                <tr>
                                    <th className="px-4 py-3 rounded-l-lg">Sede</th>
                                    <th className="px-4 py-3">Account ID</th>
                                    <th className="px-4 py-3 rounded-r-lg text-right">Acciones</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                                {/* We group by tenant to avoid checking multiple rows, but here we just list the Account ID row primarily */}
                                {credentials.filter(c => c.category === 'chatwoot' && c.name === 'CHATWOOT_ACCOUNT_ID').map(c => (
                                    <tr key={c.id} className="hover:bg-gray-50/50">
                                        <td className="px-4 py-3 font-medium text-gray-900">{getTenantName(c.tenant_id)}</td>
                                        <td className="px-4 py-3 text-gray-600">{c.value}</td>
                                        <td className="px-4 py-3 text-right">
                                            <button
                                                onClick={() => setIntConfig({ ...intConfig, tenant_id: c.tenant_id || null })}
                                                className="text-indigo-600 hover:bg-indigo-50 p-1.5 rounded-md transition"
                                            >
                                                <Edit2 size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                {credentials.filter(c => c.category === 'chatwoot').length === 0 && (
                                    <tr><td colSpan={3} className="px-4 py-8 text-center text-gray-400">No hay credenciales configuradas.</td></tr>
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
            <div className="flex justify-between items-center bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
                <div>
                    <h2 className="text-lg font-semibold text-gray-900">Otras Integraciones</h2>
                    <p className="text-sm text-gray-500">Gestión de claves para OpenAI, TiendaNube, Bases de Datos, etc.</p>
                </div>
                <button
                    onClick={() => { setEditingCred(null); setCredForm({ name: '', value: '', category: 'openai', description: '', scope: 'global', tenant_id: null }); setIsCredModalOpen(true); }}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 flex items-center gap-2 font-medium"
                >
                    <Plus size={18} /> Nueva
                </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                {credentials.filter(c => !['ycloud', 'chatwoot'].includes(c.category)).map(cred => (
                    <div key={cred.id} className="bg-white border border-gray-200 rounded-2xl p-5 hover:shadow-md transition-shadow group relative overflow-hidden">
                        <div className={`absolute top-0 left-0 w-1 h-full rounded-l-2xl ${cred.scope === 'global' ? 'bg-indigo-500' : 'bg-emerald-500'}`}></div>
                        <div className="flex justify-between items-start mb-3 pl-2">
                            <div>
                                <h4 className="font-semibold text-gray-800 leading-tight">{cred.name}</h4>
                                <span className="inline-flex items-center gap-1.5 mt-1 px-2 py-0.5 rounded-md bg-gray-100 text-xs text-gray-600 font-medium lowercase">
                                    {cred.category} • {cred.scope === 'global' ? 'Global' : getTenantName(cred.tenant_id)}
                                </span>
                            </div>
                            <div className="flex gap-1 group-hover:opacity-100 opacity-0 transition-opacity">
                                <button onClick={() => { setEditingCred(cred); setCredForm({ ...cred, value: '••••••••' }); setIsCredModalOpen(true); }} className="p-1.5 hover:bg-gray-100 rounded-lg text-gray-500 hover:text-indigo-600">
                                    <Edit2 size={16} />
                                </button>
                                <button onClick={() => handleDeleteCredential(cred.id!)} className="p-1.5 hover:bg-rose-50 rounded-lg text-gray-400 hover:text-rose-600">
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>
                        <div className="pl-2">
                            <div className="bg-gray-50 rounded-lg px-3 py-2 font-mono text-xs text-gray-500 border border-gray-100 flex items-center gap-2">
                                <Key size={12} className="text-gray-400" />
                                {cred.value.substring(0, 16)}...
                            </div>
                        </div>
                    </div>
                ))}
                {credentials.filter(c => !['ycloud', 'chatwoot'].includes(c.category)).length === 0 && (
                    <div className="col-span-full py-12 text-center text-gray-400 bg-gray-50 rounded-2xl border border-dashed border-gray-200">
                        No hay otras credenciales registradas.
                    </div>
                )}
            </div>
        </div>
    );

    if (loading && !settings) {
        return (
            <div className="p-6 flex items-center justify-center min-h-[400px]">
                <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
            </div>
        );
    }

    return (
        <div className="p-6 max-w-6xl mx-auto">
            <PageHeader
                title={t('config.title')}
                subtitle="Gestión centralizada de la clínica y canales de comunicación."
                icon={<Settings size={22} />}
            />

            {/* Error/Success Messages */}
            {error && (
                <div className="mb-6 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm flex items-center gap-2">
                    <AlertTriangle size={18} /> {error}
                </div>
            )}
            {success && (
                <div className="mb-6 p-4 rounded-xl bg-green-50 border border-green-200 text-green-700 text-sm flex items-center gap-2">
                    <CheckCircle2 size={18} /> {success}
                </div>
            )}

            {/* Tabs Header */}
            <div className="flex border-b border-gray-200 mb-8 overflow-x-auto">
                <button
                    onClick={() => setActiveTab('general')}
                    className={`px-6 py-3 font-medium text-sm whitespace-nowrap border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'general' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`}
                >
                    <Globe size={18} /> General
                </button>
                {user?.role === 'ceo' && (
                    <>
                        <button
                            onClick={() => setActiveTab('ycloud')}
                            className={`px-6 py-3 font-medium text-sm whitespace-nowrap border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'ycloud' ? 'border-green-600 text-green-600' : 'border-transparent text-gray-500 hover:text-green-600 hover:border-green-200'}`}
                        >
                            <Zap size={18} /> YCloud (WhatsApp)
                        </button>
                        <button
                            onClick={() => setActiveTab('chatwoot')}
                            className={`px-6 py-3 font-medium text-sm whitespace-nowrap border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'chatwoot' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-blue-600 hover:border-blue-200'}`}
                        >
                            <MessageCircle size={18} /> Chatwoot (Meta)
                        </button>
                        <button
                            onClick={() => setActiveTab('others')}
                            className={`px-6 py-3 font-medium text-sm whitespace-nowrap border-b-2 transition-colors flex items-center gap-2 ${activeTab === 'others' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-500 hover:text-indigo-600 hover:border-indigo-200'}`}
                        >
                            <Key size={18} /> Otras
                        </button>
                    </>
                )}
            </div>

            {/* Tabs Content */}
            <div className="min-h-[400px]">
                {activeTab === 'general' && renderGeneralTab()}
                {activeTab === 'ycloud' && user?.role === 'ceo' && renderYCloudTab()}
                {activeTab === 'chatwoot' && user?.role === 'ceo' && renderChatwootTab()}
                {activeTab === 'others' && user?.role === 'ceo' && renderOthersTab()}
            </div>

            {/* Others Generic Credential Modal */}
            <Modal isOpen={isCredModalOpen} onClose={() => setIsCredModalOpen(false)} title={editingCred ? 'Editar Credencial' : 'Nueva Credencial'}>
                <form onSubmit={handleSaveGenericCredential} className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Nombre Identificador</label>
                        <input
                            required
                            className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
                            value={credForm.name}
                            onChange={e => setCredForm({ ...credForm, name: e.target.value })}
                            placeholder="Ej: OpenAI Key Principal"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">Valor (Token/Key)</label>
                        <input
                            required
                            type="password"
                            className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-mono text-sm"
                            value={credForm.value}
                            onChange={e => setCredForm({ ...credForm, value: e.target.value })}
                        />
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Categoría</label>
                            <select
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
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
                            <label className="block text-sm font-medium text-gray-700 mb-1">Alcance</label>
                            <select
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
                                value={credForm.scope}
                                onChange={e => setCredForm({ ...credForm, scope: e.target.value as 'global' | 'tenant' })}
                            >
                                <option value="global">Global</option>
                                <option value="tenant">Por Sede</option>
                            </select>
                        </div>
                    </div>
                    {credForm.scope === 'tenant' && (
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Asignar a Sede</label>
                            <select
                                required
                                className="w-full px-4 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none bg-white"
                                value={credForm.tenant_id?.toString() || ''}
                                onChange={e => setCredForm({ ...credForm, tenant_id: parseInt(e.target.value) })}
                            >
                                <option value="">Seleccionar...</option>
                                {tenants.map(t => <option key={t.id} value={t.id}>{t.clinic_name}</option>)}
                            </select>
                        </div>
                    )}
                    <div className="flex justify-end gap-3 pt-4">
                        <button type="button" onClick={() => setIsCredModalOpen(false)} className="px-4 py-2 text-gray-600 bg-gray-100 rounded-xl">Cancelar</button>
                        <button type="submit" className="px-6 py-2 bg-indigo-600 text-white rounded-xl">Guardar</button>
                    </div>
                </form>
            </Modal>
        </div>
    );
}
