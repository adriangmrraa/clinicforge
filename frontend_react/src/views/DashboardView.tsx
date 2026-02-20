import { useEffect, useState, useRef } from 'react';
import { io, Socket } from 'socket.io-client';
import { MessageSquare, Calendar, Activity, DollarSign, TrendingUp, TrendingDown, Target, Zap, Clock, ArrowUpRight, User } from 'lucide-react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area
} from 'recharts';
import api, { BACKEND_URL } from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import PageHeader from '../components/PageHeader';
import MarketingPerformanceCard from '../components/MarketingPerformanceCard';

// ============================================
// INTERFACES & TYPES
// ============================================

interface AnalyticsStats {
  ia_conversations: number;
  ia_appointments: number;
  active_urgencies: number;
  total_revenue: number;
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

const KPICard = ({ title, value, icon: Icon, color, trend }: any) => (
  <div className="bg-white/80 backdrop-blur-md border border-white/20 rounded-2xl p-6 shadow-sm hover:shadow-md transition-all duration-300 group">
    <div className="flex justify-between items-start mb-4">
      <div className={`p - 3 rounded - xl ${color} bg - opacity - 10 group - hover: scale - 110 transition - transform`}>
        <Icon className={`w - 6 h - 6 ${color.replace('bg-', 'text-')} `} />
      </div>
      {trend && (
        <span className="flex items-center gap-1 text-xs font-medium text-green-600 bg-green-50 px-2 py-1 rounded-full">
          <TrendingUp size={12} /> {trend}
        </span>
      )}
    </div>
    <p className="text-gray-500 text-sm font-medium">{title}</p>
    <h3 className="text-2xl font-bold text-gray-800 mt-1">{value}</h3>
  </div>
);

const UrgencyBadge = ({ level }: { level: UrgencyRecord['urgency_level'] }) => {
  const styles = {
    CRITICAL: 'bg-red-100 text-red-700 border-red-200',
    HIGH: 'bg-orange-100 text-orange-700 border-orange-200',
    NORMAL: 'bg-green-100 text-green-700 border-green-200'
  };
  return (
    <span className={`px - 2 py - 1 rounded - full text - [10px] font - bold border ${styles[level]} `}>
      {level}
    </span>
  );
};

// ============================================
// MAIN VIEW
// ============================================

export default function DashboardView() {
  const { t } = useTranslation();
  const [stats, setStats] = useState<AnalyticsStats | null>(null);
  const [urgencies, setUrgencies] = useState<UrgencyRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState<'weekly' | 'monthly' | 'yearly' | 'all'>('all');
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    // 1. Conectar WebSocket
    socketRef.current = io(BACKEND_URL);

    // 2. Escuchar nuevos turnos/mensajes para actualización en vivo
    socketRef.current.on('NEW_APPOINTMENT', () => {
      setStats(prev => {
        if (!prev) return prev;
        return {
          ...prev,
          ia_appointments: (prev.ia_appointments || 0) + 1
        };
      });
    });

    const loadDashboardData = async (range: string) => {
      try {
        setLoading(true);
        const [statsRes, urgenciesRes] = await Promise.all([
          api.get(`/ admin / stats / summary ? range = ${range} `),
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
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-slate-50 overflow-hidden">
      {/* HEADER SECTION */}
      <header className="p-4 sm:p-6 shrink-0 bg-white/50 backdrop-blur-sm border-b border-slate-100">
        <PageHeader
          title={t('dashboard.analytics_title')}
          subtitle={t('dashboard.analytics_subtitle')}
          action={
            <div className="flex gap-2">
              <button
                onClick={() => setTimeRange('weekly')}
                className={`px - 3 sm: px - 4 py - 2 rounded - xl shadow - sm border text - xs sm: text - sm font - medium transition - colors ${timeRange === 'weekly'
                  ? 'bg-slate-800 text-white border-slate-800'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                  } `}
              >
                {t('dashboard.weekly')}
              </button>
              <button
                onClick={() => setTimeRange('monthly')}
                className={`px - 3 sm: px - 4 py - 2 rounded - xl shadow - sm border text - xs sm: text - sm font - medium transition - colors ${timeRange === 'monthly'
                  ? 'bg-slate-800 text-white border-slate-800'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                  } `}
              >
                {t('dashboard.monthly')}
              </button>
              <button
                onClick={() => setTimeRange('yearly')}
                className={`px - 3 sm: px - 4 py - 2 rounded - xl shadow - sm border text - xs sm: text - sm font - medium transition - colors ${timeRange === 'yearly'
                  ? 'bg-slate-800 text-white border-slate-800'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                  } `}
              >
                {t('dashboard.this_year')}
              </button>
              <button
                onClick={() => setTimeRange('all')}
                className={`px - 3 sm: px - 4 py - 2 rounded - xl shadow - sm border text - xs sm: text - sm font - medium transition - colors ${timeRange === 'all'
                  ? 'bg-slate-800 text-white border-slate-800'
                  : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
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

        {/* TOP ROW: KPI CARDS */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <KPICard
            title={t('dashboard.conversations')}
            value={stats?.ia_conversations?.toLocaleString() || '0'}
            icon={MessageSquare}
            color="bg-blue-500"
            trend={(stats as any)?.ia_conversations_trend}
          />
          <KPICard
            title={t('dashboard.appointments')}
            value={stats?.ia_appointments?.toLocaleString() || '0'}
            icon={Calendar}
            color="bg-indigo-500"
            trend={(stats as any)?.ia_appointments_trend}
          />
          <KPICard
            title={t('dashboard.urgencies')}
            value={stats?.active_urgencies}
            icon={Activity}
            color="bg-rose-500"
          />
          <KPICard
            title={t('dashboard.revenue_confirmed')}
            value={`$${(stats as any)?.total_revenue?.toLocaleString() || 0} `}
            icon={DollarSign}
            color="bg-emerald-500"
            trend={(stats as any)?.total_revenue_trend}
          />
          <KPICard
            title={t('dashboard.revenue_estimated')}
            value={`$${(stats as any)?.estimated_revenue?.toLocaleString() || 0} `}
            icon={TrendingUp}
            color="bg-amber-500"
            trend="+15%"
          />
        </div>

        {/* MIDDLE ROW: CHARTS */}
        <div className="grid grid-cols-1 gap-6">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-100 p-6">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-lg font-semibold text-slate-800">{t('dashboard.chart_title')}</h2>
              <div className="hidden sm:flex gap-4 text-xs font-medium text-slate-500">
                <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-blue-500"></div> {t('dashboard.referrals')}</span>
                <span className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-emerald-500"></div> {t('dashboard.completed')}</span>
              </div>
            </div>
            <div className="h-[300px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={stats?.growth_data}>
                  <defs>
                    <linearGradient id="colorIA" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorDone" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.1} />
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                  <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} dy={10} />
                  <YAxis axisLine={false} tickLine={false} tick={{ fill: '#94a3b8', fontSize: 12 }} />
                  <Tooltip
                    contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                  />
                  <Area type="monotone" dataKey="ia_referrals" stroke="#3b82f6" strokeWidth={3} fillOpacity={1} fill="url(#colorIA)" />
                  <Area type="monotone" dataKey="completed_appointments" stroke="#10b981" strokeWidth={3} fillOpacity={1} fill="url(#colorDone)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

        </div>

        {/* Spec 09: MARKETING PERFORMANCE */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <MarketingPerformanceCard timeRange={timeRange === 'all' ? 'lifetime' : timeRange === 'yearly' ? 'this_year' : timeRange === 'monthly' ? 'last_30d' : 'weekly'} />
        </div>

        {/* BOTTOM ROW: RECENT URGENCIES TABLE */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden flex flex-col mb-4">
          <div className="p-6 border-b border-slate-50 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-slate-800">{t('dashboard.urgencies_recent')}</h2>
            <button className="text-blue-600 text-sm font-semibold hover:underline px-3 py-2">{t('dashboard.see_all')}</button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[600px]">
              <thead>
                <tr className="bg-slate-50/50">
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">{t('dashboard.patient')}</th>
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">{t('dashboard.reason')}</th>
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">{t('dashboard.severity')}</th>
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">{t('dashboard.time')}</th>
                  <th className="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {urgencies.map((u) => (
                  <tr key={u.id} className="hover:bg-slate-50/50 transition-colors group">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-full bg-slate-100 flex items-center justify-center text-slate-500 group-hover:bg-blue-100 group-hover:text-blue-600 transition-colors">
                          <User size={18} />
                        </div>
                        <div>
                          <p className="text-sm font-semibold text-slate-800">{u.patient_name}</p>
                          <p className="text-[11px] text-slate-500 font-mono tracking-tighter">{u.phone}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-600 font-medium">{u.reason}</td>
                    <td className="px-6 py-4">
                      <UrgencyBadge level={u.urgency_level} />
                    </td>
                    <td className="px-6 py-4 text-sm text-slate-500">
                      <div className="flex items-center gap-1.5">
                        <Clock size={14} className="text-slate-400" /> {u.timestamp}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button className="p-2 hover:bg-white rounded-lg border border-transparent hover:border-slate-200 text-slate-400 hover:text-blue-600 transition-all min-h-[44px] min-w-[44px] flex items-center justify-center">
                        <ArrowUpRight size={20} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </main>
    </div>
  );
}
