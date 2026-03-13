import React, { useState, useEffect, useCallback } from 'react';
import { 
  Smartphone, Instagram, Facebook, Settings, AlertCircle, CheckCircle2, 
  Clock, SkipForward, Send, UserCheck, Zap, Pencil, Trash2, Plus, 
  Lock, Files, MessageSquare, RefreshCw, X, Eye, Inbox
} from 'lucide-react';
import api from '../api/axios';
import PageHeader from '../components/PageHeader';

// ─── Mobile Hook ──────────────────────────────────────────────────────────────
function useWindowWidth() {
  const [width, setWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1024);
  useEffect(() => {
    const handler = () => setWidth(window.innerWidth);
    window.addEventListener('resize', handler);
    return () => window.removeEventListener('resize', handler);
  }, []);
  return width;
}

// ─── Types ────────────────────────────────────────────────────────────────────

interface AutomationRule {
  id: number;
  name: string;
  is_active: boolean;
  is_system: boolean;
  trigger_type: string;
  condition_json: Record<string, any>;
  message_type: 'free_text' | 'hsm';
  free_text_message?: string;
  ycloud_template_name?: string;
  ycloud_template_lang?: string;
  ycloud_template_vars?: Record<string, string>;
  channels: string[];
  send_hour_min: number;
  send_hour_max: number;
  created_at: string;
  updated_at: string;
}

interface AutomationLog {
  id: number;
  rule_name?: string;
  trigger_type: string;
  patient_name?: string;
  phone_number?: string;
  channel?: string;
  message_type?: string;
  message_preview?: string;
  template_name?: string;
  status: string;
  skip_reason?: string;
  error_details?: string;
  triggered_at: string;
  sent_at?: string;
}

interface YCloudTemplate {
  name: string;
  language: string;
  category: string;
  status: string;
  components: Array<{
    type: string;
    text?: string;
    example?: { body_text?: string[][] };
  }>;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const TRIGGER_LABELS: Record<string, string> = {
  appointment_reminder: 'Recordatorio 24h',
  post_appointment_completed: 'Feedback post-consulta',
  lead_meta_no_booking: 'Lead Meta sin turno',
  post_treatment_followup: 'Seguimiento tratamiento',
  patient_reactivation: 'Reactivación paciente',
  appointment_status_change: 'Cambio de estado',
};

const TRIGGER_COLORS: Record<string, string> = {
  appointment_reminder: '#6366f1',
  post_appointment_completed: '#10b981',
  lead_meta_no_booking: '#f59e0b',
  post_treatment_followup: '#8b5cf6',
  patient_reactivation: '#ec4899',
  appointment_status_change: '#64748b',
};

const STATUS_STYLES: Record<string, { bg: string; text: string }> = {
  sent:      { bg: '#d1fae5', text: '#065f46' },
  delivered: { bg: '#dbeafe', text: '#1e40af' },
  read:      { bg: '#e0e7ff', text: '#3730a3' },
  failed:    { bg: '#fee2e2', text: '#991b1b' },
  skipped:   { bg: '#fef9c3', text: '#713f12' },
  pending:   { bg: '#f1f5f9', text: '#475569' },
};

const CHANNEL_ICONS: Record<string, any> = {
  whatsapp: <Smartphone size={14} />,
  instagram: <Instagram size={14} />,
  facebook: <Facebook size={14} />,
  system: <Settings size={14} />,
};

const AVAILABLE_VARS = [
  { key: 'first_name', label: 'Nombre' },
  { key: 'last_name', label: 'Apellido' },
  { key: 'appointment_date', label: 'Fecha del turno' },
  { key: 'appointment_time', label: 'Hora del turno' },
  { key: 'treatment_name', label: 'Tratamiento' },
  { key: 'clinic_name', label: 'Nombre clínica' },
  { key: 'professional_name', label: 'Profesional' },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.pending;
  const icons: Record<string, any> = {
    sent: <CheckCircle2 size={12} />,
    delivered: <CheckCircle2 size={12} />,
    read: <Eye size={12} />,
    failed: <AlertCircle size={12} />,
    skipped: <SkipForward size={12} />,
    pending: <Clock size={12} />,
  };

  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '2px 10px', borderRadius: '9999px',
      fontSize: '12px', fontWeight: 600, background: s.bg, color: s.text, textTransform: 'capitalize',
    }}>
      {icons[status] || icons.pending}
      {status === 'sent' ? 'Enviado' :
       status === 'delivered' ? 'Entregado' :
       status === 'read' ? 'Leído' :
       status === 'failed' ? 'Fallido' :
       status === 'skipped' ? 'Omitido' : status}
    </span>
  );
}

function TriggerBadge({ type }: { type: string }) {
  const color = TRIGGER_COLORS[type] || '#64748b';
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: '9999px',
      fontSize: '12px', fontWeight: 600,
      background: color + '18', color: color, border: `1px solid ${color}33`,
    }}>
      {TRIGGER_LABELS[type] || type}
    </span>
  );
}

