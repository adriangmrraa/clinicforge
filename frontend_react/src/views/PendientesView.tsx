import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ListTodo, Plus, RefreshCw, X, CheckCircle2, Clock,
    AlertTriangle, MessageSquare, Bot, User as UserIcon,
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';

/*
 * Módulo Pendientes con vencimiento (mig 075, tarea #2 2026-07-16).
 * Para que no se olviden chats/tareas cuando interviene la secretaria:
 *  - "Chats esperando respuesta": detección EN VIVO (override humano + el último
 *    mensaje es del paciente + >2h) — el caso Pau.
 *  - Pendientes con vencimiento: vencidas / hoy / próximas / sin fecha.
 *  - El bot crea pendientes solos al derivar (derivhumano → vence en 24h).
 */

interface PendingRow {
    id: number;
    title: string;
    note: string | null;
    due_at: string | null;
    status: string;
    assigned_to: string | null;
    created_by: string;
    source: string | null;
    done_at: string | null;
    created_at: string;
    patient_id: number | null;
    conversation_id: string | null;
    is_overdue: boolean;
    patient_name: string | null;
    chat_phone: string | null;
}

interface UnansweredChat {
    conversation_id: string;
    chat_phone: string;
    display_name: string | null;
    last_message_at: string;
    last_message_preview: string | null;
    patient_id: number | null;
    patient_name: string | null;
    hours_waiting: number;
}

const inputCls =
    'w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm focus:border-blue-500 focus:ring-0 outline-none placeholder-white/30';

function fmtDueRelative(dueAt: string | null, t: (k: string) => string): string {
    if (!dueAt) return t('pendientes.no_due');
    const due = new Date(dueAt);
    const diffMs = due.getTime() - Date.now();
    const abs = Math.abs(diffMs);
    const hours = Math.round(abs / 3_600_000);
    const days = Math.round(abs / 86_400_000);
    const when = hours < 1
        ? t('pendientes.minutes_short')
        : hours < 48
            ? `${hours} h`
            : `${days} ${t('pendientes.days_short')}`;
    return diffMs < 0
        ? `${t('pendientes.overdue_by')} ${when}`
        : `${t('pendientes.due_in')} ${when}`;
}

