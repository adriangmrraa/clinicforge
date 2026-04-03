import React from 'react';
import { useTranslation } from '../../context/LanguageContext';
import { STATE_FILLS, type ToothStatus } from './ToothSVG';

interface AvailableState {
  id: ToothStatus;
  label: string;
}

interface OdontogramLegendProps {
  availableStates: AvailableState[];
}

export function OdontogramLegend({ availableStates }: OdontogramLegendProps) {
  const { t } = useTranslation();

  return (
    <div className="mt-4 pt-4 border-t border-white/[0.06]">
      <h4 className="text-[10px] font-bold text-white/30 uppercase tracking-widest mb-3">
        {t('odontogram.legend')}
      </h4>
      <div className="flex flex-wrap gap-2">
        {availableStates.map(s => {
          const fills = STATE_FILLS[s.id];
          return (
            <div key={s.id} className="flex items-center gap-1.5">
              <svg viewBox="0 0 12 12" className="w-3 h-3">
                <circle cx="6" cy="6" r="5" fill={fills.fill} stroke={fills.stroke} strokeWidth="1" />
              </svg>
              <span className="text-[11px] text-white/50 font-medium">{s.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
