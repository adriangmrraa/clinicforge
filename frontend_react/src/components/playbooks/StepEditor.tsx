import React, { useState } from 'react';
import {
  ChevronDown, ChevronUp, Trash2, ArrowUp, ArrowDown,
  Send, MessageSquare, FileText, Clock, RefreshCw, Bell, Settings, GitBranch, Plus, X
} from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import MessagePreview from './MessagePreview';

export interface StepData {
  id?: number;
  step_order: number;
  step_label?: string;
  action_type: string;
  delay_minutes: number;
  schedule_hour_min?: number | null;
  schedule_hour_max?: number | null;
  template_name?: string;
  template_lang?: string;
  template_vars?: Record<string, string>;
  message_text?: string;
  instruction_source?: string;
  custom_instructions?: string;
  notify_channel?: string;
  notify_message?: string;
  update_field?: string;
  update_value?: string;
  wait_timeout_minutes?: number;
  response_rules?: Array<{ name: string; keywords: string[]; action: string }>;
  on_no_response?: string;
  on_unclassified?: string;
  on_response_next_step?: number | null;
  on_no_response_next_step?: number | null;
}

interface StepEditorProps {
  step: StepData;
  stepIndex: number;
  totalSteps: number;
  templates: Array<{ name: string; language: string; components?: any[] }>;
  onChange: (updated: StepData) => void;
  onDelete: () => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
}

const ACTION_OPTIONS = [
  { value: 'send_template', label: 'Enviar plantilla HSM', icon: <Send size={14} />, hint: 'Usa una plantilla aprobada de WhatsApp (con botones interactivos). Ideal para recordatorios y reseñas.' },
  { value: 'send_text', label: 'Enviar mensaje de texto', icon: <MessageSquare size={14} />, hint: 'Mensaje libre con variables. Úsalo para seguimientos personalizados como "¿Cómo te sentís?".' },
  { value: 'send_instructions', label: 'Enviar instrucciones del tratamiento', icon: <FileText size={14} />, hint: 'Envía automáticamente las instrucciones post-operatorias configuradas en el tratamiento.' },
  { value: 'wait', label: 'Esperar (delay)', icon: <Clock size={14} />, hint: 'Pausa la secuencia por un tiempo antes de ejecutar el siguiente paso.' },
  { value: 'wait_response', label: 'Esperar respuesta del paciente', icon: <RefreshCw size={14} />, hint: 'Pausa hasta que el paciente responda. Si no responde en el tiempo configurado, continúa o aborta.' },
  { value: 'notify_team', label: 'Notificar al equipo', icon: <Bell size={14} />, hint: 'Envía una alerta al equipo por Telegram o el dashboard. Útil si el paciente reporta dolor o urgencia.' },
  { value: 'update_status', label: 'Actualizar estado', icon: <Settings size={14} />, hint: 'Cambia automáticamente el estado de un turno (ej: marcar como confirmado).' },
];

const DELAY_PRESETS = [
  { label: 'Inmediato', value: 0 },
  { label: '30 min', value: 30 },
  { label: '1 hora', value: 60 },
  { label: '2 horas', value: 120 },
  { label: '3 horas', value: 180 },
  { label: '6 horas', value: 360 },
  { label: '12 horas', value: 720 },
  { label: '24 horas', value: 1440 },
  { label: '48 horas', value: 2880 },
  { label: '3 días', value: 4320 },
  { label: '7 días', value: 10080 },
  { label: '30 días', value: 43200 },
];

const RESPONSE_ACTIONS = [
  { value: 'continue', label: 'Continuar al siguiente paso' },
  { value: 'abort', label: 'Abortar la secuencia' },
  { value: 'pause', label: 'Pausar y esperar intervención' },
  { value: 'notify_and_pause', label: 'Notificar al equipo y pausar' },
  { value: 'pass_to_ai', label: 'Pasar al agente IA' },
];

const VARIABLE_LIST = [
  '{{nombre_paciente}}', '{{apellido_paciente}}', '{{tratamiento}}',
  '{{profesional}}', '{{fecha_turno}}', '{{hora_turno}}', '{{dia_semana}}',
  '{{sede}}', '{{precio}}', '{{saldo_pendiente}}', '{{nombre_clinica}}',
];

