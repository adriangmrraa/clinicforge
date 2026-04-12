import React, { useState, useEffect, useCallback } from 'react';
import { X, Plus, Loader2, Save, Zap, Users, Shield, Clock } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import api from '../../api/axios';
import StepEditor, { StepData } from './StepEditor';
import StepTimeline from './StepTimeline';

interface PlaybookConfigModalProps {
  playbookId: number | null;
  onClose: () => void;
  onSaved: () => void;
}

const TRIGGER_OPTIONS = [
  { value: 'appointment_reminder', label: 'Recordatorio de turno (antes del turno)', icon: '📋' },
  { value: 'appointment_completed', label: 'Turno completado', icon: '✅' },
  { value: 'no_show', label: 'Paciente no asistió (no-show)', icon: '❌' },
  { value: 'appointment_created', label: 'Turno creado', icon: '📅' },
  { value: 'lead_no_booking', label: 'Lead sin turno agendado', icon: '🎯' },
  { value: 'patient_inactive', label: 'Paciente inactivo (X días)', icon: '💤' },
  { value: 'payment_pending', label: 'Pago pendiente', icon: '💰' },
];

const CATEGORY_OPTIONS = [
  { value: 'retention', label: 'Retención' },
  { value: 'revenue', label: 'Ingresos' },
  { value: 'reputation', label: 'Reputación' },
  { value: 'clinical', label: 'Clínico' },
  { value: 'recovery', label: 'Recuperación' },
  { value: 'custom', label: 'Personalizado' },
];

/** Safely parse a value that might be string JSON, dict, or null into a dict */
function safeDict(v: any): Record<string, any> {
  if (!v) return {};
  if (typeof v === 'object' && !Array.isArray(v)) return v;
  if (typeof v === 'string') {
    try { const p = JSON.parse(v); return typeof p === 'object' && !Array.isArray(p) ? p : {}; }
    catch { return {}; }
  }
  return {};
}

/** Safely parse array (might be string JSON) */
function safeArray(v: any): any[] {
  if (!v) return [];
  if (Array.isArray(v)) return v;
  if (typeof v === 'string') {
    try { const p = JSON.parse(v); return Array.isArray(p) ? p : []; }
    catch { return []; }
  }
  return [];
}

/** Clean step data for POST (remove DB-only fields) */
function cleanStepForPost(s: StepData, idx: number): Record<string, any> {
  return {
    step_order: idx,
    step_label: s.step_label || null,
    action_type: s.action_type || 'send_text',
    delay_minutes: Number(s.delay_minutes) || 0,
    schedule_hour_min: s.schedule_hour_min ?? null,
    schedule_hour_max: s.schedule_hour_max ?? null,
    template_name: s.template_name || null,
    template_lang: s.template_lang || 'es',
    template_vars: safeDict(s.template_vars),
    message_text: s.message_text || null,
    instruction_source: s.instruction_source || 'from_treatment',
    custom_instructions: s.custom_instructions || null,
    notify_channel: s.notify_channel || 'telegram',
    notify_message: s.notify_message || null,
    update_field: s.update_field || null,
    update_value: s.update_value || null,
    wait_timeout_minutes: Number(s.wait_timeout_minutes) || 120,
    response_rules: safeArray(s.response_rules),
    on_no_response: s.on_no_response || 'continue',
    on_unclassified: s.on_unclassified || 'pass_to_ai',
    on_response_next_step: s.on_response_next_step ?? null,
    on_no_response_next_step: s.on_no_response_next_step ?? null,
  };
}

