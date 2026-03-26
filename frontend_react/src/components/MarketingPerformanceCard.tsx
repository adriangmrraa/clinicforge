import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, DollarSign, Users, Award, Target } from 'lucide-react';
import api from '../api/axios';
import { useTranslation } from '../context/LanguageContext';

interface MarketingPerformanceCardProps {
    stats?: any;
    loading?: boolean;
    timeRange?: string;
}

export default function MarketingPerformanceCard({ stats: externalStats, loading: externalLoading, timeRange = 'last_30d' }: MarketingPerformanceCardProps) {
    const { t } = useTranslation();
    const [stats, setStats] = useState<any>(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        if (externalStats) {
            setStats(externalStats);
            setLoading(externalLoading || false);
            return;
        }

        const fetchStats = async () => {
            try {
                setLoading(true);
                const { data } = await api.get(`/admin/marketing/stats/roi?range=${timeRange}`);
                setStats(data);
            } catch (error) {
                console.error("Error fetching ROI stats:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchStats();
    }, [externalStats, externalLoading, timeRange]);

    if (loading) return (
        <div className="bg-white border border-gray-200 rounded-3xl p-8 h-full flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
        </div>
    );

    const investment = stats?.total_spend || 0;
    const revenue = stats?.total_revenue || 0;
    const roi = investment > 0 ? ((revenue - investment) / investment) * 100 : 0;

    return (
        <div className="bg-white border border-gray-200 rounded-2xl p-4 sm:p-6 shadow-sm overflow-hidden relative">
            <div className="absolute top-0 right-0 w-48 h-48 bg-indigo-50 rounded-full blur-3xl -mr-24 -mt-24 opacity-40"></div>

            <div className="relative z-10">
                {/* ROI + Investment/Return in a compact row */}
                <div className="flex items-center gap-4 mb-4">
                    <div className="flex-1">
                        <h3 className="text-gray-400 font-medium text-[10px] uppercase tracking-wider">{t('marketing.roi_card_title')}</h3>
                        <p className="text-2xl sm:text-3xl font-black text-gray-900 leading-tight">
                            {roi >= 0 ? '+' : ''}{roi.toFixed(1)}%
                        </p>
                    </div>
                    <div className={`p-2 rounded-xl ${roi >= 0 ? 'bg-green-100 text-green-600' : 'bg-rose-100 text-rose-600'}`}>
                        {roi >= 0 ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-3 mb-4">
                    <div className="bg-slate-50 rounded-xl p-2.5">
                        <div className="flex items-center gap-1 text-gray-400 text-[10px] font-bold uppercase tracking-wider mb-1">
                            <DollarSign size={12} className="text-indigo-500" /> {t('marketing.investment')}
                        </div>
                        <p className="text-base sm:text-lg font-bold text-gray-800 break-words">{stats?.currency === 'USD' ? '$' : stats?.currency || ''}{investment.toLocaleString()}</p>
                    </div>
                    <div className="bg-emerald-50 rounded-xl p-2.5">
                        <div className="flex items-center gap-1 text-gray-400 text-[10px] font-bold uppercase tracking-wider mb-1">
                            <Target size={12} className="text-emerald-500" /> {t('marketing.return')}
                        </div>
                        <p className="text-base sm:text-lg font-bold text-gray-800 break-words">{stats?.currency === 'USD' ? '$' : stats?.currency || ''}{revenue.toLocaleString()}</p>
                    </div>
                </div>
            </div>

            <div className="relative z-10 grid grid-cols-3 gap-2 pt-3 border-t border-gray-100">
                <div className="text-center bg-gray-50 rounded-lg py-2">
                    <p className="text-lg font-bold text-gray-700">{stats?.currency === 'USD' ? '$' : ''}{stats?.cpa > 999 ? Math.round(stats.cpa).toLocaleString() : stats?.cpa?.toFixed(0) || '0'}</p>
                    <p className="text-[10px] text-gray-400 font-semibold uppercase">CPA</p>
                </div>
                <div className="text-center bg-blue-50 rounded-lg py-2">
                    <p className="text-lg font-bold text-blue-700">{stats?.leads || 0}</p>
                    <p className="text-[10px] text-blue-400 font-semibold uppercase">Leads</p>
                </div>
                <div className="text-center bg-emerald-50 rounded-lg py-2">
                    <p className="text-lg font-bold text-emerald-700">{stats?.patients_converted || 0}</p>
                    <p className="text-[10px] text-emerald-400 font-semibold uppercase">{t('marketing.patients')}</p>
                </div>
            </div>
        </div>
    );
}
