import { useState, useEffect } from 'react';
import { Building2, Plus, Edit, Trash2, Phone, Loader2, AlertCircle, CheckCircle2, Calendar, CalendarX, Clock, MapPin, HelpCircle, ChevronDown, ChevronUp, X, DollarSign, Shield, ShieldAlert, GitMerge, ToggleLeft, ToggleRight, Info, Search, Check, Pencil } from 'lucide-react';
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
    system_prompt_template?: string;
    bot_name?: string | null;
    // Payment & financing (migration 035)
    payment_methods?: string[] | null;
    financing_available?: boolean | null;
    max_installments?: number | null;
    installments_interest_free?: boolean | null;
    financing_provider?: string | null;
    financing_notes?: string | null;
    cash_discount_percent?: number | null;
    accepts_crypto?: boolean | null;
    // Clinic special conditions (migration 036)
    accepts_pregnant_patients?: boolean | null;
    pregnancy_restricted_treatments?: string[] | null;
    pregnancy_notes?: string | null;
    accepts_pediatric?: boolean | null;
    min_pediatric_age_years?: number | null;
    pediatric_notes?: string | null;
    high_risk_protocols?: Record<string, HighRiskProtocolEntry> | null;
    requires_anamnesis_before_booking?: boolean | null;
    // Support / complaints / review config (migration 039)
    complaint_escalation_email?: string | null;
    complaint_escalation_phone?: string | null;
    expected_wait_time_minutes?: number | null;
    revision_policy?: string | null;
    review_platforms?: ReviewPlatformItem[] | null;
    complaint_handling_protocol?: { level_1?: string; level_2?: string; level_3?: string } | null;
    auto_send_review_link_after_followup?: boolean;
    config?: { calendar_provider?: 'local' | 'google' };
    created_at: string;
    updated_at?: string;
}

interface ReviewPlatformItem {
    name: string;
    url: string;
    show_after_days: number;
}

interface HighRiskProtocolEntry {
    requires_medical_clearance: boolean;
    requires_pre_appointment_call: boolean;
    restricted_treatments: string[];
    notes: string;
}

// UI-only flattened shape for the dynamic card editor. Serializa a
// Record<string, HighRiskProtocolEntry> (la condition es la key) al enviar.
interface HighRiskProtocolCard extends HighRiskProtocolEntry {
    condition: string;
}

const ALLOWED_PAYMENT_METHODS = [
    'cash', 'credit_card', 'debit_card', 'transfer', 'mercado_pago',
    'rapipago', 'pagofacil', 'modo', 'uala', 'naranja', 'crypto', 'other',
] as const;
type PaymentMethodToken = typeof ALLOWED_PAYMENT_METHODS[number];

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
    coverage_by_treatment?: Record<string, TreatmentCoverageEntry>;
    is_prepaid?: boolean;
    employee_discount_percent?: number;
    default_copay_percent?: number;
    external_target?: string;
    requires_copay: boolean;
    copay_notes?: string;
    ai_response_template?: string;
    sort_order: number;
    is_active: boolean;
}

interface TreatmentCoverageEntry {
    covered: boolean;
    copay_percent: number;
    requires_pre_authorization: boolean;
    pre_auth_leadtime_days: number;
    waiting_period_days: number;
    max_annual_coverage: number | null;
    notes: string;
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
    // Migration 038 — escalation fallback fields
    enable_escalation?: boolean;
    fallback_professional_id?: number | null;
    fallback_professional_name?: string | null;
    fallback_team_mode?: boolean;
    max_wait_days_before_escalation?: number;
    escalation_message_template?: string | null;
    criteria_custom?: Record<string, unknown> | null;
}

const CALENDAR_PROVIDER_OPTIONS = (t: (k: string) => string) => [
    { value: 'local' as const, label: t('clinics.calendar_local') },
    { value: 'google' as const, label: t('clinics.calendar_google') },
];

// Holidays integration — surfaces existing tenant_holidays infrastructure
// (migrations 010 + 014) inside the Edit Clinic modal as a collapsible
// section. See openspec/changes/clinic-holidays-integration.
interface HolidayItem {
    id?: number;
    date: string;
    name: string;
    holiday_type: 'closure' | 'override_open';
    source: 'library' | 'custom';
    is_recurring?: boolean;
    custom_hours?: { start: string; end: string } | null;
    custom_hours_start?: string | null;
    custom_hours_end?: string | null;
}

interface NewHolidayForm {
    date: string;
    name: string;
    holiday_type: 'closure' | 'override_open';
    custom_hours_start: string;
    custom_hours_end: string;
    is_recurring: boolean;
}

const emptyHolidayForm: NewHolidayForm = {
    date: '',
    name: '',
    holiday_type: 'closure',
    custom_hours_start: '09:00',
    custom_hours_end: '13:00',
    is_recurring: false,
};

