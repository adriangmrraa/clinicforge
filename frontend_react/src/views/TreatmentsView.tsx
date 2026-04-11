import React, { useState, useEffect } from 'react';
import { Clock, AlertCircle, CheckCircle, Save, X, Zap, Shield, Heart, Activity, Stethoscope, Edit2, Upload, Trash2, Image as ImageIcon, Users, FileText, CheckCircle2, Plus, Info, Search } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import PageHeader from '../components/PageHeader';
import GlassCard, { CARD_IMAGES } from '../components/GlassCard';

interface Professional {
  id: number;
  first_name: string;
  last_name: string;
  specialty?: string;
}

interface TreatmentType {
  id: number;
  code: string;
  name: string;
  description: string;
  default_duration_minutes: number;
  min_duration_minutes: number;
  max_duration_minutes: number;
  complexity_level: string;
  category: string;
  requires_multiple_sessions: boolean;
  session_gap_days: number;
  is_active: boolean;
  is_available_for_booking: boolean;
  internal_notes: string;
  base_price?: number;
  professional_ids?: number[];
  pre_instructions?: string;
  post_instructions?: PostInstruction[];
  followup_template?: FollowupMessage[];
  // Migration 041: consultation fields for high-ticket treatments
  is_high_ticket?: boolean;
  consultation_duration_minutes?: number;
  consultation_requirements?: string;
  consultation_notes?: string;
  ai_response_template?: string;
}

type PostTiming = 'immediate' | '24h' | '48h' | '72h' | '1w' | 'stitch_removal' | 'custom';

interface PostInstruction {
  timing: PostTiming;
  custom_days?: number;
  book_followup?: boolean;
  content: string;
}

interface FollowupMessage {
  hours_after: number;
  message: string;
}

// Migration 037: structured pre-treatment instructions form. Mirrors the
// PreInstructions Pydantic model in admin_routes.py.
interface PreInstructionsForm {
  preparation_days_before: number | null;
  fasting_required: boolean | null;
  fasting_hours: number | null;
  medications_to_avoid: string[];
  medications_to_take: string[];
  what_to_bring: string[];
  general_notes: string;
}

// Migration 037: structured post-treatment recovery protocol form.
// Mirrors the PostInstructions Pydantic model in admin_routes.py.
interface PostInstructionsForm {
  care_duration_days: number | null;
  dietary_restrictions: string[];
  activity_restrictions: string[];
  allowed_medications: string[];
  prohibited_medications: string[];
  sutures_removal_day: number | null;
  normal_symptoms: string[];
  alarm_symptoms: string[];
  escalation_message: string;
}

const emptyPreForm: PreInstructionsForm = {
  preparation_days_before: null,
  fasting_required: null,
  fasting_hours: null,
  medications_to_avoid: [],
  medications_to_take: [],
  what_to_bring: [],
  general_notes: '',
};

const emptyPostForm: PostInstructionsForm = {
  care_duration_days: null,
  dietary_restrictions: [],
  activity_restrictions: [],
  allowed_medications: [],
  prohibited_medications: [],
  sutures_removal_day: null,
  normal_symptoms: [],
  alarm_symptoms: [],
  escalation_message: '',
};

// Helper: parse pre_instructions from API response into form state.
// Accepts: dict (new shape), string (legacy raw), {general_notes: str} wrap.
function parsePreInstructions(value: unknown): PreInstructionsForm {
  if (!value) return { ...emptyPreForm };
  if (typeof value === 'string') {
    return { ...emptyPreForm, general_notes: value };
  }
  if (typeof value === 'object') {
    const v = value as Record<string, unknown>;
    return {
      preparation_days_before: typeof v.preparation_days_before === 'number' ? v.preparation_days_before : null,
      fasting_required: typeof v.fasting_required === 'boolean' ? v.fasting_required : null,
      fasting_hours: typeof v.fasting_hours === 'number' ? v.fasting_hours : null,
      medications_to_avoid: Array.isArray(v.medications_to_avoid) ? (v.medications_to_avoid as string[]) : [],
      medications_to_take: Array.isArray(v.medications_to_take) ? (v.medications_to_take as string[]) : [],
      what_to_bring: Array.isArray(v.what_to_bring) ? (v.what_to_bring as string[]) : [],
      general_notes: typeof v.general_notes === 'string' ? v.general_notes : '',
    };
  }
  return { ...emptyPreForm };
}

// Helper: parse post_instructions from API response.
// Returns either the new structured form OR the legacy timed list (not both).
function parsePostInstructions(value: unknown): { post: PostInstructionsForm; legacy: PostInstruction[] } {
  if (!value) return { post: { ...emptyPostForm }, legacy: [] };
  // Legacy timed sequence (bare list)
  if (Array.isArray(value)) {
    return { post: { ...emptyPostForm }, legacy: value as PostInstruction[] };
  }
  if (typeof value === 'object') {
    const v = value as Record<string, unknown>;
    // Check for legacy wrap: {general_notes: "<serialized list>"}
    if (typeof v.general_notes === 'string') {
      try {
        const parsed = JSON.parse(v.general_notes as string);
        if (Array.isArray(parsed)) {
          return { post: { ...emptyPostForm }, legacy: parsed as PostInstruction[] };
        }
      } catch {
        // Not a serialized list — fall through to dict path
      }
    }
    // New structured form
    return {
      post: {
        care_duration_days: typeof v.care_duration_days === 'number' ? v.care_duration_days : null,
        dietary_restrictions: Array.isArray(v.dietary_restrictions) ? (v.dietary_restrictions as string[]) : [],
        activity_restrictions: Array.isArray(v.activity_restrictions) ? (v.activity_restrictions as string[]) : [],
        allowed_medications: Array.isArray(v.allowed_medications) ? (v.allowed_medications as string[]) : [],
        prohibited_medications: Array.isArray(v.prohibited_medications) ? (v.prohibited_medications as string[]) : [],
        sutures_removal_day: typeof v.sutures_removal_day === 'number' ? v.sutures_removal_day : null,
        normal_symptoms: Array.isArray(v.normal_symptoms) ? (v.normal_symptoms as string[]) : [],
        alarm_symptoms: Array.isArray(v.alarm_symptoms) ? (v.alarm_symptoms as string[]) : [],
        escalation_message: typeof v.escalation_message === 'string' ? v.escalation_message : '',
      },
      legacy: [],
    };
  }
  return { post: { ...emptyPostForm }, legacy: [] };
}

// Helper: drop empty fields from PostInstructionsForm so we don't send a wall
// of nulls to the backend. Returns null if everything is empty.
function postFormHasContent(form: PostInstructionsForm): boolean {
  return (
    form.care_duration_days !== null ||
    form.sutures_removal_day !== null ||
    form.escalation_message.trim().length > 0 ||
    form.dietary_restrictions.length > 0 ||
    form.activity_restrictions.length > 0 ||
    form.allowed_medications.length > 0 ||
    form.prohibited_medications.length > 0 ||
    form.normal_symptoms.length > 0 ||
    form.alarm_symptoms.length > 0
  );
}

function preFormHasContent(form: PreInstructionsForm): boolean {
  return (
    form.preparation_days_before !== null ||
    form.fasting_required !== null ||
    form.fasting_hours !== null ||
    form.general_notes.trim().length > 0 ||
    form.medications_to_avoid.length > 0 ||
    form.medications_to_take.length > 0 ||
    form.what_to_bring.length > 0
  );
}

interface TreatmentInstructions {
  // Migration 037 — instruction state shape now carries 3 separate buckets:
  // - preForm: structured PreInstructions dict
  // - postForm: structured PostInstructions dict
  // - timedSequence: legacy list shape (preserved for backwards compat)
  // Save handler chooses dict OR list based on which form has content.
  preForm: PreInstructionsForm;
  postForm: PostInstructionsForm;
  timedSequence: PostInstruction[];
  followup_template: FollowupMessage[];
}

// Reusable inline component for editing a list of free-text strings
// (medications, restrictions, symptoms, etc.). Each row has an X button.
const StringListEditor: React.FC<{
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
  accentColor?: 'blue' | 'red' | 'amber';
}> = ({ label, items, onChange, placeholder, accentColor = 'blue' }) => {
  const accentText =
    accentColor === 'red' ? 'text-red-400 hover:text-red-300'
    : accentColor === 'amber' ? 'text-amber-400 hover:text-amber-300'
    : 'text-blue-400 hover:text-blue-300';
  const labelText =
    accentColor === 'red' ? 'text-red-400'
    : accentColor === 'amber' ? 'text-amber-400'
    : 'text-white/60';
  const updateAt = (idx: number, val: string) => {
    const next = [...items];
    next[idx] = val;
    onChange(next);
  };
  const removeAt = (idx: number) => {
    onChange(items.filter((_, i) => i !== idx));
  };
  const add = () => onChange([...items, '']);
  return (
    <div className="space-y-2">
      <label className={`text-xs font-semibold uppercase tracking-wider ${labelText}`}>{label}</label>
      <div className="space-y-2">
        {items.length === 0 ? (
          <input
            type="text"
            value=""
            onChange={e => updateAt(0, e.target.value) || add()}
            placeholder={placeholder}
            className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-blue-500/20"
            onFocus={() => items.length === 0 && onChange([''])}
          />
        ) : (
          items.map((item, idx) => (
            <div key={idx} className="flex items-center gap-2">
              <input
                type="text"
                value={item}
                onChange={e => updateAt(idx, e.target.value)}
                placeholder={placeholder}
                className="flex-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-blue-500/20"
              />
              <button
                type="button"
                onClick={() => removeAt(idx)}
                className="p-1.5 text-white/30 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors shrink-0"
              >
                <X size={16} />
              </button>
            </div>
          ))
        )}
      </div>
      <button
        type="button"
        onClick={add}
        className={`text-sm font-semibold flex items-center gap-1 ${accentText}`}
      >
        <Plus size={14} /> Agregar
      </button>
    </div>
  );
};

