import { useState, useEffect, useCallback, useRef } from 'react';
import { X, Loader2, Calendar, AlertTriangle, Copy, Check, ChevronRight, ChevronLeft } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

// ── Types ──────────────────────────────────────────────

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
  default_duration_minutes: number;
  base_price?: number;
  professional_ids?: number[];
  is_active: boolean;
  is_available_for_booking: boolean;
}

interface CollisionResult {
  has_collisions: boolean;
  conflicting_appointments: Array<{ id: string; appointment_datetime: string; patient_name?: string; duration_minutes: number }>;
  conflicting_blocks?: Array<{ id: string; title: string }>;
}

interface ScheduleAppointmentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSaved: (appointment: any) => void;
  onPatientCreated?: (patient: { id: number; first_name: string; last_name: string; phone_number: string; status: string }) => void;
  patientId?: number;
  patientPhone: string;
  patientName?: string;
  tenantId: number;
}

const inputCls = "w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white placeholder-white/30 focus:outline-none focus:border-white/20 text-sm";
const readonlyCls = "w-full px-3 py-2 rounded-lg bg-white/[0.02] border border-white/[0.04] text-white/40 cursor-not-allowed text-sm";
const selectCls = "w-full px-3 py-2 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white focus:outline-none focus:border-white/20 text-sm [&>option]:bg-[#0d1117]";
const labelCls = "block text-xs font-medium text-white/50 mb-1";

