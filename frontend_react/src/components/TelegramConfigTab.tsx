import React, { useState, useEffect, useCallback } from 'react';
import { Send, Eye, EyeOff, Copy, Check, Trash2, ChevronDown, ChevronUp, Loader2, Plus, X, Building2 } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

interface Tenant {
    id: number;
    clinic_name: string;
}

// ─── Types ────────────────────────────────────────────────────────────────────

interface BotStatus {
    connected: boolean;
    username?: string;
    webhook_url?: string;
}

interface AuthorizedUser {
    id: number;
    display_name: string;
    telegram_chat_id: string;
    user_role: 'ceo' | 'secretary' | 'professional';
    is_active: boolean;
}

type UserRole = 'ceo' | 'secretary' | 'professional';

interface NewUserForm {
    display_name: string;
    telegram_chat_id: string;
    user_role: UserRole;
}

const ROLE_COLORS: Record<UserRole, string> = {
    ceo: 'bg-purple-500/10 text-purple-400',
    secretary: 'bg-blue-500/10 text-blue-400',
    professional: 'bg-green-500/10 text-green-400',
};

const maskChatId = (id: string) => {
    if (id.length <= 4) return '****';
    return id.slice(0, 3) + '•'.repeat(Math.max(id.length - 5, 3)) + id.slice(-2);
};

// ─── Component ────────────────────────────────────────────────────────────────

