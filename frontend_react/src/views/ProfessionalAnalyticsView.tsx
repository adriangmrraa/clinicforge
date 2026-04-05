import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, PieChart, Pie, Cell } from 'recharts';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import {
  Zap, Crown, Award, TrendingUp, AlertTriangle, BarChart3,
  DollarSign, CalendarCheck, Users, UserCheck, XCircle, Clock,
  Target, ArrowUpRight, ArrowDownRight, Percent, Star, Activity
} from 'lucide-react';
import AnalyticsFilters from '../components/analytics/AnalyticsFilters';
import PageHeader from '../components/PageHeader';
import GlassCard, { CARD_IMAGES } from '../components/GlassCard';
import LiquidationTab from '../components/analytics/LiquidationTab';

interface MetricData {
  id: number;
  name: string;
  specialty: string;
  metrics: {
    total_appointments: number;
    completion_rate: number;
    cancellation_rate: number;
    no_show_rate: number;
    revenue: number;
    avg_revenue_per_appointment: number;
    retention_rate: number;
    unique_patients: number;
    paid_appointments: number;
    partial_payments: number;
  };
  top_treatment: { name: string; count: number };
  busiest_day: string;
  tags: string[];
}

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#06b6d4', '#84cc16'];

export default function ProfessionalAnalyticsView() {
  const { t } = useTranslation();
  const [data, setData] = useState<MetricData[]>([]);
  const [filters, setFilters] = useState({ startDate: '', endDate: '', professionalIds: [] as number[] });
  const [searchParams, setSearchParams] = useSearchParams();
  const activeTab = searchParams.get('tab') === 'liquidacion' ? 'liquidacion' : 'rendimiento';
  const switchTab = (tab: string) => {
    setSearchParams(prev => { prev.set('tab', tab); return prev; }, { replace: true });
  };

  const fetchData = async () => {
    if (!filters.startDate || !filters.endDate) return;
    try {
      const params = new URLSearchParams({ start_date: filters.startDate, end_date: filters.endDate });
      const response = await api.get(`/admin/analytics/professionals/summary?${params}`);
      let filteredData = response.data;
      if (filters.professionalIds.length > 0) {
        filteredData = filteredData.filter((d: MetricData) => filters.professionalIds.includes(d.id));
      }
      setData(filteredData);
    } catch (error) {
      console.error("Error fetching analytics", error);
    }
  };

  useEffect(() => { fetchData(); }, [filters]);

  // Aggregated stats
  const totalRevenue = data.reduce((acc, c) => acc + c.metrics.revenue, 0);
  const totalAppointments = data.reduce((acc, c) => acc + c.metrics.total_appointments, 0);
  const totalPatients = data.reduce((acc, c) => acc + c.metrics.unique_patients, 0);
  const avgCompletion = data.length ? data.reduce((acc, c) => acc + c.metrics.completion_rate, 0) / data.length : 0;
  const avgNoShow = data.length ? data.reduce((acc, c) => acc + (c.metrics.no_show_rate || 0), 0) / data.length : 0;
  const avgCancellation = data.length ? data.reduce((acc, c) => acc + c.metrics.cancellation_rate, 0) / data.length : 0;
  const avgRetention = data.length ? data.reduce((acc, c) => acc + c.metrics.retention_rate, 0) / data.length : 0;
  const totalPaid = data.reduce((acc, c) => acc + (c.metrics.paid_appointments || 0), 0);

  // Treatment distribution
  const treatmentDist = data
    .filter(d => d.top_treatment && d.top_treatment.name !== 'N/A')
    .map(d => ({ name: d.top_treatment.name, value: d.top_treatment.count, professional: d.name }));

  // Chart data for comparison
  const chartData = data.map(d => ({
    name: d.name.split(' ')[0],
    completionRate: d.metrics.completion_rate,
    retentionRate: d.metrics.retention_rate,
    noShowRate: d.metrics.no_show_rate || 0,
    revenue: d.metrics.revenue,
  }));

  const getTagBadge = (tag: string) => {
    const styles: Record<string, string> = {
      'High Performance': 'bg-purple-500/10 text-purple-400 border-purple-500/20',
      'Retention Master': 'bg-green-500/10 text-green-400 border-green-500/20',
      'Top Revenue': 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
      'Risk: Cancellations': 'bg-red-500/10 text-red-400 border-red-500/20',
      'Risk: No-Shows': 'bg-orange-500/10 text-orange-400 border-orange-500/20',
      'High Ticket': 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    };
    const icons: Record<string, JSX.Element> = {
      'High Performance': <Zap size={11} />,
      'Retention Master': <Crown size={11} />,
      'Top Revenue': <Award size={11} />,
      'Risk: Cancellations': <AlertTriangle size={11} />,
      'Risk: No-Shows': <AlertTriangle size={11} />,
      'High Ticket': <DollarSign size={11} />,
    };
    const tagKeys: Record<string, string> = {
      'High Performance': 'analytics.tag_high_performance',
      'Retention Master': 'analytics.tag_retention_master',
      'Top Revenue': 'analytics.tag_top_revenue',
      'Risk: Cancellations': 'analytics.tag_risk_cancellations',
      'Risk: No-Shows': 'analytics.tag_risk_no_shows',
      'High Ticket': 'analytics.tag_high_ticket',
    };
    return (
      <span key={tag} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${styles[tag] || 'bg-white/[0.04] text-white/60 border-white/[0.06]'}`}>
        {icons[tag]} {t(tagKeys[tag] || tag)}
      </span>
    );
  };

  const KPI = ({ icon, label, value, sub, color, trend, image }: { icon: JSX.Element; label: string; value: string | number; sub?: string; color: string; trend?: 'up' | 'down' | null; image?: string }) => (
    <GlassCard image={image}>
      <div className="p-4 sm:p-5">
        <div className="flex items-start justify-between mb-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>{icon}</div>
          {trend && (
            <span className={`flex items-center gap-0.5 text-xs font-semibold ${trend === 'up' ? 'text-green-400' : 'text-red-400'}`}>
              {trend === 'up' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
            </span>
          )}
        </div>
        <p className="text-2xl font-bold text-white tracking-tight">{value}</p>
        <p className="text-xs text-white/40 mt-0.5">{label}</p>
        {sub && <p className="text-[10px] text-white/30 mt-1">{sub}</p>}
      </div>
    </GlassCard>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden">
      <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-5">
        <PageHeader
          title={t('analytics.strategic_title')}
          subtitle={t('analytics.strategic_subtitle')}
          icon={<BarChart3 size={22} />}
          action={<span className="text-xs text-white/30">{t('analytics.realtime_data')}</span>}
        />

        <AnalyticsFilters onFilterChange={setFilters} />

        {/* Tab Bar */}
        <div className="flex gap-1 mb-6 border-b border-white/[0.06]">
          <button
            onClick={() => switchTab('rendimiento')}
            className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
              activeTab === 'rendimiento'
                ? 'text-white'
                : 'text-white/40 hover:text-white/60'
            }`}
          >
            {t('liquidation.tab_rendimiento')}
            {activeTab === 'rendimiento' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-white rounded-full" />
            )}
          </button>
          <button
            onClick={() => switchTab('liquidacion')}
            className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${
              activeTab === 'liquidacion'
                ? 'text-white'
                : 'text-white/40 hover:text-white/60'
            }`}
          >
            {t('liquidation.tab_liquidacion')}
            {activeTab === 'liquidacion' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-white rounded-full" />
            )}
          </button>
        </div>

        {activeTab === 'rendimiento' && (
        <>

        {/* KPI Grid — 8 cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          <KPI icon={<DollarSign size={20} className="text-green-400" />} label={t('analytics.estimated_revenue')} value={`$${totalRevenue.toLocaleString()}`} sub={`${totalPaid} ${t('analytics.paid_appointments')}`} color="bg-green-500/10" trend={totalRevenue > 0 ? 'up' : null} image={CARD_IMAGES.revenue} />
          <KPI icon={<CalendarCheck size={20} className="text-blue-400" />} label={t('analytics.total_appointments')} value={totalAppointments} sub={`${totalPatients} ${t('analytics.patients')}`} color="bg-blue-500/10" image={CARD_IMAGES.appointments} />
          <KPI icon={<Percent size={20} className="text-purple-400" />} label={t('analytics.completion_rate')} value={`${avgCompletion.toFixed(0)}%`} sub={`${avgCancellation.toFixed(0)}% ${t('analytics.cancellations')}`} color="bg-purple-500/10" trend={avgCompletion > 80 ? 'up' : 'down'} image={CARD_IMAGES.completion} />
          <KPI icon={<UserCheck size={20} className="text-emerald-400" />} label={t('analytics.retention_rate')} value={`${avgRetention.toFixed(0)}%`} sub={t('analytics.patients_come_back')} color="bg-emerald-500/10" trend={avgRetention > 50 ? 'up' : null} image={CARD_IMAGES.patients} />
          <KPI icon={<XCircle size={20} className="text-red-400" />} label={t('analytics.no_shows')} value={`${avgNoShow.toFixed(1)}%`} sub={t('analytics.team_average')} color="bg-red-500/10" trend={avgNoShow > 10 ? 'down' : 'up'} image={CARD_IMAGES.analytics} />
          <KPI icon={<Target size={20} className="text-amber-400" />} label={t('analytics.avg_ticket')} value={`$${totalAppointments > 0 ? Math.round(totalRevenue / totalAppointments).toLocaleString() : 0}`} sub={t('analytics.per_appointment')} color="bg-amber-500/10" image={CARD_IMAGES.revenue} />
          <KPI icon={<Users size={20} className="text-indigo-400" />} label={t('analytics.active_professionals')} value={data.length} sub={`${data.map(d => d.specialty).filter((v, i, a) => a.indexOf(v) === i).length} ${t('analytics.specialties')}`} color="bg-indigo-500/10" image={CARD_IMAGES.team} />
          <KPI icon={<Star size={20} className="text-pink-400" />} label={t('analytics.best_professional')} value={data.length > 0 ? data.sort((a, b) => b.metrics.revenue - a.metrics.revenue)[0]?.name.split(' ')[0] || '-' : '-'} sub={t('analytics.by_revenue')} color="bg-pink-500/10" image={CARD_IMAGES.profile} />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Performance Comparison Chart */}
          <GlassCard image={CARD_IMAGES.analytics} className="lg:col-span-2" hoverScale={false}>
            <div className="p-5">
              <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                <Activity size={16} className="text-blue-400" /> {t('analytics.comparative_performance')}
              </h3>
              <div className="h-72">
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.06)" />
                      <XAxis dataKey="name" tick={{ fontSize: 11, fill: 'rgba(255,255,255,0.4)' }} stroke="rgba(255,255,255,0.1)" />
                      <YAxis tick={{ fontSize: 11, fill: 'rgba(255,255,255,0.4)' }} stroke="rgba(255,255,255,0.1)" />
                      <Tooltip
                        contentStyle={{ borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(10,14,26,0.9)', boxShadow: '0 4px 12px rgba(0,0,0,0.3)', fontSize: '12px', color: '#fff' }}
                      />
                      <Bar dataKey="completionRate" name={t('analytics.attendance_pct')} fill="#3b82f6" radius={[6, 6, 0, 0]} barSize={16} />
                      <Bar dataKey="retentionRate" name={t('analytics.retention_pct')} fill="#10b981" radius={[6, 6, 0, 0]} barSize={16} />
                      <Bar dataKey="noShowRate" name={t('analytics.no_show_pct')} fill="#ef4444" radius={[6, 6, 0, 0]} barSize={16} />
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-full flex items-center justify-center text-white/30 text-sm">{t('analytics.select_date_range')}</div>
                )}
              </div>
            </div>
          </GlassCard>

          {/* Treatment Distribution */}
          <GlassCard image={CARD_IMAGES.dental} hoverScale={false}>
            <div className="p-5">
              <h3 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                <Target size={16} className="text-amber-400" /> {t('analytics.top_treatment_by_prof')}
              </h3>
              {treatmentDist.length > 0 ? (
                <>
                  <div className="h-44">
                    <ResponsiveContainer width="100%" height="100%">
                      <PieChart>
                        <Pie data={treatmentDist} cx="50%" cy="50%" innerRadius={40} outerRadius={70} dataKey="value" paddingAngle={3}>
                          {treatmentDist.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                        </Pie>
                        <Tooltip contentStyle={{ borderRadius: '12px', border: '1px solid rgba(255,255,255,0.1)', background: 'rgba(10,14,26,0.9)', boxShadow: '0 4px 12px rgba(0,0,0,0.3)', fontSize: '12px', color: '#fff' }} />
                      </PieChart>
                    </ResponsiveContainer>
                  </div>
                  <div className="space-y-2 mt-2">
                    {treatmentDist.map((item, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                          <span className="text-white/60 truncate max-w-[120px]">{item.name}</span>
                        </div>
                        <span className="text-white/40 font-medium">{item.value} {t('analytics.appointments')}</span>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <div className="h-44 flex items-center justify-center text-white/30 text-sm">{t('analytics.no_data_short')}</div>
              )}
            </div>
          </GlassCard>
        </div>

        {/* Professional Detail Cards — 2 columns on desktop */}
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2 mb-3">
            <TrendingUp size={16} className="text-blue-400" /> {t('analytics.professional_detail')}
          </h3>
          {data.length === 0 && (
            <GlassCard image={CARD_IMAGES.team} hoverScale={false}>
              <div className="p-8 text-center text-white/30 text-sm">
                {t('analytics.select_dates_to_see')}
              </div>
            </GlassCard>
          )}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {data.map((prof) => (
            <GlassCard key={prof.id} image={CARD_IMAGES.team}>
              <div className="p-4 sm:p-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-white font-bold text-lg shrink-0">
                      {prof.name.charAt(0)}
                    </div>
                    <div>
                      <h4 className="font-bold text-white">{prof.name}</h4>
                      <p className="text-xs text-white/40">{prof.specialty}</p>
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1">
                    {prof.tags.length > 0 ? prof.tags.map(tag => getTagBadge(tag)) : <span className="text-[10px] text-white/30">{t('analytics.no_tags')}</span>}
                  </div>
                </div>

                {/* Metrics grid */}
                <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                  <div className="text-center p-2 rounded-xl bg-white/[0.04]">
                    <p className="text-lg font-bold text-white">{prof.metrics.total_appointments}</p>
                    <p className="text-[10px] text-white/40">{t('analytics.appointments')}</p>
                  </div>
                  <div className="text-center p-2 rounded-xl bg-white/[0.04]">
                    <p className="text-lg font-bold text-green-400">${prof.metrics.revenue.toLocaleString()}</p>
                    <p className="text-[10px] text-white/40">{t('analytics.billed')}</p>
                  </div>
                  <div className="text-center p-2 rounded-xl bg-white/[0.04]">
                    <p className={`text-lg font-bold ${prof.metrics.completion_rate > 80 ? 'text-blue-400' : 'text-orange-400'}`}>{prof.metrics.completion_rate}%</p>
                    <p className="text-[10px] text-white/40">{t('analytics.attendance')}</p>
                  </div>
                  <div className="text-center p-2 rounded-xl bg-white/[0.04]">
                    <p className={`text-lg font-bold ${(prof.metrics.no_show_rate || 0) < 10 ? 'text-green-400' : 'text-red-400'}`}>{prof.metrics.no_show_rate || 0}%</p>
                    <p className="text-[10px] text-white/40">{t('analytics.no_show')}</p>
                  </div>
                  <div className="text-center p-2 rounded-xl bg-white/[0.04]">
                    <p className={`text-lg font-bold ${prof.metrics.retention_rate > 50 ? 'text-emerald-400' : 'text-white/60'}`}>{prof.metrics.retention_rate}%</p>
                    <p className="text-[10px] text-white/40">{t('analytics.retention_rate')}</p>
                  </div>
                  <div className="text-center p-2 rounded-xl bg-white/[0.04]">
                    <p className="text-lg font-bold text-white">{prof.metrics.unique_patients}</p>
                    <p className="text-[10px] text-white/40">{t('analytics.patients')}</p>
                  </div>
                </div>

                {/* Extra info row */}
                <div className="flex flex-wrap gap-4 mt-3 pt-3 border-t border-white/[0.06] text-xs text-white/40">
                  {prof.top_treatment?.name !== 'N/A' && (
                    <span>{t('analytics.top_treatment')}: <strong className="text-white/60">{prof.top_treatment.name}</strong> ({prof.top_treatment.count})</span>
                  )}
                  {prof.busiest_day !== 'N/A' && (
                    <span>{t('analytics.busiest_day')}: <strong className="text-white/60">{prof.busiest_day}</strong></span>
                  )}
                  {prof.metrics.avg_revenue_per_appointment > 0 && (
                    <span>{t('analytics.avg_ticket_short')}: <strong className="text-white/60">${prof.metrics.avg_revenue_per_appointment.toLocaleString()}</strong></span>
                  )}
                  {prof.metrics.paid_appointments > 0 && (
                    <span>{t('analytics.paid_short')}: <strong className="text-green-400">{prof.metrics.paid_appointments}</strong></span>
                  )}
                </div>
              </div>
            </GlassCard>
          ))}
          </div>
        </div>

        </>
        )}

        {activeTab === 'liquidacion' && (
          <LiquidationTab
            startDate={filters.startDate}
            endDate={filters.endDate}
            professionalIds={filters.professionalIds}
          />
        )}

      </div>
    </div>
  );
}
