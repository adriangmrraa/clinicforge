import React, { useState, useEffect } from 'react';
import { Clock, AlertCircle, CheckCircle, Save, X, Zap, Shield, Heart, Activity, Stethoscope, Edit2, Upload, Trash2, Image as ImageIcon, Users } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
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
  priority?: 'high' | 'medium-high' | 'medium' | 'low';
}

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

export default function TreatmentsView() {
  const { t } = useTranslation();
  const [treatments, setTreatments] = useState<TreatmentType[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<Partial<TreatmentType>>({});
  const [saving, setSaving] = useState(false);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [isCreating, setIsCreating] = useState(false);
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
    priority: 'medium' as const
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

  const handleSave = async (code: string) => {
    if (!editForm.code) return;

    try {
      setSaving(true);
      await api.put(`/admin/treatment-types/${code}`, editForm);
      await api.put(`/admin/treatment-types/${code}/professionals`, { professional_ids: editForm.professional_ids || [] });
      await fetchTreatments();
      setEditingId(null);
      setEditForm({});
    } catch (error) {
      console.error('Error saving treatment:', error);
      alert(t('alerts.error_save_treatment'));
    } finally {
      setSaving(false);
    }
  };

  const handleCreate = async () => {
    if (!newForm.code || !newForm.name) {
      alert(t('alerts.code_name_required'));
      return;
    }

    try {
      setSaving(true);
      await api.post('/admin/treatment-types', newForm);
      await fetchTreatments();
      setIsCreating(false);
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
        priority: 'medium' as const,
        professional_ids: []
      });
    } catch (error: any) {
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
            <button
              onClick={() => setIsCreating(true)}
              className="px-4 sm:px-5 py-2.5 bg-white text-[#0a0e1a] rounded-xl hover:bg-white/90 transition-all flex items-center justify-center gap-2 active:scale-[0.98] font-semibold text-sm"
            >
              <Zap size={18} fill="currentColor" />
              {t('treatments.new_service')}
            </button>
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
            <div className="flex items-center gap-4 p-4 bg-white/[0.03] rounded-2xl border border-white/[0.06] hover:border-white/[0.12] transition-colors">
              <div className="p-3 bg-blue-500/10 text-blue-400 rounded-xl">
                <Clock size={20} />
              </div>
              <div className="flex flex-col">
                <span className="text-white/40 font-medium uppercase text-[10px] tracking-wider">{t('treatments.urgency_consult')}</span>
                <span className="text-white font-bold text-lg">15 {t('common.minutes_short')}</span>
              </div>
            </div>
            <div className="flex items-center gap-4 p-4 bg-white/[0.03] rounded-2xl border border-white/[0.06] hover:border-white/[0.12] transition-colors">
              <div className="p-3 bg-green-500/10 text-green-400 rounded-xl">
                <Clock size={20} />
              </div>
              <div className="flex flex-col">
                <span className="text-white/40 font-medium uppercase text-[10px] tracking-wider">{t('treatments.deep_cleaning')}</span>
                <span className="text-white font-bold text-lg">30 {t('common.minutes_short')}</span>
              </div>
            </div>
            <div className="flex items-center gap-4 p-4 bg-white/[0.03] rounded-2xl border border-white/[0.06] hover:border-white/[0.12] transition-colors">
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
                    <label className="block text-xs font-bold text-white/40 uppercase tracking-wider">{t('treatments.base_price_label') || 'Precio base ($)'}</label>
                    <div className="relative">
                      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-white/30 text-sm font-bold">$</span>
                      <input
                        type="number" step="1" min="0" placeholder="0"
                        value={newForm.base_price || ''}
                        onChange={(e) => setNewForm({ ...newForm, base_price: e.target.value ? parseFloat(e.target.value) : 0 })}
                        className="w-full pl-8 pr-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-blue-500/20 outline-none font-bold text-lg"
                      />
                    </div>
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
                  <div className="space-y-2">
                    <label className="block text-xs font-bold text-white/40 uppercase tracking-wider">{t('professionals.priority.label')}</label>
                    <select
                      value={newForm.priority || 'medium'}
                      onChange={(e) => setNewForm({ ...newForm, priority: e.target.value as TreatmentType['priority'] })}
                      className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 outline-none appearance-none cursor-pointer font-bold"
                    >
                      <option value="high">{t('professionals.priority.high')}</option>
                      <option value="medium-high">{t('professionals.priority.mediumHigh')}</option>
                      <option value="medium">{t('professionals.priority.medium')}</option>
                      <option value="low">{t('professionals.priority.low')}</option>
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
                <div className="p-6 border-b border-white/[0.06] bg-white/[0.02] flex justify-between items-center sticky top-0 z-10 backdrop-blur-md transition-colors group-hover:bg-white/[0.04]">
                  <div className="flex items-center gap-4">
                    <div className="p-3 bg-white/[0.06] rounded-2xl border border-white/[0.06]">
                      {categoryIcons[category] || <Stethoscope size={24} className="text-white/60" />}
                    </div>
                    <div>
                      <h2 className="font-bold text-white text-xl capitalize tracking-tight">{t('treatments.category_' + category) || category}</h2>
                      <span className="text-[10px] text-blue-400 font-bold uppercase tracking-widest">{categoryTreatments.length} {t('treatments.active_services')}</span>
                    </div>
                  </div>
                </div>

                <div className="divide-y divide-white/[0.06]">
                  {categoryTreatments.map((treatment) => (
                    <div key={treatment.id} className="p-6 hover:bg-white/[0.04] transition-all">
                      {editingId === treatment.id ? (
                        // Edit Mode
                        <div className="space-y-6 bg-white/[0.03] p-6 rounded-3xl border border-white/[0.06] animate-in fade-in zoom-in-95 duration-300">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div className="space-y-2">
                              <label className="block text-xs font-bold text-white/40 ml-1 uppercase">{t('treatments.service_name_label')}</label>
                              <input
                                type="text"
                                value={editForm.name || ''}
                                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                                className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all font-semibold"
                              />
                            </div>
                            <div className="space-y-2">
                              <label className="block text-xs font-bold text-white/40 ml-1 uppercase">{t('treatments.code_reference')}</label>
                              <input
                                type="text"
                                value={editForm.code || ''}
                                disabled
                                className="w-full px-4 py-3 bg-white/[0.02] border border-white/[0.06] rounded-xl text-white/30 font-mono text-sm cursor-not-allowed"
                              />
                            </div>
                          </div>

                          <div className="space-y-2">
                            <label className="block text-xs font-bold text-white/40 ml-1 uppercase">{t('treatments.clinical_description')}</label>
                            <textarea
                              value={editForm.description || ''}
                              onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                              rows={2}
                              className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all resize-none font-medium"
                            />
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
                            <label className="block text-xs font-bold text-white/40 ml-1 uppercase">{t('treatments.base_price_label') || 'Precio base ($)'}</label>
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
                            <p className="text-[10px] text-white/30 ml-1">Valor del tratamiento. Se usa para calcular el monto a cobrar en los turnos.</p>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                            <div className="space-y-2">
                              <label className="block text-xs font-bold text-white/40 ml-1 uppercase">{t('treatments.complexity_level_label')}</label>
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
                            <div className="space-y-2">
                              <label className="block text-xs font-bold text-white/40 ml-1 uppercase">{t('professionals.priority.label')}</label>
                              <select
                                value={editForm.priority || 'medium'}
                                onChange={(e) => setEditForm({ ...editForm, priority: e.target.value as TreatmentType['priority'] })}
                                className="w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none appearance-none font-bold"
                              >
                                <option value="high">{t('professionals.priority.high')}</option>
                                <option value="medium-high">{t('professionals.priority.mediumHigh')}</option>
                                <option value="medium">{t('professionals.priority.medium')}</option>
                                <option value="low">{t('professionals.priority.low')}</option>
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

                          {/* Assigned Professionals */}
                          {professionals.length > 0 && (
                            <div className="space-y-3">
                              <div>
                                <label className="block text-xs font-bold text-white/40 ml-1 uppercase flex items-center gap-2">
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
                              {treatment.priority && (
                                <span className={`inline-flex items-center px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest border ${
                                  treatment.priority === 'high' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                                  treatment.priority === 'medium-high' ? 'bg-orange-500/10 text-orange-400 border-orange-500/20' :
                                  treatment.priority === 'medium' ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' :
                                  'bg-green-500/10 text-green-400 border-green-500/20'
                                }`}>
                                  {({
                                    high: t('professionals.priority.high'),
                                    'medium-high': t('professionals.priority.mediumHigh'),
                                    medium: t('professionals.priority.medium'),
                                    low: t('professionals.priority.low'),
                                  } as Record<string, string>)[treatment.priority] ?? t('professionals.priority.medium')}
                                </span>
                              )}
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
                              <p className="text-white/40 text-sm leading-relaxed mb-4 max-w-2xl font-medium">{treatment.description}</p>
                            )}

                            <div className="flex flex-wrap items-center gap-y-2 gap-x-8">
                              <div className="flex items-center gap-2.5">
                                <div className="p-1.5 bg-blue-500/10 text-blue-400 rounded-lg">
                                  <Clock size={14} />
                                </div>
                                <span className="text-white/60 text-sm font-semibold">
                                  <strong className="text-white text-base">{treatment.default_duration_minutes}</strong> {t('common.minutes_short')} <span className="text-white/30 font-medium">{t('treatments.min_standard')}</span>
                                </span>
                              </div>
                              <div className="h-4 w-px bg-white/[0.06] hidden sm:block"></div>
                              <div className="flex items-center gap-4 text-xs font-bold text-white/30 uppercase tracking-tight">
                               <span>{t('treatments.min_short')}: <span className="text-white">{treatment.min_duration_minutes}{t('common.min_short')}</span></span>
                                <span>{t('treatments.max_short')}: <span className="text-white">{treatment.max_duration_minutes}{t('common.min_short')}</span></span>
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
                                <Users size={14} className="text-white/30 shrink-0" />
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
    </div>
  );
}
