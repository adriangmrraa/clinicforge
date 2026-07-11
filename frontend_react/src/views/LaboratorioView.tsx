import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
    FlaskConical, Plus, RefreshCw, X, ChevronRight,
    CheckCircle2, Building2, Pencil,
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';

/*
 * Módulo Laboratorio — F2-4 L1 (scratch/PLAN_LABORATORIO.md).
 * Tablero por estados con semáforo de vencimientos. Referencias: Dentalink
 * (estados + pago por solicitud), Open Dental (vínculo con turnos),
 * Crownbeam (semáforo por fecha prometida).
 */

interface LabRow {
    id: number;
    name: string;
    email: string | null;
    phone: string | null;
    notes: string | null;
    is_active: boolean;
}

interface LabCaseRow {
    id: number;
    patient_id: number;
    patient_name: string;
    patient_phone: string | null;
    professional_id: number | null;
    professional_name: string | null;
    lab_id: number | null;
    lab_name: string | null;
    work_type: string;
    tooth_numbers: string | null;
    shade: string | null;
    status: string;
    sent_at: string | null;
    promised_at: string | null;
    received_at: string | null;
    placed_at: string | null;
    rework_count: number;
    cost: number | null;
    lab_paid: boolean;
    notes: string | null;
    is_overdue: boolean;
    origin_appointment_id: string | null;
    patient_notified_at?: string | null;
    lab_chased_at?: string | null;
}

interface ProfessionalOpt {
    id: number;
    first_name: string;
    last_name?: string;
}

const WORK_TYPES = [
    'Corona', 'Puente', 'Prótesis completa', 'Prótesis parcial',
    'Placa de bruxismo', 'Férula', 'Carilla', 'Incrustación', 'Otro',
];

const STATUS_ORDER = ['pendiente_envio', 'enviado', 'recibido', 'a_ajustar', 'colocado'] as const;

const NEXT_STATUS: Record<string, string> = {
    pendiente_envio: 'enviado',
    enviado: 'recibido',
    a_ajustar: 'recibido',
};

const STATUS_STYLE: Record<string, { dot: string; col: string }> = {
    pendiente_envio: { dot: 'bg-amber-400', col: 'border-amber-500/20' },
    enviado: { dot: 'bg-blue-400', col: 'border-blue-500/20' },
    recibido: { dot: 'bg-violet-400', col: 'border-violet-500/20' },
    a_ajustar: { dot: 'bg-orange-400', col: 'border-orange-500/25' },
    colocado: { dot: 'bg-emerald-400', col: 'border-emerald-500/20' },
    cancelado: { dot: 'bg-white/30', col: 'border-white/[0.08]' },
};

function fmtDate(d: string | null): string {
    if (!d) return '—';
    const [y, m, day] = d.split('-');
    return `${day}/${m}/${y.slice(2)}`;
}

const inputCls =
    'w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm focus:border-blue-500 focus:ring-0 outline-none placeholder-white/30';

