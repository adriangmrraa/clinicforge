```
import React, { useState, useEffect } from 'react';
import {
    MessageCircle, Key, CheckCircle, AlertTriangle,
    Store, Link as LinkIcon, User, X, Settings, Globe, Zap
} from 'lucide-react';
import { api } from '../../api/axios';

interface IntegrationWizardProps {
    onSuggestClose: () => void;
    onRefresh: () => void;
}

interface IntegrationConfig {
    provider: 'ycloud' | 'chatwoot';
    chatwoot_base_url?: string;
    chatwoot_api_token?: string;
    chatwoot_account_id?: string;
    ycloud_api_key?: string;
    ycloud_webhook_secret?: string;
    tenant_id: number | null;
}

interface Tenant {
    id: number;
    clinic_name: string;
}

export const IntegrationWizard: React.FC<IntegrationWizardProps> = ({ onSuggestClose, onRefresh }) => {
    const [provider, setProvider] = useState<'ycloud' | 'chatwoot'>('ycloud');
    const [config, setConfig] = useState<IntegrationConfig>({ provider: 'ycloud', tenant_id: null });
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    // Load Tenants on Mount (Replicating ChatsView logic)
    useEffect(() => {
        const loadTenants = async () => {
            try {
                const { data } = await api.get<Tenant[]>('/admin/chat/tenants');
                if (Array.isArray(data)) {
                    setTenants(data);
                    // Default to first tenant if available, similar to ChatsView
                    if (data.length > 0 && config.tenant_id === null) {
                        setConfig(prev => ({ ...prev, tenant_id: data[0].id }));
                    }
                }
            } catch (e) {
                console.error("Error loading tenants:", e);
            }
        };
        loadTenants();
    }, []);

    // Load Config on Provider or Tenant Change
    useEffect(() => {
        const loadConfig = async () => {
            setLoading(true);
            setError(null);
            setSuccess(false); // Reset success on change

            try {
                // Append tenant_id query param if selected
                const query = config.tenant_id ? `? tenant_id = ${ config.tenant_id } ` : '';
                const { data } = await api.get(`/ admin / integrations / ${ provider }/config${query}`);

// Merge loaded data with current provider/tenant selection
// We preserve tenant_id and provider from state, and overwrite config fields
setConfig(prev => ({
    ...prev,
    ...data,
    provider, // Ensure provider stays set
    tenant_id: prev.tenant_id // Ensure tenant_id stays set
}));
            } catch (err: any) {
    console.error("Error loading config:", err);
} finally {
    setLoading(false);
}
        };
loadConfig();
    }, [provider, config.tenant_id]);

const handleSave = async () => {
    setLoading(true);
    setError(null);
    setSuccess(false);

    // Validation
    if (provider === 'ycloud') {
        if (!config.ycloud_api_key) {
            setError("La API Key es obligatoria para WhatsApp (YCloud).");
            setLoading(false);
            return;
        }
        if (!config.ycloud_webhook_secret) {
            setError("El Webhook Secret es obligatorio para la seguridad de WhatsApp.");
            setLoading(false);
            return;
        }
    }

    if (provider === 'chatwoot') {
        if (!config.chatwoot_base_url) {
            setError("La URL base es obligatoria.");
            setLoading(false);
            return;
        }
        if (!config.chatwoot_api_token && !config.chatwoot_api_token?.startsWith("••••")) {
            if (!config.chatwoot_api_token) {
                setError("El API Token es obligatorio.");
                setLoading(false);
                return;
            }
        }
        if (!config.chatwoot_account_id) {
            setError("El Account ID es obligatorio.");
            setLoading(false);
            return;
        }
    }

    try {
        await api.post(`/admin/integrations/${provider}/config`, config);
        setSuccess(true);
        onRefresh();

        // Don't auto close immediately so user sees the success message and which tenant it was applied to
        setTimeout(onSuggestClose, 1500);
    } catch (err: any) {
        console.error("Error saving integration:", err);
        setError(err.message || "Error al guardar la integración.");
    } finally {
        setLoading(false);
    }
};

return (
    <div className="space-y-8 p-8 max-h-[85vh] overflow-y-auto custom-scrollbar">
        {/* Header */}
        <div className="text-center">
            <h2 className="text-3xl font-bold text-gray-900 tracking-tight mb-2">Asistente de Integración</h2>
            <p className="text-gray-500 text-lg">Conecta tus canales oficiales de forma segura.</p>
        </div>

        {/* Tenant Selector */}
        <div className="flex justify-center mb-6">
            <div className="inline-flex items-center bg-gray-50 rounded-lg p-1 border border-gray-200">
                <span className="px-3 text-sm font-medium text-gray-500 flex items-center gap-2">
                    <Store size={16} />
                    Sede:
                </span>
                <select
                    className="bg-transparent text-sm font-medium text-gray-800 py-1 pl-2 pr-8 outline-none cursor-pointer focus:ring-2 focus:ring-indigo-500 rounded-md transition-all"
                    value={config.tenant_id || ''}
                    onChange={(e) => setConfig({ ...config, tenant_id: e.target.value ? parseInt(e.target.value) : null })}
                >
                    <option value="">Global (Todas las Sedes)</option>
                    {tenants.map(t => (
                        <option key={t.id} value={t.id}>{t.clinic_name}</option>
                    ))}
                </select>
            </div>
        </div>

        {/* Provider Selector */}
        <div className="flex justify-center space-x-6">
            <button
                onClick={() => { setProvider('ycloud'); setSuccess(false); setError(null); }}
                className={`flex flex-col items-center p-6 rounded-2xl border-2 transition-all w-48 group ${provider === 'ycloud'
                    ? 'border-green-500 bg-green-50/50 shadow-md ring-2 ring-green-100'
                    : 'border-gray-100 hover:border-green-200 hover:bg-white text-gray-400 hover:shadow-lg'
                    }`}
            >
                <div className={`p-4 rounded-full mb-4 transition-colors ${provider === 'ycloud' ? 'bg-white shadow-sm' : 'bg-gray-50 group-hover:bg-green-50'}`}>
                    <MessageCircle className={`w-10 h-10 ${provider === 'ycloud' ? 'text-green-500' : 'text-gray-400 group-hover:text-green-400'}`} />
                </div>
                <span className={`font-bold text-lg ${provider === 'ycloud' ? 'text-gray-800' : 'text-gray-500'}`}>WhatsApp</span>
                <span className="text-xs font-medium mt-1 opacity-60">YCloud API</span>
            </button>

            <button
                onClick={() => { setProvider('chatwoot'); setSuccess(false); setError(null); }}
                className={`flex flex-col items-center p-6 rounded-2xl border-2 transition-all w-48 group ${provider === 'chatwoot'
                    ? 'border-blue-500 bg-blue-50/50 shadow-md ring-2 ring-blue-100'
                    : 'border-gray-100 hover:border-blue-200 hover:bg-white text-gray-400 hover:shadow-lg'
                    }`}
            >
                <div className={`p-4 rounded-full mb-4 transition-colors ${provider === 'chatwoot' ? 'bg-white shadow-sm' : 'bg-gray-50 group-hover:bg-blue-50'}`}>
                    <MessageCircle className={`w-10 h-10 ${provider === 'chatwoot' ? 'text-blue-500' : 'text-gray-400 group-hover:text-blue-400'}`} />
                </div>
                <span className={`font-bold text-lg ${provider === 'chatwoot' ? 'text-gray-800' : 'text-gray-500'}`}>Meta</span>
                <span className="text-xs font-medium mt-1 opacity-60">Chatwoot</span>
            </button>
        </div>

        {/* Dynamic Form */}
        <div className="bg-white p-8 rounded-2xl border border-gray-100 shadow-sm">
            {provider === 'ycloud' && (
                <div className="space-y-6 animate-fadeIn">
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">YCloud API Key</label>
                        <div className="relative group">
                            <input
                                type="password"
                                value={config.ycloud_api_key || ''}
                                onChange={(e) => setConfig({ ...config, ycloud_api_key: e.target.value })}
                                className="w-full pl-12 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all bg-gray-50 focus:bg-white group-hover:bg-white"
                                placeholder="Pegar API Key de YCloud..."
                            />
                            <Key className="w-5 h-5 text-gray-400 absolute left-4 top-3.5 transition-colors group-hover:text-green-500" />
                        </div>
                        <p className="text-xs text-gray-400 mt-2 ml-1">Requerido para enviar mensajes.</p>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">Webhook Secret</label>
                        <div className="relative group">
                            <input
                                type="password"
                                value={config.ycloud_webhook_secret || ''}
                                onChange={(e) => setConfig({ ...config, ycloud_webhook_secret: e.target.value })}
                                className="w-full pl-12 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all bg-gray-50 focus:bg-white group-hover:bg-white"
                                placeholder="Pegar Secret del Webhook..."
                            />
                            <Key className="w-5 h-5 text-gray-400 absolute left-4 top-3.5 transition-colors group-hover:text-green-500" />
                        </div>
                        <p className="text-xs text-gray-400 mt-2 ml-1">Requerido para validar mensajes entrantes.</p>
                    </div>
                </div>
            )}

            {provider === 'chatwoot' && (
                <div className="space-y-6 animate-fadeIn">
                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">Chatwoot URL</label>
                        <div className="relative group">
                            <input
                                type="text"
                                value={config.chatwoot_base_url || 'https://app.chatwoot.com'}
                                onChange={(e) => setConfig({ ...config, chatwoot_base_url: e.target.value })}
                                className="w-full pl-12 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all bg-gray-50 focus:bg-white group-hover:bg-white"
                                placeholder="https://app.chatwoot.com"
                            />
                            <LinkIcon className="w-5 h-5 text-gray-400 absolute left-4 top-3.5 transition-colors group-hover:text-blue-500" />
                        </div>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">User API Token</label>
                        <div className="relative group">
                            <input
                                type="password"
                                value={config.chatwoot_api_token || ''}
                                onChange={(e) => setConfig({ ...config, chatwoot_api_token: e.target.value })}
                                className="w-full pl-12 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all bg-gray-50 focus:bg-white group-hover:bg-white"
                                placeholder="Token de usuario administrador..."
                            />
                            <Key className="w-5 h-5 text-gray-400 absolute left-4 top-3.5 transition-colors group-hover:text-blue-500" />
                        </div>
                        <p className="text-xs text-gray-400 mt-2 ml-1">Perfil &gt; Configuración de perfil &gt; Token de acceso</p>
                    </div>

                    <div>
                        <label className="block text-sm font-semibold text-gray-700 mb-2">Account ID</label>
                        <div className="relative group">
                            <input
                                type="text"
                                value={config.chatwoot_account_id || ''}
                                onChange={(e) => setConfig({ ...config, chatwoot_account_id: e.target.value })}
                                className="w-full pl-12 pr-4 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all bg-gray-50 focus:bg-white group-hover:bg-white"
                                placeholder="Ej: 1"
                            />
                            <User className="w-5 h-5 text-gray-400 absolute left-4 top-3.5 transition-colors group-hover:text-blue-500" />
                        </div>
                        <p className="text-xs text-gray-400 mt-2 ml-1">ID numérico visible en la URL de Chatwoot (../accounts/<b>1</b>/...)</p>
                    </div>
                </div>
            )}
        </div>

        {/* Footer / Actions */}
        <div className="flex flex-col gap-4">
            {error && (
                <div className="bg-red-50 text-red-600 p-4 rounded-xl flex items-center animate-shake border border-red-100">
                    <AlertTriangle className="w-5 h-5 mr-3 flex-shrink-0" />
                    <span className="text-sm font-medium">{error}</span>
                </div>
            )}

            {success && (
                <div className="bg-green-50 text-green-700 p-4 rounded-xl flex items-center animate-fadeIn border border-green-100">
                    <CheckCircle className="w-5 h-5 mr-3 flex-shrink-0" />
                    <span className="text-sm font-medium">Configuración guardada correctamente.</span>
                </div>
            )}

            <div className="flex justify-end space-x-4 pt-4 border-t border-gray-100">
                <button
                    onClick={onSuggestClose}
                    className="px-6 py-3 text-gray-600 hover:text-gray-900 font-medium transition-colors"
                >
                    Cancelar
                </button>
                <button
                    onClick={handleSave}
                    disabled={loading}
                    className={`px-8 py-3 rounded-xl font-bold text-white shadow-lg transition-all transform hover:-translate-y-0.5 active:translate-y-0 flex items-center
                ${loading
                            ? 'bg-gray-400 cursor-not-allowed shadow-none'
                            : provider === 'ycloud' ? 'bg-green-600 hover:bg-green-700 shadow-green-200' : 'bg-blue-600 hover:bg-blue-700 shadow-blue-200'
                        }`}
                >
                    {loading ? (
                        <span className="flex items-center">
                            <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                            </svg>
                            Guardando...
                        </span>
                    ) : (
                        'Guardar Integración'
                    )}
                </button>
            </div>
        </div>
    </div>
);
};
