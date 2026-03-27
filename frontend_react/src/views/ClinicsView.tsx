import { useState, useEffect } from 'react';
import { Building2, Plus, Edit, Trash2, Phone, Loader2, AlertCircle, CheckCircle2, Calendar, Clock, MapPin, HelpCircle, ChevronDown, X, DollarSign } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';

/* ── Types ── */
interface DayConfig { enabled: boolean; slots: { start: string; end: string }[]; location?: string; address?: string; maps_url?: string; }
interface WorkingHours {
  monday: DayConfig; tuesday: DayConfig; wednesday: DayConfig; thursday: DayConfig;
  friday: DayConfig; saturday: DayConfig; sunday: DayConfig;
}
const DAY_KEYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'] as const;

function createDefaultWorkingHours(): WorkingHours {
  const wh = {} as WorkingHours;
  DAY_KEYS.forEach((key) => {
    wh[key] = { enabled: key !== 'sunday' && key !== 'saturday', slots: (key !== 'sunday' && key !== 'saturday') ? [{ start: '09:00', end: '18:00' }] : [] };
  });
  return wh;
}
function parseWorkingHours(raw: unknown): WorkingHours {
  // asyncpg puede devolver JSONB como string; parsear si es necesario
  let parsed = raw;
  if (typeof parsed === 'string') {
    try { parsed = JSON.parse(parsed); } catch { return createDefaultWorkingHours(); }
  }
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    const o = parsed as Record<string, unknown>;
    const base = createDefaultWorkingHours();
    (Object.keys(base) as (keyof WorkingHours)[]).forEach(k => {
      if (o[k] && typeof o[k] === 'object' && !Array.isArray(o[k])) {
        const d = o[k] as { enabled?: boolean; slots?: { start?: string; end?: string }[]; location?: string; address?: string; maps_url?: string };
        base[k] = {
          enabled: d.enabled ?? base[k].enabled,
          slots: Array.isArray(d.slots) ? d.slots.map(s => ({ start: s?.start ?? '09:00', end: s?.end ?? '18:00' })) : base[k].slots,
          location: d.location ?? '',
          address: d.address ?? '',
          maps_url: d.maps_url ?? '',
        };
      }
    });
    return base;
  }
  return createDefaultWorkingHours();
}

export interface Clinica {
    id: number;
    clinic_name: string;
    bot_phone_number: string;
    address?: string;
    google_maps_url?: string;
    working_hours?: unknown;
    consultation_price?: number | null;
    bank_cbu?: string;
    bank_alias?: string;
    bank_holder_name?: string;
    derivation_email?: string;
    max_chairs?: number;
    config?: { calendar_provider?: 'local' | 'google' };
    created_at: string;
    updated_at?: string;
}

interface FAQ {
    id?: number;
    tenant_id?: number;
    category: string;
    question: string;
    answer: string;
    sort_order: number;
}

const CALENDAR_PROVIDER_OPTIONS = (t: (k: string) => string) => [
    { value: 'local' as const, label: t('clinics.calendar_local') },
    { value: 'google' as const, label: t('clinics.calendar_google') },
];

