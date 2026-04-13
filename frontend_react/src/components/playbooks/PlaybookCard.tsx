import React, { useState } from 'react';
import { Settings, BarChart3, Zap, ZapOff, Play, Clock, Send } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import api from '../../api/axios';

interface PlaybookCardProps {
  playbook: {
    id: number;
    name: string;
    description?: string;
    icon?: string;
    category: string;
    trigger_type: string;
    is_active: boolean;
    is_system: boolean;
    stats_cache?: {
      sent?: number;
      confirm_rate?: number;
      completion_rate?: number;
    };
    step_count?: number;
    active_executions?: number;
  };
  onConfigure: (id: number) => void;
  onToggle: (id: number) => void;
  onStats: (id: number) => void;
}

const CATEGORY_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  retention: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20' },
  revenue: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20' },
  reputation: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20' },
  clinical: { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/20' },
  recovery: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20' },
  custom: { bg: 'bg-white/[0.06]', text: 'text-white/60', border: 'border-white/[0.08]' },
};

const CATEGORY_LABELS: Record<string, string> = {
  retention: 'Retención',
  revenue: 'Ingresos',
  reputation: 'Reputación',
  clinical: 'Clínico',
  recovery: 'Recuperación',
  custom: 'Personalizado',
};

export default function PlaybookCard({ playbook, onConfigure, onToggle, onStats }: PlaybookCardProps) {
  const { t } = useTranslation();
  const colors = CATEGORY_COLORS[playbook.category] || CATEGORY_COLORS.custom;
  const stats = playbook.stats_cache || {};
  const isActive = playbook.is_active;
  const isReminder = playbook.trigger_type === 'appointment_reminder';
  const [sendingReminders, setSendingReminders] = useState(false);
  const [reminderResult, setReminderResult] = useState<string | null>(null);

  const handleSendRemindersNow = async () => {
    if (!confirm('Enviar recordatorios de turnos de mañana ahora?')) return;
    setSendingReminders(true);
    setReminderResult(null);
    try {
      const { data } = await api.post('/admin/playbooks/send-reminders-now');
      setReminderResult(`${data.sent} de ${data.total} enviados`);
      setTimeout(() => setReminderResult(null), 8000);
    } catch (err: any) {
      setReminderResult('Error al enviar');
      setTimeout(() => setReminderResult(null), 5000);
    } finally {
      setSendingReminders(false);
    }
  };

  return (
    <div className={`bg-white/[0.03] border rounded-2xl p-5 transition-all hover:bg-white/[0.05] ${isActive ? 'border-white/[0.08]' : 'border-white/[0.04] opacity-70'}`}>
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{playbook.icon || '📋'}</span>
          <div>
            <h3 className="font-bold text-white text-base leading-tight">{playbook.name}</h3>
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold uppercase tracking-wider border ${colors.bg} ${colors.text} ${colors.border}`}>
              {CATEGORY_LABELS[playbook.category] || playbook.category}
            </span>
          </div>
        </div>
        <button
          onClick={() => onToggle(playbook.id)}
          className={`relative w-12 h-6 rounded-full transition-colors ${isActive ? 'bg-green-500' : 'bg-white/10'}`}
        >
          <span className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${isActive ? 'left-[26px]' : 'left-0.5'}`} />
        </button>
      </div>

      {/* Description */}
      <p className="text-sm text-white/50 mb-4 leading-relaxed line-clamp-2">
        {playbook.description || t('playbooks.no_description')}
      </p>

      {/* KPIs */}
      {isActive && (stats.sent || playbook.active_executions) ? (
        <div className="flex gap-3 mb-4">
          {stats.confirm_rate != null && (
            <div className="bg-green-500/10 border border-green-500/20 rounded-lg px-3 py-1.5 text-center flex-1">
              <div className="text-green-400 font-bold text-lg">{stats.confirm_rate}%</div>
              <div className="text-[10px] text-green-400/60">{t('playbooks.confirm_rate')}</div>
            </div>
          )}
          {stats.sent != null && (
            <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg px-3 py-1.5 text-center flex-1">
              <div className="text-blue-400 font-bold text-lg">{stats.sent}</div>
              <div className="text-[10px] text-blue-400/60">{t('playbooks.sent')}</div>
            </div>
          )}
          {playbook.active_executions ? (
            <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-1.5 text-center flex-1">
              <div className="text-amber-400 font-bold text-lg">{playbook.active_executions}</div>
              <div className="text-[10px] text-amber-400/60">{t('playbooks.active')}</div>
            </div>
          ) : null}
        </div>
      ) : !isActive ? (
        <div className="bg-white/[0.04] border border-dashed border-white/[0.08] rounded-lg px-3 py-3 mb-4 text-center">
          <p className="text-xs text-white/40">
            💡 {t('playbooks.activate_hint')}
          </p>
        </div>
      ) : null}

      {/* Reminder manual trigger */}
      {isReminder && reminderResult && (
        <div className="bg-green-500/10 border border-green-500/20 rounded-lg px-3 py-2 mb-3 text-center">
          <p className="text-xs text-green-400 font-medium">{reminderResult}</p>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center gap-2">
        <div className="flex-1 flex items-center gap-1 text-white/30 text-xs">
          <Play size={12} />
          <span>{playbook.step_count || 0} {t('playbooks.steps')}</span>
        </div>
        {isReminder && (
          <button
            onClick={handleSendRemindersNow}
            disabled={sendingReminders}
            className="px-3 py-1.5 bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5 border border-blue-500/20 disabled:opacity-50"
            title="Enviar recordatorios de mañana ahora"
          >
            <Send size={12} className={sendingReminders ? 'animate-pulse' : ''} />
            {sendingReminders ? 'Enviando...' : 'Enviar ahora'}
          </button>
        )}
        <button
          onClick={() => onStats(playbook.id)}
          className="p-2 text-white/40 hover:text-white/70 hover:bg-white/[0.04] rounded-lg transition-colors"
          title={t('playbooks.view_stats')}
        >
          <BarChart3 size={16} />
        </button>
        <button
          onClick={() => onConfigure(playbook.id)}
          className="px-4 py-1.5 bg-white/[0.06] hover:bg-white/[0.10] text-white text-sm font-medium rounded-lg transition-colors flex items-center gap-1.5"
        >
          <Settings size={14} />
          {t('playbooks.configure')}
        </button>
      </div>
    </div>
  );
}
