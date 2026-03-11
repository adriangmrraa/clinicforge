import { useState, useEffect, useCallback } from 'react';
import api from '../api/axios';

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

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  sent:      { bg: '#d1fae5', text: '#065f46' },
  delivered: { bg: '#dbeafe', text: '#1e40af' },
  read:      { bg: '#e0e7ff', text: '#3730a3' },
  failed:    { bg: '#fee2e2', text: '#991b1b' },
  skipped:   { bg: '#fef9c3', text: '#713f12' },
  pending:   { bg: '#f1f5f9', text: '#475569' },
};

const CHANNEL_ICONS: Record<string, string> = {
  whatsapp: '📱',
  instagram: '📸',
  facebook: '👍',
  system: '⚙️',
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
  const colors = STATUS_COLORS[status] || STATUS_COLORS.pending;
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 10px',
      borderRadius: '9999px',
      fontSize: '12px',
      fontWeight: 600,
      background: colors.bg,
      color: colors.text,
      textTransform: 'capitalize',
    }}>
      {status === 'sent' ? '✅ Enviado' :
       status === 'delivered' ? '📬 Entregado' :
       status === 'read' ? '👁️ Leído' :
       status === 'failed' ? '❌ Fallido' :
       status === 'skipped' ? '⏭️ Omitido' : status}
    </span>
  );
}

function TriggerBadge({ type }: { type: string }) {
  const color = TRIGGER_COLORS[type] || '#64748b';
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 10px',
      borderRadius: '9999px',
      fontSize: '12px',
      fontWeight: 600,
      background: color + '22',
      color: color,
      border: `1px solid ${color}44`,
    }}>
      {TRIGGER_LABELS[type] || type}
    </span>
  );
}

// ─── Rule Form Modal ──────────────────────────────────────────────────────────

