import React, { useState, useEffect } from 'react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import {
    UserCheck, UserX, Clock, ShieldCheck, Mail,
    AlertTriangle, User, Users, Lock, Unlock, X, Building2, Stethoscope, BarChart3, MessageSquare, Plus, Phone, Save, Settings, ChevronDown, ChevronUp, Edit
} from 'lucide-react';

interface DayConfig { enabled: boolean; slots: { start: string; end: string }[]; }
interface WorkingHours {
  monday: DayConfig; tuesday: DayConfig; wednesday: DayConfig; thursday: DayConfig;
  friday: DayConfig; saturday: DayConfig; sunday: DayConfig;
}
const DAY_KEYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const;
const DAYS_HORARIOS = DAY_KEYS.map((key) => ({ key }));
function createDefaultWorkingHours(): WorkingHours {
  const wh = {} as WorkingHours;
  DAY_KEYS.forEach((key) => {
    wh[key] = {
      enabled: key !== 'sunday',
      slots: key !== 'sunday' ? [{ start: '09:00', end: '18:00' }] : [],
    };
  });
  return wh;
}
function parseWorkingHours(raw: unknown): WorkingHours {
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    const o = raw as Record<string, unknown>;
    const base = createDefaultWorkingHours();
    (Object.keys(base) as (keyof WorkingHours)[]).forEach(k => {
      if (o[k] && typeof o[k] === 'object' && !Array.isArray(o[k])) {
        const d = o[k] as { enabled?: boolean; slots?: { start?: string; end?: string }[] };
        base[k] = {
          enabled: d.enabled ?? base[k].enabled,
          slots: Array.isArray(d.slots) ? d.slots.map(s => ({ start: s?.start ?? '09:00', end: s?.end ?? '18:00' })) : base[k].slots,
        };
      }
    });
    return base;
  }
  return createDefaultWorkingHours();
}

interface StaffUser {
    id: string;
    email: string;
    role: string;
    status: 'pending' | 'active' | 'suspended';
    created_at: string;
    first_name?: string;
    last_name?: string;
}

const SPECIALTIES: { value: string; key: string }[] = [
  { value: 'Odontología General', key: 'specialty_general' },
  { value: 'Ortodoncia', key: 'specialty_orthodontics' },
  { value: 'Endodoncia', key: 'specialty_endodontics' },
  { value: 'Periodoncia', key: 'specialty_periodontics' },
  { value: 'Cirugía Oral', key: 'specialty_oral_surgery' },
  { value: 'Prótesis Dental', key: 'specialty_prosthodontics' },
  { value: 'Odontopediatría', key: 'specialty_pediatric' },
  { value: 'Implantología', key: 'specialty_implantology' },
  { value: 'Estética Dental', key: 'specialty_aesthetic' },
];

interface ProfessionalRow {
    id: number;
    tenant_id?: number;
    first_name?: string;
    last_name?: string;
    email?: string;
    specialty?: string;
    is_active?: boolean;
    working_hours?: unknown;
    phone_number?: string;
    registration_id?: string;
    google_calendar_id?: string;
}

