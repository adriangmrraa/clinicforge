import { useState, useEffect } from 'react';
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
      'High Performance': 'bg-purple-50 text-purple-700 border-purple-200',
      'Retention Master': 'bg-green-50 text-green-700 border-green-200',
      'Top Revenue': 'bg-yellow-50 text-yellow-700 border-yellow-200',
      'Risk: Cancellations': 'bg-red-50 text-red-700 border-red-200',
      'Risk: No-Shows': 'bg-orange-50 text-orange-700 border-orange-200',
      'High Ticket': 'bg-blue-50 text-blue-700 border-blue-200',
    };
    const icons: Record<string, JSX.Element> = {
      'High Performance': <Zap size={11} />,
      'Retention Master': <Crown size={11} />,
      'Top Revenue': <Award size={11} />,
      'Risk: Cancellations': <AlertTriangle size={11} />,
      'Risk: No-Shows': <AlertTriangle size={11} />,
      'High Ticket': <DollarSign size={11} />,
    };
    return (
      <span key={tag} className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold border ${styles[tag] || 'bg-gray-50 text-gray-600 border-gray-200'}`}>
        {icons[tag]} {tag}
      </span>
    );
  };

  const KPI = ({ icon, label, value, sub, color, trend }: { icon: JSX.Element; label: string; value: string | number; sub?: string; color: string; trend?: 'up' | 'down' | null }) => (
    <div className={`bg-white rounded-2xl border border-slate-100 shadow-sm p-4 sm:p-5 hover:shadow-md transition-shadow`}>
      <div className="flex items-start justify-between mb-3">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color}`}>{icon}</div>
        {trend && (
          <span className={`flex items-center gap-0.5 text-xs font-semibold ${trend === 'up' ? 'text-green-600' : 'text-red-500'}`}>
            {trend === 'up' ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
          </span>
        )}
      </div>
      <p className="text-2xl font-bold text-slate-900 tracking-tight">{value}</p>
      <p className="text-xs text-slate-500 mt-0.5">{label}</p>
      {sub && <p className="text-[10px] text-slate-400 mt-1">{sub}</p>}
    </div>
  );

  return (
    <div className="flex flex-col h-full overflow-hidden bg-slate-50">
      <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6 space-y-5">
        <PageHeader
          title={t('analytics.strategic_title')}
          subtitle={t('analytics.strategic_subtitle')}
          icon={<BarChart3 size={22} />}
          action={<span className="text-xs text-slate-400">{t('analytics.realtime_data')}</span>}
        />

        <AnalyticsFilters onFilterChange={setFilters} />

        {/* KPI Grid — 8 cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          <KPI icon={<DollarSign size={20} className="text-green-600" />} label="Ingresos estimados" value={`$${totalRevenue.toLocaleString()}`} sub={`${totalPaid} turnos pagados`} color="bg-green-50" trend={totalRevenue > 0 ? 'up' : null} />
          <KPI icon={<CalendarCheck size={20} className="text-blue-600" />} label="Turnos totales" value={totalAppointments} sub={`${totalPatients} pacientes unicos`} color="bg-blue-50" />
          <KPI icon={<Percent size={20} className="text-purple-600" />} label="Tasa de asistencia" value={`${avgCompletion.toFixed(0)}%`} sub={`${avgCancellation.toFixed(0)}% cancelaciones`} color="bg-purple-50" trend={avgCompletion > 80 ? 'up' : 'down'} />
          <KPI icon={<UserCheck size={20} className="text-emerald-600" />} label="Retencion" value={`${avgRetention.toFixed(0)}%`} sub="Pacientes que vuelven" color="bg-emerald-50" trend={avgRetention > 50 ? 'up' : null} />
          <KPI icon={<XCircle size={20} className="text-red-500" />} label="No-shows" value={`${avgNoShow.toFixed(1)}%`} sub="Promedio del equipo" color="bg-red-50" trend={avgNoShow > 10 ? 'down' : 'up'} />
          <KPI icon={<Target size={20} className="text-amber-600" />} label="Ticket promedio" value={`$${totalAppointments > 0 ? Math.round(totalRevenue / totalAppointments).toLocaleString() : 0}`} sub="Por turno" color="bg-amber-50" />
          <KPI icon={<Users size={20} className="text-indigo-600" />} label="Profesionales activos" value={data.length} sub={data.map(d => d.specialty).filter((v, i, a) => a.indexOf(v) === i).length + ' especialidades'} color="bg-indigo-50" />
          <KPI icon={<Star size={20} className="text-pink-600" />} label="Mejor profesional" value={data.length > 0 ? data.sort((a, b) => b.metrics.revenue - a.metrics.revenue)[0]?.name.split(' ')[0] || '-' : '-'} sub="Por facturacion" color="bg-pink-50" />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Performance Comparison Chart */}
          <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
            <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Activity size={16} className="text-blue-500" /> Rendimiento comparativo
            </h3>
            <div className="h-72">
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                    <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: '12px' }}
                    />
                    <Bar dataKey="completionRate" name="Asistencia %" fill="#3b82f6" radius={[6, 6, 0, 0]} barSize={16} />
                    <Bar dataKey="retentionRate" name="Retencion %" fill="#10b981" radius={[6, 6, 0, 0]} barSize={16} />
                    <Bar dataKey="noShowRate" name="No-show %" fill="#ef4444" radius={[6, 6, 0, 0]} barSize={16} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex items-center justify-center text-slate-400 text-sm">Selecciona un rango de fechas</div>
              )}
            </div>
          </div>

          {/* Treatment Distribution */}
          <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
            <h3 className="text-sm font-bold text-slate-800 mb-4 flex items-center gap-2">
              <Target size={16} className="text-amber-500" /> Tratamiento top por profesional
            </h3>
            {treatmentDist.length > 0 ? (
              <>
                <div className="h-44">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={treatmentDist} cx="50%" cy="50%" innerRadius={40} outerRadius={70} dataKey="value" paddingAngle={3}>
                        {treatmentDist.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                      </Pie>
                      <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)', fontSize: '12px' }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="space-y-2 mt-2">
                  {treatmentDist.map((t, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: COLORS[i % COLORS.length] }} />
                        <span className="text-slate-700 truncate max-w-[120px]">{t.name}</span>
                      </div>
                      <span className="text-slate-500 font-medium">{t.value} turnos</span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="h-44 flex items-center justify-center text-slate-400 text-sm">Sin datos</div>
            )}
          </div>
        </div>

        {/* Professional Detail Cards */}
        <div className="space-y-3">
          <h3 className="text-sm font-bold text-slate-800 flex items-center gap-2">
            <TrendingUp size={16} className="text-blue-500" /> Detalle por profesional
          </h3>
          {data.length === 0 && (
            <div className="bg-white rounded-2xl border border-slate-100 p-8 text-center text-slate-400 text-sm">
              Selecciona un rango de fechas para ver las metricas
            </div>
          )}
          {data.map((prof) => (
            <div key={prof.id} className="bg-white rounded-2xl border border-slate-100 shadow-sm p-4 sm:p-5 hover:shadow-md transition-shadow">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center text-white font-bold text-lg shrink-0">
                    {prof.name.charAt(0)}
                  </div>
                  <div>
                    <h4 className="font-bold text-slate-900">{prof.name}</h4>
                    <p className="text-xs text-slate-500">{prof.specialty}</p>
                  </div>
                </div>
                <div className="flex flex-wrap gap-1">
                  {prof.tags.length > 0 ? prof.tags.map(tag => getTagBadge(tag)) : <span className="text-[10px] text-slate-400">Sin tags</span>}
                </div>
              </div>

              {/* Metrics grid */}
              <div className="grid grid-cols-3 sm:grid-cols-6 gap-3">
                <div className="text-center p-2 rounded-xl bg-slate-50">
                  <p className="text-lg font-bold text-slate-900">{prof.metrics.total_appointments}</p>
                  <p className="text-[10px] text-slate-500">Turnos</p>
                </div>
                <div className="text-center p-2 rounded-xl bg-slate-50">
                  <p className="text-lg font-bold text-green-600">${prof.metrics.revenue.toLocaleString()}</p>
                  <p className="text-[10px] text-slate-500">Facturado</p>
                </div>
                <div className="text-center p-2 rounded-xl bg-slate-50">
                  <p className={`text-lg font-bold ${prof.metrics.completion_rate > 80 ? 'text-blue-600' : 'text-orange-600'}`}>{prof.metrics.completion_rate}%</p>
                  <p className="text-[10px] text-slate-500">Asistencia</p>
                </div>
                <div className="text-center p-2 rounded-xl bg-slate-50">
                  <p className={`text-lg font-bold ${(prof.metrics.no_show_rate || 0) < 10 ? 'text-green-600' : 'text-red-600'}`}>{prof.metrics.no_show_rate || 0}%</p>
                  <p className="text-[10px] text-slate-500">No-show</p>
                </div>
                <div className="text-center p-2 rounded-xl bg-slate-50">
                  <p className={`text-lg font-bold ${prof.metrics.retention_rate > 50 ? 'text-emerald-600' : 'text-slate-600'}`}>{prof.metrics.retention_rate}%</p>
                  <p className="text-[10px] text-slate-500">Retencion</p>
                </div>
                <div className="text-center p-2 rounded-xl bg-slate-50">
                  <p className="text-lg font-bold text-slate-900">{prof.metrics.unique_patients}</p>
                  <p className="text-[10px] text-slate-500">Pacientes</p>
                </div>
              </div>

              {/* Extra info row */}
              <div className="flex flex-wrap gap-4 mt-3 pt-3 border-t border-slate-100 text-xs text-slate-500">
                {prof.top_treatment?.name !== 'N/A' && (
                  <span>Top: <strong className="text-slate-700">{prof.top_treatment.name}</strong> ({prof.top_treatment.count})</span>
                )}
                {prof.busiest_day !== 'N/A' && (
                  <span>Dia mas activo: <strong className="text-slate-700">{prof.busiest_day}</strong></span>
                )}
                {prof.metrics.avg_revenue_per_appointment > 0 && (
                  <span>Ticket prom: <strong className="text-slate-700">${prof.metrics.avg_revenue_per_appointment.toLocaleString()}</strong></span>
                )}
                {prof.metrics.paid_appointments > 0 && (
                  <span>Pagados: <strong className="text-green-700">{prof.metrics.paid_appointments}</strong></span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