export default function PlaybookConfigModal({ playbookId, onClose, onSaved }: PlaybookConfigModalProps) {
  const { t } = useTranslation();
  const isEdit = playbookId !== null;

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [icon, setIcon] = useState('📋');
  const [category, setCategory] = useState('custom');
  const [triggerType, setTriggerType] = useState('appointment_completed');
  const [triggerConfig, setTriggerConfig] = useState<Record<string, any>>({});
  const [conditions, setConditions] = useState<Record<string, any>>({});
  const [maxMsgsPerDay, setMaxMsgsPerDay] = useState(2);
  const [scheduleMin, setScheduleMin] = useState(9);
  const [scheduleMax, setScheduleMax] = useState(20);
  const [abortOnBooking, setAbortOnBooking] = useState(true);
  const [abortOnHuman, setAbortOnHuman] = useState(true);
  const [abortOnOptout, setAbortOnOptout] = useState(true);

  const [steps, setSteps] = useState<StepData[]>([]);
  const [activeStep, setActiveStep] = useState(0);

  const [templates, setTemplates] = useState<any[]>([]);
  const [treatments, setTreatments] = useState<any[]>([]);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const [tplRes, ttRes] = await Promise.all([
          api.get('/admin/automations/ycloud-templates').catch(() => ({ data: { templates: [] } })),
          api.get('/admin/treatment-types').catch(() => ({ data: [] })),
        ]);
        setTemplates(tplRes.data.templates || []);
        const ttData = ttRes.data;
        setTreatments(Array.isArray(ttData) ? ttData : ttData?.treatments || ttData?.data || []);

        if (isEdit) {
          const { data } = await api.get(`/admin/playbooks/${playbookId}`);
          setName(data.name || '');
          setDescription(data.description || '');
          setIcon(data.icon || '📋');
          setCategory(data.category || 'custom');
          setTriggerType(data.trigger_type || 'appointment_completed');
          setTriggerConfig(safeDict(data.trigger_config));
          setConditions(safeDict(data.conditions));
          setMaxMsgsPerDay(data.max_messages_per_day ?? 2);
          setScheduleMin(data.schedule_hour_min ?? 9);
          setScheduleMax(data.schedule_hour_max ?? 20);
          setAbortOnBooking(data.abort_on_booking ?? true);
          setAbortOnHuman(data.abort_on_human ?? true);
          setAbortOnOptout(data.abort_on_optout ?? true);
          setSteps((data.steps || []).map((s: any, i: number) => ({
            ...s,
            step_order: i,
            template_vars: safeDict(s.template_vars),
            response_rules: safeArray(s.response_rules),
          })));
        }
      } catch (e) {
        console.error('Error loading playbook data:', e);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, [playbookId, isEdit]);

  const handleSave = async () => {
    if (!name.trim()) { setError(t('playbooks.error_name_required')); return; }
    setSaving(true);
    setError('');
    try {
      const playbookPayload = {
        name, description, icon, category,
        trigger_type: triggerType,
        trigger_config: triggerConfig,
        conditions,
        max_messages_per_day: maxMsgsPerDay,
        schedule_hour_min: scheduleMin,
        schedule_hour_max: scheduleMax,
        abort_on_booking: abortOnBooking,
        abort_on_human: abortOnHuman,
        abort_on_optout: abortOnOptout,
      };

      if (isEdit) {
        await api.patch(`/admin/playbooks/${playbookId}`, playbookPayload);
        // Sync steps: delete all existing, then recreate
        const existing = await api.get(`/admin/playbooks/${playbookId}/steps`);
        for (const s of (existing.data.steps || [])) {
          await api.delete(`/admin/playbooks/${playbookId}/steps/${s.id}`);
        }
        for (let i = 0; i < steps.length; i++) {
          await api.post(`/admin/playbooks/${playbookId}/steps`, cleanStepForPost(steps[i], i));
        }
      } else {
        // Create with steps in one call
        await api.post('/admin/playbooks', {
          ...playbookPayload,
          steps: steps.map((s, i) => cleanStepForPost(s, i)),
        });
      }
      onSaved();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      const errorMsg = typeof detail === 'string' ? detail
        : Array.isArray(detail) ? detail.map((d: any) => typeof d === 'string' ? d : d?.msg || JSON.stringify(d)).join(', ')
        : detail && typeof detail === 'object' ? JSON.stringify(detail)
        : t('playbooks.error_saving');
      setError(String(errorMsg));
    } finally {
      setSaving(false);
    }
  };

  const addStep = () => {
    setSteps(prev => [...prev, {
      step_order: prev.length,
      action_type: 'send_text',
      delay_minutes: prev.length === 0 ? 0 : 120,
    }]);
    setActiveStep(steps.length);
  };

  const updateStep = (idx: number, updated: StepData) => {
    setSteps(prev => prev.map((s, i) => i === idx ? updated : s));
  };

  const deleteStep = (idx: number) => {
    setSteps(prev => prev.filter((_, i) => i !== idx).map((s, i) => ({ ...s, step_order: i })));
  };

  const moveStep = (idx: number, dir: -1 | 1) => {
    const newSteps = [...steps];
    const target = idx + dir;
    if (target < 0 || target >= newSteps.length) return;
    [newSteps[idx], newSteps[target]] = [newSteps[target], newSteps[idx]];
    setSteps(newSteps.map((s, i) => ({ ...s, step_order: i })));
    setActiveStep(target);
  };

  const selectedTreatments = safeArray(conditions.treatments) as string[];
  const toggleTreatment = (code: string) => {
    const current = [...selectedTreatments];
    const idx = current.indexOf(code);
    if (idx >= 0) current.splice(idx, 1);
    else current.push(code);
    setConditions({ ...conditions, treatments: current });
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center">
        <div className="bg-[#0d1117] rounded-2xl p-8">
          <Loader2 className="w-8 h-8 animate-spin text-blue-400 mx-auto" />
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="bg-[#0d1117] rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto border border-white/[0.08]">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-[#0d1117] px-6 py-4 border-b border-white/[0.06] flex justify-between items-center">
          <h2 className="text-lg font-bold text-white">
            {isEdit ? t('playbooks.edit_playbook') : t('playbooks.create_playbook')}
          </h2>
          <button onClick={onClose} className="p-2 text-white/30 hover:text-white/60"><X size={20} /></button>
        </div>

        <div className="px-6 py-5 space-y-6">
          {/* Section 1: Identity */}
          <section>
            <h3 className="text-sm font-bold text-white/60 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Zap size={14} /> {t('playbooks.section_identity')}
            </h3>
            <p className="text-[11px] text-white/25 mb-3 leading-relaxed">
              Dale un nombre claro que describa el objetivo de esta estrategia. La categoría te ayuda a organizarlas visualmente en la galería.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-white/40">{t('playbooks.name')}</label>
                <input value={name} onChange={e => setName(e.target.value)}
                  placeholder="Escudo Anti-Ausencias"
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none" />
              </div>
              <div>
                <label className="text-xs text-white/40">{t('playbooks.category')}</label>
                <select value={category} onChange={e => setCategory(e.target.value)}
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none">
                  {CATEGORY_OPTIONS.map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                </select>
              </div>
            </div>
            <div className="mt-3">
              <label className="text-xs text-white/40">{t('playbooks.description')}</label>
              <textarea value={description} onChange={e => setDescription(e.target.value)}
                placeholder="Le recuerda al paciente su turno y le pide que confirme"
                rows={2}
                className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none resize-none" />
            </div>
          </section>

          {/* Section 2: Trigger */}
          <section>
            <h3 className="text-sm font-bold text-white/60 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Clock size={14} /> {t('playbooks.section_trigger')}
            </h3>
            <p className="text-[11px] text-white/25 mb-3 leading-relaxed">
              Elegí qué evento dispara esta secuencia. Por ejemplo, "Turno completado" se activa cuando la doctora marca un turno como atendido.
            </p>
            <select value={triggerType} onChange={e => setTriggerType(e.target.value)}
              className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none">
              {TRIGGER_OPTIONS.map(opt => <option key={opt.value} value={opt.value}>{opt.icon} {opt.label}</option>)}
            </select>
          </section>

          {/* Section 3: Conditions */}
          <section>
            <h3 className="text-sm font-bold text-white/60 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Users size={14} /> {t('playbooks.section_conditions')}
            </h3>
            <p className="text-[11px] text-white/25 mb-3 leading-relaxed">
              Filtrá para qué tratamientos aplica esta estrategia. Si no seleccionás ninguno, se aplica a todos.
            </p>
            <div>
              <label className="text-xs text-white/40 mb-2 block">{t('playbooks.filter_treatments')}</label>
              <div className="flex flex-wrap gap-1.5">
                {treatments.map((tt: any) => {
                  const code = tt.code || tt.id;
                  const selected = selectedTreatments.includes(code);
                  return (
                    <button key={code} type="button" onClick={() => toggleTreatment(code)}
                      className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors border
                        ${selected
                          ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                          : 'bg-white/[0.04] text-white/40 border-white/[0.08] hover:bg-white/[0.08]'
                        }`}>
                      {tt.name || code}
                    </button>
                  );
                })}
              </div>
              {selectedTreatments.length === 0 && (
                <p className="text-xs text-white/30 mt-1">{t('playbooks.all_treatments')}</p>
              )}
            </div>
          </section>

          {/* Section 4: Steps */}
          <section>
            <h3 className="text-sm font-bold text-white/60 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Zap size={14} /> {t('playbooks.section_steps')} ({steps.length})
            </h3>
            <p className="text-[11px] text-white/25 mb-2 leading-relaxed">
              Armá la secuencia paso a paso. Cada paso se ejecuta después del anterior con el delay que configures. Usá ⬆️⬇️ para reordenar.
            </p>
            <div className="p-2.5 bg-blue-500/[0.08] border border-blue-500/[0.15] rounded-lg mb-3">
              <p className="text-[11px] text-blue-400/80 leading-relaxed">
                <b>📋 Regla de WhatsApp:</b> Para iniciar una conversación o reabrir después de 24h sin respuesta, es obligatorio usar una <b>Plantilla HSM</b> aprobada. Los mensajes de texto libre solo funcionan dentro de la ventana de 24h. Los mensajes al equipo por Telegram no tienen esta restricción.
              </p>
            </div>

            {steps.length > 0 && (
              <div className="mb-4 p-3 bg-white/[0.02] rounded-xl border border-white/[0.04]">
                <StepTimeline steps={steps} activeStepOrder={activeStep} onStepClick={setActiveStep} />
              </div>
            )}

            <div className="space-y-2">
              {steps.map((step, idx) => (
                <StepEditor
                  key={`step-${idx}-${step.action_type}`}
                  step={step}
                  stepIndex={idx}
                  totalSteps={steps.length}
                  templates={templates}
                  accumulatedDelayMinutes={steps.slice(0, idx + 1).reduce((sum, s) => sum + (Number(s.delay_minutes) || 0), 0)}
                  triggerType={triggerType}
                  onChange={(updated) => updateStep(idx, updated)}
                  onDelete={() => deleteStep(idx)}
                  onMoveUp={() => moveStep(idx, -1)}
                  onMoveDown={() => moveStep(idx, 1)}
                />
              ))}
            </div>

            <button type="button" onClick={addStep}
              className="w-full mt-3 py-2.5 border-2 border-dashed border-white/10 hover:border-blue-500/30 rounded-xl text-sm text-white/40 hover:text-blue-400 transition-colors flex items-center justify-center gap-2">
              <Plus size={16} /> {t('playbooks.add_step')}
            </button>
          </section>

          {/* Section 5: Safety */}
          <section>
            <h3 className="text-sm font-bold text-white/60 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Shield size={14} /> {t('playbooks.section_safety')}
            </h3>
            <p className="text-[11px] text-white/25 mb-3 leading-relaxed">
              Controlá cuántos mensajes por día puede recibir un paciente y en qué horarios. La secuencia se detiene automáticamente si el paciente agenda, si un humano toma el chat, o si pide que no le escriban más.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="text-xs text-white/40">{t('playbooks.max_msgs_day')}</label>
                <select value={maxMsgsPerDay} onChange={e => setMaxMsgsPerDay(Number(e.target.value))}
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none">
                  <option value={1}>1 por día</option>
                  <option value={2}>2 por día</option>
                  <option value={3}>3 por día</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-white/40">{t('playbooks.schedule_from')}</label>
                <select value={scheduleMin} onChange={e => setScheduleMin(Number(e.target.value))}
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none">
                  {Array.from({ length: 16 }, (_, i) => i + 6).map(h => (
                    <option key={h} value={h}>{h}:00</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-xs text-white/40">{t('playbooks.schedule_to')}</label>
                <select value={scheduleMax} onChange={e => setScheduleMax(Number(e.target.value))}
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none">
                  {Array.from({ length: 16 }, (_, i) => i + 6).map(h => (
                    <option key={h} value={h}>{h}:00</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex flex-wrap gap-4 mt-3">
              {[
                { key: 'booking', label: t('playbooks.abort_booking'), value: abortOnBooking, set: setAbortOnBooking },
                { key: 'human', label: t('playbooks.abort_human'), value: abortOnHuman, set: setAbortOnHuman },
                { key: 'optout', label: t('playbooks.abort_optout'), value: abortOnOptout, set: setAbortOnOptout },
              ].map(({ key, label, value, set }) => (
                <label key={key} className="flex items-center gap-2 text-sm text-white/60 cursor-pointer">
                  <input type="checkbox" checked={value} onChange={e => set(e.target.checked)} className="accent-blue-500 rounded" />
                  {label}
                </label>
              ))}
            </div>
          </section>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">{error}</div>
          )}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-[#0d1117] px-6 py-4 border-t border-white/[0.06] flex justify-end gap-3">
          <button onClick={onClose} className="px-5 py-2.5 text-white/50 hover:text-white text-sm">{t('common.cancel')}</button>
          <button onClick={handleSave} disabled={saving}
            className="px-6 py-2.5 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-600/50 text-white rounded-xl font-medium flex items-center gap-2 transition-colors">
            {saving ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
            {t('playbooks.save')}
          </button>
        </div>
      </div>
    </div>
  );
}
