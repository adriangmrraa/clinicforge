import React from 'react';
import { useTranslation } from '../../context/LanguageContext';

export type DentitionType = 'permanent' | 'deciduous';

interface OdontogramTabsProps {
  activeDentition: DentitionType;
  onChange: (dentition: DentitionType) => void;
  hasDecidData?: boolean;
}

export function OdontogramTabs({ activeDentition, onChange, hasDecidData = false }: OdontogramTabsProps) {
  const { t } = useTranslation();
  const isPermanent = activeDentition === 'permanent';

  return (
    <div className="flex items-center gap-1 p-1 bg-white/[0.04] rounded-xl border border-white/[0.06]">
      <button
        onClick={() => onChange('permanent')}
        className={`
          flex-1 relative px-4 py-2.5 sm:py-2 rounded-lg text-xs sm:text-xs font-bold
          transition-all duration-300 ease-out touch-manipulation
          ${isPermanent
            ? 'bg-white/[0.12] text-white shadow-lg shadow-black/20'
            : 'text-white/50 active:bg-white/[0.06]'
          }
        `}
      >
        {t('odontogram.tabs.permanent')}
      </button>

      <button
        onClick={() => onChange('deciduous')}
        className={`
          flex-1 relative px-4 py-2.5 sm:py-2 rounded-lg text-xs sm:text-xs font-bold
          transition-all duration-300 ease-out touch-manipulation
          ${!isPermanent
            ? 'bg-white/[0.12] text-white shadow-lg shadow-black/20'
            : 'text-white/50 active:bg-white/[0.06]'
          }
        `}
      >
        {t('odontogram.tabs.deciduous')}
        {hasDecidData && (
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-emerald-400 rounded-full shadow-[0_0_4px_rgba(52,211,153,0.6)]" />
        )}
      </button>
    </div>
  );
}
