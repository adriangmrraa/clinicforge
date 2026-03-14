/**
 * Dashboard CEO: Tokens, métricas del agente IA y estado del sistema.
 * Consume la API /dashboard/api/metrics - diseño integrado con ClinicForge.
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
  BarChart3
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

interface MetricsResponse {
  timestamp: string;
  status?: string;
  message?: string;
  token_metrics?: TokenMetrics;
  daily_usage?: { date: string; total_tokens: number; cost_usd: number }[];
  model_usage?: { model: string; total_tokens: number }[];
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
  <div className="bg-white/80 backdrop-blur-md border border-white/20 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all duration-300">
    <div className="flex justify-between items-start mb-3">
      <div className={`p-3 rounded-xl ${color} bg-opacity-10`}>
        <Icon className={`w-6 h-6 ${color.replace('bg-', 'text-')}`} />
      </div>
    </div>
    <p className="text-slate-500 text-sm font-medium">{title}</p>
    <h3 className="text-2xl font-bold text-slate-800 mt-1">{value}</h3>
    {subtitle && <p className="text-xs text-slate-400 mt-1">{subtitle}</p>}
  </div>
);

export default function DashboardStatusView() {
  const [data, setData] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(30);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.get<MetricsResponse>('/dashboard/api/metrics', {
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

  if (loading && !data) {
    return (
      <div className="h-screen flex flex-col bg-slate-50">
        <div className="p-6">
          <PageHeader title="Dashboard de Tokens" subtitle="Cargando métricas del agente IA..." />
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="flex flex-col items-center gap-4">
            <RefreshCw className="w-12 h-12 text-blue-500 animate-spin" />
            <p className="text-slate-500">Cargando...</p>
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
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden">
      <div className="flex-shrink-0 p-4 sm:p-6 bg-white/50 backdrop-blur-sm border-b border-slate-100">
        <PageHeader
          title="Dashboard de Tokens y Métricas"
          subtitle="Uso de IA, costos y estado del agente"
          icon={<BarChart3 size={22} />}
          action={
            <div className="flex items-center gap-2">
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="px-3 py-2 rounded-xl border border-slate-200 text-sm font-medium bg-white focus:ring-2 focus:ring-medical-500"
              >
                <option value={7}>Últimos 7 días</option>
                <option value={30}>Últimos 30 días</option>
                <option value={90}>Últimos 90 días</option>
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
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-red-500 shrink-0" />
            <div>
              <p className="font-medium text-red-800">No se pudieron cargar las métricas</p>
              <p className="text-sm text-red-600">{error}</p>
            </div>
            <button
              onClick={fetchMetrics}
              className="ml-auto px-3 py-1.5 text-sm font-medium text-red-700 bg-red-100 hover:bg-red-200 rounded-lg"
            >
              Reintentar
            </button>
          </div>
        )}

        {isSimplified && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-xl flex items-center gap-3">
            <AlertCircle className="w-6 h-6 text-amber-500 shrink-0" />
            <p className="text-amber-800">{data?.message || 'Módulos del dashboard no disponibles. Métricas limitadas.'}</p>
          </div>
        )}

        {data && !error && (
          <div className="space-y-6">
            {/* KPI Row */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
              <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
                  <Activity size={20} className="text-medical-600" />
                  Uso diario de tokens
                </h2>
                <div className="h-[280px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={dailyUsage}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                      <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 12 }} />
                      <YAxis tick={{ fill: '#64748b', fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                        formatter={(value: number, name: string) =>
                          [name === 'cost_usd' ? `$${value.toFixed(4)}` : value.toLocaleString(), name === 'cost_usd' ? 'Costo USD' : 'Tokens']
                        }
                      />
                      <Bar dataKey="total_tokens" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Tokens" />
                      <Bar dataKey="cost_usd" fill="#10b981" radius={[4, 4, 0, 0]} name="Costo USD" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Config & Projections */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
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
                    <div key={label} className="flex justify-between py-2 border-b border-slate-100 last:border-0">
                      <dt className="text-slate-600">{label}</dt>
                      <dd className="font-mono font-medium text-slate-800">{val}</dd>
                    </div>
                  ))}
                </dl>
              </div>

              <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
                <h2 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
                  <Database size={20} className="text-medical-600" />
                  Estadísticas de base de datos
                </h2>
                <dl className="space-y-3 text-sm">
                  {Object.entries(dbStats).map(([key, val]) => (
                    <div key={key} className="flex justify-between py-2 border-b border-slate-100 last:border-0">
                      <dt className="text-slate-600 capitalize">
                        {key.replace(/_/g, ' ')}
                      </dt>
                      <dd className="font-mono font-medium text-slate-800">{typeof val === 'number' ? val.toLocaleString() : val}</dd>
                    </div>
                  ))}
                  {Object.keys(dbStats).length === 0 && (
                    <p className="text-slate-400 italic">Sin datos de BD disponibles</p>
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