export default function ClinicsView() {
    const { t } = useTranslation();
    const [clinicas, setClinicas] = useState<Clinica[]>([]);
    const [loading, setLoading] = useState(true);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingClinica, setEditingClinica] = useState<Clinica | null>(null);
    const [formData, setFormData] = useState({
        clinic_name: '',
        bot_name: '',
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
        system_prompt_template: '',
        working_hours: createDefaultWorkingHours(),
        // Payment & financing (migration 035)
        payment_methods: [] as string[],
        financing_available: false,
        max_installments: '' as string,
        installments_interest_free: true,
        financing_provider: '',
        financing_notes: '',
        cash_discount_percent: '' as string,
        accepts_crypto: false,
        // Clinic special conditions (migration 036)
        accepts_pregnant_patients: true,
        pregnancy_restricted_treatments: [] as string[],
        pregnancy_notes: '',
        accepts_pediatric: true,
        min_pediatric_age_years: '' as string,
        pediatric_notes: '',
        high_risk_protocols: [] as HighRiskProtocolCard[],
        requires_anamnesis_before_booking: false,
        // Migration 039 — support / complaints / review config
        complaint_escalation_email: '',
        complaint_escalation_phone: '',
        expected_wait_time_minutes: '' as string,
        revision_policy: '',
        review_platforms: [] as ReviewPlatformItem[],
        complaint_handling_protocol: { level_1: '', level_2: '', level_3: '' },
        auto_send_review_link_after_followup: false,
    });
    const [expandedDays, setExpandedDays] = useState<string[]>([]);
    const [paymentSectionExpanded, setPaymentSectionExpanded] = useState(false);
    const [specialConditionsExpanded, setSpecialConditionsExpanded] = useState(false);
    const [supportComplaintsExpanded, setSupportComplaintsExpanded] = useState(false);

    // Holidays integration state (pack 4)
    const [holidaysSectionOpen, setHolidaysSectionOpen] = useState(false);
    const [holidayList, setHolidayList] = useState<HolidayItem[]>([]);
    const [holidaysLoading, setHolidaysLoading] = useState(false);
    const [holidaysFetchError, setHolidaysFetchError] = useState<string | null>(null);
    const [newHoliday, setNewHoliday] = useState<NewHolidayForm>({ ...emptyHolidayForm });
    const [addingSaving, setAddingSaving] = useState(false);
    const [addError, setAddError] = useState<string | null>(null);
    const [addSuccess, setAddSuccess] = useState(false);
    const [editingHolidayId, setEditingHolidayId] = useState<number | null>(null);
    const [editHolidayForm, setEditHolidayForm] = useState<NewHolidayForm>({ ...emptyHolidayForm });
    const [deletingHolidayId, setDeletingHolidayId] = useState<number | null>(null);

    const resetHolidaysState = () => {
        setHolidaysSectionOpen(false);
        setHolidayList([]);
        setHolidaysFetchError(null);
        setNewHoliday({ ...emptyHolidayForm });
        setAddError(null);
        setAddSuccess(false);
        setEditingHolidayId(null);
        setDeletingHolidayId(null);
    };

    const fetchHolidays = async () => {
        setHolidaysLoading(true);
        setHolidaysFetchError(null);
        try {
            const res = await api.get('/admin/holidays', { params: { days: 90 } });
            setHolidayList((res.data?.upcoming as HolidayItem[]) || []);
        } catch (e) {
            console.error('Error fetching holidays:', e);
            setHolidaysFetchError(t('clinics.holidays.fetch_error'));
        } finally {
            setHolidaysLoading(false);
        }
    };

    // Fetch holidays when section expands for an existing clinic
    useEffect(() => {
        if (holidaysSectionOpen && editingClinica) {
            fetchHolidays();
        }
    }, [holidaysSectionOpen, editingClinica?.id]);

    // Validate the holiday form per REQ-5.7
    const validateHolidayForm = (form: NewHolidayForm): string | null => {
        if (!form.date) return t('clinics.holidays.date_label') + ' ✖';
        if (!form.name.trim()) return t('clinics.holidays.name_label') + ' ✖';
        if (form.holiday_type === 'override_open') {
            if (!form.custom_hours_start || !form.custom_hours_end) {
                return t('holidays.invalidTimeRange') || 'Horario requerido';
            }
            if (form.custom_hours_start >= form.custom_hours_end) {
                return t('holidays.invalidTimeRange') || 'Horario inválido';
            }
        }
        return null;
    };

    const handleAddHoliday = async () => {
        const err = validateHolidayForm(newHoliday);
        if (err) {
            setAddError(err);
            return;
        }
        setAddError(null);
        setAddingSaving(true);
        try {
            const payload: Record<string, unknown> = {
                date: newHoliday.date,
                name: newHoliday.name.trim(),
                holiday_type: newHoliday.holiday_type,
                is_recurring: newHoliday.is_recurring,
            };
            if (newHoliday.holiday_type === 'override_open') {
                payload.custom_hours_start = newHoliday.custom_hours_start;
                payload.custom_hours_end = newHoliday.custom_hours_end;
            }
            await api.post('/admin/holidays', payload);
            setNewHoliday({ ...emptyHolidayForm });
            setAddSuccess(true);
            await fetchHolidays();
            setTimeout(() => setAddSuccess(false), 2000);
        } catch (e: unknown) {
            const err = e as { response?: { status?: number } };
            if (err?.response?.status === 409) {
                setAddError(t('clinics.holidays.conflict_error'));
            } else {
                setAddError(t('clinics.holidays.fetch_error'));
            }
        } finally {
            setAddingSaving(false);
        }
    };

    const handleDeleteHoliday = async (id: number) => {
        try {
            await api.delete(`/admin/holidays/${id}`);
            setDeletingHolidayId(null);
            await fetchHolidays();
        } catch (e) {
            console.error('Error deleting holiday:', e);
            setHolidaysFetchError(t('clinics.holidays.fetch_error'));
            setDeletingHolidayId(null);
        }
    };

    const startEditHoliday = (h: HolidayItem) => {
        if (!h.id) return;
        setEditingHolidayId(h.id);
        setEditHolidayForm({
            date: h.date,
            name: h.name,
            holiday_type: h.holiday_type,
            custom_hours_start: h.custom_hours?.start || h.custom_hours_start || '09:00',
            custom_hours_end: h.custom_hours?.end || h.custom_hours_end || '13:00',
            is_recurring: h.is_recurring || false,
        });
    };

    const handleSaveEditHoliday = async () => {
        if (!editingHolidayId) return;
        const err = validateHolidayForm(editHolidayForm);
        if (err) {
            setAddError(err);
            return;
        }
        try {
            const payload: Record<string, unknown> = {
                date: editHolidayForm.date,
                name: editHolidayForm.name.trim(),
                holiday_type: editHolidayForm.holiday_type,
                is_recurring: editHolidayForm.is_recurring,
            };
            if (editHolidayForm.holiday_type === 'override_open') {
                payload.custom_hours_start = editHolidayForm.custom_hours_start;
                payload.custom_hours_end = editHolidayForm.custom_hours_end;
            } else {
                payload.custom_hours_start = null;
                payload.custom_hours_end = null;
            }
            await api.put(`/admin/holidays/${editingHolidayId}`, payload);
            setEditingHolidayId(null);
            await fetchHolidays();
        } catch (e) {
            console.error('Error updating holiday:', e);
            setHolidaysFetchError(t('clinics.holidays.fetch_error'));
        }
    };

    const togglePaymentMethod = (method: string) => {
        setFormData(prev => ({
            ...prev,
            payment_methods: prev.payment_methods.includes(method)
                ? prev.payment_methods.filter((m: string) => m !== method)
                : [...prev.payment_methods, method],
        }));
    };

    // High-risk protocols card editor helpers
    const addHighRiskCard = () => {
        setFormData(prev => ({
            ...prev,
            high_risk_protocols: [
                ...prev.high_risk_protocols,
                {
                    condition: '',
                    requires_medical_clearance: false,
                    requires_pre_appointment_call: false,
                    restricted_treatments: [],
                    notes: '',
                },
            ],
        }));
    };
    const updateHighRiskCard = (
        index: number,
        patch: Partial<HighRiskProtocolCard>,
    ) => {
        setFormData(prev => ({
            ...prev,
            high_risk_protocols: prev.high_risk_protocols.map((card, i) =>
                i === index ? { ...card, ...patch } : card,
            ),
        }));
    };
    const removeHighRiskCard = (index: number) => {
        setFormData(prev => ({
            ...prev,
            high_risk_protocols: prev.high_risk_protocols.filter((_, i) => i !== index),
        }));
    };
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
        coverage_by_treatment: {}, is_prepaid: false, default_copay_percent: undefined, employee_discount_percent: undefined,
    });
    const [insuranceSaving, setInsuranceSaving] = useState(false);
    const [insuranceTreatments, setInsuranceTreatments] = useState<{code: string; name: string}[]>([]);
    const [insuranceTreatmentSearch, setInsuranceTreatmentSearch] = useState('');
    const [coverageMatrixExpanded, setCoverageMatrixExpanded] = useState(false);

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
                bot_name: clinica.bot_name || '',
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
                system_prompt_template: clinica.system_prompt_template || '',
                working_hours: parseWorkingHours(clinica.working_hours),
                // Payment & financing (migration 035)
                payment_methods: Array.isArray(clinica.payment_methods) ? clinica.payment_methods : [],
                financing_available: Boolean(clinica.financing_available),
                max_installments: clinica.max_installments != null ? String(clinica.max_installments) : '',
                installments_interest_free: clinica.installments_interest_free != null ? Boolean(clinica.installments_interest_free) : true,
                financing_provider: clinica.financing_provider || '',
                financing_notes: clinica.financing_notes || '',
                cash_discount_percent: clinica.cash_discount_percent != null ? String(clinica.cash_discount_percent) : '',
                accepts_crypto: Boolean(clinica.accepts_crypto),
                // Clinic special conditions (migration 036)
                accepts_pregnant_patients: clinica.accepts_pregnant_patients != null
                    ? Boolean(clinica.accepts_pregnant_patients)
                    : true,
                pregnancy_restricted_treatments: Array.isArray(clinica.pregnancy_restricted_treatments)
                    ? clinica.pregnancy_restricted_treatments
                    : [],
                pregnancy_notes: clinica.pregnancy_notes || '',
                accepts_pediatric: clinica.accepts_pediatric != null
                    ? Boolean(clinica.accepts_pediatric)
                    : true,
                min_pediatric_age_years: clinica.min_pediatric_age_years != null
                    ? String(clinica.min_pediatric_age_years)
                    : '',
                pediatric_notes: clinica.pediatric_notes || '',
                high_risk_protocols: clinica.high_risk_protocols
                    ? Object.entries(clinica.high_risk_protocols).map(([condition, entry]) => ({
                        condition,
                        requires_medical_clearance: Boolean(entry.requires_medical_clearance),
                        requires_pre_appointment_call: Boolean(entry.requires_pre_appointment_call),
                        restricted_treatments: Array.isArray(entry.restricted_treatments)
                            ? entry.restricted_treatments
                            : [],
                        notes: entry.notes || '',
                    }))
                    : [],
                requires_anamnesis_before_booking: Boolean(clinica.requires_anamnesis_before_booking),
                // Migration 039 — support / complaints / review config
                complaint_escalation_email: clinica.complaint_escalation_email || '',
                complaint_escalation_phone: clinica.complaint_escalation_phone || '',
                expected_wait_time_minutes: clinica.expected_wait_time_minutes != null ? String(clinica.expected_wait_time_minutes) : '',
                revision_policy: clinica.revision_policy || '',
                review_platforms: Array.isArray(clinica.review_platforms) ? clinica.review_platforms : [],
                complaint_handling_protocol: clinica.complaint_handling_protocol || { level_1: '', level_2: '', level_3: '' },
                auto_send_review_link_after_followup: Boolean(clinica.auto_send_review_link_after_followup),
            });
        } else {
            setEditingClinica(null);
            setFormData({
                clinic_name: '', bot_name: '', bot_phone_number: '', calendar_provider: 'local',
                address: '', google_maps_url: '', consultation_price: '',
                bank_cbu: '', bank_alias: '', bank_holder_name: '', derivation_email: '',
                max_chairs: '2', country_code: 'US', system_prompt_template: '',
                working_hours: createDefaultWorkingHours(),
                payment_methods: [], financing_available: false, max_installments: '',
                installments_interest_free: true, financing_provider: '', financing_notes: '',
                cash_discount_percent: '', accepts_crypto: false,
                // Clinic special conditions (migration 036)
                accepts_pregnant_patients: true,
                pregnancy_restricted_treatments: [],
                pregnancy_notes: '',
                accepts_pediatric: true,
                min_pediatric_age_years: '',
                pediatric_notes: '',
                high_risk_protocols: [],
                requires_anamnesis_before_booking: false,
                // Migration 039 defaults
                complaint_escalation_email: '',
                complaint_escalation_phone: '',
                expected_wait_time_minutes: '',
                revision_policy: '',
                review_platforms: [],
                complaint_handling_protocol: { level_1: '', level_2: '', level_3: '' },
                auto_send_review_link_after_followup: false,
            });
        }
        setPaymentSectionExpanded(false);
        setSpecialConditionsExpanded(false);
        setSupportComplaintsExpanded(false);
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
                bot_name: formData.bot_name.trim() || null,
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
                system_prompt_template: formData.system_prompt_template || null,
                working_hours: formData.working_hours,
                // Payment & financing (migration 035)
                payment_methods: formData.payment_methods.length > 0 ? formData.payment_methods : [],
                financing_available: formData.financing_available,
                max_installments: formData.max_installments !== '' ? Number(formData.max_installments) : null,
                installments_interest_free: formData.installments_interest_free,
                financing_provider: formData.financing_provider || null,
                financing_notes: formData.financing_notes || null,
                cash_discount_percent: formData.cash_discount_percent !== '' ? Number(formData.cash_discount_percent) : null,
                accepts_crypto: formData.accepts_crypto,
                // Clinic special conditions (migration 036)
                accepts_pregnant_patients: formData.accepts_pregnant_patients,
                pregnancy_restricted_treatments: formData.pregnancy_restricted_treatments,
                pregnancy_notes: formData.pregnancy_notes || null,
                accepts_pediatric: formData.accepts_pediatric,
                min_pediatric_age_years: formData.min_pediatric_age_years !== ''
                    ? parseInt(formData.min_pediatric_age_years, 10)
                    : null,
                pediatric_notes: formData.pediatric_notes || null,
                // Serializamos el array de cards a Record<string, HighRiskProtocolEntry>.
                // Las cards sin condition válida se descartan silenciosamente.
                high_risk_protocols: formData.high_risk_protocols.reduce<Record<string, HighRiskProtocolEntry>>(
                    (acc, card) => {
                        const key = card.condition.trim().toLowerCase().replace(/\s+/g, '_');
                        if (!key) return acc;
                        acc[key] = {
                            requires_medical_clearance: card.requires_medical_clearance,
                            requires_pre_appointment_call: card.requires_pre_appointment_call,
                            restricted_treatments: card.restricted_treatments,
                            notes: card.notes,
                        };
                        return acc;
                    },
                    {},
                ),
                requires_anamnesis_before_booking: formData.requires_anamnesis_before_booking,
                // Migration 039 — support / complaints / review config
                complaint_escalation_email: formData.complaint_escalation_email.trim() || null,
                complaint_escalation_phone: formData.complaint_escalation_phone.trim() || null,
                expected_wait_time_minutes: formData.expected_wait_time_minutes !== ''
                    ? parseInt(formData.expected_wait_time_minutes, 10)
                    : null,
                revision_policy: formData.revision_policy.trim() || null,
                review_platforms: formData.review_platforms.length > 0 ? formData.review_platforms : null,
                complaint_handling_protocol: (
                    formData.complaint_handling_protocol.level_1
                    || formData.complaint_handling_protocol.level_2
                    || formData.complaint_handling_protocol.level_3
                ) ? formData.complaint_handling_protocol : null,
                auto_send_review_link_after_followup: formData.auto_send_review_link_after_followup,
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
            resetHolidaysState();
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
            // Convert legacy restrictions JSON string to coverage_by_treatment if needed
            let coverage: Record<string, TreatmentCoverageEntry> = {};
            if (item.coverage_by_treatment) {
                coverage = item.coverage_by_treatment;
            } else if (item.restrictions) {
                // Legacy migration: convert old restrictions array to coverage entries
                try {
                    const codes = JSON.parse(item.restrictions);
                    codes.forEach((code: string) => {
                        coverage[code] = { covered: true, copay_percent: 0, requires_pre_authorization: false, pre_auth_leadtime_days: 0, waiting_period_days: 0, max_annual_coverage: null, notes: '' };
                    });
                } catch { coverage = {}; }
            }
            setInsuranceForm({ ...item, coverage_by_treatment: coverage });
        } else {
            setEditingInsurance(null);
            setInsuranceForm({ provider_name: '', status: 'accepted', requires_copay: true, sort_order: 0, is_active: true, coverage_by_treatment: {}, is_prepaid: false, default_copay_percent: undefined, employee_discount_percent: undefined });
        }
        setInsuranceTreatmentSearch('');
        setCoverageMatrixExpanded(false);
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
            // Spread + ensure migration 038 escalation fields have defaults
            setDerivationForm({
                ...item,
                enable_escalation: !!item.enable_escalation,
                max_wait_days_before_escalation: item.max_wait_days_before_escalation ?? 7,
                fallback_team_mode: !!item.fallback_team_mode,
            });
        } else {
            setEditingDerivation(null);
            setDerivationForm({
                rule_name: '',
                patient_condition: 'any',
                treatment_categories: [],
                target_type: 'team',
                is_active: true,
                // Migration 038 defaults
                enable_escalation: false,
                fallback_team_mode: false,
                max_wait_days_before_escalation: 7,
                escalation_message_template: null,
            });
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
                            <button onClick={() => { setIsModalOpen(false); resetHolidaysState(); }} className="p-2 hover:bg-white/[0.04] rounded-lg text-white/40"><X size={20} /></button>
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
                                        className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 font-mono focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                        value={formData.bot_phone_number} onChange={(e) => { const v = e.target.value; setFormData(prev => ({ ...prev, bot_phone_number: v })); }} />
                                </div>
                            </div>

                            {/* Nombre del bot (migration 033) */}
                            <div className="space-y-1">
                                <label className="text-sm font-semibold text-white/60">{t('clinics.bot_name_label')}</label>
                                <input type="text" maxLength={50} placeholder={t('clinics.bot_name_placeholder')}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none"
                                    value={formData.bot_name} onChange={(e) => { const v = e.target.value; setFormData(prev => ({ ...prev, bot_name: v })); }} />
                                <p className="text-xs text-white/40 mt-1">{t('clinics.bot_name_helper')}</p>
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

                            {/* Presentación de la clínica (system_prompt_template) */}
                            <div className="space-y-1 border-t border-white/[0.06] pt-4 mt-4">
                                <label className="text-sm font-semibold text-white/60">{t('clinics.system_prompt_template')}</label>
                                <textarea
                                    rows={6}
                                    placeholder={t('clinics.system_prompt_template_placeholder')}
                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm resize-y"
                                    value={formData.system_prompt_template}
                                    onChange={(e) => setFormData(prev => ({ ...prev, system_prompt_template: e.target.value }))}
                                />
                                <p className="text-xs text-white/30">{t('clinics.system_prompt_template_help')}</p>
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

                            {/* Pagos y Financiación (migration 035) */}
                            <div className="space-y-3 border-t border-white/[0.06] pt-4 mt-4">
                                <div
                                    className="flex items-center justify-between cursor-pointer"
                                    onClick={() => setPaymentSectionExpanded(v => !v)}
                                >
                                    <h3 className="text-sm font-bold text-white/60 flex items-center gap-2">
                                        <DollarSign size={14} /> {t('clinics.payment_section')}
                                    </h3>
                                    <ChevronDown
                                        size={14}
                                        className={`text-white/40 transition-transform ${paymentSectionExpanded ? 'rotate-180' : ''}`}
                                    />
                                </div>
                                <p className="text-xs text-white/30">{t('clinics.payment_section_help')}</p>

                                {paymentSectionExpanded && (
                                    <div className="space-y-4">
                                        {/* Medios de pago */}
                                        <div className="space-y-2">
                                            <label className="text-xs font-medium text-blue-400">{t('clinics.payment_methods_label')}</label>
                                            <div className="grid grid-cols-2 gap-2 mt-2">
                                                {ALLOWED_PAYMENT_METHODS.map(method => (
                                                    <label key={method} className="flex items-center gap-2 text-sm text-white/70">
                                                        <input
                                                            type="checkbox"
                                                            checked={formData.payment_methods.includes(method)}
                                                            onChange={() => togglePaymentMethod(method)}
                                                            className="accent-blue-500"
                                                        />
                                                        {t(`clinics.payment_method_${method}`)}
                                                    </label>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Financiación toggle */}
                                        <div>
                                            <label className="flex items-center gap-2 text-sm text-white/70">
                                                <input
                                                    type="checkbox"
                                                    checked={formData.financing_available}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, financing_available: e.target.checked }))}
                                                    className="accent-blue-500"
                                                />
                                                {t('clinics.financing_available_label')}
                                            </label>
                                        </div>

                                        {/* Sub-bloque de financiación (condicional) */}
                                        {formData.financing_available && (
                                            <div className="space-y-3 pl-4 border-l border-white/[0.06] mt-2">
                                                <div className="space-y-1">
                                                    <label className="text-xs font-medium text-blue-400">{t('clinics.max_installments_label')}</label>
                                                    <input
                                                        type="number"
                                                        min={1}
                                                        max={24}
                                                        placeholder="6"
                                                        className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                                        value={formData.max_installments}
                                                        onChange={(e) => setFormData(prev => ({ ...prev, max_installments: e.target.value }))}
                                                    />
                                                </div>
                                                <label className="flex items-center gap-2 text-sm text-white/70">
                                                    <input
                                                        type="checkbox"
                                                        checked={formData.installments_interest_free}
                                                        onChange={(e) => setFormData(prev => ({ ...prev, installments_interest_free: e.target.checked }))}
                                                        className="accent-blue-500"
                                                    />
                                                    {t('clinics.installments_interest_free_label')}
                                                </label>
                                                <div className="space-y-1">
                                                    <label className="text-xs font-medium text-blue-400">{t('clinics.financing_provider_label')}</label>
                                                    <input
                                                        type="text"
                                                        placeholder="Mercado Pago"
                                                        className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                                        value={formData.financing_provider}
                                                        onChange={(e) => setFormData(prev => ({ ...prev, financing_provider: e.target.value }))}
                                                    />
                                                </div>
                                                <div className="space-y-1">
                                                    <label className="text-xs font-medium text-blue-400">{t('clinics.financing_notes_label')}</label>
                                                    <textarea
                                                        rows={2}
                                                        placeholder={t('clinics.financing_notes_placeholder')}
                                                        className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                                        value={formData.financing_notes}
                                                        onChange={(e) => setFormData(prev => ({ ...prev, financing_notes: e.target.value }))}
                                                    />
                                                </div>
                                            </div>
                                        )}

                                        {/* Descuento por efectivo */}
                                        <div className="space-y-1">
                                            <label className="text-xs font-medium text-blue-400">{t('clinics.cash_discount_label')}</label>
                                            <input
                                                type="number"
                                                min={0}
                                                max={100}
                                                step={0.01}
                                                placeholder="10"
                                                className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                                value={formData.cash_discount_percent}
                                                onChange={(e) => setFormData(prev => ({ ...prev, cash_discount_percent: e.target.value }))}
                                            />
                                        </div>

                                        {/* Crypto toggle */}
                                        <label className="flex items-center gap-2 text-sm text-white/70">
                                            <input
                                                type="checkbox"
                                                checked={formData.accepts_crypto}
                                                onChange={(e) => setFormData(prev => ({ ...prev, accepts_crypto: e.target.checked }))}
                                                className="accent-blue-500"
                                            />
                                            {t('clinics.accepts_crypto_label')}
                                        </label>
                                    </div>
                                )}
                            </div>

                            {/* Condiciones Especiales (migration 036) */}
                            <div className="space-y-3 border-t border-white/[0.06] pt-4 mt-4">
                                <div
                                    className="flex items-center justify-between cursor-pointer"
                                    onClick={() => setSpecialConditionsExpanded(v => !v)}
                                >
                                    <h3 className="text-sm font-bold text-white/70 flex items-center gap-2">
                                        <ShieldAlert size={14} className="text-amber-400" /> {t('clinics.special_conditions_section')}
                                    </h3>
                                    <ChevronDown
                                        size={14}
                                        className={`text-white/40 transition-transform ${specialConditionsExpanded ? 'rotate-180' : ''}`}
                                    />
                                </div>

                                {specialConditionsExpanded && (
                                    <div className="space-y-6">
                                        {/* Legal disclaimer — always visible when section is expanded */}
                                        <p className="text-xs text-amber-400/80 bg-amber-500/5 border border-amber-500/20 rounded-lg p-3">
                                            {t('clinics.special_conditions_disclaimer')}
                                        </p>

                                        {/* Pregnancy sub-block */}
                                        <div className="space-y-3">
                                            <h4 className="text-xs font-bold text-white/50 uppercase tracking-wide">
                                                {t('clinics.pregnancy_subsection')}
                                            </h4>
                                            <label className="flex items-center gap-2 text-sm text-white/70">
                                                <input
                                                    type="checkbox"
                                                    checked={formData.accepts_pregnant_patients}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, accepts_pregnant_patients: e.target.checked }))}
                                                    className="accent-blue-500"
                                                />
                                                {t('clinics.accepts_pregnant')}
                                            </label>
                                            <div className="space-y-1">
                                                <label className="text-xs font-medium text-blue-400">
                                                    {t('clinics.pregnancy_restricted_label')}
                                                </label>
                                                <input
                                                    type="text"
                                                    placeholder="xray_panoramic, whitening"
                                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm font-mono"
                                                    value={formData.pregnancy_restricted_treatments.join(', ')}
                                                    onChange={(e) => setFormData(prev => ({
                                                        ...prev,
                                                        pregnancy_restricted_treatments: e.target.value
                                                            .split(',')
                                                            .map(s => s.trim())
                                                            .filter(Boolean),
                                                    }))}
                                                />
                                                <p className="text-xs text-white/30">{t('clinics.pregnancy_restricted_help')}</p>
                                            </div>
                                            <div className="space-y-1">
                                                <label className="text-xs font-medium text-blue-400">
                                                    {t('clinics.pregnancy_notes_label')}
                                                </label>
                                                <textarea
                                                    rows={3}
                                                    placeholder={t('clinics.pregnancy_notes_placeholder')}
                                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                                    value={formData.pregnancy_notes}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, pregnancy_notes: e.target.value }))}
                                                />
                                                <p className="text-xs text-amber-400/60">{t('clinics.pregnancy_notes_help')}</p>
                                            </div>
                                        </div>

                                        {/* Pediatric sub-block */}
                                        <div className="space-y-3">
                                            <h4 className="text-xs font-bold text-white/50 uppercase tracking-wide">
                                                {t('clinics.pediatric_subsection')}
                                            </h4>
                                            <label className="flex items-center gap-2 text-sm text-white/70">
                                                <input
                                                    type="checkbox"
                                                    checked={formData.accepts_pediatric}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, accepts_pediatric: e.target.checked }))}
                                                    className="accent-blue-500"
                                                />
                                                {t('clinics.accepts_pediatric')}
                                            </label>
                                            <div className="space-y-1">
                                                <label className="text-xs font-medium text-blue-400">
                                                    {t('clinics.min_pediatric_age_label')}
                                                </label>
                                                <input
                                                    type="number"
                                                    min={0}
                                                    placeholder="6"
                                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                                    value={formData.min_pediatric_age_years}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, min_pediatric_age_years: e.target.value }))}
                                                />
                                            </div>
                                            <div className="space-y-1">
                                                <label className="text-xs font-medium text-blue-400">
                                                    {t('clinics.pediatric_notes_label')}
                                                </label>
                                                <textarea
                                                    rows={2}
                                                    placeholder={t('clinics.pediatric_notes_placeholder')}
                                                    className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                                    value={formData.pediatric_notes}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, pediatric_notes: e.target.value }))}
                                                />
                                            </div>
                                        </div>

                                        {/* High-risk protocols dynamic card editor */}
                                        <div className="space-y-3">
                                            <div className="flex items-center justify-between">
                                                <h4 className="text-xs font-bold text-white/50 uppercase tracking-wide">
                                                    {t('clinics.high_risk_subsection')}
                                                </h4>
                                                <button
                                                    type="button"
                                                    onClick={addHighRiskCard}
                                                    className="px-3 py-1 rounded-md bg-white/[0.06] hover:bg-white/[0.10] text-xs text-white/70 flex items-center gap-1"
                                                >
                                                    <Plus size={12} /> {t('clinics.high_risk_add_button')}
                                                </button>
                                            </div>
                                            <p className="text-xs text-white/30">{t('clinics.high_risk_help')}</p>
                                            <div className="space-y-3">
                                                {formData.high_risk_protocols.length === 0 && (
                                                    <p className="text-xs text-white/30 italic">{t('clinics.high_risk_empty')}</p>
                                                )}
                                                {formData.high_risk_protocols.map((card, idx) => (
                                                    <div
                                                        key={idx}
                                                        className="space-y-2 p-3 rounded-lg border border-white/[0.06] bg-white/[0.02]"
                                                    >
                                                        <div className="flex items-center gap-2">
                                                            <input
                                                                type="text"
                                                                placeholder={t('clinics.high_risk_condition_placeholder')}
                                                                className="flex-1 px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-md text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-sm"
                                                                value={card.condition}
                                                                onChange={(e) => updateHighRiskCard(idx, { condition: e.target.value })}
                                                            />
                                                            <button
                                                                type="button"
                                                                onClick={() => removeHighRiskCard(idx)}
                                                                className="p-1.5 rounded-md text-red-400/70 hover:text-red-400 hover:bg-red-500/10"
                                                                title={t('clinics.high_risk_remove')}
                                                            >
                                                                <Trash2 size={14} />
                                                            </button>
                                                        </div>
                                                        <label className="flex items-center gap-2 text-xs text-white/70">
                                                            <input
                                                                type="checkbox"
                                                                checked={card.requires_medical_clearance}
                                                                onChange={(e) => updateHighRiskCard(idx, { requires_medical_clearance: e.target.checked })}
                                                                className="accent-blue-500"
                                                            />
                                                            {t('clinics.high_risk_clearance')}
                                                        </label>
                                                        <label className="flex items-center gap-2 text-xs text-white/70">
                                                            <input
                                                                type="checkbox"
                                                                checked={card.requires_pre_appointment_call}
                                                                onChange={(e) => updateHighRiskCard(idx, { requires_pre_appointment_call: e.target.checked })}
                                                                className="accent-blue-500"
                                                            />
                                                            {t('clinics.high_risk_pre_call')}
                                                        </label>
                                                        <div className="space-y-1">
                                                            <label className="text-xs font-medium text-blue-400">
                                                                {t('clinics.high_risk_restricted_label')}
                                                            </label>
                                                            <input
                                                                type="text"
                                                                placeholder="surgery_implant"
                                                                className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-md text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-xs font-mono"
                                                                value={card.restricted_treatments.join(', ')}
                                                                onChange={(e) => updateHighRiskCard(idx, {
                                                                    restricted_treatments: e.target.value
                                                                        .split(',')
                                                                        .map(s => s.trim())
                                                                        .filter(Boolean),
                                                                })}
                                                            />
                                                        </div>
                                                        <textarea
                                                            rows={2}
                                                            placeholder={t('clinics.high_risk_notes_placeholder')}
                                                            className="w-full px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-md text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none text-xs"
                                                            value={card.notes}
                                                            onChange={(e) => updateHighRiskCard(idx, { notes: e.target.value })}
                                                        />
                                                    </div>
                                                ))}
                                            </div>
                                        </div>

                                        {/* Anamnesis gate */}
                                        <div className="space-y-2 border-t border-white/[0.06] pt-4">
                                            <label className="flex items-center gap-2 text-sm text-white/70">
                                                <input
                                                    type="checkbox"
                                                    checked={formData.requires_anamnesis_before_booking}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, requires_anamnesis_before_booking: e.target.checked }))}
                                                    className="accent-blue-500"
                                                />
                                                {t('clinics.requires_anamnesis_label')}
                                            </label>
                                            <p className="text-xs text-white/30">{t('clinics.requires_anamnesis_help')}</p>
                                        </div>
                                    </div>
                                )}
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

                            {/* ── Holidays section (pack 4, only when editing an existing clinic) ── */}
                            {editingClinica && (
                                <div className="space-y-2 border-t border-white/[0.06] pt-5">
                                    <button
                                        type="button"
                                        onClick={() => setHolidaysSectionOpen(s => !s)}
                                        className="w-full flex items-center justify-between gap-3 text-left group"
                                    >
                                        <div className="flex items-center gap-3">
                                            <CalendarX size={18} className="text-amber-400" />
                                            <div>
                                                <h3 className="text-sm font-bold text-white">
                                                    {t('clinics.holidays.section_title')}
                                                    {holidayList.filter(h => h.source === 'custom').length > 0 && (
                                                        <span className="ml-2 text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-300">
                                                            {holidayList.filter(h => h.source === 'custom').length}
                                                        </span>
                                                    )}
                                                </h3>
                                                <p className="text-xs text-white/40">{t('clinics.holidays.section_subtitle')}</p>
                                            </div>
                                        </div>
                                        {holidaysSectionOpen
                                            ? <ChevronUp size={18} className="text-white/40 group-hover:text-white/60" />
                                            : <ChevronDown size={18} className="text-white/40 group-hover:text-white/60" />}
                                    </button>

                                    {holidaysSectionOpen && (
                                        <div className="space-y-4 pt-4">
                                            {/* List */}
                                            {holidaysLoading ? (
                                                <div className="flex items-center justify-center py-4">
                                                    <Loader2 size={18} className="text-amber-400 animate-spin" />
                                                </div>
                                            ) : holidaysFetchError ? (
                                                <div className="text-xs text-red-400 px-3 py-2 bg-red-500/10 border border-red-500/20 rounded-lg">
                                                    {holidaysFetchError}
                                                </div>
                                            ) : holidayList.length === 0 ? (
                                                <div className="text-xs text-white/40 px-3 py-3 bg-white/[0.02] border border-white/[0.06] rounded-lg text-center">
                                                    {t('clinics.holidays.empty_message')}
                                                </div>
                                            ) : (
                                                <div className="space-y-1.5 max-h-60 overflow-y-auto pr-1">
                                                    {holidayList.map((h, idx) => {
                                                        const isEditing = editingHolidayId === h.id;
                                                        const isConfirmDelete = deletingHolidayId === h.id;
                                                        if (isEditing) {
                                                            return (
                                                                <div key={`edit-${h.id}`} className="bg-white/[0.04] border border-amber-500/30 rounded-lg p-3 space-y-2">
                                                                    <div className="grid grid-cols-2 gap-2">
                                                                        <input type="date" value={editHolidayForm.date}
                                                                            onChange={e => setEditHolidayForm(prev => ({ ...prev, date: e.target.value }))}
                                                                            className="px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs" />
                                                                        <select value={editHolidayForm.holiday_type}
                                                                            onChange={e => setEditHolidayForm(prev => ({ ...prev, holiday_type: e.target.value as 'closure' | 'override_open' }))}
                                                                            className="px-2 py-1.5 bg-[#0d1117] border border-white/[0.08] rounded text-white text-xs [&>option]:bg-[#0d1117]">
                                                                            <option value="closure">{t('clinics.holidays.type_closure')}</option>
                                                                            <option value="override_open">{t('clinics.holidays.type_override_open')}</option>
                                                                        </select>
                                                                    </div>
                                                                    <input type="text" placeholder={t('clinics.holidays.name_label')} value={editHolidayForm.name}
                                                                        onChange={e => setEditHolidayForm(prev => ({ ...prev, name: e.target.value }))}
                                                                        className="w-full px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs" />
                                                                    {editHolidayForm.holiday_type === 'override_open' && (
                                                                        <div className="grid grid-cols-2 gap-2">
                                                                            <input type="time" value={editHolidayForm.custom_hours_start}
                                                                                onChange={e => setEditHolidayForm(prev => ({ ...prev, custom_hours_start: e.target.value }))}
                                                                                className="px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs" />
                                                                            <input type="time" value={editHolidayForm.custom_hours_end}
                                                                                onChange={e => setEditHolidayForm(prev => ({ ...prev, custom_hours_end: e.target.value }))}
                                                                                className="px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs" />
                                                                        </div>
                                                                    )}
                                                                    <div className="flex gap-2">
                                                                        <button type="button" onClick={handleSaveEditHoliday}
                                                                            className="flex-1 py-1 text-xs font-semibold bg-amber-500 text-[#0a0e1a] rounded hover:bg-amber-400">
                                                                            {t('common.save')}
                                                                        </button>
                                                                        <button type="button" onClick={() => setEditingHolidayId(null)}
                                                                            className="flex-1 py-1 text-xs text-white/60 hover:bg-white/[0.04] rounded">
                                                                            {t('common.cancel')}
                                                                        </button>
                                                                    </div>
                                                                </div>
                                                            );
                                                        }
                                                        if (isConfirmDelete && h.id) {
                                                            return (
                                                                <div key={`del-${h.id}`} className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center gap-2">
                                                                    <span className="text-xs text-red-300 flex-1">{t('clinics.holidays.delete_confirm')}</span>
                                                                    <button type="button" onClick={() => handleDeleteHoliday(h.id!)}
                                                                        className="px-2 py-1 text-xs font-semibold bg-red-500 text-white rounded hover:bg-red-400">
                                                                        {t('common.confirm') || 'Confirmar'}
                                                                    </button>
                                                                    <button type="button" onClick={() => setDeletingHolidayId(null)}
                                                                        className="px-2 py-1 text-xs text-white/60 hover:bg-white/[0.04] rounded">
                                                                        {t('common.cancel')}
                                                                    </button>
                                                                </div>
                                                            );
                                                        }
                                                        return (
                                                            <div key={`h-${h.id || idx}-${h.date}`} className="bg-white/[0.02] border border-white/[0.06] rounded-lg px-3 py-2 flex items-center gap-2">
                                                                <div className="flex-1 min-w-0">
                                                                    <div className="flex items-center gap-2 flex-wrap">
                                                                        <span className="text-xs font-mono text-white/50 shrink-0">{h.date}</span>
                                                                        <span className="text-sm text-white font-medium truncate">{h.name}</span>
                                                                    </div>
                                                                    <div className="flex items-center gap-1.5 mt-1">
                                                                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${h.holiday_type === 'closure' ? 'bg-red-500/10 text-red-400' : 'bg-blue-500/10 text-blue-400'}`}>
                                                                            {h.holiday_type === 'closure' ? t('clinics.holidays.type_closure') : t('clinics.holidays.type_override_open')}
                                                                        </span>
                                                                        <span className={`text-[10px] px-1.5 py-0.5 rounded font-semibold ${h.source === 'custom' ? 'bg-amber-500/10 text-amber-400' : 'bg-white/[0.05] text-white/40'}`}>
                                                                            {h.source === 'custom' ? t('clinics.holidays.source_custom') : t('clinics.holidays.source_national')}
                                                                        </span>
                                                                        {h.custom_hours && (
                                                                            <span className="text-[10px] text-white/40">
                                                                                {h.custom_hours.start}–{h.custom_hours.end}
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                </div>
                                                                {h.source === 'custom' && h.id && (
                                                                    <div className="flex gap-1 shrink-0">
                                                                        <button type="button" onClick={() => startEditHoliday(h)}
                                                                            className="p-1.5 text-white/30 hover:text-amber-400 hover:bg-amber-500/10 rounded" title={t('common.edit') || 'Editar'}>
                                                                            <Pencil size={13} />
                                                                        </button>
                                                                        <button type="button" onClick={() => setDeletingHolidayId(h.id!)}
                                                                            className="p-1.5 text-white/30 hover:text-red-400 hover:bg-red-500/10 rounded" title={t('common.delete') || 'Eliminar'}>
                                                                            <X size={13} />
                                                                        </button>
                                                                    </div>
                                                                )}
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            )}

                                            {/* Add form */}
                                            <div className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-3 space-y-2">
                                                <h4 className="text-xs font-semibold text-white/60 uppercase tracking-wider">
                                                    {t('clinics.holidays.add_form_title')}
                                                </h4>
                                                <div className="grid grid-cols-2 gap-2">
                                                    <input type="date" value={newHoliday.date}
                                                        onChange={e => setNewHoliday(prev => ({ ...prev, date: e.target.value }))}
                                                        min={new Date().toISOString().split('T')[0]}
                                                        className="px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs outline-none focus:ring-1 focus:ring-amber-400/40" />
                                                    <select value={newHoliday.holiday_type}
                                                        onChange={e => setNewHoliday(prev => ({ ...prev, holiday_type: e.target.value as 'closure' | 'override_open' }))}
                                                        className="px-2 py-1.5 bg-[#0d1117] border border-white/[0.08] rounded text-white text-xs [&>option]:bg-[#0d1117] outline-none focus:ring-1 focus:ring-amber-400/40">
                                                        <option value="closure">{t('clinics.holidays.type_closure')}</option>
                                                        <option value="override_open">{t('clinics.holidays.type_override_open')}</option>
                                                    </select>
                                                </div>
                                                <input type="text" placeholder={t('clinics.holidays.name_label')} value={newHoliday.name}
                                                    onChange={e => setNewHoliday(prev => ({ ...prev, name: e.target.value }))}
                                                    className="w-full px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs outline-none focus:ring-1 focus:ring-amber-400/40" />
                                                {newHoliday.holiday_type === 'override_open' && (
                                                    <div className="grid grid-cols-2 gap-2">
                                                        <input type="time" value={newHoliday.custom_hours_start}
                                                            onChange={e => setNewHoliday(prev => ({ ...prev, custom_hours_start: e.target.value }))}
                                                            className="px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs" />
                                                        <input type="time" value={newHoliday.custom_hours_end}
                                                            onChange={e => setNewHoliday(prev => ({ ...prev, custom_hours_end: e.target.value }))}
                                                            className="px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs" />
                                                    </div>
                                                )}
                                                <label className="flex items-center gap-2 cursor-pointer">
                                                    <input type="checkbox" checked={newHoliday.is_recurring}
                                                        onChange={e => setNewHoliday(prev => ({ ...prev, is_recurring: e.target.checked }))}
                                                        className="h-3.5 w-3.5 rounded border-white/[0.08] text-amber-400 focus:ring-amber-500" />
                                                    <span className="text-xs text-white/60">{t('clinics.holidays.is_recurring_label')}</span>
                                                </label>
                                                {addError && (
                                                    <p className="text-xs text-red-400">{addError}</p>
                                                )}
                                                {addSuccess && (
                                                    <p className="text-xs text-emerald-400">{t('clinics.holidays.add_success')}</p>
                                                )}
                                                <button type="button" onClick={handleAddHoliday} disabled={addingSaving}
                                                    className="w-full py-1.5 text-xs font-semibold bg-amber-500 text-[#0a0e1a] rounded hover:bg-amber-400 disabled:opacity-50 flex items-center justify-center gap-1">
                                                    {addingSaving ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                                                    {t('clinics.holidays.add_button')}
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* ── Support / Complaints / Reviews section (migration 039) ── */}
                            <div className="space-y-2 border-t border-white/[0.06] pt-5">
                                <button
                                    type="button"
                                    onClick={() => setSupportComplaintsExpanded(s => !s)}
                                    className="w-full flex items-center justify-between gap-3 text-left group"
                                >
                                    <div className="flex items-center gap-3">
                                        <ShieldAlert size={18} className="text-orange-400" />
                                        <div>
                                            <h3 className="text-sm font-bold text-white">{t('clinics.support.section_title')}</h3>
                                            <p className="text-xs text-white/40">{t('clinics.support.section_subtitle')}</p>
                                        </div>
                                    </div>
                                    {supportComplaintsExpanded
                                        ? <ChevronUp size={18} className="text-white/40 group-hover:text-white/60" />
                                        : <ChevronDown size={18} className="text-white/40 group-hover:text-white/60" />}
                                </button>

                                {supportComplaintsExpanded && (
                                    <div className="space-y-4 pt-4">
                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                            <div className="space-y-1">
                                                <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                                                    {t('clinics.support.escalation_email')}
                                                </label>
                                                <input type="email" value={formData.complaint_escalation_email}
                                                    onChange={e => setFormData(p => ({ ...p, complaint_escalation_email: e.target.value }))}
                                                    placeholder="quejas@clinica.com"
                                                    className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-orange-500/20" />
                                            </div>
                                            <div className="space-y-1">
                                                <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                                                    {t('clinics.support.escalation_phone')}
                                                </label>
                                                <input type="text" value={formData.complaint_escalation_phone}
                                                    onChange={e => setFormData(p => ({ ...p, complaint_escalation_phone: e.target.value }))}
                                                    placeholder="+54 9 11 ..."
                                                    className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-orange-500/20" />
                                            </div>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                                            <div className="space-y-1">
                                                <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                                                    {t('clinics.support.expected_wait')}
                                                </label>
                                                <input type="number" min={1} value={formData.expected_wait_time_minutes}
                                                    onChange={e => setFormData(p => ({ ...p, expected_wait_time_minutes: e.target.value }))}
                                                    placeholder="15"
                                                    className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-orange-500/20" />
                                            </div>
                                        </div>

                                        <div className="space-y-1">
                                            <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                                                {t('clinics.support.revision_policy')}
                                            </label>
                                            <textarea value={formData.revision_policy}
                                                onChange={e => setFormData(p => ({ ...p, revision_policy: e.target.value }))}
                                                placeholder={t('clinics.support.revision_policy_placeholder')}
                                                rows={2}
                                                maxLength={2000}
                                                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-orange-500/20 resize-none" />
                                        </div>

                                        <div className="space-y-2">
                                            <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                                                {t('clinics.support.complaint_protocol')}
                                            </label>
                                            <p className="text-[10px] text-white/40">{t('clinics.support.complaint_protocol_help')}</p>
                                            <input type="text" value={formData.complaint_handling_protocol.level_1}
                                                onChange={e => setFormData(p => ({ ...p, complaint_handling_protocol: { ...p.complaint_handling_protocol, level_1: e.target.value } }))}
                                                placeholder={t('clinics.support.level_1_placeholder')}
                                                maxLength={500}
                                                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-orange-500/20" />
                                            <input type="text" value={formData.complaint_handling_protocol.level_2}
                                                onChange={e => setFormData(p => ({ ...p, complaint_handling_protocol: { ...p.complaint_handling_protocol, level_2: e.target.value } }))}
                                                placeholder={t('clinics.support.level_2_placeholder')}
                                                maxLength={500}
                                                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-orange-500/20" />
                                            <input type="text" value={formData.complaint_handling_protocol.level_3}
                                                onChange={e => setFormData(p => ({ ...p, complaint_handling_protocol: { ...p.complaint_handling_protocol, level_3: e.target.value } }))}
                                                placeholder={t('clinics.support.level_3_placeholder')}
                                                maxLength={500}
                                                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-orange-500/20" />
                                        </div>

                                        <div className="space-y-2">
                                            <div className="flex items-center justify-between">
                                                <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                                                    {t('clinics.support.review_platforms')}
                                                </label>
                                                <button type="button"
                                                    onClick={() => setFormData(p => ({ ...p, review_platforms: [...p.review_platforms, { name: '', url: '', show_after_days: 1 }] }))}
                                                    className="text-xs text-orange-400 hover:text-orange-300 font-semibold flex items-center gap-1">
                                                    <Plus size={12} /> {t('clinics.support.add_platform')}
                                                </button>
                                            </div>
                                            {formData.review_platforms.map((p, idx) => (
                                                <div key={idx} className="grid grid-cols-12 gap-2 bg-white/[0.02] border border-white/[0.06] rounded-lg p-2">
                                                    <input type="text" placeholder="Google Maps" value={p.name}
                                                        onChange={e => setFormData(prev => ({
                                                            ...prev,
                                                            review_platforms: prev.review_platforms.map((x, i) => i === idx ? { ...x, name: e.target.value } : x),
                                                        }))}
                                                        className="col-span-3 px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs outline-none" />
                                                    <input type="url" placeholder="https://..." value={p.url}
                                                        onChange={e => setFormData(prev => ({
                                                            ...prev,
                                                            review_platforms: prev.review_platforms.map((x, i) => i === idx ? { ...x, url: e.target.value } : x),
                                                        }))}
                                                        className="col-span-6 px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs outline-none" />
                                                    <input type="number" min={1} value={p.show_after_days}
                                                        onChange={e => setFormData(prev => ({
                                                            ...prev,
                                                            review_platforms: prev.review_platforms.map((x, i) => i === idx ? { ...x, show_after_days: parseInt(e.target.value) || 1 } : x),
                                                        }))}
                                                        className="col-span-2 px-2 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs outline-none" />
                                                    <button type="button"
                                                        onClick={() => setFormData(prev => ({ ...prev, review_platforms: prev.review_platforms.filter((_, i) => i !== idx) }))}
                                                        className="col-span-1 text-white/30 hover:text-red-400">
                                                        <X size={14} />
                                                    </button>
                                                </div>
                                            ))}
                                        </div>

                                        <label className="flex items-center gap-3 cursor-pointer">
                                            <input type="checkbox"
                                                checked={formData.auto_send_review_link_after_followup}
                                                onChange={e => setFormData(p => ({ ...p, auto_send_review_link_after_followup: e.target.checked }))}
                                                className="h-4 w-4 rounded border-white/[0.08] text-orange-400 focus:ring-orange-500" />
                                            <div>
                                                <span className="text-sm font-semibold text-white">{t('clinics.support.auto_send_review')}</span>
                                                <p className="text-xs text-white/40">{t('clinics.support.auto_send_review_help')}</p>
                                            </div>
                                        </label>
                                    </div>
                                )}
                            </div>

                            <div className="flex gap-3 pt-4 sticky bottom-0 bg-[#0d1117] pb-2">
                                <button type="button" onClick={() => { setIsModalOpen(false); resetHolidaysState(); }}
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
                            {/* New insurance fields: is_prepaid, default_copay, employee_discount */}
                            {(insuranceForm.status === 'accepted' || insuranceForm.status === 'restricted') && (
                                <>
                                    <div className="flex items-center gap-3">
                                        <label className="flex items-center gap-3 cursor-pointer">
                                            <input type="checkbox" checked={insuranceForm.is_prepaid ?? false} onChange={e => setInsuranceForm(p => ({ ...p, is_prepaid: e.target.checked }))}
                                                className="h-5 w-5 rounded border-white/[0.08] text-blue-400 focus:ring-blue-500" />
                                            <span className="text-sm font-medium text-white/60">{t('settings.insurance.fields.isPrepaid')}</span>
                                        </label>
                                    </div>
                                    <div className="grid grid-cols-2 gap-3">
                                        <div className="space-y-1">
                                            <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.defaultCopay')}</label>
                                            <input type="number" min="0" max="100" value={insuranceForm.default_copay_percent ?? ''} onChange={e => setInsuranceForm(p => ({ ...p, default_copay_percent: e.target.value ? Number(e.target.value) : undefined }))}
                                                className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none" />
                                        </div>
                                        <div className="space-y-1">
                                            <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.employeeDiscount')}</label>
                                            <input type="number" min="0" max="100" value={insuranceForm.employee_discount_percent ?? ''} onChange={e => setInsuranceForm(p => ({ ...p, employee_discount_percent: e.target.value ? Number(e.target.value) : undefined }))}
                                                className="w-full px-4 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500 outline-none" />
                                        </div>
                                    </div>
                                </>
                            )}
                            {/* Coverage Matrix - shown when status is 'accepted' or 'restricted' */}
                            {(insuranceForm.status === 'accepted' || insuranceForm.status === 'restricted') && insuranceTreatments.length > 0 && (
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between">
                                        <label className="text-sm font-semibold text-white/60">{t('settings.insurance.fields.coverageMatrix')}</label>
                                        <button type="button" onClick={() => setCoverageMatrixExpanded(!coverageMatrixExpanded)} className="text-xs text-blue-400 hover:text-blue-300">
                                            {coverageMatrixExpanded ? t('settings.insurance.fields.coverageCollapsed') : t('settings.insurance.fields.coverageCollapsed')}
                                        </button>
                                    </div>
                                    <p className="text-xs text-white/30">{t('settings.insurance.fields.coverageMatrixHint')}</p>
                                    
                                    {/* Quick action: Mark all as covered */}
                                    <button type="button" onClick={() => {
                                        const allCoverage: Record<string, TreatmentCoverageEntry> = {};
                                        insuranceTreatments.forEach(t => {
                                            allCoverage[t.code] = { covered: true, copay_percent: insuranceForm.default_copay_percent || 0, requires_pre_authorization: false, pre_auth_leadtime_days: 0, waiting_period_days: 0, max_annual_coverage: null, notes: '' };
                                        });
                                        setInsuranceForm(p => ({ ...p, coverage_by_treatment: allCoverage }));
                                    }} className="text-xs text-emerald-400 hover:text-emerald-300">
                                        {t('settings.insurance.fields.configureAllCovered')}
                                    </button>

                                    {coverageMatrixExpanded && (
                                        <div className="max-h-64 overflow-y-auto rounded-lg border border-white/[0.08] bg-white/[0.02] divide-y divide-white/[0.04]">
                                            {insuranceTreatments.map(treat => {
                                                const coverage = insuranceForm.coverage_by_treatment?.[treat.code] || { covered: false, copay_percent: 0, requires_pre_authorization: false, pre_auth_leadtime_days: 0, waiting_period_days: 0, max_annual_coverage: null, notes: '' };
                                                return (
                                                    <div key={treat.code} className="p-3 space-y-2">
                                                        <div className="flex items-center justify-between">
                                                            <div className="flex items-center gap-2">
                                                                <input type="checkbox" checked={coverage.covered} onChange={e => {
                                                                    const newCoverage = { ...insuranceForm.coverage_by_treatment };
                                                                    if (e.target.checked) {
                                                                        newCoverage[treat.code] = { covered: true, copay_percent: insuranceForm.default_copay_percent || 0, requires_pre_authorization: false, pre_auth_leadtime_days: 0, waiting_period_days: 0, max_annual_coverage: null, notes: '' };
                                                                    } else {
                                                                        delete newCoverage[treat.code];
                                                                    }
                                                                    setInsuranceForm(p => ({ ...p, coverage_by_treatment: newCoverage }));
                                                                }} className="h-4 w-4 rounded border-white/20 text-emerald-400" />
                                                                <span className="text-sm text-white font-medium">{treat.name}</span>
                                                                <span className="text-xs text-white/30">({treat.code})</span>
                                                            </div>
                                                        </div>
                                                        {coverage.covered && (
                                                            <div className="pl-6 grid grid-cols-2 gap-2 text-xs">
                                                                <div>
                                                                    <label className="text-white/40">{t('settings.insurance.fields.copayPercent')}</label>
                                                                    <input type="number" min="0" max="100" value={coverage.copay_percent} onChange={e => {
                                                                        const newCoverage = { ...insuranceForm.coverage_by_treatment };
                                                                        newCoverage[treat.code] = { ...coverage, copay_percent: Number(e.target.value) };
                                                                        setInsuranceForm(p => ({ ...p, coverage_by_treatment: newCoverage }));
                                                                    }} className="w-full px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-white" />
                                                                </div>
                                                                <div>
                                                                    <label className="text-white/40">{t('settings.insurance.fields.waitingDays')}</label>
                                                                    <input type="number" min="0" value={coverage.waiting_period_days} onChange={e => {
                                                                        const newCoverage = { ...insuranceForm.coverage_by_treatment };
                                                                        newCoverage[treat.code] = { ...coverage, waiting_period_days: Number(e.target.value) };
                                                                        setInsuranceForm(p => ({ ...p, coverage_by_treatment: newCoverage }));
                                                                    }} className="w-full px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-white" />
                                                                </div>
                                                                <div className="col-span-2 flex items-center gap-2">
                                                                    <input type="checkbox" checked={coverage.requires_pre_authorization} onChange={e => {
                                                                        const newCoverage = { ...insuranceForm.coverage_by_treatment };
                                                                        newCoverage[treat.code] = { ...coverage, requires_pre_authorization: e.target.checked };
                                                                        setInsuranceForm(p => ({ ...p, coverage_by_treatment: newCoverage }));
                                                                    }} className="h-4 w-4 rounded border-white/20 text-blue-400" />
                                                                    <span className="text-white/60">{t('settings.insurance.fields.requiresPreAuth')}</span>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                    <p className="text-xs text-white/30">
                                        {Object.keys(insuranceForm.coverage_by_treatment || {}).filter(code => insuranceForm.coverage_by_treatment?.[code]?.covered).length} {t('settings.insurance.fields.treatmentsSelected')}
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

                            {/* Escalation fallback section (migration 038) */}
                            <div className="space-y-3 border-t border-white/[0.06] pt-4">
                                <label className="flex items-center gap-3 cursor-pointer">
                                    <input type="checkbox"
                                        checked={!!derivationForm.enable_escalation}
                                        onChange={e => setDerivationForm(p => ({ ...p, enable_escalation: e.target.checked }))}
                                        className="h-4 w-4 rounded border-white/[0.08] text-amber-400 focus:ring-amber-500" />
                                    <div>
                                        <span className="text-sm font-semibold text-white">{t('settings.derivation.fields.enableEscalation')}</span>
                                        <p className="text-xs text-white/40">{t('settings.derivation.fields.enableEscalationHelp')}</p>
                                    </div>
                                </label>

                                {derivationForm.enable_escalation && (
                                    <div className="space-y-3 pl-7 border-l-2 border-amber-500/20">
                                        <div className="space-y-1">
                                            <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                                                {t('settings.derivation.fields.maxWaitDays')}
                                            </label>
                                            <input type="number" min={1} max={30}
                                                value={derivationForm.max_wait_days_before_escalation ?? 7}
                                                onChange={e => setDerivationForm(p => ({ ...p, max_wait_days_before_escalation: parseInt(e.target.value) || 7 }))}
                                                className="w-24 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-2 focus:ring-amber-500/20" />
                                            <p className="text-[10px] text-white/40">{t('settings.derivation.fields.maxWaitDaysHelp')}</p>
                                        </div>

                                        <div className="space-y-2">
                                            <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                                                {t('settings.derivation.fields.fallbackTarget')}
                                            </label>
                                            <label className="flex items-center gap-3 cursor-pointer p-2 rounded hover:bg-white/[0.02]">
                                                <input type="radio" name="fallback_mode"
                                                    checked={!!derivationForm.fallback_team_mode}
                                                    onChange={() => setDerivationForm(p => ({ ...p, fallback_team_mode: true, fallback_professional_id: null }))}
                                                    className="h-4 w-4 text-amber-400 border-white/[0.08]" />
                                                <span className="text-sm text-white/70">{t('settings.derivation.fields.fallbackTeamMode')}</span>
                                            </label>
                                            <label className="flex items-center gap-3 cursor-pointer p-2 rounded hover:bg-white/[0.02]">
                                                <input type="radio" name="fallback_mode"
                                                    checked={!derivationForm.fallback_team_mode && !!derivationForm.fallback_professional_id}
                                                    onChange={() => setDerivationForm(p => ({ ...p, fallback_team_mode: false }))}
                                                    className="h-4 w-4 text-amber-400 border-white/[0.08]" />
                                                <span className="text-sm text-white/70">{t('settings.derivation.fields.fallbackSpecific')}</span>
                                            </label>
                                            {!derivationForm.fallback_team_mode && (
                                                <select value={derivationForm.fallback_professional_id ?? ''}
                                                    onChange={e => setDerivationForm(p => ({ ...p, fallback_professional_id: e.target.value ? parseInt(e.target.value) : null }))}
                                                    className="w-full px-3 py-2 bg-[#0d1117] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-2 focus:ring-amber-500/20 [&>option]:bg-[#0d1117]">
                                                    <option value="">—</option>
                                                    {derivationProfessionals
                                                        .filter(p => p.id !== derivationForm.target_professional_id)
                                                        .map(p => (
                                                            <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
                                                        ))}
                                                </select>
                                            )}
                                        </div>

                                        <div className="space-y-1">
                                            <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                                                {t('settings.derivation.fields.escalationMessage')}
                                            </label>
                                            <textarea value={derivationForm.escalation_message_template || ''}
                                                onChange={e => setDerivationForm(p => ({ ...p, escalation_message_template: e.target.value || null }))}
                                                placeholder={t('settings.derivation.fields.escalationMessagePlaceholder')}
                                                rows={3}
                                                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-amber-500/20 resize-none" />
                                            <p className="text-[10px] text-white/40">{t('settings.derivation.fields.escalationMessageHelp')}</p>
                                        </div>
                                    </div>
                                )}
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
