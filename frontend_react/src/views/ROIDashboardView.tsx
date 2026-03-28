import { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp,
  DollarSign,
  Users,
  Target,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
  Info,
} from 'lucide-react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  Legend,
} from 'recharts';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

type Period = 'last_7d' | 'last_30d' | 'last_90d' | 'this_year';

interface ExecutiveSummary {
  total_spend: number;
  total_revenue: number;
  roi_percentage: number;
  total_leads: number;
  total_conversions: number;
  conversion_rate: number;
  cost_per_lead: number;
  cost_per_conversion: number;
  top_campaign: { name: string; patients: number } | null;
  data_source: 'meta_api' | 'estimated';
  currency: string;
  platforms: string[];
}

interface TrendDataPoint {
  period: string;
  total_patients: number;
  total_leads: number;
  converted_leads: number;
  conversion_rate: number;
}

interface AttributionMix {
  first_touch_percentage: number;
  last_touch_percentage: number;
  conversion_percentage: number;
  organic_percentage: number;
  total_patients: number;
}

interface TopCampaign {
  campaign_name: string;
  total_patients: number;
  total_leads: number;
  converted_leads: number;
  conversion_rate: number;
}

const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#6b7280'];

function KPICard({
  label,
  value,
  prefix,
  suffix,
  icon,
  trend,
}: {
  label: string;
  value: string | number;
  prefix?: string;
  suffix?: string;
  icon: React.ReactNode;
  trend?: 'up' | 'down' | 'neutral';
}) {
  return (
    <div className="bg-white/[0.04] border border-white/[0.06] rounded-xl p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-white/50 text-xs uppercase tracking-wider">{label}</span>
        <div className="text-white/30">{icon}</div>
      </div>
      <div className="flex items-end gap-1">
        {prefix && <span className="text-white/50 text-sm">{prefix}</span>}
        <span className="text-2xl font-bold text-white">{value}</span>
        {suffix && <span className="text-white/50 text-sm">{suffix}</span>}
        {trend === 'up' && <ArrowUpRight size={16} className="text-green-400 ml-1" />}
        {trend === 'down' && <ArrowDownRight size={16} className="text-red-400 ml-1" />}
      </div>
    </div>
  );
}