// ─── Rule Form Modal ──────────────────────────────────────────────────────────

function RuleFormModal({
  rule, templates, onClose, onSave, isMobile
}: {
  rule?: AutomationRule | null;
  templates: YCloudTemplate[];
  onClose: () => void;
  onSave: () => void;
  isMobile: boolean;
}) {
  const isEdit = !!rule;
  const isSystem = rule?.is_system ?? false;
  const messageOnly = isSystem; // solo puede editar el mensaje, no el trigger/canales/horario

  const [name, setName] = useState(rule?.name ?? '');
  const [triggerType, setTriggerType] = useState(rule?.trigger_type ?? 'appointment_reminder');
  const [conditionJson, setConditionJson] = useState<Record<string, any>>(rule?.condition_json ?? {});
  const [messageType, setMessageType] = useState<'free_text' | 'hsm'>(rule?.message_type ?? 'free_text');
  const [freeText, setFreeText] = useState(rule?.free_text_message ?? '');
  const [templateName, setTemplateName] = useState(rule?.ycloud_template_name ?? '');
  const [templateVars, setTemplateVars] = useState<Record<string, string>>(rule?.ycloud_template_vars ?? {});
  const [channels, setChannels] = useState<string[]>(rule?.channels ?? ['whatsapp']);
  const [sendHourMin, setSendHourMin] = useState(rule?.send_hour_min ?? 8);
  const [sendHourMax, setSendHourMax] = useState(rule?.send_hour_max ?? 20);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const icons = {
    edit: <Pencil size={18} />,
    plus: <Plus size={18} />,
    lock: <Lock size={14} />,
    save: <Send size={16} />,
  };

  const selectedTemplate = templates.find(t => t.name === templateName);
  const bodyComp = selectedTemplate?.components?.find(c => c.type === 'BODY');
  const bodyText = bodyComp?.text ?? '';
  const varMatches = bodyText.match(/\{\{\d+\}\}/g) ?? [];

  const handleChannelToggle = (ch: string) =>
    setChannels(prev => prev.includes(ch) ? prev.filter(c => c !== ch) : [...prev, ch]);

  const handleSave = async () => {
    if (!name.trim()) { setError('El nombre es obligatorio.'); return; }
    if (messageType === 'free_text' && !freeText.trim()) { setError('El mensaje es obligatorio.'); return; }
    if (messageType === 'hsm' && !templateName) { setError('Seleccioná una plantilla HSM.'); return; }
    setSaving(true); setError('');
    try {
      const payload = {
        name, trigger_type: triggerType, condition_json: conditionJson,
        message_type: messageType,
        free_text_message: messageType === 'free_text' ? freeText : null,
        ycloud_template_name: messageType === 'hsm' ? templateName : null,
        ycloud_template_lang: 'es',
        ycloud_template_vars: messageType === 'hsm' ? templateVars : {},
        channels, send_hour_min: sendHourMin, send_hour_max: sendHourMax,
      };
      if (isEdit && rule) await api.patch(`/admin/automations/rules/${rule.id}`, payload);
      else await api.post('/admin/automations/rules', payload);
      onSave();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Error al guardar la regla.');
    } finally { setSaving(false); }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(15,23,42,0.5)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: '#fff', borderRadius: isMobile ? '0' : '16px', width: '100%', 
        maxWidth: isMobile ? '100%' : '600px',
        height: isMobile ? '100%' : 'auto',
        maxHeight: isMobile ? '100%' : '90vh', overflowY: 'auto',
        boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
        border: '1px solid #e2e8f0',
      }}>
        {/* Header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ color: '#6366f1' }}>{isEdit ? icons.edit : icons.plus}</div>
            <div>
              <h2 style={{ margin: 0, color: '#0f172a', fontSize: '18px', fontWeight: 700 }}>
                {messageOnly ? 'Editar Mensaje' : isEdit ? 'Editar Regla' : 'Nueva Regla'}
              </h2>
              {messageOnly && <p style={{ margin: '4px 0 0', color: '#64748b', fontSize: '13px' }}>Podés cambiar el mensaje que se envía. El trigger, canales y horario son propios del sistema.</p>}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', cursor: 'pointer', display: 'flex', alignItems: 'center' }}><X size={20} /></button>
        </div>

        <div style={{ padding: '20px 24px' }}>
          {error && (
            <div style={{ background: '#fee2e2', color: '#991b1b', padding: '10px 14px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px' }}>{error}</div>
          )}

          {/* Nombre */}
          <div style={{ marginBottom: '16px' }}>
            <label style={labelStyle}>Nombre de la regla</label>
            <input value={name} onChange={e => setName(e.target.value)} disabled={isSystem}
              placeholder="Ej: Seguimiento post-implante"
              style={{ ...lightInputStyle, opacity: isSystem ? 0.6 : 1, background: isSystem ? '#f8fafc' : '#fff', cursor: isSystem ? 'not-allowed' : 'text' }} />
          </div>

          {/* Trigger - solo informativo para reglas de sistema */}
          {messageOnly ? (
            <div style={{ marginBottom: '16px', background: '#f8fafc', borderRadius: '10px', padding: '12px 16px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Cuándo se activa</span>
              <div style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={12} style={{ color: '#94a3b8' }} />
                <span style={{ color: '#334155', fontSize: '14px', fontWeight: 600 }}>{TRIGGER_LABELS[triggerType] || triggerType}</span>
                <span style={{ fontSize: '11px', color: '#94a3b8' }}>(propietaria)</span>
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle}>¿Cuándo se activa?</label>
              <select value={triggerType} onChange={e => setTriggerType(e.target.value)} style={lightInputStyle}>
                <option value="appointment_reminder">Recordatorio 24h antes del turno</option>
                <option value="post_appointment_completed">45 min después de completar consulta</option>
                <option value="lead_meta_no_booking">Lead de Meta no agendó</option>
                <option value="post_treatment_followup">Seguimiento post-tratamiento</option>
                <option value="patient_reactivation">Paciente inactivo X días</option>
              </select>
            </div>
          )}

          {/* Cond dinámica - solo si no es sistema */}
          {!messageOnly && (triggerType === 'lead_meta_no_booking' || triggerType === 'patient_reactivation') && (
            <div style={{ marginBottom: '16px', background: '#f0f4ff', borderRadius: '10px', padding: '14px', border: '1px solid #c7d2fe' }}>
              <label style={{ ...labelStyle, color: '#4338ca' }}>
                {triggerType === 'lead_meta_no_booking' ? 'Horas de espera sin turno' : 'Días de inactividad'}
              </label>
              <input type="number"
                value={triggerType === 'lead_meta_no_booking' ? (conditionJson.delay_minutes || 120) / 60 : (conditionJson.days_inactive || 90)}
                onChange={e => {
                  const v = parseInt(e.target.value);
                  setConditionJson(triggerType === 'lead_meta_no_booking'
                    ? { ...conditionJson, delay_minutes: v * 60 }
                    : { ...conditionJson, days_inactive: v });
                }}
                style={{ ...lightInputStyle, width: '120px' }} />
            </div>
          )}

          {/* Canales - informativo para sistema */}
          {messageOnly ? (
            <div style={{ marginBottom: '16px', background: '#f8fafc', borderRadius: '10px', padding: '12px 16px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Canales</span>
              <div style={{ marginTop: '4px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {channels.map(ch => (
                  <span key={ch} style={{ padding: '4px 10px', borderRadius: '6px', background: '#ede9fe', color: '#6366f1', fontSize: '12px', fontWeight: 600 }}>
                    {CHANNEL_ICONS[ch]} {ch}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle}>Canales</label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {['whatsapp', 'instagram', 'facebook'].map(ch => (
                  <button key={ch} onClick={() => handleChannelToggle(ch)} style={{
                    padding: '7px 14px', borderRadius: '8px', cursor: 'pointer',
                    fontSize: '14px', fontWeight: 600, transition: 'all 0.15s',
                    border: channels.includes(ch) ? '2px solid #6366f1' : '2px solid #e2e8f0',
                    background: channels.includes(ch) ? '#ede9fe' : '#fff',
                    color: channels.includes(ch) ? '#6366f1' : '#64748b',
                  }}>
                    {CHANNEL_ICONS[ch]} {ch.charAt(0).toUpperCase() + ch.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Tipo de mensaje - siempre editable */}
          <>
              <div style={{ marginBottom: '16px' }}>
                <label style={labelStyle}>Tipo de mensaje</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {(['free_text', 'hsm'] as const).map(type => (
                    <button key={type} onClick={() => setMessageType(type)} style={{
                      flex: 1, padding: '11px', borderRadius: '9px', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                      border: messageType === type ? '2px solid #6366f1' : '2px solid #e2e8f0',
                      background: messageType === type ? '#ede9fe' : '#fafafa',
                      color: messageType === type ? '#6366f1' : '#64748b',
                      fontWeight: 600, fontSize: '14px', transition: 'all 0.15s',
                    }}>
                      {type === 'free_text' ? <MessageSquare size={16} /> : <Files size={16} />}
                      {type === 'free_text' ? 'Texto libre' : 'Plantilla HSM'}
                    </button>
                  ))}
                </div>
                <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#94a3b8' }}>
                  {messageType === 'free_text'
                    ? 'Gratuito · Solo dentro de ventana 24h de WhatsApp'
                    : 'Plantilla aprobada por Meta · Funciona fuera de la ventana de 24h'}
                </p>
              </div>

              {messageType === 'free_text' && (
                <div style={{ marginBottom: '16px' }}>
                  <label style={labelStyle}>Mensaje</label>
                  <p style={{ margin: '0 0 6px', fontSize: '12px', color: '#94a3b8' }}>
                    Variables disponibles: {'{{first_name}}'} {'{{appointment_time}}'} {'{{treatment_name}}'} {'{{clinic_name}}'}
                  </p>
                  <textarea value={freeText} onChange={e => setFreeText(e.target.value)} rows={4}
                    placeholder="Hola {{first_name}}, te recordamos tu turno mañana..."
                    style={{ ...lightInputStyle, resize: 'vertical', minHeight: '90px' }} />
                </div>
              )}

              {messageType === 'hsm' && (
                <div style={{ marginBottom: '16px' }}>
                  <label style={labelStyle}>Plantilla HSM</label>
                  {templates.length === 0 ? (
                    <div style={{ padding: '12px', background: '#fef9c3', borderRadius: '8px', color: '#854d0e', fontSize: '13px' }}>
                      ⚠️ No hay plantillas aprobadas disponibles. Verificá YCLOUD_API_KEY en el servidor.
                    </div>
                  ) : (
                    <select value={templateName} onChange={e => setTemplateName(e.target.value)} style={lightInputStyle}>
                      <option value="">— Elegí una plantilla —</option>
                      {templates.map(t => <option key={t.name} value={t.name}>{t.name} · {t.language} · {t.category}</option>)}
                    </select>
                  )}
                  {bodyText && (
                    <div style={{ marginTop: '10px', background: '#f8fafc', borderRadius: '8px', padding: '12px', border: '1px solid #e2e8f0' }}>
                      <p style={{ margin: '0 0 6px', fontSize: '11px', color: '#94a3b8', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Preview</p>
                      <p style={{ margin: 0, color: '#334155', fontSize: '13px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>{bodyText}</p>
                    </div>
                  )}
                  {varMatches.length > 0 && (
                    <div style={{ marginTop: '14px' }}>
                      <label style={{ ...labelStyle, marginBottom: '6px' }}>Mapeo de variables</label>
                      {varMatches.map(v => (
                        <div key={v} style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                          <span style={{ width: '48px', textAlign: 'center', padding: '7px', borderRadius: '6px', background: '#ede9fe', color: '#6366f1', fontSize: '12px', fontWeight: 700 }}>{v}</span>
                          <span style={{ color: '#94a3b8' }}>→</span>
                          <select value={templateVars[v] ?? ''} onChange={e => setTemplateVars(prev => ({ ...prev, [v]: e.target.value }))} style={{ ...lightInputStyle, flex: 1 }}>
                            <option value="">— Campo del paciente —</option>
                            {AVAILABLE_VARS.map(av => <option key={av.key} value={av.key}>{av.label}</option>)}
                          </select>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>

          {/* Horario - informativo para sistema */}
          {messageOnly ? (
            <div style={{ marginBottom: '24px', background: '#f8fafc', borderRadius: '10px', padding: '12px 16px', border: '1px solid #e2e8f0' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Horario</span>
              <div style={{ marginTop: '4px', color: '#334155', fontSize: '14px', fontWeight: 600 }}>
                {sendHourMin}:00 – {sendHourMax}:00 hs &nbsp;<span style={{ fontSize: '11px', color: '#94a3b8' }}>(no editable)</span>
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: '24px' }}>
              <label style={labelStyle}>Horario de envío</label>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  <span style={{ fontSize: '11px', color: '#94a3b8' }}>Desde</span>
                  <input type="number" min={0} max={23} value={sendHourMin} onChange={e => setSendHourMin(Number(e.target.value))} style={{ ...lightInputStyle, width: '76px' }} />
                </div>
                <span style={{ color: '#94a3b8', marginTop: '16px' }}>–</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  <span style={{ fontSize: '11px', color: '#94a3b8' }}>Hasta</span>
                  <input type="number" min={0} max={23} value={sendHourMax} onChange={e => setSendHourMax(Number(e.target.value))} style={{ ...lightInputStyle, width: '76px' }} />
                </div>
                <span style={{ color: '#94a3b8', marginTop: '16px', fontSize: '13px' }}>hs</span>
              </div>
            </div>
          )}

          {/* Botones */}
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', paddingTop: '16px', borderTop: '1px solid #f1f5f9' }}>
            <button onClick={onClose} style={btnSecondaryStyle}>Cancelar</button>
            <button onClick={handleSave} disabled={saving} style={{ ...btnPrimaryStyle, opacity: saving ? 0.6 : 1, display: 'flex', alignItems: 'center', gap: '8px' }}>
              {saving ? <RefreshCw size={16} className="animate-spin" /> : icons.save}
              {saving ? 'Guardando...' : messageOnly ? 'Guardar Mensaje' : isEdit ? 'Guardar Cambios' : 'Crear Regla'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Rule Card ────────────────────────────────────────────────────────────────

function RuleCard({ rule, onToggle, onEdit, onDelete }: {
  rule: AutomationRule; onToggle: () => void;
  onEdit: () => void; onDelete: (() => void) | null;
}) {
  const triggerColor = TRIGGER_COLORS[rule.trigger_type] || '#64748b';
  return (
    <div style={{
      background: '#fff', borderRadius: '12px', padding: '14px 18px',
      border: `1px solid ${rule.is_active ? '#e0e7ff' : '#f1f5f9'}`,
      display: 'flex', alignItems: 'center', gap: '14px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
      transition: 'box-shadow 0.15s',
    }}>
      {/* Toggle */}
      <div onClick={onToggle} style={{
        width: '38px', height: '22px', borderRadius: '11px',
        background: rule.is_active ? '#6366f1' : '#e2e8f0',
        position: 'relative', cursor: 'pointer', flexShrink: 0, transition: 'background 0.2s',
      }}>
        <div style={{
          position: 'absolute', top: '3px',
          left: rule.is_active ? '18px' : '3px',
          width: '16px', height: '16px', borderRadius: '50%',
          background: '#fff', transition: 'left 0.2s',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
        }} />
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ color: '#0f172a', fontSize: '15px', fontWeight: 700 }}>{rule.name}</span>
          {rule.is_system && (
            <span style={{ padding: '1px 7px', borderRadius: '5px', fontSize: '11px', fontWeight: 700, background: '#ede9fe', color: '#6366f1', display: 'flex', alignItems: 'center', gap: '3px' }}>
              <Lock size={10} /> Sistema
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px', marginTop: '5px', flexWrap: 'wrap', alignItems: 'center' }}>
          <TriggerBadge type={rule.trigger_type} />
          <span style={{ color: '#94a3b8', fontSize: '12px' }}>
            {rule.message_type === 'hsm' ? `📋 HSM: ${rule.ycloud_template_name}` : '💬 Texto libre'}
          </span>
          {rule.channels.map(ch => (
            <span key={ch} style={{ color: '#94a3b8', fontSize: '12px' }}>{CHANNEL_ICONS[ch]}</span>
          ))}
          <span style={{ color: '#cbd5e1', fontSize: '12px' }}>{rule.send_hour_min}:00 – {rule.send_hour_max}:00 hs</span>
        </div>
      </div>

      {/* Acciones */}
      <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
        <button onClick={onEdit} title={rule.is_system ? 'Ver' : 'Editar'} style={iconBtnStyle}>
          {rule.is_system ? <Eye size={16} /> : <Pencil size={16} />}
        </button>
        {onDelete && (
          <button onClick={onDelete} title="Eliminar" style={{ ...iconBtnStyle, color: '#ef4444' }}>
            <Trash2 size={16} />
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, color }: { icon: React.ComponentType<{ size?: number; className?: string }>; label: string; value: string | number; color: string }) {
  return (
    <div style={{
      background: '#fff', borderRadius: '12px', padding: '18px 22px',
      border: `1px solid ${color}33`,
      display: 'flex', alignItems: 'center', gap: '14px',
      boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
    }}>
      <div style={{ width: '44px', height: '44px', borderRadius: '12px', background: color + '18', display: 'flex', alignItems: 'center', justifyContent: 'center', color: color }}>
        <Icon size={24} />
      </div>
      <div>
        <div style={{ color: '#0f172a', fontSize: '24px', fontWeight: 800, lineHeight: 1 }}>{value}</div>
        <div style={{ color: '#94a3b8', fontSize: '13px', marginTop: '3px' }}>{label}</div>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function MetaTemplatesView() {
  const width = useWindowWidth();
  const isMobile = width < 768;
  const [activeTab, setActiveTab] = useState<'rules' | 'logs' | 'templates'>('rules');
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [logs, setLogs] = useState<AutomationLog[]>([]);
  const [templates, setTemplates] = useState<YCloudTemplate[]>([]);
  const [stats, setStats] = useState({ sent: 0, delivery_rate: 0, active_rules: 0 });
  // Carga rápida: solo rules bloquea el render inicial
  const [rulesLoading, setRulesLoading] = useState(true);
  const [logsLoading, setLogsLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [editingRule, setEditingRule] = useState<AutomationRule | null>(null);

  // Filtros logs
  const [filterTrigger, setFilterTrigger] = useState('');
  const [filterStatus, setFilterStatus] = useState('');
  const [filterChannel, setFilterChannel] = useState('');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');
  const [logPage, setLogPage] = useState(1);
  const [logTotal, setLogTotal] = useState(0);
  const [logPages, setLogPages] = useState(1);

  const loadRules = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/automations/rules');
      setRules(data.rules || []);
      const active = (data.rules || []).filter((r: AutomationRule) => r.is_active).length;
      setStats(prev => ({ ...prev, active_rules: active }));
    } catch { /* silencioso */ }
  }, []);

  const loadLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const params: Record<string, any> = { page: logPage, limit: 50 };
      if (filterTrigger) params.trigger_type = filterTrigger;
      if (filterStatus) params.status = filterStatus;
      if (filterChannel) params.channel = filterChannel;
      if (filterDateFrom) params.date_from = filterDateFrom;
      if (filterDateTo) params.date_to = filterDateTo;
      const { data } = await api.get('/admin/automations/logs', { params });
      setLogs(data.logs || []);
      setLogTotal(data.total || 0);
      setLogPages(data.pages || 1);
      const sent = (data.logs || []).filter((l: AutomationLog) => ['sent','delivered'].includes(l.status)).length;
      const delivered = (data.logs || []).filter((l: AutomationLog) => l.status === 'delivered').length;
      setStats(prev => ({ ...prev, sent, delivery_rate: sent > 0 ? Math.round((delivered / sent) * 100) : 0 }));
    } catch { /* silencioso */ } finally { setLogsLoading(false); }
  }, [logPage, filterTrigger, filterStatus, filterChannel, filterDateFrom, filterDateTo]);

  const loadTemplates = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/automations/ycloud-templates');
      setTemplates(data.templates || []);
    } catch { /* silencioso */ }
  }, []);

  // Init: reglas primero (rápido), logs y templates en background
  useEffect(() => {
    setRulesLoading(true);
    loadRules().finally(() => setRulesLoading(false));
    // Background: no bloquea el render
    loadLogs();
    loadTemplates();
  }, []); // eslint-disable-line

  // Recargar logs cuando cambian filtros
  useEffect(() => { loadLogs(); }, [loadLogs]);

  const handleToggleRule = async (rule: AutomationRule) => {
    try { await api.patch(`/admin/automations/rules/${rule.id}/toggle`); await loadRules(); } catch { /* */ }
  };

  const handleDeleteRule = async (rule: AutomationRule) => {
    if (!confirm(`¿Eliminar "${rule.name}"?`)) return;
    try { await api.delete(`/admin/automations/rules/${rule.id}`); await loadRules(); }
    catch (e: any) { alert(e?.response?.data?.detail ?? 'Error al eliminar.'); }
  };

  const systemRules = rules.filter(r => r.is_system);
  const customRules = rules.filter(r => !r.is_system);

  // Loading solo bloquea si rules aún no cargaron
  if (rulesLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', background: '#f8fafc' }}>
        <div style={{ textAlign: 'center', color: '#64748b' }}>
          <RefreshCw size={32} className="animate-spin" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
          <p style={{ margin: 0, fontSize: '14px', fontWeight: 500 }}>Cargando automatizaciones...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', background: '#f8fafc', padding: isMobile ? '16px' : '28px 32px' }}>
      {/* Header */}
      <PageHeader 
        title="Automatizaciones & HSM" 
        subtitle="Motor de Reglas · Seguimientos · WhatsApp Marketing"
      />

      {/* Stats */}
      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, 1fr)', 
        gap: '12px', 
        marginBottom: '24px' 
      }}>
        <StatCard icon={Send} label="Enviados (total)" value={stats.sent} color="#6366f1" />
        <StatCard icon={UserCheck} label="Tasa de entrega" value={`${stats.delivery_rate}%`} color="#10b981" />
        <StatCard icon={Zap} label="Reglas activas" value={stats.active_rules} color="#f59e0b" />
      </div>

      {/* Tabs */}
      <div style={{ 
        display: 'flex', 
        gap: '2px', 
        background: '#e2e8f0', 
        borderRadius: '10px', 
        padding: '3px', 
        marginBottom: '22px', 
        width: isMobile ? '100%' : 'fit-content',
        overflowX: 'auto',
        WebkitOverflowScrolling: 'touch'
      }}>
            <button key={tab} onClick={() => setActiveTab(tab)} style={{
              padding: '8px 18px', borderRadius: '8px', border: 'none', cursor: 'pointer',
              fontSize: '13px', fontWeight: 600, transition: 'all 0.15s',
              display: 'flex', alignItems: 'center', gap: '8px',
              background: activeTab === tab ? '#fff' : 'transparent',
              color: activeTab === tab ? '#6366f1' : '#64748b',
              boxShadow: activeTab === tab ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
              whiteSpace: 'nowrap'
            }}>
              {tab === 'rules' ? <Zap size={14} /> : tab === 'logs' ? <MessageSquare size={14} /> : <Files size={14} />}
              {tab === 'rules' ? 'Reglas' : tab === 'logs' ? 'Logs de Envío' : 'Plantillas YCloud'}
            </button>
      </div>

      {/* ── TAB: REGLAS ── */}
      {activeTab === 'rules' && (
        <div>
          {/* Reglas Sistema */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Zap size={18} style={{ color: '#6366f1' }} />
              <h2 style={{ margin: 0, color: '#0f172a', fontSize: '15px', fontWeight: 700 }}>Reglas del Sistema</h2>
              <span style={{ padding: '1px 8px', background: '#ede9fe', color: '#6366f1', borderRadius: '6px', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Lock size={10} /> Propietarias
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {systemRules.map(rule => (
                <RuleCard key={rule.id} rule={rule} onToggle={() => handleToggleRule(rule)}
                  onEdit={() => { setEditingRule(rule); setShowModal(true); }} onDelete={null} />
              ))}
              {systemRules.length === 0 && (
                <div style={{ color: '#94a3b8', fontSize: '13px', padding: '14px', background: '#fff', borderRadius: '10px', border: '1px solid #f1f5f9' }}>
                  Las reglas de sistema se crearán automáticamente al reiniciar el servidor.
                </div>
              )}
            </div>
          </div>

          {/* Reglas Personalizadas */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '3px', height: '18px', background: '#10b981', borderRadius: '2px' }} />
                <h2 style={{ margin: 0, color: '#0f172a', fontSize: '15px', fontWeight: 700 }}>Reglas Personalizadas</h2>
              </div>
              <button onClick={() => { setEditingRule(null); setShowModal(true); }} style={{ ...btnPrimaryStyle, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Plus size={16} /> Nueva Regla
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {customRules.map(rule => (
                <RuleCard key={rule.id} rule={rule} onToggle={() => handleToggleRule(rule)}
                  onEdit={() => { setEditingRule(rule); setShowModal(true); }}
                  onDelete={() => handleDeleteRule(rule)} />
              ))}
              {customRules.length === 0 && (
                <div style={{
                  padding: '40px', borderRadius: '12px', border: '2px dashed #e2e8f0',
                  textAlign: 'center', color: '#94a3b8', background: '#fff',
                }}>
                  <div style={{ marginBottom: '16px', color: '#e2e8f0' }}>
                    <Zap size={48} style={{ margin: '0 auto' }} />
                  </div>
                  <p style={{ margin: '0 0 14px', fontSize: '14px', fontWeight: 500 }}>Aún no tenés reglas personalizadas.</p>
                  <button onClick={() => { setEditingRule(null); setShowModal(true); }} style={btnPrimaryStyle}>
                    Crear primera regla
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── TAB: LOGS ── */}
      {activeTab === 'logs' && (
        <div>
          {/* Filtros */}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px', background: '#fff', borderRadius: '10px', padding: '14px', border: '1px solid #f1f5f9', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            <select value={filterTrigger} onChange={e => { setFilterTrigger(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 150px' }}>
              <option value="">Todos los triggers</option>
              {Object.entries(TRIGGER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 130px' }}>
              <option value="">Todos los estados</option>
              <option value="sent">Enviado</option>
              <option value="delivered">Entregado</option>
              <option value="failed">Fallido</option>
              <option value="skipped">Omitido</option>
            </select>
            <select value={filterChannel} onChange={e => { setFilterChannel(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 120px' }}>
              <option value="">Todos los canales</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
            </select>
            <input type="date" value={filterDateFrom} onChange={e => { setFilterDateFrom(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 130px' }} />
            <input type="date" value={filterDateTo} onChange={e => { setFilterDateTo(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 130px' }} />
            <button onClick={() => { setFilterTrigger(''); setFilterStatus(''); setFilterChannel(''); setFilterDateFrom(''); setFilterDateTo(''); setLogPage(1); }} style={btnSecondaryStyle}>
              Limpiar
            </button>
          </div>

          <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #f1f5f9', overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
            {logsLoading ? (
              <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontSize: '14px' }}>Cargando logs...</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: '#f8fafc' }}>
                      {['Paciente', 'Trigger', 'Canal', 'Mensaje', 'Fecha/Hora', 'Estado'].map(h => (
                        <th key={h} style={{ padding: '11px 14px', textAlign: 'left', color: '#94a3b8', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid #f1f5f9', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {logs.length === 0 && (
                      <tr><td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8', fontSize: '14px' }}>
                        No hay logs con los filtros actuales.
                      </td></tr>
                    )}
                    {logs.map((log, i) => (
                      <tr key={log.id} style={{ borderBottom: '1px solid #f8fafc', background: i % 2 === 0 ? '#fff' : '#fafafa' }}>
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ color: '#0f172a', fontSize: '13px', fontWeight: 600 }}>{log.patient_name || '—'}</div>
                          <div style={{ color: '#94a3b8', fontSize: '11px' }}>{log.phone_number || ''}</div>
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <TriggerBadge type={log.trigger_type} />
                          {log.rule_name && <div style={{ color: '#94a3b8', fontSize: '11px', marginTop: '2px' }}>{log.rule_name}</div>}
                        </td>
                        <td style={{ padding: '12px 14px', color: '#64748b', fontSize: '13px' }}>
                          {CHANNEL_ICONS[log.channel || 'whatsapp']} {log.channel || 'whatsapp'}
                        </td>
                        <td style={{ padding: '12px 14px', maxWidth: '200px' }}>
                          <div style={{ color: '#64748b', fontSize: '12px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {log.message_preview || log.template_name || '—'}
                          </div>
                          {log.skip_reason && <div style={{ color: '#b45309', fontSize: '11px', marginTop: '1px', display: 'flex', alignItems: 'center', gap: '4px' }}><SkipForward size={10} /> {log.skip_reason}</div>}
                        </td>
                        <td style={{ padding: '12px 14px', color: '#94a3b8', fontSize: '12px', whiteSpace: 'nowrap' }}>
                          {new Date(log.triggered_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                        </td>
                        <td style={{ padding: '12px 14px' }}><StatusBadge status={log.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {logPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderTop: '1px solid #f1f5f9' }}>
                <span style={{ color: '#94a3b8', fontSize: '12px' }}>{logTotal} registros · Pág. {logPage} de {logPages}</span>
                <div style={{ display: 'flex', gap: '6px' }}>
                  <button disabled={logPage <= 1} onClick={() => setLogPage(p => p - 1)} style={{ ...btnSecondaryStyle, padding: '5px 12px', opacity: logPage <= 1 ? 0.4 : 1 }}>‹</button>
                  <button disabled={logPage >= logPages} onClick={() => setLogPage(p => p + 1)} style={{ ...btnSecondaryStyle, padding: '5px 12px', opacity: logPage >= logPages ? 0.4 : 1 }}>›</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB: PLANTILLAS YCLOUD ── */}
      {activeTab === 'templates' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <h2 style={{ margin: '0 0 2px', color: '#0f172a', fontSize: '15px', fontWeight: 700 }}>Plantillas HSM de YCloud</h2>
              <p style={{ margin: 0, color: '#94a3b8', fontSize: '12px' }}>Solo plantillas con estado APPROVED · Solo lectura</p>
            </div>
            <button onClick={loadTemplates} style={btnSecondaryStyle}>🔄 Actualizar</button>
          </div>

          {templates.length === 0 ? (
            <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8', background: '#fff', borderRadius: '12px', border: '1px solid #f1f5f9' }}>
              <div style={{ color: '#e2e8f0', marginBottom: '16px' }}>
                <Inbox size={48} style={{ margin: '0 auto' }} />
              </div>
              <p style={{ margin: '0 0 6px', fontSize: '14px', fontWeight: 500, color: '#64748b' }}>No hay plantillas aprobadas.</p>
              <p style={{ margin: 0, fontSize: '12px' }}>Verificá que YCLOUD_API_KEY esté configurada en el servidor.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px' }}>
              {templates.map(t => {
                const body = t.components?.find(c => c.type === 'BODY');
                const catColors: Record<string, string> = { MARKETING: '#f59e0b', UTILITY: '#6366f1', AUTHENTICATION: '#10b981' };
                const catColor = catColors[t.category] || '#64748b';
                return (
                  <div key={t.name} style={{ background: '#fff', borderRadius: '10px', padding: '16px', border: '1px solid #f1f5f9', boxShadow: '0 1px 3px rgba(0,0,0,0.04)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <div>
                        <p style={{ margin: '0 0 2px', color: '#0f172a', fontSize: '13px', fontWeight: 700 }}>{t.name}</p>
                        <span style={{ fontSize: '11px', color: '#94a3b8' }}>{t.language}</span>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', alignItems: 'flex-end' }}>
                        <span style={{ padding: '1px 7px', borderRadius: '5px', fontSize: '10px', fontWeight: 700, background: catColor + '18', color: catColor }}>{t.category}</span>
                        <span style={{ padding: '1px 7px', borderRadius: '5px', fontSize: '10px', fontWeight: 700, background: '#d1fae5', color: '#065f46', display: 'flex', alignItems: 'center', gap: '3px' }}><CheckCircle2 size={10} /> APPROVED</span>
                      </div>
                    </div>
                    {body?.text && (
                      <p style={{ margin: 0, color: '#64748b', fontSize: '12px', lineHeight: '1.5', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                        {body.text}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Modal */}
      {showModal && (
        <RuleFormModal
          rule={editingRule}
          templates={templates}
          isMobile={isMobile}
          onClose={() => { setShowModal(false); setEditingRule(null); }}
          onSave={async () => { setShowModal(false); setEditingRule(null); await loadRules(); }}
        />
      )}
    </div>
  );
}

// ─── Shared Styles ────────────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  display: 'block', marginBottom: '6px',
  color: '#374151', fontSize: '13px', fontWeight: 600,
};

// ✅ Inputs tipo light: texto oscuro, fondo blanco — no invisible
const lightInputStyle: React.CSSProperties = {
  display: 'block', width: '100%', boxSizing: 'border-box',
  padding: '9px 12px', borderRadius: '8px',
  background: '#fff', border: '1px solid #e2e8f0',
  color: '#1e293b', fontSize: '14px',
  outline: 'none', appearance: 'auto',
};

const btnPrimaryStyle: React.CSSProperties = {
  padding: '9px 18px', borderRadius: '8px', border: 'none', cursor: 'pointer',
  background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
  color: '#fff', fontSize: '13px', fontWeight: 700,
  boxShadow: '0 2px 8px rgba(99,102,241,0.3)', transition: 'all 0.15s',
};

const btnSecondaryStyle: React.CSSProperties = {
  padding: '9px 14px', borderRadius: '8px', cursor: 'pointer',
  background: '#fff', border: '1px solid #e2e8f0',
  color: '#64748b', fontSize: '13px', fontWeight: 600, transition: 'all 0.15s',
};

const iconBtnStyle: React.CSSProperties = {
  padding: '6px 10px', borderRadius: '7px', cursor: 'pointer',
  background: '#f8fafc', border: '1px solid #f1f5f9',
  color: '#64748b', fontSize: '14px', transition: 'all 0.15s',
};