// Category icons mapping
const categoryIcons: Record<string, React.ReactNode> = {
  prevention: <Heart size={16} className="text-green-600" />,
  restorative: <Activity size={16} className="text-blue-600" />,
  surgical: <Zap size={16} className="text-red-600" />,
  orthodontics: <Shield size={16} className="text-purple-600" />,
  emergency: <AlertCircle size={16} className="text-orange-600" />,
};

// Category icons mapping already defined

const TreatmentImagesList = ({ code }: { code: string }) => {
  const { t } = useTranslation();
  const [images, setImages] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    fetchImages();
  }, [code]);

  const fetchImages = async () => {
    try {
      setLoading(true);
      const res = await api.get(`/admin/treatment-types/${code}/images`);
      setImages(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    const formData = new FormData();
    formData.append('file', file);

    try {
      setUploading(true);
      await api.post(`/admin/treatment-types/${code}/images`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });
      await fetchImages();
    } catch (e) {
      console.error(e);
      alert(t('treatments.error_upload_image'));
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm(t('treatments.confirm_delete_image'))) return;
    try {
      await api.delete(`/admin/treatment-types/${code}/images/${id}`);
      await fetchImages();
    } catch (e) {
      console.error(e);
      alert(t('treatments.error_delete_image'));
    }
  };

  // Construct base API URL depending on environment so we fetch absolute images when testing UI
  const baseURL = api.defaults.baseURL || '';
  const makeImgUrl = (id: string) => baseURL ? `${baseURL}/admin/public/media/${id}` : `/api/admin/public/media/${id}`;

  return (
    <div className="mt-5 pt-5 border-t border-white/[0.06]">
      <div className="flex items-center justify-between mb-4">
        <h4 className="flex items-center gap-2 text-xs font-bold text-white/30 uppercase tracking-widest">
          <ImageIcon size={14} className="text-white/30" /> {t('treatments.attachments_title')}
        </h4>
        <label className="cursor-pointer bg-white/[0.06] border border-white/[0.06] text-blue-400 px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wider hover:bg-white/[0.04] transition-colors flex items-center gap-2">
          {uploading ? <div className="w-3.5 h-3.5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" /> : <Upload size={14} />}
          {t('treatments.upload_image')}
          <input type="file" className="hidden" accept="image/*" onChange={handleUpload} disabled={uploading} />
        </label>
      </div>

      {loading ? (
        <div className="text-xs font-medium text-white/30">{t('treatments.loading_images')}</div>
      ) : images.length === 0 ? (
        <div className="text-xs font-medium text-white/30 bg-white/[0.02] p-4 rounded-xl border border-dashed border-white/[0.06] text-center flex items-center justify-center gap-2">
          <ImageIcon size={16} /> {t('treatments.no_images')}
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2 custom-scrollbar items-center">
          {images.map(img => (
            <div key={img.id} className="relative group shrink-0 w-24 h-24 rounded-xl border border-white/[0.06] overflow-hidden bg-white/[0.02]">
              <img src={makeImgUrl(img.id)} alt={img.filename} className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px] opacity-0 group-hover:opacity-100 transition-all flex items-center justify-center">
                <button onClick={() => handleDelete(img.id)} className="p-2 bg-red-500/90 text-white rounded-xl hover:bg-red-600 shadow-xl active:scale-95 transition-all" title={t('common.delete')}>
                  <Trash2 size={16} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

interface PriceAuditItem {
  code: string;
  name: string;
  base_price: number;
  ratio: number;
}

interface PriceAuditResult {
  tenant_id: number;
  consultation_price: number | null;
  threshold: number | null;
  suspicious: PriceAuditItem[];
  total_treatments: number;
  total_suspicious: number;
  warning?: string;
}

const formatARS = (value: number) =>
  new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(value);

export default function TreatmentsView() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const [treatments, setTreatments] = useState<TreatmentType[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<TreatmentType>>({});
  const [saving, setSaving] = useState(false);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [isCreating, setIsCreating] = useState(false);

  // Audit modal state (Bug #3)
  const [auditOpen, setAuditOpen] = useState(false);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditResult, setAuditResult] = useState<PriceAuditResult | null>(null);

  // Unusual price confirmation state (Bug #3)
  const [unusualPriceConfirm, setUnusualPriceConfirm] = useState<{ context: 'create' | 'edit'; code?: string } | null>(null);

  // Instructions modal state — migration 037 splits into 3 buckets
  const [instructionsModalOpen, setInstructionsModalOpen] = useState(false);
  const [instructionsTarget, setInstructionsTarget] = useState<'edit' | 'create'>('edit');
  // Tab switcher: 'protocol' = new structured PostInstructions form,
  // 'sequence' = legacy timed list. They are mutually exclusive on save.
  const [postEditMode, setPostEditMode] = useState<'protocol' | 'sequence'>('protocol');
  const [instructionsLocal, setInstructionsLocal] = useState<TreatmentInstructions>({
    preForm: { ...emptyPreForm },
    postForm: { ...emptyPostForm },
    timedSequence: [],
    followup_template: [],
  });

  const openInstructionsModal = (target: 'edit' | 'create') => {
    setInstructionsTarget(target);
    const form = target === 'edit' ? editForm : newForm;
    const preForm = parsePreInstructions(form.pre_instructions);
    const { post: postForm, legacy } = parsePostInstructions(form.post_instructions);
    setInstructionsLocal({
      preForm,
      postForm,
      timedSequence: legacy,
      followup_template: form.followup_template || [],
    });
    // Default to legacy view if there's existing legacy data and no new form data
    setPostEditMode(legacy.length > 0 && !postFormHasContent(postForm) ? 'sequence' : 'protocol');
    setInstructionsModalOpen(true);
  };

  const saveInstructions = async () => {
    // Migration 037 save handler:
    // - pre_instructions: send the structured PreInstructionsForm dict if
    //   any field is set; otherwise null
    // - post_instructions: send the dict if user is in protocol mode and
    //   there is content; otherwise send the legacy timed list if non-empty;
    //   otherwise null
    const preOut = preFormHasContent(instructionsLocal.preForm)
      ? instructionsLocal.preForm
      : null;

    let postOut: PostInstructionsForm | PostInstruction[] | null = null;
    if (postEditMode === 'protocol' && postFormHasContent(instructionsLocal.postForm)) {
      postOut = instructionsLocal.postForm;
    } else if (instructionsLocal.timedSequence.length > 0) {
      postOut = instructionsLocal.timedSequence;
    }

    const patch = {
      pre_instructions: preOut as unknown as string | undefined,
      post_instructions: postOut as unknown as PostInstruction[] | undefined,
      followup_template: instructionsLocal.followup_template,
    };
    if (instructionsTarget === 'edit') {
      const updatedForm = { ...editForm, ...patch };
      setEditForm(updatedForm);
      // Auto-persist to backend immediately (don't require second save click)
      try {
        setSaving(true);
        await api.put(`/admin/treatment-types/${editForm.code}`, updatedForm);
        await fetchTreatments();
      } catch (error: any) {
        console.error('Error saving instructions:', error);
        alert(error.response?.data?.detail || t('alerts.error_save_treatment'));
      } finally {
        setSaving(false);
      }
    } else {
      setNewForm(prev => ({ ...prev, ...patch }));
    }
    setInstructionsModalOpen(false);
  };

  // Legacy timed-sequence editors (preserved unchanged)
  const addPostInstruction = () => {
    setInstructionsLocal(prev => ({
      ...prev,
      timedSequence: [...prev.timedSequence, { timing: 'immediate', content: '' }],
    }));
  };

  const removePostInstruction = (idx: number) => {
    setInstructionsLocal(prev => ({
      ...prev,
      timedSequence: prev.timedSequence.filter((_, i) => i !== idx),
    }));
  };

  const updatePostInstruction = (idx: number, field: keyof PostInstruction, value: unknown) => {
    setInstructionsLocal(prev => ({
      ...prev,
      timedSequence: prev.timedSequence.map((item, i) => i === idx ? { ...item, [field]: value } : item),
    }));
  };

  // Helpers for the new structured forms
  const updatePreField = <K extends keyof PreInstructionsForm>(field: K, value: PreInstructionsForm[K]) => {
    setInstructionsLocal(prev => ({ ...prev, preForm: { ...prev.preForm, [field]: value } }));
  };

  const updatePostField = <K extends keyof PostInstructionsForm>(field: K, value: PostInstructionsForm[K]) => {
    setInstructionsLocal(prev => ({ ...prev, postForm: { ...prev.postForm, [field]: value } }));
  };

  const addFollowup = () => {
    setInstructionsLocal(prev => ({
      ...prev,
      followup_template: [...prev.followup_template, { hours_after: 24, message: '' }],
    }));
  };

  const removeFollowup = (idx: number) => {
    setInstructionsLocal(prev => ({
      ...prev,
      followup_template: prev.followup_template.filter((_, i) => i !== idx),
    }));
  };

  const updateFollowup = (idx: number, field: keyof FollowupMessage, value: unknown) => {
    setInstructionsLocal(prev => ({
      ...prev,
      followup_template: prev.followup_template.map((item, i) => i === idx ? { ...item, [field]: value } : item),
    }));
  };

  const [newForm, setNewForm] = useState<Partial<TreatmentType>>({
    code: '',
    name: '',
    description: '',
    default_duration_minutes: 30,
    min_duration_minutes: 15,
    max_duration_minutes: 60,
    complexity_level: 'medium',
    category: 'restorative',
    requires_multiple_sessions: false,
    session_gap_days: 0,
    is_active: true,
    is_available_for_booking: true,
    internal_notes: '',
    base_price: 0,
    professional_ids: [],
    is_high_ticket: false,
    consultation_duration_minutes: 30,
    consultation_requirements: '',
    consultation_notes: '',
  });

  const fetchTreatments = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/treatment-types');
      const list = Array.isArray(response?.data) ? response.data : [];
      setTreatments(list);
    } catch (error) {
      console.error('Error fetching treatments:', error);
      setTreatments([]);
    } finally {
      setLoading(false);
    }
  };

  const fetchProfessionals = async () => {
    try {
      const response = await api.get('/admin/professionals');
      setProfessionals(Array.isArray(response?.data) ? response.data : []);
    } catch (error) {
      console.error('Error fetching professionals:', error);
    }
  };

  useEffect(() => {
    fetchTreatments();
    fetchProfessionals();
  }, []);

  const handleEdit = (treatment: TreatmentType) => {
    setEditingId(treatment.id);
    setEditForm({ ...treatment, professional_ids: treatment.professional_ids || [] });
  };

  const handleCancel = () => {
    setEditingId(null);
    setEditForm({});
  };

  const handleSave = async (code: string, confirmUnusual = false) => {
    if (!editForm.code) return;

    try {
      setSaving(true);
      await api.put(`/admin/treatment-types/${code}`, { ...editForm, confirm_unusual_price: confirmUnusual });
      await api.put(`/admin/treatment-types/${code}/professionals`, { professional_ids: editForm.professional_ids || [] });
      await fetchTreatments();
      setEditingId(null);
      setEditForm({});
      setUnusualPriceConfirm(null);
    } catch (error: any) {
      if (error.response?.status === 422 && error.response?.data?.detail?.includes('confirm_unusual_price')) {
        setUnusualPriceConfirm({ context: 'edit', code });
        return;
      }
      console.error('Error saving treatment:', error);
      alert(error.response?.data?.detail || t('alerts.error_save_treatment'));
    } finally {
      setSaving(false);
    }
  };

  const handleCreate = async (confirmUnusual = false) => {
    if (!newForm.code || !newForm.name) {
      alert(t('alerts.code_name_required'));
      return;
    }

    try {
      setSaving(true);
      await api.post('/admin/treatment-types', { ...newForm, confirm_unusual_price: confirmUnusual });
      await fetchTreatments();
      setIsCreating(false);
      setUnusualPriceConfirm(null);
      setNewForm({
        code: '',
        name: '',
        description: '',
        default_duration_minutes: 30,
        min_duration_minutes: 15,
        max_duration_minutes: 60,
        complexity_level: 'medium',
        category: 'restorative',
        requires_multiple_sessions: false,
        session_gap_days: 0,
        is_active: true,
        is_available_for_booking: true,
        internal_notes: '',
        professional_ids: []
      });
    } catch (error: any) {
      if (error.response?.status === 422 && error.response?.data?.detail?.includes('confirm_unusual_price')) {
        setUnusualPriceConfirm({ context: 'create' });
        return;
      }
      console.error('Error creating treatment:', error);
      alert(error.response?.data?.detail || t('alerts.error_create_treatment'));
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (code: string) => {
    if (!confirm(t('alerts.confirm_delete_treatment').replace('{{code}}', code))) return;

    try {
      setSaving(true);
      await api.delete(`/admin/treatment-types/${code}`);
      await fetchTreatments();
    } catch (error) {
      console.error('Error deleting treatment:', error);
      alert(t('alerts.error_delete_treatment'));
    } finally {
      setSaving(false);
    }
  };

  const handleOpenAudit = async () => {
    setAuditOpen(true);
    setAuditLoading(true);
    try {
      const res = await api.get('/admin/treatments/price-audit');
      setAuditResult(res.data);
    } catch (err) {
      console.error('Error fetching price audit:', err);
    } finally {
      setAuditLoading(false);
    }
  };

  const handleDurationChange = (field: 'min' | 'default' | 'max', value: string) => {
    const numValue = parseInt(value) || 0;
    setEditForm(prev => ({
      ...prev,
      [field === 'min' ? 'min_duration_minutes' : field === 'default' ? 'default_duration_minutes' : 'max_duration_minutes']: numValue
    }));
  };

  // Group treatments by category (guard against non-array or missing category)
  const safeTreatments = Array.isArray(treatments) ? treatments : [];
  const groupedTreatments = safeTreatments.reduce((acc, treatment) => {
    const cat = treatment?.category ?? 'restorative';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(treatment);
    return acc;
  }, {} as Record<string, TreatmentType[]>);

  return (
    <div className="flex flex-col h-full overflow-hidden bg-transparent">
      {/* Scrollable Container Wrapper */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 lg:p-6 custom-scrollbar">
        <PageHeader
          title={t('treatments.title')}
          subtitle={t('treatments.subtitle')}
          icon={<Stethoscope size={22} />}
          action={
            <div className="flex items-center gap-2">
              {user?.role === 'ceo' && (
                <button
                  onClick={handleOpenAudit}
                  className="px-4 py-2.5 bg-white/[0.06] border border-white/[0.08] text-white/70 rounded-xl hover:bg-white/[0.10] transition-all flex items-center justify-center gap-2 active:scale-[0.98] font-semibold text-sm"
                >
                  <Search size={16} />
                  {t('treatments.auditButton')}
                </button>
              )}
              <button
                onClick={() => setIsCreating(true)}
                className="px-4 sm:px-5 py-2.5 bg-white text-[#0a0e1a] rounded-xl hover:bg-white/90 transition-all flex items-center justify-center gap-2 active:scale-[0.98] font-semibold text-sm"
              >
                <Zap size={18} fill="currentColor" />
                {t('treatments.new_service')}
              </button>
            </div>
          }
        />

        {/* Quick Reference */}
        <GlassCard image={CARD_IMAGES.dental} hoverScale={false} className="mb-10 rounded-3xl">
        <div className="p-6">
          <h3 className="font-bold text-white mb-5 flex items-center gap-2">
            <Clock size={20} className="text-blue-400" />
            {t('treatments.recommended_durations')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-sm">
            <div className="flex items-center gap-4 p-4 bg-white/[0.06] rounded-2xl border border-white/[0.10] hover:border-white/[0.18] transition-colors">
              <div className="p-3 bg-blue-500/10 text-blue-400 rounded-xl">
                <Clock size={20} />
              </div>
              <div className="flex flex-col">
                <span className="text-white/40 font-medium uppercase text-[10px] tracking-wider">{t('treatments.urgency_consult')}</span>
                <span className="text-white font-bold text-lg">15 {t('common.minutes_short')}</span>
              </div>
            </div>
            <div className="flex items-center gap-4 p-4 bg-white/[0.06] rounded-2xl border border-white/[0.10] hover:border-white/[0.18] transition-colors">
              <div className="p-3 bg-green-500/10 text-green-400 rounded-xl">
                <Clock size={20} />
              </div>
              <div className="flex flex-col">
                <span className="text-white/40 font-medium uppercase text-[10px] tracking-wider">{t('treatments.deep_cleaning')}</span>
                <span className="text-white font-bold text-lg">30 {t('common.minutes_short')}</span>
              </div>
            </div>
            <div className="flex items-center gap-4 p-4 bg-white/[0.06] rounded-2xl border border-white/[0.10] hover:border-white/[0.18] transition-colors">
              <div className="p-3 bg-red-500/10 text-red-400 rounded-xl">
                <Clock size={20} />
              </div>
              <div className="flex flex-col">
                <span className="text-white/40 font-medium uppercase text-[10px] tracking-wider">{t('treatments.complex_treatment')}</span>
                <span className="text-white font-bold text-lg">60 {t('common.minutes_short')}</span>
              </div>
            </div>
          </div>
        </div>
        </GlassCard>

        {/* Modal: Nuevo Servicio / Crear tratamiento (centrado en mobile y desktop) */}
        {isCreating && (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
            onClick={(e) => e.target === e.currentTarget && setIsCreating(false)}
          >
            <div className="bg-[#0d1117] border border-white/[0.08] rounded-2xl sm:rounded-3xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
              <div className="flex justify-between items-center gap-3 p-4 sm:p-6 border-b border-white/[0.06] shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="p-2.5 sm:p-3 bg-blue-500/10 text-blue-400 rounded-xl shrink-0">
                    <Stethoscope size={22} className="sm:w-6 sm:h-6" />
                  </div>
                  <h3 className="text-lg sm:text-xl font-bold text-white truncate">{t('treatments.create_new_treatment')}</h3>
                </div>
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="p-2 rounded-xl text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-all shrink-0"
                  aria-label={t('common.close')}
                >
                  <X size={22} />
                </button>
              </div>
              <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-6">
                  <div className="space-y-2">
                    <label className="block text-sm font-semibold text-white/60">{t('treatments.name')}</label>
                    <input
                      type="text"
                      value={newForm.name || ''}
                      onChange={(e) => setNewForm({ ...newForm, name: e.target.value })}
                      placeholder={t('treatments.placeholder_name')}
                      className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none font-medium"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-sm font-semibold text-white/60">{t('treatments.code_unique')}</label>
                    <input
                      type="text"
                      value={newForm.code || ''}
                      onChange={(e) => setNewForm({ ...newForm, code: e.target.value.toLowerCase().replace(/\s+/g, '_') })}
                      placeholder={t('treatments.placeholder_code')}
                      className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none font-mono text-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="block text-sm font-semibold text-white/60">{t('treatments.category')}</label>
                    <div className="relative">
                      <select
                        value={newForm.category || 'restorative'}
                        onChange={(e) => setNewForm({ ...newForm, category: e.target.value })}
                        className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none appearance-none cursor-pointer font-medium"
                      >
                        <option value="prevention">{t('treatments.category_prevention')}</option>
                        <option value="restorative">{t('treatments.category_restorative')}</option>
                        <option value="surgical">{t('treatments.category_surgical')}</option>
                        <option value="orthodontics">{t('treatments.category_orthodontics')}</option>
                        <option value="emergency">{t('treatments.emergency')}</option>
                      </select>
                      <Activity size={18} className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-white/30" />
                    </div>
                  </div>
                </div>

                <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-6">
                  <div className="space-y-2 sm:col-span-2">
                    <label className="block text-sm font-semibold text-white/60">{t('treatments.description')}</label>
                    <textarea
                      value={newForm.description || ''}
                      onChange={(e) => setNewForm({ ...newForm, description: e.target.value })}
                      placeholder={t('treatments.placeholder_description')}
                      className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/20 focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none resize-none font-medium h-[100px]"
                    />
                  </div>
                  <div className="space-y-2 sm:col-span-2">
                    <label className="block text-sm font-semibold text-white/60">{t('treatments.ai_response')}</label>
                    <p className="text-xs text-white/30">{t('treatments.ai_response_hint')}</p>
                    <textarea
                      value={newForm.ai_response_template || ''}
                      onChange={(e) => setNewForm({ ...newForm, ai_response_template: e.target.value })}
                      placeholder={t('treatments.placeholder_ai_response')}
                      className="w-full px-4 py-3 bg-white/[0.04] border border-indigo-500/20 rounded-xl text-white placeholder-white/20 focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 outline-none resize-none font-medium h-[120px]"
                      maxLength={1000}
                    />
                    <p className="text-xs text-white/20 text-right">{(newForm.ai_response_template || '').length}/1000</p>
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs font-bold text-white/40 uppercase tracking-wider">{t('treatments.duration_min')}</label>
                    <div className="relative">
                      <input
                        type="number"
                        value={newForm.default_duration_minutes || ''}
                        onChange={(e) => setNewForm({ ...newForm, default_duration_minutes: parseInt(e.target.value) })}
                        className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none font-bold"
                      />
                      <Clock size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-white/20" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs font-bold text-white/40 uppercase tracking-wider flex items-center gap-1.5">
                      {t('treatments.base_price_label') || 'Precio base ($)'}
                      <span className="relative group/tooltip inline-flex">
                        <Info size={12} className="text-white/30 cursor-help" />
                        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[#1a1f2e] border border-white/[0.08] rounded-lg text-[10px] text-white/70 whitespace-nowrap opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none z-50">
                          {t('treatments.priceTooltip')}
                        </span>
                      </span>
                    </label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 text-sm font-bold">$</span>
                      <input
                        type="number" step="1" min="0" placeholder="0"
                        value={newForm.base_price || ''}
                        onChange={(e) => setNewForm({ ...newForm, base_price: e.target.value ? parseFloat(e.target.value) : 0 })}
                        className="w-full pl-8 pr-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-blue-500/20 outline-none font-bold text-lg"
                      />
                    </div>
                    <p className="text-[10px] text-white/30">{t('treatments.priceHint')}</p>
                    {(newForm.base_price ?? 0) > 0 && (
                      <p className="text-[11px] text-blue-400 font-semibold">{formatARS(newForm.base_price ?? 0)}</p>
                    )}
                  </div>
                  <div className="space-y-2">
                    <label className="block text-xs font-bold text-white/40 uppercase tracking-wider">{t('treatments.complexity')}</label>
                    <select
                      value={newForm.complexity_level || 'medium'}
                      onChange={(e) => setNewForm({ ...newForm, complexity_level: e.target.value })}
                      className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none appearance-none cursor-pointer font-bold"
                    >
                      <option value="low">{t('treatments.low')}</option>
                      <option value="medium">{t('treatments.medium')}</option>
                      <option value="high">{t('treatments.high')}</option>
                    </select>
                  </div>
                </div>

                <div className="mt-6 flex items-center gap-3">
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={newForm.requires_multiple_sessions || false}
                      onChange={(e) => setNewForm({ ...newForm, requires_multiple_sessions: e.target.checked })}
                      className="h-5 w-5 rounded border-white/[0.08] text-blue-400 focus:ring-blue-500"
                    />
                    <span className="text-sm font-medium text-white/60">{t('treatments.multiple_sessions')}</span>
                  </label>
                </div>

                {/* Assigned Professionals */}
                {professionals.length > 0 && (
                  <div className="mt-6 space-y-3">
                    <div>
                      <label className="block text-sm font-semibold text-white/60 flex items-center gap-2">
                        <Users size={16} className="text-blue-400" />
                        {t('treatments.assigned_professionals')}
                      </label>
                      <p className="text-xs text-white/30 mt-0.5">{t('treatments.all_if_none')}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {professionals.map(prof => {
                        const selected = (newForm.professional_ids || []).includes(prof.id);
                        return (
                          <button
                            key={prof.id}
                            type="button"
                            onClick={() => {
                              const ids = newForm.professional_ids || [];
                              setNewForm({
                                ...newForm,
                                professional_ids: selected ? ids.filter(id => id !== prof.id) : [...ids, prof.id]
                              });
                            }}
                            className={`px-3 py-1.5 rounded-full text-xs font-bold border transition-all ${
                              selected
                                ? 'bg-medical-600 text-white border-medical-600 shadow-sm'
                                : 'bg-white/[0.04] text-white/60 border-white/[0.06] hover:border-blue-400/30 hover:text-blue-400'
                            }`}
                          >
                            {prof.first_name} {prof.last_name}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
              {/* Instructions teaser — create form */}
              <div className={`mx-4 sm:mx-6 mb-2 flex items-center gap-4 p-4 rounded-2xl border transition-all ${(newForm.pre_instructions || (newForm.post_instructions && newForm.post_instructions.length > 0)) ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-white/[0.02] border-white/[0.06]'}`}>
                <div className="flex-1 flex items-center gap-3">
                  {(newForm.pre_instructions || (newForm.post_instructions && newForm.post_instructions.length > 0)) ? (
                    <>
                      <CheckCircle2 size={20} className="text-emerald-400 shrink-0" />
                      <span className="text-sm font-semibold text-emerald-400">{t('treatments.instructions.configured')}</span>
                    </>
                  ) : (
                    <>
                      <FileText size={20} className="text-white/30 shrink-0" />
                      <div>
                        <p className="text-sm font-semibold text-white/60">{t('treatments.instructions.configureButton')}</p>
                        <p className="text-xs text-white/30 mt-0.5">{t('treatments.instructions.explanation')}</p>
                      </div>
                    </>
                  )}
                </div>
                <button type="button" onClick={() => openInstructionsModal('create')}
                  className="px-4 py-2 bg-white/[0.06] hover:bg-white/[0.10] border border-white/[0.08] rounded-xl text-sm font-semibold text-white/70 transition-all shrink-0">
                  {(newForm.pre_instructions || (newForm.post_instructions && newForm.post_instructions.length > 0)) ? t('treatments.instructions.editButton') : t('treatments.instructions.configureButton')}
                </button>
              </div>

              <div className="flex justify-end gap-3 p-4 sm:p-6 border-t border-white/[0.06] shrink-0 bg-white/[0.02]">
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="px-5 py-2.5 text-white/70 font-semibold hover:bg-white/[0.06] rounded-xl transition-all"
                >
                  {t('common.cancel')}
                </button>
                <button
                  type="button"
                  onClick={handleCreate}
                  disabled={saving}
                  className="px-6 sm:px-8 py-2.5 bg-white text-[#0a0e1a] rounded-xl font-bold hover:bg-white/90 transition-all disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98] flex items-center gap-2"
                >
                  {saving ? (
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  ) : <Save size={20} />}
                  {saving ? t('common.saving') : t('treatments.create_treatment')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Treatments by Category */}
        {loading ? (
          <div className="p-8 sm:p-12 lg:p-20 text-center flex flex-col items-center">
            <div className="w-16 h-16 border-4 border-white/[0.06] border-t-blue-400 rounded-full animate-spin mb-6"></div>
            <p className="font-bold text-white/30 text-lg">{t('treatments.syncing_services')}</p>
          </div>
        ) : (
          <div className="space-y-12 pb-20">
            {Object.entries(groupedTreatments).map(([category, categoryTreatments]) => (
              <GlassCard key={category} image={CARD_IMAGES.dental} hoverScale={false} className="rounded-[2.5rem]">
              <div className="overflow-hidden group">
                <div className="p-6 border-b border-white/[0.10] bg-white/[0.05] flex justify-between items-center sticky top-0 z-10 backdrop-blur-md transition-colors group-hover:bg-white/[0.07]">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-white/[0.08] rounded-2xl border border-white/[0.12]">
                      {categoryIcons[category] || <Stethoscope size={24} className="text-white/70" />}
                    </div>
                    <div>
                      <h2 className="font-bold text-white text-xl capitalize tracking-tight">{t('treatments.category_' + category) || category}</h2>
                      <span className="text-[10px] text-blue-400 font-bold uppercase tracking-widest">{categoryTreatments.length} {t('treatments.active_services')}</span>
                    </div>
                  </div>
                </div>

                <div className="divide-y divide-white/[0.08]">
                  {categoryTreatments.map((treatment) => (
                    <div key={treatment.id} className="p-6 hover:bg-white/[0.06] transition-all">
                      {editingId === treatment.id ? (
                        // Edit Mode
                        <div className="space-y-6 bg-white/[0.05] p-6 rounded-3xl border border-white/[0.10] animate-in fade-in zoom-in-95 duration-300">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                              <label className="block text-xs font-bold text-white/55 ml-1 uppercase">{t('treatments.service_name_label')}</label>
                              <input
                                type="text"
                                value={editForm.name || ''}
                                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all font-semibold"
                              />
                            </div>
                            <div className="space-y-2">
                              <label className="block text-xs font-bold text-white/55 ml-1 uppercase">{t('treatments.code_reference')}</label>
                              <input
                                type="text"
                                value={editForm.code || ''}
                                disabled
                                className="w-full px-4 py-3 bg-white/[0.02] border border-white/[0.06] rounded-xl text-white/30 font-mono text-sm cursor-not-allowed"
                              />
                            </div>
                          </div>

                          <div className="space-y-2">
                            <label className="block text-xs font-bold text-white/55 ml-1 uppercase">{t('treatments.clinical_description')}</label>
                            <textarea
                              value={editForm.description || ''}
                              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                              rows={2}
                              className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all resize-none font-medium"
                            />
                          </div>

                          <div className="space-y-2">
                            <label className="block text-xs font-bold text-white/55 ml-1 uppercase">{t('treatments.ai_response')}</label>
                            <p className="text-xs text-white/30 ml-1">{t('treatments.ai_response_hint')}</p>
                            <textarea
                              value={editForm.ai_response_template || ''}
                              onChange={(e) => setEditForm({ ...editForm, ai_response_template: e.target.value })}
                              placeholder={t('treatments.placeholder_ai_response')}
                              rows={4}
                              maxLength={1000}
                              className="w-full px-4 py-3 bg-white/[0.04] border border-indigo-500/20 rounded-xl text-white placeholder-white/20 focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none transition-all resize-none font-medium"
                            />
                            <p className="text-xs text-white/20 text-right">{(editForm.ai_response_template || '').length}/1000</p>
                          </div>

                          {/* Duration Settings */}
                          <div className="p-6 bg-blue-500/5 rounded-2xl border border-blue-500/10">
                            <h4 className="text-xs font-bold text-blue-400 mb-4 flex items-center gap-2 uppercase tracking-widest">
                              <Clock size={14} />
                              {t('treatments.time_config_minutes')}
                            </h4>
                            <div className="grid grid-cols-3 gap-6">
                              <div className="space-y-1">
                                <label className="block text-[10px] font-bold text-blue-400 uppercase">{t('treatments.min_label')}</label>
                                <input
                                  type="number"
                                  value={editForm.min_duration_minutes || ''}
                                  onChange={(e) => handleDurationChange('min', e.target.value)}
                                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:ring-2 focus:ring-blue-400 outline-none font-bold text-white text-center"
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="block text-[10px] font-bold text-blue-400 uppercase">{t('treatments.default_label')}</label>
                                <input
                                  type="number"
                                  value={editForm.default_duration_minutes || ''}
                                  onChange={(e) => handleDurationChange('default', e.target.value)}
                                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:ring-4 focus:ring-blue-400/20 outline-none font-bold text-white text-center text-lg"
                                />
                              </div>
                              <div className="space-y-1">
                                <label className="block text-[10px] font-bold text-blue-400 uppercase">{t('treatments.max_label')}</label>
                                <input
                                  type="number"
                                  value={editForm.max_duration_minutes || ''}
                                  onChange={(e) => handleDurationChange('max', e.target.value)}
                                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg focus:ring-2 focus:ring-blue-400 outline-none font-bold text-white text-center"
                                />
                              </div>
                            </div>
                          </div>

                          {/* Precio base */}
                          <div className="space-y-2">
                            <label className="block text-xs font-bold text-white/55 ml-1 uppercase flex items-center gap-1.5">
                              {t('treatments.base_price_label') || 'Precio base ($)'}
                              <span className="relative group/tooltip inline-flex">
                                <Info size={12} className="text-white/30 cursor-help" />
                                <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-2 py-1 bg-[#1a1f2e] border border-white/[0.08] rounded-lg text-[10px] text-white/70 whitespace-nowrap opacity-0 group-hover/tooltip:opacity-100 transition-opacity pointer-events-none z-50">
                                  {t('treatments.priceTooltip')}
                                </span>
                              </span>
                            </label>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 text-sm font-bold">$</span>
                              <input
                                type="number"
                                step="1"
                                min="0"
                                placeholder="0"
                                value={editForm.base_price || ''}
                                onChange={(e) => setEditForm({ ...editForm, base_price: e.target.value ? parseFloat(e.target.value) : 0 })}
                                className="w-full pl-8 pr-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none font-bold text-lg"
                              />
                            </div>
                            <p className="text-[10px] text-white/30 ml-1">{t('treatments.priceHint')}</p>
                            {(editForm.base_price ?? 0) > 0 && (
                              <p className="text-[11px] text-blue-400 font-semibold ml-1">{formatARS(editForm.base_price ?? 0)}</p>
                            )}
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            <div className="space-y-2">
                              <label className="block text-xs font-bold text-white/55 ml-1 uppercase">{t('treatments.complexity_level_label')}</label>
                              <select
                                value={editForm.complexity_level || 'medium'}
                                onChange={(e) => setEditForm({ ...editForm, complexity_level: e.target.value })}
                                className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none appearance-none font-bold"
                              >
                                <option value="low">{t('treatments.low')}</option>
                                <option value="medium">{t('treatments.medium')}</option>
                                <option value="high">{t('treatments.high')}</option>
                                <option value="emergency">{t('treatments.emergency')}</option>
                              </select>
                            </div>

                            <div className="flex flex-wrap items-center gap-6">
                              <label className="flex items-center gap-3 cursor-pointer group">
                                <div className="relative flex items-center">
                                  <input
                                    type="checkbox"
                                    checked={editForm.requires_multiple_sessions || false}
                                    onChange={(e) => setEditForm({ ...editForm, requires_multiple_sessions: e.target.checked })}
                                    className="peer h-6 w-6 cursor-pointer appearance-none rounded-lg border border-white/[0.08] bg-white/[0.04] transition-all checked:bg-purple-600 checked:border-purple-600 shadow-sm"
                                  />
                                  <CheckCircle className="absolute hidden h-4 w-4 text-white peer-checked:block left-1" />
                                </div>
                                <span className="text-sm font-bold text-white/40 group-hover:text-purple-600 transition-colors">{t('treatments.multiple_sessions')}</span>
                              </label>

                              <label className="flex items-center gap-3 cursor-pointer group">
                                <div className="relative flex items-center">
                                  <input
                                    type="checkbox"
                                    checked={editForm.is_active || false}
                                    onChange={(e) => setEditForm({ ...editForm, is_active: e.target.checked })}
                                    className="peer h-6 w-6 cursor-pointer appearance-none rounded-lg border border-white/[0.08] bg-white/[0.04] transition-all checked:bg-green-600 checked:border-green-600 shadow-sm"
                                  />
                                  <CheckCircle className="absolute hidden h-4 w-4 text-white peer-checked:block left-1" />
                                </div>
                                <span className="text-sm font-bold text-white/40 group-hover:text-green-600 transition-colors">{t('treatments.active')}</span>
                              </label>

                              <label className="flex items-center gap-3 cursor-pointer group">
                                <div className="relative flex items-center">
                                  <input
                                    type="checkbox"
                                    checked={editForm.is_available_for_booking || false}
                                    onChange={(e) => setEditForm({ ...editForm, is_available_for_booking: e.target.checked })}
                                    className="peer h-6 w-6 cursor-pointer appearance-none rounded-lg border border-white/[0.08] bg-white/[0.04] transition-all checked:bg-blue-600 checked:border-blue-600 shadow-sm"
                                  />
                                  <CheckCircle className="absolute hidden h-4 w-4 text-white peer-checked:block left-1" />
                                </div>
                                <span className="text-sm font-bold text-white/40 group-hover:text-blue-600 transition-colors">{t('treatments.in_catalog')}</span>
                              </label>
                            </div>
                          </div>

                          {/* Consultation (High Ticket) */}
                          <div className="space-y-3 border border-amber-500/20 rounded-xl p-4 bg-amber-500/[0.03]">
                            <label className="flex items-center gap-3 cursor-pointer group">
                              <div className="relative flex items-center">
                                <input
                                  type="checkbox"
                                  checked={editForm.is_high_ticket || false}
                                  onChange={(e) => setEditForm({ ...editForm, is_high_ticket: e.target.checked })}
                                  className="peer h-6 w-6 cursor-pointer appearance-none rounded-lg border border-white/[0.08] bg-white/[0.04] transition-all checked:bg-amber-600 checked:border-amber-600 shadow-sm"
                                />
                                <CheckCircle className="absolute hidden h-4 w-4 text-white peer-checked:block left-1" />
                              </div>
                              <span className="text-sm font-bold text-white/40 group-hover:text-amber-500 transition-colors">{t('treatments.requires_consultation')}</span>
                            </label>
                            {editForm.is_high_ticket && (
                              <div className="space-y-3 mt-2">
                                <div>
                                  <label className="block text-xs font-bold text-white/55 ml-1 uppercase">{t('treatments.consultation_duration')}</label>
                                  <input
                                    type="number"
                                    min={15}
                                    max={120}
                                    value={editForm.consultation_duration_minutes ?? 30}
                                    onChange={(e) => setEditForm({ ...editForm, consultation_duration_minutes: parseInt(e.target.value) || 30 })}
                                    className="w-full mt-1 px-4 py-3 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white text-sm focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500/30"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-bold text-white/55 ml-1 uppercase">{t('treatments.consultation_requirements')}</label>
                                  <textarea
                                    rows={2}
                                    value={editForm.consultation_requirements || ''}
                                    onChange={(e) => setEditForm({ ...editForm, consultation_requirements: e.target.value })}
                                    placeholder={t('treatments.consultation_requirements_placeholder')}
                                    className="w-full mt-1 px-4 py-3 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white text-sm focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500/30 placeholder-white/20 resize-none"
                                  />
                                </div>
                                <div>
                                  <label className="block text-xs font-bold text-white/55 ml-1 uppercase">{t('treatments.consultation_notes')}</label>
                                  <textarea
                                    rows={2}
                                    value={editForm.consultation_notes || ''}
                                    onChange={(e) => setEditForm({ ...editForm, consultation_notes: e.target.value })}
                                    placeholder={t('treatments.consultation_notes_placeholder')}
                                    className="w-full mt-1 px-4 py-3 border border-white/[0.08] rounded-xl bg-white/[0.04] text-white text-sm focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500/30 placeholder-white/20 resize-none"
                                  />
                                </div>
                              </div>
                            )}
                          </div>

                          {/* Assigned Professionals */}
                          {professionals.length > 0 && (
                            <div className="space-y-3">
                              <div>
                                <label className="block text-xs font-bold text-white/55 ml-1 uppercase flex items-center gap-2">
                                  <Users size={14} className="text-blue-400" />
                                  {t('treatments.assigned_professionals')}
                                </label>
                                <p className="text-xs text-white/30 mt-0.5 ml-1">{t('treatments.all_if_none')}</p>
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {professionals.map(prof => {
                                  const selected = (editForm.professional_ids || []).includes(prof.id);
                                  return (
                                    <button
                                      key={prof.id}
                                      type="button"
                                      onClick={() => {
                                        const ids = editForm.professional_ids || [];
                                        setEditForm({
                                          ...editForm,
                                          professional_ids: selected ? ids.filter(id => id !== prof.id) : [...ids, prof.id]
                                        });
                                      }}
                                      className={`px-3 py-1.5 rounded-full text-xs font-bold border transition-all ${
                                        selected
                                          ? 'bg-medical-600 text-white border-medical-600 shadow-sm'
                                          : 'bg-white/[0.04] text-white/60 border-white/[0.06] hover:border-blue-400/30 hover:text-blue-400'
                                      }`}
                                    >
                                      {prof.first_name} {prof.last_name}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                          )}

                          {/* Instructions teaser — edit form */}
                          <div className={`flex items-center gap-4 p-4 rounded-2xl border transition-all ${(editForm.pre_instructions || (editForm.post_instructions && editForm.post_instructions.length > 0)) ? 'bg-emerald-500/5 border-emerald-500/20' : 'bg-white/[0.02] border-white/[0.06]'}`}>
                            <div className="flex-1 flex items-center gap-3">
                              {(editForm.pre_instructions || (editForm.post_instructions && editForm.post_instructions.length > 0)) ? (
                                <>
                                  <CheckCircle2 size={20} className="text-emerald-400 shrink-0" />
                                  <span className="text-sm font-semibold text-emerald-400">{t('treatments.instructions.configured')}</span>
                                </>
                              ) : (
                                <>
                                  <FileText size={20} className="text-white/30 shrink-0" />
                                  <div>
                                    <p className="text-sm font-semibold text-white/60">{t('treatments.instructions.configureButton')}</p>
                                    <p className="text-xs text-white/30 mt-0.5">{t('treatments.instructions.explanation')}</p>
                                  </div>
                                </>
                              )}
                            </div>
                            <button type="button" onClick={() => openInstructionsModal('edit')}
                              className="px-4 py-2 bg-white/[0.06] hover:bg-white/[0.10] border border-white/[0.08] rounded-xl text-sm font-semibold text-white/70 transition-all shrink-0">
                              {(editForm.pre_instructions || (editForm.post_instructions && editForm.post_instructions.length > 0)) ? t('treatments.instructions.editButton') : t('treatments.instructions.configureButton')}
                            </button>
                          </div>

                          <div className="flex justify-end gap-3 pt-4 border-t border-white/[0.06]">
                            <button
                              onClick={handleCancel}
                              className="px-6 py-2.5 text-white/40 font-bold hover:bg-white/[0.04] rounded-xl transition-all"
                            >
                              {t('common.cancel')}
                            </button>
                            <button
                              onClick={() => handleSave(treatment.code)}
                              disabled={saving}
                              className="px-8 py-2.5 bg-white text-[#0a0e1a] rounded-xl font-bold hover:bg-white/90 transition-all active:scale-95 flex items-center gap-2"
                            >
                              {saving ? (
                                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                              ) : <Save size={18} />}
                              {saving ? t('common.saving') : t('treatments.update_service')}
                            </button>
                          </div>
                        </div>
                      ) : (
                        // View Mode
                        <div className="flex items-start justify-between group/item">
                          <div className="flex-1">
                            <div className="flex items-center flex-wrap gap-3 mb-3">
                              <h3 className="font-bold text-white text-lg tracking-tight">{treatment.name}</h3>
                              <span className={`inline-flex items-center px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${treatment.complexity_level === 'high' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                                treatment.complexity_level === 'medium' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' :
                                  'bg-green-500/10 text-green-400 border-green-500/20'
                                }`}>
                                {t('treatments.' + (treatment.complexity_level || 'medium'))}
                              </span>
                              {treatment.requires_multiple_sessions && (
                                <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                  <CheckCircle size={10} />
                                  {t('treatments.multiple_sessions')}
                                </span>
                              )}
                              {!treatment.is_active && (
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest bg-white/[0.06] text-white/30 border border-white/[0.06]">
                                  {t('treatments.inactive')}
                                </span>
                              )}
                            </div>

                            {treatment.description && (
                              <p className="text-white/60 text-sm leading-relaxed mb-4 max-w-2xl font-medium">{treatment.description}</p>
                            )}

                            <div className="flex flex-wrap items-center gap-y-2 gap-x-8">
                              <div className="flex items-center gap-2.5">
                                <div className="p-1.5 bg-blue-500/15 text-blue-400 rounded-lg">
                                  <Clock size={14} />
                                </div>
                                <span className="text-white/70 text-sm font-semibold">
                                  <strong className="text-white text-base">{treatment.default_duration_minutes}</strong> {t('common.minutes_short')} <span className="text-white/50 font-medium">{t('treatments.min_standard')}</span>
                                </span>
                              </div>
                              <div className="h-4 w-px bg-white/[0.10] hidden sm:block"></div>
                              <div className="flex items-center gap-4 text-xs font-bold text-white/50 uppercase tracking-tight">
                               <span>{t('treatments.min_short')}: <span className="text-white/90">{treatment.min_duration_minutes}{t('common.min_short')}</span></span>
                                <span>{t('treatments.max_short')}: <span className="text-white/90">{treatment.max_duration_minutes}{t('common.min_short')}</span></span>
                              </div>
                              {treatment.session_gap_days > 0 && (
                                <div className="flex items-center gap-2 text-xs font-bold text-purple-500 uppercase tracking-tight">
                                  <Activity size={12} />
                                  <span>{treatment.session_gap_days} {t('treatments.session_gap_days')}</span>
                                </div>
                              )}
                            </div>

                            {/* Assigned Professionals Badges */}
                            {professionals.length > 0 && (
                              <div className="flex items-center gap-2 mt-3 flex-wrap">
                                <Users size={14} className="text-white/50 shrink-0" />
                                {(treatment.professional_ids || []).length > 0 ? (
                                  professionals
                                    .filter(p => (treatment.professional_ids || []).includes(p.id))
                                    .map(p => (
                                      <span key={p.id} className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                        {p.first_name} {p.last_name}
                                      </span>
                                    ))
                                ) : (
                                  <span className="text-xs text-white/30 font-medium">{t('treatments.all_professionals')}</span>
                                )}
                              </div>
                            )}

                            {/* IMAGES GALLERY */}
                            <TreatmentImagesList code={treatment.code} />
                          </div>

                          <div className="flex gap-2 opacity-0 group-hover/item:opacity-100 transition-all translate-x-2 group-hover/item:translate-x-0">
                            <button
                              onClick={() => handleEdit(treatment)}
                              className="p-3 text-white/30 hover:text-blue-400 hover:bg-blue-500/10 rounded-2xl transition-all bg-white/[0.04] border border-white/[0.06]"
                              title={t('common.edit')}
                            >
                              <Edit2 size={18} />
                            </button>
                            <button
                              onClick={() => handleDelete(treatment.code)}
                              className="p-3 text-white/30 hover:text-red-400 hover:bg-red-500/10 rounded-2xl transition-all bg-white/[0.04] border border-white/[0.06]"
                              title={t('common.delete')}
                            >
                              <X size={18} />
                            </button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              </GlassCard>
            ))}
          </div>
        )}

        {/* Empty State */}
        {!loading && treatments.length === 0 && (
          <GlassCard image={CARD_IMAGES.dental} hoverScale={false} className="rounded-[2.5rem] animate-in fade-in duration-700">
          <div className="p-8 sm:p-12 lg:p-20 text-center">
            <div className="w-24 h-24 bg-blue-500/10 text-blue-400/30 rounded-full flex items-center justify-center mx-auto mb-8">
              <Activity size={48} strokeWidth={1.5} />
            </div>
            <h3 className="text-2xl font-bold text-white mb-3">{t('treatments.no_treatments_defined')}</h3>
            <p className="text-white/40 max-w-sm mx-auto mb-8 font-medium">
              {t('treatments.empty_hint')}
            </p>
            <button
              onClick={() => setIsCreating(true)}
              className="px-8 py-4 bg-white text-[#0a0e1a] rounded-2xl font-bold hover:bg-white/90 transition-all flex items-center gap-2 mx-auto active:scale-95"
            >
              <Zap size={20} fill="currentColor" />
              {t('treatments.setup_first_service')}
            </button>
            <div className="mt-12 p-4 bg-blue-500/10 rounded-2xl border border-blue-500/20 inline-block text-blue-400 text-xs font-bold uppercase tracking-widest">
              {t('treatments.tip_migration')}
            </div>
          </div>
          </GlassCard>
        )}
      </div>

      {/* ── Instructions Modal (higher z-index, overlays treatment modals) ── */}
      {instructionsModalOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4" onClick={e => e.target === e.currentTarget && setInstructionsModalOpen(false)}>
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-2xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center gap-3 p-4 sm:p-6 border-b border-white/[0.06] shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-blue-500/10 text-blue-400 rounded-xl">
                  <FileText size={20} />
                </div>
                <h3 className="text-lg sm:text-xl font-bold text-white">{t('treatments.instructions.modalTitle')}</h3>
              </div>
              <button type="button" onClick={() => setInstructionsModalOpen(false)} className="p-2 rounded-xl text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-all shrink-0">
                <X size={22} />
              </button>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-8">
              {/* Legal disclaimer (migration 037) */}
              <div className="bg-amber-500/10 border border-amber-500/20 text-amber-300 text-xs rounded-xl px-4 py-3 flex items-start gap-2">
                <AlertCircle size={14} className="shrink-0 mt-0.5" />
                <p>{t('treatments.instructions.disclaimer')}</p>
              </div>

              {/* Section 1: Pre-treatment (structured — migration 037) */}
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <Info size={16} className="text-blue-400 shrink-0" />
                  <h4 className="font-bold text-white">{t('treatments.instructions.pre.title')}</h4>
                </div>
                <p className="text-xs text-white/40">{t('treatments.instructions.pre.helper')}</p>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="space-y-1">
                    <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                      {t('treatments.instructions.pre.preparationDaysBefore')}
                    </label>
                    <input
                      type="number" min="0"
                      value={instructionsLocal.preForm.preparation_days_before ?? ''}
                      onChange={e => updatePreField('preparation_days_before', e.target.value === '' ? null : parseInt(e.target.value))}
                      className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-blue-500/20"
                    />
                  </div>

                  <div className="space-y-1">
                    <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                      {t('treatments.instructions.pre.fastingRequired')}
                    </label>
                    <select
                      value={instructionsLocal.preForm.fasting_required === null ? '' : instructionsLocal.preForm.fasting_required ? 'yes' : 'no'}
                      onChange={e => {
                        const val = e.target.value;
                        updatePreField('fasting_required', val === '' ? null : val === 'yes');
                      }}
                      className="w-full px-3 py-2 bg-[#0d1117] border border-white/[0.08] rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-blue-500/20 [&>option]:bg-[#0d1117]"
                    >
                      <option value="">—</option>
                      <option value="yes">{t('common.yes')}</option>
                      <option value="no">{t('common.no')}</option>
                    </select>
                  </div>

                  {instructionsLocal.preForm.fasting_required === true && (
                    <div className="space-y-1">
                      <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                        {t('treatments.instructions.pre.fastingHours')}
                      </label>
                      <input
                        type="number" min="0"
                        value={instructionsLocal.preForm.fasting_hours ?? ''}
                        onChange={e => updatePreField('fasting_hours', e.target.value === '' ? null : parseInt(e.target.value))}
                        className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-blue-500/20"
                      />
                    </div>
                  )}
                </div>

                <StringListEditor
                  label={t('treatments.instructions.pre.medicationsToAvoid')}
                  items={instructionsLocal.preForm.medications_to_avoid}
                  onChange={items => updatePreField('medications_to_avoid', items)}
                  placeholder="Aspirina"
                  accentColor="amber"
                />
                <StringListEditor
                  label={t('treatments.instructions.pre.medicationsToTake')}
                  items={instructionsLocal.preForm.medications_to_take}
                  onChange={items => updatePreField('medications_to_take', items)}
                  placeholder="Paracetamol 500mg 1h antes"
                />
                <StringListEditor
                  label={t('treatments.instructions.pre.whatToBring')}
                  items={instructionsLocal.preForm.what_to_bring}
                  onChange={items => updatePreField('what_to_bring', items)}
                  placeholder="DNI, estudios previos"
                />

                <div className="space-y-1">
                  <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                    {t('treatments.instructions.pre.generalNotes')}
                  </label>
                  <textarea
                    value={instructionsLocal.preForm.general_notes}
                    onChange={e => updatePreField('general_notes', e.target.value)}
                    placeholder={t('treatments.instructions.pre.placeholder')}
                    rows={4}
                    className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-blue-500/20 resize-none"
                  />
                </div>
              </div>

              {/* Section 2: Post-treatment (tab switcher between structured + legacy) */}
              <div className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <h4 className="font-bold text-white">{t('treatments.instructions.post.title')}</h4>
                  <div className="flex gap-1 bg-white/[0.04] rounded-xl p-1">
                    <button
                      type="button"
                      onClick={() => setPostEditMode('protocol')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${postEditMode === 'protocol' ? 'bg-white text-[#0a0e1a]' : 'text-white/60 hover:text-white'}`}
                    >
                      {t('treatments.instructions.post.modeProtocol')}
                    </button>
                    <button
                      type="button"
                      onClick={() => setPostEditMode('sequence')}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors ${postEditMode === 'sequence' ? 'bg-white text-[#0a0e1a]' : 'text-white/60 hover:text-white'}`}
                    >
                      {t('treatments.instructions.post.modeSequence')}
                    </button>
                  </div>
                </div>

                {postEditMode === 'protocol' ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      <div className="space-y-1">
                        <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                          {t('treatments.instructions.post.careDurationDays')}
                        </label>
                        <input
                          type="number" min="0"
                          value={instructionsLocal.postForm.care_duration_days ?? ''}
                          onChange={e => updatePostField('care_duration_days', e.target.value === '' ? null : parseInt(e.target.value))}
                          className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-blue-500/20"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-semibold uppercase tracking-wider text-white/60">
                          {t('treatments.instructions.post.suturesRemovalDay')}
                        </label>
                        <input
                          type="number" min="0"
                          value={instructionsLocal.postForm.sutures_removal_day ?? ''}
                          onChange={e => updatePostField('sutures_removal_day', e.target.value === '' ? null : parseInt(e.target.value))}
                          className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white text-sm outline-none focus:ring-2 focus:ring-blue-500/20"
                        />
                      </div>
                    </div>

                    <StringListEditor
                      label={t('treatments.instructions.post.dietaryRestrictions')}
                      items={instructionsLocal.postForm.dietary_restrictions}
                      onChange={items => updatePostField('dietary_restrictions', items)}
                      placeholder="No comer caliente por 24h"
                    />
                    <StringListEditor
                      label={t('treatments.instructions.post.activityRestrictions')}
                      items={instructionsLocal.postForm.activity_restrictions}
                      onChange={items => updatePostField('activity_restrictions', items)}
                      placeholder="No actividad física intensa por 48h"
                    />
                    <StringListEditor
                      label={t('treatments.instructions.post.allowedMedications')}
                      items={instructionsLocal.postForm.allowed_medications}
                      onChange={items => updatePostField('allowed_medications', items)}
                      placeholder="Ibuprofeno 400mg cada 8h"
                    />
                    <StringListEditor
                      label={t('treatments.instructions.post.prohibitedMedications')}
                      items={instructionsLocal.postForm.prohibited_medications}
                      onChange={items => updatePostField('prohibited_medications', items)}
                      placeholder="Aspirina"
                      accentColor="amber"
                    />
                    <StringListEditor
                      label={t('treatments.instructions.post.normalSymptoms')}
                      items={instructionsLocal.postForm.normal_symptoms}
                      onChange={items => updatePostField('normal_symptoms', items)}
                      placeholder="Ligero sangrado las primeras 24h"
                    />
                    <StringListEditor
                      label={t('treatments.instructions.post.alarmSymptoms')}
                      items={instructionsLocal.postForm.alarm_symptoms}
                      onChange={items => updatePostField('alarm_symptoms', items)}
                      placeholder="Sangrado abundante que no cede"
                      accentColor="red"
                    />

                    <div className="space-y-1">
                      <label className="text-xs font-semibold uppercase tracking-wider text-red-400">
                        {t('treatments.instructions.post.escalationMessage')}
                      </label>
                      <textarea
                        value={instructionsLocal.postForm.escalation_message}
                        onChange={e => updatePostField('escalation_message', e.target.value)}
                        placeholder="Contactá inmediatamente a la clínica al…"
                        rows={2}
                        maxLength={500}
                        className="w-full px-3 py-2 bg-white/[0.04] border border-red-500/20 rounded-xl text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-red-500/20 resize-none"
                      />
                      <p className="text-[10px] text-white/30">
                        {t('treatments.instructions.post.escalationHelper')}
                      </p>
                    </div>
                  </div>
                ) : (
                  <>
                    <p className="text-xs text-white/40">{t('treatments.instructions.post.legacyHelper')}</p>
                    <div className="space-y-3">
                      {instructionsLocal.timedSequence.map((item, idx) => (
                        <div key={idx} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4 space-y-3">
                          <div className="flex items-center gap-3">
                            <select
                              value={item.timing}
                              onChange={e => updatePostInstruction(idx, 'timing', e.target.value as PostTiming)}
                              className="flex-1 px-3 py-2 bg-[#0d1117] border border-white/[0.08] rounded-lg text-white text-sm focus:ring-2 focus:ring-blue-500/20 outline-none [&>option]:bg-[#0d1117]"
                            >
                              {(['immediate', '24h', '48h', '72h', '1w', 'stitch_removal', 'custom'] as PostTiming[]).map(timing => (
                                <option key={timing} value={timing}>{t(`treatments.instructions.post.timing.${timing}`)}</option>
                              ))}
                            </select>
                            {(item.timing === 'stitch_removal' || item.timing === 'custom') && (
                              <div className="flex items-center gap-2">
                                <input
                                  type="number" min="1" value={item.custom_days || ''} onChange={e => updatePostInstruction(idx, 'custom_days', parseInt(e.target.value) || undefined)}
                                  className="w-20 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-2 focus:ring-blue-500/20"
                                />
                                <span className="text-xs text-white/40">{t('treatments.instructions.post.days')}</span>
                              </div>
                            )}
                            <button type="button" onClick={() => removePostInstruction(idx)} className="p-1.5 text-white/30 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors shrink-0">
                              <X size={16} />
                            </button>
                          </div>
                          {item.timing === 'stitch_removal' && (
                            <label className="flex items-center gap-2 cursor-pointer">
                              <input type="checkbox" checked={item.book_followup || false} onChange={e => updatePostInstruction(idx, 'book_followup', e.target.checked)} className="h-4 w-4 rounded border-white/[0.08] text-blue-400 focus:ring-blue-500" />
                              <span className="text-xs text-white/60">{t('treatments.instructions.post.bookFollowup')}</span>
                            </label>
                          )}
                          <textarea
                            value={item.content} onChange={e => updatePostInstruction(idx, 'content', e.target.value)}
                            placeholder={t('treatments.instructions.post.contentPlaceholder')} rows={3}
                            className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-blue-500/20 resize-none"
                          />
                        </div>
                      ))}
                    </div>
                    <button type="button" onClick={addPostInstruction} className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 font-semibold transition-colors">
                      <Plus size={16} /> {t('treatments.instructions.post.addButton')}
                    </button>
                  </>
                )}
              </div>

              {/* Section 3: Follow-up messages */}
              <div className="space-y-3">
                <h4 className="font-bold text-white">{t('treatments.instructions.followup.title')}</h4>
                <div className="flex items-start gap-2 bg-blue-500/5 border border-blue-500/20 rounded-lg p-3">
                  <Info size={14} className="text-blue-400 shrink-0 mt-0.5" />
                  <p className="text-xs text-blue-300/80">{t('treatments.instructions.followup.inDevelopment')}</p>
                </div>
                <p className="text-xs text-white/30">{t('treatments.instructions.followup.variables')}</p>
                <div className="space-y-3">
                  {instructionsLocal.followup_template.map((item, idx) => (
                    <div key={idx} className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4 space-y-3">
                      <div className="flex items-center gap-3">
                        <input type="number" min="1" value={item.hours_after} onChange={e => updateFollowup(idx, 'hours_after', parseInt(e.target.value) || 24)}
                          className="w-20 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-2 focus:ring-blue-500/20" />
                        <span className="text-xs text-white/40 shrink-0">{t('treatments.instructions.followup.hoursAfter')}</span>
                        <div className="flex-1" />
                        <button type="button" onClick={() => removeFollowup(idx)} className="p-1.5 text-white/30 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors">
                          <X size={16} />
                        </button>
                      </div>
                      <textarea
                        value={item.message} onChange={e => updateFollowup(idx, 'message', e.target.value)}
                        placeholder={t('treatments.instructions.followup.messagePlaceholder')} rows={3}
                        className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm placeholder-white/20 outline-none focus:ring-2 focus:ring-blue-500/20 resize-none"
                      />
                    </div>
                  ))}
                </div>
                <button type="button" onClick={addFollowup} className="flex items-center gap-2 text-sm text-blue-400 hover:text-blue-300 font-semibold transition-colors">
                  <Plus size={16} /> {t('treatments.instructions.followup.addButton')}
                </button>
              </div>
            </div>

            <div className="flex justify-end gap-3 p-4 sm:p-6 border-t border-white/[0.06] shrink-0 bg-white/[0.02]">
              <button type="button" onClick={() => setInstructionsModalOpen(false)} className="px-5 py-2.5 text-white/70 font-semibold hover:bg-white/[0.06] rounded-xl transition-all">
                {t('treatments.instructions.cancel')}
              </button>
              <button type="button" onClick={saveInstructions} className="px-6 py-2.5 bg-white text-[#0a0e1a] rounded-xl font-bold hover:bg-white/90 transition-all active:scale-[0.98] flex items-center gap-2">
                <Save size={18} /> {t('treatments.instructions.save')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Price Audit Modal (CEO only) ── */}
      {auditOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[60] flex items-center justify-center p-4"
          onClick={(e) => e.target === e.currentTarget && setAuditOpen(false)}
        >
          <div className="bg-[#0d1117] border border-white/[0.08] rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center gap-3 p-4 sm:p-6 border-b border-white/[0.06] shrink-0">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-amber-500/10 text-amber-400 rounded-xl">
                  <Search size={20} />
                </div>
                <h3 className="text-lg font-bold text-white">{t('treatments.auditModalTitle')}</h3>
              </div>
              <button
                type="button"
                onClick={() => setAuditOpen(false)}
                className="p-2 rounded-xl text-white/30 hover:text-white/60 hover:bg-white/[0.04] transition-all"
              >
                <X size={22} />
              </button>
            </div>
            <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6">
              {auditLoading ? (
                <div className="flex items-center justify-center py-12">
                  <div className="w-10 h-10 border-4 border-white/[0.06] border-t-amber-400 rounded-full animate-spin" />
                </div>
              ) : !auditResult ? (
                <p className="text-white/40 text-sm text-center py-8">{t('common.error') || 'Error al cargar'}</p>
              ) : auditResult.warning ? (
                <p className="text-amber-400/70 text-sm text-center py-8">{auditResult.warning}</p>
              ) : auditResult.suspicious.length === 0 ? (
                <div className="flex flex-col items-center gap-3 py-10">
                  <CheckCircle2 size={40} className="text-emerald-400" />
                  <p className="text-emerald-400 font-semibold">{t('treatments.auditNoIssues')}</p>
                  {auditResult.consultation_price && (
                    <p className="text-white/30 text-xs">
                      Umbral: {formatARS(auditResult.threshold ?? 0)} (consulta × 100)
                    </p>
                  )}
                </div>
              ) : (
                <div className="space-y-4">
                  {auditResult.consultation_price && (
                    <p className="text-white/40 text-xs mb-4">
                      Precio de consulta: {formatARS(auditResult.consultation_price)} — Umbral: {formatARS(auditResult.threshold ?? 0)}
                    </p>
                  )}
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-white/30 text-[10px] uppercase tracking-widest border-b border-white/[0.06]">
                        <th className="text-left pb-2">{t('treatments.auditTableHeaderName')}</th>
                        <th className="text-right pb-2">{t('treatments.auditTableHeaderPrice')}</th>
                        <th className="text-right pb-2">{t('treatments.auditTableHeaderRatio')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/[0.04]">
                      {auditResult.suspicious.map((item) => (
                        <tr key={item.code} className="text-white">
                          <td className="py-3 font-semibold">{item.name}<span className="ml-2 text-white/30 font-mono text-[10px]">{item.code}</span></td>
                          <td className="py-3 text-right text-amber-400 font-bold">{formatARS(item.base_price)}</td>
                          <td className="py-3 text-right text-red-400 font-bold">{item.ratio}×</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Unusual Price Confirmation Dialog (Bug #3) ── */}
      {unusualPriceConfirm && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[70] flex items-center justify-center p-4">
          <div className="bg-[#0d1117] border border-amber-500/20 rounded-2xl w-full max-w-md p-6 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex items-start gap-4 mb-5">
              <div className="p-2.5 bg-amber-500/10 text-amber-400 rounded-xl shrink-0">
                <AlertCircle size={20} />
              </div>
              <p className="text-white font-semibold leading-relaxed">{t('treatments.priceConfirmUnusual')}</p>
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setUnusualPriceConfirm(null)}
                className="px-5 py-2.5 text-white/70 font-semibold hover:bg-white/[0.06] rounded-xl transition-all"
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={() => {
                  if (unusualPriceConfirm.context === 'create') {
                    handleCreate(true);
                  } else if (unusualPriceConfirm.context === 'edit' && unusualPriceConfirm.code) {
                    handleSave(unusualPriceConfirm.code, true);
                  }
                }}
                className="px-6 py-2.5 bg-amber-500 text-white rounded-xl font-bold hover:bg-amber-400 transition-all active:scale-[0.98]"
              >
                {t('common.confirm') || 'Confirmar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
