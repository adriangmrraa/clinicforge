import React from 'react';
import { DollarSign, CheckCircle, Clock, Calendar } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import type { LiquidationTotals } from '../../types/liquidation';

interface LiquidationSummaryProps {
  totals: LiquidationTotals | null;
  loading: boolean;
}

function formatCurrency(amount: number): string {
  if (amount >= 1_000_000) {
    return `$ ${(amount / 1_000_000).toFixed(1)}M`;
  }
  if (amount >= 100_000) {
    return `$ ${Math.round(amount / 1000)}K`;
  }
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 0,
  }).format(amount);
}

const SkeletonCard: React.FC = () => (
  <div className="bg-white/[0.03] border border-white/[0.04] rounded-2xl p-4 animate-pulse">
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
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map((i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    );
  }

  const pct = totals && totals.billed > 0 ? Math.round((totals.paid / totals.billed) * 100) : 0;

  const cards = [
    {
      label: t('liquidation.total_billed'),
      value: totals ? formatCurrency(totals.billed) : '—',
      icon: <DollarSign size={20} />,
      iconClass: 'bg-white/[0.08] text-white/70',
      borderClass: 'border-l-2 border-l-blue-500/40',
      iconRingClass: 'ring-1 ring-blue-500/20 shadow-[0_0_12px_rgba(59,130,246,0.15)]',
      extra: null,
    },
    {
      label: t('liquidation.total_paid'),
      value: totals ? formatCurrency(totals.paid) : '—',
      icon: <CheckCircle size={20} />,
      iconClass: 'bg-emerald-500/10 text-emerald-400',
      borderClass: 'border-l-2 border-l-emerald-500/50',
      iconRingClass: 'ring-1 ring-emerald-500/20 shadow-[0_0_12px_rgba(16,185,129,0.15)]',
      extra: (
        <div className="mt-2">
          <div className="flex justify-between text-[10px] text-white/30 mb-1">
            <span>Cobrado</span>
            <span>{pct}%</span>
          </div>
          <div className="h-1 rounded-full bg-white/[0.06] overflow-hidden">
            <div
              className="h-full bg-emerald-500/70 rounded-full transition-all duration-700 ease-out"
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>
      ),
    },
    {
      label: t('liquidation.total_pending'),
      value: totals ? formatCurrency(totals.pending) : '—',
      icon: <Clock size={20} />,
      iconClass: 'bg-amber-500/10 text-amber-400',
      borderClass: 'border-l-2 border-l-amber-500/50',
      iconRingClass: 'ring-1 ring-amber-500/20 shadow-[0_0_12px_rgba(245,158,11,0.15)]',
      extra: null,
    },
    {
      label: t('liquidation.total_appointments'),
      value: totals ? String(totals.appointments) : '—',
      icon: <Calendar size={20} />,
      iconClass: 'bg-blue-500/10 text-blue-400',
      borderClass: 'border-l-2 border-l-blue-400/40',
      iconRingClass: 'ring-1 ring-blue-400/20 shadow-[0_0_12px_rgba(96,165,250,0.15)]',
      extra: null,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card, index) => (
        <div
          key={card.label}
          className={`bg-white/[0.03] border border-white/[0.04] rounded-2xl p-4 hover:scale-[1.02] transition-transform duration-300 ${card.borderClass}`}
          style={{
            animation: 'slideUp 0.35s ease-out both',
            animationDelay: `${index * 80}ms`,
            transitionTimingFunction: 'cubic-bezier(0.34, 1.56, 0.64, 1)',
          }}
        >
          <div className="flex items-start gap-3">
            <div className={`w-10 h-10 rounded-full flex items-center justify-center shrink-0 ${card.iconClass} ${card.iconRingClass}`}>
              {card.icon}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs text-white/50 mb-1 truncate">{card.label}</p>
              <p className="text-lg sm:text-xl font-bold text-white leading-tight truncate">{card.value}</p>
              {card.extra}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default LiquidationSummary;
