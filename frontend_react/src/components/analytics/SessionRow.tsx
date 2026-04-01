import { useState } from 'react';
import { FileText, Calendar } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import type { LiquidationSession } from '../../types/liquidation';

interface Props {
  session: LiquidationSession;
  formatCurrency: (n: number) => string;
}

const PAYMENT_STATUS_STYLES: Record<LiquidationSession['payment_status'], string> = {
  paid: 'bg-emerald-500/10 text-emerald-400',
  partial: 'bg-amber-500/10 text-amber-400',
  pending: 'bg-red-500/10 text-red-400',
};

export default function SessionRow({ session, formatCurrency }: Props) {
  const { t } = useTranslation();
  const [showNotes, setShowNotes] = useState(false);

  const formattedDate = new Date(session.date).toLocaleDateString('es-AR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

  const formattedTime = new Date(session.date).toLocaleTimeString('es-AR', {
    hour: '2-digit',
    minute: '2-digit',
  });

  const paymentLabel: Record<LiquidationSession['payment_status'], string> = {
    paid: t('liquidation.status_paid'),
    partial: t('liquidation.status_partial'),
    pending: t('liquidation.status_pending'),
  };

  return (
    <div className="border-b border-white/[0.04] last:border-b-0">
      {/* Main row */}
      <div className="px-4 py-2 grid grid-cols-[1fr_auto_auto_auto_auto] items-center gap-3">
        {/* Date + time */}
        <div className="flex items-center gap-1.5 min-w-0">
          <Calendar size={12} className="text-white/20 shrink-0" />
          <span className="text-xs text-white/60 truncate">
            {formattedDate}
            <span className="text-white/30 ml-1">{formattedTime}</span>
          </span>
        </div>

        {/* Amount */}
        <span className="text-xs text-white font-medium tabular-nums whitespace-nowrap">
          {formatCurrency(session.billing_amount)}
        </span>

        {/* Payment status badge */}
        <span className={`text-xs px-2 py-0.5 rounded-full whitespace-nowrap ${PAYMENT_STATUS_STYLES[session.payment_status]}`}>
          {paymentLabel[session.payment_status]}
        </span>

        {/* Billing notes (truncated) */}
        {session.billing_notes ? (
          <span className="text-xs text-white/30 truncate max-w-[120px]" title={session.billing_notes}>
            {session.billing_notes}
          </span>
        ) : (
          <span />
        )}

        {/* Clinical notes toggle */}
        {session.clinical_notes ? (
          <button
            onClick={() => setShowNotes(prev => !prev)}
            title={t('liquidation.toggle_notes')}
            className={`p-1 rounded transition-colors ${
              showNotes
                ? 'text-blue-400 bg-blue-500/10'
                : 'text-white/20 hover:text-white/50 hover:bg-white/[0.04]'
            }`}
          >
            <FileText size={12} />
          </button>
        ) : (
          <span />
        )}
      </div>

      {/* Clinical notes panel */}
      {showNotes && (
        <div className="px-4 pb-2">
          <div className="bg-white/[0.02] rounded-lg p-3 mt-1 mb-2 ml-8">
            <p className="text-white/40 text-xs mb-1">{t('liquidation.clinical_notes')}:</p>
            {session.clinical_notes ? (
              <p className="text-white/60 text-sm leading-relaxed">{session.clinical_notes}</p>
            ) : (
              <p className="text-white/20 text-sm italic">{t('liquidation.no_clinical_notes')}</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
