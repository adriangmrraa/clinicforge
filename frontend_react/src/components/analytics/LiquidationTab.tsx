import React, { useEffect, useState, useCallback } from 'react';
import { FileText, ExternalLink, RefreshCw, Loader2, Zap, Database } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import { useAuth } from '../../context/AuthContext';
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
  const { user } = useAuth();
  const isCEO = user?.role === 'ceo';

  const [data, setData] = useState<LiquidationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [paymentStatus, setPaymentStatus] = useState<'all' | 'pending' | 'partial' | 'paid'>('all');

  // T5.1: Data source mode — 'computed' (on-the-fly) or 'persistent' (liquidation_records)
  const [dataSource, setDataSource] = useState<'computed' | 'persistent'>('computed');
  const [persistentLoading, setPersistentLoading] = useState(false);
  const [hasPersistentData, setHasPersistentData] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  // Computed-on-the-fly fetch (existing behavior)
  useEffect(() => {
    if (!startDate || !endDate) return;
    if (dataSource !== 'computed') return;

    const controller = new AbortController();

    async function fetchLiquidation() {
      setLoading(true);
      setFetchError(null);
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
        setFetchError(err instanceof Error ? err.message : 'Error al cargar liquidación');
        setData(null);
      } finally {
        setLoading(false);
      }
    }

    fetchLiquidation();

    return () => {
      controller.abort();
    };
  }, [startDate, endDate, paymentStatus, dataSource, professionalIds]);

  // T5.1: Fetch persistent liquidation records
  const fetchPersistentData = useCallback(async () => {
    if (!startDate || !endDate) return;
    setPersistentLoading(true);
    setFetchError(null);
    try {
      const params = new URLSearchParams({
        period_start: startDate,
        period_end: endDate,
        page: '1',
        page_size: '100',
      });
      if (professionalIds.length === 1) {
        params.set('professional_id', String(professionalIds[0]));
      }
      const res = await api.get(`/admin/liquidations?${params}`);
      const liquidations = res.data.liquidations || [];
      setHasPersistentData(liquidations.length > 0);

      if (liquidations.length > 0) {
        // Transform liquidation_records into the LiquidationResponse shape
        const transformed: LiquidationProfessional[] = liquidations.map((l: any) => ({
          id: l.professional_id,
          name: l.professional_name,
          total_billed: l.total_billed || 0,
          total_paid: l.total_paid || 0,
          total_pending: l.total_pending || 0,
          commission_pct: l.commission_pct || 0,
          commission_amount: l.commission_amount || 0,
          payout_amount: l.payout_amount || 0,
          status: l.status,
          sessions: [],
          patients: 0,
          appointments: 0,
          treatment_groups: [],
        }));

        const totals = liquidations.reduce(
          (acc: any, l: any) => ({
            total_billed: (acc.total_billed || 0) + (l.total_billed || 0),
            total_paid: (acc.total_paid || 0) + (l.total_paid || 0),
            total_pending: (acc.total_pending || 0) + (l.total_pending || 0),
            total_commission: (acc.total_commission || 0) + (l.commission_amount || 0),
            total_payout: (acc.total_payout || 0) + (l.payout_amount || 0),
          }),
          {}
        );

        setData({ professionals: transformed, totals });
      } else {
        setData(null);
      }
    } catch (err: any) {
      // Fallback to computed if persistent endpoint fails
      console.warn('Persistent liquidation fetch failed, falling back to computed:', err);
      setHasPersistentData(false);
      setDataSource('computed');
    } finally {
      setPersistentLoading(false);
    }
  }, [startDate, endDate, professionalIds]);

  // When switching to persistent mode, fetch data
  useEffect(() => {
    if (dataSource === 'persistent' && startDate && endDate) {
      fetchPersistentData();
    }
  }, [dataSource, fetchPersistentData, startDate, endDate]);

  const handleToggleDataSource = () => {
    const next = dataSource === 'computed' ? 'persistent' : 'computed';
    setDataSource(next);
    setData(null);
  };

  // T5.1: Generate bulk liquidations
  const handleGenerateBulk = async () => {
    setGenerating(true);
    try {
      const res = await api.post('/admin/liquidations/generate-bulk', {
        period_start: startDate,
        period_end: endDate,
      });
      const { generated_count, skipped_count } = res.data;
      let msg = '';
      if (generated_count > 0) msg += `${generated_count} ${t('liquidation.new_generated')}`;
      if (skipped_count > 0) msg += (msg ? '. ' : '') + `${skipped_count} ${t('liquidation.already_exists')}`;
      alert(msg || t('liquidation.generated_success'));
      // Refresh persistent data if in that mode
      if (dataSource === 'persistent') {
        fetchPersistentData();
      }
    } catch (err: any) {
      console.error('Error generating liquidations:', err);
      alert(err.response?.data?.detail || 'Error al generar liquidaciones');
    } finally {
      setGenerating(false);
    }
  };

  // Client-side filter by professionalIds when multiple are selected
  const visibleProfessionals: LiquidationProfessional[] = React.useMemo(() => {
    if (!data) return [];
    if (professionalIds.length <= 1) return data.professionals;
    return data.professionals.filter((p) => professionalIds.includes(p.id));
  }, [data, professionalIds]);

  const handlePaymentStatusChange = (v: string) => {
    setPaymentStatus(v as 'all' | 'pending' | 'partial' | 'paid');
  };

  const isEmpty = !loading && !persistentLoading && visibleProfessionals.length === 0;
  const isLoading = loading || persistentLoading;

  return (
    <div className="space-y-5">
      {/* T5.1: Data source toggle + Generate button (CEO only) */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleToggleDataSource}
          className={`flex items-center gap-2 px-3 py-1.5 rounded-xl text-xs font-medium transition-colors ${
            dataSource === 'persistent'
              ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
              : 'bg-white/[0.04] text-white/50 border border-white/[0.08]'
          }`}
          title={dataSource === 'persistent' ? t('liquidation.using_persistent', 'Usando liquidaciones generadas') : t('liquidation.using_realtime', 'Usando datos en tiempo real')}
        >
          {dataSource === 'persistent' ? (
            <Database size={12} />
          ) : (
            <Zap size={12} />
          )}
          {dataSource === 'persistent'
            ? t('liquidation.using_persistent', 'Liquidaciones generadas')
            : t('liquidation.using_realtime', 'Datos en tiempo real')}
        </button>

        {isCEO && (
          <button
            onClick={handleGenerateBulk}
            disabled={generating || !startDate || !endDate}
            className="flex items-center gap-2 px-3 py-1.5 bg-emerald-500/15 text-emerald-400 rounded-xl text-xs font-medium hover:bg-emerald-500/25 transition-colors disabled:opacity-40"
          >
            {generating ? (
              <Loader2 size={12} className="animate-spin" />
            ) : (
              <RefreshCw size={12} />
            )}
            {generating ? t('liquidation.generating') : t('finance.generate_liquidations')}
          </button>
        )}

        {isCEO && (
          <a
            href="/finanzas?tab=liquidaciones"
            className="ml-auto flex items-center gap-1.5 text-xs text-blue-400 hover:text-blue-300 transition-colors"
          >
            {t('liquidation.view_in_finance', 'Ver en Finanzas')} <ExternalLink size={12} />
          </a>
        )}
      </div>

      {/* Summary cards */}
      <LiquidationSummary
        totals={data?.totals ?? null}
        loading={isLoading}
      />

      {/* Filter row */}
      <div className="flex items-center justify-between gap-4 flex-wrap border-b border-white/[0.04] pb-4 mb-4">
        <PaymentStatusFilter
          value={paymentStatus}
          onChange={handlePaymentStatusChange}
        />
        <ExportCSVButton data={data} disabled={isLoading || isEmpty} />
      </div>

      {/* Error state */}
      {fetchError && isEmpty && (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <p className="text-amber-400/60 text-sm mb-3">{fetchError}</p>
          <button
            onClick={() => {
              setFetchError(null);
              if (dataSource === 'persistent') {
                fetchPersistentData();
              }
            }}
            className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-xl hover:bg-blue-500/30 transition-colors text-sm font-medium"
          >
            {t('finance.retry')}
          </button>
        </div>
      )}

      {/* Professional list */}
      {!isEmpty ? (
        <div className="space-y-3">
          {visibleProfessionals.map((prof, i) => (
            <div
              key={prof.id}
              style={{ animation: 'slideUp 0.35s ease-out both', animationDelay: `${i * 60}ms` }}
            >
              <ProfessionalAccordion
                professional={prof}
                formatCurrency={formatCurrency}
              />
            </div>
          ))}
        </div>
      ) : (
        !isLoading && !fetchError && (
          <div className="flex flex-col items-center justify-center py-16 text-center animate-fade-in">
            <div
              className="w-14 h-14 rounded-2xl bg-white/[0.04] flex items-center justify-center mb-4 ring-1 ring-white/[0.06]"
              style={{ animation: 'slideUp 0.4s ease-out' }}
            >
              <FileText size={26} className="text-white/20" />
            </div>
            <p className="text-white/40 text-sm font-medium">{t('liquidation.no_data')}</p>
          </div>
        )
      )}
    </div>
  );
};

export default LiquidationTab;
