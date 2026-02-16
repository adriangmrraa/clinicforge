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
    ad_headline: string;
    leads: number;
    appointments: number;
    conversion_rate: number;
}

interface MarketingSummary {
    total_leads: number;
    total_appointments: number;
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
                    <p className="text-xs text-gray-500">Meta Ads Attribution</p>
                </div>
            </div>

            {/* KPIs Row */}
            <div className="grid grid-cols-3 gap-4 mb-5">
                <div className="text-center p-3 bg-blue-50 rounded-lg">
                    <Users size={18} className="mx-auto text-blue-500 mb-1" />
                    <p className="text-2xl font-bold text-gray-900">{summary.total_leads}</p>
                    <p className="text-xs text-gray-500">Leads</p>
                </div>
                <div className="text-center p-3 bg-green-50 rounded-lg">
                    <CalendarCheck size={18} className="mx-auto text-green-500 mb-1" />
                    <p className="text-2xl font-bold text-gray-900">{summary.total_appointments}</p>
                    <p className="text-xs text-gray-500">Citas</p>
                </div>
                <div className="text-center p-3 bg-purple-50 rounded-lg">
                    <TrendingUp size={18} className="mx-auto text-purple-500 mb-1" />
                    <p className="text-2xl font-bold text-gray-900">{Math.round(summary.overall_conversion_rate * 100)}%</p>
                    <p className="text-xs text-gray-500">Conversión</p>
                </div>
            </div>

            {/* Campaign Table */}
            {campaigns.length > 0 && (
                <div className="border-t pt-4">
                    <p className="text-xs font-medium text-gray-500 uppercase mb-3">Por Campaña</p>
                    <div className="space-y-2 max-h-40 overflow-y-auto">
                        {campaigns.slice(0, 5).map((c, i) => (
                            <div key={i} className="flex items-center justify-between text-sm">
                                <div className="flex-1 min-w-0">
                                    <p className="font-medium text-gray-700 truncate" title={c.campaign_name}>
                                        {c.campaign_name}
                                    </p>
                                    {c.ad_headline && (
                                        <p className="text-xs text-gray-400 truncate">{c.ad_headline}</p>
                                    )}
                                </div>
                                <div className="flex items-center gap-3 ml-3 text-xs text-gray-500">
                                    <span>{c.leads} leads</span>
                                    <span className="text-green-600 font-medium">{c.appointments} citas</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}
