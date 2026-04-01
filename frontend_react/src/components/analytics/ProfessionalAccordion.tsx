import { useState } from 'react';
import { ChevronDown, Stethoscope } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
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

  const pct = summary.billed > 0 ? Math.round((summary.paid / summary.billed) * 100) : 0;
  const hue = (professional.name.charCodeAt(0) * 17) % 360;

  return (
    <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl mb-3 overflow-hidden">
      {/* Header */}
      <button
        onClick={() => setExpanded(prev => !prev)}
        className="w-full px-4 py-3 hover:bg-white/[0.04] transition-colors duration-200 text-left relative"
      >
        {/* Blue left accent bar when expanded */}
        {expanded && (
          <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-blue-400/60 rounded-r-full" />
        )}

        {/* Top row: chevron + avatar + name + specialty */}
        <div className="flex items-center gap-2.5">
          <ChevronDown
            size={16}
            className="text-white/30 shrink-0 transition-transform duration-250"
            style={{
              transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
              transitionTimingFunction: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
            }}
          />

          {/* Gradient avatar */}
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold text-white/80"
            style={{
              background: `linear-gradient(135deg, hsl(${hue},50%,25%), hsl(${hue},40%,18%))`,
              boxShadow: `0 0 10px hsla(${hue},50%,40%,0.2)`,
            }}
          >
            {professional.name[0].toUpperCase()}
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-white text-sm truncate">{professional.name}</span>
              <span className="text-white/40 text-xs flex items-center gap-1">
                <Stethoscope size={11} />
                {professional.specialty}
              </span>
            </div>
            <p className="text-white/30 text-xs mt-0.5">
              {summary.appointments} {t('liquidation.appointments')} · {summary.patients} {t('liquidation.patients')}
            </p>
          </div>
        </div>

        {/* Bottom row: amount badges — indented past chevron + avatar */}
        <div className="flex items-center gap-2 mt-2 ml-12 flex-wrap">
          <div className="flex flex-col items-center">
            <span className="text-[9px] text-white/30 uppercase">{t('liquidation.billed')}</span>
            <span className="text-xs bg-white/[0.06] text-white px-2 py-0.5 rounded-md font-medium">
              {formatCurrency(summary.billed)}
            </span>
          </div>
          <div className="flex flex-col items-center">
            <span className="text-[9px] text-emerald-400/60 uppercase">{t('liquidation.paid')}</span>
            <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-0.5 rounded-md font-medium">
              {formatCurrency(summary.paid)}
            </span>
          </div>
          {summary.pending > 0 && (
            <div className="flex flex-col items-center">
              <span className="text-[9px] text-amber-400/60 uppercase">{t('liquidation.pending')}</span>
              <span className="text-xs bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded-md font-medium">
                {formatCurrency(summary.pending)}
              </span>
            </div>
          )}
        </div>

        {/* Progress bar — aligned with the amount badges row */}
        <div className="w-full h-0.5 bg-white/[0.06] rounded-full overflow-hidden mt-2 ml-12" style={{ width: 'calc(100% - 3rem)' }}>
          <div
            className="h-full bg-emerald-500/50 rounded-full"
            style={{ width: `${pct}%`, transition: 'width 0.6s ease-out' }}
          />
        </div>
      </button>

      {/* Expanded content — smooth max-height transition */}
      <div
        style={{
          maxHeight: expanded ? '2000px' : '0',
          overflow: 'hidden',
          transition: expanded
            ? 'max-height 0.4s ease-out, opacity 0.3s ease-out'
            : 'max-height 0.25s ease-in, opacity 0.15s ease-in',
          opacity: expanded ? 1 : 0,
        }}
      >
        <div className="px-4 pb-4 pt-1">
          {professional.treatment_groups.map(group => (
            <TreatmentGroupAccordion
              key={`${group.patient_id}-${group.treatment_code}`}
              group={group}
              formatCurrency={formatCurrency}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
