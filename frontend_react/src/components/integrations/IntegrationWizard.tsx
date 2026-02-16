
import React, { useState, useEffect } from 'react';
import { useApi } from '../../hooks/useApi';
import { MessageCircle, CheckCircle, AlertTriangle, Key, Link as LinkIcon, User } from 'lucide-react';

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
}

export const IntegrationWizard: React.FC<IntegrationWizardProps> = ({ onSuggestClose, onRefresh }) => {
    const { fetchWithAuth } = useApi();
    const [provider, setProvider] = useState<'ycloud' | 'chatwoot'>('ycloud');
    const [config, setConfig] = useState<IntegrationConfig>({ provider: 'ycloud' });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);

    // Load existing config on provider change
    useEffect(() => {
        const loadConfig = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await fetchWithAuth(`/admin/integrations/${provider}/config`);
                setConfig({ provider, ...data });
            } catch (err: any) {
                console.error("Error loading config:", err);
                // Don't block UI on load error, just user might need to re-enter
            } finally {
                setLoading(false);
            }
        };
        loadConfig();
    }, [provider]);

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
                // If masking is present, user didn't change it, so it's technically valid to submit (backend handles it)
                // But if completely empty:
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
            await fetchWithAuth(`/admin/integrations/${provider}/config`, {
                method: 'POST',
                body: JSON.stringify(config),
            });
            setSuccess(true);
            onRefresh();
            setTimeout(onSuggestClose, 1500); // Close after success
        } catch (err: any) {
            console.error("Error saving integration:", err);
            setError(err.message || "Error al guardar la integración.");
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="text-center mb-8">
                <h2 className="text-2xl font-bold text-gray-900 mb-2">Asistente de Integración</h2>
                <p className="text-gray-500">Conecta tus canales de comunicación oficiales.</p>
            </div>

            {/* Provider Selector */}
            <div className="flex justify-center space-x-4 mb-8">
                <button
                    onClick={() => { setProvider('ycloud'); setSuccess(false); setError(null); }}
                    className={`flex flex-col items-center p-4 rounded-xl border-2 transition-all w-40 ${provider === 'ycloud'
                            ? 'border-green-500 bg-green-50 text-green-700'
                            : 'border-gray-200 hover:border-green-200 text-gray-500'
                        }`}
                >
                    <div className="p-3 bg-white rounded-full shadow-sm mb-3">
                        <MessageCircle className={`w-8 h-8 ${provider === 'ycloud' ? 'text-green-500' : 'text-gray-400'}`} />
                    </div>
                    <span className="font-semibold">WhatsApp</span>
                    <span className="text-xs mt-1 opacity-70">YCloud API</span>
                </button>

                <button
                    onClick={() => { setProvider('chatwoot'); setSuccess(false); setError(null); }}
                    className={`flex flex-col items-center p-4 rounded-xl border-2 transition-all w-40 ${provider === 'chatwoot'
                            ? 'border-blue-500 bg-blue-50 text-blue-700'
                            : 'border-gray-200 hover:border-blue-200 text-gray-500'
                        }`}
                >
                    <div className="p-3 bg-white rounded-full shadow-sm mb-3">
                        <MessageCircle className={`w-8 h-8 ${provider === 'chatwoot' ? 'text-blue-500' : 'text-gray-400'}`} />
                    </div>
                    <span className="font-semibold">Meta</span>
                    <span className="text-xs mt-1 opacity-70">Chatwoot</span>
                </button>
            </div>

            {/* Dynamic Form */}
            <div className="bg-gray-50 p-6 rounded-xl border border-gray-200">
                {provider === 'ycloud' && (
                    <div className="space-y-4 animate-fadeIn">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">YCloud API Key</label>
                            <div className="relative">
                                <input
                                    type="password"
                                    value={config.ycloud_api_key || ''}
                                    onChange={(e) => setConfig({ ...config, ycloud_api_key: e.target.value })}
                                    className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all"
                                    placeholder="Pegar API Key de YCloud..."
                                />
                                <Key className="w-5 h-5 text-gray-400 absolute left-3 top-2.5" />
                            </div>
                            <p className="text-xs text-gray-500 mt-1">Requerido para enviar mensajes.</p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Webhook Secret</label>
                            <div className="relative">
                                <input
                                    type="password"
                                    value={config.ycloud_webhook_secret || ''}
                                    onChange={(e) => setConfig({ ...config, ycloud_webhook_secret: e.target.value })}
                                    className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all"
                                    placeholder="Pegar Secret del Webhook..."
                                />
                                <Key className="w-5 h-5 text-gray-400 absolute left-3 top-2.5" />
                            </div>
                            <p className="text-xs text-gray-500 mt-1">Requerido para validar mensajes entrantes.</p>
                        </div>
                    </div>
                )}

                {provider === 'chatwoot' && (
                    <div className="space-y-4 animate-fadeIn">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Chatwoot URL</label>
                            <div className="relative">
                                <input
                                    type="text"
                                    value={config.chatwoot_base_url || 'https://app.chatwoot.com'}
                                    onChange={(e) => setConfig({ ...config, chatwoot_base_url: e.target.value })}
                                    className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                                    placeholder="https://app.chatwoot.com"
                                />
                                <LinkIcon className="w-5 h-5 text-gray-400 absolute left-3 top-2.5" />
                            </div>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">User API Token</label>
                            <div className="relative">
                                <input
                                    type="password"
                                    value={config.chatwoot_api_token || ''}
                                    onChange={(e) => setConfig({ ...config, chatwoot_api_token: e.target.value })}
                                    className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                                    placeholder="Token de usuario administrador..."
                                />
                                <Key className="w-5 h-5 text-gray-400 absolute left-3 top-2.5" />
                            </div>
                            <p className="text-xs text-gray-500 mt-1">Perfil &gt; Configuración de perfil &gt; Token de acceso</p>
                        </div>

                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-1">Account ID</label>
                            <div className="relative">
                                <input
                                    type="text"
                                    value={config.chatwoot_account_id || ''}
                                    onChange={(e) => setConfig({ ...config, chatwoot_account_id: e.target.value })}
                                    className="w-full pl-10 pr-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                                    placeholder="Ej: 1"
                                />
                                <User className="w-5 h-5 text-gray-400 absolute left-3 top-2.5" />
                            </div>
                            <p className="text-xs text-gray-500 mt-1">ID numérico visible en la URL de Chatwoot (../accounts/<b>1</b>/...)</p>
                        </div>
                    </div>
                )}
            </div>

            {/* Messages */}
            {error && (
                <div className="bg-red-50 text-red-600 p-4 rounded-lg flex items-center animate-shake">
                    <AlertTriangle className="w-5 h-5 mr-3 flex-shrink-0" />
                    <span className="text-sm">{error}</span>
                </div>
            )}

            {success && (
                <div className="bg-green-50 text-green-600 p-4 rounded-lg flex items-center animate-fadeIn">
                    <CheckCircle className="w-5 h-5 mr-3 flex-shrink-0" />
                    <span className="text-sm">Configuración guardada correctamente.</span>
                </div>
            )}

            {/* Actions */}
            <div className="flex justify-end space-x-3 pt-4 border-t border-gray-100">
                <button
                    onClick={onSuggestClose}
                    className="px-6 py-2 text-gray-600 hover:text-gray-800 font-medium transition-colors"
                >
                    Cancelar
                </button>
                <button
                    onClick={handleSave}
                    disabled={loading}
                    className={`px-6 py-2 rounded-lg font-medium text-white shadow-lg shadow-blue-500/30 transition-all transform active:scale-95 flex items-center
            ${loading
                            ? 'bg-gray-400 cursor-not-allowed'
                            : provider === 'ycloud' ? 'bg-green-600 hover:bg-green-700' : 'bg-blue-600 hover:bg-blue-700'
                        }`}
                >
                    {loading ? (
                        <span className="flex items-center">
                            <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
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
    );
};
