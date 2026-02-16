import { useState, useEffect } from 'react';
import { Settings, Globe, Loader2, CheckCircle2, Copy, MessageCircle } from 'lucide-react';
import api from '../api/axios';
import { fetchChatwootConfig } from '../api/chats';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';

type UiLanguage = 'es' | 'en' | 'fr';

interface ClinicSettings {
    name: string;
    location?: string;
    hours_start?: string;
    hours_end?: string;
    ui_language: UiLanguage;
}

const LANGUAGE_OPTIONS: { value: UiLanguage; labelKey: string }[] = [
    { value: 'es', labelKey: 'config.language_es' },
    { value: 'en', labelKey: 'config.language_en' },
    { value: 'fr', labelKey: 'config.language_fr' },
];

export default function ConfigView() {
    const { t, setLanguage } = useTranslation();
    const [settings, setSettings] = useState<ClinicSettings | null>(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);
    const [selectedLang, setSelectedLang] = useState<UiLanguage>('en');
    const [chatwootConfig, setChatwootConfig] = useState<{ webhook_path: string; access_token: string; api_base: string } | null>(null);
    const [chatwootConfigLoading, setChatwootConfigLoading] = useState(false);

    useEffect(() => {
        fetchSettings();
    }, []);

    useEffect(() => {
        const load = async () => {
            setChatwootConfigLoading(true);
            try {
                const c = await fetchChatwootConfig();
                setChatwootConfig(c);
            } catch {
                setChatwootConfig(null);
            } finally {
                setChatwootConfigLoading(false);
            }
        };
        load();
    }, []);

    const fetchSettings = async () => {
        try {
            setLoading(true);
            const res = await api.get<ClinicSettings>('/admin/settings/clinic');
            setSettings(res.data);
            setSelectedLang((res.data.ui_language as UiLanguage) || 'en');
        } catch (err) {
            setError(t('config.load_error'));
        } finally {
            setLoading(false);
        }
    };

    const handleLanguageChange = async (value: UiLanguage) => {
        setSelectedLang(value);
        setSuccess(null);
        setError(null);
        setLanguage(value);
        setSaving(true);
        try {
            await api.patch('/admin/settings/clinic', { ui_language: value });
            setSettings((prev) => (prev ? { ...prev, ui_language: value } : null));
            setSuccess(t('config.saved'));
        } catch (err) {
            setError(t('config.save_error'));
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="p-6 flex items-center justify-center min-h-[200px]">
                <Loader2 className="w-8 h-8 animate-spin text-gray-400" />
            </div>
        );
    }

    return (
        <div className="p-6 max-w-2xl">
            <PageHeader
                title={t('config.title')}
                subtitle={t('config.subtitle')}
                icon={<Settings size={22} />}
            />

            {settings && (
                <div className="space-y-6">
                    <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center gap-2 mb-4">
                            <Globe size={20} className="text-gray-600" />
                            <h2 className="text-lg font-semibold text-gray-800">{t('config.language_label')}</h2>
                        </div>
                        <p className="text-sm text-gray-500 mb-4">
                            {t('config.language_help')}
                        </p>
                        <div className="flex flex-wrap gap-3">
                            {LANGUAGE_OPTIONS.map((opt) => (
                                <button
                                    key={opt.value}
                                    type="button"
                                    onClick={() => handleLanguageChange(opt.value)}
                                    disabled={saving}
                                    className={`px-4 py-2.5 rounded-xl font-medium transition-colors border-2 min-h-[44px] touch-manipulation ${
                                        selectedLang === opt.value
                                            ? 'border-blue-600 bg-blue-50 text-blue-700'
                                            : 'border-gray-200 bg-white text-gray-700 hover:border-gray-300 hover:bg-gray-50'
                                    }`}
                                >
                                    {saving && selectedLang === opt.value ? (
                                        <Loader2 className="w-5 h-5 animate-spin inline-block" />
                                    ) : (
                                        t(opt.labelKey)
                                    )}
                                </button>
                            ))}
                        </div>
                        <p className="text-xs text-gray-400 mt-3">
                            {t('config.current_clinic')}: <strong>{settings.name}</strong>
                        </p>
                    </div>

                    {/* Sección Chatwoot: URL webhook para conectar inbox */}
                    <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
                        <div className="flex items-center gap-2 mb-4">
                            <MessageCircle size={20} className="text-indigo-600" />
                            <h2 className="text-lg font-semibold text-gray-800">Chatwoot</h2>
                        </div>
                        <p className="text-sm text-gray-500 mb-4">
                            Conecta tu inbox de Chatwoot (WhatsApp, Instagram, Facebook) para recibir y responder conversaciones desde esta plataforma. Usa la URL de webhook siguiente en la configuración de tu inbox.
                        </p>
                        {chatwootConfigLoading ? (
                            <div className="flex items-center gap-2 text-gray-500">
                                <Loader2 className="w-5 h-5 animate-spin" />
                                <span>Cargando configuración...</span>
                            </div>
                        ) : chatwootConfig ? (
                            <>
                                <div className="flex gap-2 mb-3">
                                    <input
                                        readOnly
                                        value={`${(chatwootConfig.api_base || '').replace(/\/$/, '')}${chatwootConfig.webhook_path}?access_token=${chatwootConfig.access_token}`}
                                        className="flex-1 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-sm font-mono"
                                    />
                                    <button
                                        type="button"
                                        onClick={() => {
                                            const url = `${(chatwootConfig.api_base || '').replace(/\/$/, '')}${chatwootConfig.webhook_path}?access_token=${chatwootConfig.access_token}`;
                                            navigator.clipboard.writeText(url);
                                            setSuccess('URL copiada al portapapeles');
                                            setTimeout(() => setSuccess(null), 3000);
                                        }}
                                        className="px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 flex items-center gap-2 shrink-0"
                                    >
                                        <Copy size={18} />
                                        Copiar
                                    </button>
                                </div>
                                <p className="text-xs text-gray-500">
                                    Pega esta URL en Chatwoot → Configuración del Inbox → Webhooks → URL del webhook. Así recibirás los mensajes en la bandeja de Chats de esta clínica.
                                </p>
                            </>
                        ) : (
                            <p className="text-sm text-amber-700">No se pudo cargar la configuración de Chatwoot. Comprueba que tienes acceso de administrador.</p>
                        )}
                    </div>
                </div>
            )}

            {error && (
                <div className="mt-4 p-4 rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm">
                    {error}
                </div>
            )}
            {success && (
                <div className="mt-4 p-4 rounded-xl bg-green-50 border border-green-200 text-green-700 text-sm flex items-center gap-2">
                    <CheckCircle2 size={18} />
                    {success}
                </div>
            )}
        </div>
    );
}