function RuleFormModal({
  rule,
  templates,
  onClose,
  onSave,
}: {
  rule?: AutomationRule | null;
  templates: YCloudTemplate[];
  onClose: () => void;
  onSave: () => void;
}) {
  const isEdit = !!rule;
  const isSystem = rule?.is_system ?? false;

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

  // Detectar variables {{N}} de la template seleccionada
  const selectedTemplate = templates.find(t => t.name === templateName);
  const bodyComp = selectedTemplate?.components?.find(c => c.type === 'BODY');
  const bodyText = bodyComp?.text ?? '';
  const varMatches = bodyText.match(/\{\{(\d+)\}\}/g) ?? [];

  const handleChannelToggle = (ch: string) => {
    setChannels(prev =>
      prev.includes(ch) ? prev.filter(c => c !== ch) : [...prev, ch]
    );
  };

  const handleSave = async () => {
    if (!name.trim()) { setError('El nombre es obligatorio.'); return; }
    if (messageType === 'free_text' && !freeText.trim()) { setError('El mensaje de texto libre es obligatorio.'); return; }
    if (messageType === 'hsm' && !templateName) { setError('Seleccioná una plantilla HSM.'); return; }

    setSaving(true);
    setError('');
    try {
      const payload = {
        name,
        trigger_type: triggerType,
        condition_json: conditionJson,
        message_type: messageType,
        free_text_message: messageType === 'free_text' ? freeText : null,
        ycloud_template_name: messageType === 'hsm' ? templateName : null,
        ycloud_template_lang: 'es',
        ycloud_template_vars: messageType === 'hsm' ? templateVars : {},
        channels,
        send_hour_min: sendHourMin,
        send_hour_max: sendHourMax,
      };

      if (isEdit && rule) {
        await api.patch(`/admin/automations/rules/${rule.id}`, payload);
      } else {
        await api.post('/admin/automations/rules', payload);
      }
      onSave();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? 'Error al guardar la regla.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(0,0,0,0.55)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '24px',
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: '#1e2533', borderRadius: '16px', width: '100%', maxWidth: '620px',
        maxHeight: '90vh', overflowY: 'auto',
        border: '1px solid rgba(255,255,255,0.1)',
        boxShadow: '0 25px 60px rgba(0,0,0,0.5)',
      }}>
        {/* Header */}
        <div style={{ padding: '24px 28px 16px', borderBottom: '1px solid rgba(255,255,255,0.08)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ margin: 0, color: '#f1f5f9', fontSize: '18px', fontWeight: 700 }}>
              {isEdit ? (isSystem ? '🔒 Regla del Sistema' : '✏️ Editar Regla') : '✨ Nueva Regla'}
            </h2>
            {isSystem && <p style={{ margin: '4px 0 0', color: '#94a3b8', fontSize: '13px' }}>Las reglas del sistema solo pueden activarse o desactivarse.</p>}
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#94a3b8', fontSize: '22px', cursor: 'pointer', padding: '4px' }}>×</button>
        </div>

        <div style={{ padding: '24px 28px' }}>
          {error && (
            <div style={{ background: '#fee2e2', color: '#991b1b', padding: '10px 14px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px' }}>
              {error}
            </div>
          )}

          {/* Nombre */}
          <div style={{ marginBottom: '20px' }}>
            <label style={labelStyle}>Nombre de la regla</label>
            <input
              value={name}
              onChange={e => setName(e.target.value)}
              disabled={isSystem}
              placeholder="Ej: Seguimiento post-implante"
              style={{ ...inputStyle, opacity: isSystem ? 0.5 : 1 }}
            />
          </div>

          {/* Trigger */}
          {!isSystem && (
            <div style={{ marginBottom: '20px' }}>
              <label style={labelStyle}>¿Cuándo se activa?</label>
              <select value={triggerType} onChange={e => setTriggerType(e.target.value)} style={inputStyle}>
                <option value="appointment_reminder">Recordatorio 24h antes del turno</option>
                <option value="post_appointment_completed">45 min después de completar consulta</option>
                <option value="lead_meta_no_booking">Lead de Meta no agendó</option>
                <option value="post_treatment_followup">Seguimiento post-tratamiento</option>
                <option value="patient_reactivation">Paciente inactivo X días</option>
              </select>
            </div>
          )}

          {/* Condición dinámica */}
          {!isSystem && (triggerType === 'lead_meta_no_booking' || triggerType === 'patient_reactivation') && (
            <div style={{ marginBottom: '20px', background: 'rgba(99,102,241,0.08)', borderRadius: '10px', padding: '16px', border: '1px solid rgba(99,102,241,0.2)' }}>
              <label style={{ ...labelStyle, color: '#a5b4fc' }}>
                {triggerType === 'lead_meta_no_booking' ? 'Horas de espera sin turno' : 'Días de inactividad'}
              </label>
              <input
                type="number"
                value={triggerType === 'lead_meta_no_booking' ? (conditionJson.delay_minutes || 120) / 60 : (conditionJson.days_inactive || 90)}
                onChange={e => {
                  const v = parseInt(e.target.value);
                  setConditionJson(triggerType === 'lead_meta_no_booking'
                    ? { ...conditionJson, delay_minutes: v * 60 }
                    : { ...conditionJson, days_inactive: v });
                }}
                style={{ ...inputStyle, width: '120px' }}
              />
            </div>
          )}

          {/* Canales */}
          {!isSystem && (
            <div style={{ marginBottom: '20px' }}>
              <label style={labelStyle}>Canales</label>
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                {['whatsapp', 'instagram', 'facebook'].map(ch => (
                  <button
                    key={ch}
                    onClick={() => handleChannelToggle(ch)}
                    style={{
                      padding: '8px 16px', borderRadius: '8px', cursor: 'pointer',
                      fontSize: '14px', fontWeight: 600, transition: 'all 0.2s',
                      border: channels.includes(ch) ? '2px solid #6366f1' : '2px solid rgba(255,255,255,0.1)',
                      background: channels.includes(ch) ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.04)',
                      color: channels.includes(ch) ? '#818cf8' : '#94a3b8',
                    }}
                  >
                    {CHANNEL_ICONS[ch]} {ch.charAt(0).toUpperCase() + ch.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Tipo de mensaje */}
          {!isSystem && (
            <>
              <div style={{ marginBottom: '20px' }}>
                <label style={labelStyle}>Tipo de mensaje</label>
                <div style={{ display: 'flex', gap: '10px' }}>
                  {['free_text', 'hsm'].map(type => (
                    <button
                      key={type}
                      onClick={() => setMessageType(type as 'free_text' | 'hsm')}
                      style={{
                        flex: 1, padding: '12px', borderRadius: '10px', cursor: 'pointer',
                        border: messageType === type ? '2px solid #6366f1' : '2px solid rgba(255,255,255,0.1)',
                        background: messageType === type ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.03)',
                        color: messageType === type ? '#a5b4fc' : '#94a3b8',
                        fontWeight: 600, fontSize: '14px', transition: 'all 0.2s',
                      }}
                    >
                      {type === 'free_text' ? '💬 Texto libre' : '📋 Plantilla HSM'}
                    </button>
                  ))}
                </div>
                {messageType === 'free_text' && (
                  <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Gratuito · Solo dentro de ventana de 24h de WhatsApp
                  </p>
                )}
                {messageType === 'hsm' && (
                  <p style={{ margin: '6px 0 0', fontSize: '12px', color: '#64748b' }}>
                    Plantilla aprobada por Meta · Costo por envío · Funciona fuera de la ventana de 24h
                  </p>
                )}
              </div>

              {messageType === 'free_text' && (
                <div style={{ marginBottom: '20px' }}>
                  <label style={labelStyle}>Mensaje</label>
                  <p style={{ margin: '0 0 8px', fontSize: '12px', color: '#64748b' }}>
                    Variables: {'{{first_name}}'} {'{{appointment_time}}'} {'{{treatment_name}}'} {'{{clinic_name}}'}
                  </p>
                  <textarea
                    value={freeText}
                    onChange={e => setFreeText(e.target.value)}
                    rows={4}
                    placeholder="Hola {{first_name}}, te recordamos tu turno mañana a las {{appointment_time}}..."
                    style={{ ...inputStyle, resize: 'vertical', minHeight: '100px' }}
                  />
                </div>
              )}

              {messageType === 'hsm' && (
                <div style={{ marginBottom: '20px' }}>
                  <label style={labelStyle}>Seleccionar plantilla HSM</label>
                  {templates.length === 0 ? (
                    <div style={{ padding: '14px', background: 'rgba(245,158,11,0.1)', borderRadius: '8px', color: '#fbbf24', fontSize: '13px' }}>
                      ⚠️ No se encontraron plantillas aprobadas. Verificá la configuración de YCLOUD_API_KEY.
                    </div>
                  ) : (
                    <select value={templateName} onChange={e => setTemplateName(e.target.value)} style={inputStyle}>
                      <option value="">— Elegí una plantilla —</option>
                      {templates.map(t => (
                        <option key={t.name} value={t.name}>
                          {t.name} · {t.language} · {t.category}
                        </option>
                      ))}
                    </select>
                  )}

                  {/* Preview de la template seleccionada */}
                  {bodyText && (
                    <div style={{ marginTop: '12px', background: 'rgba(255,255,255,0.04)', borderRadius: '10px', padding: '14px', border: '1px solid rgba(255,255,255,0.08)' }}>
                      <p style={{ margin: '0 0 8px', fontSize: '12px', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Preview</p>
                      <p style={{ margin: 0, color: '#cbd5e1', fontSize: '14px', lineHeight: '1.5', whiteSpace: 'pre-wrap' }}>{bodyText}</p>
                    </div>
                  )}

                  {/* Mapeo de variables */}
                  {varMatches.length > 0 && (
                    <div style={{ marginTop: '16px' }}>
                      <label style={{ ...labelStyle, marginBottom: '8px' }}>Mapeo de variables</label>
                      <p style={{ margin: '0 0 12px', fontSize: '12px', color: '#64748b' }}>
                        Asigná cada variable de la plantilla a un campo de datos del paciente.
                      </p>
                      {varMatches.map(v => {
                        const key = v; // "{{1}}", "{{2}}", etc.
                        return (
                          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '10px' }}>
                            <span style={{
                              width: '50px', textAlign: 'center', padding: '8px', borderRadius: '6px',
                              background: 'rgba(99,102,241,0.15)', color: '#818cf8', fontSize: '13px', fontWeight: 700,
                            }}>{key}</span>
                            <span style={{ color: '#64748b', fontSize: '16px' }}>→</span>
                            <select
                              value={templateVars[key] ?? ''}
                              onChange={e => setTemplateVars(prev => ({ ...prev, [key]: e.target.value }))}
                              style={{ ...inputStyle, flex: 1, marginBottom: 0 }}
                            >
                              <option value="">— Campo del paciente —</option>
                              {AVAILABLE_VARS.map(av => (
                                <option key={av.key} value={av.key}>{av.label}</option>
                              ))}
                            </select>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Horario de envío */}
          {!isSystem && (
            <div style={{ marginBottom: '28px' }}>
              <label style={labelStyle}>Horario de envío</label>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontSize: '12px', color: '#64748b' }}>Desde</span>
                  <input type="number" min={0} max={23} value={sendHourMin} onChange={e => setSendHourMin(Number(e.target.value))} style={{ ...inputStyle, width: '80px', marginBottom: 0 }} />
                </div>
                <span style={{ color: '#64748b', marginTop: '18px' }}>–</span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <span style={{ fontSize: '12px', color: '#64748b' }}>Hasta</span>
                  <input type="number" min={0} max={23} value={sendHourMax} onChange={e => setSendHourMax(Number(e.target.value))} style={{ ...inputStyle, width: '80px', marginBottom: 0 }} />
                </div>
                <span style={{ color: '#64748b', marginTop: '18px', fontSize: '13px' }}>hs (horario clínica)</span>
              </div>
            </div>
          )}

          {/* Botones */}
          <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
            <button onClick={onClose} style={btnSecondaryStyle}>Cancelar</button>
            <button onClick={handleSave} disabled={saving || isSystem} style={{ ...btnPrimaryStyle, opacity: saving || isSystem ? 0.6 : 1 }}>
              {saving ? '⏳ Guardando...' : isEdit ? '💾 Guardar cambios' : '✨ Crear regla'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function MetaTemplatesView() {
  const [activeTab, setActiveTab] = useState<'rules' | 'logs' | 'templates'>('rules');
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [logs, setLogs] = useState<AutomationLog[]>([]);
  const [templates, setTemplates] = useState<YCloudTemplate[]>([]);
  const [stats, setStats] = useState({ hsm_sent: 0, delivery_rate: 0, active_rules: 0 });
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingRule, setEditingRule] = useState<AutomationRule | null>(null);

  // Filtros de logs
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
    } catch (e) { console.error('Error cargando reglas:', e); }
  }, []);

  const loadLogs = useCallback(async () => {
    try {
      const params: any = { page: logPage, limit: 50 };
      if (filterTrigger) params.trigger_type = filterTrigger;
      if (filterStatus) params.status = filterStatus;
      if (filterChannel) params.channel = filterChannel;
      if (filterDateFrom) params.date_from = filterDateFrom;
      if (filterDateTo) params.date_to = filterDateTo;
      const { data } = await api.get('/admin/automations/logs', { params });
      setLogs(data.logs || []);
      setLogTotal(data.total || 0);
      setLogPages(data.pages || 1);

      // Calcular stats desde logs del día
      const todayLogs = (data.logs || []).filter((l: AutomationLog) => {
        const d = new Date(l.triggered_at);
        const today = new Date();
        return d.getDate() === today.getDate() && d.getMonth() === today.getMonth();
      });
      const sent = todayLogs.filter((l: AutomationLog) => l.status === 'sent' || l.status === 'delivered').length;
      const delivered = todayLogs.filter((l: AutomationLog) => l.status === 'delivered').length;
      const rate = sent > 0 ? Math.round((delivered / sent) * 100) : 0;
      setStats(prev => ({ ...prev, hsm_sent: sent, delivery_rate: rate }));
    } catch (e) { console.error('Error cargando logs:', e); }
  }, [logPage, filterTrigger, filterStatus, filterChannel, filterDateFrom, filterDateTo]);

  const loadTemplates = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/automations/ycloud-templates');
      setTemplates(data.templates || []);
    } catch (e) { console.error('Error cargando templates:', e); }
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await Promise.all([loadRules(), loadLogs(), loadTemplates()]);
      setLoading(false);
    };
    init();
  }, []);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  const handleToggleRule = async (rule: AutomationRule) => {
    try {
      await api.patch(`/admin/automations/rules/${rule.id}/toggle`);
      await loadRules();
    } catch (e) { console.error('Error toggling rule:', e); }
  };

  const handleDeleteRule = async (rule: AutomationRule) => {
    if (!confirm(`¿Eliminar la regla "${rule.name}"? Esta acción no se puede deshacer.`)) return;
    try {
      await api.delete(`/admin/automations/rules/${rule.id}`);
      await loadRules();
    } catch (e: any) {
      alert(e?.response?.data?.detail ?? 'Error al eliminar.');
    }
  };

  const systemRules = rules.filter(r => r.is_system);
  const customRules = rules.filter(r => !r.is_system);

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '40px', marginBottom: '12px' }}>⚙️</div>
          <p>Cargando Motor de Automatización...</p>
        </div>
      </div>
    );
  }

  return (
    <div style={{ height: '100%', overflowY: 'auto', background: '#0f1623', padding: '28px 32px' }}>
      {/* Header */}
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ margin: '0 0 4px', color: '#f1f5f9', fontSize: '24px', fontWeight: 800 }}>
          Automatizaciones & HSM
        </h1>
        <p style={{ margin: 0, color: '#64748b', fontSize: '15px' }}>Motor de Reglas · Seguimientos · WhatsApp Marketing</p>
      </div>

      {/* Stats Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '16px', marginBottom: '28px' }}>
        <StatCard icon="📤" label="Enviados hoy" value={stats.hsm_sent} color="#6366f1" />
        <StatCard icon="📬" label="Tasa de entrega" value={`${stats.delivery_rate}%`} color="#10b981" />
        <StatCard icon="⚡" label="Reglas activas" value={stats.active_rules} color="#f59e0b" />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '4px', background: 'rgba(255,255,255,0.04)', borderRadius: '12px', padding: '4px', marginBottom: '24px', width: 'fit-content' }}>
        {(['rules', 'logs', 'templates'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              padding: '9px 20px', borderRadius: '9px', border: 'none', cursor: 'pointer',
              fontSize: '14px', fontWeight: 600, transition: 'all 0.2s',
              background: activeTab === tab ? '#6366f1' : 'transparent',
              color: activeTab === tab ? '#fff' : '#64748b',
            }}
          >
            {tab === 'rules' ? '⚡ Reglas' : tab === 'logs' ? '📋 Logs' : '🗂️ Plantillas YCloud'}
          </button>
        ))}
      </div>

      {/* ── TAB: REGLAS ── */}
      {activeTab === 'rules' && (
        <div>
          {/* Sistema */}
          <div style={{ marginBottom: '28px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
              <div style={{ width: '4px', height: '20px', background: '#6366f1', borderRadius: '2px' }} />
              <h2 style={{ margin: 0, color: '#f1f5f9', fontSize: '16px', fontWeight: 700 }}>Reglas del Sistema</h2>
              <span style={{ padding: '2px 8px', background: 'rgba(99,102,241,0.15)', color: '#818cf8', borderRadius: '6px', fontSize: '12px', fontWeight: 600 }}>No editables</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {systemRules.map(rule => (
                <RuleCard
                  key={rule.id}
                  rule={rule}
                  onToggle={() => handleToggleRule(rule)}
                  onEdit={() => { setEditingRule(rule); setShowModal(true); }}
                  onDelete={null}
                />
              ))}
              {systemRules.length === 0 && (
                <div style={{ color: '#64748b', fontSize: '14px', padding: '16px', background: 'rgba(255,255,255,0.03)', borderRadius: '10px' }}>
                  Las reglas de sistema se crearán automáticamente al reiniciar el servidor.
                </div>
              )}
            </div>
          </div>

          {/* Personalizadas */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div style={{ width: '4px', height: '20px', background: '#10b981', borderRadius: '2px' }} />
                <h2 style={{ margin: 0, color: '#f1f5f9', fontSize: '16px', fontWeight: 700 }}>Reglas Personalizadas</h2>
              </div>
              <button
                onClick={() => { setEditingRule(null); setShowModal(true); }}
                style={btnPrimaryStyle}
              >
                + Nueva Regla
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {customRules.map(rule => (
                <RuleCard
                  key={rule.id}
                  rule={rule}
                  onToggle={() => handleToggleRule(rule)}
                  onEdit={() => { setEditingRule(rule); setShowModal(true); }}
                  onDelete={() => handleDeleteRule(rule)}
                />
              ))}
              {customRules.length === 0 && (
                <div style={{
                  padding: '40px', borderRadius: '14px', border: '2px dashed rgba(255,255,255,0.08)',
                  textAlign: 'center', color: '#64748b',
                }}>
                  <div style={{ fontSize: '36px', marginBottom: '12px' }}>⚡</div>
                  <p style={{ margin: '0 0 16px', fontSize: '15px' }}>Aún no tenés reglas personalizadas.</p>
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
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '20px', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', padding: '16px', border: '1px solid rgba(255,255,255,0.07)' }}>
            <select value={filterTrigger} onChange={e => { setFilterTrigger(e.target.value); setLogPage(1); }} style={{ ...inputStyle, margin: 0, flex: '1 1 160px', minWidth: '160px' }}>
              <option value="">Todos los triggers</option>
              {Object.entries(TRIGGER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setLogPage(1); }} style={{ ...inputStyle, margin: 0, flex: '1 1 140px', minWidth: '140px' }}>
              <option value="">Todos los estados</option>
              <option value="sent">Enviado</option>
              <option value="delivered">Entregado</option>
              <option value="failed">Fallido</option>
              <option value="skipped">Omitido</option>
              <option value="pending">Pendiente</option>
            </select>
            <select value={filterChannel} onChange={e => { setFilterChannel(e.target.value); setLogPage(1); }} style={{ ...inputStyle, margin: 0, flex: '1 1 130px', minWidth: '130px' }}>
              <option value="">Todos los canales</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
              <option value="system">Sistema</option>
            </select>
            <input type="date" value={filterDateFrom} onChange={e => { setFilterDateFrom(e.target.value); setLogPage(1); }} style={{ ...inputStyle, margin: 0, flex: '1 1 140px', minWidth: '140px' }} />
            <input type="date" value={filterDateTo} onChange={e => { setFilterDateTo(e.target.value); setLogPage(1); }} style={{ ...inputStyle, margin: 0, flex: '1 1 140px', minWidth: '140px' }} />
            <button onClick={() => { setFilterTrigger(''); setFilterStatus(''); setFilterChannel(''); setFilterDateFrom(''); setFilterDateTo(''); setLogPage(1); }} style={{ ...btnSecondaryStyle, margin: 0 }}>
              Limpiar
            </button>
          </div>

          {/* Tabla de logs */}
          <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.07)', overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                    {['Paciente', 'Trigger', 'Canal', 'Mensaje', 'Fecha/Hora', 'Estado'].map(h => (
                      <th key={h} style={{ padding: '12px 16px', textAlign: 'left', color: '#64748b', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid rgba(255,255,255,0.07)', whiteSpace: 'nowrap' }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {logs.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ padding: '48px', textAlign: 'center', color: '#64748b' }}>
                        <div style={{ fontSize: '32px', marginBottom: '8px' }}>📋</div>
                        <p style={{ margin: 0 }}>No hay logs disponibles con los filtros actuales.</p>
                      </td>
                    </tr>
                  )}
                  {logs.map((log, idx) => (
                    <tr key={log.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)', background: idx % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.01)', transition: 'background 0.15s' }}>
                      <td style={{ padding: '13px 16px' }}>
                        <div style={{ color: '#e2e8f0', fontSize: '14px', fontWeight: 600 }}>{log.patient_name || '—'}</div>
                        <div style={{ color: '#64748b', fontSize: '12px' }}>{log.phone_number || ''}</div>
                      </td>
                      <td style={{ padding: '13px 16px' }}>
                        <TriggerBadge type={log.trigger_type} />
                        {log.rule_name && <div style={{ color: '#64748b', fontSize: '11px', marginTop: '3px' }}>{log.rule_name}</div>}
                      </td>
                      <td style={{ padding: '13px 16px', color: '#94a3b8', fontSize: '14px' }}>
                        {CHANNEL_ICONS[log.channel || 'whatsapp']} {log.channel || 'whatsapp'}
                      </td>
                      <td style={{ padding: '13px 16px', maxWidth: '220px' }}>
                        <div style={{ color: '#94a3b8', fontSize: '13px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {log.message_preview || log.template_name || '—'}
                        </div>
                        {log.skip_reason && <div style={{ color: '#f59e0b', fontSize: '11px', marginTop: '2px' }}>⏭ {log.skip_reason}</div>}
                        {log.error_details && <div style={{ color: '#ef4444', fontSize: '11px', marginTop: '2px' }}>❌ {log.error_details}</div>}
                      </td>
                      <td style={{ padding: '13px 16px', color: '#64748b', fontSize: '13px', whiteSpace: 'nowrap' }}>
                        {new Date(log.triggered_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td style={{ padding: '13px 16px' }}>
                        <StatusBadge status={log.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Paginación */}
            {logPages > 1 && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', borderTop: '1px solid rgba(255,255,255,0.07)' }}>
                <span style={{ color: '#64748b', fontSize: '13px' }}>
                  {logTotal} registros · Página {logPage} de {logPages}
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button disabled={logPage <= 1} onClick={() => setLogPage(p => p - 1)} style={{ ...btnSecondaryStyle, padding: '6px 14px', opacity: logPage <= 1 ? 0.4 : 1 }}>‹ Anterior</button>
                  <button disabled={logPage >= logPages} onClick={() => setLogPage(p => p + 1)} style={{ ...btnSecondaryStyle, padding: '6px 14px', opacity: logPage >= logPages ? 0.4 : 1 }}>Siguiente ›</button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── TAB: PLANTILLAS YCLOUD ── */}
      {activeTab === 'templates' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '20px' }}>
            <div>
              <h2 style={{ margin: '0 0 4px', color: '#f1f5f9', fontSize: '16px', fontWeight: 700 }}>Plantillas HSM de YCloud</h2>
              <p style={{ margin: 0, color: '#64748b', fontSize: '13px' }}>Solo se muestran plantillas con estado APPROVED. Solo lectura.</p>
            </div>
            <button onClick={loadTemplates} style={btnSecondaryStyle}>🔄 Actualizar</button>
          </div>

          {templates.length === 0 ? (
            <div style={{ padding: '60px', textAlign: 'center', color: '#64748b', background: 'rgba(255,255,255,0.03)', borderRadius: '14px', border: '1px solid rgba(255,255,255,0.07)' }}>
              <div style={{ fontSize: '40px', marginBottom: '12px' }}>📭</div>
              <p style={{ margin: '0 0 8px', fontSize: '15px' }}>No se encontraron plantillas aprobadas.</p>
              <p style={{ margin: 0, fontSize: '13px' }}>Verificá que YCLOUD_API_KEY esté configurada correctamente en el servidor.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
              {templates.map(t => {
                const body = t.components?.find(c => c.type === 'BODY');
                const catColors = { MARKETING: '#f59e0b', UTILITY: '#6366f1', AUTHENTICATION: '#10b981' } as const;
                const catColor = catColors[t.category as keyof typeof catColors] || '#64748b';
                return (
                  <div key={t.name} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: '12px', padding: '18px', border: '1px solid rgba(255,255,255,0.08)', transition: 'border-color 0.2s' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                      <div>
                        <p style={{ margin: '0 0 4px', color: '#e2e8f0', fontSize: '14px', fontWeight: 700 }}>{t.name}</p>
                        <span style={{ fontSize: '12px', color: '#64748b' }}>{t.language}</span>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', alignItems: 'flex-end' }}>
                        <span style={{ padding: '2px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700, background: catColor + '22', color: catColor }}>{t.category}</span>
                        <span style={{ padding: '2px 8px', borderRadius: '6px', fontSize: '11px', fontWeight: 700, background: '#d1fae522', color: '#10b981' }}>✅ APPROVED</span>
                      </div>
                    </div>
                    {body?.text && (
                      <p style={{ margin: 0, color: '#94a3b8', fontSize: '13px', lineHeight: '1.5', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
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
          onClose={() => { setShowModal(false); setEditingRule(null); }}
          onSave={async () => { setShowModal(false); setEditingRule(null); await loadRules(); }}
        />
      )}
    </div>
  );
}

// ─── Rule Card ────────────────────────────────────────────────────────────────

function RuleCard({
  rule,
  onToggle,
  onEdit,
  onDelete,
}: {
  rule: AutomationRule;
  onToggle: () => void;
  onEdit: () => void;
  onDelete: (() => void) | null;
}) {
  const triggerColor = TRIGGER_COLORS[rule.trigger_type] || '#64748b';
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)',
      borderRadius: '12px',
      padding: '16px 20px',
      border: `1px solid ${rule.is_active ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.07)'}`,
      display: 'flex',
      alignItems: 'center',
      gap: '16px',
      transition: 'border-color 0.2s',
    }}>
      {/* Toggle */}
      <div
        onClick={onToggle}
        style={{
          width: '40px', height: '24px', borderRadius: '12px',
          background: rule.is_active ? '#6366f1' : 'rgba(255,255,255,0.1)',
          position: 'relative', cursor: 'pointer', flexShrink: 0, transition: 'background 0.2s',
        }}
      >
        <div style={{
          position: 'absolute', top: '3px',
          left: rule.is_active ? '19px' : '3px',
          width: '18px', height: '18px', borderRadius: '50%',
          background: '#fff', transition: 'left 0.2s',
          boxShadow: '0 1px 4px rgba(0,0,0,0.3)',
        }} />
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ color: '#f1f5f9', fontSize: '15px', fontWeight: 700 }}>{rule.name}</span>
          {rule.is_system && (
            <span style={{ padding: '1px 7px', borderRadius: '5px', fontSize: '11px', fontWeight: 700, background: 'rgba(99,102,241,0.15)', color: '#818cf8' }}>🔒 Sistema</span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px', marginTop: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
          <TriggerBadge type={rule.trigger_type} />
          <span style={{ color: '#64748b', fontSize: '12px' }}>
            {rule.message_type === 'hsm' ? `📋 HSM: ${rule.ycloud_template_name}` : '💬 Texto libre'}
          </span>
          {rule.channels.map(ch => (
            <span key={ch} style={{ color: '#64748b', fontSize: '12px' }}>{CHANNEL_ICONS[ch]}</span>
          ))}
          <span style={{ color: '#475569', fontSize: '12px' }}>
            {rule.send_hour_min}:00 – {rule.send_hour_max}:00 hs
          </span>
        </div>
      </div>

      {/* Acciones */}
      <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
        <button onClick={onEdit} title={rule.is_system ? 'Ver detalles' : 'Editar'} style={{ ...btnSecondaryStyle, padding: '7px 12px', fontSize: '14px' }}>
          {rule.is_system ? '👁️' : '✏️'}
        </button>
        {onDelete && (
          <button onClick={onDelete} title="Eliminar" style={{ ...btnSecondaryStyle, padding: '7px 12px', fontSize: '14px', color: '#ef4444' }}>
            🗑️
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({ icon, label, value, color }: { icon: string; label: string; value: any; color: string }) {
  return (
    <div style={{
      background: 'rgba(255,255,255,0.04)', borderRadius: '14px', padding: '20px 24px',
      border: `1px solid ${color}33`,
      display: 'flex', alignItems: 'center', gap: '16px',
    }}>
      <div style={{ fontSize: '28px', width: '48px', height: '48px', borderRadius: '12px', background: color + '22', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {icon}
      </div>
      <div>
        <div style={{ color: '#f1f5f9', fontSize: '26px', fontWeight: 800, lineHeight: 1 }}>{value}</div>
        <div style={{ color: '#64748b', fontSize: '13px', marginTop: '4px' }}>{label}</div>
      </div>
    </div>
  );
}

// ─── Shared Styles ────────────────────────────────────────────────────────────

const labelStyle: React.CSSProperties = {
  display: 'block', marginBottom: '8px',
  color: '#e2e8f0', fontSize: '13px', fontWeight: 600,
};

const inputStyle: React.CSSProperties = {
  display: 'block', width: '100%', boxSizing: 'border-box',
  padding: '10px 14px', borderRadius: '9px',
  background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
  color: '#f1f5f9', fontSize: '14px', marginBottom: '0',
  outline: 'none',
};

const btnPrimaryStyle: React.CSSProperties = {
  padding: '10px 20px', borderRadius: '9px', border: 'none', cursor: 'pointer',
  background: 'linear-gradient(135deg,#6366f1,#8b5cf6)',
  color: '#fff', fontSize: '14px', fontWeight: 700,
  boxShadow: '0 4px 14px rgba(99,102,241,0.35)', transition: 'all 0.2s',
};

const btnSecondaryStyle: React.CSSProperties = {
  padding: '10px 16px', borderRadius: '9px', cursor: 'pointer',
  background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
  color: '#94a3b8', fontSize: '14px', fontWeight: 600, transition: 'all 0.2s',
};
