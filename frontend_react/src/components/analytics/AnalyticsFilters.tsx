import React, { useState, useEffect } from 'react';
import api from '../../api/axios';
import { useTranslation } from '../../context/LanguageContext';
import { Calendar, Users } from 'lucide-react';

interface Professional {
    id: number;
    first_name: string;
    last_name?: string;
}

function professionalDisplayName(p: Professional): string {
    return [p.first_name, p.last_name].filter(Boolean).join(' ').trim() || 'Profesional';
}

interface AnalyticsFiltersProps {
    onFilterChange: (filters: { startDate: string; endDate: string; professionalIds: number[] }) => void;
}

const AnalyticsFilters: React.FC<AnalyticsFiltersProps> = ({ onFilterChange }) => {
    const { t } = useTranslation();
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [selectedProfs, setSelectedProfs] = useState<number[]>([]);
    const [professionals, setProfessionals] = useState<Professional[]>([]);

    useEffect(() => {
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        setStartDate(firstDay.toISOString().split('T')[0]);
        setEndDate(lastDay.toISOString().split('T')[0]);
        fetchProfessionals();
    }, []);

    const fetchProfessionals = async () => {
        try {
            const response = await api.get('/admin/professionals');
            setProfessionals(response.data || []);
        } catch (error) {
            console.error("Error fetching professionals for filter", error);
        }
    };

    useEffect(() => {
        if (startDate && endDate) {
            onFilterChange({ startDate, endDate, professionalIds: selectedProfs });
        }
    }, [startDate, endDate, selectedProfs]);

    return (
        <div className="bg-white p-4 sm:p-5 rounded-2xl border border-slate-100 shadow-sm mb-6">
            <div className="flex flex-wrap gap-4 sm:gap-6 items-end">
                <div className="flex items-center gap-2 min-w-0">
                    <Calendar size={18} className="text-slate-500 shrink-0" />
                    <div>
                        <label className="block text-xs font-semibold text-slate-600 mb-1 uppercase tracking-wider">{t('analytics.from_date')}</label>
                        <input
                            type="date"
                            value={startDate}
                            onChange={(e) => setStartDate(e.target.value)}
                            className="border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-medical-500/30 focus:border-medical-500 min-w-[140px]"
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-xs font-semibold text-slate-600 mb-1 uppercase tracking-wider">{t('analytics.to_date')}</label>
                    <input
                        type="date"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        className="border border-slate-200 rounded-xl px-3 py-2.5 text-sm text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-medical-500/30 focus:border-medical-500 min-w-[140px]"
                    />
                </div>
                <div className="min-w-[200px] flex-1 sm:flex-initial">
                    <label className="block text-xs font-semibold text-slate-600 mb-1 uppercase tracking-wider flex items-center gap-1">
                        <Users size={14} /> {t('analytics.professionals_filter')}
                    </label>
                    <select
                        multiple
                        className="border border-slate-200 rounded-xl px-3 py-2.5 text-sm w-full min-h-[88px] text-slate-800 bg-white focus:outline-none focus:ring-2 focus:ring-medical-500/30 focus:border-medical-500"
                        value={selectedProfs.map(String)}
                        onChange={(e) => {
                            const options = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                            setSelectedProfs(options);
                        }}
                    >
                        {professionals.map(p => (
                            <option key={p.id} value={p.id}>{professionalDisplayName(p)}</option>
                        ))}
                    </select>
                    <p className="text-[11px] text-slate-500 mt-1">{t('chats.ctrl_click_multiple')}</p>
                </div>
            </div>
        </div>
    );
};

export default AnalyticsFilters;
