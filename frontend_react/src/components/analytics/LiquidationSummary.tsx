import React from 'react';
import { DollarSign, CheckCircle, Clock, Calendar } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import type { LiquidationTotals } from '../../types/liquidation';

interface LiquidationSummaryProps {
  totals: LiquidationTotals | null;
  loading: boolean;
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 0,
  }).format(amount);
}

const SkeletonCard: React.FC = () => (
  <div className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4 animate-pulse">
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 rounded-lg bg-white/[0.06] shrink-0" />
      <div className="flex-1 space-y-2 pt-1">
        <div className="h-3 bg-white/[0.06] rounded w-24" />
        <div className="h-6 bg-white/[0.06] rounded w-32" />
      </div>
    </div>
  </div>
);

const LiquidationSummary: React.FC<LiquidationSummaryProps> = ({ totals, loading }) => {
  const { t } = useTranslation();

  if (loading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  const cards = [
    {
      label: t('liquidation.total_billed'),
      value: totals ? formatCurrency(totals.billed) : '—',
      icon: <DollarSign size={20} />,
      iconClass: 'bg-white/[0.08] text-white/70',
    },
    {
      label: t('liquidation.total_paid'),
      value: totals ? formatCurrency(totals.paid) : '—',
      icon: <CheckCircle size={20} />,
      iconClass: 'bg-emerald-500/10 text-emerald-400',
    },
    {
      label: t('liquidation.total_pending'),
      value: totals ? formatCurrency(totals.pending) : '—',
      icon: <Clock size={20} />,
      iconClass: 'bg-amber-500/10 text-amber-400',
    },
    {
      label: t('liquidation.total_appointments'),
      value: totals ? String(totals.appointments) : '—',
      icon: <Calendar size={20} />,
      iconClass: 'bg-blue-500/10 text-blue-400',
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="bg-white/[0.03] border border-white/[0.06] rounded-xl p-4"
        >
          <div className="flex items-start gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center shrink-0 ${card.iconClass}`}>
              {card.icon}
            </div>
            <div className="min-w-0">
              <p className="text-xs text-white/50 mb-1 truncate">{card.label}</p>
              <p className="text-xl font-bold text-white leading-tight">{card.value}</p>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default LiquidationSummary;
