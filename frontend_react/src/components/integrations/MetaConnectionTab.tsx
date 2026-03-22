import React, { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '../../context/LanguageContext';
import { Facebook, Instagram, MessageCircle, Check, Loader2, AlertTriangle, Trash2, RefreshCw } from 'lucide-react';
import { useFacebookSdk } from '../../hooks/useFacebookSdk';
import api from '../../api/axios';

interface MetaAssets {
    pages: Array<{ id: string; name: string }>;
    instagram: Array<{ id: string; username: string }>;
    whatsapp: Array<{ id: string; name: string; phone_numbers: Array<{ display_phone_number: string }> }>;
}

const MetaConnectionTab: React.FC = () => {
    const { t } = useTranslation();
    const isSdkReady = useFacebookSdk();

    const [status, setStatus] = useState<'loading' | 'idle' | 'connecting' | 'connected' | 'error'>('loading');
    const [errorMsg, setErrorMsg] = useState('');
    const [assets, setAssets] = useState<MetaAssets | null>(null);
    const [disconnecting, setDisconnecting] = useState(false);

    // Check connection status on mount
    const checkStatus = useCallback(async () => {
        try {
            const { data } = await api.get('/admin/meta/status');
            if (data.connected) {
                setAssets(data.assets);
                setStatus('connected');
            } else {
                setStatus('idle');
            }
        } catch {
            setStatus('idle');
        }
    }, []);

    useEffect(() => {
        checkStatus();
    }, [checkStatus]);

    const handleLogin = () => {
        if (!isSdkReady || !window.FB) {
            setErrorMsg('El SDK de Facebook no pudo cargarse. Revisa que no tengas un bloqueador de anuncios activo.');
            setStatus('error');
            return;
        }

        setStatus('connecting');
        setErrorMsg('');

        const loginParams: any = {
            config_id: import.meta.env.VITE_META_CONFIG_ID,
            response_type: 'code',
            override_default_response_type: true,
        };

        if (import.meta.env.VITE_META_EMBEDDED_SIGNUP === 'true') {
            loginParams.extras = {
                feature: 'whatsapp_embedded_signup',
                setup: {}
            };
        }

        window.FB.login((response: any) => {
            const code = response.authResponse?.code || response.code;
            const accessToken = response.authResponse?.accessToken;

            if (accessToken) {
                connectWithBackend(accessToken, 'token');
            } else if (code) {
                connectWithBackend(code, 'code');
            } else {
                setStatus('idle');
                if (response.status !== 'connected' && response.status !== 'unknown') {
                    setErrorMsg('No se recibio autorizacion de Meta.');
                    setStatus('error');
                }
            }
        }, loginParams);
    };

    const connectWithBackend = async (credential: string, type: 'code' | 'token') => {
        try {
            const redirectUri = window.location.href.split('?')[0].split('#')[0];
            const { data } = await api.post('/admin/meta/connect', {
                ...(type === 'code' ? { code: credential } : { access_token: credential }),
                redirect_uri: redirectUri
            });

            if (data.status === 'success') {
                setAssets(data.assets);
                setStatus('connected');
            } else {
                setStatus('error');
                setErrorMsg(data.message || 'La conexion no se completo correctamente.');
            }
        } catch (e: any) {
            setStatus('error');
            setErrorMsg(e.response?.data?.detail || e.message || 'Error connecting to server');
        }
    };

    const handleDisconnect = async () => {
        if (!confirm('Estas seguro? Se eliminaran todas las credenciales, conversaciones y mensajes de Meta Direct para esta clinica.')) {
            return;
        }
        setDisconnecting(true);
        try {
            await api.delete('/admin/meta/disconnect');
            setAssets(null);
            setStatus('idle');
        } catch (e: any) {
            setErrorMsg(e.response?.data?.detail || 'Error al desconectar');
            setStatus('error');
        } finally {
            setDisconnecting(false);
        }
    };

    // Loading state
    if (status === 'loading') {
        return (
            <div className="flex items-center justify-center py-20">
                <Loader2 size={24} className="animate-spin text-blue-600" />
            </div>
        );
    }

    // Connected state
    if (status === 'connected' && assets) {
        return (
            <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
                <div className="bg-white border border-gray-200 rounded-2xl p-8 shadow-sm">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-10 h-10 rounded-full bg-green-100 flex items-center justify-center">
                            <Check size={20} className="text-green-600" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-gray-900">Meta conectado</h2>
                            <p className="text-sm text-gray-500">Canales activos recibiendo mensajes</p>
                        </div>
                    </div>

                    {/* Asset Cards */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                        <div className={`p-4 rounded-xl border flex flex-col items-center gap-2 ${assets.pages.length > 0 ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 border-gray-200 opacity-50'}`}>
                            <Facebook size={24} className={assets.pages.length > 0 ? 'text-blue-600' : 'text-gray-400'} />
                            <span className="text-xs font-bold">Facebook</span>
                            {assets.pages.length > 0 ? <Check size={14} className="text-blue-600" /> : <span className="text-[10px] text-gray-400">No detectado</span>}
                        </div>
                        <div className={`p-4 rounded-xl border flex flex-col items-center gap-2 ${assets.instagram.length > 0 ? 'bg-pink-50 border-pink-200' : 'bg-gray-50 border-gray-200 opacity-50'}`}>
                            <Instagram size={24} className={assets.instagram.length > 0 ? 'text-pink-600' : 'text-gray-400'} />
                            <span className="text-xs font-bold">Instagram</span>
                            {assets.instagram.length > 0 ? <Check size={14} className="text-pink-600" /> : <span className="text-[10px] text-gray-400">No detectado</span>}
                        </div>
                        <div className={`p-4 rounded-xl border flex flex-col items-center gap-2 ${assets.whatsapp.length > 0 ? 'bg-green-50 border-green-200' : 'bg-gray-50 border-gray-200 opacity-50'}`}>
                            <MessageCircle size={24} className={assets.whatsapp.length > 0 ? 'text-green-600' : 'text-gray-400'} />
                            <span className="text-xs font-bold">WhatsApp</span>
                            {assets.whatsapp.length > 0 ? <Check size={14} className="text-green-600" /> : <span className="text-[10px] text-yellow-500">No detectado</span>}
                        </div>
                    </div>

                    {/* Asset Details */}
                    <div className="text-sm text-gray-600 space-y-1 mb-6">
                        {assets.pages.map(p => <div key={p.id}>Facebook Page: <strong>{p.name}</strong></div>)}
                        {assets.instagram.map(ig => <div key={ig.id}>Instagram: <strong>@{ig.username}</strong></div>)}
                        {assets.whatsapp.flatMap(wa => wa.phone_numbers.map(ph => (
                            <div key={ph.display_phone_number}>WhatsApp: <strong>{ph.display_phone_number}</strong></div>
                        )))}
                    </div>

                    {/* Actions */}
                    <div className="flex gap-3">
                        <button
                            onClick={handleLogin}
                            className="px-4 py-2 bg-blue-50 text-blue-700 rounded-xl hover:bg-blue-100 border border-blue-200 transition flex items-center gap-2"
                        >
                            <RefreshCw size={16} /> Reconectar
                        </button>
                        <button
                            onClick={handleDisconnect}
                            disabled={disconnecting}
                            className="px-4 py-2 bg-red-50 text-red-700 rounded-xl hover:bg-red-100 border border-red-200 transition flex items-center gap-2"
                        >
                            {disconnecting ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                            Desconectar
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // Idle / Error state (not connected)
    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">
            <div className="bg-white border border-gray-200 rounded-2xl p-8 shadow-sm flex flex-col items-center text-center">
                <div className="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center mb-6">
                    <Facebook size={32} className="text-blue-600" />
                </div>

                <h2 className="text-xl font-bold text-gray-900 mb-2">Conectar canales de Meta</h2>
                <p className="text-sm text-gray-500 mb-8 max-w-sm">
                    Conecta tus paginas de Facebook, Instagram y WhatsApp Business directamente para recibir mensajes y que tu agente de IA responda.
                </p>

                <button
                    onClick={handleLogin}
                    disabled={!isSdkReady || status === 'connecting'}
                    className={`w-full max-w-xs px-6 py-3 bg-[#1877F2] hover:bg-[#166fe5] text-white rounded-xl font-semibold shadow-lg shadow-blue-600/20 transition-all flex justify-center items-center gap-2 ${(!isSdkReady || status === 'connecting') ? 'opacity-60 cursor-not-allowed' : ''}`}
                >
                    {status === 'connecting' ? (
                        <><Loader2 size={18} className="animate-spin" /> Conectando...</>
                    ) : !isSdkReady ? (
                        <><Loader2 size={18} className="animate-spin" /> Cargando SDK...</>
                    ) : (
                        <><Facebook size={18} /> Conectar con Meta</>
                    )}
                </button>

                {(status === 'error' && errorMsg) && (
                    <div className="mt-4 text-red-600 text-sm bg-red-50 p-3 rounded-lg border border-red-200 w-full max-w-sm">
                        {errorMsg}
                    </div>
                )}
            </div>

            {/* Info card */}
            <div className="bg-white border border-gray-200 rounded-2xl p-6 shadow-sm">
                <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2">
                    <MessageCircle size={16} /> Que sucede al conectar?
                </h3>
                <ol className="space-y-2 text-sm text-gray-600 list-decimal list-inside">
                    <li>Se abre un popup de Meta donde seleccionas tus paginas y cuentas</li>
                    <li>Se suscriben automaticamente a webhooks para recibir mensajes</li>
                    <li>Tu agente de IA comienza a responder en esos canales</li>
                    <li>Para agendar turnos, el agente pedira el telefono del paciente</li>
                </ol>
            </div>

            {/* Requirements warning */}
            <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-4">
                <div className="flex items-start gap-2">
                    <AlertTriangle size={16} className="text-yellow-600 mt-0.5 shrink-0" />
                    <div className="text-xs text-yellow-700">
                        <strong>Requisitos:</strong> Facebook Page con rol de Administrador, Instagram Business Account vinculado a la Page. Para WhatsApp, necesitas una cuenta de WhatsApp Cloud API (no WhatsApp Business App).
                    </div>
                </div>
            </div>
        </div>
    );
};

export default MetaConnectionTab;
