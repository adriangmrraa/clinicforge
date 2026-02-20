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
        <div className="bg-white border border-gray-200 rounded-3xl p-8 shadow-sm h-full flex flex-col justify-between overflow-hidden relative">
            <div className="absolute top-0 right-0 w-64 h-64 bg-indigo-50 rounded-full blur-3xl -mr-32 -mt-32 opacity-50"></div>

            <div className="relative z-10">
                <div className="flex justify-between items-start mb-8">
                    <div>
                        <h3 className="text-gray-500 font-medium text-xs sm:text-sm mb-1 uppercase tracking-wider">{t('marketing.roi_card_title')}</h3>
                        <p className="text-3xl sm:text-4xl font-black text-gray-900 leading-tight">
                            {roi >= 0 ? '+' : ''}{roi.toFixed(1)}%
                        </p>
                    </div>
                    <div className={`p-2 sm:p-3 rounded-2xl ${roi >= 0 ? 'bg-green-100 text-green-600' : 'bg-rose-100 text-rose-600'}`}>
                        {roi >= 0 ? <TrendingUp size={20} className="sm:w-6 sm:h-6" /> : <TrendingDown size={20} className="sm:w-6 sm:h-6" />}
                    </div>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-8 mb-8">
                    <div className="space-y-1">
                        <div className="flex items-center gap-1.5 text-gray-500 text-[10px] sm:text-xs font-bold uppercase tracking-widest">
                            <DollarSign size={14} className="text-indigo-500" /> {t('marketing.investment')}
                        </div>
                        <p className="text-xl sm:text-2xl font-bold text-gray-800 break-words">{stats?.currency === 'USD' ? '$' : stats?.currency || ''}{investment.toLocaleString()}</p>
                    </div>
                    <div className="space-y-1">
                        <div className="flex items-center gap-1.5 text-gray-500 text-[10px] sm:text-xs font-bold uppercase tracking-widest">
                            <Target size={14} className="text-emerald-500" /> {t('marketing.return')}
                        </div>
                        <p className="text-xl sm:text-2xl font-bold text-gray-800 break-words">{stats?.currency === 'USD' ? '$' : stats?.currency || ''}{revenue.toLocaleString()}</p>
                    </div>
                </div>
            </div>

            <div className="relative z-10 grid grid-cols-3 gap-1 sm:gap-4 pt-6 border-t border-gray-100">
                <div className="text-center">
                    <p className="text-gray-400 text-[9px] sm:text-[10px] font-bold uppercase mb-1">CPA</p>
                    <p className="text-[10px] sm:text-sm font-bold text-gray-700">{stats?.currency === 'USD' ? '$' : stats?.currency || ''}{stats?.cpa > 999 ? Math.round(stats.cpa).toLocaleString() : stats?.cpa?.toFixed(2) || '0.00'}</p>
                </div>
                <div className="text-center border-x border-gray-50 px-1">
                    <p className="text-gray-400 text-[9px] sm:text-[10px] font-bold uppercase mb-1">Leads</p>
                    <p className="text-[10px] sm:text-sm font-bold text-gray-700">{stats?.leads || 0}</p>
                </div>
                <div className="text-center">
                    <p className="text-gray-400 text-[9px] sm:text-[10px] font-bold uppercase mb-1 truncate px-1">{t('marketing.patients')}</p>
                    <p className="text-[10px] sm:text-sm font-bold text-gray-700">{stats?.patients_converted || 0}</p>
                </div>
            </div>
        </div>
    );
}
