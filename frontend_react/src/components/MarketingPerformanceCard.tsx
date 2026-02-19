/**
 * Spec 09: MarketingPerformanceCard
 * Tarjeta de dashboard con KPIs de rendimiento de campañas Meta Ads.
 * Consume GET /admin/marketing/stats.
 */
import { useState, useEffect } from 'react';
import { Megaphone, TrendingUp, Users, CalendarCheck, Loader2 } from 'lucide-react';
import api from '../api/axios';

interface CampaignStat {
    campaign_name: string;
    ad_id: string;
    ad_name?: string;
    leads: number;
    appointments: number;
    spend: number;
    revenue: number;
    roi: number;
    conversion_rate: number;
}

interface MarketingSummary {
    total_leads: number;
    total_appointments: number;
    total_spend: number;
    total_revenue: number;
    overall_roi: number;
    overall_conversion_rate: number;
}

interface MarketingStatsResponse {
    campaigns: CampaignStat[];
    summary: MarketingSummary;
}

export default function MarketingPerformanceCard() {
    const [data, setData] = useState<MarketingStatsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    useEffect(() => {
        const fetchStats = async () => {
            try {
                setLoading(true);
                const res = await api.get('/admin/marketing/stats');
                setData(res.data);
                setError(false);
            } catch {
                setError(true);
            } finally {
                setLoading(false);
            }
        };
        fetchStats();
    }, []);

    if (loading) {
        return (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <Megaphone size={20} className="text-blue-600" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-gray-900">Marketing Performance</h3>
                        <p className="text-xs text-gray-500">Meta Ads</p>
                    </div>
                </div>
                <div className="flex items-center justify-center py-8 text-gray-400">
                    <Loader2 size={24} className="animate-spin" />
                </div>
            </div>
        );
    }

    if (error || !data) {
        return (
            <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
                <div className="flex items-center gap-3 mb-4">
                    <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                        <Megaphone size={20} className="text-blue-600" />
                    </div>
                    <h3 className="font-semibold text-gray-900">Marketing Performance</h3>
                </div>
                <p className="text-sm text-gray-400 text-center py-4">Sin datos de campañas</p>
            </div>
        );
    }

    const { summary, campaigns } = data;

    return (
        <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-100">
            {/* Header */}
            <div className="flex items-center gap-3 mb-5">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                    <Megaphone size={20} className="text-blue-600" />
                </div>
                <div>
                    <h3 className="font-semibold text-gray-900">Marketing Performance</h3>
                    <p className="text-xs text-gray-500">Meta Ads ROI Real</p>
                </div>
            </div>

            {/* KPIs Row Main (Summary) */}
            <div className="grid grid-cols-2 gap-4 mb-4">
                <div className="p-4 bg-indigo-600 rounded-xl text-white">
                    <p className="text-xs text-indigo-100 uppercase font-bold tracking-wider mb-1">ROI Global</p>
                    <p className="text-3xl font-black">{summary.overall_roi > 0 ? '+' : ''}{Math.round(summary.overall_roi * 100)}%</p>
                </div>
                <div className="p-4 bg-gray-900 rounded-xl text-white">
                    <p className="text-xs text-gray-400 uppercase font-bold tracking-wider mb-1">Inversión (Spend)</p>
                    <p className="text-3xl font-black">${Math.round(summary.total_spend).toLocaleString()}</p>
                </div>
            </div>

            {/* KPIs Row Secondary */}
            <div className="grid grid-cols-3 gap-3 mb-5">
                <div className="text-center p-2 bg-blue-50 rounded-lg border border-blue-100">
                    <Users size={16} className="mx-auto text-blue-500 mb-1" />
                    <p className="text-lg font-bold text-gray-900">{summary.total_leads}</p>
                    <p className="text-[10px] text-gray-500 uppercase font-medium">Leads</p>
                </div>
                <div className="text-center p-2 bg-green-50 rounded-lg border border-green-100">
                    <CalendarCheck size={16} className="mx-auto text-green-500 mb-1" />
                    <p className="text-lg font-bold text-gray-900">{summary.total_appointments}</p>
                    <p className="text-[10px] text-gray-500 uppercase font-medium">Citas</p>
                </div>
                <div className="text-center p-2 bg-purple-50 rounded-lg border border-purple-100">
                    <TrendingUp size={16} className="mx-auto text-purple-500 mb-1" />
                    <p className="text-lg font-bold text-gray-900">{Math.round(summary.overall_conversion_rate * 100)}%</p>
                    <p className="text-[10px] text-gray-500 uppercase font-medium">Conv.</p>
                </div>
            </div>

            {/* Campaign Table */}
            {campaigns.length > 0 && (
                <div className="border-t pt-4">
                    <div className="flex items-center justify-between mb-3">
                        <p className="text-xs font-bold text-gray-500 uppercase">Top Campañas (ROI)</p>
                        <span className="text-[10px] text-gray-400">Últimos 30 días</span>
                    </div>
                    <div className="space-y-3 max-h-48 overflow-y-auto pr-1">
                        {campaigns.sort((a, b) => b.roi - a.roi).slice(0, 5).map((c, i) => (
                            <div key={i} className="flex items-center justify-between text-sm group">
                                <div className="flex-1 min-w-0">
                                    <p className="font-bold text-gray-700 truncate group-hover:text-blue-600 transition-colors" title={c.ad_name || c.campaign_name}>
                                        {c.ad_name || c.campaign_name}
                                    </p>
                                    <div className="flex items-center gap-2 text-[10px]">
                                        <span className="text-gray-400">${Math.round(c.spend)} gastados</span>
                                        <span className="text-gray-300">•</span>
                                        <span className="text-indigo-500 font-bold">{c.leads} leads</span>
                                    </div>
                                </div>
                                <div className="text-right ml-3">
                                    <p className={`font-black ${c.roi > 0 ? 'text-green-600' : 'text-gray-400'}`}>
                                        {c.roi > 0 ? '+' : ''}{Math.round(c.roi * 100)}%
                                    </p>
                                    <p className="text-[10px] text-gray-500">${Math.round(c.revenue).toLocaleString()}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
