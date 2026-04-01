import { useState } from 'react';
import { ChevronDown, Phone } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import type { TreatmentGroup } from '../../types/liquidation';
import SessionRow from './SessionRow';

interface Props {
  group: TreatmentGroup;
  formatCurrency: (n: number) => string;
}

export default function TreatmentGroupAccordion({ group, formatCurrency }: Props) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  const isPending = group.total_paid < group.total_billed;

  return (
    <div
      className="ml-4 bg-white/[0.01] mb-2 rounded-r-xl"
      style={{
        borderLeft: expanded ? '2px solid rgba(59,130,246,0.35)' : '2px solid rgba(255,255,255,0.06)',
        transition: 'border-color 0.3s ease',
      }}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded(prev => !prev)}
        className="w-full px-3 py-2.5 hover:bg-white/[0.03] transition-colors text-left"
      >
        {/* Row 1: chevron + patient name + phone */}
        <div className="flex items-center gap-1.5">
          <ChevronDown
            size={13}
            className="text-white/20 shrink-0 transition-transform duration-200"
            style={{
              transform: expanded ? 'rotate(0deg)' : 'rotate(-90deg)',
              transitionTimingFunction: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
            }}
          />
          <span className="text-sm text-white/80 font-medium truncate">{group.patient_name}</span>
          {group.patient_phone && (
            <span className="text-white/30 text-xs flex items-center gap-0.5 shrink-0">
              <Phone size={10} />
              {group.patient_phone}
            </span>
          )}
        </div>

        {/* Row 2: treatment badge + session count + amounts */}
        <div className="flex items-center gap-2 mt-1.5 ml-5 flex-wrap">
          <span
            className={`text-xs rounded-full px-2 py-0.5 ${
              isPending
                ? 'bg-amber-500/10 text-amber-400 ring-1 ring-amber-500/20'
                : 'bg-blue-500/10 text-blue-400'
            }`}
          >
            {group.treatment_name}
          </span>
          <span className="text-white/30 text-xs">
            {group.session_count} {t('liquidation.sessions')}
          </span>
          <span className="text-white text-xs font-medium ml-auto">{formatCurrency(group.total_billed)}</span>
          <span className="text-emerald-400 text-xs font-medium">{formatCurrency(group.total_paid)}</span>
        </div>
      </button>

      {/* Sessions — smooth max-height transition */}
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
        <div className="ml-4">
          {group.sessions.map(session => (
            <SessionRow
              key={session.appointment_id}
              session={session}
              formatCurrency={formatCurrency}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