export default function ClinicsView() {
    const { t } = useTranslation();
    const [clinicas, setClinicas] = useState<Clinica[]>([]);
    const [loading, setLoading] = useState(true);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingClinica, setEditingClinica] = useState<Clinica | null>(null);
    const [formData, setFormData] = useState({
        clinic_name: '',
        bot_phone_number: '',
        calendar_provider: 'local' as 'local' | 'google',
        address: '',
        google_maps_url: '',
        consultation_price: '' as string,
        bank_cbu: '',
        bank_alias: '',
        bank_holder_name: '',
        derivation_email: '',
        max_chairs: '2',
        working_hours: createDefaultWorkingHours(),
    });
    const [expandedDays, setExpandedDays] = useState<string[]>([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // FAQ state
    const [faqModalOpen, setFaqModalOpen] = useState(false);
    const [faqClinicId, setFaqClinicId] = useState<number | null>(null);
    const [faqClinicName, setFaqClinicName] = useState('');
    const [faqs, setFaqs] = useState<FAQ[]>([]);
    const [faqLoading, setFaqLoading] = useState(false);
    const [faqEditing, setFaqEditing] = useState<FAQ | null>(null);
    const [faqForm, setFaqForm] = useState<FAQ>({ category: 'General', question: '', answer: '', sort_order: 0 });
    const [faqSaving, setFaqSaving] = useState(false);

    useEffect(() => { fetchClinicas(); }, []);

    const fetchClinicas = async () => {
        try {
            setLoading(true);
            const resp = await api.get('/admin/tenants');
            setClinicas(resp.data);
        } catch (err) {
            console.error('Error cargando clínicas:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleOpenModal = (clinica: Clinica | null = null) => {
        if (clinica) {
            setEditingClinica(clinica);
            setFormData({
                clinic_name: clinica.clinic_name,
                bot_phone_number: clinica.bot_phone_number,
                calendar_provider: (clinica.config?.calendar_provider === 'google' ? 'google' : 'local'),
                address: clinica.address || '',
                google_maps_url: clinica.google_maps_url || '',
                consultation_price: clinica.consultation_price != null ? String(clinica.consultation_price) : '',
                bank_cbu: clinica.bank_cbu || '',
                bank_alias: clinica.bank_alias || '',
                bank_holder_name: clinica.bank_holder_name || '',
                derivation_email: clinica.derivation_email || '',
                max_chairs: clinica.max_chairs != null ? String(clinica.max_chairs) : '2',
                working_hours: parseWorkingHours(clinica.working_hours),
            });
        } else {
            setEditingClinica(null);
            setFormData({ clinic_name: '', bot_phone_number: '', calendar_provider: 'local', address: '', google_maps_url: '', consultation_price: '', bank_cbu: '', bank_alias: '', bank_holder_name: '', derivation_email: '', max_chairs: '2', working_hours: createDefaultWorkingHours() });
        }
        setExpandedDays([]);
        setError(null);
        setIsModalOpen(true);
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError(null);
        try {
            const payload = {
                clinic_name: formData.clinic_name,
                bot_phone_number: formData.bot_phone_number,
                calendar_provider: formData.calendar_provider,
                address: formData.address || null,
                google_maps_url: formData.google_maps_url || null,
                consultation_price: formData.consultation_price ? parseFloat(formData.consultation_price) : null,
                bank_cbu: formData.bank_cbu || null,
                bank_alias: formData.bank_alias || null,
                bank_holder_name: formData.bank_holder_name || null,
                derivation_email: formData.derivation_email || null,
                max_chairs: formData.max_chairs ? parseInt(formData.max_chairs) : 2,
                working_hours: formData.working_hours,
            };
            if (editingClinica) {
                await api.put(`/admin/tenants/${editingClinica.id}`, payload);
                setSuccess(t('clinics.toast_updated'));
            } else {
                await api.post('/admin/tenants', payload);
                setSuccess(t('clinics.toast_created'));
            }
            await fetchClinicas();
            setIsModalOpen(false);
            setTimeout(() => setSuccess(null), 3000);
        } catch (err: any) {
            setError(err.response?.data?.detail || t('clinics.toast_error'));
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async (id: number) => {
        if (!window.confirm(t('alerts.confirm_delete_clinic'))) return;
        try {
            await api.delete(`/admin/tenants/${id}`);
            fetchClinicas();
        } catch (err) {
            console.error('Error eliminando clínica:', err);
        }
    };

    /* ── Working Hours Handlers ── */
    const toggleDayEnabled = (dayKey: keyof WorkingHours) => {
        setFormData(prev => ({
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
    const addTimeSlot = (dayKey: keyof WorkingHours) => {
        setFormData(prev => ({
            ...prev,
            working_hours: {
                ...prev.working_hours,
                [dayKey]: { ...prev.working_hours[dayKey], slots: [...prev.working_hours[dayKey].slots, { start: '09:00', end: '18:00' }] },
            },
        }));
    };
    const removeTimeSlot = (dayKey: keyof WorkingHours, index: number) => {
        setFormData(prev => ({
            ...prev,
            working_hours: {
                ...prev.working_hours,
                [dayKey]: { ...prev.working_hours[dayKey], slots: prev.working_hours[dayKey].slots.filter((_, i) => i !== index) },
            },
        }));
    };
    const updateTimeSlot = (dayKey: keyof WorkingHours, index: number, field: 'start' | 'end', value: string) => {
        setFormData(prev => ({
            ...prev,
            working_hours: {
                ...prev.working_hours,
                [dayKey]: {
                    ...prev.working_hours[dayKey],
                    slots: prev.working_hours[dayKey].slots.map((slot, i) => i === index ? { ...slot, [field]: value } : slot),
                },
            },
        }));
    };

    const updateDayField = (dayKey: keyof WorkingHours, field: 'location' | 'address' | 'maps_url', value: string) => {
        setFormData(prev => ({
            ...prev,
            working_hours: {
                ...prev.working_hours,
                [dayKey]: { ...prev.working_hours[dayKey], [field]: value },
            },
        }));
    };

    /* ── FAQ Handlers ── */
    const openFaqModal = async (clinica: Clinica) => {
        setFaqClinicId(clinica.id);
        setFaqClinicName(clinica.clinic_name);
        setFaqEditing(null);
        setFaqForm({ category: 'General', question: '', answer: '', sort_order: 0 });
        setFaqModalOpen(true);
        await fetchFaqs(clinica.id);
    };

    const fetchFaqs = async (tenantId: number) => {
        setFaqLoading(true);
        try {
            const resp = await api.get(`/admin/tenants/${tenantId}/faqs`);
            setFaqs(resp.data);
        } catch (err) {
            console.error('Error cargando FAQs:', err);
        } finally {
            setFaqLoading(false);
        }
    };

    const handleFaqSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!faqClinicId) return;
        setFaqSaving(true);
        try {
            if (faqEditing?.id) {
                await api.put(`/admin/faqs/${faqEditing.id}`, faqForm);
            } else {
                await api.post(`/admin/tenants/${faqClinicId}/faqs`, faqForm);
            }
            setFaqEditing(null);
            setFaqForm({ category: 'General', question: '', answer: '', sort_order: 0 });
            await fetchFaqs(faqClinicId);
        } catch (err: any) {
            console.error('Error guardando FAQ:', err);
        } finally {
            setFaqSaving(false);
        }
    };

    const handleFaqEdit = (faq: FAQ) => {
        setFaqEditing(faq);
        setFaqForm({ category: faq.category, question: faq.question, answer: faq.answer, sort_order: faq.sort_order });
    };

    const handleFaqDelete = async (faqId: number) => {
        if (!window.confirm(t('clinics.faq_confirm_delete'))) return;
        try {
            await api.delete(`/admin/faqs/${faqId}`);
            if (faqClinicId) await fetchFaqs(faqClinicId);
        } catch (err) {
            console.error('Error eliminando FAQ:', err);
        }
    };

    const calendarProviderLabel = (cp: string) =>
        CALENDAR_PROVIDER_OPTIONS(t).find(o => o.value === cp)?.label ?? cp;

    if (loading) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-3 min-h-0 overflow-y-auto">
                <Loader2 className="animate-spin text-blue-400" size={32} />
                <p className="text-white/60 font-medium">{t('common.loading')}</p>
            </div>
        );
    }

    return (
        <div className="p-4 sm:p-6 max-w-7xl mx-auto space-y-6 min-h-0 overflow-y-auto">
            <PageHeader
                title={t('clinics.title')}
                subtitle={t('clinics.subtitle')}
                icon={<Building2 size={22} />}
                action={
                    <button
                        onClick={() => handleOpenModal()}
                        className="flex items-center justify-center gap-2 bg-white text-[#0a0e1a] px-4 py-2.5 rounded-xl hover:bg-white/90 transition-all font-medium text-sm sm:text-base active:scale-[0.98]"
                    >
                        <Plus size={20} /> {t('clinics.new_clinic')}
                    </button>
                }
            />

            {success && (
                <div className="bg-green-500/10 text-green-400 p-3 rounded-lg flex items-center gap-2 border border-green-500/20 animate-fade-in">
                    <CheckCircle2 size={18} /> {success}
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {clinicas.map((clinica) => (
                    <div
                        key={clinica.id}
                        className="bg-white/[0.03] rounded-xl border border-white/[0.06] overflow-hidden hover:border-white/[0.12] transition-all group"
                    >
                        <div className="p-5 space-y-4">
                            <div className="flex justify-between items-start">
                                <div className="bg-blue-500/10 p-3 rounded-lg text-blue-400 group-hover:bg-blue-500 group-hover:text-white transition-colors">
                                    <Building2 size={24} />
                                </div>
                                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                        onClick={() => openFaqModal(clinica)}
                                        className="p-2 text-amber-400 hover:bg-amber-500/10 rounded-lg transition-colors"
                                        title={t('clinics.faq_manage')}
                                    >
                                        <HelpCircle size={18} />
                                    </button>
                                    <button
                                        onClick={() => handleOpenModal(clinica)}
                                        className="p-2 text-blue-400 hover:bg-blue-500/10 rounded-lg transition-colors"
                                    >
                                        <Edit size={18} />
                                    </button>
                                    <button
                                        onClick={() => handleDelete(clinica.id)}
                                        className="p-2 text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                                    >
                                        <Trash2 size={18} />
                                    </button>
                                </div>
                            </div>

                            <div>
                                <h3 className="font-bold text-white text-lg">{clinica.clinic_name}</h3>
                                <div className="flex items-center gap-2 text-blue-400 mt-2 text-sm">
                                    <Phone size={14} className="shrink-0" />
                                    <span className="font-mono">{clinica.bot_phone_number}</span>
                                </div>
                                {clinica.address && (
                                    <div className="flex items-center gap-2 text-white/40 mt-1 text-xs">
                                        <MapPin size={12} className="shrink-0" />
                                        <span>{clinica.address}</span>
                                    </div>
                                )}
                                <div className="flex items-center gap-2 text-white/40 mt-1 text-xs">
                                    <Calendar size={12} className="shrink-0" />
                                    <span>{calendarProviderLabel(clinica.config?.calendar_provider || 'local')}</span>
                                </div>
                            </div>

                            <div className="pt-4 border-t border-white/[0.06] flex justify-between items-center text-xs text-white/30">
                                <span>ID: {clinica.id}</span>
                                <span>{t('common.since')}: {new Date(clinica.created_at).toLocaleDateString()}</span>
                            </div>
                        </div>
                    </div>
                ))}
            </div>

            {/* ── Modal Editar/Crear Clínica ── */}
            {isModalOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-2xl animate-scale-in max-h-[90vh] flex flex-col">
                        <div className="p-4 sm:p-6 border-b border-white/[0.06] shrink-0 flex justify-between items-center">
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                {editingClinica ? <Edit className="text-blue-400" /> : <Plus className="text-blue-400" />}
                                {editingClinica ? t('clinics.edit_clinic') : t('clinics.create_clinic')}
                            </h2>
                            <button onClick={() => setIsModalOpen(false)} className="p-2 hover:bg-white/[0.04] rounded-lg text-white/40"><X size={20} /></button>
                        </div>

                        <form onSubmit={handleSubmit} className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-5">
                            {error && (
                                <div className="bg-red-500/10 text-red-400 p-3 rounded-lg flex items-center gap-2 text-sm border border-red-500/20">
                                    <AlertCircle size={16} /> {error}
                                </div>
                            )}

                            {/* Nombre y teléfono */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                                <div className="space-y-1">
                                    <label className="text-sm font-semibold text-white/60">{t('clinics.clinic_name_label')}</label>
                                    <input required type="text" placeholder={t('clinics.clinic_name_placeholder')}
                                        className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none"
                                        value={formData.clinic_name} onChange={(e) => { const v = e.target.value; setFormData(prev => ({ ...prev, clinic_name: v })); }} />
                                </div>
                                <div className="space-y-1">
                                    <label className="text-sm font-semibold text-white/60">{t('clinics.bot_phone_label')}</label>
                                    <input required type="text" placeholder={t('clinics.bot_phone_placeholder')}
                                        className="w-full px-4 py-2 border rounded-lg font-mono focus:ring-2 focus:ring-medical-500 outline-none"
                                        value={formData.bot_phone_number} onChange={(e) => { const v = e.target.value; setFormData(prev => ({ ...prev, bot_phone_number: v })); }} />
                                </div>
                            </div>

                            {/* Dirección y Maps */}
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60 flex items-center gap-2"><MapPin size={14} /> {t('clinics.address_label')}</label>
                                <input type="text" placeholder={t('clinics.address_placeholder')}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none"
                                    value={formData.address} onChange={(e) => { const v = e.target.value; setFormData(prev => ({ ...prev, address: v })); }} />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('clinics.maps_url_label')}</label>
                                <input type="url" placeholder={t('clinics.maps_url_placeholder')}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                    value={formData.google_maps_url} onChange={(e) => { const v = e.target.value; setFormData(prev => ({ ...prev, google_maps_url: v })); }} />
                            </div>

                            {/* Valor de consulta */}
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('clinics.consultation_price_label')}</label>
                                <input type="number" step="0.01" min="0" placeholder={t('clinics.consultation_price_placeholder')}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none"
                                    value={formData.consultation_price} onChange={(e) => { const v = e.target.value; setFormData(prev => ({ ...prev, consultation_price: v })); }} />
                                <p className="text-xs text-white/30">{t('clinics.consultation_price_help')}</p>
                            </div>

                            {/* Sillones / Chairs */}
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">Sillones disponibles</label>
                                <input type="number" min="1" max="20" placeholder="2"
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none"
                                    value={formData.max_chairs} onChange={(e) => { const v = e.target.value; setFormData(prev => ({ ...prev, max_chairs: v })); }} />
                                <p className="text-xs text-white/30">Cantidad de sillones en la clinica. Limita cuantos turnos pueden ocurrir al mismo tiempo.</p>
                            </div>

                            {/* Datos Bancarios */}
                            <div className="space-y-3 border-t pt-4 mt-4">
                                <h3 className="text-sm font-bold text-white/60 flex items-center gap-2"><DollarSign size={14} /> {t('clinics.bank_section')}</h3>
                                <p className="text-xs text-white/30">{t('clinics.bank_help')}</p>
                                <div className="space-y-2">
                                    <div className="space-y-1">
                                        <label className="text-xs font-medium text-blue-400">{t('clinics.bank_cbu')}</label>
                                        <input type="text" placeholder="0000003100010000000001"
                                            className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm font-mono"
                                            value={formData.bank_cbu} onChange={(e) => setFormData(prev => ({ ...prev, bank_cbu: e.target.value }))} />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs font-medium text-blue-400">{t('clinics.bank_alias')}</label>
                                        <input type="text" placeholder="clinica.delgado"
                                            className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                            value={formData.bank_alias} onChange={(e) => setFormData(prev => ({ ...prev, bank_alias: e.target.value }))} />
                                    </div>
                                    <div className="space-y-1">
                                        <label className="text-xs font-medium text-blue-400">{t('clinics.bank_holder_name')}</label>
                                        <input type="text" placeholder="Laura Delgado"
                                            className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                            value={formData.bank_holder_name} onChange={(e) => setFormData(prev => ({ ...prev, bank_holder_name: e.target.value }))} />
                                    </div>
                                </div>
                            </div>

                            {/* Email de derivación */}
                            <div className="space-y-1 border-t pt-4 mt-4">
                                <label className="text-sm font-semibold text-white/60">{t('clinics.derivation_email_label')}</label>
                                <input type="email" placeholder="consultorio@ejemplo.com"
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                    value={formData.derivation_email} onChange={(e) => setFormData(prev => ({ ...prev, derivation_email: e.target.value }))} />
                                <p className="text-xs text-white/30">{t('clinics.derivation_email_help')}</p>
                            </div>

                            {/* Calendar provider */}
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60 flex items-center gap-2"><Calendar size={14} /> {t('clinics.calendar_provider_label')}</label>
                                <select className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none"
                                    value={formData.calendar_provider}
                                    onChange={(e) => { const v = e.target.value as 'local' | 'google'; setFormData(prev => ({ ...prev, calendar_provider: v })); }}>
                                    {CALENDAR_PROVIDER_OPTIONS(t).map((opt) => (
                                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Horarios por día */}
                            <div className="space-y-3">
                                <h3 className="text-sm font-bold text-white/60 flex items-center gap-2"><Clock size={14} /> {t('clinics.working_hours_label')}</h3>
                                <p className="text-xs text-white/30">{t('clinics.working_hours_help')}</p>
                                <div className="space-y-2">
                                    {DAY_KEYS.map((dayKey) => {
                                        const config = formData.working_hours[dayKey];
                                        const isExpanded = expandedDays.includes(dayKey);
                                        return (
                                            <div key={dayKey} className="rounded-xl border border-white/[0.06] overflow-hidden bg-white/[0.03]">
                                                <div className="flex items-center justify-between px-4 py-3 hover:bg-white/[0.04] transition-colors">
                                                    <label className="flex items-center gap-3 cursor-pointer flex-1">
                                                        <input type="checkbox" checked={config.enabled} onChange={() => toggleDayEnabled(dayKey)}
                                                            className="w-4 h-4 rounded border-white/[0.08] text-blue-400" />
                                                        <span className="text-sm font-medium text-white">{t('approvals.day_' + dayKey)}</span>
                                                    </label>
                                                    <div className="flex items-center gap-2">
                                                        <span className="text-xs text-white/40">{config.slots.length} {t('approvals.slots')}</span>
                                                        <button type="button" onClick={() => setExpandedDays(prev => isExpanded ? prev.filter(d => d !== dayKey) : [...prev, dayKey])}
                                                            className="p-2 rounded-lg hover:bg-white/[0.06] text-white/40">
                                                            <ChevronDown size={18} className={isExpanded ? 'rotate-180 transition-transform' : 'transition-transform'} />
                                                        </button>
                                                    </div>
                                                </div>
                                                {isExpanded && config.enabled && (
                                                    <div className="px-4 pb-4 pt-1 space-y-3 bg-white/[0.02] border-t border-white/[0.06]">
                                                        {config.slots.map((slot, idx) => (
                                                            <div key={idx} className="flex items-center gap-3">
                                                                <input type="time" value={slot.start} onChange={(e) => updateTimeSlot(dayKey, idx, 'start', e.target.value)}
                                                                    className="px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white w-28" />
                                                                <span className="text-white/30">-</span>
                                                                <input type="time" value={slot.end} onChange={(e) => updateTimeSlot(dayKey, idx, 'end', e.target.value)}
                                                                    className="px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white w-28" />
                                                                <button type="button" onClick={() => removeTimeSlot(dayKey, idx)} className="text-sm text-red-500 hover:text-red-700">{t('approvals.remove')}</button>
                                                            </div>
                                                        ))}
                                                        <button type="button" onClick={() => addTimeSlot(dayKey)} className="text-sm font-medium text-blue-400 hover:text-blue-300">+ {t('approvals.add_schedule')}</button>

                                                        {/* Sede / Ubicación por día */}
                                                        <div className="mt-3 pt-3 border-t border-white/[0.06] space-y-2">
                                                            <p className="text-xs font-semibold text-white/40 flex items-center gap-1"><MapPin size={12} /> {t('clinics.day_location_title')}</p>
                                                            <input type="text" placeholder={t('clinics.day_location_name')}
                                                                className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white"
                                                                value={config.location || ''} onChange={(e) => updateDayField(dayKey, 'location', e.target.value)} />
                                                            <input type="text" placeholder={t('clinics.day_location_address')}
                                                                className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white"
                                                                value={config.address || ''} onChange={(e) => updateDayField(dayKey, 'address', e.target.value)} />
                                                            <input type="url" placeholder={t('clinics.day_location_maps')}
                                                                className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white"
                                                                value={config.maps_url || ''} onChange={(e) => updateDayField(dayKey, 'maps_url', e.target.value)} />
                                                            <p className="text-xs text-white/30">{t('clinics.day_location_help')}</p>
                                                        </div>
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>

                            <div className="flex gap-3 pt-4 sticky bottom-0 bg-[#0d1117] pb-2">
                                <button type="button" onClick={() => setIsModalOpen(false)}
                                    className="flex-1 py-2 text-white/70 font-medium hover:bg-white/[0.04] rounded-lg transition-all">
                                    {t('common.cancel')}
                                </button>
                                <button type="submit" disabled={saving}
                                    className="flex-1 py-2 bg-white text-[#0a0e1a] font-bold rounded-lg hover:bg-white/90 transition-all disabled:opacity-50 flex items-center justify-center gap-2">
                                    {saving ? <Loader2 className="animate-spin" size={20} /> : t('common.save')}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* ── Modal FAQs ── */}
            {faqModalOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-2xl animate-scale-in max-h-[90vh] flex flex-col">
                        <div className="p-4 sm:p-6 border-b border-white/[0.06] shrink-0 flex justify-between items-center">
                            <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                <HelpCircle className="text-amber-400" />
                                {t('clinics.faq_title')} - {faqClinicName}
                            </h2>
                            <button onClick={() => setFaqModalOpen(false)} className="p-2 hover:bg-white/[0.04] rounded-lg text-white/40"><X size={20} /></button>
                        </div>

                        <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-6">
                            {/* Formulario agregar/editar FAQ */}
                            <form onSubmit={handleFaqSubmit} className="space-y-3 bg-white/[0.02] p-4 rounded-xl border border-white/[0.06]">
                                <h3 className="text-sm font-bold text-white/60">
                                    {faqEditing ? t('clinics.faq_edit') : t('clinics.faq_add')}
                                </h3>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div>
                                        <label className="text-xs font-semibold text-white/60">{t('clinics.faq_category')}</label>
                                        <input type="text" value={faqForm.category} onChange={e => setFaqForm({ ...faqForm, category: e.target.value })}
                                            className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white mt-1" placeholder="Ej: Pagos, General, Tratamientos" />
                                    </div>
                                    <div>
                                        <label className="text-xs font-semibold text-white/60">{t('clinics.faq_order')}</label>
                                        <input type="number" value={faqForm.sort_order} onChange={e => setFaqForm({ ...faqForm, sort_order: parseInt(e.target.value) || 0 })}
                                            className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white mt-1" />
                                    </div>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-white/60">{t('clinics.faq_question')}</label>
                                    <input required type="text" value={faqForm.question} onChange={e => setFaqForm({ ...faqForm, question: e.target.value })}
                                        className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white mt-1" placeholder={t('clinics.faq_question_placeholder')} />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-white/60">{t('clinics.faq_answer')}</label>
                                    <textarea required value={faqForm.answer} onChange={e => setFaqForm({ ...faqForm, answer: e.target.value })}
                                        className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white mt-1 min-h-[60px]" placeholder={t('clinics.faq_answer_placeholder')} />
                                </div>
                                <div className="flex gap-2">
                                    {faqEditing && (
                                        <button type="button" onClick={() => { setFaqEditing(null); setFaqForm({ category: 'General', question: '', answer: '', sort_order: 0 }); }}
                                            className="px-4 py-1.5 text-sm text-white/70 hover:bg-white/[0.06] rounded-lg">{t('common.cancel')}</button>
                                    )}
                                    <button type="submit" disabled={faqSaving}
                                        className="px-4 py-1.5 text-sm bg-white text-[#0a0e1a] rounded-lg hover:bg-white/90 disabled:opacity-50 flex items-center gap-2">
                                        {faqSaving && <Loader2 className="animate-spin" size={14} />}
                                        {faqEditing ? t('common.save') : t('clinics.faq_add_btn')}
                                    </button>
                                </div>
                            </form>

                            {/* Lista de FAQs */}
                            {faqLoading ? (
                                <div className="flex justify-center py-8"><Loader2 className="animate-spin text-blue-400" size={24} /></div>
                            ) : faqs.length === 0 ? (
                                <p className="text-center text-white/30 py-8 text-sm">{t('clinics.faq_empty')}</p>
                            ) : (
                                <div className="space-y-3">
                                    {faqs.map((faq) => (
                                        <div key={faq.id} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4 space-y-2 hover:border-white/[0.12] transition-all">
                                            <div className="flex justify-between items-start">
                                                <span className="text-xs font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full">{faq.category}</span>
                                                <div className="flex gap-1">
                                                    <button onClick={() => handleFaqEdit(faq)} className="p-1 text-blue-400 hover:bg-blue-500/10 rounded"><Edit size={14} /></button>
                                                    <button onClick={() => faq.id && handleFaqDelete(faq.id)} className="p-1 text-red-400 hover:bg-red-500/10 rounded"><Trash2 size={14} /></button>
                                                </div>
                                            </div>
                                            <p className="text-sm font-medium text-white">{faq.question}</p>
                                            <p className="text-sm text-white/60">{faq.answer}</p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
