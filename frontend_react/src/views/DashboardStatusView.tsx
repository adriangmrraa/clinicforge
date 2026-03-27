/**
 * Dashboard CEO: Tokens, métricas del agente IA y estado del sistema.
 * Consume la API /admin/dashboard/metrics - diseño integrado con ClinicForge.
 */
import { useEffect, useState } from 'react';
import {
  Zap,
  DollarSign,
  TrendingUp,
  Activity,
  Database,
  Cpu,
  RefreshCw,
  AlertCircle,
  BarChart3,
  Settings,
  Check,
  MessageSquare,
  Brain,
  Mic,
  Sparkles
} from 'lucide-react';
import api from '../api/axios';
import PageHeader from '../components/PageHeader';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar
} from 'recharts';

interface TokenMetrics {
  totals?: {
    total_cost_usd: number;
    total_tokens: number;
    total_conversations: number;
    avg_tokens_per_conversation: number;
    avg_cost_per_conversation: number;
  };
  today?: { cost_usd: number; total_tokens: number; conversations: number };
  current_month?: { cost_usd: number };
}

interface ServiceBreakdown {
  service: string;
  model: string;
  total_tokens: number;
  cost_usd: number;
  calls: number;
}

interface MetricsResponse {
  timestamp: string;
  status?: string;
  message?: string;
  token_metrics?: TokenMetrics;
  daily_usage?: { date: string; total_tokens: number; cost_usd: number }[];
  model_usage?: { model: string; total_tokens: number }[];
  service_breakdown?: ServiceBreakdown[];
  db_stats?: Record<string, number>;
  projections?: Record<string, number>;
  current_config?: Record<string, string>;
  system_metrics?: Record<string, unknown>;
}

const StatCard = ({
  title,
  value,
  icon: Icon,
  color,
  subtitle
}: {
  title: string;
  value: string | number;
  icon: any;
  color: string;
  subtitle?: string;
}) => (
  <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl p-3 sm:p-5 hover:bg-white/[0.05] transition-all duration-300">
    <div className="flex justify-between items-start mb-2">
      <div className={`p-2 sm:p-3 rounded-xl ${color} bg-opacity-10`}>
        <Icon className={`w-4 h-4 sm:w-6 sm:h-6 ${color.replace('bg-', 'text-')}`} />
      </div>
    </div>
    <p className="text-white/40 text-[11px] sm:text-sm font-medium leading-tight">{title}</p>
    <h3 className="text-lg sm:text-2xl font-bold text-white mt-0.5">{value}</h3>
    {subtitle && <p className="text-[10px] sm:text-xs text-white/30 mt-0.5">{subtitle}</p>}
  </div>
);

const AVAILABLE_MODELS = [
  // === OpenAI — GPT-5.4 (Marzo 2026) ===
  { id: 'gpt-5.4', label: 'GPT-5.4 Flagship (1M ctx)', tier: 'premium', type: 'text', provider: 'openai' },
  { id: 'gpt-5.4-pro', label: 'GPT-5.4 Pro — Maximo razonamiento', tier: 'premium', type: 'text', provider: 'openai' },
  { id: 'gpt-5.4-mini', label: 'GPT-5.4 Mini — Rapido y barato', tier: 'economy', type: 'text', provider: 'openai' },
  { id: 'gpt-5.4-nano', label: 'GPT-5.4 Nano — Ultra economico', tier: 'economy', type: 'text', provider: 'openai' },
  // === OpenAI — GPT-5.x ===
  { id: 'gpt-5.3', label: 'GPT-5.3 Balanceado (400K ctx)', tier: 'standard', type: 'text', provider: 'openai' },
  { id: 'gpt-5', label: 'GPT-5 Original (400K ctx)', tier: 'standard', type: 'text', provider: 'openai' },
  { id: 'gpt-5-mini', label: 'GPT-5 Mini (400K ctx)', tier: 'economy', type: 'text', provider: 'openai' },
  // === OpenAI — Legacy ===
  { id: 'gpt-4o', label: 'GPT-4o Legacy (128K ctx)', tier: 'standard', type: 'text', provider: 'openai' },
  { id: 'gpt-4o-mini', label: 'GPT-4o Mini Legacy (128K ctx)', tier: 'economy', type: 'text', provider: 'openai' },
  // === OpenAI — Realtime (voice) ===
  { id: 'gpt-4o-mini-realtime-preview', label: 'Realtime Mini — Voz economica', tier: 'economy', type: 'realtime', provider: 'openai' },
  { id: 'gpt-4o-realtime-preview', label: 'Realtime Premium — Voz', tier: 'premium', type: 'realtime', provider: 'openai' },
  // === DeepSeek ===
  { id: 'deepseek-chat', label: 'DeepSeek V4 Chat — Muy barato, excelente', tier: 'economy', type: 'text', provider: 'deepseek' },
  { id: 'deepseek-reasoner', label: 'DeepSeek V4 Reasoner — Razonamiento profundo', tier: 'standard', type: 'text', provider: 'deepseek' },
];