const UserApprovalView: React.FC = () => {
    const { t } = useTranslation();
    const [users, setUsers] = useState<StaffUser[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [activeTab, setActiveTab] = useState<'requests' | 'staff'>('requests');
    const [selectedStaff, setSelectedStaff] = useState<StaffUser | null>(null);
    const [staffDetailLoading, setStaffDetailLoading] = useState(false);
    const [professionalRows, setProfessionalRows] = useState<ProfessionalRow[]>([]);
    const [clinics, setClinics] = useState<{ id: number; clinic_name: string }[]>([]);
    const [showLinkForm, setShowLinkForm] = useState(false);
    const [linkFormData, setLinkFormData] = useState({ tenant_id: null as number | null, phone: '', specialty: '', license_number: '' });
    const [linkFormSubmitting, setLinkFormSubmitting] = useState(false);
    const [editingProfessionalRow, setEditingProfessionalRow] = useState<ProfessionalRow | null>(null);
    const [staffForEditModal, setStaffForEditModal] = useState<StaffUser | null>(null);
    const [editFormData, setEditFormData] = useState<{
        name: string; email: string; phone: string; specialty: string; license_number: string;
        google_calendar_id: string; is_active: boolean; working_hours: WorkingHours;
    }>({ name: '', email: '', phone: '', specialty: '', license_number: '', google_calendar_id: '', is_active: true, working_hours: createDefaultWorkingHours() });
    const [editFormSubmitting, setEditFormSubmitting] = useState(false);
    const [expandedEditDays, setExpandedEditDays] = useState<string[]>([]);
    const [expandedAccordion, setExpandedAccordion] = useState<'pacientes' | 'uso' | 'mensajes' | null>(null);
    const [accordionData, setAccordionData] = useState<{
        analytics: Record<string, { metrics: { total_appointments: number; unique_patients: number; completion_rate: number; cancellation_rate: number; revenue: number; retention_rate: number }; tags: string[] }>;
        chatCountByTenant: Record<string, number>;
    }>({ analytics: {}, chatCountByTenant: {} });
    const [accordionLoading, setAccordionLoading] = useState<'pacientes' | 'uso' | 'mensajes' | null>(null);

    useEffect(() => {
        fetchAllUsers();
    }, []);

    useEffect(() => {
        api.get<{ id: number; clinic_name: string }[]>('/admin/chat/tenants').then((res) => {
            setClinics(res.data || []);
        }).catch(() => setClinics([]));
    }, []);

    useEffect(() => {
        if (!selectedStaff) {
            setProfessionalRows([]);
            return;
        }
        setStaffDetailLoading(true);
        api.get<ProfessionalRow[]>(`/admin/professionals/by-user/${selectedStaff.id}`)
            .then((res) => setProfessionalRows(res.data || []))
            .catch(() => setProfessionalRows([]))
            .finally(() => setStaffDetailLoading(false));
    }, [selectedStaff?.id]);

    const fetchAllUsers = async () => {
        try {
            setLoading(true);
            const response = await api.get('/admin/users');
            setUsers(response.data);
        } catch (err: any) {
            setError(t('approvals.error_load_users'));
        } finally {
            setLoading(false);
        }
    };

    const handleAction = async (userId: string, action: 'active' | 'suspended') => {
        try {
            await api.post(`/admin/users/${userId}/status`, { status: action });
            setUsers(prev => prev.map(u =>
                u.id === userId ? { ...u, status: action } : u
            ));
        } catch (err: any) {
            alert(t('alerts.error_process'));
        }
    };

    const closeStaffModal = () => {
        setSelectedStaff(null);
        setShowLinkForm(false);
        setLinkFormData({ tenant_id: null, phone: '', specialty: '', license_number: '' });
        setExpandedAccordion(null);
        setAccordionData({ analytics: {}, chatCountByTenant: {} });
    };

    const getMonthRange = () => {
        const now = new Date();
        const start = new Date(now.getFullYear(), now.getMonth(), 1);
        const end = new Date(now.getFullYear(), now.getMonth() + 1, 0, 23, 59, 59);
        return { start_date: start.toISOString().slice(0, 10), end_date: end.toISOString().slice(0, 10) };
    };

    const handleAccordionToggle = async (section: 'pacientes' | 'uso' | 'mensajes') => {
        const next = expandedAccordion === section ? null : section;
        setExpandedAccordion(next);
        if (!next) return;
        if (section === 'pacientes' || section === 'uso') {
            const alreadyLoaded = professionalRows.length > 0 && accordionData.analytics[`${professionalRows[0].id}-${professionalRows[0].tenant_id}`];
            if (alreadyLoaded) return;
            setAccordionLoading(section);
            const { start_date, end_date } = getMonthRange();
            const results: Record<string, { metrics: any; tags: string[] }> = {};
            for (const row of professionalRows) {
                try {
                    const res = await api.get(`/admin/professionals/${row.id}/analytics`, {
                        params: { tenant_id: row.tenant_id, start_date, end_date },
                    });
                    results[`${row.id}-${row.tenant_id}`] = { metrics: res.data.metrics, tags: res.data.tags || [] };
                } catch {
                    results[`${row.id}-${row.tenant_id}`] = { metrics: null, tags: [] };
                }
            }
            setAccordionData((prev) => ({ ...prev, analytics: { ...prev.analytics, ...results } }));
            setAccordionLoading(null);
        } else {
            if (accordionData.chatCountByTenant['loaded']) return;
            setAccordionLoading('mensajes');
            const counts: Record<string, number> = { loaded: 1 };
            for (const row of professionalRows) {
                const tid = row.tenant_id ?? 0;
                if (tid) {
                    try {
                        const res = await api.get('/admin/chat/sessions', { params: { tenant_id: tid } });
                        counts[String(tid)] = Array.isArray(res.data) ? res.data.length : 0;
                    } catch {
                        counts[String(tid)] = 0;
                    }
                }
            }
            setAccordionData((prev) => ({ ...prev, chatCountByTenant: { ...prev.chatCountByTenant, ...counts } }));
            setAccordionLoading(null);
        }
    };

    const handleConfigClick = async (user: StaffUser) => {
        try {
            const res = await api.get<ProfessionalRow[]>(`/admin/professionals/by-user/${user.id}`);
            const rows = res.data || [];
            if (rows.length === 0) {
                setSelectedStaff(user);
                setShowLinkForm(true);
                return;
            }
            const row = rows[0];
            setStaffForEditModal(user);
            setEditingProfessionalRow(row);
            const name = `${row.first_name || ''} ${row.last_name || ''}`.trim() || (user.first_name && user.last_name ? `${user.first_name} ${user.last_name}` : user.email);
            setEditFormData({
                name,
                email: row.email || user.email || '',
                phone: row.phone_number || '',
                specialty: row.specialty || '',
                license_number: row.registration_id || '',
                google_calendar_id: row.google_calendar_id ?? '',
                is_active: row.is_active ?? true,
                working_hours: parseWorkingHours(row.working_hours),
            });
            setExpandedEditDays([]);
        } catch {
            alert(t('alerts.error_load_pro'));
        }
    };

    const closeEditProfileModal = () => {
        setEditingProfessionalRow(null);
        setStaffForEditModal(null);
    };

    const toggleEditDayEnabled = (dayKey: keyof WorkingHours) => {
        setEditFormData(prev => ({
            ...prev,
            working_hours: {
                ...prev.working_hours,
                [dayKey]: {
                    ...prev.working_hours[dayKey],
                    enabled: !prev.working_hours[dayKey].enabled,
                    slots: !prev.working_hours[dayKey].enabled && prev.working_hours[dayKey].slots.length === 0
                        ? [{ start: '09:00', end: '18:00' }] : prev.working_hours[dayKey].slots,
                },
            },
        }));
    };
    const addEditTimeSlot = (dayKey: keyof WorkingHours) => {
        setEditFormData(prev => ({
            ...prev,
            working_hours: {
                ...prev.working_hours,
                [dayKey]: {
                    ...prev.working_hours[dayKey],
                    slots: [...prev.working_hours[dayKey].slots, { start: '09:00', end: '18:00' }],
                },
            },
        }));
    };
    const removeEditTimeSlot = (dayKey: keyof WorkingHours, index: number) => {
        setEditFormData(prev => ({
            ...prev,
            working_hours: {
                ...prev.working_hours,
                [dayKey]: {
                    ...prev.working_hours[dayKey],
                    slots: prev.working_hours[dayKey].slots.filter((_, i) => i !== index),
                },
            },
        }));
    };
    const updateEditTimeSlot = (dayKey: keyof WorkingHours, index: number, field: 'start' | 'end', value: string) => {
        setEditFormData(prev => ({
            ...prev,
            working_hours: {
                ...prev.working_hours,
                [dayKey]: {
                    ...prev.working_hours[dayKey],
                    slots: prev.working_hours[dayKey].slots.map((slot, i) =>
                        i === index ? { ...slot, [field]: value } : slot
                    ),
                },
            },
        }));
    };

    const handleEditProfileSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!editingProfessionalRow) return;
        setEditFormSubmitting(true);
        try {
            await api.put(`/admin/professionals/${editingProfessionalRow.id}`, {
                name: editFormData.name,
                email: editFormData.email,
                phone: editFormData.phone,
                specialty: editFormData.specialty || undefined,
                license_number: editFormData.license_number || undefined,
                google_calendar_id: editFormData.google_calendar_id?.trim() || undefined,
                is_active: editFormData.is_active,
                availability: {},
                working_hours: editFormData.working_hours,
            });
            closeEditProfileModal();
            if (selectedStaff && selectedStaff.id === staffForEditModal?.id) {
                const res = await api.get<ProfessionalRow[]>(`/admin/professionals/by-user/${selectedStaff.id}`);
                setProfessionalRows(res.data || []);
            }
        } catch (err: any) {
            alert(err?.response?.data?.detail || t('alerts.error_save'));
        } finally {
            setEditFormSubmitting(false);
        }
    };

    const handleLinkToSedeSubmit = async (e: React.FormEvent) => {
        if (!selectedStaff) return;
        const tenant_id = linkFormData.tenant_id ?? clinics[0]?.id;
        if (!tenant_id) {
            alert(t('alerts.select_sede'));
            return;
        }
        e.preventDefault();
        setLinkFormSubmitting(true);
        try {
            const name = `${selectedStaff.first_name || ''} ${selectedStaff.last_name || ''}`.trim() || 'Profesional';
            await api.post('/admin/professionals', {
                email: selectedStaff.email,
                tenant_id,
                name,
                phone: linkFormData.phone || undefined,
                specialty: linkFormData.specialty || undefined,
                license_number: linkFormData.license_number || undefined,
                is_active: true,
            });
            const res = await api.get<ProfessionalRow[]>(`/admin/professionals/by-user/${selectedStaff.id}`);
            setProfessionalRows(res.data || []);
            setShowLinkForm(false);
            setLinkFormData({ tenant_id: null, phone: '', specialty: '', license_number: '' });
        } catch (err: any) {
            const msg = err?.response?.data?.detail || err?.message || t('alerts.error_link_sede');
            alert(msg);
        } finally {
            setLinkFormSubmitting(false);
        }
    };

    // Filtrar solicitudes (solo pendientes)
    const requests = users.filter(u => u.status === 'pending');

    // Filtrar personal (activos y suspendidos, excluyendo al CEO actual si se desea, 
    // pero aquí mostramos todos menos el rol 'ceo' para evitar auto-bloqueo accidental)
    const staff = users.filter(u => u.status !== 'pending' && u.role !== 'ceo');

    if (loading) return <div className="p-6">{t('approvals.loading_staff')}</div>;

    return (
        <div className="view active flex flex-col h-full min-h-0 overflow-hidden p-6">
            <div className="flex justify-between items-center mb-6 shrink-0">
                <div>
                    <h1 className="view-title flex items-center gap-3">
                        <ShieldCheck color="var(--accent)" />
                        {t('approvals.page_title')}
                    </h1>
                    <p className="text-secondary">{t('approvals.page_subtitle')}</p>
                </div>
            </div>

            {/* TABS */}
            <div className="flex gap-4 mb-4 border-b border-gray-200 pb-px shrink-0">
                <button
                    onClick={() => setActiveTab('requests')}
                    className={`pb-3 px-6 font-semibold transition-all relative rounded-t-xl ${activeTab === 'requests'
                            ? 'text-medical-600'
                            : 'text-gray-500 hover:text-medical-700'
                        }`}
                >
                    <div className="flex items-center gap-2">
                        {t('approvals.requests')}
                        {requests.length > 0 && (
                            <span className="bg-danger text-white text-[10px] px-1.5 py-0.5 rounded-full shadow-sm">
                                {requests.length}
                            </span>
                        )}
                    </div>
                    {activeTab === 'requests' && (
                        <>
                            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-medical-600" />
                            <div className="absolute inset-0 bg-medical-400/10 blur-xl rounded-full -z-10 shadow-[0_0_20px_rgba(0,102,204,0.15)]" />
                        </>
                    )}
                </button>
                <button
                    onClick={() => setActiveTab('staff')}
                    className={`pb-3 px-6 font-semibold transition-all relative rounded-t-xl ${activeTab === 'staff'
                            ? 'text-medical-600'
                            : 'text-gray-500 hover:text-medical-700'
                        }`}
                >
                    {t('approvals.staff')}
                    {activeTab === 'staff' && (
                        <>
                            <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-medical-600" />
                            <div className="absolute inset-0 bg-medical-400/10 blur-xl rounded-full -z-10 shadow-[0_0_20px_rgba(0,102,204,0.15)]" />
                        </>
                    )}
                </button>
            </div>

            {error ? (
                <div className="glass p-6 text-center border-red-500/20 shrink-0">
                    <AlertTriangle color="#ff4d4d" size={48} className="mx-auto mb-4" />
                    <p className="text-red-400">{error}</p>
                </div>
            ) : (
                <div className="flex-1 min-h-0 overflow-y-auto pb-4">
                    <div className="grid gap-4">
                        {activeTab === 'requests' ? (
                            requests.length === 0 ? (
                                <div className="glass p-12 text-center">
                                    <Clock size={48} className="mx-auto mb-4 opacity-50" />
                                    <h3 className="text-xl font-medium mb-2">{t('approvals.no_requests')}</h3>
                                    <p className="text-secondary">{t('approvals.no_requests_processed')}</p>
                                </div>
                            ) : (
                                requests.map(user => (
                                    <UserCard key={user.id} user={user} onAction={handleAction} isRequest />
                                ))
                            )
                        ) : (
                            staff.length === 0 ? (
                                <div className="glass p-12 text-center">
                                    <Users size={48} className="mx-auto mb-4 opacity-50" />
                                    <h3 className="text-xl font-medium mb-2">{t('approvals.no_staff')}</h3>
                                    <p className="text-secondary">{t('approvals.no_staff_register')}</p>
                                </div>
                            ) : (
                                staff.map(user => (
                                    <UserCard
                                        key={user.id}
                                        user={user}
                                        onAction={handleAction}
                                        onCardClick={() => setSelectedStaff(user)}
                                        onConfigClick={() => handleConfigClick(user)}
                                    />
                                ))
                            )
                        )}
                    </div>
                </div>
            )}

            {/* Modal: detalle del profesional (optimizado mobile: full-height, scroll aislado, touch targets) */}
            {selectedStaff && (
                <div
                    className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
                    onClick={(e) => e.target === e.currentTarget && closeStaffModal()}
                >
                    <div className="bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl w-full max-w-6xl h-[92dvh] sm:h-auto sm:max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in duration-200">
                        <div className="flex items-center justify-between gap-3 px-4 py-4 sm:px-6 sm:py-5 border-b border-gray-100 shrink-0">
                            <h2 className="text-lg sm:text-xl font-bold text-gray-900 truncate min-w-0">
                                {selectedStaff.first_name || 'Sin nombre'} {selectedStaff.last_name || ''}
                            </h2>
                            <button type="button" onClick={closeStaffModal} className="shrink-0 p-2.5 min-w-[44px] min-h-[44px] rounded-xl text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors touch-manipulation" aria-label="Cerrar">
                                <X size={24} />
                            </button>
                        </div>
                        <div className="flex-1 overflow-y-auto min-h-0 px-4 py-4 sm:px-6 sm:py-5 space-y-6 overscroll-contain">
                            <div className="flex flex-col sm:flex-row sm:flex-wrap gap-4 items-stretch sm:items-start justify-between">
                                <div className="flex flex-wrap gap-3 items-start min-w-0">
                                    <div className="role-badge shrink-0" data-role={selectedStaff.role}>
                                        {selectedStaff.role.toUpperCase()}
                                    </div>
                                    <div className="min-w-0">
                                        <p className="text-sm text-gray-600 flex items-center gap-2 truncate">
                                            <Mail size={14} className="shrink-0" />
                                            <span className="truncate">{selectedStaff.email}</span>
                                        </p>
                                        <p className="text-xs text-gray-500 mt-1">
                                            {t('approvals.member_since')}: {new Date(selectedStaff.created_at).toLocaleDateString()}
                                        </p>
                                    </div>
                                </div>
                                <button
                                    type="button"
                                    onClick={() => {
                                        setShowLinkForm(true);
                                        setLinkFormData((p) => ({ ...p, tenant_id: clinics[0]?.id ?? null }));
                                    }}
                                    className="btn-vincular-sede min-h-[44px] touch-manipulation shrink-0"
                                >
                                    <Plus size={18} />
                                    {professionalRows.length > 0 ? t('approvals.link_to_another_sede') : t('approvals.link_to_sede')}
                                </button>
                            </div>

                            {showLinkForm && (
                                <form onSubmit={handleLinkToSedeSubmit} className="glass p-4 sm:p-5 rounded-xl space-y-4">
                                    <h3 className="text-sm font-semibold text-gray-800">{t('approvals.create_profile_sede')}</h3>
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-xs font-medium text-gray-600 mb-1">{t('approvals.choose_clinic')}</label>
                                            <select
                                                value={linkFormData.tenant_id ?? ''}
                                                onChange={(e) => setLinkFormData((p) => ({ ...p, tenant_id: e.target.value ? parseInt(e.target.value, 10) : null }))}
                                                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                                                required
                                            >
                                                <option value="">{t('approvals.choose_clinic')}</option>
                                                {clinics.map((c) => (
                                                    <option key={c.id} value={c.id}>{c.clinic_name}</option>
                                                ))}
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-600 mb-1 flex items-center gap-1"><Phone size={12} /> {t('approvals.phone')}</label>
                                            <input
                                                type="text"
                                                value={linkFormData.phone}
                                                onChange={(e) => setLinkFormData((p) => ({ ...p, phone: e.target.value }))}
                                                placeholder={t('approvals.phone_placeholder')}
                                                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-600 mb-1">{t('approvals.specialty')}</label>
                                            <select
                                                value={linkFormData.specialty}
                                                onChange={(e) => setLinkFormData((p) => ({ ...p, specialty: e.target.value }))}
                                                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                                            >
                                                <option value="">{t('approvals.select_optional')}</option>
                                                {SPECIALTIES.map((s) => (
                                                    <option key={s.value} value={s.value}>{t('approvals.' + s.key)}</option>
                                                ))}
                                            </select>
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-600 mb-1">{t('approvals.license_number')}</label>
                                            <input
                                                type="text"
                                                value={linkFormData.license_number}
                                                onChange={(e) => setLinkFormData((p) => ({ ...p, license_number: e.target.value }))}
                                                placeholder={t('approvals.optional')}
                                                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                                            />
                                        </div>
                                    </div>
                                    <div className="flex gap-2">
                                        <button type="submit" disabled={linkFormSubmitting} className="btn-icon-labeled success">
                                            <Save size={18} />
                                            {linkFormSubmitting ? t('common.saving') : t('approvals.save_and_link')}
                                        </button>
                                        <button type="button" onClick={() => { setShowLinkForm(false); setLinkFormData({ tenant_id: null, phone: '', specialty: '', license_number: '' }); }} className="btn-icon-labeled">
{t('common.cancel')}
                                            </button>
                                    </div>
                                </form>
                            )}

                            {staffDetailLoading ? (
                                <p className="text-gray-500">{t('approvals.loading_clinics')}</p>
                            ) : professionalRows.length > 0 ? (
                                <>
                                    <div>
                                        <h3 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                                            <Building2 size={16} />
                                            {t('approvals.assigned_locations')}
                                        </h3>
                                        <ul className="list-disc list-inside text-sm text-gray-600">
                                            {professionalRows.map((p) => (
                                                <li key={p.id}>
                                                    {clinics.find((c) => c.id === p.tenant_id)?.clinic_name || t('approvals.location_id').replace('{{id}}', String(p.tenant_id))}
                                                    {p.specialty && ` · ${p.specialty}`}
                                                </li>
                                            ))}
                                        </ul>
                                    </div>

                                    <div className="border border-gray-200 rounded-xl overflow-hidden">
                                        <button
                                            type="button"
                                            onClick={() => handleAccordionToggle('pacientes')}
                                            className="w-full flex items-center justify-between gap-2 p-4 min-h-[48px] text-left bg-gray-50 hover:bg-gray-100 active:bg-gray-200 transition-colors touch-manipulation"
                                        >
                                            <span className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                                                <Stethoscope size={16} />
                                                {t('approvals.their_patients')}
                                            </span>
                                            {expandedAccordion === 'pacientes' ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                                        </button>
                                        {expandedAccordion === 'pacientes' && (
                                            <div className="p-4 border-t border-gray-200 bg-white">
                                                {accordionLoading === 'pacientes' ? (
                                                    <p className="text-sm text-gray-500">{t('approvals.loading_metrics')}</p>
                                                ) : (
                                                    <div className="space-y-4">
                                                        {professionalRows.map((row) => {
                                                            const key = `${row.id}-${row.tenant_id}`;
                                                            const d = accordionData.analytics[key];
                                                            const m = d?.metrics;
                                                            const clinicName = clinics.find((c) => c.id === row.tenant_id)?.clinic_name || t('approvals.location_id').replace('{{id}}', String(row.tenant_id));
                                                            return (
                                                                <div key={key} className="text-sm">
                                                                    <p className="font-medium text-gray-700 mb-1">{clinicName}</p>
                                                                    {m ? (
                                                                        <ul className="text-gray-600 space-y-0.5">
                                                                            <li>{t('approvals.metrics_unique_patients')}: <strong>{m.unique_patients}</strong></li>
                                                                            <li>{t('approvals.metrics_total_appointments')}: <strong>{m.total_appointments}</strong></li>
                                                                            <li>{t('approvals.metrics_completion_rate')}: <strong>{m.completion_rate}%</strong></li>
                                                                            <li>{t('approvals.metrics_retention')}: <strong>{m.retention_rate}%</strong></li>
                                                                        </ul>
                                                                    ) : (
                                                                        <p className="text-gray-500">{t('approvals.no_data_period')}</p>
                                                                    )}
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    <div className="border border-gray-200 rounded-xl overflow-hidden">
                                        <button
                                            type="button"
                                            onClick={() => handleAccordionToggle('uso')}
                                            className="w-full flex items-center justify-between gap-2 p-4 min-h-[48px] text-left bg-gray-50 hover:bg-gray-100 active:bg-gray-200 transition-colors touch-manipulation"
                                        >
                                            <span className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                                                <BarChart3 size={16} />
                                                {t('approvals.platform_usage')}
                                            </span>
                                            {expandedAccordion === 'uso' ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                                        </button>
                                        {expandedAccordion === 'uso' && (
                                            <div className="p-4 border-t border-gray-200 bg-white">
                                                {accordionLoading === 'uso' ? (
                                                    <p className="text-sm text-gray-500">{t('approvals.loading_metrics')}</p>
                                                ) : (
                                                    <div className="space-y-4">
                                                        {professionalRows.map((row) => {
                                                            const key = `${row.id}-${row.tenant_id}`;
                                                            const d = accordionData.analytics[key];
                                                            const m = d?.metrics;
                                                            const clinicName = clinics.find((c) => c.id === row.tenant_id)?.clinic_name || t('approvals.location_id').replace('{{id}}', String(row.tenant_id));
                                                            return (
                                                                <div key={key} className="text-sm">
                                                                    <p className="font-medium text-gray-700 mb-1">{clinicName}</p>
                                                                    {m ? (
                                                                        <ul className="text-gray-600 space-y-0.5">
                                                                            <li>{t('approvals.completed_appointments')}: <strong>{m.total_appointments}</strong> ({t('approvals.completion')} {m.completion_rate}%)</li>
                                                                            <li>{t('approvals.cancellations')}: <strong>{m.cancellation_rate}%</strong></li>
                                                                            <li>{t('approvals.estimated_revenue')}: <strong>${typeof m.revenue === 'number' ? m.revenue.toLocaleString() : m.revenue}</strong></li>
                                                                            {d?.tags?.length ? <li>Tags: {d.tags.join(', ')}</li> : null}
                                                                        </ul>
                                                                    ) : (
                                                                        <p className="text-gray-500">{t('approvals.no_data_period')}</p>
                                                                    )}
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    <div className="border border-gray-200 rounded-xl overflow-hidden">
                                        <button
                                            type="button"
                                            onClick={() => handleAccordionToggle('mensajes')}
                                            className="w-full flex items-center justify-between gap-2 p-4 min-h-[48px] text-left bg-gray-50 hover:bg-gray-100 active:bg-gray-200 transition-colors touch-manipulation"
                                        >
                                            <span className="text-sm font-semibold text-gray-700 flex items-center gap-2">
                                                <MessageSquare size={16} />
                                                {t('approvals.messages_interactions')}
                                            </span>
                                            {expandedAccordion === 'mensajes' ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                                        </button>
                                        {expandedAccordion === 'mensajes' && (
                                            <div className="p-4 border-t border-gray-200 bg-white">
                                                {accordionLoading === 'mensajes' ? (
                                                    <p className="text-sm text-gray-500">{t('approvals.loading_short')}</p>
                                                ) : (
                                                    <div className="space-y-2 text-sm text-gray-600">
                                                        {professionalRows.map((row) => {
                                                            const tid = row.tenant_id ?? 0;
                                                            const count = tid ? (accordionData.chatCountByTenant[String(tid)] ?? '—') : '—';
                                                            const clinicName = clinics.find((c) => c.id === row.tenant_id)?.clinic_name || t('approvals.location_id').replace('{{id}}', String(row.tenant_id));
                                                            return (
                                                                <p key={row.id}>
                                                                    <strong>{clinicName}:</strong> {typeof count === 'number' ? t('approvals.conversations_count').replace('{{count}}', String(count)) : count}
                                                                </p>
                                                            );
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                    </div>
                                </>
                            ) : (
                                <div className="glass p-4 rounded-xl text-center text-gray-500 text-sm">
                                    {t('approvals.not_linked_hint')}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* Modal Editar Perfil (optimizado mobile: bottom-sheet en móvil, tres columnas en desktop) */}
            {editingProfessionalRow && (
                <div
                    className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
                    onClick={(e) => e.target === e.currentTarget && closeEditProfileModal()}
                >
                    <div className="bg-white rounded-t-3xl sm:rounded-3xl shadow-2xl w-full max-w-6xl h-[92dvh] sm:h-auto sm:max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in duration-200">
                        <div className="flex items-center justify-between gap-3 px-4 py-4 sm:px-6 sm:py-5 border-b border-gray-100 shrink-0">
                            <div className="flex items-center gap-3 sm:gap-4 min-w-0">
                                <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl bg-blue-50 flex items-center justify-center text-blue-600 shrink-0">
                                    <Edit size={22} className="sm:w-6 sm:h-6" />
                                </div>
                                <div className="min-w-0">
                                    <h2 className="text-base sm:text-xl font-bold text-gray-900 truncate">
                                        {t('approvals.edit_profile_title')}: {editFormData.name || (staffForEditModal?.first_name && staffForEditModal?.last_name ? `${staffForEditModal.first_name} ${staffForEditModal.last_name}` : staffForEditModal?.email) || t('approvals.professional_fallback')}
                                    </h2>
                                    <p className="text-xs sm:text-sm text-gray-500 mt-0.5 hidden sm:block">{t('approvals.complete_staff_info')}</p>
                                </div>
                            </div>
                            <button type="button" onClick={closeEditProfileModal} className="shrink-0 p-2.5 min-w-[44px] min-h-[44px] rounded-xl text-gray-400 hover:bg-gray-100 hover:text-gray-700 transition-colors touch-manipulation" aria-label="Cerrar">
                                <X size={24} />
                            </button>
                        </div>
                        <form onSubmit={handleEditProfileSubmit} className="flex-1 overflow-y-auto min-h-0 overscroll-contain">
                            <div className="p-4 sm:p-6 lg:p-8 grid grid-cols-1 lg:grid-cols-12 gap-6 lg:gap-8">
                                <div className="lg:col-span-4 space-y-5">
                                    <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest">{t('approvals.main_data')}</h3>
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{t('approvals.clinic_label')}</label>
                                        <div className="px-4 py-3 bg-gray-50 border border-gray-200 rounded-2xl text-sm font-medium text-gray-800">
                                            {clinics.find((c) => c.id === editingProfessionalRow.tenant_id)?.clinic_name || t('approvals.location_id').replace('{{id}}', String(editingProfessionalRow.tenant_id ?? '—'))}
                                        </div>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{t('approvals.full_name_required')}</label>
                                        <input type="text" value={editFormData.name} onChange={(e) => setEditFormData((p) => ({ ...p, name: e.target.value }))} className="edit-profile-input" required />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{t('approvals.specialty')}</label>
                                        <select value={editFormData.specialty} onChange={(e) => setEditFormData((p) => ({ ...p, specialty: e.target.value }))} className="edit-profile-input">
                                            <option value="">{t('approvals.select')}</option>
                                            {SPECIALTIES.map((s) => <option key={s.value} value={s.value}>{t('approvals.' + s.key)}</option>)}
                                        </select>
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{t('approvals.license_number')}</label>
                                        <input type="text" value={editFormData.license_number} onChange={(e) => setEditFormData((p) => ({ ...p, license_number: e.target.value }))} className="edit-profile-input" placeholder={t('approvals.license_placeholder')} />
                                    </div>
                                </div>
                                <div className="lg:col-span-4 space-y-5">
                                    <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest">{t('approvals.contact_status')}</h3>
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{t('approvals.email')}</label>
                                        <input type="email" value={editFormData.email} onChange={(e) => setEditFormData((p) => ({ ...p, email: e.target.value }))} className="edit-profile-input" />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{t('approvals.phone')}</label>
                                        <input type="text" value={editFormData.phone} onChange={(e) => setEditFormData((p) => ({ ...p, phone: e.target.value }))} className="edit-profile-input" placeholder={t('approvals.phone_edit_placeholder')} />
                                    </div>
                                    <div>
                                        <label className="block text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">{t('approvals.google_calendar_id')}</label>
                                        <input type="text" value={editFormData.google_calendar_id} onChange={(e) => setEditFormData((p) => ({ ...p, google_calendar_id: e.target.value }))} className="edit-profile-input" placeholder={t('approvals.google_calendar_id_placeholder')} />
                                    </div>
                                    <label className="flex items-center gap-3 cursor-pointer mt-4">
                                        <input type="checkbox" checked={editFormData.is_active} onChange={(e) => setEditFormData((p) => ({ ...p, is_active: e.target.checked }))} className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
                                        <span className="text-sm font-medium text-gray-700">{t('approvals.active')}</span>
                                    </label>
                                </div>
                                <div className="lg:col-span-4 space-y-4">
                                    <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest flex items-center gap-2"><Clock size={14} /> {t('approvals.availability')}</h3>
                                    <p className="text-xs text-gray-500">{t('approvals.availability_help')}</p>
                                    <div className="space-y-2">
                                        {DAYS_HORARIOS.map((day) => {
                                            const dayKey = day.key;
                                            const config = editFormData.working_hours[dayKey];
                                            const isExpanded = expandedEditDays.includes(dayKey);
                                            return (
                                                <div key={day.key} className="rounded-2xl border border-gray-200 overflow-hidden bg-white">
                                                    <div className="flex items-center justify-between px-4 py-3 min-h-[48px] hover:bg-gray-50/80 transition-colors">
                                                        <label className="flex items-center gap-3 cursor-pointer flex-1 touch-manipulation py-1">
                                                            <input type="checkbox" checked={config.enabled} onChange={() => toggleEditDayEnabled(dayKey)} className="w-4 h-4 rounded border-gray-300 text-blue-600" />
                                                            <span className="text-sm font-medium text-gray-800">{t('approvals.day_' + day.key)}</span>
                                                        </label>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-xs text-gray-500 tabular-nums">{config.slots.length} {t('approvals.slots')}</span>
                                                            <button type="button" onClick={() => setExpandedEditDays((prev) => isExpanded ? prev.filter((d) => d !== dayKey) : [...prev, dayKey])} className="p-2.5 min-w-[44px] min-h-[44px] rounded-lg hover:bg-gray-200 text-gray-500 touch-manipulation flex items-center justify-center">
                                                                <ChevronDown size={18} className={isExpanded ? 'rotate-180' : ''} />
                                                            </button>
                                                        </div>
                                                    </div>
                                                    {isExpanded && config.enabled && (
                                                        <div className="px-4 pb-4 pt-1 space-y-3 bg-gray-50/50 border-t border-gray-100">
                                                            {config.slots.map((slot, idx) => (
                                                                <div key={idx} className="flex items-center gap-3">
                                                                    <input type="time" value={slot.start} onChange={(e) => updateEditTimeSlot(dayKey, idx, 'start', e.target.value)} className="edit-profile-input w-28" />
                                                                    <span className="text-gray-400">–</span>
                                                                    <input type="time" value={slot.end} onChange={(e) => updateEditTimeSlot(dayKey, idx, 'end', e.target.value)} className="edit-profile-input w-28" />
                                                                    <button type="button" onClick={() => removeEditTimeSlot(dayKey, idx)} className="text-sm text-red-500 hover:text-red-700">{t('approvals.remove')}</button>
                                                                </div>
                                                            ))}
                                                            <button type="button" onClick={() => addEditTimeSlot(dayKey)} className="text-sm font-medium text-blue-600 hover:text-blue-800">+ {t('approvals.add_schedule')}</button>
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                    </div>
                                </div>
                            </div>
                            <div className="px-4 sm:px-6 lg:px-8 py-4 sm:py-5 border-t border-gray-100 bg-gray-50/50 flex flex-col-reverse sm:flex-row gap-3 justify-end rounded-b-3xl shrink-0">
                                <button type="button" onClick={closeEditProfileModal} className="w-full sm:w-auto min-h-[44px] px-5 py-2.5 rounded-xl border border-gray-300 bg-white text-gray-700 font-medium hover:bg-gray-50 touch-manipulation">
{t('common.cancel')}
                                            </button>
                                <button type="submit" disabled={editFormSubmitting} className="w-full sm:w-auto min-h-[44px] px-5 py-2.5 rounded-xl bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 touch-manipulation">
                                    {editFormSubmitting ? t('common.saving') : t('common.save_changes')}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            <style>{`
        .glass {
          background: white;
          border: 1px solid var(--white-300);
          border-radius: 16px;
          box-shadow: var(--shadow-card);
          transition: all 0.3s ease;
        }
        .glass:hover {
          box-shadow: var(--shadow-soft);
          border-color: var(--medical-300);
        }
        
        .role-badge {
          padding: 4px 10px;
          border-radius: 8px;
          font-size: 0.7rem;
          font-weight: 700;
          background: #f8f9fa;
          letter-spacing: 0.5px;
          border: 1px solid rgba(0,0,0,0.05);
        }
        .role-badge[data-role='ceo'] { color: #856404; background: #fff3cd; border-color: #ffeeba; }
        .role-badge[data-role='professional'] { color: #004085; background: #cce5ff; border-color: #b8daff; }
        .role-badge[data-role='secretary'] { color: #155724; background: #d4edda; border-color: #c3e6cb; }

        .btn-icon-labeled {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 8px 16px;
          border-radius: 10px;
          font-size: 0.9rem;
          font-weight: 500;
          border: 1px solid #dee2e6;
          background: #fff;
          transition: all 0.3s;
          color: #495057;
        }
        .btn-icon-labeled:hover {
          background: #f8f9fa;
          border-color: #adb5bd;
          transform: translateY(-1px);
        }
        .btn-icon-labeled.success {
          border-color: #c3e6cb;
          background: #d4edda;
          color: #155724;
        }
        .btn-icon-labeled.success:hover {
          background: #c3e6cb;
          border-color: #155724;
        }
        .btn-icon-labeled.danger {
          border-color: #f5c6cb;
          background: #f8d7da;
          color: #721c24;
        }
        .btn-icon-labeled.danger:hover {
          background: #f5c6cb;
          border-color: #721c24;
        }
        .btn-icon-labeled.warning {
          border-color: #ffeeba;
          background: #fff3cd;
          color: #856404;
        }
        .btn-icon-labeled.warning:hover {
          background: #ffeeba;
          border-color: #856404;
        }
        .btn-vincular-sede {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          padding: 10px 20px;
          border-radius: 10px;
          font-size: 0.9rem;
          font-weight: 600;
          border: none;
          background: #2563eb;
          color: white;
          cursor: pointer;
          transition: all 0.2s;
          box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        .btn-vincular-sede:hover {
          background: #1d4ed8;
          transform: translateY(-1px);
          box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        }
        .btn-gear {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 44px;
          height: 44px;
          border-radius: 50%;
          border: 1px solid #dee2e6;
          background: #fff;
          color: #495057;
          cursor: pointer;
          transition: all 0.2s;
          flex-shrink: 0;
        }
        .btn-gear:hover {
          background: #f8f9fa;
          border-color: #adb5bd;
          color: #2563eb;
          transform: translateY(-1px);
        }
        .edit-profile-input {
          width: 100%;
          padding: 12px 16px;
          border: 1px solid #e5e7eb;
          border-radius: 16px;
          font-size: 0.875rem;
          color: #1f2937;
          background: #fff;
          transition: border-color 0.2s, box-shadow 0.2s;
        }
        .edit-profile-input:focus {
          outline: none;
          border-color: #3b82f6;
          box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
        }
        .animate-fadeIn {
          animation: fadeIn 0.4s ease-out;
        }
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
        </div>
    );
};

interface UserCardProps {
    user: StaffUser;
    onAction: (id: string, action: 'active' | 'suspended') => void;
    isRequest?: boolean;
    onCardClick?: () => void;
    onConfigClick?: () => void;
}

const UserCard: React.FC<UserCardProps> = ({ user, onAction, isRequest, onCardClick, onConfigClick }) => {
    const { t } = useTranslation();
    return (
    <div className="glass p-5 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 animate-fadeIn">
        <div
            className={`flex items-start sm:items-center gap-4 flex-1 min-w-0 ${onCardClick ? 'cursor-pointer hover:opacity-90' : ''}`}
            onClick={onCardClick}
            role={onCardClick ? 'button' : undefined}
        >
            <div className={`role-badge shrink-0 ${user.status === 'suspended' ? 'opacity-40' : ''}`} data-role={user.role}>
                {user.role.toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
                <div className={`font-medium flex items-center gap-2 flex-wrap ${user.status === 'suspended' ? 'text-secondary line-through' : ''}`}>
                    <User size={14} className="opacity-50 shrink-0" />
                    <span className="truncate">{user.first_name || t('approvals.no_name')} {user.last_name || ''}</span>
                    {user.status === 'suspended' && (
                        <span className="text-[10px] bg-red-500/20 text-red-400 px-1.5 py-0.5 rounded-full uppercase shrink-0">{t('approvals.suspended')}</span>
                    )}
                </div>
                <div className="text-sm flex items-center gap-2 opacity-70 truncate">
                    <Mail size={12} className="shrink-0" />
                    <span className="truncate">{user.email}</span>
                </div>
                <div className="text-xs text-secondary mt-1">
                    {isRequest ? t('approvals.requested_at') + ': ' : t('approvals.member_since') + ': '} {new Date(user.created_at).toLocaleDateString()}
                </div>
            </div>
        </div>

        <div className="flex items-center justify-end sm:justify-start gap-2 shrink-0 flex-wrap" onClick={(e) => e.stopPropagation()}>
            {!isRequest && onConfigClick && (
                <button
                    type="button"
                    onClick={onConfigClick}
                    className="btn-gear"
                    title={t('approvals.edit_profile_schedules')}
                    aria-label={t('approvals.edit_profile_schedules')}
                >
                    <Settings size={20} />
                </button>
            )}
            {isRequest ? (
                <>
                    <button onClick={() => onAction(user.id, 'active')} className="btn-icon-labeled success">
                        <UserCheck size={18} /> {t('approvals.approve')}
                    </button>
                    <button onClick={() => onAction(user.id, 'suspended')} className="btn-icon-labeled danger">
                        <UserX size={18} /> {t('approvals.reject')}
                    </button>
                </>
            ) : (
                user.status === 'active' ? (
                    <button onClick={() => onAction(user.id, 'suspended')} className="btn-icon-labeled warning">
                        <Lock size={18} /> {t('approvals.suspend')}
                    </button>
                ) : (
                    <button onClick={() => onAction(user.id, 'active')} className="btn-icon-labeled success">
                        <Unlock size={18} /> {t('approvals.reactivate')}
                    </button>
                )
            )}
        </div>
    </div>
    );
};

export default UserApprovalView;
