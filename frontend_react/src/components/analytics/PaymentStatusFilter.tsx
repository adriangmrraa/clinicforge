import React from 'react';
import { useTranslation } from '../../context/LanguageContext';

interface PaymentStatusFilterProps {
  value: string;
  onChange: (v: string) => void;
}

interface FilterOption {
  key: string;
  label: string;
  activeClass: string;
}

const PaymentStatusFilter: React.FC<PaymentStatusFilterProps> = ({ value, onChange }) => {
  const { t } = useTranslation();

  const options: FilterOption[] = [
    {
      key: 'all',
      label: t('liquidation.filter_all'),
      activeClass: 'bg-white/[0.12] text-white',
    },
    {
      key: 'pending',
      label: t('liquidation.filter_pending'),
      activeClass: 'bg-red-500/20 text-red-400',
    },
    {
      key: 'partial',
      label: t('liquidation.filter_partial'),
      activeClass: 'bg-amber-500/20 text-amber-400',
    },
    {
      key: 'paid',
      label: t('liquidation.filter_paid'),
      activeClass: 'bg-emerald-500/20 text-emerald-400',
    },
  ];

  return (
    <div className="flex items-center overflow-hidden border border-white/[0.04] rounded-full bg-white/[0.02]">
      {options.map((option) => {
        const isActive = value === option.key;
        return (
          <button
            key={option.key}
            onClick={() => onChange(option.key)}
            className={`px-4 py-1.5 text-xs font-medium transition-all duration-200 whitespace-nowrap ${
              isActive
                ? option.activeClass
                : 'text-white/40 hover:bg-white/[0.04] hover:text-white/60'
            }`}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
};

export default PaymentStatusFilter;
