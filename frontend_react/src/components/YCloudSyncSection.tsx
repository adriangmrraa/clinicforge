/**
 * YCloud Sync Section Component.
 * Allows CEOs to start/stop WhatsApp message sync from YCloud.
 */

import React, { useState, useEffect, useCallback } from 'react';
import { RefreshCw, Clock, Loader2, CheckCircle2, AlertCircle, XCircle, Lock } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';
import {
    startYCloudSync, 
    getSyncStatus, 
    cancelSync, 
    getSyncConfig, 
    YCloudSyncProgress,
    YCloudSyncConfig 
} from '../api/ycloud';

interface YCloudSyncSectionProps {
    tenantId: number;
    className?: string;
}

const POLL_INTERVAL = 2000; // 2 seconds

export const YCloudSyncSection: React.FC<YCloudSyncSectionProps> = ({ tenantId, className = '' }) => {
    const { t } = useTranslation();
    
    // Config state
    const [config, setConfig] = useState<YCloudSyncConfig | null>(null);
    const [loadingConfig, setLoadingConfig] = useState(true);
    
    // Progress state
    const [progress, setProgress] = useState<YCloudSyncProgress | null>(null);
    const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
    
    // Modal state
    const [showPasswordModal, setShowPasswordModal] = useState(false);
    const [password, setPassword] = useState('');
    const [passwordError, setPasswordError] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    
    // Polling
    const [polling, setPolling] = useState(false);

    // Purge state
    const [purgeConfirm, setPurgeConfirm] = useState(false);
    const [purging, setPurging] = useState(false);
    const [purgeResult, setPurgeResult] = useState<string | null>(null);
    
    // Load config + check for active sync on mount
    useEffect(() => {
        loadConfig();
        checkActiveSync();
    }, [tenantId]);

    const checkActiveSync = async () => {
        try {
            const { data } = await api.get(`/admin/ycloud/sync/active`);
            if (data.active && data.task_id) {
                setCurrentTaskId(data.task_id);
                setProgress({
                    task_id: data.task_id,
                    status: data.status || 'processing',
                    messages_fetched: data.messages_fetched || 0,
                    messages_saved: data.messages_saved || 0,
                    media_downloaded: data.media_downloaded || 0,
                    errors: data.errors || [],
                    started_at: data.started_at || '',
                    completed_at: null,
                    last_sync_at: null,
                });
                // Resume polling
                setPolling(true);
            }
        } catch {
            // No active sync — normal
        }
    };

    const loadConfig = async () => {
        try {
            setLoadingConfig(true);
            const cfg = await getSyncConfig(tenantId);
            setConfig(cfg);
        } catch (err) {
            console.error('Failed to load sync config:', err);
        } finally {
            setLoadingConfig(false);
        }
    };
    
    // Poll progress when task is running
    useEffect(() => {
        let interval: NodeJS.Timeout;
        
        if (currentTaskId && polling) {
            interval = setInterval(async () => {
                try {
                    const status = await getSyncStatus(currentTaskId);
                    setProgress(status);
                    
                    // Stop polling if completed/error/cancelled
                    if (['completed', 'error', 'cancelled'].includes(status.status)) {
                        setPolling(false);
                        setCurrentTaskId(null);
                        // Refresh config to update last_sync_at
                        loadConfig();
                    }
                } catch (err) {
                    console.error('Failed to poll progress:', err);
                }
            }, POLL_INTERVAL);
        }
        
        return () => {
            if (interval) clearInterval(interval);
        };
    }, [currentTaskId, polling]);
    
    const handleStartSync = async () => {
        if (!password) {
            setPasswordError(t('ycloud_sync.error_no_password'));
            return;
        }
        
        setSubmitting(true);
        setPasswordError(null);
        
        try {
            const result = await startYCloudSync(tenantId, password);
            setCurrentTaskId(result.task_id);
            setProgress({
                task_id: result.task_id,
                status: 'queued',
                messages_fetched: 0,
                messages_saved: 0,
                media_downloaded: 0,
                errors: [],
                started_at: new Date().toISOString(),
                completed_at: null,
                last_sync_at: null,
            });
            setPolling(true);
            setShowPasswordModal(false);
            setPassword('');
        } catch (err: any) {
            const msg = err.response?.data?.detail || err.message || 'Error starting sync';
            if (msg.includes('password') || msg.includes('401')) {
                setPasswordError(t('ycloud_sync.error_invalid_password'));
            } else if (msg.includes('rate limit') || msg.includes('429')) {
                setPasswordError(t('ycloud_sync.error_rate_limited'));
            } else if (msg.includes('sync in progress')) {
                setPasswordError(t('ycloud_sync.error_sync_in_progress'));
            } else {
                setPasswordError(msg);
            }
        } finally {
            setSubmitting(false);
        }
    };
    
    const handlePurge = async () => {
        setPurging(true);
        setPurgeResult(null);
        try {
            const { data } = await api.post(`/admin/ycloud/sync/purge/${tenantId}`);
            setPurgeResult(`Eliminados: ${data.conversations_deleted || 0} conversaciones, ${data.messages_deleted || 0} mensajes`);
            setTimeout(() => { setPurgeConfirm(false); setPurgeResult(null); }, 5000);
        } catch (err: any) {
            setPurgeResult(`Error: ${err.response?.data?.detail || err.message}`);
        } finally {
            setPurging(false);
        }
    };

    const handleCancelSync = async () => {
        if (!currentTaskId) return;

        try {
            await cancelSync(currentTaskId);
            setPolling(false);
            setCurrentTaskId(null);
            loadConfig();
        } catch (err) {
            console.error('Failed to cancel sync:', err);
        }
    };
    
    const isSyncing = progress && ['queued', 'processing'].includes(progress.status);
    const canStart = config && config.sync_enabled && config.ycloud_api_key_configured && !config.rate_limited && !isSyncing;
    
    // Format last sync time
    const formatLastSync = (dateStr: string | null) => {
        if (!dateStr) return t('ycloud_sync.last_sync_never');
        const date = new Date(dateStr);
        return date.toLocaleString();
    };
    
    // Get status color/class
    const getStatusBadge = (status: string) => {
        switch (status) {
            case 'queued':
                return 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20';
            case 'processing':
                return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
            case 'completed':
                return 'bg-green-500/10 text-green-400 border-green-500/20';
            case 'error':
            case 'cancelled':
                return 'bg-red-500/10 text-red-400 border-red-500/20';
            default:
                return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
        }
    };
    
    const getStatusText = (status: string) => {
        switch (status) {
            case 'queued': return t('ycloud_sync.status_queued');
            case 'processing': return t('ycloud_sync.status_processing');
            case 'completed': return t('ycloud_sync.status_completed');
            case 'error': return t('ycloud_sync.status_error');
            case 'cancelled': return t('ycloud_sync.status_cancelled');
            default: return status;
        }
    };
    
    if (loadingConfig) {
        return (
            <div className={`bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6 ${className}`}>
                <div className="flex items-center gap-2 text-white/40">
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Cargando...</span>
                </div>
            </div>
        );
    }
    
    // Show section even without API key configured (to prompt setup)
    // if (!config?.ycloud_api_key_configured) {
    //     return null;
    // }
    
    const isConfigured = config?.ycloud_api_key_configured;
    
    return (
        <div className={`bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6 ${className}`}>
            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-green-500/10 rounded-lg">
                    <RefreshCw className="w-5 h-5 text-green-400" />
                </div>
                <div>
                    <h3 className="text-lg font-semibold text-white">{t('ycloud_sync.title')}</h3>
                    <p className="text-sm text-white/60">{t('ycloud_sync.description')}</p>
                </div>
            </div>
            
            {/* Last Sync Info */}
            <div className="flex items-center gap-2 text-white/60 mb-4">
                <Clock className="w-4 h-4" />
                <span className="text-sm">
                    {t('ycloud_sync.last_sync')}: {formatLastSync(config?.last_sync_at)}
                </span>
            </div>
            
            {/* Progress (when syncing) */}
            {isSyncing && progress && (
                <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/20 rounded-xl space-y-3">
                    <div className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                        <span className="text-sm font-medium text-blue-400">
                            Sincronizando...
                        </span>
                    </div>

                    {/* Current week being processed */}
                    {(progress as any).current_week && (
                        <div className="text-xs text-white/50">
                            Procesando: <span className="text-white/70 font-medium">{(progress as any).current_week}</span>
                        </div>
                    )}

                    {/* Stats grid */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="bg-white/[0.04] rounded-lg p-2 text-center">
                            <div className="text-lg font-bold text-white">{progress.messages_saved}</div>
                            <div className="text-[10px] text-white/40">Mensajes guardados</div>
                        </div>
                        <div className="bg-white/[0.04] rounded-lg p-2 text-center">
                            <div className="text-lg font-bold text-white">{(progress as any).unique_conversations || 0}</div>
                            <div className="text-[10px] text-white/40">Conversaciones</div>
                        </div>
                        <div className="bg-white/[0.04] rounded-lg p-2 text-center">
                            <div className="text-lg font-bold text-white">{progress.messages_fetched}</div>
                            <div className="text-[10px] text-white/40">Descargados</div>
                        </div>
                        <div className="bg-white/[0.04] rounded-lg p-2 text-center">
                            <div className="text-lg font-bold text-white">{progress.media_downloaded}</div>
                            <div className="text-[10px] text-white/40">Archivos</div>
                        </div>
                    </div>

                    {/* Week-by-week log */}
                    {(progress as any).week_log && (progress as any).week_log.length > 0 && (
                        <div className="bg-black/20 rounded-lg p-3 max-h-48 overflow-y-auto font-mono text-xs space-y-0.5">
                            {((progress as any).week_log as string[]).map((entry: string, i: number) => (
                                <div key={i} className={
                                    entry.startsWith('✅') ? 'text-green-400' :
                                    entry.startsWith('⏹') ? 'text-amber-400 font-bold' :
                                    'text-white/30'
                                }>
                                    {entry}
                                </div>
                            ))}
                        </div>
                    )}

                    {/* Errors */}
                    {progress.errors && progress.errors.length > 0 && (
                        <div className="text-xs text-red-400/70 mt-1">
                            {progress.errors.slice(-2).map((err: string, i: number) => (
                                <div key={i}>⚠️ {err}</div>
                            ))}
                        </div>
                    )}
                </div>
            )}
            
            {/* Completed state */}
            {progress && progress.status === 'completed' && (
                <div className="mb-6 p-4 bg-green-500/10 border border-green-500/20 rounded-xl">
                    <div className="flex items-center gap-2 text-green-400">
                        <CheckCircle2 className="w-4 h-4" />
                        <span className="text-sm font-medium">
                            {t('ycloud_sync.success', { 
                                fetched: progress.messages_fetched, 
                                saved: progress.messages_saved 
                            })}
                        </span>
                    </div>
                </div>
            )}
            
            {/* Error state */}
            {progress && progress.status === 'error' && (
                <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
                    <div className="flex items-center gap-2 text-red-400 mb-2">
                        <AlertCircle className="w-4 h-4" />
                        <span className="text-sm font-medium">{t('ycloud_sync.errors')}</span>
                    </div>
                    <ul className="text-sm text-red-300/80 space-y-1">
                        {progress.errors.map((err, i) => (
                            <li key={i}>• {err}</li>
                        ))}
                    </ul>
                </div>
            )}
            
            {/* Buttons */}
            <div className="flex gap-3">
                {!isSyncing ? (
                    <button
                        onClick={() => setShowPasswordModal(true)}
                        disabled={!canStart}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
                            canStart
                                ? 'bg-green-600 hover:bg-green-700 text-white'
                                : 'bg-white/10 text-white/40 cursor-not-allowed'
                        }`}
                    >
                        <RefreshCw className="w-4 h-4" />
                        {config?.rate_limited
                            ? t('ycloud_sync.rate_limited', { minutes: 60 })
                            : t('ycloud_sync.button')
                        }
                    </button>
                ) : (
                    <button
                        onClick={handleCancelSync}
                        className="flex items-center gap-2 px-4 py-2 bg-red-600/80 hover:bg-red-600 text-white rounded-lg font-medium transition-all"
                    >
                        <XCircle className="w-4 h-4" />
                        {t('ycloud_sync.button_cancel')}
                    </button>
                )}
            </div>
            
            {/* Purge Button */}
            {!isSyncing && (
                <button
                    onClick={() => setPurgeConfirm(true)}
                    className="flex items-center gap-2 px-4 py-2 bg-red-600/20 hover:bg-red-600/40 text-red-400 border border-red-500/20 rounded-lg font-medium transition-all text-sm"
                >
                    <XCircle className="w-4 h-4" />
                    Eliminar datos sincronizados
                </button>
            )}

            {/* Purge Confirmation */}
            {purgeConfirm && (
                <div className="mt-3 p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
                    <p className="text-sm text-red-400 font-medium mb-2">⚠️ ¿Estás seguro?</p>
                    <p className="text-xs text-red-400/70 mb-3">
                        Esto eliminará TODAS las conversaciones y mensajes cargados por sincronización de YCloud.
                        Los mensajes recibidos en tiempo real por webhook NO se eliminan.
                    </p>
                    <div className="flex gap-2">
                        <button
                            onClick={handlePurge}
                            disabled={purging}
                            className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium flex items-center gap-2"
                        >
                            {purging ? <Loader2 className="w-4 h-4 animate-spin" /> : <XCircle className="w-4 h-4" />}
                            Sí, eliminar todo
                        </button>
                        <button
                            onClick={() => setPurgeConfirm(false)}
                            className="px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg text-sm"
                        >
                            Cancelar
                        </button>
                    </div>
                    {purgeResult && (
                        <p className="text-xs text-green-400 mt-2">{purgeResult}</p>
                    )}
                </div>
            )}

            {/* Password Modal */}
            {showPasswordModal && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
                    <div className="bg-gray-900 border border-white/[0.06] rounded-2xl p-6 w-full max-w-md">
                        <div className="flex items-center gap-3 mb-4">
                            <Lock className="w-5 h-5 text-green-400" />
                            <h3 className="text-lg font-semibold text-white">{t('ycloud_sync.modal_title')}</h3>
                        </div>
                        
                        <p className="text-sm text-white/60 mb-4">{t('ycloud_sync.modal_password_hint')}</p>
                        
                        <div className="space-y-4">
                            <div>
                                <label className="text-sm font-medium text-white/70 mb-1 block">
                                    {t('ycloud_sync.modal_password_label')}
                                </label>
                                <input
                                    type="password"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    className="w-full px-4 py-2 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white focus:ring-2 focus:ring-green-500 outline-none"
                                    placeholder="••••••••"
                                    autoFocus
                                    onKeyDown={(e) => e.key === 'Enter' && handleStartSync()}
                                />
                            </div>
                            
                            {passwordError && (
                                <div className="flex items-center gap-2 text-red-400 text-sm">
                                    <AlertCircle className="w-4 h-4" />
                                    {passwordError}
                                </div>
                            )}
                            
                            <div className="flex gap-3">
                                <button
                                    onClick={() => {
                                        setShowPasswordModal(false);
                                        setPassword('');
                                        setPasswordError(null);
                                    }}
                                    className="flex-1 px-4 py-2 bg-white/10 hover:bg-white/20 text-white rounded-lg font-medium transition-all"
                                >
                                    {t('common.cancel')}
                                </button>
                                <button
                                    onClick={handleStartSync}
                                    disabled={submitting}
                                    className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-all flex items-center justify-center gap-2"
                                >
                                    {submitting ? (
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                    ) : (
                                        <CheckCircle2 className="w-4 h-4" />
                                    )}
                                    {t('common.confirm')}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default YCloudSyncSection;