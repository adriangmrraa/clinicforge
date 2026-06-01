import React, { useState, useEffect, useCallback } from 'react';
import { Zap, Layout, Clock, MessageSquare, Plus } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';
import PlaybookCard from '../components/playbooks/PlaybookCard';
import PlaybookConfigModal from '../components/playbooks/PlaybookConfigModal';

// ─── Types ────────────────────────────────────────────────────────────────────

interface Playbook {
  id: number;
  name: string;
  description?: string;
  icon?: string;
  category: string;
  trigger_type: string;
  is_active: boolean;
  is_system: boolean;
  stats_cache?: any;
  step_count?: number;
  active_executions?: number;
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

const CATEGORIES = [
  { value: 'all', label: 'Todos' },
  { value: 'retention', label: 'Retención' },
  { value: 'revenue', label: 'Ingresos' },
  { value: 'reputation', label: 'Reputación' },
  { value: 'clinical', label: 'Clínico' },
  { value: 'recovery', label: 'Recuperación' },
  { value: 'custom', label: 'Personalizado' },
];

const TRIGGER_LABELS: Record<string, string> = {
  appointment_reminder: 'Recordatorio 24h',
  post_appointment_completed: 'Post-Atención',
  lead_meta_no_booking: 'Recuperación de Leads',
  post_treatment_followup: 'Post-Tratamiento',
  patient_reactivation: 'Reactivación',
  appointment_status_change: 'Cambio de Estado',
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

// ─── Tabs ─────────────────────────────────────────────────────────────────────

type Tab = 'playbooks' | 'logs' | 'templates';

// ─── Main Component ───────────────────────────────────────────────────────────

export default function AutomationView() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<Tab>('playbooks');
  const isMobile = typeof window !== 'undefined' && window.innerWidth < 640;

  // Playbooks state
  const [playbooks, setPlaybooks] = useState<Playbook[]>([]);
  const [loadingPlaybooks, setLoadingPlaybooks] = useState(true);
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [configModal, setConfigModal] = useState<{ open: boolean; playbookId: number | null }>({ open: false, playbookId: null });

  // Logs state
  const [logs, setLogs] = useState<AutomationLog[]>([]);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [logFilter, setLogFilter] = useState('all');
  const [logPage, setLogPage] = useState(1);
  const [logTotal, setLogTotal] = useState(0);
  const LOG_PAGE_SIZE = 25;

  // Templates state
  const [templates, setTemplates] = useState<YCloudTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);

  // ── Loaders ───────────────────────────────────────────────────────────────

