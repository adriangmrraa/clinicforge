import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, DollarSign, Users, Award, Target } from 'lucide-react';
import api from '../api/axios';

interface MarketingPerformanceCardProps {
    stats?: any;
    loading?: boolean;
}

export default function MarketingPerformanceCard({ stats: externalStats, loading: externalLoading }: MarketingPerformanceCardProps) {
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
                const { data } = await api.get('/admin/marketing/stats/roi');
                setStats(data);
            } catch (error) {
                console.error("Error fetching ROI stats:", error);
            } finally {
                setLoading(false);
            }
        };
        fetchStats();
    }, [externalStats, externalLoading]);

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
                        <h3 className="text-gray-500 font-medium text-sm mb-1 uppercase tracking-wider">ROI Real de Marketing</h3>
                        <p className="text-4xl font-black text-gray-900 leading-tight">
                            {roi >= 0 ? '+' : ''}{roi.toFixed(1)}%
                        </p>
                    </div>
                    <div className={`p-3 rounded-2xl ${roi >= 0 ? 'bg-green-100 text-green-600' : 'bg-rose-100 text-rose-600'}`}>
                        {roi >= 0 ? <TrendingUp size={24} /> : <TrendingDown size={24} />}
                    </div>
                </div>

                <div className="grid grid-cols-2 gap-8 mb-8">
                    <div className="space-y-1">
                        <div className="flex items-center gap-1.5 text-gray-500 text-xs font-bold uppercase tracking-widest">
                            <DollarSign size={14} className="text-indigo-500" /> Inversión
                        </div>
                        <p className="text-2xl font-bold text-gray-800">{stats?.currency === 'USD' ? '$' : stats?.currency || ''}{investment.toLocaleString()}</p>
                    </div>
                    <div className="space-y-1">
                        <div className="flex items-center gap-1.5 text-gray-500 text-xs font-bold uppercase tracking-widest">
                            <Target size={14} className="text-emerald-500" /> Retorno (Ingresos)
                        </div>
                        <p className="text-2xl font-bold text-gray-800">{stats?.currency === 'USD' ? '$' : stats?.currency || ''}{revenue.toLocaleString()}</p>
                    </div>
                </div>
            </div>

            <div className="relative z-10 grid grid-cols-3 gap-4 pt-6 border-t border-gray-100">
                <div className="text-center">
                    <p className="text-gray-400 text-[10px] font-bold uppercase mb-1">CPA</p>
                    <p className="text-sm font-bold text-gray-700">{stats?.currency === 'USD' ? '$' : stats?.currency || ''}{stats?.cpa?.toFixed(2) || '0.00'}</p>
                </div>
                <div className="text-center">
                    <p className="text-gray-400 text-[10px] font-bold uppercase mb-1">Leads</p>
                    <p className="text-sm font-bold text-gray-700">{stats?.leads || 0}</p>
                </div>
                <div className="text-center">
                    <p className="text-gray-400 text-[10px] font-bold uppercase mb-1">Pacientes</p>
                    <p className="text-sm font-bold text-gray-700">{stats?.patients_converted || 0}</p>
                </div>
            </div>
        </div>
    );
}
