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

// Fecha local YYYY-MM-DD — toISOString() es UTC y puede correr un dia
function fmtLocal(d: Date): string {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

const AnalyticsFilters: React.FC<AnalyticsFiltersProps> = ({ onFilterChange }) => {
    const { t } = useTranslation();
    const [startDate, setStartDate] = useState('');
    const [endDate, setEndDate] = useState('');
    const [selectedProfs, setSelectedProfs] = useState<number[]>([]);
    const [professionals, setProfessionals] = useState<Professional[]>([]);

    const now = new Date();
    const presets = [
        {
            key: 'this_month',
            label: t('analytics.preset_this_month', 'Este mes'),
            start: fmtLocal(new Date(now.getFullYear(), now.getMonth(), 1)),
            end: fmtLocal(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
        },
        {
            key: 'last_month',
            label: t('analytics.preset_last_month', 'Mes pasado'),
            start: fmtLocal(new Date(now.getFullYear(), now.getMonth() - 1, 1)),
            end: fmtLocal(new Date(now.getFullYear(), now.getMonth(), 0)),
        },
        {
            key: 'this_year',
            label: t('analytics.preset_this_year', 'Este año'),
            start: fmtLocal(new Date(now.getFullYear(), 0, 1)),
            end: fmtLocal(new Date(now.getFullYear(), 11, 31)),
        },
    ];

    useEffect(() => {
        // Antes arrancaba con el AÑO entero y se mezclaba todo
        // (pedido Carlos 2026-07-10: "necesitamos del mes")
        const thisMonth = presets[0];
        setStartDate(thisMonth.start);
        setEndDate(thisMonth.end);
        fetchProfessionals();
        // eslint-disable-next-line react-hooks/exhaustive-deps
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
        <div className="bg-white/[0.03] p-4 sm:p-5 rounded-2xl border border-white/[0.06] mb-6">
            {/* Accesos rapidos de periodo */}
            <div className="flex items-center gap-2 flex-wrap mb-4">
                {presets.map((p) => {
                    const active = startDate === p.start && endDate === p.end;
                    return (
                        <button
                            key={p.key}
                            onClick={() => {
                                setStartDate(p.start);
                                setEndDate(p.end);
                            }}
                            className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-colors ${
                                active
                                    ? 'bg-white text-[#0a0e1a] border-white'
                                    : 'bg-white/[0.04] text-white/60 border-white/[0.08] hover:text-white hover:bg-white/[0.08]'
                            }`}
                        >
                            {p.label}
                        </button>
                    );
                })}
            </div>
            <div className="flex flex-wrap gap-4 sm:gap-6 items-end">
                <div className="flex items-center gap-2 min-w-0">
                    <Calendar size={18} className="text-white/40 shrink-0" />
                    <div>
                        <label className="block text-xs font-semibold text-white/60 mb-1 uppercase tracking-wider">{t('analytics.from_date')}</label>
                        <input
                            type="date"
                            value={startDate}
                            onChange={(e) => setStartDate(e.target.value)}
                            className="border border-white/[0.08] rounded-xl px-3 py-2.5 text-sm text-white bg-white/[0.04] focus:outline-none focus:ring-2 focus:ring-medical-500/30 focus:border-medical-500 min-w-[140px]"
                        />
                    </div>
                </div>
                <div>
                    <label className="block text-xs font-semibold text-white/60 mb-1 uppercase tracking-wider">{t('analytics.to_date')}</label>
                    <input
                        type="date"
                        value={endDate}
                        onChange={(e) => setEndDate(e.target.value)}
                        className="border border-white/[0.08] rounded-xl px-3 py-2.5 text-sm text-white bg-white/[0.04] focus:outline-none focus:ring-2 focus:ring-medical-500/30 focus:border-medical-500 min-w-[140px]"
                    />
                </div>
                <div className="min-w-[200px] flex-1 sm:flex-initial">
                    <label className="block text-xs font-semibold text-white/60 mb-1 uppercase tracking-wider flex items-center gap-1">
                        <Users size={14} /> {t('analytics.professionals_filter')}
                    </label>
                    <select
                        multiple
                        className="border border-white/[0.08] rounded-xl px-3 py-2.5 text-sm w-full min-h-[88px] text-white bg-white/[0.04] focus:outline-none focus:ring-2 focus:ring-medical-500/30 focus:border-medical-500"
                        value={selectedProfs.map(String)}
                        onChange={(e) => {
                            const options = Array.from(e.target.selectedOptions, option => parseInt(option.value));
                            setSelectedProfs(options);
                        }}
                    >
                        {professionals.map(p => (
                            <option key={p.id} value={p.id} className="bg-[#0d1117] text-white">{professionalDisplayName(p)}</option>
                        ))}
                    </select>
                    <p className="text-[11px] text-white/40 mt-1">{t('chats.ctrl_click_multiple')}</p>
                </div>
            </div>
        </div>
    );
};

export default AnalyticsFilters;