export default function LaboratorioView() {
    const { t } = useTranslation();
    const [searchParams, setSearchParams] = useSearchParams();

    const [cases, setCases] = useState<LabCaseRow[]>([]);
    const [labs, setLabs] = useState<LabRow[]>([]);
    const [professionals, setProfessionals] = useState<ProfessionalOpt[]>([]);
    const [patients, setPatients] = useState<any[]>([]);
    const [overdueCount, setOverdueCount] = useState(0);
    const [loading, setLoading] = useState(false);

    const [filterLab, setFilterLab] = useState<number | ''>('');
    const [filterProf, setFilterProf] = useState<number | ''>('');
    const [onlyOverdue, setOnlyOverdue] = useState(false);
    const [showCancelled, setShowCancelled] = useState(false);
    // Pulido UI (pedido Carlos): búsqueda por paciente, en vivo y sin servidor
    const [searchQ, setSearchQ] = useState('');

    const [caseModal, setCaseModal] = useState<Partial<LabCaseRow> | null>(null);
    const [labsModal, setLabsModal] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchCases = useCallback(async () => {
        setLoading(true);
        try {
            const params = new URLSearchParams();
            if (filterLab) params.set('lab_id', String(filterLab));
            if (filterProf) params.set('professional_id', String(filterProf));
            if (onlyOverdue) params.set('overdue', 'true');
            const res = await api.get(`/admin/lab-cases?${params}`);
            setCases(res.data.cases || []);
            setOverdueCount(res.data.overdue_count || 0);
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Error al cargar trabajos');
        } finally {
            setLoading(false);
        }
    }, [filterLab, filterProf, onlyOverdue]);

    const fetchLabs = useCallback(async () => {
        try {
            const res = await api.get('/admin/labs?include_inactive=true');
            setLabs(res.data.labs || []);
        } catch { /* noop */ }
    }, []);

    useEffect(() => { fetchCases(); }, [fetchCases]);
    useEffect(() => {
        fetchLabs();
        api.get('/admin/professionals').then(r => setProfessionals(r.data || [])).catch(() => {});
        api.get('/admin/patients?limit=5000').then(r => setPatients(r.data?.patients || r.data || [])).catch(() => {});
    }, [fetchLabs]);

    // Alta pre-cargada desde el drawer del turno (?new=1&patient_id=&professional_id=&appointment_id=)
    useEffect(() => {
        if (searchParams.get('new') === '1') {
            setCaseModal({
                patient_id: Number(searchParams.get('patient_id')) || undefined,
                professional_id: Number(searchParams.get('professional_id')) || undefined,
                origin_appointment_id: searchParams.get('appointment_id') || null,
            } as Partial<LabCaseRow>);
            setSearchParams(prev => {
                ['new', 'patient_id', 'professional_id', 'appointment_id'].forEach(k => prev.delete(k));
                return prev;
            }, { replace: true });
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const changeStatus = async (c: LabCaseRow, status: string) => {
        try {
            await api.patch(`/admin/lab-cases/${c.id}`, { status });
            fetchCases();
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Error al cambiar el estado');
        }
    };

    // L2: acciones manuales (nada automático sin control)
    const [notice, setNotice] = useState<string | null>(null);
    useEffect(() => {
        if (notice) {
            const t2 = setTimeout(() => setNotice(null), 4000);
            return () => clearTimeout(t2);
        }
    }, [notice]);

    // Blindaje anti-costos / anti-mensajes-falsos: el click NO envía nada —
    // pide el preflight (destinatario, mensaje exacto, vía y costo) y abre
    // un modal de confirmación. El servidor re-verifica la vía al confirmar.
    const [notifyConfirm, setNotifyConfirm] = useState<{
        caseRow: LabCaseRow;
        pf: any;
    } | null>(null);
    const [notifySending, setNotifySending] = useState(false);

    const notifyPatient = async (c: LabCaseRow) => {
        try {
            const res = await api.get(`/admin/lab-cases/${c.id}/notify-preflight`);
            setNotifyConfirm({ caseRow: c, pf: res.data });
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Error al preparar el aviso');
        }
    };

    const confirmNotify = async () => {
        if (!notifyConfirm) return;
        setNotifySending(true);
        try {
            await api.post(`/admin/lab-cases/${notifyConfirm.caseRow.id}/notify-patient`);
            setNotice(t('lab.notice_sent'));
            setNotifyConfirm(null);
            fetchCases();
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Error al enviar el WhatsApp');
            setNotifyConfirm(null);
        } finally {
            setNotifySending(false);
        }
    };

    const chaseLab = async (c: LabCaseRow) => {
        try {
            await api.post(`/admin/lab-cases/${c.id}/chase-lab`);
            setNotice(t('lab.email_sent'));
            fetchCases();
        } catch (e: any) {
            setError(e?.response?.data?.detail || 'Error al enviar el email');
        }
    };

    const columns = useMemo(() => {
        const q = searchQ.trim().toLowerCase();
        const visible = cases.filter(
            c =>
                (showCancelled || c.status !== 'cancelado') &&
                (!q ||
                    c.patient_name.toLowerCase().includes(q) ||
                    c.work_type.toLowerCase().includes(q) ||
                    (c.lab_name || '').toLowerCase().includes(q))
        );
        return STATUS_ORDER.map(key => ({
            key,
            items: visible.filter(c => c.status === key),
        }));
    }, [cases, showCancelled, searchQ]);

    // Resumen de lo cargado (pedido Carlos: "lo que se ha cargado y demás")
    const stats = useMemo(() => {
        const active = cases.filter(
            c => !['colocado', 'cancelado'].includes(c.status)
        ).length;
        const toNotify = cases.filter(
            c => c.status === 'recibido' && !c.patient_notified_at
        ).length;
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - 30);
        const placed30 = cases.filter(
            c =>
                c.status === 'colocado' &&
                c.placed_at &&
                new Date(c.placed_at + 'T00:00:00') >= cutoff
        ).length;
        return { active, toNotify, placed30 };
    }, [cases]);

    const cancelledItems = useMemo(
        () => cases.filter(c => c.status === 'cancelado'),
        [cases]
    );

    const activeLabs = labs.filter(l => l.is_active);

    return (
        <div className="flex flex-col h-full overflow-hidden">
            <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-5">
                <PageHeader
                    title={t('lab.title')}
                    subtitle={t('lab.subtitle')}
                    icon={<FlaskConical size={22} />}
                />

                {/* Resumen de lo cargado */}
                <div className="flex flex-wrap items-center gap-2">
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-300 border border-blue-500/20">
                        🔬 {stats.active} {t('lab.stat_active')}
                    </span>
                    <button
                        onClick={() => setOnlyOverdue(v => !v)}
                        className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold border transition-colors ${
                            onlyOverdue
                                ? 'bg-red-500/25 text-red-300 border-red-500/40'
                                : 'bg-red-500/10 text-red-400 border-red-500/20 hover:bg-red-500/20'
                        }`}
                    >
                        ⚠ {overdueCount} {t('lab.stat_overdue')}
                    </button>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-violet-500/10 text-violet-300 border border-violet-500/20">
                        📲 {stats.toNotify} {t('lab.stat_to_notify')}
                    </span>
                    <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        ✅ {stats.placed30} {t('lab.stat_placed30')}
                    </span>
                </div>

                {/* Toolbar */}
                <div className="flex flex-wrap items-center gap-2.5">
                    <button
                        onClick={() => setCaseModal({})}
                        className="flex items-center gap-2 px-4 py-2.5 bg-white text-[#0a0e1a] rounded-xl text-sm font-semibold hover:bg-white/90 transition-colors"
                    >
                        <Plus size={16} /> {t('lab.new_case')}
                    </button>
                    <button
                        onClick={() => setLabsModal(true)}
                        className="flex items-center gap-2 px-3 py-2.5 bg-white/[0.05] text-white/70 border border-white/[0.08] rounded-xl text-sm font-medium hover:bg-white/[0.09] transition-colors"
                    >
                        <Building2 size={15} /> {t('lab.manage_labs')}
                    </button>
                    <input
                        value={searchQ}
                        onChange={e => setSearchQ(e.target.value)}
                        placeholder={t('lab.search_patient')}
                        className="flex-1 min-w-[170px] max-w-[280px] px-3 py-2.5 bg-white/[0.04] border border-white/[0.08] rounded-xl text-sm text-white placeholder-white/25 focus:border-blue-500/40 focus:outline-none"
                    />
                    <select
                        value={filterLab}
                        onChange={e => setFilterLab(e.target.value ? Number(e.target.value) : '')}
                        className="bg-white/[0.04] border border-white/[0.08] text-white text-sm rounded-lg px-3 py-2.5 focus:outline-none"
                    >
                        <option value="">{t('lab.lab')}: {t('lab.all')}</option>
                        {activeLabs.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                    </select>
                    <button
                        onClick={fetchCases}
                        className="p-2.5 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white/50 hover:text-white transition-colors"
                        title={t('lab.refresh')}
                    >
                        <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>

                {/* Profesionales como pills (mismo patrón que Estrategia) */}
                <div className="flex items-center gap-2 flex-wrap">
                    <button
                        onClick={() => setFilterProf('')}
                        className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                            filterProf === ''
                                ? 'bg-white text-[#0a0e1a] border-white'
                                : 'bg-white/[0.04] text-white/60 border-white/[0.08] hover:text-white hover:bg-white/[0.08]'
                        }`}
                    >
                        {t('lab.all')}
                    </button>
                    {professionals.map(p => {
                        const name = `${p.first_name} ${p.last_name || ''}`.trim();
                        const active = filterProf === p.id;
                        return (
                            <button
                                key={p.id}
                                onClick={() => setFilterProf(active ? '' : p.id)}
                                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                                    active
                                        ? 'bg-blue-500/20 text-blue-300 border-blue-500/40'
                                        : 'bg-white/[0.04] text-white/60 border-white/[0.08] hover:text-white hover:bg-white/[0.08]'
                                }`}
                            >
                                {name}
                            </button>
                        );
                    })}
                </div>

                {error && (
                    <div className="px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/25 text-red-400 text-sm flex items-center justify-between">
                        {error}
                        <button onClick={() => setError(null)}><X size={14} /></button>
                    </div>
                )}
                {notice && (
                    <div className="px-4 py-3 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 text-sm">
                        ✓ {notice}
                    </div>
                )}

                {/* Tablero */}
                <div className="flex gap-3 overflow-x-auto pb-3">
                    {columns.map(col => (
                        <div
                            key={col.key}
                            className={`shrink-0 w-[265px] rounded-2xl border bg-white/[0.015] ${STATUS_STYLE[col.key].col}`}
                        >
                            <div className="px-3.5 py-3 flex items-center gap-2 border-b border-white/[0.05]">
                                <span className={`w-2 h-2 rounded-full ${STATUS_STYLE[col.key].dot}`} />
                                <span className="text-xs font-bold text-white/70 uppercase tracking-wider">
                                    {t(`lab.st_${col.key}`)}
                                </span>
                                <span className="ml-auto text-xs text-white/30">{col.items.length}</span>
                            </div>
                            <div className="p-2.5 space-y-2 min-h-[120px] max-h-[calc(100vh-330px)] overflow-y-auto">
                                {col.items.length === 0 && (
                                    <p className="text-[11px] text-white/20 text-center py-6">
                                        {t('lab.no_cases')}
                                    </p>
                                )}
                                {col.items.map(c => (
                                    <div
                                        key={c.id}
                                        className={`rounded-xl border p-3 bg-white/[0.03] hover:bg-white/[0.05] transition-colors ${
                                            c.is_overdue ? 'border-red-500/40' : 'border-white/[0.06]'
                                        }`}
                                    >
                                        <div className="flex items-start justify-between gap-2">
                                            <button
                                                onClick={() => setCaseModal(c)}
                                                className="text-left flex-1 min-w-0"
                                            >
                                                <p className="text-sm font-semibold text-white truncate">
                                                    {c.patient_name}
                                                </p>
                                                <p className="text-xs text-white/50 truncate">
                                                    {c.work_type}
                                                    {c.tooth_numbers ? ` · ${c.tooth_numbers}` : ''}
                                                    {c.shade ? ` · ${c.shade}` : ''}
                                                </p>
                                            </button>
                                            <div className="flex flex-col items-end gap-1 shrink-0">
                                                <button
                                                    onClick={() => setCaseModal(c)}
                                                    className="text-white/25 hover:text-white/60"
                                                    title={t('lab.edit')}
                                                >
                                                    <Pencil size={13} />
                                                </button>
                                                {c.cost != null && c.cost > 0 && (
                                                    <span className="text-[10px] text-white/35 tabular-nums">
                                                        ${Number(c.cost).toLocaleString('es-AR')}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-1.5 mt-2 flex-wrap">
                                            {c.professional_name && c.professional_name.trim() && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-300/80">
                                                    {c.professional_name.trim().split(' ')[0]}
                                                </span>
                                            )}
                                            {c.lab_name && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-white/50">
                                                    {c.lab_name}
                                                </span>
                                            )}
                                            {c.promised_at && (
                                                <span
                                                    className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                                                        c.is_overdue
                                                            ? 'bg-red-500/15 text-red-400'
                                                            : 'bg-white/[0.06] text-white/40'
                                                    }`}
                                                >
                                                    {c.is_overdue ? `⚠ ${t('lab.overdue_badge')} ` : ''}
                                                    {t('lab.promised')} {fmtDate(c.promised_at)}
                                                </span>
                                            )}
                                            {c.rework_count > 0 && (
                                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-500/15 text-orange-400 font-medium">
                                                    🔁 {c.rework_count}
                                                </span>
                                            )}
                                        </div>
                                        {/* Acciones de transición */}
                                        <div className="flex gap-1.5 mt-2.5">
                                            {c.status === 'recibido' ? (
                                                <>
                                                    <button
                                                        onClick={() => changeStatus(c, 'colocado')}
                                                        className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-[11px] font-semibold rounded-lg bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 hover:bg-emerald-500/25 transition-colors"
                                                    >
                                                        <CheckCircle2 size={12} /> {t('lab.set_placed')}
                                                    </button>
                                                    <button
                                                        onClick={() => changeStatus(c, 'a_ajustar')}
                                                        className="px-2 py-1.5 text-[11px] font-semibold rounded-lg bg-orange-500/15 text-orange-400 border border-orange-500/25 hover:bg-orange-500/25 transition-colors"
                                                    >
                                                        🔁 {t('lab.set_adjust')}
                                                    </button>
                                                </>
                                            ) : NEXT_STATUS[c.status] ? (
                                                <button
                                                    onClick={() => changeStatus(c, NEXT_STATUS[c.status])}
                                                    className="flex-1 flex items-center justify-center gap-1 px-2 py-1.5 text-[11px] font-semibold rounded-lg bg-white/[0.06] text-white/70 border border-white/[0.08] hover:bg-white/[0.1] transition-colors"
                                                >
                                                    {t('lab.advance')} {t(`lab.st_${NEXT_STATUS[c.status]}`)}
                                                    <ChevronRight size={12} />
                                                </button>
                                            ) : null}
                                        </div>
                                        {/* L2: avisar al paciente que llegó su trabajo */}
                                        {c.status === 'recibido' && (
                                            <button
                                                onClick={() => notifyPatient(c)}
                                                className={`w-full mt-1.5 px-2 py-1.5 text-[11px] font-semibold rounded-lg border transition-colors ${
                                                    c.patient_notified_at
                                                        ? 'bg-white/[0.03] text-white/35 border-white/[0.06]'
                                                        : 'bg-violet-500/15 text-violet-300 border-violet-500/25 hover:bg-violet-500/25'
                                                }`}
                                            >
                                                📲 {c.patient_notified_at
                                                    ? `${t('lab.notified')} ✓`
                                                    : t('lab.notify_patient')}
                                            </button>
                                        )}
                                        {/* L2: reclamar al laboratorio un trabajo vencido */}
                                        {c.is_overdue && (
                                            <button
                                                onClick={() => chaseLab(c)}
                                                className={`w-full mt-1.5 px-2 py-1.5 text-[11px] font-semibold rounded-lg border transition-colors ${
                                                    c.lab_chased_at
                                                        ? 'bg-white/[0.03] text-white/35 border-white/[0.06]'
                                                        : 'bg-red-500/15 text-red-400 border-red-500/25 hover:bg-red-500/25'
                                                }`}
                                            >
                                                📧 {c.lab_chased_at
                                                    ? `${t('lab.chased')} ${fmtDate(c.lab_chased_at.slice(0, 10))}`
                                                    : t('lab.chase_lab')}
                                            </button>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Cancelados (plegado) */}
                <button
                    onClick={() => setShowCancelled(v => !v)}
                    className="text-xs text-white/30 hover:text-white/60 transition-colors"
                >
                    {showCancelled ? '▾' : '▸'} {t('lab.st_cancelado')} ({cancelledItems.length})
                </button>
            </div>

            {/* Modal trabajo */}
            {caseModal !== null && (
                <LabCaseModal
                    initial={caseModal}
                    labs={activeLabs}
                    professionals={professionals}
                    patients={patients}
                    saving={saving}
                    onClose={() => setCaseModal(null)}
                    onSave={async payload => {
                        setSaving(true);
                        try {
                            if ((caseModal as LabCaseRow).id) {
                                await api.patch(`/admin/lab-cases/${(caseModal as LabCaseRow).id}`, payload);
                            } else {
                                await api.post('/admin/lab-cases', payload);
                            }
                            setCaseModal(null);
                            fetchCases();
                        } catch (e: any) {
                            setError(e?.response?.data?.detail || 'Error al guardar');
                        } finally {
                            setSaving(false);
                        }
                    }}
                />
            )}

            {/* Modal laboratorios */}
            {labsModal && (
                <LabsModal
                    labs={labs}
                    onClose={() => setLabsModal(false)}
                    onChanged={fetchLabs}
                />
            )}

            {/* Modal de confirmación de aviso al paciente (anti-mensajes-falsos) */}
            {notifyConfirm && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
                    onClick={() => setNotifyConfirm(null)}
                >
                    <div
                        className="bg-[#0d1117] border border-white/[0.08] rounded-2xl w-full max-w-md p-5 space-y-4"
                        onClick={e => e.stopPropagation()}
                    >
                        <h3 className="text-base font-bold text-white">
                            📲 {t('lab.notify_confirm_title')}
                        </h3>

                        <div className="space-y-1">
                            <p className="text-xs text-white/40">{t('lab.notify_to')}</p>
                            <p className="text-sm font-semibold text-white">
                                {notifyConfirm.pf.patient_name}
                                <span className="text-white/40 font-normal ml-2">
                                    {notifyConfirm.pf.phone}
                                </span>
                            </p>
                        </div>

                        <div className="space-y-1">
                            <p className="text-xs text-white/40">{t('lab.notify_msg')}</p>
                            <div className="rounded-xl bg-emerald-500/[0.06] border border-emerald-500/15 p-3 text-sm text-white/80 leading-relaxed">
                                {notifyConfirm.pf.message}
                            </div>
                        </div>

                        {/* Semáforo de vía / costo (regla octubre: cada mensaje vale plata) */}
                        {notifyConfirm.pf.will_use === 'session' && (
                            <div className="px-3 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 text-xs font-medium">
                                🟢 {t('lab.win_free')}
                            </div>
                        )}
                        {notifyConfirm.pf.will_use === 'template' && (
                            <div className="px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-400 text-xs font-medium">
                                🟠 {t('lab.win_template')}
                            </div>
                        )}
                        {notifyConfirm.pf.will_use === 'blocked' && (
                            <div className="px-3 py-2 rounded-xl bg-red-500/10 border border-red-500/25 text-red-400 text-xs font-medium">
                                🔴 {t('lab.win_blocked')}
                            </div>
                        )}
                        {notifyConfirm.pf.already_notified_at && (
                            <div className="px-3 py-2 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-400 text-xs">
                                ⚠ {t('lab.already_notified_warn')}{' '}
                                {fmtDate(notifyConfirm.pf.already_notified_at.slice(0, 10))} —{' '}
                                {t('lab.resend_q')}
                            </div>
                        )}

                        <div className="flex gap-2 pt-1">
                            <button
                                onClick={() => setNotifyConfirm(null)}
                                className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium bg-white/[0.05] text-white/60 border border-white/[0.08] hover:bg-white/[0.09] transition-colors"
                            >
                                {t('lab.cancel')}
                            </button>
                            <button
                                onClick={confirmNotify}
                                disabled={notifySending || notifyConfirm.pf.will_use === 'blocked'}
                                className="flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:bg-emerald-500/30 transition-colors disabled:opacity-40"
                            >
                                {notifySending ? '…' : t('lab.send_confirm')}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------

function LabCaseModal({
    initial, labs, professionals, patients, saving, onClose, onSave,
}: {
    initial: Partial<LabCaseRow>;
    labs: LabRow[];
    professionals: ProfessionalOpt[];
    patients: any[];
    saving: boolean;
    onClose: () => void;
    onSave: (payload: any) => Promise<void>;
}) {
    const { t } = useTranslation();
    const isEdit = !!initial.id;
    const [form, setForm] = useState({
        patient_id: initial.patient_id ? String(initial.patient_id) : '',
        professional_id: initial.professional_id ? String(initial.professional_id) : '',
        lab_id: initial.lab_id ? String(initial.lab_id) : '',
        work_type: initial.work_type || '',
        tooth_numbers: initial.tooth_numbers || '',
        shade: initial.shade || '',
        promised_at: initial.promised_at || '',
        cost: initial.cost != null ? String(initial.cost) : '',
        notes: initial.notes || '',
        status: initial.status || 'pendiente_envio',
    });
    const [patientSearch, setPatientSearch] = useState('');

    useEffect(() => {
        if (initial.patient_id && patients.length) {
            const p = patients.find((x: any) => x.id === initial.patient_id);
            if (p) setPatientSearch(`${p.first_name} ${p.last_name || ''}`.trim());
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [patients]);

    const filteredPatients = useMemo(() => {
        const q = patientSearch.trim().toLowerCase();
        if (!q) return [];
        return patients
            .filter((p: any) =>
                `${p.first_name} ${p.last_name || ''}`.toLowerCase().includes(q) ||
                (p.phone_number || '').includes(q)
            )
            .slice(0, 8);
    }, [patients, patientSearch]);

    const set = (k: string, v: string) => setForm(prev => ({ ...prev, [k]: v }));

    const submit = () => {
        if (!form.patient_id || !form.work_type) return;
        onSave({
            patient_id: Number(form.patient_id),
            professional_id: form.professional_id ? Number(form.professional_id) : null,
            lab_id: form.lab_id ? Number(form.lab_id) : null,
            work_type: form.work_type,
            tooth_numbers: form.tooth_numbers || null,
            shade: form.shade || null,
            promised_at: form.promised_at || null,
            cost: form.cost !== '' ? Number(form.cost) : null,
            notes: form.notes || null,
            ...(isEdit ? {} : {
                status: form.status,
                origin_appointment_id: initial.origin_appointment_id || null,
            }),
        });
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
            <div
                className="bg-[#0d1117] border border-white/[0.08] rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-5 space-y-4"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex items-center justify-between">
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                        <FlaskConical size={17} className="text-white/40" />
                        {isEdit ? `${t('lab.edit')} — ${initial.patient_name}` : t('lab.new_case')}
                    </h3>
                    <button onClick={onClose} className="text-white/30 hover:text-white"><X size={18} /></button>
                </div>

                {!isEdit && (
                    <div className="space-y-1 relative">
                        <label className="text-xs font-semibold text-white/50">{t('lab.patient')} *</label>
                        <input
                            className={inputCls}
                            value={patientSearch}
                            placeholder={t('lab.select')}
                            onChange={e => {
                                setPatientSearch(e.target.value);
                                set('patient_id', '');
                            }}
                        />
                        {patientSearch && !form.patient_id && filteredPatients.length > 0 && (
                            <div className="absolute z-10 left-0 right-0 mt-1 bg-[#0d1117] border border-white/[0.1] rounded-xl overflow-hidden shadow-xl">
                                {filteredPatients.map((p: any) => (
                                    <button
                                        key={p.id}
                                        className="w-full text-left px-3 py-2 text-sm text-white/80 hover:bg-white/[0.06]"
                                        onClick={() => {
                                            set('patient_id', String(p.id));
                                            setPatientSearch(`${p.first_name} ${p.last_name || ''}`.trim());
                                        }}
                                    >
                                        {p.first_name} {p.last_name || ''}
                                        <span className="text-white/30 text-xs ml-2">{p.phone_number}</span>
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-white/50">{t('lab.work_type')} *</label>
                        <select className={inputCls} value={form.work_type} onChange={e => set('work_type', e.target.value)}>
                            <option value="">{t('lab.select')}</option>
                            {WORK_TYPES.map(w => <option key={w} value={w}>{w}</option>)}
                            {form.work_type && !WORK_TYPES.includes(form.work_type) && (
                                <option value={form.work_type}>{form.work_type}</option>
                            )}
                        </select>
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-white/50">{t('lab.lab')}</label>
                        <select className={inputCls} value={form.lab_id} onChange={e => set('lab_id', e.target.value)}>
                            <option value="">{t('lab.select')}</option>
                            {labs.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
                        </select>
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-white/50">{t('lab.professional')}</label>
                        <select className={inputCls} value={form.professional_id} onChange={e => set('professional_id', e.target.value)}>
                            <option value="">{t('lab.select')}</option>
                            {professionals.map(p => (
                                <option key={p.id} value={p.id}>
                                    {`${p.first_name} ${p.last_name || ''}`.trim()}
                                </option>
                            ))}
                        </select>
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-white/50">{t('lab.promised')}</label>
                        <input type="date" className={inputCls} value={form.promised_at} onChange={e => set('promised_at', e.target.value)} />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-white/50">{t('lab.tooth')}</label>
                        <input className={inputCls} placeholder="Ej: 11, 12" value={form.tooth_numbers} onChange={e => set('tooth_numbers', e.target.value)} />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-white/50">{t('lab.shade')}</label>
                        <input className={inputCls} placeholder="Ej: A2" value={form.shade} onChange={e => set('shade', e.target.value)} />
                    </div>
                    <div className="space-y-1">
                        <label className="text-xs font-semibold text-white/50">{t('lab.cost')}</label>
                        <input type="number" min="0" step="0.01" className={inputCls} placeholder="0.00" value={form.cost} onChange={e => set('cost', e.target.value)} />
                    </div>
                    {isEdit && (
                        <div className="space-y-1">
                            <label className="text-xs font-semibold text-white/50">{t('lab.st_label')}</label>
                            <select className={inputCls} value={form.status} onChange={e => set('status', e.target.value)}>
                                {['pendiente_envio', 'enviado', 'recibido', 'a_ajustar', 'colocado', 'cancelado'].map(s => (
                                    <option key={s} value={s}>{t(`lab.st_${s}`)}</option>
                                ))}
                            </select>
                        </div>
                    )}
                </div>

                <div className="space-y-1">
                    <label className="text-xs font-semibold text-white/50">{t('lab.notes')}</label>
                    <textarea rows={2} className={inputCls} value={form.notes} onChange={e => set('notes', e.target.value)} />
                </div>

                <div className="flex gap-2 pt-1">
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-2.5 rounded-xl text-sm font-medium bg-white/[0.05] text-white/60 border border-white/[0.08] hover:bg-white/[0.09] transition-colors"
                    >
                        {t('lab.cancel')}
                    </button>
                    <button
                        onClick={() => {
                            if (isEdit) {
                                onSave({
                                    professional_id: form.professional_id ? Number(form.professional_id) : null,
                                    lab_id: form.lab_id ? Number(form.lab_id) : null,
                                    work_type: form.work_type,
                                    tooth_numbers: form.tooth_numbers || null,
                                    shade: form.shade || null,
                                    promised_at: form.promised_at || null,
                                    cost: form.cost !== '' ? Number(form.cost) : null,
                                    notes: form.notes || null,
                                    status: form.status,
                                });
                            } else {
                                submit();
                            }
                        }}
                        disabled={saving || (!isEdit && (!form.patient_id || !form.work_type)) || (isEdit && !form.work_type)}
                        className="flex-1 px-4 py-2.5 rounded-xl text-sm font-semibold bg-white text-[#0a0e1a] hover:bg-white/90 transition-colors disabled:opacity-40"
                    >
                        {saving ? '…' : t('lab.save')}
                    </button>
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------

function LabsModal({
    labs, onClose, onChanged,
}: {
    labs: LabRow[];
    onClose: () => void;
    onChanged: () => void;
}) {
    const { t } = useTranslation();
    const [form, setForm] = useState({ name: '', email: '', phone: '' });
    const [busy, setBusy] = useState(false);
    const [msg, setMsg] = useState<string | null>(null);

    // Idea Carlos: los labs cargados en BLOQUEOS (etiqueta "Laboratorio") se
    // ofrecen acá para importar con un click — solo se completa el email
    const [candidates, setCandidates] = useState<{ phone_number: string; name: string }[]>([]);
    const fetchCandidates = () =>
        api.get('/admin/labs/blocked-candidates')
            .then(r => setCandidates(r.data.candidates || []))
            .catch(() => {});
    useEffect(() => { fetchCandidates(); }, []);

    const addLab = async () => {
        if (!form.name.trim()) return;
        setBusy(true);
        setMsg(null);
        try {
            await api.post('/admin/labs', form);
            setForm({ name: '', email: '', phone: '' });
            onChanged();
            fetchCandidates();
        } catch (e: any) {
            setMsg(e?.response?.data?.detail || 'Error');
        } finally {
            setBusy(false);
        }
    };

    const toggleActive = async (l: LabRow) => {
        try {
            await api.patch(`/admin/labs/${l.id}`, { is_active: !l.is_active });
            onChanged();
        } catch { /* noop */ }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
            <div
                className="bg-[#0d1117] border border-white/[0.08] rounded-2xl w-full max-w-md max-h-[85vh] overflow-y-auto p-5 space-y-4"
                onClick={e => e.stopPropagation()}
            >
                <div className="flex items-center justify-between">
                    <h3 className="text-base font-bold text-white flex items-center gap-2">
                        <Building2 size={17} className="text-white/40" /> {t('lab.manage_labs')}
                    </h3>
                    <button onClick={onClose} className="text-white/30 hover:text-white"><X size={18} /></button>
                </div>

                {/* Importar desde la lista de bloqueos (etiqueta Laboratorio) */}
                {candidates.length > 0 && (
                    <div className="space-y-1.5">
                        <p className="text-[11px] font-semibold text-white/35 uppercase tracking-wider">
                            {t('lab.from_blocked')}
                        </p>
                        {candidates.map(c => (
                            <div
                                key={c.phone_number}
                                className="flex items-center gap-2 px-3 py-2 rounded-xl bg-blue-500/[0.06] border border-blue-500/15"
                            >
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm text-white/80 truncate">{c.name}</p>
                                    <p className="text-[11px] text-white/35">{c.phone_number}</p>
                                </div>
                                <button
                                    onClick={() =>
                                        setForm({ name: c.name, phone: c.phone_number, email: '' })
                                    }
                                    className="text-[11px] px-2.5 py-1 rounded-lg font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/25 hover:bg-blue-500/25 transition-colors"
                                >
                                    {t('lab.use_candidate')}
                                </button>
                            </div>
                        ))}
                        <p className="text-[10px] text-white/25">{t('lab.candidate_hint')}</p>
                    </div>
                )}

                <div className="space-y-2">
                    <input className={inputCls} placeholder={`${t('lab.name')} *`} value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} />
                    <div className="grid grid-cols-2 gap-2">
                        <input className={inputCls} placeholder={t('lab.email')} value={form.email} onChange={e => setForm(p => ({ ...p, email: e.target.value }))} />
                        <input className={inputCls} placeholder={t('lab.phone')} value={form.phone} onChange={e => setForm(p => ({ ...p, phone: e.target.value }))} />
                    </div>
                    <button
                        onClick={addLab}
                        disabled={busy || !form.name.trim()}
                        className="w-full px-4 py-2.5 rounded-xl text-sm font-semibold bg-white text-[#0a0e1a] hover:bg-white/90 transition-colors disabled:opacity-40"
                    >
                        {busy ? '…' : t('lab.add_lab')}
                    </button>
                    {msg && <p className="text-xs text-red-400">{msg}</p>}
                </div>

                <div className="space-y-1.5">
                    {labs.map(l => (
                        <div key={l.id} className="flex items-center gap-2 px-3 py-2 rounded-xl bg-white/[0.03] border border-white/[0.05]">
                            <div className="flex-1 min-w-0">
                                <p className={`text-sm font-medium truncate ${l.is_active ? 'text-white' : 'text-white/30 line-through'}`}>
                                    {l.name}
                                </p>
                                <p className="text-[11px] text-white/30 truncate">
                                    {[l.email, l.phone].filter(Boolean).join(' · ') || '—'}
                                </p>
                            </div>
                            <button
                                onClick={() => toggleActive(l)}
                                className={`text-[11px] px-2 py-1 rounded-lg font-medium border transition-colors ${
                                    l.is_active
                                        ? 'bg-white/[0.04] text-white/40 border-white/[0.08] hover:text-red-400'
                                        : 'bg-emerald-500/10 text-emerald-400 border-emerald-500/25'
                                }`}
                            >
                                {l.is_active ? t('lab.deactivate') : t('lab.activate')}
                            </button>
                        </div>
                    ))}
                    {labs.length === 0 && (
                        <p className="text-xs text-white/25 text-center py-3">{t('lab.no_labs')}</p>
                    )}
                </div>
            </div>
        </div>
    );
}
