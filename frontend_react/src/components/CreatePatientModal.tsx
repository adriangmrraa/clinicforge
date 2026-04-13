import { useState, useEffect } from 'react';
import { X, Loader2, User } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

interface PatientFormData {
  first_name: string;
  last_name: string;
  phone_number: string;
  dni: string;
  insurance: string;
  email: string;
  city: string;
  notes: string;
}

interface CreatePatientModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved: (patient: { id: number; first_name: string; last_name: string; phone_number: string; status: string }) => void;
  initialPhone: string;
  initialName?: string;
  editPatientId?: number;
  editPatientData?: Partial<PatientFormData>;
  tenantId: number;
}

const inputCls = "w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white placeholder-white/30 focus:outline-none focus:border-white/20 text-sm";
const readonlyCls = "w-full px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.04] text-white/40 cursor-not-allowed text-sm";
const labelCls = "block text-xs font-medium text-white/50 mb-1";

export default function CreatePatientModal({
  isOpen, onClose, onSaved, initialPhone, initialName, editPatientId, editPatientData, tenantId,
}: CreatePatientModalProps) {
  const { t } = useTranslation();
  const isEdit = !!editPatientId;

  const [form, setForm] = useState<PatientFormData>({
    first_name: '',
    last_name: '',
    phone_number: '',
    dni: '',
    insurance: '',
    email: '',
    city: '',
    notes: '',
  });
  const [insuranceOptions, setInsuranceOptions] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  // Initialize form on open
  useEffect(() => {
    if (!isOpen) return;
    setError('');
    if (isEdit && editPatientData) {
      setForm({
        first_name: editPatientData.first_name || '',
        last_name: editPatientData.last_name || '',
        phone_number: initialPhone,
        dni: editPatientData.dni || '',
        insurance: editPatientData.insurance || '',
        email: editPatientData.email || '',
        city: editPatientData.city || '',
        notes: editPatientData.notes || '',
      });
    } else {
      const isPhoneName = /^\+?[\d\s()\-]{7,}$/.test(initialName || '');
      setForm({
        first_name: isPhoneName ? '' : (initialName || ''),
        last_name: '',
        phone_number: initialPhone,
        dni: '',
        insurance: '',
        email: '',
        city: '',
        notes: '',
      });
    }
  }, [isOpen, isEdit, editPatientData, initialPhone, initialName]);

  // Fetch insurance providers
  useEffect(() => {
    if (!isOpen) return;
    api.get('/admin/insurance-providers/used').then(r => {
      setInsuranceOptions(r.data.providers || []);
    }).catch(() => {});
  }, [isOpen]);

  // Lock body scroll
  useEffect(() => {
    if (isOpen) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = '';
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  const handleChange = (field: keyof PatientFormData, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }));
    if (error) setError('');
  };

  const handleSubmit = async () => {
    if (!form.first_name.trim()) return;
    setSaving(true);
    setError('');
    try {
      const body = {
        first_name: form.first_name.trim(),
        last_name: form.last_name.trim(),
        phone_number: form.phone_number,
        email: form.email.trim() || null,
        dni: form.dni.trim() || null,
        insurance: form.insurance.trim() || null,
        city: form.city.trim() || null,
        notes: form.notes.trim() || null,
      };
      let res;
      if (isEdit) {
        res = await api.put(`/admin/patients/${editPatientId}`, body);
      } else {
        res = await api.post('/admin/patients', body);
      }
      onSaved(res.data);
      onClose();
    } catch (err: any) {
      if (err.response?.status === 409) {
        setError(t('create_patient_modal.error_duplicate_phone'));
      } else {
        setError(err.response?.data?.detail || t('create_patient_modal.error_generic'));
      }
    } finally {
      setSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end lg:items-center justify-center lg:p-4 bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-full lg:max-w-lg bg-[#0d1117] border-t lg:border border-white/[0.06] rounded-t-2xl lg:rounded-2xl shadow-2xl flex flex-col max-h-[92vh] lg:max-h-[85vh]">
        {/* Header */}
        <div className="flex justify-between items-center px-5 py-4 border-b border-white/[0.06] shrink-0">
          <div className="flex items-center gap-2">
            <User size={18} className="text-white/50" />
            <h2 className="text-lg font-bold text-white">
              {isEdit ? t('create_patient_modal.title_edit') : t('create_patient_modal.title_create')}
            </h2>
          </div>
          <button onClick={onClose} className="p-2 text-white/40 hover:text-white hover:bg-white/[0.06] rounded-lg transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Form */}
        <div className="px-5 py-4 overflow-y-auto overscroll-contain space-y-4" style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}>
          <div className="grid grid-cols-2 gap-4">
            {/* Nombre */}
            <div>
              <label className={labelCls}>{t('create_patient_modal.field_first_name')} *</label>
              <input
                type="text"
                value={form.first_name}
                onChange={e => handleChange('first_name', e.target.value)}
                placeholder="Ej: Laura"
                className={inputCls}
                autoFocus
              />
            </div>
            {/* Apellido */}
            <div>
              <label className={labelCls}>{t('create_patient_modal.field_last_name')}</label>
              <input
                type="text"
                value={form.last_name}
                onChange={e => handleChange('last_name', e.target.value)}
                placeholder="Ej: García"
                className={inputCls}
              />
            </div>
            {/* Teléfono (read-only) */}
            <div>
              <label className={labelCls}>{t('create_patient_modal.field_phone')}</label>
              <input type="text" value={form.phone_number} readOnly className={readonlyCls} />
            </div>
            {/* DNI */}
            <div>
              <label className={labelCls}>{t('create_patient_modal.field_dni')}</label>
              <input
                type="text"
                value={form.dni}
                onChange={e => handleChange('dni', e.target.value)}
                placeholder="12345678"
                className={inputCls}
              />
            </div>
            {/* Obra Social */}
            <div>
              <label className={labelCls}>{t('create_patient_modal.field_insurance')}</label>
              <input
                type="text"
                list="insurance-options"
                value={form.insurance}
                onChange={e => handleChange('insurance', e.target.value)}
                placeholder={t('create_patient_modal.no_insurance')}
                className={inputCls}
              />
              <datalist id="insurance-options">
                {insuranceOptions.map(p => <option key={p} value={p} />)}
              </datalist>
            </div>
            {/* Email */}
            <div>
              <label className={labelCls}>{t('create_patient_modal.field_email')}</label>
              <input
                type="email"
                value={form.email}
                onChange={e => handleChange('email', e.target.value)}
                placeholder="email@ejemplo.com"
                className={inputCls}
              />
            </div>
            {/* Ciudad */}
            <div>
              <label className={labelCls}>{t('create_patient_modal.field_city')}</label>
              <input
                type="text"
                value={form.city}
                onChange={e => handleChange('city', e.target.value)}
                placeholder="Ej: Resistencia"
                className={inputCls}
              />
            </div>
          </div>
          {/* Notas (full width) */}
          <div>
            <label className={labelCls}>{t('create_patient_modal.field_notes')}</label>
            <textarea
              value={form.notes}
              onChange={e => handleChange('notes', e.target.value)}
              placeholder={t('create_patient_modal.notes_placeholder')}
              rows={2}
              className={inputCls + ' resize-none'}
            />
          </div>

          {/* Error */}
          {error && (
            <div className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-5 py-4 border-t border-white/[0.06] shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg bg-white/[0.04] text-white/70 hover:bg-white/[0.08] text-sm transition-colors"
          >
            {t('common.cancel')}
          </button>
          <button
            onClick={handleSubmit}
            disabled={saving || !form.first_name.trim()}
            className="px-4 py-2 rounded-lg bg-white text-[#0a0e1a] font-medium text-sm hover:bg-white/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {saving && <Loader2 size={14} className="animate-spin" />}
            {saving
              ? t('create_patient_modal.saving_button')
              : isEdit
                ? t('create_patient_modal.save_edit_button')
                : t('create_patient_modal.save_button')
            }
          </button>
        </div>
      </div>
    </div>
  );
}
