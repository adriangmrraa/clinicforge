import { useTranslation } from '../../context/LanguageContext';

interface LiquidationStatusBadgeProps {
  status: 'draft' | 'generated' | 'approved' | 'paid';
}

const statusConfig: Record<LiquidationStatusBadgeProps['status'], { bg: string; text: string; dot: string; labelKey: string }> = {
  draft: {
    bg: 'bg-white/[0.06]',
    text: 'text-white/50',
    dot: 'bg-white/40',
    labelKey: 'finance.status_draft',
  },
  generated: {
    bg: 'bg-blue-500/10',
    text: 'text-blue-400',
    dot: 'bg-blue-400',
    labelKey: 'finance.status_generated',
  },
  approved: {
    bg: 'bg-emerald-500/10',
    text: 'text-emerald-400',
    dot: 'bg-emerald-400',
    labelKey: 'finance.status_approved',
  },
  paid: {
    bg: 'bg-purple-500/10',
    text: 'text-purple-400',
    dot: 'bg-purple-400',
    labelKey: 'finance.status_paid',
  },
};

export default function LiquidationStatusBadge({ status }: LiquidationStatusBadgeProps) {
  const { t } = useTranslation();
  const config = statusConfig[status];

  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot}`} />
      {t(config.labelKey)}
    </span>
  );
}