const TelegramConfigTab: React.FC = () => {
    const { t } = useTranslation();

    // Tenant selector state
    const [tenants, setTenants] = useState<Tenant[]>([]);
    const [selectedTenantId, setSelectedTenantId] = useState<number | null>(null);
    const [loadingTenants, setLoadingTenants] = useState(true);

    // Bot config state
    const [botStatus, setBotStatus] = useState<BotStatus>({ connected: false });
    const [botToken, setBotToken] = useState('');
    const [showToken, setShowToken] = useState(false);
    const [connectingBot, setConnectingBot] = useState(false);
    const [disconnectingBot, setDisconnectingBot] = useState(false);
    const [copied, setCopied] = useState(false);

    // Authorized users state
    const [users, setUsers] = useState<AuthorizedUser[]>([]);
    const [loadingUsers, setLoadingUsers] = useState(false);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [savingUser, setSavingUser] = useState(false);
    const [togglingId, setTogglingId] = useState<number | null>(null);
    const [deletingId, setDeletingId] = useState<number | null>(null);

    // New user form state
    const [newUser, setNewUser] = useState<NewUserForm>({
        display_name: '',
        telegram_chat_id: '',
        user_role: 'secretary',
    });

    // Instructions collapsible
    const [instructionsOpen, setInstructionsOpen] = useState(false);

    // Feedback messages
    const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; msg: string } | null>(null);

    const showFeedback = (type: 'success' | 'error', msg: string) => {
        setFeedback({ type, msg });
        setTimeout(() => setFeedback(null), 3500);
    };

    // ── Tenant-scoped API helper ─────────────────────────────────────────────

    const tenantHeaders = useCallback(() => {
        if (!selectedTenantId) return {};
        return { headers: { 'X-Tenant-ID': String(selectedTenantId) } };
    }, [selectedTenantId]);

    // ── Data Fetchers ──────────────────────────────────────────────────────────

    const fetchTenants = useCallback(async () => {
        setLoadingTenants(true);
        try {
            const { data } = await api.get<Tenant[]>('/admin/chat/tenants');
            if (Array.isArray(data)) {
                setTenants(data);
                if (data.length > 0 && !selectedTenantId) {
                    setSelectedTenantId(data[0].id);
                }
            }
        } catch {
            setTenants([]);
        } finally {
            setLoadingTenants(false);
        }
    }, []);

    const fetchBotStatus = useCallback(async () => {
        if (!selectedTenantId) return;
        try {
            const { data } = await api.get<BotStatus>('/admin/telegram/config', tenantHeaders());
            setBotStatus(data);
        } catch {
            setBotStatus({ connected: false });
        }
    }, [selectedTenantId, tenantHeaders]);

    const fetchUsers = useCallback(async () => {
        if (!selectedTenantId) return;
        setLoadingUsers(true);
        try {
            const { data } = await api.get<AuthorizedUser[]>('/admin/telegram/authorized-users', tenantHeaders());
            setUsers(Array.isArray(data) ? data : []);
        } catch {
            setUsers([]);
        } finally {
            setLoadingUsers(false);
        }
    }, [selectedTenantId, tenantHeaders]);

    // Load tenants on mount
    useEffect(() => {
        fetchTenants();
    }, [fetchTenants]);

    // Reload bot status when tenant changes
    useEffect(() => {
        if (selectedTenantId) {
            setBotStatus({ connected: false });
            setUsers([]);
            setBotToken('');
            fetchBotStatus();
        }
    }, [selectedTenantId]);

    // Load users when bot is connected
    useEffect(() => {
        if (botStatus.connected && selectedTenantId) {
            fetchUsers();
        }
    }, [botStatus.connected, selectedTenantId]);

    // ── Handlers ──────────────────────────────────────────────────────────────

    const handleConnect = async () => {
        if (!botToken.trim() || !selectedTenantId) return;
        setConnectingBot(true);
        try {
            const { data } = await api.post<BotStatus>('/admin/telegram/config', { bot_token: botToken }, tenantHeaders());
            setBotStatus(data);
            setBotToken('');
            showFeedback('success', t('telegram.connect'));
        } catch (err: any) {
            showFeedback('error', err?.response?.data?.detail || 'Error al conectar el bot');
        } finally {
            setConnectingBot(false);
        }
    };

    const handleDisconnect = async () => {
        if (!confirm(t('telegram.disconnect') + '?')) return;
        setDisconnectingBot(true);
        try {
            await api.delete('/admin/telegram/config', tenantHeaders());
            setBotStatus({ connected: false });
            setUsers([]);
        } catch (err: any) {
            showFeedback('error', err?.response?.data?.detail || 'Error al desconectar');
        } finally {
            setDisconnectingBot(false);
        }
    };

    const handleCopyWebhook = async () => {
        if (!botStatus.webhook_url) return;
        await navigator.clipboard.writeText(botStatus.webhook_url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleAddUser = async (e: React.FormEvent) => {
        e.preventDefault();
        setSavingUser(true);
        try {
            await api.post('/admin/telegram/authorized-users', newUser, tenantHeaders());
            setIsModalOpen(false);
            setNewUser({ display_name: '', telegram_chat_id: '', user_role: 'secretary' });
            await fetchUsers();
            showFeedback('success', t('telegram.user_added'));
        } catch (err: any) {
            showFeedback('error', err?.response?.data?.detail || 'Error al agregar usuario');
        } finally {
            setSavingUser(false);
        }
    };

    const handleToggleActive = async (user: AuthorizedUser) => {
        setTogglingId(user.id);
        try {
            await api.put(`/admin/telegram/authorized-users/${user.id}`, { is_active: !user.is_active }, tenantHeaders());
            setUsers(prev => prev.map(u => u.id === user.id ? { ...u, is_active: !u.is_active } : u));
        } catch (err: any) {
            showFeedback('error', err?.response?.data?.detail || 'Error al actualizar');
        } finally {
            setTogglingId(null);
        }
    };

    const handleDeleteUser = async (id: number) => {
        if (!confirm(t('telegram.confirm_delete'))) return;
        setDeletingId(id);
        try {
            await api.delete(`/admin/telegram/authorized-users/${id}`, tenantHeaders());
            setUsers(prev => prev.filter(u => u.id !== id));
            showFeedback('success', t('telegram.user_removed'));
        } catch (err: any) {
            showFeedback('error', err?.response?.data?.detail || 'Error al eliminar');
        } finally {
            setDeletingId(null);
        }
    };

    // ── Render ────────────────────────────────────────────────────────────────

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-300">

            {/* Clinic / Tenant Selector */}
            <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-4 sm:p-6">
                <div className="flex items-center gap-2 mb-3">
                    <Building2 size={20} className="text-sky-400" />
                    <h2 className="text-lg font-semibold text-white">{t('telegram.select_clinic') || 'Seleccionar clínica'}</h2>
                </div>
                <p className="text-sm text-white/40 mb-4">{t('telegram.select_clinic_hint') || 'Cada clínica tiene su propio bot de Telegram con sus pacientes y datos independientes.'}</p>
                {loadingTenants ? (
                    <div className="flex items-center gap-2 text-white/40 text-sm">
                        <Loader2 size={16} className="animate-spin" /> Cargando clínicas...
                    </div>
                ) : tenants.length === 0 ? (
                    <p className="text-sm text-white/40">No hay clínicas configuradas.</p>
                ) : (
                    <select
                        className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-sky-500 outline-none transition-all"
                        value={selectedTenantId ?? ''}
                        onChange={(e) => {
                            const tid = e.target.value ? Number(e.target.value) : null;
                            setSelectedTenantId(tid);
                        }}
                    >
                        <option value="">{t('config.select_placeholder') || 'Seleccionar...'}</option>
                        {tenants.map(tenant => (
                            <option key={tenant.id} value={tenant.id}>{tenant.clinic_name}</option>
                        ))}
                    </select>
                )}
            </div>

            {/* Everything below requires a selected tenant */}
            {!selectedTenantId ? (
                <div className="text-center py-8 text-white/30 text-sm">
                    {t('telegram.select_clinic_first') || 'Seleccioná una clínica para configurar Telegram'}
                </div>
            ) : (<>

            {/* Feedback toast */}
            {feedback && (
                <div className={`px-4 py-3 rounded-xl text-sm font-medium border ${
                    feedback.type === 'success'
                        ? 'bg-green-500/10 border-green-500/20 text-green-400'
                        : 'bg-red-500/10 border-red-500/20 text-red-400'
                }`}>
                    {feedback.msg}
                </div>
            )}

            {/* ── Section 1: Bot Configuration ─────────────────────────────── */}
            <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4 sm:p-6 space-y-4">
                <div className="flex items-center gap-2">
                    <Send size={18} className="text-sky-400" />
                    <h2 className="text-base font-semibold text-white">{t('telegram.bot_config')}</h2>
                </div>

                {/* Connection status badge */}
                <div className="flex items-center gap-2">
                    {botStatus.connected ? (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-green-500/10 text-green-400 border border-green-500/20">
                            <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                            {t('telegram.connected')}{botStatus.username ? ` @${botStatus.username}` : ''}
                        </span>
                    ) : (
                        <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-white/10 text-white/50 border border-white/[0.08]">
                            <span className="w-1.5 h-1.5 rounded-full bg-white/30 inline-block" />
                            {t('telegram.disconnected')}
                        </span>
                    )}
                </div>

                {/* Token input + connect (only when disconnected) */}
                {!botStatus.connected && (
                    <div className="space-y-3">
                        <div>
                            <label className="block text-sm font-medium text-white/60 mb-1.5">
                                {t('telegram.bot_token')}
                            </label>
                            <div className="relative">
                                <input
                                    type={showToken ? 'text' : 'password'}
                                    value={botToken}
                                    onChange={e => setBotToken(e.target.value)}
                                    placeholder={t('telegram.bot_token_placeholder')}
                                    className="w-full px-4 py-2.5 pr-10 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm placeholder:text-white/30 focus:outline-none focus:border-sky-500/40 focus:ring-1 focus:ring-sky-500/20 transition-all"
                                    onKeyDown={e => e.key === 'Enter' && handleConnect()}
                                />
                                <button
                                    type="button"
                                    onClick={() => setShowToken(v => !v)}
                                    className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60 transition-colors"
                                >
                                    {showToken ? <EyeOff size={16} /> : <Eye size={16} />}
                                </button>
                            </div>
                        </div>

                        <button
                            onClick={handleConnect}
                            disabled={connectingBot || !botToken.trim()}
                            className="flex items-center gap-2 px-5 py-2.5 bg-white text-[#0a0e1a] rounded-xl font-semibold text-sm hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            {connectingBot ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                            {t('telegram.connect')}
                        </button>
                    </div>
                )}

                {/* Webhook URL + disconnect (only when connected) */}
                {botStatus.connected && (
                    <div className="space-y-3">
                        <div>
                            <label className="block text-sm font-medium text-white/60 mb-1.5">
                                {t('telegram.webhook_url')}
                            </label>
                            <div className="flex gap-2">
                                <input
                                    readOnly
                                    value={botStatus.webhook_url || ''}
                                    className="flex-1 px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white/50 text-sm font-mono focus:outline-none"
                                />
                                <button
                                    onClick={handleCopyWebhook}
                                    className="px-3 py-2.5 bg-white/[0.06] border border-white/[0.08] rounded-xl text-white/60 hover:text-white hover:bg-white/[0.08] transition-all flex items-center gap-1.5 text-sm"
                                    title={t('telegram.copy_url')}
                                >
                                    {copied ? <Check size={16} className="text-green-400" /> : <Copy size={16} />}
                                    <span className="hidden sm:inline">
                                        {copied ? t('telegram.copied') : t('telegram.copy_url')}
                                    </span>
                                </button>
                            </div>
                        </div>

                        <button
                            onClick={handleDisconnect}
                            disabled={disconnectingBot}
                            className="flex items-center gap-2 px-4 py-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-sm font-medium hover:bg-red-500/15 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                        >
                            {disconnectingBot ? <Loader2 size={15} className="animate-spin" /> : <X size={15} />}
                            {t('telegram.disconnect')}
                        </button>
                    </div>
                )}
            </div>

            {/* ── Section 2: Authorized Users ──────────────────────────────── */}
            {botStatus.connected && (
                <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4 sm:p-6 space-y-4">
                    <div className="flex items-center justify-between">
                        <h2 className="text-base font-semibold text-white">{t('telegram.authorized_users')}</h2>
                        <button
                            onClick={() => setIsModalOpen(true)}
                            className="flex items-center gap-1.5 px-3 py-1.5 bg-white text-[#0a0e1a] rounded-lg font-semibold text-xs hover:bg-white/90 transition-all"
                        >
                            <Plus size={14} />
                            {t('telegram.add_user')}
                        </button>
                    </div>

                    {loadingUsers ? (
                        <div className="flex justify-center py-8">
                            <Loader2 size={22} className="animate-spin text-white/30" />
                        </div>
                    ) : users.length === 0 ? (
                        <p className="text-center text-white/30 text-sm py-8">
                            No hay usuarios autorizados aún
                        </p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-white/[0.06]">
                                        <th className="text-left py-2.5 px-3 text-white/40 font-medium">{t('telegram.display_name')}</th>
                                        <th className="text-left py-2.5 px-3 text-white/40 font-medium hidden sm:table-cell">{t('telegram.chat_id')}</th>
                                        <th className="text-left py-2.5 px-3 text-white/40 font-medium">{t('telegram.role')}</th>
                                        <th className="text-center py-2.5 px-3 text-white/40 font-medium">{t('telegram.active')}</th>
                                        <th className="py-2.5 px-3" />
                                    </tr>
                                </thead>
                                <tbody>
                                    {users.map(user => (
                                        <tr key={user.id} className="border-b border-white/[0.04] hover:bg-white/[0.02] transition-colors">
                                            <td className="py-3 px-3 text-white font-medium">{user.display_name}</td>
                                            <td className="py-3 px-3 text-white/40 font-mono text-xs hidden sm:table-cell">
                                                {maskChatId(user.telegram_chat_id)}
                                            </td>
                                            <td className="py-3 px-3">
                                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_COLORS[user.user_role]}`}>
                                                    {user.user_role}
                                                </span>
                                            </td>
                                            <td className="py-3 px-3 text-center">
                                                <button
                                                    onClick={() => handleToggleActive(user)}
                                                    disabled={togglingId === user.id}
                                                    className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none disabled:opacity-50 ${
                                                        user.is_active ? 'bg-green-500' : 'bg-white/10'
                                                    }`}
                                                    aria-label={t('telegram.active')}
                                                >
                                                    <span className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                                                        user.is_active ? 'translate-x-4' : 'translate-x-0.5'
                                                    }`} />
                                                </button>
                                            </td>
                                            <td className="py-3 px-3 text-right">
                                                <button
                                                    onClick={() => handleDeleteUser(user.id)}
                                                    disabled={deletingId === user.id}
                                                    className="p-1.5 text-white/20 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all disabled:opacity-40"
                                                    title={t('telegram.confirm_delete')}
                                                >
                                                    {deletingId === user.id
                                                        ? <Loader2 size={14} className="animate-spin" />
                                                        : <Trash2 size={14} />
                                                    }
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}

            {/* ── Section 3: Instructions (collapsible) ────────────────────── */}
            <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl overflow-hidden">
                <button
                    onClick={() => setInstructionsOpen(v => !v)}
                    className="w-full flex items-center justify-between px-4 sm:px-6 py-4 text-left hover:bg-white/[0.02] transition-colors"
                >
                    <span className="text-sm font-medium text-white/70">{t('telegram.instructions_title')}</span>
                    {instructionsOpen
                        ? <ChevronUp size={16} className="text-white/30" />
                        : <ChevronDown size={16} className="text-white/30" />
                    }
                </button>
                {instructionsOpen && (
                    <div className="px-4 sm:px-6 pb-5 space-y-3 border-t border-white/[0.04]">
                        <div className="pt-4 space-y-2">
                            <div className="flex gap-3 items-start">
                                <span className="flex-shrink-0 w-5 h-5 mt-0.5 rounded-full bg-sky-500/15 text-sky-400 flex items-center justify-center text-xs font-bold">1</span>
                                <p className="text-sm text-white/50">{t('telegram.instructions_token')}</p>
                            </div>
                            <div className="flex gap-3 items-start">
                                <span className="flex-shrink-0 w-5 h-5 mt-0.5 rounded-full bg-sky-500/15 text-sky-400 flex items-center justify-center text-xs font-bold">2</span>
                                <p className="text-sm text-white/50">{t('telegram.instructions_chatid')}</p>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* ── Add User Modal ────────────────────────────────────────────── */}
            {isModalOpen && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
                    onClick={e => { if (e.target === e.currentTarget) setIsModalOpen(false); }}
                >
                    <div className="w-full max-w-md bg-[#0d1117] border border-white/[0.08] rounded-2xl shadow-2xl">
                        <div className="flex items-center justify-between px-6 pt-5 pb-4 border-b border-white/[0.06]">
                            <h3 className="text-base font-semibold text-white">{t('telegram.add_user')}</h3>
                            <button onClick={() => setIsModalOpen(false)} className="text-white/30 hover:text-white/60 transition-colors">
                                <X size={18} />
                            </button>
                        </div>

                        <form onSubmit={handleAddUser} className="px-6 py-5 space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-white/60 mb-1.5">
                                    {t('telegram.display_name')}
                                </label>
                                <input
                                    type="text"
                                    required
                                    value={newUser.display_name}
                                    onChange={e => setNewUser(v => ({ ...v, display_name: e.target.value }))}
                                    className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm placeholder:text-white/30 focus:outline-none focus:border-sky-500/40 focus:ring-1 focus:ring-sky-500/20 transition-all"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/60 mb-1.5">
                                    {t('telegram.chat_id')}
                                </label>
                                <input
                                    type="number"
                                    required
                                    value={newUser.telegram_chat_id}
                                    onChange={e => setNewUser(v => ({ ...v, telegram_chat_id: e.target.value }))}
                                    className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm placeholder:text-white/30 focus:outline-none focus:border-sky-500/40 focus:ring-1 focus:ring-sky-500/20 transition-all [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
                                />
                            </div>

                            <div>
                                <label className="block text-sm font-medium text-white/60 mb-1.5">
                                    {t('telegram.role')}
                                </label>
                                <select
                                    value={newUser.user_role}
                                    onChange={e => setNewUser(v => ({ ...v, user_role: e.target.value as UserRole }))}
                                    className="w-full px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm focus:outline-none focus:border-sky-500/40 focus:ring-1 focus:ring-sky-500/20 transition-all"
                                >
                                    <option value="ceo">CEO</option>
                                    <option value="secretary">Secretary</option>
                                    <option value="professional">Professional</option>
                                </select>
                            </div>

                            <div className="flex gap-3 pt-1">
                                <button
                                    type="button"
                                    onClick={() => setIsModalOpen(false)}
                                    className="flex-1 px-4 py-2.5 bg-white/[0.04] border border-white/[0.08] text-white/60 rounded-xl text-sm font-medium hover:bg-white/[0.06] transition-all"
                                >
                                    Cancelar
                                </button>
                                <button
                                    type="submit"
                                    disabled={savingUser}
                                    className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-white text-[#0a0e1a] rounded-xl text-sm font-semibold hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
                                >
                                    {savingUser ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
                                    Guardar
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            </>)}
        </div>
    );
};

export default TelegramConfigTab;
