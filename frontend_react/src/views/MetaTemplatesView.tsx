import React, { useState, useEffect, useCallback } from 'react';
import { 
  Smartphone, Instagram, Facebook, Settings, AlertCircle, CheckCircle2, 
  Clock, SkipForward, Send, UserCheck, Zap, Pencil, Trash2, Plus, 
  Lock, Files, MessageSquare, RefreshCw, X, Eye, Inbox
} from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
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
  appointment_reminder: 'meta_templates.triggers.appointment_reminder',
  post_appointment_completed: 'meta_templates.triggers.post_appointment_completed',
  lead_meta_no_booking: 'meta_templates.triggers.lead_meta_no_booking',
  post_treatment_followup: 'meta_templates.triggers.post_treatment_followup',
  patient_reactivation: 'meta_templates.triggers.patient_reactivation',
  appointment_status_change: 'meta_templates.triggers.appointment_status_change',
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
  sent:      { bg: 'rgba(16,185,129,0.12)', text: '#34d399' },
  delivered: { bg: 'rgba(59,130,246,0.12)', text: '#60a5fa' },
  read:      { bg: 'rgba(99,102,241,0.12)', text: '#818cf8' },
  failed:    { bg: 'rgba(239,68,68,0.12)', text: '#f87171' },
  skipped:   { bg: 'rgba(245,158,11,0.12)', text: '#fbbf24' },
  pending:   { bg: 'rgba(255,255,255,0.06)', text: 'rgba(255,255,255,0.5)' },
};

const CHANNEL_ICONS: Record<string, any> = {
  whatsapp: <Smartphone size={14} />,
  instagram: <Instagram size={14} />,
  facebook: <Facebook size={14} />,
  system: <Settings size={14} />,
};

const AVAILABLE_VARS = [
  { key: 'first_name', label: 'meta_templates.variables.first_name' },
  { key: 'last_name', label: 'meta_templates.variables.last_name' },
  { key: 'appointment_date', label: 'meta_templates.variables.appointment_date' },
  { key: 'appointment_time', label: 'meta_templates.variables.appointment_time' },
  { key: 'treatment_name', label: 'meta_templates.variables.treatment_name' },
  { key: 'clinic_name', label: 'meta_templates.variables.clinic_name' },
  { key: 'professional_name', label: 'meta_templates.variables.professional_name' },
];

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation();
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
      {status === 'sent' ? t('meta_templates.statuses.sent') :
       status === 'delivered' ? t('meta_templates.statuses.delivered') :
       status === 'read' ? t('meta_templates.statuses.read') :
       status === 'failed' ? t('meta_templates.statuses.failed') :
       status === 'skipped' ? t('meta_templates.statuses.skipped') : 
       status === 'pending' ? t('meta_templates.statuses.pending') : status}
    </span>
  );
}