  const loadPlaybooks = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/playbooks');
      setPlaybooks(data.playbooks || []);
    } catch (e) {
      console.error('Error loading playbooks:', e);
    } finally {
      setLoadingPlaybooks(false);
    }
  }, []);

  const loadLogs = useCallback(async (page: number = 1) => {
    setLoadingLogs(true);
    try {
      const params: any = { page, page_size: LOG_PAGE_SIZE };
      if (logFilter !== 'all') params.trigger_type = logFilter;
      const { data } = await api.get('/admin/automations/logs', { params });
      setLogs(data.logs || []);
      setLogTotal(data.total || 0);
    } catch (e) {
      console.error('Error loading logs:', e);
    } finally {
      setLoadingLogs(false);
    }
  }, [logFilter]);

  const loadTemplates = useCallback(async () => {
    setLoadingTemplates(true);
    try {
      const { data } = await api.get('/admin/automations/ycloud-templates');
      setTemplates(data.templates || []);
    } catch (e) {
      console.error('Error loading templates:', e);
    } finally {
      setLoadingTemplates(false);
    }
  }, []);

  useEffect(() => {
    loadPlaybooks();
  }, [loadPlaybooks]);

  useEffect(() => {
    if (activeTab === 'logs') loadLogs(logPage);
  }, [activeTab, logPage, loadLogs]);

  useEffect(() => {
    if (activeTab === 'templates') loadTemplates();
  }, [activeTab, loadTemplates]);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleToggle = async (id: number) => {
    setPlaybooks(prev => prev.map(p => p.id === id ? { ...p, is_active: !p.is_active } : p));
    try {
      await api.patch(`/admin/playbooks/${id}/toggle`);
      await loadPlaybooks();
    } catch (e: any) {
      setPlaybooks(prev => prev.map(p => p.id === id ? { ...p, is_active: !p.is_active } : p));
    }
  };

  const handleConfigure = (id: number) => {
    setConfigModal({ open: true, playbookId: id });
  };

  const filteredPlaybooks = categoryFilter === 'all'
    ? playbooks
    : playbooks.filter(p => p.category === categoryFilter);

  const totalLogPages = Math.ceil(logTotal / LOG_PAGE_SIZE);

  // ── Render ────────────────────────────────────────────────────────────────

  const tabStyle = (tab: Tab): React.CSSProperties => ({
    padding: '10px 20px',
    borderRadius: '10px',
    border: 'none',
    cursor: 'pointer',
    fontSize: '14px',
    fontWeight: 600,
    background: activeTab === tab ? 'rgba(255,255,255,0.08)' : 'transparent',
    color: activeTab === tab ? '#fff' : 'rgba(255,255,255,0.4)',
    transition: 'all 0.15s',
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  });

  return (
    <div className="h-full overflow-y-auto bg-[#06060e]">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-3">
              <Zap className="text-amber-400" size={24} />
              Automatización
            </h1>
            <p className="text-sm text-white/50 mt-1">Motor de reglas, seguimientos y plantillas HSM</p>
          </div>
          {activeTab === 'playbooks' && (
            <button
              onClick={() => setConfigModal({ open: true, playbookId: null })}
              className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium flex items-center gap-2 transition-colors shrink-0"
            >
              <Plus size={18} />
              Nueva estrategia
            </button>
          )}
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-white/[0.06] pb-2">
          <button style={tabStyle('playbooks')} onClick={() => setActiveTab('playbooks')}>
            <Zap size={16} /> Estrategias
          </button>
          <button style={tabStyle('logs')} onClick={() => { setActiveTab('logs'); setLogPage(1); }}>
            <Clock size={16} /> Logs
          </button>
          <button style={tabStyle('templates')} onClick={() => setActiveTab('templates')}>
            <MessageSquare size={16} /> Plantillas YCloud
          </button>
        </div>

        {/* ── TAB: Playbooks ───────────────────────────────────── */}
        {activeTab === 'playbooks' && (
          <div className="space-y-4">
            {/* Category filter */}
            <div className="flex flex-wrap gap-1.5 items-center">
              {CATEGORIES.map(cat => (
                <button
                  key={cat.value}
                  onClick={() => setCategoryFilter(cat.value)}
                  className={`px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-colors
                    ${categoryFilter === cat.value
                      ? 'bg-white/[0.10] text-white border border-white/[0.12]'
                      : 'text-white/40 hover:text-white/60 hover:bg-white/[0.04]'
                    }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>

            {/* Playbook grid */}
            {loadingPlaybooks ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {[1, 2, 3, 4].map(i => (
                  <div key={i} className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-5 animate-pulse h-48" />
                ))}
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {filteredPlaybooks.map(pb => (
                  <PlaybookCard
                    key={pb.id}
                    playbook={pb}
                    onConfigure={handleConfigure}
                    onToggle={handleToggle}
                  />
                ))}
                {filteredPlaybooks.length === 0 && (
                  <div className="col-span-full text-center py-16">
                    <Zap size={48} className="mx-auto text-white/10 mb-4" />
                    <p className="text-white/40 text-lg font-medium">No hay estrategias en esta categoría</p>
                    <p className="text-white/30 text-sm mt-1 mb-4">Creá una nueva estrategia para empezar</p>
                    <button
                      onClick={() => setConfigModal({ open: true, playbookId: null })}
                      className="px-5 py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-medium inline-flex items-center gap-2 transition-colors"
                    >
                      <Plus size={16} />
                      Crear primera estrategia
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── TAB: Logs ─────────────────────────────────────────── */}
        {activeTab === 'logs' && (
          <div className="space-y-4">
            {/* Filter */}
            <div className="flex gap-2 flex-wrap">
              {['all', ...Object.keys(TRIGGER_LABELS)].map(filter => (
                <button
                  key={filter}
                  onClick={() => { setLogFilter(filter); setLogPage(1); }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                    logFilter === filter
                      ? 'bg-white/[0.10] text-white border border-white/[0.12]'
                      : 'text-white/40 hover:text-white/60'
                  }`}
                >
                  {filter === 'all' ? 'Todos' : TRIGGER_LABELS[filter] || filter}
                </button>
              ))}
            </div>

            {/* Table */}
            {loadingLogs ? (
              <div className="text-center py-8 text-white/30">Cargando logs...</div>
            ) : logs.length === 0 ? (
              <div className="text-center py-16 text-white/30">No hay logs todavía</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-white/40 text-left border-b border-white/[0.06]">
                      <th className="pb-2 pr-4 font-medium">Paciente</th>
                      <th className="pb-2 pr-4 font-medium">Tipo</th>
                      <th className="pb-2 pr-4 font-medium">Estado</th>
                      <th className="pb-2 pr-4 font-medium">Mensaje</th>
                      <th className="pb-2 pr-4 font-medium">Enviado</th>
                    </tr>
                  </thead>
                  <tbody>
                    {logs.map(log => (
                      <tr key={log.id} className="border-b border-white/[0.04] text-white/70">
                        <td className="py-2.5 pr-4">{log.patient_name || log.phone_number || '-'}</td>
                        <td className="py-2.5 pr-4">
                          <span style={{
                            display: 'inline-block', padding: '1px 8px', borderRadius: '9999px',
                            fontSize: '11px', fontWeight: 600,
                            background: (TRIGGER_COLORS[log.trigger_type] || '#64748b') + '18',
                            color: TRIGGER_COLORS[log.trigger_type] || '#64748b',
                          }}>
                            {TRIGGER_LABELS[log.trigger_type] || log.trigger_type}
                          </span>
                        </td>
                        <td className="py-2.5 pr-4">
                          <span style={{
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                            padding: '2px 8px', borderRadius: '9999px', fontSize: '11px', fontWeight: 600,
                            ...STATUS_STYLES[log.status] || STATUS_STYLES.pending,
                          }}>
                            {log.status}
                          </span>
                        </td>
                        <td className="py-2.5 pr-4 max-w-[200px] truncate text-white/50">
                          {log.message_preview || log.template_name || '-'}
                        </td>
                        <td className="py-2.5 text-white/40 text-xs">
                          {log.sent_at ? new Date(log.sent_at).toLocaleString('es-AR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                {/* Pagination */}
                {totalLogPages > 1 && (
                  <div className="flex justify-center gap-2 mt-4">
                    {Array.from({ length: totalLogPages }, (_, i) => (
                      <button
                        key={i}
                        onClick={() => setLogPage(i + 1)}
                        className={`px-3 py-1 rounded-lg text-xs font-medium ${
                          logPage === i + 1 ? 'bg-white/[0.10] text-white' : 'text-white/40 hover:text-white/60'
                        }`}
                      >
                        {i + 1}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* ── TAB: Templates ────────────────────────────────────── */}
        {activeTab === 'templates' && (
          <div className="space-y-4">
            {loadingTemplates ? (
              <div className="text-center py-8 text-white/30">Cargando plantillas...</div>
            ) : templates.length === 0 ? (
              <div className="text-center py-16 text-white/30">No hay plantillas disponibles</div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {templates.map(tpl => {
                  const body = tpl.components?.find(c => c.type === 'BODY');
                  return (
                    <div key={tpl.name} className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-5 space-y-3">
                      <div className="flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-white font-medium text-sm truncate">{tpl.name}</p>
                          <p className="text-white/40 text-xs mt-0.5">{tpl.language} · {tpl.category}</p>
                        </div>
                        {tpl.status === 'APPROVED' && (
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold"
                            style={{ background: 'rgba(16,185,129,0.12)', color: '#34d399', whiteSpace: 'nowrap' }}>
                            APPROVED
                          </span>
                        )}
                      </div>
                      {body?.text && (
                        <p className="text-white/50 text-xs leading-relaxed line-clamp-3">
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
      </div>

      {/* Config Modal */}
      {configModal.open && (
        <PlaybookConfigModal
          playbookId={configModal.playbookId}
          onClose={() => setConfigModal({ open: false, playbookId: null })}
          onSaved={() => {
            setConfigModal({ open: false, playbookId: null });
            loadPlaybooks();
          }}
        />
      )}
    </div>
  );
}
