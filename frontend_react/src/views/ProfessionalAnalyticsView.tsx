import { useState, useEffect } from 'react';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';
import { Zap, Crown, Award, TrendingUp, AlertTriangle, BarChart3 } from 'lucide-react';
import KPICard from '../components/analytics/KPICard';
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
        revenue: number;
        retention_rate: number;
        unique_patients: number;
    };
    tags: string[];
}

export default function ProfessionalAnalyticsView() {
    const { t } = useTranslation();
    const [data, setData] = useState<MetricData[]>([]);
    const [filters, setFilters] = useState({ startDate: '', endDate: '', professionalIds: [] as number[] });

    const fetchData = async () => {
        if (!filters.startDate || !filters.endDate) return;

        try {
            const params = new URLSearchParams({
                start_date: filters.startDate,
                end_date: filters.endDate
            });
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

    useEffect(() => {
        fetchData();
    }, [filters]);

    // Aggregated Stats for Cards
    const totalRevenue = data.reduce((acc, curr) => acc + curr.metrics.revenue, 0);
    const totalAppointments = data.reduce((acc, curr) => acc + curr.metrics.total_appointments, 0);
    const avgCompletion = data.length ? data.reduce((acc, curr) => acc + curr.metrics.completion_rate, 0) / data.length : 0;
    const totalPatients = data.reduce((acc, curr) => acc + curr.metrics.unique_patients, 0);

    const getTagBadge = (tag: string) => {
        switch (tag) {
            case 'High Performance':
                return <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-purple-100 text-purple-800"><Zap size={12} /> High Perf</span>;
            case 'Retention Master':
                return <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800"><Crown size={12} /> Customer Love</span>;
            case 'Top Revenue':
                return <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800"><Award size={12} /> Rainmaker</span>;
            case 'Risk: Cancellations':
                return <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800"><AlertTriangle size={12} /> Risk</span>;
            default:
                return <span className="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-800">{tag}</span>;
        }
    };

    return (
        <div className="flex flex-col h-full overflow-hidden bg-slate-50">
            <div className="flex-1 min-h-0 overflow-y-auto p-4 sm:p-6">
                <PageHeader
                    title={t('analytics.strategic_title')}
                    subtitle={t('analytics.strategic_subtitle')}
                    icon={<BarChart3 size={22} />}
                    action={
                        <span className="text-xs sm:text-sm text-slate-500">{t('analytics.realtime_data')}</span>
                    }
                />

                <AnalyticsFilters onFilterChange={setFilters} />

            {/* KPI Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <KPICard
                    title={t('analytics.estimated_revenue')}
                    value={`$${totalRevenue.toLocaleString()}`}
                    icon="money"
                    color="green"
                    subtext={t('analytics.total_period')}
                />
                <KPICard
                    title={t('analytics.total_appointments')}
                    value={totalAppointments}
                    icon="calendar"
                    color="blue"
                    subtext={t('analytics.unique_patients').replace('{{count}}', String(totalPatients))}
                />
                <KPICard
                    title={t('analytics.completion_rate')}
                    value={`${avgCompletion.toFixed(1)}%`}
                    icon="activity"
                    color="purple"
                    subtext={t('analytics.avg_overall')}
                />
                <KPICard
                    title={t('analytics.active_professionals')}
                    value={data.length}
                    icon="users"
                    color="orange"
                />
                </div>

                {/* Main Content Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                {/* Chart Section */}
                    <div className="lg:col-span-2 bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
                    <h3 className="text-lg font-bold text-slate-800 mb-4">{t('analytics.comparative_performance')}</h3>
                    <div className="h-80">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                                <XAxis type="number" />
                                <YAxis dataKey="name" type="category" width={100} tick={{ fontSize: 12 }} />
                                <Tooltip
                                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)' }}
                                />
                                <Bar dataKey="completionRate" name={t('analytics.completion_rate')} fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={20} />
                                <Bar dataKey="retentionRate" name={t('analytics.retention_rate')} fill="#10b981" radius={[4, 4, 0, 0]} barSize={20} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                    </div>

                    {/* Top Performers / Strategic Insights */}
                    <div className="bg-white rounded-2xl border border-slate-100 shadow-sm p-5">
                    <h3 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
                        <TrendingUp className="text-medical-500" /> {t('analytics.insights')}
                    </h3>
                    <div className="space-y-4">
                        {data.slice(0, 5).map((prof) => (
                            <div key={prof.id} className="flex items-start gap-3 p-3 rounded-xl hover:bg-slate-50 transition-colors">
                                <div className="w-10 h-10 rounded-full bg-medical-100 flex items-center justify-center text-medical-700 font-bold shrink-0">
                                    {prof.name.charAt(0)}
                                </div>
                                <div>
                                    <h4 className="font-medium text-slate-900 text-sm">{prof.name}</h4>
                                    <p className="text-xs text-slate-500 mb-2">{prof.specialty}</p>
                                    <div className="flex flex-wrap gap-1">
                                        {prof.tags.length > 0 ? prof.tags.map(tag => getTagBadge(tag)) : <span className="text-xs text-gray-400">{t('analytics.no_tags')}</span>}
                                    </div>
                                </div>
                            </div>
                        ))}
                        {data.length === 0 && <p className="text-sm text-slate-400 text-center py-4">{t('analytics.no_data')}</p>}
                    </div>
                    </div>
                </div>

                {/* Detailed Table */}
                <div className="bg-white rounded-2xl border border-slate-100 shadow-sm overflow-hidden">
                <div className="p-4 sm:p-6 border-b border-slate-100">
                    <h3 className="text-lg font-bold text-slate-800">{t('analytics.operational_detail')}</h3>
                </div>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead className="bg-slate-50">
                            <tr>
                                <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{t('analytics.professional')}</th>
                                <th className="px-4 sm:px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">{t('analytics.appointments')}</th>
                                <th className="px-4 sm:px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">{t('analytics.completion')}</th>
                                <th className="px-4 sm:px-6 py-3 text-center text-xs font-medium text-slate-500 uppercase tracking-wider">{t('analytics.retention')}</th>
                                <th className="px-4 sm:px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">{t('analytics.revenue_est')}</th>
                                <th className="px-4 sm:px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">{t('analytics.tags')}</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {data.map((prof) => (
                                <tr key={prof.id} className="hover:bg-slate-50/80">
                                    <td className="px-4 sm:px-6 py-4 whitespace-nowrap">
                                        <div className="text-sm font-medium text-slate-900">{prof.name}</div>
                                        <div className="text-xs text-slate-500">{prof.specialty}</div>
                                    </td>
                                    <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-center text-sm text-slate-600">
                                        {prof.metrics.total_appointments}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-center">
                                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${prof.metrics.completion_rate > 90 ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'
                                            }`}>
                                            {prof.metrics.completion_rate}%
                                        </span>
                                    </td>
                                    <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-center text-sm text-slate-600">
                                        {prof.metrics.retention_rate}%
                                    </td>
                                    <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-right text-sm text-slate-900 font-medium">
                                        ${prof.metrics.revenue.toLocaleString()}
                                    </td>
                                    <td className="px-4 sm:px-6 py-4 whitespace-nowrap text-sm text-slate-500">
                                        <div className="flex gap-1 flex-wrap">
                                            {prof.tags.map(tag => getTagBadge(tag))}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                </div>

            </div>
        </div>
    );
}
