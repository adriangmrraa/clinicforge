import { useState } from 'react';
import { ChevronDown, ChevronRight, Phone } from 'lucide-react';
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

  return (
    <div className="ml-4 bg-white/[0.01] border-l-2 border-white/[0.06] mb-2">
      {/* Header */}
      <button
        onClick={() => setExpanded(prev => !prev)}
        className="w-full flex items-center gap-2 px-4 py-2.5 hover:bg-white/[0.03] transition-colors text-left"
      >
        {/* Chevron */}
        <span className="text-white/20 shrink-0">
          {expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </span>

        {/* Patient info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-sm text-white/80 font-medium truncate">{group.patient_name}</span>
            {group.patient_phone && (
              <span className="flex items-center gap-1 text-white/30 text-xs">
                <Phone size={10} />
                {group.patient_phone}
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="bg-blue-500/10 text-blue-400 text-xs rounded-full px-2 py-0.5">
              {group.treatment_name}
            </span>
            <span className="text-white/30 text-xs">
              {group.session_count} {t('liquidation.sessions')}
            </span>
          </div>
        </div>

        {/* Amounts */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right">
            <p className="text-[10px] text-white/30 uppercase tracking-wide">{t('liquidation.billed')}</p>
            <p className="text-xs text-white font-medium">{formatCurrency(group.total_billed)}</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] text-white/30 uppercase tracking-wide">{t('liquidation.paid')}</p>
            <p className="text-xs text-emerald-400 font-medium">{formatCurrency(group.total_paid)}</p>
          </div>
        </div>
      </button>

      {/* Sessions */}
      {expanded && (
        <div className="ml-4">
          {group.sessions.map(session => (
            <SessionRow
              key={session.appointment_id}
              session={session}
              formatCurrency={formatCurrency}
            />
          ))}
        </div>
      )}
    </div>
  );
}