function fmtDateTime(iso: string | null): string {
    if (!iso) return '—';
    const d = new Date(iso);
    return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

export default function PendientesView() {
    const { t } = useTranslation();
    const navigate = useNavigate();

    const [rows, setRows] = useState<PendingRow[]>([]);
    const [unanswered, setUnanswered] = useState<UnansweredChat[]>([]);
    const [loading, setLoading] = useState(false);
    const [showClosed, setShowClosed] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [modal, setModal] = useState<boolean>(false);
    const [saving, setSaving] = useState(false);
    const [fTitle, setFTitle] = useState('');
    const [fNote, setFNote] = useState('');
    const [fDue, setFDue] = useState('');
    const [fAssigned, setFAssigned] = useState('');

    const fetchAll = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [pendings, chats] = await Promise.all([
                api.get(`/admin/pendings?bucket=todas&include_closed=${showClosed}`),
                api.get('/admin/pendings/unanswered-chats?hours=2'),
            ]);
            setRows(pendings.data as PendingRow[]);
            setUnanswered(chats.data as UnansweredChat[]);
        } catch {
            setError(t('pendientes.load_error'));
        } finally {
            setLoading(false);
        }
    }, [showClosed, t]);

    useEffect(() => { void fetchAll(); }, [fetchAll]);

    const buckets = useMemo(() => {
        const open = rows.filter((r) => r.status === 'abierto');
        const todayStr = new Date().toDateString();
        return {
            vencidas: open.filter((r) => r.is_overdue),
            hoy: open.filter((r) => !r.is_overdue && r.due_at && new Date(r.due_at).toDateString() === todayStr),
            proximas: open.filter((r) => !r.is_overdue && r.due_at && new Date(r.due_at).toDateString() !== todayStr),
            sinFecha: open.filter((r) => !r.due_at),
            cerradas: rows.filter((r) => r.status !== 'abierto'),
        };
    }, [rows]);

    const createPending = async () => {
        if (!fTitle.trim()) return;
        setSaving(true);
        try {
            await api.post('/admin/pendings', {
                title: fTitle.trim(),
                note: fNote.trim() || null,
                due_at: fDue || null,
                assigned_to: fAssigned.trim() || null,
                source: 'manual',
            });
            setModal(false);
            setFTitle(''); setFNote(''); setFDue(''); setFAssigned('');
            void fetchAll();
        } catch {
            setError(t('pendientes.save_error'));
        } finally {
            setSaving(false);
        }
    };

    const setStatus = async (id: number, status: 'hecho' | 'cancelado' | 'abierto') => {
        try {
            await api.patch(`/admin/pendings/${id}`, { status });
            void fetchAll();
        } catch {
            setError(t('pendientes.save_error'));
        }
    };

    const goToChat = (phone: string | null) => {
        if (phone) navigate(`/chats?phone=${encodeURIComponent(phone)}`);
        else navigate('/chats');
    };

    const Card = ({ r }: { r: PendingRow }) => (
        <div className={`rounded-xl border p-3 bg-white/[0.02] ${r.is_overdue ? 'border-red-500/30' : 'border-white/[0.06]'}`}>
            <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        {r.created_by === 'bot'
                            ? <Bot size={13} className="text-violet-400 shrink-0" />
                            : <UserIcon size={13} className="text-white/40 shrink-0" />}
                        <span className="text-sm text-white font-medium truncate">{r.title}</span>
                    </div>
                    {r.note && <p className="text-xs text-white/50 mt-1 line-clamp-2">{r.note}</p>}
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2 text-[11px] text-white/40">
                        <span className={`inline-flex items-center gap-1 ${r.is_overdue ? 'text-red-400' : ''}`}>
                            <Clock size={11} /> {fmtDueRelative(r.due_at, t)}{r.due_at ? ` · ${fmtDateTime(r.due_at)}` : ''}
                        </span>
                        {r.patient_name && <span>👤 {r.patient_name}</span>}
                        {r.assigned_to && <span>→ {r.assigned_to}</span>}
                    </div>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                    {r.chat_phone && (
                        <button
                            onClick={() => goToChat(r.chat_phone)}
                            title={t('pendientes.go_chat')}
                            className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.1] text-white/60"
                        >
                            <MessageSquare size={14} />
                        </button>
                    )}
                    {r.status === 'abierto' ? (
                        <>
                            <button
                                onClick={() => void setStatus(r.id, 'hecho')}
                                title={t('pendientes.mark_done')}
                                className="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/25 text-emerald-400"
                            >
                                <CheckCircle2 size={14} />
                            </button>
                            <button
                                onClick={() => void setStatus(r.id, 'cancelado')}
                                title={t('pendientes.cancel')}
                                className="p-1.5 rounded-lg bg-white/[0.04] hover:bg-red-500/20 text-white/40 hover:text-red-400"
                            >
                                <X size={14} />
                            </button>
                        </>
                    ) : (
                        <button
                            onClick={() => void setStatus(r.id, 'abierto')}
                            className="px-2 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.1] text-[11px] text-white/50"
                        >
                            {t('pendientes.reopen')}
                        </button>
                    )}
                </div>
            </div>
        </div>
    );

    const Section = ({ title, items, tone }: { title: string; items: PendingRow[]; tone?: 'red' | 'amber' }) => {
        if (!items.length) return null;
        return (
            <div>
                <h3 className={`text-xs uppercase tracking-wide mb-2 ${tone === 'red' ? 'text-red-400' : tone === 'amber' ? 'text-amber-400' : 'text-white/40'}`}>
                    {title} <span className="text-white/30">({items.length})</span>
                </h3>
                <div className="space-y-2">{items.map((r) => <Card key={r.id} r={r} />)}</div>
            </div>
        );
    };

    return (
        <div className="h-full flex flex-col overflow-hidden">
            <PageHeader
                title={t('nav.pendientes')}
                subtitle={t('pendientes.subtitle')}
                icon={<ListTodo size={20} />}
                action={
                    <div className="flex items-center gap-2">
                        <label className="flex items-center gap-1.5 text-xs text-white/50 cursor-pointer select-none">
                            <input
                                type="checkbox"
                                checked={showClosed}
                                onChange={(e) => setShowClosed(e.target.checked)}
                                className="accent-blue-500"
                            />
                            {t('pendientes.show_closed')}
                        </label>
                        <button
                            onClick={() => void fetchAll()}
                            className="p-2 rounded-lg bg-white/[0.04] hover:bg-white/[0.1] text-white/60"
                            title={t('pendientes.refresh')}
                        >
                            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
                        </button>
                        <button
                            onClick={() => setModal(true)}
                            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-white text-[#0a0e1a] text-sm font-medium hover:bg-white/90"
                        >
                            <Plus size={15} /> {t('pendientes.new')}
                        </button>
                    </div>
                }
            />

            <div className="flex-1 min-h-0 overflow-y-auto px-4 pb-8 space-y-6">
                {error && (
                    <div className="rounded-lg border border-red-500/30 bg-red-500/10 text-red-300 text-sm px-3 py-2">
                        {error}
                    </div>
                )}

                {/* Chats esperando respuesta (caso Pau): detección en vivo, sin datos nuevos */}
                {unanswered.length > 0 && (
                    <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-3">
                        <h3 className="text-xs uppercase tracking-wide text-amber-400 mb-2 flex items-center gap-1.5">
                            <AlertTriangle size={13} /> {t('pendientes.unanswered_title')} ({unanswered.length})
                        </h3>
                        <div className="space-y-1.5">
                            {unanswered.map((c) => (
                                <button
                                    key={c.conversation_id}
                                    onClick={() => goToChat(c.chat_phone)}
                                    className="w-full text-left rounded-lg bg-white/[0.03] hover:bg-white/[0.08] px-3 py-2 flex items-center justify-between gap-3"
                                >
                                    <div className="min-w-0">
                                        <span className="text-sm text-white">
                                            {c.patient_name?.trim() || c.display_name || c.chat_phone}
                                        </span>
                                        {c.last_message_preview && (
                                            <p className="text-xs text-white/40 truncate">“{c.last_message_preview}”</p>
                                        )}
                                    </div>
                                    <span className="text-[11px] text-amber-400 shrink-0">
                                        {Math.round(c.hours_waiting)} h {t('pendientes.waiting')}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                <Section title={t('pendientes.bucket_overdue')} items={buckets.vencidas} tone="red" />
                <Section title={t('pendientes.bucket_today')} items={buckets.hoy} tone="amber" />
                <Section title={t('pendientes.bucket_upcoming')} items={buckets.proximas} />
                <Section title={t('pendientes.bucket_no_date')} items={buckets.sinFecha} />
                {showClosed && <Section title={t('pendientes.bucket_closed')} items={buckets.cerradas} />}

                {!loading && !rows.length && !unanswered.length && (
                    <div className="text-center text-white/30 text-sm py-16">
                        {t('pendientes.empty')}
                    </div>
                )}
            </div>

            {/* Modal nuevo pendiente */}
            {modal && (
                <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setModal(false)}>
                    <div className="bg-[#0d1117] border border-white/[0.08] rounded-2xl w-full max-w-md p-5" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-between mb-4">
                            <h3 className="text-white font-medium">{t('pendientes.new')}</h3>
                            <button onClick={() => setModal(false)} className="text-white/40 hover:text-white"><X size={18} /></button>
                        </div>
                        <div className="space-y-3">
                            <input
                                className={inputCls}
                                placeholder={t('pendientes.f_title')}
                                value={fTitle}
                                onChange={(e) => setFTitle(e.target.value)}
                                maxLength={200}
                                autoFocus
                            />
                            <textarea
                                className={`${inputCls} min-h-[70px]`}
                                placeholder={t('pendientes.f_note')}
                                value={fNote}
                                onChange={(e) => setFNote(e.target.value)}
                            />
                            <div>
                                <label className="text-xs text-white/40 block mb-1">{t('pendientes.f_due')}</label>
                                <input
                                    type="datetime-local"
                                    className={inputCls}
                                    value={fDue}
                                    onChange={(e) => setFDue(e.target.value)}
                                />
                            </div>
                            <input
                                className={inputCls}
                                placeholder={t('pendientes.f_assigned')}
                                value={fAssigned}
                                onChange={(e) => setFAssigned(e.target.value)}
                                maxLength={120}
                            />
                        </div>
                        <div className="flex justify-end gap-2 mt-5">
                            <button onClick={() => setModal(false)} className="px-3 py-2 rounded-lg bg-white/[0.04] text-white/60 text-sm hover:bg-white/[0.1]">
                                {t('pendientes.close')}
                            </button>
                            <button
                                onClick={() => void createPending()}
                                disabled={saving || !fTitle.trim()}
                                className="px-4 py-2 rounded-lg bg-white text-[#0a0e1a] text-sm font-medium hover:bg-white/90 disabled:opacity-40"
                            >
                                {saving ? '…' : t('pendientes.save')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