function TriggerBadge({ type }: { type: string }) {
  const { t } = useTranslation();
  const color = TRIGGER_COLORS[type] || '#64748b';
  return (
    <span style={{
      display: 'inline-block', padding: '2px 10px', borderRadius: '9999px',
      fontSize: '12px', fontWeight: 600,
      background: color + '18', color: color, border: `1px solid ${color}33`,
    }}>
      {TRIGGER_LABELS[type] ? t(TRIGGER_LABELS[type]) : type}
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
  const { t } = useTranslation();
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
  const [schedule, setSchedule] = useState({
    start_time: rule?.send_hour_min != null ? `${String(rule.send_hour_min).padStart(2, '0')}:00` : '08:00',
    end_time: rule?.send_hour_max != null ? `${String(rule.send_hour_max).padStart(2, '0')}:00` : '20:00',
  });
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
    if (!name.trim()) { setError(t('meta_templates.form.name_required')); return; }
    if (messageType === 'free_text' && !freeText.trim()) { setError(t('meta_templates.form.message_required')); return; }
    if (messageType === 'hsm' && !templateName) { setError(t('meta_templates.form.template_required')); return; }
    setSaving(true); setError('');
    try {
      const [hMin] = schedule.start_time.split(':').map(Number);
      const [hMax] = schedule.end_time.split(':').map(Number);
      const payload = {
        name, trigger_type: triggerType, condition_json: conditionJson,
        message_type: messageType,
        free_text_message: messageType === 'free_text' ? freeText : null,
        ycloud_template_name: messageType === 'hsm' ? templateName : null,
        ycloud_template_lang: 'es',
        ycloud_template_vars: messageType === 'hsm' ? templateVars : {},
        channels, send_hour_min: hMin, send_hour_max: hMax,
      };
      if (isEdit && rule) await api.patch(`/admin/automations/rules/${rule.id}`, payload);
      else await api.post('/admin/automations/rules', payload);
      onSave();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? t('meta_templates.form.error_saving'));
    } finally { setSaving(false); }
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: 'rgba(15,23,42,0.5)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '24px',
    }} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{
        background: '#0d1117', borderRadius: isMobile ? '0' : '16px', width: '100%',
        maxWidth: isMobile ? '100%' : '600px',
        height: isMobile ? '100%' : 'auto',
        maxHeight: isMobile ? '100%' : '90vh', overflowY: 'auto',
        boxShadow: '0 20px 60px rgba(0,0,0,0.5)',
        border: '1px solid rgba(255,255,255,0.08)',
      }}>
        {/* Header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{ color: '#6366f1' }}>{isEdit ? icons.edit : icons.plus}</div>
            <div>
              <h2 style={{ margin: 0, color: '#fff', fontSize: '18px', fontWeight: 700 }}>
                {messageOnly ? t('meta_templates.form.edit_message') : isEdit ? t('meta_templates.form.edit_rule') : t('meta_templates.form.new_rule')}
              </h2>
              {messageOnly && <p style={{ margin: '4px 0 0', color: 'rgba(255,255,255,0.5)', fontSize: '13px' }}>{t('meta_templates.form.system_rule_hint')}</p>}
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'rgba(255,255,255,0.3)', cursor: 'pointer', display: 'flex', alignItems: 'center' }}><X size={20} /></button>
        </div>

        <div style={{ padding: '20px 24px' }}>
          {error && (
            <div style={{ background: 'rgba(239,68,68,0.12)', color: '#f87171', padding: '10px 14px', borderRadius: '8px', marginBottom: '16px', fontSize: '14px' }}>{error}</div>
          )}

          {/* Nombre */}
          <div style={{ marginBottom: '16px' }}>
            <label style={labelStyle}>{t('meta_templates.form.rule_name')}</label>
            <input value={name} onChange={(e: React.ChangeEvent<HTMLInputElement>) => setName(e.target.value)} disabled={isSystem}
              placeholder={t('meta_templates.form.rule_name_placeholder')}
              style={{ ...lightInputStyle, opacity: isSystem ? 0.6 : 1, background: isSystem ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.04)', cursor: isSystem ? 'not-allowed' : 'text' }} />
          </div>

          {/* Trigger - solo informativo para reglas de sistema */}
          {messageOnly ? (
            <div style={{ marginBottom: '16px', background: 'rgba(255,255,255,0.03)', borderRadius: '10px', padding: '12px 16px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t('meta_templates.form.trigger_when')}</span>
              <div style={{ marginTop: '4px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Lock size={12} style={{ color: 'rgba(255,255,255,0.35)' }} />
                <span style={{ color: 'rgba(255,255,255,0.8)', fontSize: '14px', fontWeight: 600 }}>{TRIGGER_LABELS[triggerType] ? t(TRIGGER_LABELS[triggerType]) : triggerType}</span>
                <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.35)' }}>{t('meta_templates.form.not_editable')}</span>
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle}>{t('meta_templates.form.trigger_label')}</label>
              <select value={triggerType} onChange={e => setTriggerType(e.target.value)} style={lightInputStyle}>
                <option value="appointment_reminder">{t('meta_templates.trigger_options.appointment_reminder')}</option>
                <option value="post_appointment_completed">{t('meta_templates.trigger_options.post_appointment_completed')}</option>
                <option value="lead_meta_no_booking">{t('meta_templates.trigger_options.lead_meta_no_booking')}</option>
                <option value="post_treatment_followup">{t('meta_templates.trigger_options.post_treatment_followup')}</option>
                <option value="patient_reactivation">{t('meta_templates.trigger_options.patient_reactivation')}</option>
              </select>
            </div>
          )}

          {/* Cond dinámica - solo si no es sistema */}
          {!messageOnly && (triggerType === 'lead_meta_no_booking' || triggerType === 'patient_reactivation') && (
            <div style={{ marginBottom: '16px', background: 'rgba(99,102,241,0.08)', borderRadius: '10px', padding: '14px', border: '1px solid rgba(99,102,241,0.2)' }}>
              <label style={{ ...labelStyle, color: '#4338ca' }}>
                {triggerType === 'lead_meta_no_booking' ? t('meta_templates.form.delay_hours') : t('meta_templates.form.delay_days')}
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
            <div style={{ marginBottom: '16px', background: 'rgba(255,255,255,0.03)', borderRadius: '10px', padding: '12px 16px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t('meta_templates.form.channels')}</span>
              <div style={{ marginTop: '4px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                {channels.map(ch => (
                  <span key={ch} style={{ padding: '4px 10px', borderRadius: '6px', background: 'rgba(99,102,241,0.15)', color: '#818cf8', fontSize: '12px', fontWeight: 600 }}>
                    {CHANNEL_ICONS[ch]} {ch}
                  </span>
                ))}
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: '16px' }}>
              <label style={labelStyle}>{t('meta_templates.form.channels')}</label>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                {['whatsapp', 'instagram', 'facebook'].map(ch => (
                  <button key={ch} onClick={() => handleChannelToggle(ch)} style={{
                    padding: '7px 14px', borderRadius: '8px', cursor: 'pointer',
                    fontSize: '14px', fontWeight: 600, transition: 'all 0.15s',
                    border: channels.includes(ch) ? '2px solid #6366f1' : '2px solid rgba(255,255,255,0.08)',
                    background: channels.includes(ch) ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.03)',
                    color: channels.includes(ch) ? '#6366f1' : '#64748b',
                  }}>
                    {CHANNEL_ICONS[ch]} {ch.charAt(0).toUpperCase() + ch.slice(1)}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Lead Recovery: panel informativo especial (mensajes generados por IA, no configurables) */}
          {isSystem && triggerType === 'lead_meta_no_booking' ? (
            <div style={{ marginBottom: '16px' }}>
              <div style={{ background: 'rgba(99,102,241,0.08)', borderRadius: '12px', padding: '16px', border: '1px solid rgba(99,102,241,0.2)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                  <Zap size={16} style={{ color: '#818cf8' }} />
                  <span style={{ fontSize: '14px', fontWeight: 700, color: '#818cf8' }}>{t('meta_templates.form.ai_messages_title')}</span>
                </div>
                <p style={{ fontSize: '12px', color: 'rgba(255,255,255,0.5)', margin: '0 0 12px', lineHeight: '1.5' }}>
                  {t('meta_templates.form.ai_messages_desc')}
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {[
                    { label: 'Touch 1 (2h)', desc: t('meta_templates.form.touch1_desc'), color: '#6366f1' },
                    { label: 'Touch 2 (8h)', desc: t('meta_templates.form.touch2_desc'), color: '#8b5cf6' },
                    { label: 'Touch 3 (18h)', desc: t('meta_templates.form.touch3_desc'), color: '#a78bfa' },
                  ].map(touch => (
                    <div key={touch.label} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', padding: '8px 12px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.04)' }}>
                      <span style={{ fontSize: '11px', fontWeight: 700, color: touch.color, minWidth: '80px', whiteSpace: 'nowrap' }}>{touch.label}</span>
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)' }}>{touch.desc}</span>
                    </div>
                  ))}
                </div>
                <p style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', margin: '12px 0 0', fontStyle: 'italic' }}>
                  {t('meta_templates.form.ai_messages_note')}
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Tipo de mensaje — editable para reglas normales */}
              <div style={{ marginBottom: '16px' }}>
                <label style={labelStyle}>{t('meta_templates.form.message_type')}</label>
                <div style={{ display: 'flex', gap: '8px' }}>
                  {(['free_text', 'hsm'] as const).map(type => (
                    <button key={type} onClick={() => setMessageType(type)} style={{
                      flex: 1, padding: '11px', borderRadius: '9px', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                      border: messageType === type ? '2px solid #6366f1' : '2px solid rgba(255,255,255,0.08)',
                      background: messageType === type ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.03)',
                      color: messageType === type ? '#6366f1' : '#64748b',
                      fontWeight: 600, fontSize: '14px', transition: 'all 0.15s',
                    }}>
                      {type === 'free_text' ? <MessageSquare size={16} /> : <Files size={16} />}
                      {type === 'free_text' ? t('meta_templates.form.free_text') : t('meta_templates.form.hsm_template')}
                    </button>
                  ))}
                </div>
                <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'rgba(255,255,255,0.35)' }}>
                  {messageType === 'free_text'
                    ? t('meta_templates.form.free_text_hint')
                    : t('meta_templates.form.hsm_hint')}
                </p>
              </div>

              {messageType === 'free_text' && (
                <div style={{ marginBottom: '16px' }}>
                  <label style={labelStyle}>{t('meta_templates.form.message')}</label>
                  <p style={{ margin: '0 0 6px', fontSize: '12px', color: 'rgba(255,255,255,0.35)' }}>
                    {t('meta_templates.form.available_vars')} {'{{first_name}}'} {'{{appointment_time}}'} {'{{treatment_name}}'} {'{{clinic_name}}'}
                  </p>
                  <textarea value={freeText} onChange={e => setFreeText(e.target.value)} rows={4}
                    placeholder={t('meta_templates.form.message_placeholder')}
                    style={{ ...lightInputStyle, resize: 'vertical', minHeight: '90px' }} />
                </div>
              )}

              {messageType === 'hsm' && (
                <div style={{ marginBottom: '16px' }}>
                  <label style={labelStyle}>{t('meta_templates.form.hsm_template')}</label>
                  {templates.length === 0 ? (
                    <div style={{ padding: '12px', background: 'rgba(245,158,11,0.1)', color: '#fbbf24', borderRadius: '8px', fontSize: '12px', border: '1px solid rgba(245,158,11,0.2)' }}>
                      {t('meta_templates.form.no_templates')}
                    </div>
                  ) : (
                    <select value={templateName} onChange={e => {
                        setTemplateName(e.target.value);
                        setTemplateVars({});
                      }}
                      style={lightInputStyle}
                    >
                      <option value="">{t('meta_templates.form.select_template')}</option>
                      {templates.map(t => <option key={t.name} value={t.name}>{t.name} · {t.language} · {t.category}</option>)}
                    </select>
                  )}
                  {selectedTemplate?.components?.find(c => c.type === 'BODY')?.text && (
                    <div style={{ marginTop: '12px', padding: '12px', background: 'rgba(255,255,255,0.04)', borderRadius: '8px', border: '1px solid rgba(255,255,255,0.08)', fontSize: '12px', color: 'rgba(255,255,255,0.5)' }}>
                      <strong style={{ color: 'rgba(255,255,255,0.6)' }}>{t('meta_templates.form.preview')}:</strong><br/>
                      {selectedTemplate.components.find(c => c.type === 'BODY')?.text}
                    </div>
                  )}
                  {varMatches.length > 0 && (
                    <div style={{ marginTop: '16px', background: 'rgba(16,185,129,0.08)', padding: '12px 16px', borderRadius: '8px', border: '1px solid rgba(16,185,129,0.2)' }}>
                      <label style={{ ...labelStyle, color: '#34d399', marginBottom: '8px' }}>{t('meta_templates.form.var_mapping')}</label>
                      {varMatches.map(v => (
                        <div key={v} style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{ fontSize: '13px', color: '#34d399', fontWeight: 600, minWidth: '40px' }}>{v}:</span>
                          <select
                            value={templateVars[v] || ''}
                            onChange={e => setTemplateVars({ ...templateVars, [v]: e.target.value })}
                            style={{ ...lightInputStyle, flex: 1, padding: '6px 10px', fontSize: '13px' }}
                          >
                            <option value="">{t('meta_templates.form.patient_field')}</option>
                            {AVAILABLE_VARS.map(opt => (
                              <option key={opt.key} value={opt.key}>{t(opt.label)}</option>
                            ))}
                          </select>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Horario - informativo para sistema */}
          {messageOnly ? (
            <div style={{ marginBottom: '24px', background: 'rgba(255,255,255,0.03)', borderRadius: '10px', padding: '12px 16px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>{t('meta_templates.form.schedule')}</span>
              <div style={{ marginTop: '4px', fontSize: '14px', color: 'rgba(255,255,255,0.8)', fontWeight: 600 }}>
                {schedule.start_time} {t('meta_templates.form.hs')} &nbsp;—&nbsp; {schedule.end_time} {t('meta_templates.form.hs')}
              </div>
            </div>
          ) : (
            <div style={{ marginBottom: '24px' }}>
              <label style={{ ...labelStyle, marginBottom: '8px' }}>{t('meta_templates.form.schedule_label')}</label>
              <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', display: 'block', marginBottom: '4px' }}>{t('meta_templates.form.from')}</span>
                  <input type="time" value={schedule.start_time} onChange={e => setSchedule({ ...schedule, start_time: e.target.value })} style={lightInputStyle} />
                </div>
                <span style={{ color: 'rgba(255,255,255,0.2)', fontWeight: 300 }}>—</span>
                <div style={{ flex: 1 }}>
                  <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', display: 'block', marginBottom: '4px' }}>{t('meta_templates.form.to')}</span>
                  <input type="time" value={schedule.end_time} onChange={e => setSchedule({ ...schedule, end_time: e.target.value })} style={lightInputStyle} />
                </div>
              </div>
            </div>
          )}

          {/* Botones */}
          <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end', paddingTop: '16px', borderTop: '1px solid rgba(255,255,255,0.06)' }}>
            <button onClick={onClose} style={btnSecondaryStyle}>{t('meta_templates.form.cancel')}</button>
            <button onClick={handleSave} disabled={saving} style={{ ...btnPrimaryStyle, opacity: saving ? 0.6 : 1, display: 'flex', alignItems: 'center', gap: '8px' }}>
              {saving ? <RefreshCw size={16} className="animate-spin" /> : icons.save}
              {saving ? t('meta_templates.form.saving') : messageOnly ? t('meta_templates.form.save_message') : isEdit ? t('meta_templates.form.save') : t('meta_templates.form.create_rule')}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Rule Card ────────────────────────────────────────────────────────────────

function RuleCard({ rule, onEdit, onDelete, onToggle }: {
  rule: AutomationRule; onToggle: () => void;
  onEdit: () => void; onDelete: (() => void) | null;
}) {
  const { t } = useTranslation();
  const triggerColor = TRIGGER_COLORS[rule.trigger_type] || '#64748b';
  return (
    <div style={{
      background: 'rgba(255,255,255,0.03)', borderRadius: '12px', padding: '14px 18px',
      border: `1px solid ${rule.is_active ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.06)'}`,
      display: 'flex', alignItems: 'center', gap: '14px',
      boxShadow: 'none',
      transition: 'box-shadow 0.15s',
    }}>
      {/* Toggle */}
      <div onClick={onToggle} style={{
        width: '38px', height: '22px', borderRadius: '11px',
        background: rule.is_active ? '#6366f1' : 'rgba(255,255,255,0.1)',
        position: 'relative', cursor: 'pointer', flexShrink: 0, transition: 'background 0.2s',
      }}>
        <div style={{
          position: 'absolute', top: '3px',
          left: rule.is_active ? '18px' : '3px',
          width: '16px', height: '16px', borderRadius: '50%',
          background: 'rgba(255,255,255,0.03)', transition: 'left 0.2s',
          boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
        }} />
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ color: '#fff', fontSize: '15px', fontWeight: 700 }}>{rule.name}</span>
          {rule.is_system && (
            <span style={{ padding: '1px 7px', borderRadius: '5px', fontSize: '11px', fontWeight: 700, background: 'rgba(99,102,241,0.15)', color: '#818cf8', display: 'flex', alignItems: 'center', gap: '3px' }}>
              <Lock size={10} /> {t('meta_templates.rules.system')}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: '8px', marginTop: '5px', flexWrap: 'wrap', alignItems: 'center' }}>
          <TriggerBadge type={rule.trigger_type} />
          <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: '12px' }}>
            {rule.message_type === 'hsm' ? `📋 ${t('meta_templates.rules.hsm_template')}: ${rule.ycloud_template_name}` : `💬 ${t('meta_templates.rules.free_text')}`}
          </span>
          {rule.channels.map(ch => (
            <span key={ch} style={{ color: 'rgba(255,255,255,0.35)', fontSize: '12px' }}>{CHANNEL_ICONS[ch]}</span>
          ))}
          <span style={{ color: 'rgba(255,255,255,0.2)', fontSize: '12px' }}>{rule.send_hour_min}:00 – {rule.send_hour_max}:00 {t('meta_templates.rules.hours')}</span>
        </div>
      </div>

      {/* Acciones */}
      <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
        <button onClick={onEdit} title={rule.is_system ? t('meta_templates.rules.view') : t('meta_templates.rules.edit')} style={iconBtnStyle}>
          {rule.is_system ? <Eye size={16} /> : <Pencil size={16} />}
        </button>
        {onDelete && (
          <button onClick={onDelete} title={t('meta_templates.rules.delete')} style={{ ...iconBtnStyle, color: '#ef4444' }}>
            <Trash2 size={16} />
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Stat Card ────────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, color }: { icon: any; label: string; value: string | number; color: string }) {
  return (
    <div className="bg-white/[0.03] rounded-2xl border border-white/[0.06] p-4 sm:p-5 flex items-center gap-4 hover:bg-white/[0.05] transition-colors">
      <div className="w-11 h-11 rounded-xl flex items-center justify-center shrink-0" style={{ background: color + '15', color }}>
        <Icon size={22} />
      </div>
      <div>
        <p className="text-2xl font-bold text-white tracking-tight leading-none">{value}</p>
        <p className="text-xs text-white/40 mt-1">{label}</p>
      </div>
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function MetaTemplatesView() {
  const { t } = useTranslation();
  const isMobile = useWindowWidth() < 768;
  const [activeTab, setActiveTab] = useState<'rules' | 'logs' | 'templates'>('rules');
  const [rules, setRules] = useState<AutomationRule[]>([]);
  const [logs, setLogs] = useState<AutomationLog[]>([]);
  const [templates, setTemplates] = useState<YCloudTemplate[]>([]);
  const [templatesWarning, setTemplatesWarning] = useState<string>('');
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
      if (data.warning) {
        setTemplatesWarning(data.warning);
        // Log diagnostic info to browser console for debugging
        if (data.diagnostic) {
          console.warn('[YCloud templates] diagnostic:', data.diagnostic);
        }
      } else {
        setTemplatesWarning('');
      }
    } catch (err: any) {
      console.error('[YCloud templates] fetch error:', err);
      setTemplatesWarning(err?.response?.data?.warning || err?.message || 'Error al cargar plantillas');
    }
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
    if (!confirm(t('meta_templates.rules.confirm_delete', { name: rule.name }))) return;
    try { await api.delete(`/admin/automations/rules/${rule.id}`); await loadRules(); }
    catch (e: any) { alert(e?.response?.data?.detail ?? t('meta_templates.rules.error_deleting')); }
  };

  const systemRules = rules.filter(r => r.is_system);
  const customRules = rules.filter(r => !r.is_system);

  // Loading solo bloquea si rules aún no cargaron
  if (rulesLoading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', background: 'rgba(255,255,255,0.04)' }}>
      <div style={{ textAlign: 'center', color: 'rgba(255,255,255,0.5)' }}>
        <RefreshCw size={32} className="animate-spin" style={{ margin: '0 auto 12px', color: '#6366f1' }} />
        <p style={{ margin: 0, fontSize: '14px', fontWeight: 500 }}>{t('meta_templates.loading_rules')}</p>
      </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-[#0a0e1a] p-4 sm:p-6 lg:p-8">
      {/* Header */}
      <PageHeader
        title={t('meta_templates.title')}
        subtitle={t('meta_templates.subtitle')}
      />

      {/* Stats — 2 columns on mobile, 3 on desktop */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 sm:gap-4 mb-6">
        <StatCard icon={Send} label={t('meta_templates.stats.sent')} value={stats.sent} color="#6366f1" />
        <StatCard icon={UserCheck} label={t('meta_templates.stats.delivery_rate')} value={`${stats.delivery_rate}%`} color="#10b981" />
        <StatCard icon={Zap} label={t('meta_templates.stats.active_rules')} value={stats.active_rules} color="#f59e0b" />
      </div>

      {/* Tabs */}
      <div className="flex gap-0.5 bg-white/[0.06] rounded-xl p-1 mb-6 w-full sm:w-fit overflow-hidden">
        {(['rules', 'logs', 'templates'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-[13px] font-semibold transition-all whitespace-nowrap ${
              activeTab === tab
                ? 'bg-white/[0.1] text-indigo-400'
                : 'text-white/40 hover:text-white/60'
            }`}
          >
            {tab === 'rules' ? <Zap size={14} /> : tab === 'logs' ? <MessageSquare size={14} /> : <Files size={14} />}
            {tab === 'rules' ? t('meta_templates.tabs.rules') : tab === 'logs' ? t('meta_templates.tabs.logs') : t('meta_templates.tabs.templates')}
          </button>
        ))}
      </div>

      {/* ── TAB: REGLAS ── */}
      {activeTab === 'rules' && (
        <div>
          {/* Reglas Sistema */}
          <div style={{ marginBottom: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
              <Zap size={18} style={{ color: '#6366f1' }} />
              <h2 style={{ margin: 0, color: '#fff', fontSize: '15px', fontWeight: 700 }}>{t('meta_templates.rules.system_rules')}</h2>
              <span style={{ padding: '1px 8px', background: 'rgba(99,102,241,0.15)', color: '#818cf8', borderRadius: '6px', fontSize: '11px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Lock size={10} /> {t('meta_templates.form.not_editable')}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {systemRules.map(rule => (
                <RuleCard key={rule.id} rule={rule} onToggle={() => handleToggleRule(rule)}
                  onEdit={() => { setEditingRule(rule); setShowModal(true); }} onDelete={null} />
              ))}
              {systemRules.length === 0 && (
                <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: '13px', padding: '14px', background: 'rgba(255,255,255,0.03)', borderRadius: '10px', border: '1px solid rgba(255,255,255,0.06)' }}>
                  {t('meta_templates.rules.system_auto_created')}
                </div>
              )}
            </div>
          </div>

          {/* Reglas Personalizadas */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ width: '3px', height: '18px', background: '#10b981', borderRadius: '2px' }} />
                <h2 style={{ margin: 0, color: '#fff', fontSize: '15px', fontWeight: 700 }}>{t('meta_templates.rules.custom_rules')}</h2>
              </div>
              <button onClick={() => { setEditingRule(null); setShowModal(true); }} style={{ ...btnPrimaryStyle, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Plus size={16} /> {t('meta_templates.rules.new_rule_btn')}
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
                  padding: '40px', borderRadius: '12px', border: '2px dashed rgba(255,255,255,0.08)',
                  textAlign: 'center', color: 'rgba(255,255,255,0.35)', background: 'rgba(255,255,255,0.03)',
                }}>
                  <div style={{ marginBottom: '16px', color: 'rgba(255,255,255,0.1)' }}>
                    <Zap size={48} style={{ margin: '0 auto' }} />
                  </div>
                  <p style={{ margin: '0 0 14px', fontSize: '14px', fontWeight: 500 }}>{t('meta_templates.rules.no_custom_rules')}</p>
                  <button onClick={() => { setEditingRule(null); setShowModal(true); }} style={btnPrimaryStyle}>
                    {t('meta_templates.rules.create_first_rule')}
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
          <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', flexWrap: 'wrap' }}>
            <select value={filterTrigger} onChange={e => { setFilterTrigger(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 150px' }}>
              <option value="">{t('meta_templates.logs.all_triggers')}</option>
              {Object.entries(TRIGGER_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <select value={filterStatus} onChange={e => { setFilterStatus(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 130px' }}>
              <option value="">{t('meta_templates.logs.all_statuses')}</option>
              <option value="sent">{t('meta_templates.logs.status_sent')}</option>
              <option value="delivered">{t('meta_templates.logs.status_delivered')}</option>
              <option value="failed">{t('meta_templates.logs.status_failed')}</option>
              <option value="skipped">{t('meta_templates.logs.status_skipped')}</option>
            </select>
            <select value={filterChannel} onChange={e => { setFilterChannel(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 120px' }}>
              <option value="">{t('meta_templates.logs.all_channels')}</option>
              <option value="whatsapp">WhatsApp</option>
              <option value="instagram">Instagram</option>
              <option value="facebook">Facebook</option>
            </select>
            <input type="date" value={filterDateFrom} onChange={e => { setFilterDateFrom(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 130px' }} />
            <input type="date" value={filterDateTo} onChange={e => { setFilterDateTo(e.target.value); setLogPage(1); }} style={{ ...lightInputStyle, flex: '1 1 130px' }} />
            <button onClick={() => { setFilterTrigger(''); setFilterStatus(''); setFilterChannel(''); setFilterDateFrom(''); setFilterDateTo(''); setLogPage(1); }} style={btnSecondaryStyle}>
              {t('meta_templates.logs.clear_filters')}
            </button>
          </div>

          <div style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.06)', overflow: 'hidden', boxShadow: 'none' }}>
            {logsLoading ? (
              <div style={{ padding: '40px', textAlign: 'center', color: 'rgba(255,255,255,0.35)', fontSize: '14px' }}>{t('meta_templates.logs.loading_logs')}</div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr style={{ background: 'rgba(255,255,255,0.04)' }}>
                      {[t('meta_templates.logs.patient'), t('meta_templates.logs.trigger'), t('meta_templates.logs.channel'), t('meta_templates.logs.message'), t('meta_templates.logs.date_time'), t('meta_templates.logs.status')].map(h => (
                        <th key={h} style={{ padding: '11px 14px', textAlign: 'left', color: 'rgba(255,255,255,0.35)', fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid #f1f5f9', whiteSpace: 'nowrap' }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {logs.length === 0 && (
                      <tr><td colSpan={6} style={{ padding: '40px', textAlign: 'center', color: 'rgba(255,255,255,0.35)', fontSize: '14px' }}>
                        {t('meta_templates.logs.no_logs_with_filters')}
                      </td></tr>
                    )}
                    {logs.map((log, i) => (
                      <tr key={log.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.02)' }}>
                        <td style={{ padding: '12px 14px' }}>
                          <div style={{ color: '#fff', fontSize: '13px', fontWeight: 600 }}>{log.patient_name || '—'}</div>
                          <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: '11px' }}>{log.phone_number || ''}</div>
                        </td>
                        <td style={{ padding: '12px 14px' }}>
                          <TriggerBadge type={log.trigger_type} />
                          {log.rule_name && <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: '11px', marginTop: '2px' }}>{log.rule_name}</div>}
                        </td>
                        <td style={{ padding: '12px 14px', color: 'rgba(255,255,255,0.5)', fontSize: '13px' }}>
                          {CHANNEL_ICONS[log.channel || 'whatsapp']} {log.channel || 'whatsapp'}
                        </td>
                        <td style={{ padding: '12px 14px', maxWidth: '200px' }}>
                          <div style={{ color: 'rgba(255,255,255,0.5)', fontSize: '12px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {log.message_preview || log.template_name || '—'}
                          </div>
                          {log.skip_reason && <div style={{ color: '#fbbf24', fontSize: '11px', marginTop: '1px', display: 'flex', alignItems: 'center', gap: '4px' }}><SkipForward size={10} /> {log.skip_reason}</div>}
                        </td>
                        <td style={{ padding: '12px 14px', color: 'rgba(255,255,255,0.35)', fontSize: '12px', whiteSpace: 'nowrap' }}>
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
                <span style={{ color: 'rgba(255,255,255,0.35)', fontSize: '12px' }}>{logTotal} {t('meta_templates.logs.records')} · {t('meta_templates.logs.page')} {logPage} {t('meta_templates.logs.of')} {logPages}</span>
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
              <h2 style={{ margin: '0 0 2px', color: '#fff', fontSize: '15px', fontWeight: 700 }}>{t('meta_templates.templates.title')}</h2>
              <p style={{ margin: 0, color: 'rgba(255,255,255,0.35)', fontSize: '12px' }}>{t('meta_templates.templates.subtitle')}</p>
            </div>
            <button onClick={loadTemplates} style={btnSecondaryStyle}>{t('meta_templates.templates.refresh')}</button>
          </div>

          {templates.length === 0 ? (
            <div style={{ padding: '60px', textAlign: 'center', color: 'rgba(255,255,255,0.35)', background: 'rgba(255,255,255,0.03)', borderRadius: '12px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ color: 'rgba(255,255,255,0.1)', marginBottom: '16px' }}>
                <Inbox size={48} style={{ margin: '0 auto' }} />
              </div>
              <p style={{ margin: '0 0 6px', fontSize: '14px', fontWeight: 500, color: 'rgba(255,255,255,0.5)' }}>{t('meta_templates.templates.no_templates')}</p>
              {templatesWarning ? (
                <p style={{ margin: '12px auto 0', fontSize: '12px', maxWidth: '600px', color: 'rgba(245,158,11,0.9)', background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', padding: '10px 14px', borderRadius: '8px', textAlign: 'left', whiteSpace: 'pre-wrap' }}>
                  ⚠️ {templatesWarning}
                </p>
              ) : (
                <p style={{ margin: 0, fontSize: '12px' }}>{t('meta_templates.templates.verify_api_key')}</p>
              )}
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '14px' }}>
              {templates.map(t => {
                const body = t.components?.find(c => c.type === 'BODY');
                const catColors: Record<string, string> = { MARKETING: '#f59e0b', UTILITY: '#6366f1', AUTHENTICATION: '#10b981' };
                const catColor = catColors[t.category] || '#64748b';
                return (
                  <div key={t.name} style={{ background: 'rgba(255,255,255,0.03)', borderRadius: '10px', padding: '16px', border: '1px solid rgba(255,255,255,0.06)', boxShadow: 'none' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                      <div>
                        <p style={{ margin: '0 0 2px', color: '#fff', fontSize: '13px', fontWeight: 700 }}>{t.name}</p>
                        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.35)' }}>{t.language}</span>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', alignItems: 'flex-end' }}>
                        <span style={{ padding: '1px 7px', borderRadius: '5px', fontSize: '10px', fontWeight: 700, background: catColor + '18', color: catColor }}>{t.category}</span>
                        <span style={{ padding: '1px 7px', borderRadius: '5px', fontSize: '10px', fontWeight: 700, background: 'rgba(16,185,129,0.12)', color: '#34d399', display: 'flex', alignItems: 'center', gap: '3px' }}><CheckCircle2 size={10} /> APPROVED</span>
                      </div>
                    </div>
                    {body?.text && (
                      <p style={{ margin: 0, color: 'rgba(255,255,255,0.5)', fontSize: '12px', lineHeight: '1.5', display: '-webkit-box', WebkitLineClamp: 3, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
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
  color: 'rgba(255,255,255,0.7)', fontSize: '13px', fontWeight: 600,
};

// ✅ Inputs tipo light: texto oscuro, fondo blanco — no invisible
const lightInputStyle: React.CSSProperties = {
  display: 'block', width: '100%', boxSizing: 'border-box',
  padding: '9px 12px', borderRadius: '8px',
  background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
  color: '#fff', fontSize: '14px',
  outline: 'none', appearance: 'auto',
};

const btnPrimaryStyle: React.CSSProperties = {
  padding: '9px 18px', borderRadius: '8px', border: 'none', cursor: 'pointer',
  background: '#fff',
  color: '#0a0e1a', fontSize: '13px', fontWeight: 700,
  boxShadow: '0 2px 8px rgba(255,255,255,0.1)', transition: 'all 0.15s',
};

const btnSecondaryStyle: React.CSSProperties = {
  padding: '9px 14px', borderRadius: '8px', cursor: 'pointer',
  background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)',
  color: 'rgba(255,255,255,0.7)', fontSize: '13px', fontWeight: 600, transition: 'all 0.15s',
};

const iconBtnStyle: React.CSSProperties = {
  padding: '6px 10px', borderRadius: '7px', cursor: 'pointer',
  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.06)',
  color: 'rgba(255,255,255,0.5)', fontSize: '14px', transition: 'all 0.15s',
};