export default function ScheduleAppointmentModal({
  isOpen, onClose, onSaved, onPatientCreated, patientId, patientPhone, patientName, tenantId,
}: ScheduleAppointmentModalProps) {
  const { t } = useTranslation();

  // Wizard state
  const [step, setStep] = useState<1 | 2>(patientId ? 2 : 1);
  const [createdPatientId, setCreatedPatientId] = useState<number | null>(null);
  const effectivePatientId = patientId || createdPatientId;

  // Step 1: patient form
  const [patientForm, setPatientForm] = useState<PatientFormData>({
    first_name: '', last_name: '', phone_number: '', dni: '', insurance: '', email: '', city: '', notes: '',
  });
  const [insuranceOptions, setInsuranceOptions] = useState<string[]>([]);

  // Step 2: scheduling form
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [treatments, setTreatments] = useState<TreatmentType[]>([]);
  const [selectedProfessionalId, setSelectedProfessionalId] = useState('');
  const [selectedTreatmentCode, setSelectedTreatmentCode] = useState('');
  const [appointmentDate, setAppointmentDate] = useState('');
  const [appointmentTime, setAppointmentTime] = useState('');
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [appointmentNotes, setAppointmentNotes] = useState('');
  const [collision, setCollision] = useState<CollisionResult | null>(null);
  const [checkingCollision, setCheckingCollision] = useState(false);

  // Bank data for seña
  const [bankData, setBankData] = useState<{ bank_cbu?: string; bank_alias?: string; bank_holder_name?: string } | null>(null);
  const [copiedField, setCopiedField] = useState('');

  // Patient context (read-only header in step 2)
  const [patientContext, setPatientContext] = useState<any>(null);

  // Common state
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const collisionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Init on open ──────────────────────────────────────

  useEffect(() => {
    if (!isOpen) return;
    setError('');
    setStep(patientId ? 2 : 1);
    setCreatedPatientId(null);
    setCollision(null);
    setSelectedProfessionalId('');
    setSelectedTreatmentCode('');
    setAppointmentDate('');
    setAppointmentTime('');
    setDurationMinutes(30);
    setAppointmentNotes('');
    setCopiedField('');

    // Init patient form
    const isPhoneName = /^\+?[\d\s()\-]{7,}$/.test(patientName || '');
    setPatientForm({
      first_name: isPhoneName ? '' : (patientName || ''),
      last_name: '', phone_number: patientPhone, dni: '', insurance: '', email: '', city: '', notes: '',
    });
  }, [isOpen, patientId, patientPhone, patientName]);

  // Fetch data on open
  useEffect(() => {
    if (!isOpen) return;
    // Professionals + treatments
    api.get('/admin/professionals').then(r => setProfessionals(r.data || [])).catch(() => {});
    api.get('/admin/treatment-types').then(r => {
      const active = (r.data || []).filter((tt: TreatmentType) => tt.is_active);
      setTreatments(active);
    }).catch(() => {});
    // Insurance
    api.get('/admin/insurance-providers').then(r => setInsuranceOptions(r.data.providers || [])).catch(() => {});
    // Bank data for seña
    api.get('/admin/settings/clinic').then(r => {
      const d = r.data;
      if (d.bank_cbu || d.bank_alias) {
        setBankData({ bank_cbu: d.bank_cbu, bank_alias: d.bank_alias, bank_holder_name: d.bank_holder_name });
      }
    }).catch(() => {});
  }, [isOpen]);

  // Fetch patient context when entering step 2 with patient
  useEffect(() => {
    if (!isOpen || step !== 2 || !effectivePatientId) return;
    api.get(`/admin/patients/phone/${encodeURIComponent(patientPhone)}/context`).then(r => {
      setPatientContext(r.data);
    }).catch(() => {});
  }, [isOpen, step, effectivePatientId, patientPhone]);

  // Lock body scroll
  useEffect(() => {
    if (isOpen) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = '';
    return () => { document.body.style.overflow = ''; };
  }, [isOpen]);

  // ── Treatment change → auto-fill duration + filter professionals ──

  const selectedTreatment = treatments.find(tt => tt.code === selectedTreatmentCode);

  useEffect(() => {
    if (selectedTreatment) {
      setDurationMinutes(selectedTreatment.default_duration_minutes || 30);
      // Auto-select professional if only one assigned
      if (selectedTreatment.professional_ids?.length === 1) {
        setSelectedProfessionalId(String(selectedTreatment.professional_ids[0]));
      }
    }
  }, [selectedTreatmentCode]);

  // Filtered professionals: if treatment has assigned professionals, filter; otherwise show all
  const filteredProfessionals = selectedTreatment?.professional_ids?.length
    ? professionals.filter(p => selectedTreatment.professional_ids!.includes(p.id))
    : professionals;

  // ── Collision check (debounced) ──

  const checkCollisions = useCallback(async () => {
    if (!selectedProfessionalId || !appointmentDate || !appointmentTime || !durationMinutes) {
      setCollision(null);
      return;
    }
    setCheckingCollision(true);
    try {
      const datetimeStr = `${appointmentDate}T${appointmentTime}:00`;
      const res = await api.get('/admin/appointments/check-collisions', {
        params: { professional_id: selectedProfessionalId, datetime_str: datetimeStr, duration_minutes: durationMinutes },
      });
      setCollision(res.data);
    } catch {
      setCollision(null);
    } finally {
      setCheckingCollision(false);
    }
  }, [selectedProfessionalId, appointmentDate, appointmentTime, durationMinutes]);

  useEffect(() => {
    if (collisionTimer.current) clearTimeout(collisionTimer.current);
    collisionTimer.current = setTimeout(checkCollisions, 500);
    return () => { if (collisionTimer.current) clearTimeout(collisionTimer.current); };
  }, [checkCollisions]);

  // ── Step 1: Create Patient ──

  const handleStep1Submit = async () => {
    if (!patientForm.first_name.trim()) return;
    setSaving(true);
    setError('');
    try {
      const res = await api.post('/admin/patients', {
        first_name: patientForm.first_name.trim(),
        last_name: patientForm.last_name.trim(),
        phone_number: patientForm.phone_number,
        email: patientForm.email.trim() || null,
        dni: patientForm.dni.trim() || null,
        insurance: patientForm.insurance.trim() || null,
        city: patientForm.city.trim() || null,
        notes: patientForm.notes.trim() || null,
      });
      setCreatedPatientId(res.data.id);
      onPatientCreated?.(res.data);
      setStep(2);
    } catch (err: any) {
      if (err.response?.status === 409) {
        // Patient already exists — try to get their ID and skip to step 2
        try {
          const ctx = await api.get(`/admin/patients/phone/${encodeURIComponent(patientPhone)}/context`);
          const pid = ctx.data?.patient?.id || ctx.data?.patient_id;
          if (pid) {
            setCreatedPatientId(pid);
            setStep(2);
            return;
          }
        } catch {}
        setError(t('create_patient_modal.error_duplicate_phone'));
      } else {
        setError(err.response?.data?.detail || t('create_patient_modal.error_generic'));
      }
    } finally {
      setSaving(false);
    }
  };

  // ── Step 2: Create Appointment ──

  const handleScheduleSubmit = async () => {
    if (!effectivePatientId || !selectedProfessionalId || !appointmentDate || !appointmentTime) return;
    setSaving(true);
    setError('');
    try {
      const datetimeStr = `${appointmentDate}T${appointmentTime}:00`;
      const res = await api.post('/admin/appointments', {
        patient_id: effectivePatientId,
        professional_id: parseInt(selectedProfessionalId),
        appointment_datetime: datetimeStr,
        duration_minutes: durationMinutes,
        appointment_type: selectedTreatmentCode || 'checkup',
        notes: appointmentNotes.trim() || null,
        check_collisions: true,
      });
      onSaved(res.data);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || t('schedule_modal.error_generic'));
    } finally {
      setSaving(false);
    }
  };

  // ── Copy helper ──

  const copyToClipboard = (text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(''), 2000);
  };

  // ── Seña calculation ──

  const senaAmount = selectedTreatment?.base_price ? (selectedTreatment.base_price * 0.5) : null;

  if (!isOpen) return null;

  const needsStep1 = !patientId && !createdPatientId;
  const showStepIndicator = !patientId; // Only show steps if we started without a patient

  // Min date: today
  const today = new Date().toISOString().split('T')[0];

  return (
    <div
      className="fixed inset-0 z-[100] flex items-end lg:items-center justify-center lg:p-4 bg-black/60 backdrop-blur-sm"
      onClick={e => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="relative w-full lg:max-w-2xl bg-[#0d1117] border-t lg:border border-white/[0.06] rounded-t-2xl lg:rounded-2xl shadow-2xl flex flex-col max-h-[92vh] lg:max-h-[85vh]">

        {/* Header */}
        <div className="flex justify-between items-center px-5 py-4 border-b border-white/[0.06] shrink-0">
          <div className="flex items-center gap-2">
            <Calendar size={18} className="text-white/50" />
            <h2 className="text-lg font-bold text-white">{t('schedule_modal.title')}</h2>
          </div>
          <button onClick={onClose} className="p-2 text-white/40 hover:text-white hover:bg-white/[0.06] rounded-lg transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Step Indicator */}
        {showStepIndicator && (
          <div className="flex items-center gap-3 px-5 py-3 border-b border-white/[0.04]">
            <div className="flex items-center gap-2">
              <span className={`w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center ${step === 1 ? 'bg-white text-[#0a0e1a]' : 'bg-white/[0.1] text-white/40'}`}>1</span>
              <span className={`text-sm ${step === 1 ? 'text-white font-medium' : 'text-white/40'}`}>{t('schedule_modal.step1_title')}</span>
            </div>
            <div className="flex-1 h-px bg-white/[0.1]" />
            <div className="flex items-center gap-2">
              <span className={`w-6 h-6 rounded-full text-xs font-bold flex items-center justify-center ${step === 2 ? 'bg-white text-[#0a0e1a]' : 'bg-white/[0.1] text-white/40'}`}>2</span>
              <span className={`text-sm ${step === 2 ? 'text-white font-medium' : 'text-white/40'}`}>{t('schedule_modal.step2_title')}</span>
            </div>
          </div>
        )}

        {/* Content */}
        <div className="px-5 py-4 overflow-y-auto overscroll-contain space-y-4" style={{ paddingBottom: 'max(1rem, env(safe-area-inset-bottom))' }}>

          {/* ═══ STEP 1: Patient Data ═══ */}
          {step === 1 && needsStep1 && (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>{t('create_patient_modal.field_first_name')} *</label>
                  <input type="text" value={patientForm.first_name} onChange={e => setPatientForm(p => ({ ...p, first_name: e.target.value }))} placeholder="Ej: Laura" className={inputCls} autoFocus />
                </div>
                <div>
                  <label className={labelCls}>{t('create_patient_modal.field_last_name')}</label>
                  <input type="text" value={patientForm.last_name} onChange={e => setPatientForm(p => ({ ...p, last_name: e.target.value }))} placeholder="Ej: García" className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>{t('create_patient_modal.field_phone')}</label>
                  <input type="text" value={patientForm.phone_number} readOnly className={readonlyCls} />
                </div>
                <div>
                  <label className={labelCls}>{t('create_patient_modal.field_dni')}</label>
                  <input type="text" value={patientForm.dni} onChange={e => setPatientForm(p => ({ ...p, dni: e.target.value }))} placeholder="12345678" className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>{t('create_patient_modal.field_insurance')}</label>
                  <input type="text" list="schedule-insurance-options" value={patientForm.insurance} onChange={e => setPatientForm(p => ({ ...p, insurance: e.target.value }))} placeholder={t('create_patient_modal.no_insurance')} className={inputCls} />
                  <datalist id="schedule-insurance-options">
                    {insuranceOptions.map(p => <option key={p} value={p} />)}
                  </datalist>
                </div>
                <div>
                  <label className={labelCls}>{t('create_patient_modal.field_email')}</label>
                  <input type="email" value={patientForm.email} onChange={e => setPatientForm(p => ({ ...p, email: e.target.value }))} placeholder="email@ejemplo.com" className={inputCls} />
                </div>
              </div>
            </>
          )}

          {/* ═══ STEP 2: Schedule Appointment ═══ */}
          {step === 2 && (
            <>
              {/* Patient context header (read-only) */}
              {patientContext?.patient && (
                <div className="p-3 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-white">
                        {[patientContext.patient.first_name, patientContext.patient.last_name].filter(Boolean).join(' ')}
                      </p>
                      <p className="text-xs text-white/40">{patientPhone}</p>
                    </div>
                    {patientContext.patient.insurance_provider && (
                      <span className="px-2 py-0.5 rounded-full text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/20">
                        {patientContext.patient.insurance_provider}
                      </span>
                    )}
                  </div>
                  {/* Last appointments */}
                  {patientContext.last_appointment && (
                    <p className="text-xs text-white/30 mt-2">
                      {t('schedule_modal.last_visit')}: {new Date(patientContext.last_appointment.date).toLocaleDateString('es-AR')} — {patientContext.last_appointment.type}
                    </p>
                  )}
                </div>
              )}

              {/* Treatment type */}
              <div>
                <label className={labelCls}>{t('schedule_modal.field_treatment')}</label>
                <select
                  value={selectedTreatmentCode}
                  onChange={e => setSelectedTreatmentCode(e.target.value)}
                  className={selectCls}
                >
                  <option value="">{t('schedule_modal.select_treatment')}</option>
                  {treatments.map(tt => (
                    <option key={tt.code} value={tt.code}>{tt.name} ({tt.default_duration_minutes} min)</option>
                  ))}
                </select>
              </div>

              {/* Professional */}
              <div>
                <label className={labelCls}>{t('schedule_modal.field_professional')}</label>
                <select
                  value={selectedProfessionalId}
                  onChange={e => setSelectedProfessionalId(e.target.value)}
                  className={selectCls}
                >
                  <option value="">{t('schedule_modal.select_professional')}</option>
                  {filteredProfessionals.map(p => (
                    <option key={p.id} value={p.id}>
                      {[p.first_name, p.last_name].filter(Boolean).join(' ')}{p.specialty ? ` — ${p.specialty}` : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Date + Time */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>{t('schedule_modal.field_date')}</label>
                  <input type="date" value={appointmentDate} onChange={e => setAppointmentDate(e.target.value)} min={today} className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>{t('schedule_modal.field_time')}</label>
                  <input type="time" value={appointmentTime} onChange={e => setAppointmentTime(e.target.value)} className={inputCls} />
                </div>
              </div>

              {/* Duration */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className={labelCls}>{t('schedule_modal.field_duration')}</label>
                  <input type="number" value={durationMinutes} onChange={e => setDurationMinutes(parseInt(e.target.value) || 30)} min={15} step={15} className={inputCls} />
                </div>
              </div>

              {/* Notes */}
              <div>
                <label className={labelCls}>{t('schedule_modal.field_notes')}</label>
                <textarea value={appointmentNotes} onChange={e => setAppointmentNotes(e.target.value)} rows={2} className={inputCls + ' resize-none'} placeholder={t('schedule_modal.notes_placeholder')} />
              </div>

              {/* Collision warning */}
              {collision?.has_collisions && (
                <div className="flex items-center gap-2 px-4 py-3 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm">
                  <AlertTriangle size={16} className="shrink-0" />
                  <span>{t('schedule_modal.collision_warning')}</span>
                </div>
              )}

              {/* Seña info */}
              {senaAmount && senaAmount > 0 && bankData && (
                <div className="p-4 rounded-xl bg-white/[0.02] border border-white/[0.04]">
                  <p className="text-xs text-white/50 mb-1">{t('schedule_modal.sena_info_title')}</p>
                  <p className="text-2xl font-bold text-white">${senaAmount.toLocaleString('es-AR')}</p>
                  <div className="mt-3 space-y-2 text-sm">
                    {bankData.bank_cbu && (
                      <div className="flex items-center justify-between text-white/70">
                        <span>CBU:</span>
                        <button onClick={() => copyToClipboard(bankData.bank_cbu!, 'cbu')} className="flex items-center gap-1 font-mono text-xs hover:text-white transition-colors">
                          {bankData.bank_cbu}
                          {copiedField === 'cbu' ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        </button>
                      </div>
                    )}
                    {bankData.bank_alias && (
                      <div className="flex items-center justify-between text-white/70">
                        <span>Alias:</span>
                        <button onClick={() => copyToClipboard(bankData.bank_alias!, 'alias')} className="flex items-center gap-1 font-mono text-xs hover:text-white transition-colors">
                          {bankData.bank_alias}
                          {copiedField === 'alias' ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        </button>
                      </div>
                    )}
                    {bankData.bank_holder_name && (
                      <div className="flex items-center justify-between text-white/70">
                        <span>{t('schedule_modal.holder')}:</span>
                        <span className="text-xs">{bankData.bank_holder_name}</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {/* Error */}
          {error && (
            <div className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center px-5 py-4 border-t border-white/[0.06] shrink-0">
          <div>
            {step === 2 && showStepIndicator && (
              <button
                onClick={() => setStep(1)}
                className="px-3 py-2 rounded-lg bg-white/[0.04] text-white/70 hover:bg-white/[0.08] text-sm transition-colors flex items-center gap-1"
              >
                <ChevronLeft size={14} /> {t('schedule_modal.back')}
              </button>
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-white/[0.04] text-white/70 hover:bg-white/[0.08] text-sm transition-colors"
            >
              {t('common.cancel')}
            </button>

            {step === 1 && needsStep1 ? (
              <button
                onClick={handleStep1Submit}
                disabled={saving || !patientForm.first_name.trim()}
                className="px-4 py-2 rounded-lg bg-white text-[#0a0e1a] font-medium text-sm hover:bg-white/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {saving && <Loader2 size={14} className="animate-spin" />}
                {t('schedule_modal.next')} <ChevronRight size={14} />
              </button>
            ) : (
              <button
                onClick={handleScheduleSubmit}
                disabled={saving || !effectivePatientId || !selectedProfessionalId || !appointmentDate || !appointmentTime}
                className="px-4 py-2 rounded-lg bg-white text-[#0a0e1a] font-medium text-sm hover:bg-white/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {saving && <Loader2 size={14} className="animate-spin" />}
                {saving ? t('schedule_modal.saving_button') : t('schedule_modal.save_button')}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