export default function StepEditor({
  step, stepIndex, totalSteps, templates,
  onChange, onDelete, onMoveUp, onMoveDown,
}: StepEditorProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(stepIndex === 0);
  const action = step.action_type;
  const isMessage = ['send_template', 'send_text', 'send_instructions'].includes(action);

  const update = (partial: Partial<StepData>) => onChange({ ...step, ...partial });

  // Parse response_rules defensively (DB may return string or object)
  const parseRules = (raw: any): Array<{ name: string; keywords: string[]; action: string }> => {
    if (!raw) return [];
    if (Array.isArray(raw)) return raw;
    if (typeof raw === 'string') {
      try { const parsed = JSON.parse(raw); return Array.isArray(parsed) ? parsed : []; }
      catch { return []; }
    }
    return [];
  };

  const currentRules = parseRules(step.response_rules);

  const addKeywordRule = () => {
    const rules = [...currentRules];
    rules.push({ name: '', keywords: [], action: 'continue' });
    update({ response_rules: rules });
  };

  const updateKeywordRule = (idx: number, field: string, value: any) => {
    const rules = [...currentRules];
    rules[idx] = { ...rules[idx], [field]: value };
    update({ response_rules: rules });
  };

  const removeKeywordRule = (idx: number) => {
    const rules = [...currentRules];
    rules.splice(idx, 1);
    update({ response_rules: rules });
  };

  const selectedTemplate = templates.find(t => t.name === step.template_name);
  const bodyComp = selectedTemplate?.components?.find((c: any) => c.type === 'BODY');
  const bodyText = bodyComp?.text ?? '';

  return (
    <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl overflow-hidden">
      {/* Header - always visible */}
      <div
        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-white/[0.02]"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-white/40 font-mono text-sm w-6 text-center">{stepIndex + 1}</span>
        <div className="flex-1 min-w-0">
          <span className="text-sm font-medium text-white">
            {step.step_label || ACTION_OPTIONS.find(a => a.value === action)?.label || action}
          </span>
          {step.delay_minutes > 0 && (
            <span className="text-xs text-white/40 ml-2">
              ⏱ {DELAY_PRESETS.find(d => d.value === step.delay_minutes)?.label || `${step.delay_minutes}min`}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {stepIndex > 0 && (
            <button onClick={(e) => { e.stopPropagation(); onMoveUp(); }} className="p-1 text-white/30 hover:text-white/60"><ArrowUp size={14} /></button>
          )}
          {stepIndex < totalSteps - 1 && (
            <button onClick={(e) => { e.stopPropagation(); onMoveDown(); }} className="p-1 text-white/30 hover:text-white/60"><ArrowDown size={14} /></button>
          )}
          <button onClick={(e) => { e.stopPropagation(); onDelete(); }} className="p-1 text-red-400/50 hover:text-red-400"><Trash2 size={14} /></button>
          {expanded ? <ChevronUp size={16} className="text-white/30" /> : <ChevronDown size={16} className="text-white/30" />}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 space-y-4 border-t border-white/[0.04]">
          {/* Label */}
          <div className="pt-3">
            <label className="text-xs font-medium text-white/40">{t('playbooks.step_label')}</label>
            <input
              value={step.step_label || ''}
              onChange={e => update({ step_label: e.target.value })}
              placeholder="Nombre del paso (opcional)"
              className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-1 focus:ring-blue-500/30"
            />
          </div>

          {/* Action type */}
          <div>
            <label className="text-xs font-medium text-white/40">{t('playbooks.action_type')}</label>
            <select
              value={action}
              onChange={e => update({ action_type: e.target.value })}
              className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-1 focus:ring-blue-500/30 appearance-none"
            >
              {ACTION_OPTIONS.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
            <p className="text-[11px] text-white/30 mt-1 leading-relaxed">
              {ACTION_OPTIONS.find(o => o.value === action)?.hint}
            </p>
          </div>

          {/* Delay */}
          <div>
            <label className="text-xs font-medium text-white/40">{t('playbooks.when_execute')}</label>
            <select
              value={step.delay_minutes}
              onChange={e => update({ delay_minutes: Number(e.target.value) })}
              className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-1 focus:ring-blue-500/30 appearance-none"
            >
              {DELAY_PRESETS.map(d => (
                <option key={d.value} value={d.value}>{d.label} {d.value === 0 ? '(después del paso anterior)' : 'después'}</option>
              ))}
            </select>
          </div>

          {/* Content: send_template */}
          {action === 'send_template' && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-white/40">{t('playbooks.select_template')}</label>
                <p className="text-[11px] text-white/25">Seleccioná una plantilla aprobada en Meta. Las variables (nombre, fecha, hora) se completan automáticamente con los datos del paciente y su turno.</p>
                <select
                  value={step.template_name || ''}
                  onChange={e => update({ template_name: e.target.value })}
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-1 focus:ring-blue-500/30 appearance-none"
                >
                  <option value="">— Seleccionar plantilla —</option>
                  {templates.map(tpl => (
                    <option key={tpl.name} value={tpl.name}>{tpl.name}</option>
                  ))}
                </select>
              </div>
              {bodyText && <MessagePreview text={bodyText} />}
            </div>
          )}

          {/* Content: send_text */}
          {action === 'send_text' && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-white/40">{t('playbooks.message_text')}</label>
              <p className="text-[11px] text-white/25 leading-relaxed">
                Escribí el mensaje que recibirá el paciente. Tocá las variables de abajo para insertarlas. Se reemplazan automáticamente con los datos reales del paciente.
              </p>
              <textarea
                value={step.message_text || ''}
                onChange={e => update({ message_text: e.target.value })}
                placeholder="Hola {{nombre_paciente}}, ¿cómo te sentís?"
                rows={3}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-1 focus:ring-blue-500/30 resize-none"
              />
              <div className="flex flex-wrap gap-1">
                {VARIABLE_LIST.map(v => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => update({ message_text: (step.message_text || '') + ' ' + v })}
                    className="text-[10px] px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/20"
                  >
                    {v}
                  </button>
                ))}
              </div>
              {step.message_text && <MessagePreview text={step.message_text} />}
            </div>
          )}

          {/* Content: send_instructions */}
          {action === 'send_instructions' && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-white/40">{t('playbooks.instruction_source')}</label>
              <div className="flex gap-3">
                <label className="flex items-center gap-2 text-sm text-white/70 cursor-pointer">
                  <input
                    type="radio"
                    checked={step.instruction_source !== 'custom'}
                    onChange={() => update({ instruction_source: 'from_treatment' })}
                    className="accent-blue-500"
                  />
                  Del tratamiento (automático)
                </label>
                <label className="flex items-center gap-2 text-sm text-white/70 cursor-pointer">
                  <input
                    type="radio"
                    checked={step.instruction_source === 'custom'}
                    onChange={() => update({ instruction_source: 'custom' })}
                    className="accent-blue-500"
                  />
                  Personalizadas
                </label>
              </div>
              {step.instruction_source === 'custom' && (
                <textarea
                  value={step.custom_instructions || ''}
                  onChange={e => update({ custom_instructions: e.target.value })}
                  placeholder="Instrucciones personalizadas..."
                  rows={3}
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none focus:ring-1 focus:ring-blue-500/30 resize-none"
                />
              )}
            </div>
          )}

          {/* Content: notify_team */}
          {action === 'notify_team' && (
            <div className="space-y-2">
              <label className="text-xs font-medium text-white/40">{t('playbooks.notify_channel')}</label>
              <p className="text-[11px] text-white/25">El equipo recibirá esta alerta cuando se ejecute este paso. Podés usar variables como {{nombre_paciente}} en el mensaje.</p>
              <select
                value={step.notify_channel || 'telegram'}
                onChange={e => update({ notify_channel: e.target.value })}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none"
              >
                <option value="telegram">Telegram</option>
                <option value="dashboard">Dashboard</option>
                <option value="both">Ambos</option>
              </select>
              <textarea
                value={step.notify_message || ''}
                onChange={e => update({ notify_message: e.target.value })}
                placeholder="⚠️ {{nombre_paciente}} reporta dolor post-cirugía"
                rows={2}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none resize-none"
              />
            </div>
          )}

          {/* Content: update_status */}
          {action === 'update_status' && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-white/40">Campo</label>
                <select
                  value={step.update_field || ''}
                  onChange={e => update({ update_field: e.target.value })}
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none"
                >
                  <option value="">Seleccionar</option>
                  <option value="appointment_status">Estado del turno</option>
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-white/40">Valor</label>
                <input
                  value={step.update_value || ''}
                  onChange={e => update({ update_value: e.target.value })}
                  placeholder="confirmed"
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none"
                />
              </div>
            </div>
          )}

          {/* Wait response config */}
          {action === 'wait_response' && (
            <div className="space-y-3">
              <div>
                <label className="text-xs font-medium text-white/40">{t('playbooks.wait_timeout')}</label>
                <p className="text-[11px] text-white/25">La secuencia se pausa hasta que el paciente responda. Si no responde en el tiempo configurado, se ejecuta la acción de "si no responde" definida abajo.</p>
                <select
                  value={step.wait_timeout_minutes || 120}
                  onChange={e => update({ wait_timeout_minutes: Number(e.target.value) })}
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none"
                >
                  <option value={60}>1 hora</option>
                  <option value={120}>2 horas</option>
                  <option value={360}>6 horas</option>
                  <option value={720}>12 horas</option>
                  <option value={1440}>24 horas</option>
                </select>
              </div>
            </div>
          )}

          {/* Response handling (for message actions) */}
          {isMessage && (
            <div className="space-y-3 pt-2 border-t border-white/[0.04]">
              <h4 className="text-xs font-bold text-white/50 uppercase tracking-wider">{t('playbooks.response_handling')}</h4>

              {/* Keyword rules */}
              <div className="space-y-2">
                <label className="text-xs font-medium text-white/40">{t('playbooks.keyword_rules')}</label>
                <p className="text-[11px] text-white/25 leading-relaxed">
                  Definí grupos de palabras clave para clasificar respuestas automáticamente. Incluí conjugaciones: "dolor", "duele", "me duele". Separalas con coma. El sistema busca coincidencia exacta de cada palabra en el mensaje.
                </p>
                {currentRules.map((rule, idx) => (
                  <div key={idx} className="flex gap-2 items-start bg-white/[0.02] rounded-lg p-2">
                    <input
                      value={rule.name}
                      onChange={e => updateKeywordRule(idx, 'name', e.target.value)}
                      placeholder="Nombre (ej: urgencia)"
                      className="w-24 px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs outline-none"
                    />
                    <input
                      value={(rule.keywords || []).join(', ')}
                      onChange={e => updateKeywordRule(idx, 'keywords', e.target.value.split(',').map(k => k.trim()).filter(Boolean))}
                      placeholder="dolor, sangra, fiebre"
                      className="flex-1 px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs outline-none"
                    />
                    <select
                      value={rule.action}
                      onChange={e => updateKeywordRule(idx, 'action', e.target.value)}
                      className="w-36 px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs outline-none appearance-none"
                    >
                      {RESPONSE_ACTIONS.map(a => (
                        <option key={a.value} value={a.value}>{a.label}</option>
                      ))}
                    </select>
                    <button onClick={() => removeKeywordRule(idx)} className="p-1 text-red-400/50 hover:text-red-400"><X size={12} /></button>
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addKeywordRule}
                  className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1"
                >
                  <Plus size={12} /> Agregar regla de palabras clave
                </button>
              </div>

              {/* On no response */}
              <div>
                <label className="text-xs font-medium text-white/40">{t('playbooks.on_no_response')}</label>
                <p className="text-[11px] text-white/25">¿Qué hacer si el paciente no responde en el tiempo configurado?</p>
                <select
                  value={step.on_no_response || 'continue'}
                  onChange={e => update({ on_no_response: e.target.value })}
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none"
                >
                  {RESPONSE_ACTIONS.map(a => (
                    <option key={a.value} value={a.value}>{a.label}</option>
                  ))}
                </select>
              </div>

              {/* On unclassified */}
              <div>
                <label className="text-xs font-medium text-white/40">{t('playbooks.on_unclassified')}</label>
                <p className="text-[11px] text-white/25">¿Qué hacer si la respuesta del paciente no coincide con ninguna palabra clave ni botón?</p>
                <select
                  value={step.on_unclassified || 'pass_to_ai'}
                  onChange={e => update({ on_unclassified: e.target.value })}
                  className="w-full mt-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm outline-none appearance-none"
                >
                  <option value="pass_to_ai">Pasar al agente IA</option>
                  <option value="continue">Continuar al siguiente paso</option>
                  <option value="pause">Pausar</option>
                  <option value="classify_with_ai">Clasificar con IA (usa tokens)</option>
                </select>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
