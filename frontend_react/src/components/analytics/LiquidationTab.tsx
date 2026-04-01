import React, { useEffect, useState } from 'react';
import { FileText } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import api from '../../api/axios';
import LiquidationSummary from './LiquidationSummary';
import PaymentStatusFilter from './PaymentStatusFilter';
import { ExportCSVButton } from './ExportCSVButton';
import type { LiquidationResponse, LiquidationProfessional } from '../../types/liquidation';

// ProfessionalAccordion is created by another agent — import path is consistent
// with the analytics directory convention used across this folder.
import ProfessionalAccordion from './ProfessionalAccordion';

interface LiquidationTabProps {
  startDate: string;
  endDate: string;
  professionalIds: number[];
}

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 0,
  }).format(amount);
}

const LiquidationTab: React.FC<LiquidationTabProps> = ({
  startDate,
  endDate,
  professionalIds,
}) => {
  const { t } = useTranslation();

  const [data, setData] = useState<LiquidationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [paymentStatus, setPaymentStatus] = useState<'all' | 'pending' | 'partial' | 'paid'>('all');

  useEffect(() => {
    if (!startDate || !endDate) return;

    const controller = new AbortController();

    async function fetchLiquidation() {
      setLoading(true);
      try {
        let url = `/admin/analytics/professionals/liquidation?start_date=${startDate}&end_date=${endDate}`;
        if (paymentStatus !== 'all') {
          url += `&payment_status=${paymentStatus}`;
        }
        if (professionalIds.length === 1) {
          url += `&professional_id=${professionalIds[0]}`;
        }

        const response = await api.get<LiquidationResponse>(url, {
          signal: controller.signal,
        });
        setData(response.data);
      } catch (err: unknown) {
        if (err instanceof Error && err.name === 'CanceledError') return;
        setData(null);
      } finally {
        setLoading(false);
      }
    }

    fetchLiquidation();

    return () => {
      controller.abort();
    };
  }, [startDate, endDate, paymentStatus]);

  // Client-side filter by professionalIds when multiple are selected
  const visibleProfessionals: LiquidationProfessional[] = React.useMemo(() => {
    if (!data) return [];
    if (professionalIds.length <= 1) return data.professionals;
    return data.professionals.filter((p) => professionalIds.includes(p.id));
  }, [data, professionalIds]);

  const handlePaymentStatusChange = (v: string) => {
    setPaymentStatus(v as 'all' | 'pending' | 'partial' | 'paid');
  };

  const isEmpty = !loading && visibleProfessionals.length === 0;

  return (
    <div className="space-y-5">
      {/* Summary cards */}
      <LiquidationSummary
        totals={data?.totals ?? null}
        loading={loading}
      />

      {/* Filter row */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <PaymentStatusFilter
          value={paymentStatus}
          onChange={handlePaymentStatusChange}
        />
        <ExportCSVButton data={data} disabled={loading || isEmpty} />
      </div>

      {/* Professional list */}
      {!isEmpty ? (
        <div className="space-y-3">
          {visibleProfessionals.map((professional) => (
            <ProfessionalAccordion
              key={professional.id}
              professional={professional}
              formatCurrency={formatCurrency}
            />
          ))}
        </div>
      ) : (
        !loading && (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-12 h-12 rounded-xl bg-white/[0.04] flex items-center justify-center mb-4">
              <FileText size={24} className="text-white/30" />
            </div>
            <p className="text-white/40 text-sm">{t('liquidation.empty_state')}</p>
          </div>
        )
      )}
    </div>
  );
};

export default LiquidationTab;