export default function ROIDashboardView() {
  const { t } = useTranslation();
  const [period, setPeriod] = useState<Period>('last_30d');
  const [isLoading, setIsLoading] = useState(false);

  const [summary, setSummary] = useState<ExecutiveSummary | null>(null);
  const [trendData, setTrendData] = useState<TrendDataPoint[]>([]);
  const [attributionMix, setAttributionMix] = useState<AttributionMix | null>(null);
  const [topCampaigns, setTopCampaigns] = useState<TopCampaign[]>([]);
  const [comparison, setComparison] = useState<any>(null);

  const periodMap: Record<Period, string> = {
    last_7d: 'weekly',
    last_30d: 'monthly',
    last_90d: 'quarterly',
    this_year: 'yearly',
  };

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.allSettled([
        api.get(`/admin/metrics/executive-summary?period=${period}`).then(r => setSummary(r.data)),
        api.get(`/admin/metrics/trend?period=${periodMap[period]}`).then(r => setTrendData(r.data?.trend_data || [])),
        api.get(`/admin/metrics/attribution/mix?period=${periodMap[period]}`).then(r => setAttributionMix(r.data?.attribution_mix || null)),
        api.get(`/admin/metrics/top/campaigns?period=${periodMap[period]}`).then(r => setTopCampaigns(r.data?.top_campaigns || [])),
        api.get(`/admin/metrics/comparison/first-vs-last?period=${periodMap[period]}`).then(r => setComparison(r.data?.comparison || null)),
      ]);
    } catch (err) {
      console.error('ROI load error:', err);
    } finally {
      setIsLoading(false);
    }
  }, [period]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const pieData = attributionMix
    ? [
        { name: t('roi.first_touch'), value: attributionMix.first_touch_percentage },
        { name: t('roi.last_touch'), value: attributionMix.last_touch_percentage },
        { name: t('roi.conversion'), value: attributionMix.conversion_percentage },
        { name: t('roi.organic'), value: attributionMix.organic_percentage },
      ].filter(d => d.value > 0)
    : [];

  const fmt = (n: number) =>
    n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n.toFixed(n % 1 === 0 ? 0 : 2);

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06] shrink-0">
        <div className="flex items-center gap-3">
          <TrendingUp size={22} className="text-blue-400" />
          <h1 className="text-xl font-bold text-white">{t('roi.title')}</h1>
          {summary?.data_source === 'meta_api' && (
            <span className="text-[10px] bg-green-500/10 text-green-400 px-2 py-0.5 rounded-full">
              {t('roi.real_data_badge')}
            </span>
          )}
          {summary?.data_source === 'estimated' && (
            <span className="text-[10px] bg-yellow-500/10 text-yellow-400 px-2 py-0.5 rounded-full flex items-center gap-1">
              <Info size={10} />
              {t('roi.estimated_data_badge')}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {(['last_7d', 'last_30d', 'last_90d', 'this_year'] as Period[]).map(p => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`text-xs px-3 py-1.5 rounded-lg transition-colors ${
                period === p
                  ? 'bg-white text-[#0a0e1a] font-medium'
                  : 'bg-white/[0.04] text-white/50 hover:bg-white/[0.08]'
              }`}
            >
              {t(`roi.period_${p}`)}
            </button>
          ))}
          <button
            onClick={loadData}
            disabled={isLoading}
            className="p-1.5 rounded-lg bg-white/[0.04] text-white/50 hover:bg-white/[0.08] transition-colors ml-2"
          >
            <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-h-0 overflow-y-auto px-6 py-4 space-y-6">
        {/* KPI Cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <KPICard
            label={t('roi.total_spend')}
            value={summary ? fmt(summary.total_spend) : '-'}
            prefix={summary?.currency === 'ARS' ? '$' : '$'}
            icon={<DollarSign size={16} />}
          />
          <KPICard
            label={t('roi.total_revenue')}
            value={summary ? fmt(summary.total_revenue) : '-'}
            prefix="$"
            icon={<DollarSign size={16} />}
            trend={summary && summary.total_revenue > summary.total_spend ? 'up' : 'neutral'}
          />
          <KPICard
            label="ROI"
            value={summary ? `${summary.roi_percentage.toFixed(1)}` : '-'}
            suffix="%"
            icon={<TrendingUp size={16} />}
            trend={summary && summary.roi_percentage > 0 ? 'up' : summary && summary.roi_percentage < 0 ? 'down' : 'neutral'}
          />
          <KPICard
            label={t('roi.total_leads')}
            value={summary?.total_leads ?? '-'}
            icon={<Users size={16} />}
          />
          <KPICard
            label={t('roi.conversions')}
            value={summary?.total_conversions ?? '-'}
            icon={<Target size={16} />}
          />
          <KPICard
            label={t('roi.cost_per_lead')}
            value={summary && summary.cost_per_lead > 0 ? fmt(summary.cost_per_lead) : 'N/A'}
            prefix={summary && summary.cost_per_lead > 0 ? '$' : undefined}
            icon={<DollarSign size={16} />}
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Trend Chart */}
          <div className="lg:col-span-2 bg-white/[0.04] border border-white/[0.06] rounded-xl p-4">
            <h3 className="text-sm font-medium text-white mb-4">{t('roi.trend')}</h3>
            {trendData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="period" tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} />
                  <YAxis tick={{ fill: 'rgba(255,255,255,0.4)', fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ background: '#0d1117', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                    labelStyle={{ color: '#fff' }}
                    itemStyle={{ color: '#fff' }}
                  />
                  <Area
                    type="monotone"
                    dataKey="total_leads"
                    stroke="#3b82f6"
                    fill="#3b82f680"
                    name={t('roi.total_leads')}
                  />
                  <Area
                    type="monotone"
                    dataKey="total_patients"
                    stroke="#10b981"
                    fill="#10b98160"
                    name={t('roi.conversions')}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[260px] flex items-center justify-center text-white/30 text-sm">
                {t('roi.no_data')}
              </div>
            )}
          </div>

          {/* Attribution Mix Pie */}
          <div className="bg-white/[0.04] border border-white/[0.06] rounded-xl p-4">
            <h3 className="text-sm font-medium text-white mb-4">{t('roi.attribution_mix')}</h3>
            {pieData.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={90}
                    dataKey="value"
                    label={({ name, value }) => `${value.toFixed(0)}%`}
                    labelLine={{ stroke: 'rgba(255,255,255,0.2)' }}
                  >
                    {pieData.map((_entry, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Legend
                    wrapperStyle={{ fontSize: 11, color: 'rgba(255,255,255,0.6)' }}
                  />
                  <Tooltip
                    contentStyle={{ background: '#0d1117', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8 }}
                    itemStyle={{ color: '#fff' }}
                    formatter={(val: number) => `${val.toFixed(1)}%`}
                  />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-[260px] flex items-center justify-center text-white/30 text-sm">
                {t('roi.no_data')}
              </div>
            )}
          </div>
        </div>

        {/* First vs Last Touch Comparison */}
        {comparison && (
          <div className="bg-white/[0.04] border border-white/[0.06] rounded-xl p-4">
            <h3 className="text-sm font-medium text-white mb-4">
              {t('roi.first_touch')} vs {t('roi.last_touch')}
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {['total_patients', 'average_conversion_rate', 'total_spend', 'average_roi'].map(key => (
                <div key={key} className="text-center">
                  <span className="text-white/40 text-xs block mb-2">{key.replace(/_/g, ' ')}</span>
                  <div className="flex items-center justify-center gap-4">
                    <div>
                      <span className="text-blue-400 text-xs block">First</span>
                      <span className="text-white text-lg font-bold">
                        {typeof comparison.first_touch?.[key] === 'number'
                          ? comparison.first_touch[key].toFixed(key.includes('rate') || key.includes('roi') ? 1 : 0)
                          : '-'}
                      </span>
                    </div>
                    <span className="text-white/20">vs</span>
                    <div>
                      <span className="text-purple-400 text-xs block">Last</span>
                      <span className="text-white text-lg font-bold">
                        {typeof comparison.last_touch?.[key] === 'number'
                          ? comparison.last_touch[key].toFixed(key.includes('rate') || key.includes('roi') ? 1 : 0)
                          : '-'}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top Campaigns Table */}
        <div className="bg-white/[0.04] border border-white/[0.06] rounded-xl p-4">
          <h3 className="text-sm font-medium text-white mb-4">{t('roi.top_campaigns')}</h3>
          {topCampaigns.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-white/40 text-xs border-b border-white/[0.06]">
                    <th className="text-left py-2 px-3">{t('roi.campaign')}</th>
                    <th className="text-right py-2 px-3">{t('roi.total_leads')}</th>
                    <th className="text-right py-2 px-3">{t('roi.conversions')}</th>
                    <th className="text-right py-2 px-3">{t('roi.conversion_rate')}</th>
                    <th className="text-right py-2 px-3">{t('roi.patients')}</th>
                  </tr>
                </thead>
                <tbody>
                  {topCampaigns.map((c, i) => (
                    <tr
                      key={i}
                      className="border-b border-white/[0.03] hover:bg-white/[0.02] transition-colors"
                    >
                      <td className="py-2.5 px-3 text-white">{c.campaign_name}</td>
                      <td className="py-2.5 px-3 text-right text-white/70">{c.total_leads}</td>
                      <td className="py-2.5 px-3 text-right text-white/70">{c.converted_leads}</td>
                      <td className="py-2.5 px-3 text-right">
                        <span
                          className={`px-2 py-0.5 rounded text-xs ${
                            c.conversion_rate > 20
                              ? 'bg-green-500/10 text-green-400'
                              : c.conversion_rate > 10
                              ? 'bg-yellow-500/10 text-yellow-400'
                              : 'bg-white/[0.06] text-white/50'
                          }`}
                        >
                          {c.conversion_rate.toFixed(1)}%
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right text-white font-medium">{c.total_patients}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-12 text-center text-white/30 text-sm">{t('roi.no_data')}</div>
          )}
        </div>
      </div>
    </div>
  );
}