// Nova Voice only works with realtime models, others only with text models
const VOICE_KEYS = new Set(['MODEL_NOVA_VOICE']);

interface ModelAction {
  key: string;
  label: string;
  description: string;
  icon: any;
}

const MODEL_ACTIONS: ModelAction[] = [
  { key: 'OPENAI_MODEL', label: 'Chat con pacientes', description: 'Agente principal que conversa con pacientes por WhatsApp/Instagram/Facebook', icon: MessageSquare },
  { key: 'MODEL_INSIGHTS', label: 'Análisis diario', description: 'Genera insights y análisis de conversaciones cada 12 horas', icon: Brain },
  { key: 'MODEL_NOVA_VOICE', label: 'Nova Voz', description: 'Asistente de voz Nova para el dashboard y ficha médica', icon: Mic },
  { key: 'MODEL_PATIENT_MEMORY', label: 'Memoria de pacientes', description: 'Extrae y almacena recuerdos de las conversaciones con pacientes', icon: Sparkles },
];

export default function DashboardStatusView() {
  const [data, setData] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);
  const [modelConfig, setModelConfig] = useState<Record<string, string>>({});
  const [modelSaving, setModelSaving] = useState<string | null>(null);
  const [modelSaved, setModelSaved] = useState<string | null>(null);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<MetricsResponse>('/admin/dashboard/metrics', {
        params: { days }
      });
      setData(res.data);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Error al cargar métricas';
      setError(String(msg));
      setData(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, [days]);

  // Sync model config from fetched data
  useEffect(() => {
    if (data?.current_config) {
      const cfg: Record<string, string> = {};
      for (const action of MODEL_ACTIONS) {
        const isVoice = VOICE_KEYS.has(action.key);
        const defaultModel = isVoice ? 'gpt-4o-mini-realtime-preview' : 'gpt-4o-mini';
        cfg[action.key] = data.current_config[action.key] || defaultModel;
      }
      setModelConfig(cfg);
    }
  }, [data?.current_config]);

  const saveModelConfig = async (key: string, value: string) => {
    setModelSaving(key);
    setModelSaved(null);
    try {
      await api.post('/dashboard/api/config', { [key]: value });
      setModelConfig(prev => ({ ...prev, [key]: value }));
      setModelSaved(key);
      setTimeout(() => setModelSaved(null), 2000);
    } catch (e) {
      console.error('Error saving model config:', e);
    } finally {
      setModelSaving(null);
    }
  };

  if (loading && !data) {
    return (
      <div className="h-screen flex flex-col">
        <div className="p-6">
          <PageHeader title="Dashboard de Tokens" subtitle="Cargando métricas del agente IA..." />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <RefreshCw className="w-12 h-12 text-blue-500 animate-spin" />
            <p className="text-white/40">Cargando...</p>
          </div>
        </div>
      </div>
    );
  }

  const isSimplified = data?.status === 'modules_not_available';
  const tokenMetrics = data?.token_metrics;
  const projections = data?.projections || {};
  const dbStats = data?.db_stats || {};
  const dailyUsage = data?.daily_usage || [];

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <div className="flex-shrink-0 p-4 sm:p-6 bg-white/[0.02] backdrop-blur-sm border-b border-white/[0.06]">
        <PageHeader
          title="Dashboard de Tokens y Métricas"
          subtitle="Uso de IA, costos y estado del agente"
          icon={<BarChart3 size={22} />}
          action={
            <div className="flex items-center gap-2">
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="px-3 py-2 rounded-xl border border-white/[0.08] text-sm font-medium bg-white/[0.04] text-white focus:ring-2 focus:ring-medical-500"
              >
                <option value={7} className="bg-[#0d1117] text-white">Últimos 7 días</option>
                <option value={30} className="bg-[#0d1117] text-white">Últimos 30 días</option>
                <option value={90} className="bg-[#0d1117] text-white">Últimos 90 días</option>
              </select>
              <button
                onClick={fetchMetrics}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-medical-600 hover:bg-medical-700 text-white text-sm font-medium disabled:opacity-50 transition-colors"
              >
                <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
                Actualizar
              </button>
            </div>
          }
        />
      </div>

      <main className="flex-1 overflow-y-auto p-4 lg:p-6">
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 rounded-xl flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-red-400 shrink-0" />
            <div>
              <p className="font-medium text-red-400">No se pudieron cargar las métricas</p>
              <p className="text-sm text-red-400/70">{error}</p>
            </div>
            <button
              onClick={fetchMetrics}
              className="ml-auto px-3 py-1.5 text-sm font-medium text-red-400 bg-red-500/10 hover:bg-red-500/20 rounded-lg"
            >
              Reintentar
            </button>
          </div>
        )}

        {isSimplified && (
          <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-amber-400 shrink-0" />
            <p className="text-amber-400">{data?.message || 'Módulos del dashboard no disponibles. Métricas limitadas.'}</p>
          </div>
        )}

        {data && !error && (
          <div className="space-y-6">
            {/* KPI Row */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
              <StatCard
                title="Costo total (período)"
                value={`$${(tokenMetrics?.totals?.total_cost_usd ?? 0).toFixed(2)}`}
                icon={DollarSign}
                color="bg-emerald-500"
                subtitle={`${tokenMetrics?.totals?.total_tokens?.toLocaleString() ?? 0} tokens`}
              />
              <StatCard
                title="Tokens totales"
                value={(tokenMetrics?.totals?.total_tokens ?? 0).toLocaleString()}
                icon={Zap}
                color="bg-blue-500"
                subtitle={`${tokenMetrics?.totals?.total_conversations ?? 0} conversaciones`}
              />
              <StatCard
                title="Proyección mensual"
                value={`$${(projections.projected_monthly_cost_usd ?? 0).toFixed(2)}`}
                icon={TrendingUp}
                color="bg-amber-500"
                subtitle="Estimado según uso actual"
              />
              <StatCard
                title="BD: Pacientes / Turnos"
                value={`${dbStats.total_patients ?? 0} / ${dbStats.total_appointments ?? 0}`}
                icon={Database}
                color="bg-slate-600"
                subtitle={`${dbStats.total_conversations ?? 0} conversaciones`}
              />
            </div>

            {/* Charts Row */}
            {dailyUsage.length > 0 && (
              <div className="bg-white/[0.03] rounded-2xl border border-white/[0.06] p-6">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Activity size={20} className="text-medical-600" />
                  Uso diario de tokens
                </h2>
                <div className="h-[260px]">
                  <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
                    <BarChart data={dailyUsage} margin={{ top: 5, right: 5, left: -10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" vertical={false} />
                      <XAxis
                        dataKey="date"
                        tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(v) => { const d = new Date(v + 'T00:00:00'); return `${d.getDate()}/${d.getMonth()+1}`; }}
                      />
                      <YAxis
                        tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 10 }}
                        tickLine={false}
                        axisLine={false}
                        width={45}
                        tickFormatter={(v) => v >= 1000 ? `${(v/1000).toFixed(0)}K` : v}
                      />
                      <Tooltip
                        contentStyle={{ borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)', backgroundColor: '#0d1117', color: '#fff', fontSize: 13 }}
                        labelFormatter={(v) => { const d = new Date(v + 'T00:00:00'); return d.toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' }); }}
                        formatter={(value: number, name: string) => {
                          if (name === 'Tokens') return [value.toLocaleString('es-AR'), 'Tokens'];
                          return [value, name];
                        }}
                      />
                      <Bar dataKey="total_tokens" fill="#3b82f6" radius={[6, 6, 0, 0]} name="Tokens" barSize={20} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                {/* Cost summary below chart */}
                {dailyUsage.length > 0 && (
                  <div className="mt-3 flex items-center justify-between text-xs text-white/40 px-1">
                    <span>Costo total periodo: <strong className="text-emerald-400">${dailyUsage.reduce((s, d) => s + (d.cost_usd || 0), 0).toFixed(4)}</strong></span>
                    <span>Promedio diario: <strong className="text-blue-400">{Math.round(dailyUsage.reduce((s, d) => s + (d.total_tokens || 0), 0) / dailyUsage.length).toLocaleString('es-AR')} tokens</strong></span>
                  </div>
                )}
              </div>
            )}

            {/* Model Configuration */}
            <div className="bg-white/[0.03] rounded-2xl border border-white/[0.06] p-6">
              <h2 className="text-lg font-semibold text-white mb-1 flex items-center gap-2">
                <Settings size={20} className="text-medical-600" />
                Configuración de modelos por acción
              </h2>
              <p className="text-sm text-white/40 mb-5">Seleccioná qué modelo usar para cada funcionalidad. Los cambios se aplican inmediatamente.</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                {MODEL_ACTIONS.map((action) => {
                  const ActionIcon = action.icon;
                  const isVoice = VOICE_KEYS.has(action.key);
                  const defaultModel = isVoice ? 'gpt-4o-mini-realtime-preview' : 'gpt-4o-mini';
                  const currentModel = modelConfig[action.key] || defaultModel;
                  const filteredModels = AVAILABLE_MODELS.filter(m => isVoice ? m.type === 'realtime' : m.type === 'text');
                  return (
                    <div key={action.key} className="border border-white/[0.06] rounded-xl p-4 hover:border-white/[0.12] transition-colors">
                      <div className="flex items-start gap-3 mb-3">
                        <div className={`p-2 rounded-lg shrink-0 ${isVoice ? 'bg-violet-500/10 text-violet-400' : 'bg-blue-500/10 text-blue-400'}`}>
                          <ActionIcon size={18} />
                        </div>
                        <div className="min-w-0">
                          <h3 className="text-sm font-semibold text-white">{action.label}</h3>
                          <p className="text-xs text-white/30 mt-0.5">{action.description}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <select
                          value={currentModel}
                          onChange={(e) => saveModelConfig(action.key, e.target.value)}
                          disabled={modelSaving === action.key}
                          className={`flex-1 px-3 py-2 rounded-lg border text-sm font-medium bg-white/[0.04] text-white outline-none disabled:opacity-50 ${isVoice ? 'border-violet-500/20 focus:ring-2 focus:ring-violet-500' : 'border-white/[0.08] focus:ring-2 focus:ring-blue-500'}`}
                        >
                          {filteredModels.map((m) => (
                            <option key={m.id} value={m.id} className="bg-[#0d1117] text-white">{m.label}</option>
                          ))}
                        </select>
                        {modelSaving === action.key && (
                          <div className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin shrink-0" />
                        )}
                        {modelSaved === action.key && (
                          <Check size={18} className="text-green-500 shrink-0" />
                        )}
                      </div>
                      {isVoice && <p className="text-[10px] text-violet-400/70 mt-1.5">Solo modelos Realtime (audio bidireccional)</p>}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Config & Projections */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white/[0.03] rounded-2xl border border-white/[0.06] p-6">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Cpu size={20} className="text-medical-600" />
                  Proyecciones y eficiencia
                </h2>
                <dl className="space-y-3 text-sm">
                  {[
                    ['Proyección anual', projections.projected_annual_cost_usd != null ? `$${projections.projected_annual_cost_usd.toFixed(2)}` : '—'],
                    ['Coste/1000 tokens', projections.cost_per_1000_tokens != null ? `$${projections.cost_per_1000_tokens.toFixed(4)}` : '—'],
                    ['Prom. tokens/conversación', projections.avg_tokens_per_conversation?.toLocaleString() ?? '—'],
                    ['Score eficiencia', projections.efficiency_score != null ? `${projections.efficiency_score}/100` : '—']
                  ].map(([label, val]) => (
                    <div key={label} className="flex justify-between py-2 border-b border-white/[0.06] last:border-0">
                      <dt className="text-white/60">{label}</dt>
                      <dd className="font-mono font-medium text-white">{val}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              <div className="bg-white/[0.03] rounded-2xl border border-white/[0.06] p-6">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Database size={20} className="text-medical-600" />
                  Estadísticas de base de datos
                </h2>
                <dl className="space-y-3 text-sm">
                  {Object.entries(dbStats).map(([key, val]) => (
                    <div key={key} className="flex justify-between py-2 border-b border-white/[0.06] last:border-0">
                      <dt className="text-white/60 capitalize">
                        {key.replace(/_/g, ' ')}
                      </dt>
                      <dd className="font-mono font-medium text-white">{typeof val === 'number' ? val.toLocaleString() : val}</dd>
                    </div>
                  ))}
                  {Object.keys(dbStats).length === 0 && (
                    <p className="text-white/30 italic">Sin datos de BD disponibles</p>
                  )}
                </dl>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
