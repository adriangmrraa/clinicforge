import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    ListTodo, Plus, RefreshCw, X, CheckCircle2, Clock,
    AlertTriangle, MessageSquare, MessageCircle, Bot, User as UserIcon, Pin,
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';

/*
 * Módulo Pendientes con vencimiento (migs 075/076, tarea #2 2026-07-16).
 * Para que no se olviden chats/tareas cuando interviene la secretaria:
 *  - "Chats esperando respuesta": detección EN VIVO (caso Pau) + convertir en 1 clic.
 *  - Pendientes con vencimiento y PRIORIDAD (urgente/media/tranqui).
 *  - El bot crea pendientes URGENTES solos al derivar (Paula no mira el mail).
 */

type Priority = 'urgente' | 'media' | 'tranqui';

interface PendingRow {
    id: number;
    title: string;
    note: string | null;
    due_at: string | null;
    status: string;
    priority: Priority;
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

// Estética por prioridad: acento lateral + chip suave sin borde + punto CSS (no emoji) +
// tinte del avatar. Sin emoji (pedido Carlos 2026-07-23). Baja = celeste (calmo/profesional).
const PRIORITY_STYLE: Record<Priority, { accent: string; chip: string; dotColor: string; avatar: string; next: Priority }> = {
    urgente: { accent: 'bg-rose-500/70', chip: 'bg-rose-500/10 text-rose-300', dotColor: 'bg-rose-400', avatar: 'bg-rose-500/15 text-rose-200', next: 'media' },
    media: { accent: 'bg-amber-400/70', chip: 'bg-amber-500/10 text-amber-300', dotColor: 'bg-amber-400', avatar: 'bg-amber-500/15 text-amber-200', next: 'tranqui' },
    tranqui: { accent: 'bg-sky-500/50', chip: 'bg-sky-500/10 text-sky-300', dotColor: 'bg-sky-400', avatar: 'bg-sky-500/15 text-sky-200', next: 'urgente' },
};

// Iniciales para el avatar (ancla visual por persona → "diferenciar los nombres").
function initialsOf(s: string): string {
    const parts = s.trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return '?';
    return (parts[0][0] + (parts.length > 1 ? parts[1][0] : '')).toUpperCase();
}

function fmtPhonePretty(p: string): string {
    const d = p.replace(/\D/g, '');
    return d ? `+${d}` : p;
}

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
    const [fPriority, setFPriority] = useState<Priority>('media');

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
            abiertas: open.length,
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
                priority: fPriority,
                source: 'manual',
            });
            setModal(false);
            setFTitle(''); setFNote(''); setFDue(''); setFAssigned(''); setFPriority('media');
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

    const cyclePriority = async (r: PendingRow) => {
        try {
            await api.patch(`/admin/pendings/${r.id}`, { priority: PRIORITY_STYLE[r.priority]?.next || 'media' });
            void fetchAll();
        } catch {
            setError(t('pendientes.save_error'));
        }
    };

    const goToChat = (phone: string | null) => {
        if (phone) navigate(`/chats?phone=${encodeURIComponent(phone)}`);
        else navigate('/chats');
    };

    // Convertir un chat-colgado en pendiente con UN clic (vence en 3 horas, prioridad media).
    const convertChatToPending = async (c: UnansweredChat) => {
        try {
            const due = new Date(Date.now() + 3 * 3_600_000).toISOString();
            await api.post('/admin/pendings', {
                title: `${t('pendientes.reply_to')} ${c.patient_name?.trim() || c.display_name || c.chat_phone}`,
                note: c.last_message_preview ? `“${c.last_message_preview}”` : null,
                due_at: due,
                chat_phone: c.chat_phone,
                priority: 'media',
                source: 'chat_colgado',
            });
            void fetchAll();
        } catch {
            setError(t('pendientes.save_error'));
        }
    };

    const PriorityChip = ({ r }: { r: PendingRow }) => {
        const st = PRIORITY_STYLE[r.priority] || PRIORITY_STYLE.media;
        return (
            <button
                onClick={() => void cyclePriority(r)}
                title={t('pendientes.change_priority')}
                className={`inline-flex items-center gap-1.5 pl-2 pr-2.5 py-1 rounded-full text-[10px] font-semibold uppercase tracking-wider ${st.chip}`}
            >
                <span className={`w-1.5 h-1.5 rounded-full ${st.dotColor}`} />
                {t(`pendientes.priority_${r.priority}`)}
            </button>
        );
    };

    // Vencimiento como "tiempo que tenés": prominente y en rojo si ya venció.
    const DueBadge = ({ r }: { r: PendingRow }) => {
        if (!r.due_at) {
            return <span className="shrink-0 text-[11px] text-white/25 pt-0.5">{t('pendientes.no_due')}</span>;
        }
        return (
            <span
                className={`shrink-0 inline-flex items-center px-2.5 py-1 rounded-lg text-[11px] font-semibold tabular-nums ${
                    r.is_overdue ? 'bg-rose-500/15 text-rose-300' : 'bg-white/[0.05] text-white/55'
                }`}
                title={fmtDateTime(r.due_at)}
            >
                {fmtDueRelative(r.due_at, t)}
            </span>
        );
    };

    const Card = ({ r }: { r: PendingRow }) => {
        const pst = PRIORITY_STYLE[r.priority] || PRIORITY_STYLE.media;
        const waDigits = (r.chat_phone || '').replace(/\D/g, '');
        const person = r.patient_name?.trim() || (r.chat_phone ? fmtPhonePretty(r.chat_phone) : null);
        const heading = person || r.title;   // sin persona → la tarea es el título
        const task = person ? r.title : null; // con persona → el título es la tarea/problema
        return (
            <div className="group relative overflow-hidden rounded-2xl border border-white/[0.06] bg-white/[0.025] hover:bg-white/[0.05] transition-colors">
                <span className={`absolute left-0 top-0 bottom-0 w-1 ${pst.accent}`} />
                <div className="flex gap-3.5 p-4 pl-5">
                    {/* Avatar: ancla visual por persona (iniciales), teñido por prioridad */}
                    <div className={`shrink-0 w-10 h-10 rounded-full grid place-items-center text-[13px] font-semibold ${pst.avatar}`}>
                        {person ? initialsOf(person) : <span className={`w-2 h-2 rounded-full ${pst.dotColor}`} />}
                    </div>
                    <div className="flex-1 min-w-0">
                        {/* Fila 1: NOMBRE grande (quién) + vencimiento a la derecha (cuánto tiempo tenés) */}
                        <div className="flex items-start justify-between gap-3">
                            <h4 className="text-[15px] font-semibold text-white leading-tight truncate">{heading}</h4>
                            <DueBadge r={r} />
                        </div>
                        {/* Fila 2: la TAREA / el problema (qué hay que hacer) */}
                        {task && <p className="text-[13.5px] text-white/70 mt-1 leading-snug line-clamp-2">{task}</p>}
                        {r.note && <p className="text-[12px] text-white/40 mt-1 leading-relaxed line-clamp-2">{r.note}</p>}
                        {/* Fila 3: prioridad + origen + acciones */}
                        <div className="flex items-center justify-between gap-2 mt-3">
                            <div className="flex items-center flex-wrap gap-1.5 min-w-0">
                                <PriorityChip r={r} />
                                {r.created_by === 'bot' && (
                                    <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-medium bg-violet-500/10 text-violet-300">
                                        <Bot size={11} /> {t('pendientes.from_bot')}
                                    </span>
                                )}
                                {r.assigned_to && <span className="text-[11px] text-white/35 truncate">→ {r.assigned_to}</span>}
                            </div>
                            <div className="flex items-center gap-0.5 shrink-0 -mr-1">
                                {r.chat_phone && (
                                    <>
                                        <button
                                            onClick={() => goToChat(r.chat_phone)}
                                            title={t('pendientes.go_chat')}
                                            className="p-2 rounded-lg text-white/40 hover:text-blue-300 hover:bg-blue-500/10 transition-colors"
                                        >
                                            <MessageSquare size={16} />
                                        </button>
                                        {waDigits && (
                                            <a
                                                href={`https://wa.me/${waDigits}`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                title={t('pendientes.go_whatsapp')}
                                                className="p-2 rounded-lg text-white/40 hover:text-emerald-300 hover:bg-emerald-500/10 transition-colors"
                                            >
                                                <MessageCircle size={16} />
                                            </a>
                                        )}
                                    </>
                                )}
                                {r.status === 'abierto' ? (
                                    <>
                                        <button
                                            onClick={() => void setStatus(r.id, 'hecho')}
                                            title={t('pendientes.mark_done')}
                                            className="p-2 rounded-lg text-emerald-400/80 hover:text-emerald-300 hover:bg-emerald-500/15 transition-colors"
                                        >
                                            <CheckCircle2 size={16} />
                                        </button>
                                        <button
                                            onClick={() => void setStatus(r.id, 'cancelado')}
                                            title={t('pendientes.cancel')}
                                            className="p-2 rounded-lg text-white/30 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                                        >
                                            <X size={16} />
                                        </button>
                                    </>
                                ) : (
                                    <button
                                        onClick={() => void setStatus(r.id, 'abierto')}
                                        className="px-2.5 py-1 rounded-lg bg-white/[0.04] hover:bg-white/[0.1] text-[11px] text-white/50"
                                    >
                                        {t('pendientes.reopen')}
                                    </button>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        );
    };

    const Section = ({ title, items, tone }: { title: string; items: PendingRow[]; tone?: 'red' | 'amber' }) => {
        if (!items.length) return null;
        return (
            <div>
                <h3 className={`text-[11px] font-semibold uppercase tracking-widest mb-3 flex items-center gap-2 ${tone === 'red' ? 'text-rose-400/90' : tone === 'amber' ? 'text-amber-400/90' : 'text-white/40'}`}>
                    {title}
                    <span className={`px-1.5 py-0.5 rounded-md text-[10px] ${tone === 'red' ? 'bg-rose-500/10 text-rose-300' : tone === 'amber' ? 'bg-amber-500/10 text-amber-300' : 'bg-white/[0.06] text-white/50'}`}>{items.length}</span>
                </h3>
                <div className="space-y-3">{items.map((r) => <Card key={r.id} r={r} />)}</div>
            </div>
        );
    };

    const PrioritySelector = ({ value, onChange }: { value: Priority; onChange: (p: Priority) => void }) => (
        <div className="flex gap-1.5">
            {(['urgente', 'media', 'tranqui'] as const).map((p) => (
                <button
                    key={p}
                    onClick={() => onChange(p)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[11px] font-medium transition-all ${value === p
                        ? PRIORITY_STYLE[p].chip
                        : 'bg-white/[0.04] text-white/40 hover:bg-white/[0.08]'}`}
                >
                    <span className={`w-1.5 h-1.5 rounded-full ${PRIORITY_STYLE[p].dotColor}`} />
                    {t(`pendientes.priority_${p}`)}
                </button>
            ))}
        </div>
    );

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

                {/* Resumen: 3 contadores de un vistazo */}
                <div className="grid grid-cols-3 gap-3">
                    {[
                        { n: buckets.vencidas.length, label: t('pendientes.bucket_overdue'), cls: buckets.vencidas.length ? 'text-red-400 border-red-500/25 bg-red-500/[0.06]' : 'text-white/30 border-white/[0.06] bg-white/[0.02]' },
                        { n: buckets.hoy.length, label: t('pendientes.bucket_today'), cls: buckets.hoy.length ? 'text-amber-300 border-amber-500/25 bg-amber-500/[0.06]' : 'text-white/30 border-white/[0.06] bg-white/[0.02]' },
                        { n: buckets.abiertas, label: t('pendientes.open_total'), cls: 'text-white/70 border-white/[0.08] bg-white/[0.02]' },
                    ].map((c, i) => (
                        <div key={i} className={`rounded-xl border px-4 py-3 ${c.cls}`}>
                            <div className="text-2xl font-bold tabular-nums">{c.n}</div>
                            <div className="text-[11px] uppercase tracking-wide opacity-80">{c.label}</div>
                        </div>
                    ))}
                </div>

                {/* Chats esperando respuesta (caso Pau): detección en vivo + convertir en 1 clic */}
                {unanswered.length > 0 && (
                    <div className="rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-3.5">
                        <h3 className="text-[11px] font-semibold uppercase tracking-widest text-amber-400 mb-2.5 flex items-center gap-1.5">
                            <AlertTriangle size={13} /> {t('pendientes.unanswered_title')}
                            <span className="px-1.5 py-0.5 rounded-md text-[10px] bg-amber-500/15">{unanswered.length}</span>
                        </h3>
                        <div className="space-y-1.5">
                            {unanswered.map((c) => (
                                <div
                                    key={c.conversation_id}
                                    className="w-full rounded-lg bg-white/[0.03] hover:bg-white/[0.06] px-3 py-2 flex items-center justify-between gap-3 transition-colors"
                                >
                                    <button onClick={() => goToChat(c.chat_phone)} className="min-w-0 text-left flex-1">
                                        <span className="text-sm text-white font-medium">
                                            {c.patient_name?.trim() || c.display_name || c.chat_phone}
                                        </span>
                                        {c.last_message_preview && (
                                            <p className="text-xs text-white/40 truncate">“{c.last_message_preview}”</p>
                                        )}
                                    </button>
                                    <span className="text-[11px] text-amber-400 font-medium shrink-0 tabular-nums">
                                        {Math.round(c.hours_waiting)} h {t('pendientes.waiting')}
                                    </span>
                                    <button
                                        onClick={() => void convertChatToPending(c)}
                                        title={t('pendientes.pin_button')}
                                        className="p-2 rounded-lg bg-blue-500/10 hover:bg-blue-500/25 text-blue-400 shrink-0 transition-colors"
                                    >
                                        <Pin size={14} />
                                    </button>
                                </div>
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
                    <div className="text-center py-16">
                        <ListTodo size={36} className="mx-auto text-white/15 mb-3" />
                        <p className="text-white/30 text-sm">{t('pendientes.empty')}</p>
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
                                <label className="text-xs text-white/40 block mb-1.5">{t('pendientes.f_priority')}</label>
                                <PrioritySelector value={fPriority} onChange={setFPriority} />
                            </div>
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
