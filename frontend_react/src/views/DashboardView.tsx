import { useEffect, useState, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { MessageSquare, Calendar, Activity as LucideActivity, DollarSign, TrendingUp, TrendingDown, Target, Zap, Clock, ArrowUpRight, User, AlertCircle } from 'lucide-react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';
import api, { WS_URL } from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import { useAuth } from '../context/AuthContext';
import PageHeader from '../components/PageHeader';
import MarketingPerformanceCard from '../components/MarketingPerformanceCard';
import GlassCard, { CARD_IMAGES } from '../components/GlassCard';

// ============================================
// INTERFACES & TYPES
// ============================================

interface AnalyticsStats {
  ia_conversations: number;
  ia_appointments: number;
  active_urgencies: number;
  total_revenue: number;
  pending_payments?: number;
  today_revenue?: number;
  growth_data: { date: string; ia_referrals: number; completed_appointments: number }[];
}

interface UrgencyRecord {
  id: string;
  patient_name: string;
  phone: string;
  urgency_level: 'CRITICAL' | 'HIGH' | 'NORMAL';
  reason: string;
  timestamp: string;
}

// ============================================
// COMPONENTS
// ============================================

interface KPICardProps {
  title: string;
  value: string | number;
  icon: any;
  color: string;
  trend?: string;
  hint?: string;
  image?: string;
}

const KPICard = ({ title, value, icon: Icon, color, trend, hint, image }: KPICardProps) => (
  <GlassCard image={image}>
    <div className="p-3 sm:p-5 group" title={hint}>
      <div className="flex justify-between items-start mb-2 sm:mb-3">
        <div className={`p-2 sm:p-3 rounded-xl ${color} bg-opacity-10 group-hover:scale-110 transition-transform`}>
          <Icon className={`w-4 h-4 sm:w-6 sm:h-6 ${color.replace('bg-', 'text-')}`} />
        </div>
        {trend && (
          <span className="flex items-center gap-0.5 text-[10px] sm:text-xs font-medium text-green-400 bg-green-500/10 px-1.5 py-0.5 sm:px-2 sm:py-1 rounded-full">
            <TrendingUp size={10} /> {trend}
          </span>
        )}
      </div>
      <p className="text-white/50 text-[11px] sm:text-sm font-medium leading-tight">{title}</p>
      <h3 className="text-lg sm:text-2xl font-bold text-white mt-0.5">{value}</h3>
    </div>
  </GlassCard>
);

const UrgencyBadge = ({ level, t }: { level: UrgencyRecord['urgency_level'], t: any }) => {
  const styles = {
    CRITICAL: 'bg-red-500/10 text-red-400 border-red-500/20',
    HIGH: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    NORMAL: 'bg-green-500/10 text-green-400 border-green-500/20'
  };
  return (
    <span className={`px-2 py-1 rounded-full text-[10px] font-bold border ${styles[level]}`}>
      {t(`dashboard.severity_${level.toLowerCase()}`)}
    </span>
  );
};

// ============================================
// MAIN VIEW
// ============================================

export default function DashboardView() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const isProfessional = (user as any)?.role === 'professional';
  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [urgencies, setUrgencies] = useState<UrgencyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<'weekly' | 'monthly' | 'yearly' | 'all'>('all');
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    // 1. Conectar WebSocket
    socketRef.current = io(WS_URL);

    const loadUrgencies = async () => {
      try {
        const res = await api.get('/admin/chat/urgencies');
        setUrgencies(res.data);
      } catch (e) {
        console.error('Error refreshing urgencies:', e);
      }
    };

    // 2. Escuchar nuevos turnos/mensajes para actualización en vivo
    socketRef.current.on('NEW_APPOINTMENT', () => {
      setStats((prev: AnalyticsStats | null) => {
        if (!prev) return prev;
        return {
          ...prev,
          ia_appointments: (prev.ia_appointments || 0) + 1
        };
      });
    });

    socketRef.current.on('PAYMENT_CONFIRMED', () => {
      setStats((prev: AnalyticsStats | null) => {
        if (!prev) return prev;
        return { ...prev };
      });
    });

    socketRef.current.on('PATIENT_UPDATED', (data: any) => {
      // Actualizar contador
      setStats((prev: AnalyticsStats | null) => {
        if (!prev) return prev;
        return {
          ...prev,
          active_urgencies: (prev.active_urgencies || 0) + 1
        };
      });
      // Recargar lista de urgencias
      loadUrgencies();
    });

    // Nova billing/CRUD updates — debounced refetch (avoid flooding API)
    let dashboardRefreshTimer: ReturnType<typeof setTimeout> | null = null;
    const debouncedRefresh = () => {
      if (dashboardRefreshTimer) clearTimeout(dashboardRefreshTimer);
      dashboardRefreshTimer = setTimeout(() => loadDashboardData(timeRange), 3000);
    };
    socketRef.current.on('BILLING_UPDATED', debouncedRefresh);
    socketRef.current.on('RECORD_UPDATED', debouncedRefresh);
    socketRef.current.on('TREATMENT_PLAN_UPDATED', debouncedRefresh);

    const loadDashboardData = async (range: string) => {
      try {
        setLoading(true);
        const [statsRes, urgenciesRes] = await Promise.all([
          api.get(`/admin/stats/summary?range=${range}`),
          api.get('/admin/chat/urgencies')
        ]);

        setStats(statsRes.data);
        setUrgencies(urgenciesRes.data);

      } catch (error) {
        console.error('Error loading analytics:', error);
      } finally {
        setLoading(false);
      }
    };

    loadDashboardData(timeRange);

    return () => {
      if (socketRef.current) socketRef.current.disconnect();
    };
  }, [timeRange]); // Re-run effect when timeRange changes to fetch new data

  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* HEADER SECTION */}
      <header className="p-4 sm:p-6 shrink-0 bg-white/[0.02] backdrop-blur-sm border-b border-white/[0.06]">
        <PageHeader
          title={t('dashboard.analytics_title')}
          subtitle={t('dashboard.analytics_subtitle')}
          action={
            <div className="flex gap-2">
              <button
                onClick={() => setTimeRange('weekly')}
                className={`px-3 sm:px-4 py-2 rounded-xl shadow-sm border text-xs sm:text-sm font-medium transition-colors ${timeRange === 'weekly'
                  ? 'bg-white text-[#0a0e1a] border-white'
                  : 'bg-white/[0.03] text-white/50 border-white/[0.06] hover:bg-white/[0.04]'
                  } `}
              >
                {t('dashboard.weekly')}
              </button>
              <button
                onClick={() => setTimeRange('monthly')}
                className={`px-3 sm:px-4 py-2 rounded-xl shadow-sm border text-xs sm:text-sm font-medium transition-colors ${timeRange === 'monthly'
                  ? 'bg-white text-[#0a0e1a] border-white'
                  : 'bg-white/[0.03] text-white/50 border-white/[0.06] hover:bg-white/[0.04]'
                  } `}
              >
                {t('dashboard.monthly')}
              </button>
              <button
                onClick={() => setTimeRange('yearly')}
                className={`px-3 sm:px-4 py-2 rounded-xl shadow-sm border text-xs sm:text-sm font-medium transition-colors ${timeRange === 'yearly'
                  ? 'bg-white text-[#0a0e1a] border-white'
                  : 'bg-white/[0.03] text-white/50 border-white/[0.06] hover:bg-white/[0.04]'
                  } `}
              >
                {t('dashboard.this_year')}
              </button>
              <button
                onClick={() => setTimeRange('all')}
                className={`px-3 sm:px-4 py-2 rounded-xl shadow-sm border text-xs sm:text-sm font-medium transition-colors ${timeRange === 'all'
                  ? 'bg-white text-[#0a0e1a] border-white'
                  : 'bg-white/[0.03] text-white/50 border-white/[0.06] hover:bg-white/[0.04]'
                  } `}
              >
                {t('dashboard.all')}
              </button>
            </div>
          }
        />
      </header>

      {/* MAIN SCROLLABLE CONTENT WITH ISORATION */}
      <main className="flex-1 overflow-y-auto p-4 lg:p-6 space-y-6 scroll-smooth">

        {/* TOP ROW: KPI CARDS — role-aware */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
          <KPICard
            title={t('dashboard.conversations')}
            value={stats?.ia_conversations?.toLocaleString() || '0'}
            icon={MessageSquare}
            color="bg-blue-500"
            trend={(stats as any)?.ia_conversations_trend}
            image={CARD_IMAGES.patients}
          />
          <KPICard
            title={t('dashboard.appointments')}
            value={stats?.ia_appointments?.toLocaleString() || '0'}
            icon={Calendar}
            color="bg-emerald-500"
            trend={(stats as any)?.ia_appointments_trend}
            hint={t('dashboard.appointments_hint')}
            image={CARD_IMAGES.appointments}
          />
          <KPICard
            title={t('dashboard.urgencies')}
            value={stats?.active_urgencies}
            icon={LucideActivity}
            color="bg-rose-500"
            image={CARD_IMAGES.completion}
          />
          {user?.role === 'ceo' && (
            <>
              <KPICard
                title={t('dashboard.revenue_confirmed')}
                value={`$${(stats as any)?.total_revenue?.toLocaleString() || 0}`}
                icon={DollarSign}
                color="bg-emerald-500"
                trend={(stats as any)?.total_revenue_trend}
                image={CARD_IMAGES.revenue}
              />
              <KPICard
                title={t('dashboard.revenue_estimated')}
                value={`$${(stats as any)?.estimated_revenue?.toLocaleString() || 0}`}
                icon={TrendingUp}
                color="bg-amber-500"
                trend="+15%"
                image={CARD_IMAGES.revenue}
              />
              <KPICard
                title={t('dashboard.pending_payments')}
                value={`$${Math.round(stats?.pending_payments || 0).toLocaleString('es-AR')}`}
                icon={AlertCircle}
                color="bg-amber-500"
                image={CARD_IMAGES?.pending}
              />
              <KPICard
                title={t('dashboard.today_revenue')}
                value={`$${Math.round(stats?.today_revenue || 0).toLocaleString('es-AR')}`}
                icon={DollarSign}
                color="bg-teal-500"
                image={CARD_IMAGES?.revenue_today}
              />
            </>
          )}
          {isProfessional && (
            <KPICard
              title={t('dashboard.my_patients') || 'Mis Pacientes'}
              value={(stats as any)?.total_patients?.toLocaleString() || '—'}
              icon={User}
              color="bg-purple-500"
              image={CARD_IMAGES.patients}
            />
          )}
        </div>

        {/* MIDDLE ROW: CHARTS */}
        <div className="grid grid-cols-1 gap-6">
          <GlassCard image={CARD_IMAGES.analytics}>
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-semibold text-white">{t('dashboard.chart_title')}</h2>
                <div className="hidden sm:flex gap-4 text-xs font-medium text-white/50">
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-blue-500"></div> {t('dashboard.referrals')}</span>
                  <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-emerald-500"></div> {t('dashboard.completed')}</span>
                </div>
              </div>
              <div className="h-[220px] sm:h-[300px] w-full">
                {stats?.growth_data ? (
                  <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={0}>
                    <AreaChart data={stats.growth_data} margin={{ top: 5, right: 5, left: -15, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorIA" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="colorDone" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.15} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.06)" />
                      <XAxis
                        dataKey="date"
                        axisLine={false}
                        tickLine={false}
                        tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
                        dy={10}
                        tickFormatter={(v) => { const d = new Date(v + 'T00:00:00'); return `${d.getDate()}/${d.getMonth()+1}`; }}
                      />
                      <YAxis axisLine={false} tickLine={false} tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }} width={30} allowDecimals={false} />
                      <Tooltip
                        contentStyle={{ borderRadius: '12px', border: '1px solid rgba(255,255,255,0.08)', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.3)', fontSize: 13, backgroundColor: '#1a1e2e', color: '#fff' }}
                        labelFormatter={(v) => { const d = new Date(v + 'T00:00:00'); return d.toLocaleDateString('es-AR', { day: 'numeric', month: 'short' }); }}
                        formatter={(value: number, name: string) => [
                          value,
                          name === 'ia_referrals' ? 'Derivaciones IA' : name === 'completed_appointments' ? 'Turnos completados' : name
                        ]}
                      />
                      <Area type="monotone" dataKey="ia_referrals" stroke="#3b82f6" strokeWidth={2.5} fillOpacity={1} fill="url(#colorIA)" name="Derivaciones IA" />
                      <Area type="monotone" dataKey="completed_appointments" stroke="#10b981" strokeWidth={2.5} fillOpacity={1} fill="url(#colorDone)" name="Turnos completados" />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-white/30 italic text-sm">
                    {t('dashboard.no_data_available')}
                  </div>
                )}
              </div>
            </div>
          </GlassCard>

        </div>

        {/* Spec 09: MARKETING PERFORMANCE — CEO only */}
        {user?.role === 'ceo' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MarketingPerformanceCard timeRange={timeRange === 'all' ? 'lifetime' : timeRange === 'yearly' ? 'this_year' : timeRange === 'monthly' ? 'last_30d' : 'weekly'} />
        </div>
        )}

        {/* BOTTOM ROW: RECENT URGENCIES TABLE */}
        <GlassCard image={CARD_IMAGES.dental}>
          <div className="overflow-hidden flex flex-col mb-4">
            <div className="p-6 border-b border-white/[0.06] flex justify-between items-center">
              <h2 className="text-lg font-semibold text-white">{t('dashboard.urgencies_recent')}</h2>
              <button className="text-blue-400 text-sm font-semibold hover:underline px-3 py-2">{t('dashboard.see_all')}</button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[600px]">
                <thead>
                  <tr className="bg-white/[0.02]">
                    <th className="px-6 py-4 text-xs font-bold text-white/30 uppercase tracking-wider">{t('dashboard.patient')}</th>
                    <th className="px-6 py-4 text-xs font-bold text-white/30 uppercase tracking-wider">{t('dashboard.reason')}</th>
                    <th className="px-6 py-4 text-xs font-bold text-white/30 uppercase tracking-wider">{t('dashboard.severity')}</th>
                    <th className="px-6 py-4 text-xs font-bold text-white/30 uppercase tracking-wider">{t('dashboard.time')}</th>
                    <th className="px-6 py-4 text-xs font-bold text-white/30 uppercase tracking-wider"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.06]">
                  {urgencies.map((u) => (
                    <tr key={u.id} className="hover:bg-white/[0.04] transition-colors group">
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-white/[0.06] flex items-center justify-center text-white/50 group-hover:bg-blue-500/10 group-hover:text-blue-400 transition-colors">
                            <User size={18} />
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-white">{u.patient_name}</p>
                            <p className="text-[11px] text-white/50 font-mono tracking-tighter">{u.phone}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-white/50 font-medium">{u.reason}</td>
                      <td className="px-6 py-4">
                        <UrgencyBadge level={u.urgency_level} t={t} />
                      </td>
                      <td className="px-6 py-4 text-sm text-white/50">
                        <div className="flex items-center gap-1.5">
                          <Clock size={14} className="text-white/30" /> {u.timestamp}
                        </div>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button className="p-2 hover:bg-white/[0.04] rounded-lg border border-transparent hover:border-white/[0.06] text-white/30 hover:text-blue-400 transition-all min-h-[44px] min-w-[44px] flex items-center justify-center">
                          <ArrowUpRight size={20} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </GlassCard>

      </main>
    </div>
  );
}
