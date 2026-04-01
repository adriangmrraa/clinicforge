import { useState } from 'react';
import { ChevronDown, ChevronRight, User, Stethoscope } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import type { LiquidationProfessional } from '../../types/liquidation';
import TreatmentGroupAccordion from './TreatmentGroupAccordion';

interface Props {
  professional: LiquidationProfessional;
  formatCurrency: (n: number) => string;
}

export default function ProfessionalAccordion({ professional, formatCurrency }: Props) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const { summary } = professional;

  return (
    <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl mb-3 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(prev => !prev)}
        className="w-full flex items-center gap-3 px-5 py-4 hover:bg-white/[0.04] transition-colors text-left"
      >
        {/* Chevron */}
        <span className="text-white/30 shrink-0 transition-transform duration-200">
          {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        </span>

        {/* Avatar icon */}
        <div className="w-8 h-8 rounded-full bg-white/[0.06] flex items-center justify-center shrink-0">
          <User size={14} className="text-white/40" />
        </div>

        {/* Name + specialty */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-white text-sm">{professional.name}</span>
            <span className="flex items-center gap-1 text-white/40 text-xs">
              <Stethoscope size={11} />
              {professional.specialty}
            </span>
          </div>
          <p className="text-white/30 text-xs mt-0.5">
            {summary.appointments} {t('liquidation.appointments')} · {summary.patients} {t('liquidation.patients')}
          </p>
        </div>

        {/* Amount badges */}
        <div className="flex items-center gap-2 shrink-0">
          <div className="flex flex-col items-end gap-0.5">
            <span className="text-[10px] text-white/30 uppercase tracking-wide">{t('liquidation.billed')}</span>
            <span className="text-xs bg-white/[0.06] text-white px-2 py-0.5 rounded-md font-medium">
              {formatCurrency(summary.billed)}
            </span>
          </div>
          <div className="flex flex-col items-end gap-0.5">
            <span className="text-[10px] text-white/30 uppercase tracking-wide">{t('liquidation.paid')}</span>
            <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-md font-medium">
              {formatCurrency(summary.paid)}
            </span>
          </div>
          {summary.pending > 0 && (
            <div className="flex flex-col items-end gap-0.5">
              <span className="text-[10px] text-white/30 uppercase tracking-wide">{t('liquidation.pending')}</span>
              <span className="text-xs bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded-md font-medium">
                {formatCurrency(summary.pending)}
              </span>
            </div>
          )}
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 pt-1">
          {professional.treatment_groups.map(group => (
            <TreatmentGroupAccordion
              key={`${group.patient_id}-${group.treatment_code}`}
              group={group}
              formatCurrency={formatCurrency}
            />
          ))}
        </div>
      )}
    </div>
  );
}
