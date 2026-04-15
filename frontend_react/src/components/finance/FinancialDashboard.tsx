import {
  DollarSign,
  Banknote,
  TrendingUp,
  TrendingDown,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  AlertTriangle,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  AreaChart,
  Area,
} from 'recharts';
import { useTranslation } from '../../context/LanguageContext';
import GlassCard, { CARD_IMAGES } from '../GlassCard';
import type {
  DashboardData,
  RevenueByProfessional,
  RevenueByTreatment,
  DailyCashFlow,
  PendingCollection,
  MoMGrowth,
} from '../../types/finance';

const CHART_COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

interface FinancialDashboardProps {
  data: DashboardData | null;
  loading: boolean;
  formatCurrency: (n: number) => string;
}

function KPICard({
  title,
  value,
  icon: Icon,
  color,
  trend,
  trendValue,
  image,
}: {
  title: string;
  value: string;
  icon: any;
  color: string;
  trend?: 'up' | 'down';
  trendValue?: string;
  image?: string;
}) {
  return (
    <GlassCard image={image}>
      <div className="p-4 sm:p-5">
        <div className="flex items-start justify-between mb-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>
            <Icon size={20} />
          </div>
          {trend && (
            <span
              className={`flex items-center gap-0.5 text-xs font-semibold ${trend === 'up' ? 'text-green-400' : 'text-red-400'}`}
            >
              {trend === 'up' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
              {trendValue}
            </span>
          )}
        </div>
        <p className="text-2xl font-bold text-white tracking-tight">{value}</p>
        <p className="text-xs text-white/40 mt-0.5">{title}</p>
      </div>
    </GlassCard>
  );
}

function getDaysOverdueColor(days: number): string {
  if (days > 30) return 'text-red-400';
  if (days >= 15) return 'text-amber-400';
  return 'text-yellow-400';
}

export default function FinancialDashboard({ data, loading, formatCurrency }: FinancialDashboardProps) {
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-white/[0.03] border border-white/[0.04] rounded-2xl p-5 animate-pulse">
              <div className="w-10 h-10 rounded-xl bg-white/[0.06] mb-3" />
              <div className="h-7 bg-white/[0.06] rounded w-24 mb-2" />
              <div className="h-3 bg-white/[0.06] rounded w-32" />
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {[0, 1].map((i) => (
            <div key={i} className="bg-white/[0.03] border border-white/[0.04] rounded-2xl p-6 animate-pulse h-80" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <GlassCard>
        <div className="p-8 text-center text-white/30 text-sm">
          {t('finance.no_data')}
        </div>
      </GlassCard>
    );
  }

  const { summary, revenue_by_professional, revenue_by_treatment, daily_cash_flow, mom_growth, pending_collections } = data;

  // Revenue by professional chart data
  const profChartData = revenue_by_professional.map((p: RevenueByProfessional) => ({
    name: p.professional_name.split(' ').slice(0, 2).join(' '),
    total_billed: p.total_billed,
    total_paid: p.total_paid,
  }));

  // Revenue by treatment pie data
  const treatmentTotal = revenue_by_treatment.reduce((acc, t) => acc + t.total_billed, 0);
  const pieData = revenue_by_treatment.map((t: RevenueByTreatment) => ({
    name: t.treatment_name,
    value: t.total_billed,
    pct: treatmentTotal > 0 ? ((t.total_billed / treatmentTotal) * 100).toFixed(0) : 0,
  }));

  // Daily cash flow chart data
  const cashFlowData = daily_cash_flow.map((d: DailyCashFlow) => ({
    date: new Date(d.date + 'T00:00:00').toLocaleDateString('es-AR', { day: '2-digit', month: 'short' }),
    total: d.total,
    payouts: d.payouts,
  }));

  // MoM growth
  const growth = mom_growth as MoMGrowth | undefined;

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <KPICard
          title={t('finance.total_revenue')}
          value={formatCurrency(summary.total_revenue)}
          icon={DollarSign}
          color="bg-emerald-500/10 text-emerald-400"
          trend={growth && growth.growth_pct > 0 ? 'up' : growth && growth.growth_pct < 0 ? 'down' : undefined}
          trendValue={growth ? `${growth.growth_pct >= 0 ? '+' : ''}${growth.growth_pct.toFixed(1)}%` : undefined}
          image={CARD_IMAGES.revenue}
        />
        <KPICard
          title={t('finance.total_payouts')}
          value={formatCurrency(summary.total_payouts)}
          icon={Banknote}
          color="bg-blue-500/10 text-blue-400"
          image={CARD_IMAGES.analytics}
        />
        <KPICard
          title={t('finance.net_profit')}
          value={formatCurrency(summary.net_profit)}
          icon={TrendingUp}
          color="bg-purple-500/10 text-purple-400"
          trend={summary.net_profit > 0 ? 'up' : 'down'}
          image={CARD_IMAGES.completion}
        />
        <KPICard
          title={t('finance.pending_collections')}
          value={formatCurrency(summary.total_pending)}
          icon={Clock}
          color="bg-amber-500/10 text-amber-400"
          image={CARD_IMAGES.patients}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue by Professional */}
        <GlassCard image={CARD_IMAGES.team} hoverScale={false}>
          <div className="p-5">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <TrendingUp size={16} className="text-blue-400" />
              {t('finance.revenue_by_professional')}
            </h3>
            {profChartData.length > 0 ? (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={profChartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.06)" />
                    <XAxis
                      dataKey="name"
                      tick={{ fontSize: 11, fill: 'rgba(255,255,255,0.4)' }}
                      stroke="rgba(255,255,255,0.1)"
                    />
                    <YAxis
                      tick={{ fontSize: 11, fill: 'rgba(255,255,255,0.4)' }}
                      stroke="rgba(255,255,255,0.1)"
                      tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
                    />
                    <Tooltip
                      contentStyle={{
                        borderRadius: '12px',
                        border: '1px solid rgba(255,255,255,0.1)',
                        background: 'rgba(10,14,26,0.95)',
                        boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                        fontSize: '12px',
                        color: '#fff',
                      }}
                      formatter={(value: number) => [formatCurrency(value), '']}
                    />
                    <Bar dataKey="total_billed" name="Facturado" fill="#3b82f6" radius={[6, 6, 0, 0]} barSize={20} />
                    <Bar dataKey="total_paid" name="Cobrado" fill="#10b981" radius={[6, 6, 0, 0]} barSize={20} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-72 flex items-center justify-center text-white/30 text-sm">
                {t('finance.no_data')}
              </div>
            )}
          </div>
        </GlassCard>

        {/* Revenue by Treatment */}
        <GlassCard image={CARD_IMAGES.dental} hoverScale={false}>
          <div className="p-5">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <DollarSign size={16} className="text-emerald-400" />
              {t('finance.revenue_by_treatment')}
            </h3>
            {pieData.length > 0 ? (
              <>
                <div className="h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={pieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={40}
                        outerRadius={70}
                        dataKey="value"
                        paddingAngle={3}
                      >
                        {pieData.map((entry, i) => (
                          <Cell key={entry.name} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        contentStyle={{
                          borderRadius: '12px',
                          border: '1px solid rgba(255,255,255,0.1)',
                          background: 'rgba(10,14,26,0.95)',
                          boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
                          fontSize: '12px',
                          color: '#fff',
                        }}
                        formatter={(value: number, name: string, props: any) => [
                          `${formatCurrency(value)} (${props.payload.pct}%)`,
                          name,
                        ]}
                      />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-2 mt-2">
                  {pieData.map((item, i) => (
                    <div key={item.name} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-2.5 h-2.5 rounded-full"
                          style={{ backgroundColor: CHART_COLORS[i % CHART_COLORS.length] }}
                        />
                        <span className="text-white/60 truncate max-w-[140px]">{item.name}</span>
                      </div>
                      <span className="text-white/40 font-medium">{item.pct}%</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="h-44 flex items-center justify-center text-white/30 text-sm">
                {t('finance.no_data')}
              </div>
            )}
          </div>
        </GlassCard>
      </div>

      {/* Daily Cash Flow */}
      <GlassCard image={CARD_IMAGES.analytics} hoverScale={false}>
        <div className="p-5">
          <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
            <TrendingUp size={16} className="text-cyan-400" />
            {t('finance.daily_cash_flow')}
          </h3>
          {cashFlowData.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={cashFlowData} margin={{ top: 5, right: 20, left: -15, bottom: 5 }}>
                  <defs>
                    <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorPayouts" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.06)" />
                  <XAxis
                    dataKey="date"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
                    dy={10}
                  />
                  <YAxis
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
                    width={40}
                    tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
                  />
                  <Tooltip
                    contentStyle={{
                      borderRadius: '12px',
                      border: '1px solid rgba(255,255,255,0.08)',
                      boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.3)',
                      fontSize: 13,
                      backgroundColor: '#1a1e2e',
                      color: '#fff',
                    }}
                    formatter={(value: number, name: string) => [
                      formatCurrency(value),
                      name === 'total' ? 'Ingresos' : 'Pagos',
                    ]}
                  />
                  <Area
                    type="monotone"
                    dataKey="total"
                    stroke="#3b82f6"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#colorRevenue)"
                    name="Ingresos"
                  />
                  <Area
                    type="monotone"
                    dataKey="payouts"
                    stroke="#f59e0b"
                    strokeWidth={2.5}
                    fillOpacity={1}
                    fill="url(#colorPayouts)"
                    name="Pagos"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-64 flex items-center justify-center text-white/30 text-sm">
              {t('finance.no_data')}
            </div>
          )}
        </div>
      </GlassCard>

      {/* MoM Comparison + Pending Collections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* MoM Growth */}
        {growth && (
          <GlassCard image={CARD_IMAGES.completion} hoverScale={false}>
            <div className="p-5">
              <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                <TrendingUp size={16} className="text-emerald-400" />
                {t('finance.mom_growth')}
              </h3>
              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-xs text-white/50 mb-1">
                    <span>{t('finance.current_period')}</span>
                    <span className="text-white font-semibold">{formatCurrency(growth.current_revenue)}</span>
                  </div>
                  <div className="h-3 rounded-full bg-white/[0.06] overflow-hidden">
                    <div
                      className="h-full bg-blue-500/60 rounded-full transition-all duration-700"
                      style={{
                        width: `${growth.current_revenue > 0 ? Math.min((growth.current_revenue / Math.max(growth.current_revenue, growth.previous_revenue)) * 100, 100) : 0}%`,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs text-white/50 mb-1">
                    <span>{t('finance.previous_period')}</span>
                    <span className="text-white font-semibold">{formatCurrency(growth.previous_revenue)}</span>
                  </div>
                  <div className="h-3 rounded-full bg-white/[0.06] overflow-hidden">
                    <div
                      className="h-full bg-white/20 rounded-full transition-all duration-700"
                      style={{
                        width: `${growth.previous_revenue > 0 ? Math.min((growth.previous_revenue / Math.max(growth.current_revenue, growth.previous_revenue)) * 100, 100) : 0}%`,
                      }}
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between pt-2 border-t border-white/[0.06]">
                  <span className="text-xs text-white/40">{t('finance.growth')}</span>
                  <span
                    className={`flex items-center gap-1 text-sm font-bold ${growth.growth_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}
                  >
                    {growth.growth_pct >= 0 ? <ArrowUpRight size={16} /> : <ArrowDownRight size={16} />}
                    {growth.growth_pct >= 0 ? '+' : ''}
                    {growth.growth_pct.toFixed(1)}%
                  </span>
                </div>
              </div>
            </div>
          </GlassCard>
        )}

        {/* Pending Collections */}
        <GlassCard image={CARD_IMAGES.patients} hoverScale={false}>
          <div className="p-5">
            <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-400" />
              {t('finance.pending_collections')} ({pending_collections.length})
            </h3>
            {pending_collections.length > 0 ? (
              <div className="space-y-3">
                {pending_collections.slice(0, 5).map((item: PendingCollection) => (
                  <div
                    key={item.appointment_id}
                    className="flex items-center justify-between py-2 border-b border-white/[0.04] last:border-0"
                  >
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-white truncate">{item.patient_name}</p>
                      <p className="text-[11px] text-white/40">{item.treatment_name}</p>
                    </div>
                    <div className="text-right ml-3">
                      <p className="text-sm font-semibold text-white">{formatCurrency(item.amount_pending)}</p>
                      <p className={`text-[11px] font-medium ${getDaysOverdueColor(item.days_overdue)}`}>
                        {item.days_overdue} {t('finance.days_overdue')}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-8 text-center text-white/30 text-sm">
                {t('finance.no_pending')}
              </div>
            )}
          </div>
        </GlassCard>
      </div>
    </div>
  );
}
