import { useState, useEffect } from 'react';
import { Building2, Plus, Edit, Trash2, Phone, Loader2, AlertCircle, CheckCircle2, Calendar, Clock, MapPin, HelpCircle, ChevronDown, X, DollarSign, Shield, GitMerge, ToggleLeft, ToggleRight, Info, Search, Check } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';
import GlassCard, { CARD_IMAGES } from '../components/GlassCard';

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
    country_code?: string;
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

interface InsuranceProvider {
    id: number;
    tenant_id: number;
    provider_name: string;
    status: 'accepted' | 'restricted' | 'external_derivation' | 'rejected';
    restrictions?: string;
    external_target?: string;
    requires_copay: boolean;
    copay_notes?: string;
    ai_response_template?: string;
    sort_order: number;
    is_active: boolean;
}

interface DerivationRule {
    id: number;
    tenant_id: number;
    rule_name: string;
    patient_condition: 'new_patient' | 'existing_patient' | 'any';
    treatment_categories: string[];
    target_type: 'specific_professional' | 'priority_professional' | 'team';
    target_professional_id?: number;
    target_professional_name?: string;
    priority_order: number;
    is_active: boolean;
    description?: string;
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
        country_code: 'US',
        working_hours: createDefaultWorkingHours(),
    });
    const [expandedDays, setExpandedDays] = useState<string[]>([]);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState<string | null>(null);

    // Tab state
    const [activeTab, setActiveTab] = useState<'clinics' | 'insurance' | 'derivation'>('clinics');
    const [selectedClinicId, setSelectedClinicId] = useState<number | null>(null);

    // Insurance state
    const [insuranceProviders, setInsuranceProviders] = useState<InsuranceProvider[]>([]);
    const [insuranceLoading, setInsuranceLoading] = useState(false);
    const [insuranceModalOpen, setInsuranceModalOpen] = useState(false);
    const [editingInsurance, setEditingInsurance] = useState<InsuranceProvider | null>(null);
    const [insuranceForm, setInsuranceForm] = useState<Partial<InsuranceProvider>>({
        provider_name: '', status: 'accepted', requires_copay: true, sort_order: 0, is_active: true,
    });
    const [insuranceSaving, setInsuranceSaving] = useState(false);
    const [insuranceTreatments, setInsuranceTreatments] = useState<{code: string; name: string}[]>([]);
    const [insuranceTreatmentSearch, setInsuranceTreatmentSearch] = useState('');

    // Derivation state
    const [derivationRules, setDerivationRules] = useState<DerivationRule[]>([]);
    const [derivationLoading, setDerivationLoading] = useState(false);
    const [derivationModalOpen, setDerivationModalOpen] = useState(false);
    const [editingDerivation, setEditingDerivation] = useState<DerivationRule | null>(null);
    const [derivationForm, setDerivationForm] = useState<Partial<DerivationRule>>({
        rule_name: '', patient_condition: 'any', treatment_categories: [], target_type: 'team', is_active: true,
    });
    const [derivationSaving, setDerivationSaving] = useState(false);
    const [derivationProfessionals, setDerivationProfessionals] = useState<{id: number; first_name: string; last_name: string}[]>([]);
    const [derivationTreatments, setDerivationTreatments] = useState<{code: string; name: string; priority: string}[]>([]);

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
    useEffect(() => {
        // Auto-select first clinic when clinics load and none selected
        if (clinicas.length > 0 && selectedClinicId === null) {
            setSelectedClinicId(clinicas[0].id);
        }
    }, [clinicas]);
    useEffect(() => {
        if (!selectedClinicId) return;
        if (activeTab === 'insurance') fetchInsurance();
        if (activeTab === 'derivation') fetchDerivation();
    }, [activeTab, selectedClinicId]);

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
                country_code: clinica.country_code || 'US',
                working_hours: parseWorkingHours(clinica.working_hours),
            });
        } else {
            setEditingClinica(null);
            setFormData({ clinic_name: '', bot_phone_number: '', calendar_provider: 'local', address: '', google_maps_url: '', consultation_price: '', bank_cbu: '', bank_alias: '', bank_holder_name: '', derivation_email: '', max_chairs: '2', country_code: 'US', working_hours: createDefaultWorkingHours() });
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
                country_code: formData.country_code || 'US',
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
            await api.post(`/admin/tenants/${faqClinicId}/faqs`, faqForm);
            setFaqForm({ category: 'General', question: '', answer: '', sort_order: 0 });
            await fetchFaqs(faqClinicId);
        } catch (err: any) {
            console.error('Error guardando FAQ:', err);
        } finally {
            setFaqSaving(false);
        }
    };

    const [faqEditModalOpen, setFaqEditModalOpen] = useState(false);

    const handleFaqEdit = (faq: FAQ) => {
        setFaqEditing(faq);
        setFaqForm({ category: faq.category, question: faq.question, answer: faq.answer, sort_order: faq.sort_order });
        setFaqEditModalOpen(true);
    };

    const handleFaqEditSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!faqClinicId || !faqEditing?.id) return;
        setFaqSaving(true);
        try {
            await api.put(`/admin/faqs/${faqEditing.id}`, faqForm);
            setFaqEditModalOpen(false);
            setFaqEditing(null);
            setFaqForm({ category: 'General', question: '', answer: '', sort_order: 0 });
            await fetchFaqs(faqClinicId);
        } catch (err: any) {
            console.error('Error guardando FAQ:', err);
        } finally {
            setFaqSaving(false);
        }
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

    /* ── Insurance Handlers ── */
    const tenantHeaders = selectedClinicId ? { headers: { 'X-Tenant-ID': String(selectedClinicId) } } : {};

    const fetchInsurance = async () => {
        if (!selectedClinicId) return;
        setInsuranceLoading(true);
        try {
            const th = { headers: { 'X-Tenant-ID': String(selectedClinicId) } };
            const [insResp, treatResp] = await Promise.allSettled([
                api.get('/admin/insurance-providers', th),
                api.get('/admin/treatment-types', th),
            ]);
            if (insResp.status === 'fulfilled') setInsuranceProviders(insResp.value.data);
            if (treatResp.status === 'fulfilled') {
                setInsuranceTreatments(
                    Array.isArray(treatResp.value.data)
                        ? treatResp.value.data.map((t: any) => ({ code: t.code, name: t.name }))
                        : []
                );
            }
        } catch (err) { console.error('Error cargando obras sociales:', err); }
        finally { setInsuranceLoading(false); }
    };

    // Helper: parse restrictions field — may be JSON array of codes or legacy free text
    const parseRestrictionsAsCodes = (restrictions?: string): string[] => {
        if (!restrictions) return [];
        try {
            const parsed = JSON.parse(restrictions);
            if (Array.isArray(parsed)) return parsed;
        } catch { /* legacy free text — ignore */ }
        return [];
    };

    const openInsuranceModal = (item: InsuranceProvider | null = null) => {
        if (item) {
            setEditingInsurance(item);
            setInsuranceForm({ ...item });
        } else {
            setEditingInsurance(null);
            setInsuranceForm({ provider_name: '', status: 'accepted', requires_copay: true, sort_order: 0, is_active: true, restrictions: '[]' });
        }
        setInsuranceTreatmentSearch('');
        setInsuranceModalOpen(true);
    };

    const handleInsuranceSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedClinicId) return;
        setInsuranceSaving(true);
        const th = { headers: { 'X-Tenant-ID': String(selectedClinicId) } };
        try {
            if (editingInsurance) {
                await api.put(`/admin/insurance-providers/${editingInsurance.id}`, insuranceForm, th);
            } else {
                await api.post('/admin/insurance-providers', insuranceForm, th);
            }
            setInsuranceModalOpen(false);
            await fetchInsurance();
        } catch (err: any) {
            const detail = err?.response?.data?.detail;
            if (detail) alert(detail);
            console.error('Error guardando obra social:', err);
        }
        finally { setInsuranceSaving(false); }
    };

    const handleInsuranceDelete = async (id: number, name: string) => {
        if (!window.confirm(t('settings.insurance.deleteConfirm').replace('{name}', name))) return;
        const th = { headers: { 'X-Tenant-ID': String(selectedClinicId) } };
        try {
            await api.delete(`/admin/insurance-providers/${id}`, th);
            await fetchInsurance();
        } catch (err) { console.error('Error eliminando obra social:', err); }
    };

    const handleInsuranceToggle = async (id: number) => {
        const th = { headers: { 'X-Tenant-ID': String(selectedClinicId) } };
        try {
            await api.patch(`/admin/insurance-providers/${id}/toggle-active`, null, th);
            await fetchInsurance();
        } catch (err) { console.error('Error toggling obra social:', err); }
    };

    /* ── Derivation Handlers ── */
    const fetchDerivation = async () => {
        if (!selectedClinicId) return;
        setDerivationLoading(true);
        try {
            const th = { headers: { 'X-Tenant-ID': String(selectedClinicId) } };
            const [rulesResp, profResp, treatResp] = await Promise.allSettled([
                api.get('/admin/derivation-rules', th),
                api.get('/admin/professionals', th),
                api.get('/admin/treatment-types', th),
            ]);
            if (rulesResp.status === 'fulfilled') setDerivationRules(rulesResp.value.data);
            if (profResp.status === 'fulfilled') setDerivationProfessionals(Array.isArray(profResp.value.data) ? profResp.value.data : []);
            if (treatResp.status === 'fulfilled') setDerivationTreatments(Array.isArray(treatResp.value.data) ? treatResp.value.data.map((t: any) => ({ code: t.code, name: t.name, priority: t.priority || 'medium' })) : []);
        } catch (err) { console.error('Error cargando reglas de derivación:', err); }
        finally { setDerivationLoading(false); }
    };

    const openDerivationModal = (item: DerivationRule | null = null) => {
        if (item) {
            setEditingDerivation(item);
            setDerivationForm({ ...item });
        } else {
            setEditingDerivation(null);
            setDerivationForm({ rule_name: '', patient_condition: 'any', treatment_categories: [], target_type: 'team', is_active: true });
        }
        setDerivationModalOpen(true);
    };

    const handleDerivationSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedClinicId) return;
        setDerivationSaving(true);
        const th = { headers: { 'X-Tenant-ID': String(selectedClinicId) } };
        try {
            if (editingDerivation) {
                await api.put(`/admin/derivation-rules/${editingDerivation.id}`, derivationForm, th);
            } else {
                await api.post('/admin/derivation-rules', derivationForm, th);
            }
            setDerivationModalOpen(false);
            await fetchDerivation();
        } catch (err: any) {
            const detail = err?.response?.data?.detail;
            if (detail) alert(detail);
            console.error('Error guardando regla:', err);
        }
        finally { setDerivationSaving(false); }
    };

    const handleDerivationDelete = async (id: number) => {
        if (!window.confirm(t('alerts.confirm_delete_clinic'))) return;
        const th = { headers: { 'X-Tenant-ID': String(selectedClinicId) } };
        try {
            await api.delete(`/admin/derivation-rules/${id}`, th);
            await fetchDerivation();
        } catch (err) { console.error('Error eliminando regla:', err); }
    };

    const handleDerivationToggle = async (id: number) => {
        const th = { headers: { 'X-Tenant-ID': String(selectedClinicId) } };
        try {
            await api.patch(`/admin/derivation-rules/${id}/toggle-active`, null, th);
            await fetchDerivation();
        } catch (err) { console.error('Error toggling regla:', err); }
    };

    const insuranceStatusBadge = (status: InsuranceProvider['status']) => {
        const map: Record<string, string> = {
            accepted: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
            restricted: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
            external_derivation: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
            rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
        };
        return map[status] || 'bg-white/[0.06] text-white/40 border-white/[0.06]';
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
                    activeTab === 'clinics' ? (
                        <button
                            onClick={() => handleOpenModal()}
                            className="flex items-center justify-center gap-2 bg-white text-[#0a0e1a] px-4 py-2.5 rounded-xl hover:bg-white/90 transition-all font-medium text-sm sm:text-base active:scale-[0.98]"
                        >
                            <Plus size={20} /> {t('clinics.new_clinic')}
                        </button>
                    ) : activeTab === 'insurance' ? (
                        <button
                            onClick={() => openInsuranceModal()}
                            className="flex items-center justify-center gap-2 bg-white text-[#0a0e1a] px-4 py-2.5 rounded-xl hover:bg-white/90 transition-all font-medium text-sm sm:text-base active:scale-[0.98]"
                        >
                            <Plus size={20} /> {t('settings.insurance.addButton')}
                        </button>
                    ) : (
                        <button
                            onClick={() => openDerivationModal()}
                            disabled={derivationRules.length >= 20}
                            className="flex items-center justify-center gap-2 bg-white text-[#0a0e1a] px-4 py-2.5 rounded-xl hover:bg-white/90 transition-all font-medium text-sm sm:text-base active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <Plus size={20} /> {t('settings.derivation.addButton')}
                        </button>
                    )
                }
            />

            {/* Tab navigation */}
            <div className="flex gap-1 bg-white/[0.03] p-1 rounded-xl border border-white/[0.06] w-fit">
                {([['clinics', <Building2 size={16} />, t('clinics.title')], ['insurance', <Shield size={16} />, t('settings.insurance.title')], ['derivation', <GitMerge size={16} />, t('settings.derivation.title')]] as [typeof activeTab, React.ReactNode, string][]).map(([key, icon, label]) => (
                    <button
                        key={key}
                        onClick={() => setActiveTab(key)}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all ${activeTab === key ? 'bg-white text-[#0a0e1a]' : 'text-white/50 hover:text-white hover:bg-white/[0.04]'}`}
                    >
                        {icon} {label}
                    </button>
                ))}
            </div>

            {/* Clinic selector for insurance/derivation tabs */}
            {activeTab !== 'clinics' && clinicas.length > 0 && (
                <div className="flex items-center gap-3 bg-white/[0.03] border border-white/[0.06] rounded-xl px-4 py-3">
                    <Building2 size={16} className="text-white/40" />
                    <span className="text-sm text-white/50 font-medium">{t('clinics.title')}:</span>
                    <select
                        value={selectedClinicId || ''}
                        onChange={e => setSelectedClinicId(Number(e.target.value))}
                        className="px-3 py-1.5 bg-white/[0.06] border border-white/[0.08] rounded-lg text-white text-sm font-semibold focus:ring-2 focus:ring-blue-500 outline-none [&>option]:bg-[#0d1117]"
                    >
                        {clinicas.map(c => (
                            <option key={c.id} value={c.id}>{c.clinic_name}</option>
                        ))}
                    </select>
                </div>
            )}

            {success && (
                <div className="bg-green-500/10 text-green-400 p-3 rounded-lg flex items-center gap-2 border border-green-500/20 animate-fade-in">
                    <CheckCircle2 size={18} /> {success}
                </div>
            )}

            {activeTab === 'clinics' && <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {clinicas.map((clinica) => (
                    <GlassCard
                        key={clinica.id}
                        image={CARD_IMAGES.clinic}
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
                    </GlassCard>
                ))}
            </div>}

            {/* ── Insurance Tab ── */}
            {activeTab === 'insurance' && (
                <div className="space-y-4">
                    {insuranceLoading ? (
                        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-blue-400" size={28} /></div>
                    ) : insuranceProviders.length === 0 ? (
                        <div className="text-center py-16 bg-white/[0.02] border border-white/[0.06] rounded-2xl">
                            <Shield size={40} className="text-white/20 mx-auto mb-4" />
                            <p className="text-white/40 text-sm max-w-md mx-auto">{t('settings.insurance.emptyState')}</p>
                        </div>
                    ) : (
                        <div className="bg-white/[0.02] border border-white/[0.06] rounded-2xl overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead>
                                        <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                                            <th className="text-left px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('settings.insurance.fields.providerName')}</th>
                                            <th className="text-left px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('settings.insurance.fields.status')}</th>
                                            <th className="text-left px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('settings.insurance.fields.coveredTreatments')}</th>
                                            <th className="text-left px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('settings.insurance.fields.requiresCopay')}</th>
                                            <th className="text-right px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('common.edit')}</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/[0.04]">
                                        {insuranceProviders.map((prov) => (
                                            <tr key={prov.id} className={`hover:bg-white/[0.02] transition-colors ${!prov.is_active ? 'opacity-50' : ''}`}>
                                                <td className="px-4 py-3 text-sm font-semibold text-white">{prov.provider_name}</td>
                                                <td className="px-4 py-3">
                                                    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-bold border ${insuranceStatusBadge(prov.status)}`}>
                                                        {t(`settings.insurance.status.${prov.status}`)}
                                                    </span>
                                                </td>
                                                <td className="px-4 py-3 text-xs text-white/50 max-w-xs">
                                                    {prov.status === 'external_derivation' ? prov.external_target : (() => {
                                                        const codes = parseRestrictionsAsCodes(prov.restrictions);
                                                        if (codes.length === 0) return prov.restrictions || '\u2014';
                                                        return (
                                                            <div className="flex flex-wrap gap-1">
                                                                {codes.slice(0, 3).map(code => {
                                                                    const treat = insuranceTreatments.find(t => t.code === code);
                                                                    return <span key={code} className="inline-block px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 rounded text-[10px] font-semibold">{treat ? treat.name : code}</span>;
                                                                })}
                                                                {codes.length > 3 && <span className="text-white/30 text-[10px]">+{codes.length - 3}</span>}
                                                            </div>
                                                        );
                                                    })()}
                                                </td>
                                                <td className="px-4 py-3 text-xs text-white/50">
                                                    {prov.requires_copay ? <span className="text-amber-400 font-semibold">{t('common.yes')}</span> : <span className="text-white/30">{t('common.no')}</span>}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="flex items-center justify-end gap-1">
                                                        <button onClick={() => handleInsuranceToggle(prov.id)} className="p-1.5 text-white/30 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-colors" title={prov.is_active ? 'Desactivar' : 'Activar'}>
                                                            {prov.is_active ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                                                        </button>
                                                        <button onClick={() => openInsuranceModal(prov)} className="p-1.5 text-white/30 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-colors">
                                                            <Edit size={15} />
                                                        </button>
                                                        <button onClick={() => handleInsuranceDelete(prov.id, prov.provider_name)} className="p-1.5 text-white/30 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors">
                                                            <Trash2 size={15} />
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ── Derivation Tab ── */}
            {activeTab === 'derivation' && (
                <div className="space-y-4">
                    <div className="flex items-start gap-3 bg-blue-500/5 border border-blue-500/20 rounded-xl p-4">
                        <Info size={18} className="text-blue-400 shrink-0 mt-0.5" />
                        <div className="text-sm text-blue-300/80">
                            <p>{t('settings.derivation.explainer')}</p>
                            {derivationRules.length >= 20 && <p className="mt-1 font-bold text-amber-400">{t('settings.derivation.maxRulesWarning')}</p>}
                        </div>
                    </div>

                    {derivationLoading ? (
                        <div className="flex justify-center py-12"><Loader2 className="animate-spin text-blue-400" size={28} /></div>
                    ) : derivationRules.length === 0 ? (
                        <div className="text-center py-16 bg-white/[0.02] border border-white/[0.06] rounded-2xl">
                            <GitMerge size={40} className="text-white/20 mx-auto mb-4" />
                            <p className="text-white/40 text-sm max-w-md mx-auto">{t('settings.derivation.emptyState')}</p>
                        </div>
                    ) : (
                        <div className="bg-white/[0.02] border border-white/[0.06] rounded-2xl overflow-hidden">
                            <div className="overflow-x-auto">
                                <table className="w-full">
                                    <thead>
                                        <tr className="border-b border-white/[0.06] bg-white/[0.02]">
                                            <th className="text-left px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">#</th>
                                            <th className="text-left px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('settings.derivation.fields.ruleName')}</th>
                                            <th className="text-left px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('settings.derivation.fields.patientCondition')}</th>
                                            <th className="text-left px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('settings.derivation.fields.categories')}</th>
                                            <th className="text-left px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('settings.derivation.fields.targetType')}</th>
                                            <th className="text-right px-4 py-3 text-xs font-bold text-white/40 uppercase tracking-wider">{t('common.edit')}</th>
                                        </tr>
                                    </thead>
                                    <tbody className="divide-y divide-white/[0.04]">
                                        {[...derivationRules].sort((a, b) => a.priority_order - b.priority_order).map((rule) => (
                                            <tr key={rule.id} className={`hover:bg-white/[0.02] transition-colors ${!rule.is_active ? 'opacity-50' : ''}`}>
                                                <td className="px-4 py-3">
                                                    <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-blue-500/10 text-blue-400 text-xs font-bold">{rule.priority_order}</span>
                                                </td>
                                                <td className="px-4 py-3 text-sm font-semibold text-white">{rule.rule_name}</td>
                                                <td className="px-4 py-3 text-xs text-white/60">{t(`settings.derivation.condition.${rule.patient_condition}`)}</td>
                                                <td className="px-4 py-3 text-xs text-white/50 max-w-xs">
                                                    {rule.treatment_categories.length > 0 ? rule.treatment_categories.join(', ') : '*'}
                                                </td>
                                                <td className="px-4 py-3 text-xs text-white/60">
                                                    {rule.target_type === 'specific_professional' && rule.target_professional_name
                                                        ? rule.target_professional_name
                                                        : t(`settings.derivation.target.${rule.target_type}`)}
                                                </td>
                                                <td className="px-4 py-3">
                                                    <div className="flex items-center justify-end gap-1">
                                                        <button onClick={() => handleDerivationToggle(rule.id)} className="p-1.5 text-white/30 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-colors">
                                                            {rule.is_active ? <ToggleRight size={18} /> : <ToggleLeft size={18} />}
                                                        </button>
                                                        <button onClick={() => openDerivationModal(rule)} className="p-1.5 text-white/30 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-colors">
                                                            <Edit size={15} />
                                                        </button>
                                                        <button onClick={() => handleDerivationDelete(rule.id)} className="p-1.5 text-white/30 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors">
                                                            <Trash2 size={15} />
                                                        </button>
                                                    </div>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    )}
                </div>
            )}

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

                            {/* País (para feriados) */}
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('clinics.country_code')}</label>
                                <select
                                    className="w-full px-4 py-2 bg-[#0d1117] border border-white/[0.08] rounded-lg text-white focus:ring-2 focus:ring-blue-500 outline-none [&>option]:bg-[#0d1117] [&>option]:text-white"
                                    value={formData.country_code}
                                    onChange={(e) => setFormData(prev => ({ ...prev, country_code: e.target.value }))}
                                >
                                    <option value="US">United States</option>
                                    <option value="AR">Argentina</option>
                                    <option value="MX">México</option>
                                    <option value="CO">Colombia</option>
                                    <option value="CL">Chile</option>
                                    <option value="PE">Perú</option>
                                    <option value="EC">Ecuador</option>
                                    <option value="UY">Uruguay</option>
                                    <option value="PY">Paraguay</option>
                                    <option value="BR">Brasil</option>
                                    <option value="ES">España</option>
                                    <option value="VE">Venezuela</option>
                                    <option value="BO">Bolivia</option>
                                    <option value="CR">Costa Rica</option>
                                    <option value="PA">Panamá</option>
                                    <option value="DO">Rep. Dominicana</option>
                                    <option value="GT">Guatemala</option>
                                    <option value="HN">Honduras</option>
                                    <option value="SV">El Salvador</option>
                                    <option value="NI">Nicaragua</option>
                                    <option value="CU">Cuba</option>
                                    <option value="PR">Puerto Rico</option>
                                    <option value="CA">Canadá</option>
                                    <option value="GB">United Kingdom</option>
                                    <option value="DE">Alemania</option>
                                    <option value="FR">Francia</option>
                                    <option value="IT">Italia</option>
                                    <option value="PT">Portugal</option>
                                </select>
                                <p className="text-xs text-white/30">{t('clinics.country_code_help')}</p>
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
                            {/* Formulario agregar FAQ */}
                            <form onSubmit={handleFaqSubmit} className="space-y-3 bg-white/[0.02] p-4 rounded-xl border border-white/[0.06]">
                                <h3 className="text-sm font-bold text-white/60">
                                    {t('clinics.faq_add')}
                                </h3>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                    <div>
                                        <label className="text-xs font-semibold text-white/60">{t('clinics.faq_category')}</label>
                                        <select value={faqForm.category} onChange={e => setFaqForm({ ...faqForm, category: e.target.value })}
                                            className="w-full px-3 py-1.5 bg-[#0d1117] border border-white/[0.08] rounded-lg text-sm text-white mt-1 [&>option]:bg-[#0d1117] [&>optgroup]:bg-[#0d1117] [&>optgroup]:text-white/40 [&>optgroup]:font-bold">
                                            <optgroup label="Información general">
                                                <option value="General">General</option>
                                                <option value="Ubicación y Horarios">Ubicación y Horarios</option>
                                                <option value="Estacionamiento y Acceso">Estacionamiento y Acceso</option>
                                            </optgroup>
                                            <optgroup label="Comercial">
                                                <option value="Precios y Costos">Precios y Costos</option>
                                                <option value="Medios de Pago">Medios de Pago</option>
                                                <option value="Financiación">Financiación</option>
                                                <option value="Promociones">Promociones</option>
                                            </optgroup>
                                            <optgroup label="Obras Sociales">
                                                <option value="Obras Sociales">Obras Sociales</option>
                                                <option value="Coseguros">Coseguros</option>
                                                <option value="Autorizaciones">Autorizaciones</option>
                                            </optgroup>
                                            <optgroup label="Tratamientos">
                                                <option value="Tratamientos Generales">Tratamientos Generales</option>
                                                <option value="Implantes y Prótesis">Implantes y Prótesis</option>
                                                <option value="Estética Dental">Estética Dental</option>
                                                <option value="Ortodoncia">Ortodoncia</option>
                                                <option value="Cirugía">Cirugía</option>
                                                <option value="Blanqueamiento">Blanqueamiento</option>
                                            </optgroup>
                                            <optgroup label="Experiencia del paciente">
                                                <option value="Primera Consulta">Primera Consulta</option>
                                                <option value="Cuidados Post-tratamiento">Cuidados Post-tratamiento</option>
                                                <option value="Emergencias">Emergencias</option>
                                                <option value="Garantías">Garantías</option>
                                            </optgroup>
                                            <optgroup label="Estrategia de ventas">
                                                <option value="Diferenciadores">Diferenciadores</option>
                                                <option value="Tecnología">Tecnología</option>
                                                <option value="Casos de Éxito">Casos de Éxito</option>
                                                <option value="Ventajas Competitivas">Ventajas Competitivas</option>
                                            </optgroup>
                                            <optgroup label="Scripts de respuesta">
                                                <option value="Script - Implantes">Script - Implantes</option>
                                                <option value="Script - Prótesis">Script - Prótesis</option>
                                                <option value="Script - Cirugía">Script - Cirugía</option>
                                                <option value="Script - ATM">Script - ATM</option>
                                                <option value="Script - Armonización">Script - Armonización</option>
                                                <option value="Script - Endolifting">Script - Endolifting</option>
                                                <option value="Script - General">Script - General</option>
                                                <option value="Script - Ortodoncia">Script - Ortodoncia</option>
                                                <option value="Script - Endodoncia">Script - Endodoncia</option>
                                                <option value="Script - Precio">Script - Precio</option>
                                                <option value="Script - Miedo">Script - Miedo</option>
                                                <option value="Script - Obra Social">Script - Obra Social</option>
                                                <option value="Script - Paciente Lejano">Script - Paciente Lejano</option>
                                            </optgroup>
                                        </select>
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
                                    <button type="submit" disabled={faqSaving}
                                        className="px-4 py-1.5 text-sm bg-white text-[#0a0e1a] rounded-lg hover:bg-white/90 disabled:opacity-50 flex items-center gap-2">
                                        {faqSaving && <Loader2 className="animate-spin" size={14} />}
                                        {t('clinics.faq_add_btn')}
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
                                                <div className="flex gap-2">
                                                    <button onClick={() => handleFaqEdit(faq)} className="px-2.5 py-1.5 text-blue-400 hover:bg-blue-500/10 rounded-lg flex items-center gap-1.5 text-xs font-medium" title={t('clinics.faq_edit')}>
                                                        <Edit size={15} /> {t('common.edit')}
                                                    </button>
                                                    <button onClick={() => faq.id && handleFaqDelete(faq.id)} className="px-2.5 py-1.5 text-red-400 hover:bg-red-500/10 rounded-lg flex items-center gap-1.5 text-xs font-medium" title={t('common.delete')}>
                                                        <Trash2 size={15} /> {t('common.delete')}
                                                    </button>
                                                </div>
                                            </div>
                                            <p className="text-sm font-medium text-white">{faq.question}</p>
                                            <p className="text-sm text-white/60 whitespace-pre-line">{faq.answer}</p>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
            {/* ── Modal Editar FAQ ── */}
            {faqEditModalOpen && faqEditing && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4">
                    <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-lg animate-scale-in">
                        <div className="p-4 sm:p-6 border-b border-white/[0.06] flex justify-between items-center">
                            <h2 className="text-lg font-bold text-white flex items-center gap-2">
                                <Edit size={18} className="text-blue-400" />
                                {t('clinics.faq_edit')}
                            </h2>
                            <button onClick={() => { setFaqEditModalOpen(false); setFaqEditing(null); }} className="p-2 hover:bg-white/[0.04] rounded-lg text-white/40"><X size={20} /></button>
                        </div>
                        <form onSubmit={handleFaqEditSubmit} className="p-4 sm:p-6 space-y-4">
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-white/60">{t('clinics.faq_category')}</label>
                                    <select value={faqForm.category} onChange={e => setFaqForm({ ...faqForm, category: e.target.value })}
                                        className="w-full px-3 py-1.5 bg-[#0d1117] border border-white/[0.08] rounded-lg text-sm text-white mt-1 [&>option]:bg-[#0d1117] [&>optgroup]:bg-[#0d1117] [&>optgroup]:text-white/40 [&>optgroup]:font-bold">
                                        <optgroup label="Información general">
                                            <option value="General">General</option>
                                            <option value="Ubicación y Horarios">Ubicación y Horarios</option>
                                            <option value="Estacionamiento y Acceso">Estacionamiento y Acceso</option>
                                        </optgroup>
                                        <optgroup label="Comercial">
                                            <option value="Precios y Costos">Precios y Costos</option>
                                            <option value="Medios de Pago">Medios de Pago</option>
                                            <option value="Financiación">Financiación</option>
                                            <option value="Promociones">Promociones</option>
                                        </optgroup>
                                        <optgroup label="Obras Sociales">
                                            <option value="Obras Sociales">Obras Sociales</option>
                                            <option value="Coseguros">Coseguros</option>
                                            <option value="Autorizaciones">Autorizaciones</option>
                                        </optgroup>
                                        <optgroup label="Tratamientos">
                                            <option value="Tratamientos Generales">Tratamientos Generales</option>
                                            <option value="Implantes y Prótesis">Implantes y Prótesis</option>
                                            <option value="Estética Dental">Estética Dental</option>
                                            <option value="Ortodoncia">Ortodoncia</option>
                                            <option value="Cirugía">Cirugía</option>
                                            <option value="Blanqueamiento">Blanqueamiento</option>
                                        </optgroup>
                                        <optgroup label="Experiencia del paciente">
                                            <option value="Primera Consulta">Primera Consulta</option>
                                            <option value="Cuidados Post-tratamiento">Cuidados Post-tratamiento</option>
                                            <option value="Emergencias">Emergencias</option>
                                            <option value="Garantías">Garantías</option>
                                        </optgroup>
                                        <optgroup label="Estrategia de ventas">
                                            <option value="Diferenciadores">Diferenciadores</option>
                                            <option value="Tecnología">Tecnología</option>
                                            <option value="Casos de Éxito">Casos de Éxito</option>
                                            <option value="Ventajas Competitivas">Ventajas Competitivas</option>
                                        </optgroup>
                                        <optgroup label="Scripts de respuesta">
                                            <option value="Script - Implantes">Script - Implantes</option>
                                            <option value="Script - Prótesis">Script - Prótesis</option>
                                            <option value="Script - Cirugía">Script - Cirugía</option>
                                            <option value="Script - ATM">Script - ATM</option>
                                            <option value="Script - Armonización">Script - Armonización</option>
                                            <option value="Script - Endolifting">Script - Endolifting</option>
                                            <option value="Script - General">Script - General</option>
                                            <option value="Script - Ortodoncia">Script - Ortodoncia</option>
                                            <option value="Script - Endodoncia">Script - Endodoncia</option>
                                            <option value="Script - Precio">Script - Precio</option>
                                            <option value="Script - Miedo">Script - Miedo</option>
                                            <option value="Script - Obra Social">Script - Obra Social</option>
                                            <option value="Script - Paciente Lejano">Script - Paciente Lejano</option>
                                        </optgroup>
                                    </select>
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
                                    className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white mt-1" />
                            </div>
                            <div>
                                <label className="text-xs font-semibold text-white/60">{t('clinics.faq_answer')}</label>
                                <textarea required value={faqForm.answer} onChange={e => setFaqForm({ ...faqForm, answer: e.target.value })}
                                    className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg text-sm text-white mt-1 min-h-[120px]" />
                            </div>
                            <div className="flex justify-end gap-2 pt-2">
                                <button type="button" onClick={() => { setFaqEditModalOpen(false); setFaqEditing(null); }}
                                    className="px-4 py-1.5 text-sm text-white/70 hover:bg-white/[0.06] rounded-lg">{t('common.cancel')}</button>
                                <button type="submit" disabled={faqSaving}
                                    className="px-4 py-1.5 text-sm bg-white text-[#0a0e1a] rounded-lg hover:bg-white/90 disabled:opacity-50 flex items-center gap-2">
                                    {faqSaving && <Loader2 className="animate-spin" size={14} />}
                                    {t('common.save')}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
            {/* ── Modal Insurance ── */}
            {insuranceModalOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-lg animate-scale-in max-h-[90vh] flex flex-col">
                        <div className="p-4 sm:p-6 border-b border-white/[0.06] shrink-0 flex justify-between items-center">
                            <h2 className="text-lg font-bold text-white flex items-center gap-2">
                                <Shield className="text-emerald-400" size={20} />
                                {editingInsurance ? t('common.edit') : t('settings.insurance.addButton')}
                            </h2>
                            <button onClick={() => setInsuranceModalOpen(false)} className="p-2 hover:bg-white/[0.04] rounded-lg text-white/40"><X size={20} /></button>
                        </div>
                        <form onSubmit={handleInsuranceSubmit} className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-4">
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.providerName')}</label>
                                <input required type="text" value={insuranceForm.provider_name || ''} onChange={e => setInsuranceForm(p => ({ ...p, provider_name: e.target.value }))}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none" />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.status')}</label>
                                <select value={insuranceForm.status || 'accepted'} onChange={e => setInsuranceForm(p => ({ ...p, status: e.target.value as InsuranceProvider['status'] }))}
                                    className="w-full px-4 py-2 bg-[#0d1117] border border-white/[0.08] rounded-lg text-white focus:ring-2 focus:ring-blue-500 outline-none [&>option]:bg-[#0d1117]">
                                    <option value="accepted">{t('settings.insurance.status.accepted')}</option>
                                    <option value="restricted">{t('settings.insurance.status.restricted')}</option>
                                    <option value="external_derivation">{t('settings.insurance.status.external_derivation')}</option>
                                    <option value="rejected">{t('settings.insurance.status.rejected')}</option>
                                </select>
                            </div>
                            {insuranceForm.status === 'restricted' && (
                                <div className="space-y-2">
                                    <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.coveredTreatments')}</label>
                                    <p className="text-xs text-white/30">{t('settings.insurance.fields.coveredTreatmentsHint')}</p>
                                    {/* Selected treatments tags */}
                                    {(() => {
                                        const selectedCodes = parseRestrictionsAsCodes(insuranceForm.restrictions);
                                        return selectedCodes.length > 0 && (
                                            <div className="flex flex-wrap gap-1.5">
                                                {selectedCodes.map(code => {
                                                    const treat = insuranceTreatments.find(t => t.code === code);
                                                    return (
                                                        <span key={code} className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-500/10 text-emerald-400 rounded-lg text-xs font-semibold border border-emerald-500/20">
                                                            {treat ? treat.name : code}
                                                            <button type="button" onClick={() => {
                                                                const updated = selectedCodes.filter(c => c !== code);
                                                                setInsuranceForm(p => ({ ...p, restrictions: JSON.stringify(updated) }));
                                                            }} className="ml-0.5 hover:text-red-400 transition-colors">
                                                                <X size={12} />
                                                            </button>
                                                        </span>
                                                    );
                                                })}
                                            </div>
                                        );
                                    })()}
                                    {/* Search input */}
                                    <div className="relative">
                                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30" />
                                        <input
                                            type="text"
                                            value={insuranceTreatmentSearch}
                                            onChange={e => setInsuranceTreatmentSearch(e.target.value)}
                                            placeholder={t('settings.insurance.fields.searchTreatments')}
                                            className="w-full pl-9 pr-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none"
                                        />
                                    </div>
                                    {/* Treatment list */}
                                    <div className="max-h-48 overflow-y-auto rounded-lg border border-white/[0.08] bg-white/[0.02] divide-y divide-white/[0.04]">
                                        {insuranceTreatments.length === 0 ? (
                                            <p className="text-xs text-white/30 p-3 text-center">{t('settings.insurance.fields.noTreatments')}</p>
                                        ) : (
                                            insuranceTreatments
                                                .filter(t => {
                                                    if (!insuranceTreatmentSearch) return true;
                                                    const q = insuranceTreatmentSearch.toLowerCase();
                                                    return t.name.toLowerCase().includes(q) || t.code.toLowerCase().includes(q);
                                                })
                                                .map(treat => {
                                                    const selectedCodes = parseRestrictionsAsCodes(insuranceForm.restrictions);
                                                    const isSelected = selectedCodes.includes(treat.code);
                                                    return (
                                                        <button
                                                            key={treat.code}
                                                            type="button"
                                                            onClick={() => {
                                                                const codes = parseRestrictionsAsCodes(insuranceForm.restrictions);
                                                                const updated = isSelected
                                                                    ? codes.filter(c => c !== treat.code)
                                                                    : [...codes, treat.code];
                                                                setInsuranceForm(p => ({ ...p, restrictions: JSON.stringify(updated) }));
                                                            }}
                                                            className={`w-full flex items-center gap-3 px-3 py-2.5 text-left transition-colors ${isSelected ? 'bg-emerald-500/10' : 'hover:bg-white/[0.04]'}`}
                                                        >
                                                            <div className={`flex-shrink-0 w-5 h-5 rounded border flex items-center justify-center transition-all ${isSelected ? 'bg-emerald-500 border-emerald-500' : 'border-white/20 bg-white/[0.04]'}`}>
                                                                {isSelected && <Check size={12} className="text-white" />}
                                                            </div>
                                                            <div className="flex-1 min-w-0">
                                                                <span className="text-sm text-white font-medium">{treat.name}</span>
                                                                <span className="text-xs text-white/30 ml-2">{treat.code}</span>
                                                            </div>
                                                        </button>
                                                    );
                                                })
                                        )}
                                    </div>
                                    <p className="text-xs text-white/30">
                                        {parseRestrictionsAsCodes(insuranceForm.restrictions).length} {t('settings.insurance.fields.treatmentsSelected')}
                                    </p>
                                </div>
                            )}
                            {insuranceForm.status === 'external_derivation' && (
                                <div className="space-y-1">
                                    <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.externalTarget')}</label>
                                    <input type="text" value={insuranceForm.external_target || ''} onChange={e => setInsuranceForm(p => ({ ...p, external_target: e.target.value }))}
                                        className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none" />
                                </div>
                            )}
                            <div className="flex items-center gap-3">
                                <label className="flex items-center gap-3 cursor-pointer">
                                    <input type="checkbox" checked={insuranceForm.requires_copay ?? true} onChange={e => setInsuranceForm(p => ({ ...p, requires_copay: e.target.checked }))}
                                        className="h-5 w-5 rounded border-white/[0.08] text-blue-400 focus:ring-blue-500" />
                                    <span className="text-sm font-medium text-white/60">{t('settings.insurance.fields.requiresCopay')}</span>
                                </label>
                            </div>
                            {insuranceForm.requires_copay && (
                                <div className="space-y-1">
                                    <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.copayNotes')}</label>
                                    <textarea value={insuranceForm.copay_notes || ''} onChange={e => setInsuranceForm(p => ({ ...p, copay_notes: e.target.value }))} rows={2}
                                        className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none resize-none" />
                                </div>
                            )}
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.aiTemplate')}</label>
                                <textarea value={insuranceForm.ai_response_template || ''} onChange={e => setInsuranceForm(p => ({ ...p, ai_response_template: e.target.value }))} rows={3}
                                    placeholder={t('settings.insurance.fields.aiTemplatePlaceholder')}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none resize-none text-sm" />
                                <p className="text-xs text-white/30">{t('settings.insurance.fields.aiTemplatePlaceholder')}</p>
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button type="button" onClick={() => setInsuranceModalOpen(false)} className="flex-1 py-2 text-white/70 font-medium hover:bg-white/[0.04] rounded-lg transition-all">{t('common.cancel')}</button>
                                <button type="submit" disabled={insuranceSaving} className="flex-1 py-2 bg-white text-[#0a0e1a] font-bold rounded-lg hover:bg-white/90 transition-all disabled:opacity-50 flex items-center justify-center gap-2">
                                    {insuranceSaving ? <Loader2 className="animate-spin" size={18} /> : t('common.save')}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* ── Modal Derivation ── */}
            {derivationModalOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-[#0d1117] border border-white/[0.08] rounded-xl w-full max-w-lg animate-scale-in max-h-[90vh] flex flex-col">
                        <div className="p-4 sm:p-6 border-b border-white/[0.06] shrink-0 flex justify-between items-center">
                            <h2 className="text-lg font-bold text-white flex items-center gap-2">
                                <GitMerge className="text-blue-400" size={20} />
                                {editingDerivation ? t('common.edit') : t('settings.derivation.addButton')}
                            </h2>
                            <button onClick={() => setDerivationModalOpen(false)} className="p-2 hover:bg-white/[0.04] rounded-lg text-white/40"><X size={20} /></button>
                        </div>
                        <form onSubmit={handleDerivationSubmit} className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-4">
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('settings.derivation.fields.ruleName')}</label>
                                <input required type="text" value={derivationForm.rule_name || ''} onChange={e => setDerivationForm(p => ({ ...p, rule_name: e.target.value }))}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none" />
                            </div>
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('settings.derivation.fields.patientCondition')}</label>
                                <select value={derivationForm.patient_condition || 'any'} onChange={e => setDerivationForm(p => ({ ...p, patient_condition: e.target.value as DerivationRule['patient_condition'] }))}
                                    className="w-full px-4 py-2 bg-[#0d1117] border border-white/[0.08] rounded-lg text-white focus:ring-2 focus:ring-blue-500 outline-none [&>option]:bg-[#0d1117]">
                                    <option value="new_patient">{t('settings.derivation.condition.new_patient')}</option>
                                    <option value="existing_patient">{t('settings.derivation.condition.existing_patient')}</option>
                                    <option value="any">{t('settings.derivation.condition.any')}</option>
                                </select>
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-semibold text-white/60">{t('settings.derivation.fields.categories')}</label>
                                <div className="max-h-48 overflow-y-auto border border-white/[0.08] rounded-lg p-3 space-y-1 bg-white/[0.02]">
                                    <label className="flex items-center gap-2 cursor-pointer p-1.5 rounded hover:bg-white/[0.04]">
                                        <input type="checkbox" checked={(derivationForm.treatment_categories || []).includes('*')}
                                            onChange={e => {
                                                if (e.target.checked) setDerivationForm(p => ({ ...p, treatment_categories: ['*'] }));
                                                else setDerivationForm(p => ({ ...p, treatment_categories: [] }));
                                            }}
                                            className="h-4 w-4 rounded border-white/20 text-blue-500 focus:ring-blue-500" />
                                        <span className="text-sm font-bold text-white/80">Todos los tratamientos</span>
                                    </label>
                                    {!(derivationForm.treatment_categories || []).includes('*') && derivationTreatments.map(treat => (
                                        <label key={treat.code} className="flex items-center gap-2 cursor-pointer p-1.5 rounded hover:bg-white/[0.04]">
                                            <input type="checkbox" checked={(derivationForm.treatment_categories || []).includes(treat.code)}
                                                onChange={e => {
                                                    const cats = derivationForm.treatment_categories || [];
                                                    if (e.target.checked) setDerivationForm(p => ({ ...p, treatment_categories: [...cats, treat.code] }));
                                                    else setDerivationForm(p => ({ ...p, treatment_categories: cats.filter(c => c !== treat.code) }));
                                                }}
                                                className="h-4 w-4 rounded border-white/20 text-blue-500 focus:ring-blue-500" />
                                            <span className="text-sm text-white/70">{treat.name}</span>
                                            {treat.priority === 'high' && <span className="text-[9px] px-1.5 py-0.5 rounded bg-red-500/10 text-red-400 font-bold">ALTA</span>}
                                            {treat.priority === 'medium-high' && <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 font-bold">MEDIA-ALTA</span>}
                                        </label>
                                    ))}
                                </div>
                                {derivationTreatments.length === 0 && <p className="text-xs text-white/30">No hay tratamientos configurados aún.</p>}
                            </div>
                            <div className="space-y-2">
                                <label className="text-sm font-semibold text-white/60">{t('settings.derivation.fields.targetType')}</label>
                                <div className="space-y-2">
                                    {(['specific_professional', 'priority_professional', 'team'] as DerivationRule['target_type'][]).map(tt => (
                                        <label key={tt} className="flex items-center gap-3 cursor-pointer p-3 rounded-lg hover:bg-white/[0.02] border border-transparent hover:border-white/[0.06] transition-all">
                                            <input type="radio" name="target_type" value={tt} checked={derivationForm.target_type === tt} onChange={() => setDerivationForm(p => ({ ...p, target_type: tt }))}
                                                className="h-4 w-4 text-blue-400 border-white/[0.08] focus:ring-blue-500" />
                                            <span className="text-sm font-medium text-white/70">{t(`settings.derivation.target.${tt}`)}</span>
                                        </label>
                                    ))}
                                </div>
                            </div>
                            {derivationForm.target_type === 'specific_professional' && (
                                <div className="space-y-1">
                                    <label className="text-sm font-semibold text-white/60">{t('settings.derivation.fields.professional')}</label>
                                    <select value={derivationForm.target_professional_id || ''} onChange={e => setDerivationForm(p => ({ ...p, target_professional_id: e.target.value ? parseInt(e.target.value) : undefined }))}
                                        className="w-full px-4 py-2 bg-[#0d1117] border border-white/[0.08] rounded-lg text-white focus:ring-2 focus:ring-blue-500 outline-none [&>option]:bg-[#0d1117]">
                                        <option value="">—</option>
                                        {derivationProfessionals.map(p => (
                                            <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
                                        ))}
                                    </select>
                                </div>
                            )}
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('settings.derivation.fields.description')}</label>
                                <textarea value={derivationForm.description || ''} onChange={e => setDerivationForm(p => ({ ...p, description: e.target.value }))} rows={2}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none resize-none text-sm" />
                            </div>
                            <div className="flex gap-3 pt-2">
                                <button type="button" onClick={() => setDerivationModalOpen(false)} className="flex-1 py-2 text-white/70 font-medium hover:bg-white/[0.04] rounded-lg transition-all">{t('common.cancel')}</button>
                                <button type="submit" disabled={derivationSaving} className="flex-1 py-2 bg-white text-[#0a0e1a] font-bold rounded-lg hover:bg-white/90 transition-all disabled:opacity-50 flex items-center justify-center gap-2">
                                    {derivationSaving ? <Loader2 className="animate-spin" size={18} /> : t('common.save')}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
