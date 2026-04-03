import { useState, useEffect, useCallback } from 'react';
import {
  DollarSign,
  Banknote,
  TrendingUp,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  Loader2,
} from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import api from '../../api/axios';
import GlassCard, { CARD_IMAGES } from '../GlassCard';
import type { ReconciliationData, Discrepancy } from '../../types/finance';

interface ReconciliationViewProps {
  periodStart: string;
  periodEnd: string;
  formatCurrency: (n: number) => string;
}

export default function ReconciliationView({ periodStart, periodEnd, formatCurrency }: ReconciliationViewProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<ReconciliationData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ignoring, setIgnoring] = useState<string | null>(null);
  const [confirmIgnore, setConfirmIgnore] = useState<Discrepancy | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        period_start: periodStart,
        period_end: periodEnd,
      });
      const res = await api.get(`/admin/reconciliation?${params}`);
      setData(res.data);
    } catch (err: any) {
      console.error('Error fetching reconciliation:', err);
      setError(err.response?.data?.detail || 'Error al cargar conciliación');
    } finally {
      setLoading(false);
    }
  }, [periodStart, periodEnd]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleIgnore = async (discrepancy: Discrepancy) => {
    setIgnoring(discrepancy.appointment_id);
    try {
      // Placeholder: in Phase 5 this will call a PATCH endpoint
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          discrepancies: prev.discrepancies.filter(
            (d) => d.appointment_id !== discrepancy.appointment_id
          ),
          discrepancy_count: prev.discrepancy_count - 1,
        };
      });
      setConfirmIgnore(null);
    } catch (err) {
      console.error('Error ignoring discrepancy:', err);
    } finally {
      setIgnoring(null);
    }
  };

  if (loading && !data) {
    return (
      <div className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => (
            <div key={i} className="bg-white/[0.03] border border-white/[0.04] rounded-2xl p-5 animate-pulse">
              <div className="w-10 h-10 rounded-xl bg-white/[0.06] mb-3" />
              <div className="h-7 bg-white/[0.06] rounded w-24 mb-2" />
              <div className="h-3 bg-white/[0.06] rounded w-32" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <GlassCard>
        <div className="p-8 text-center">
          <AlertTriangle size={32} className="text-amber-400 mx-auto mb-3" />
          <p className="text-white/60 mb-4">{error}</p>
          <button
            onClick={fetchData}
            className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-xl hover:bg-blue-500/30 transition-colors text-sm font-medium"
          >
            {t('finance.retry')}
          </button>
        </div>
      </GlassCard>
    );
  }

  if (!data) return null;

  const difference = (data.differences ?? data.total_patient_payments - data.total_professional_payouts);

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <GlassCard image={CARD_IMAGES.revenue}>
          <div className="p-5">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 flex items-center justify-center text-emerald-400">
                <DollarSign size={20} />
              </div>
              <div>
                <p className="text-xs text-white/40">{t('reconciliation.total_patient_payments')}</p>
                <p className="text-xl font-bold text-white mt-1">{formatCurrency(data.total_patient_payments)}</p>
              </div>
            </div>
          </div>
        </GlassCard>

        <GlassCard image={CARD_IMAGES.analytics}>
          <div className="p-5">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400">
                <Banknote size={20} />
              </div>
              <div>
                <p className="text-xs text-white/40">{t('reconciliation.total_professional_payouts')}</p>
                <p className="text-xl font-bold text-white mt-1">{formatCurrency(data.total_professional_payouts)}</p>
              </div>
            </div>
          </div>
        </GlassCard>

        <GlassCard image={CARD_IMAGES.completion}>
          <div className="p-5">
            <div className="flex items-start gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${difference >= 0 ? 'bg-purple-500/10 text-purple-400' : 'bg-red-500/10 text-red-400'}`}>
                <TrendingUp size={20} />
              </div>
              <div>
                <p className="text-xs text-white/40">{t('reconciliation.difference')}</p>
                <p className={`text-xl font-bold mt-1 ${difference >= 0 ? 'text-purple-400' : 'text-red-400'}`}>
                  {formatCurrency(Math.abs(difference))}
                </p>
              </div>
            </div>
          </div>
        </GlassCard>
      </div>

      {/* Discrepancies */}
      <GlassCard hoverScale={false}>
        <div className="p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <AlertTriangle size={16} className="text-amber-400" />
              {t('reconciliation.discrepancies')} ({data.discrepancy_count})
            </h3>
            <button
              onClick={fetchData}
              className="flex items-center gap-1.5 text-xs text-white/40 hover:text-white/60 transition-colors"
            >
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
              {t('finance.refresh')}
            </button>
          </div>

          {data.discrepancies.length === 0 ? (
            <div className="py-12 text-center">
              <CheckCircle size={40} className="text-emerald-400/40 mx-auto mb-3" />
              <p className="text-sm text-white/50">{t('reconciliation.no_discrepancies')}</p>
              <p className="text-xs text-white/30 mt-1">{t('reconciliation.no_discrepancies_desc')}</p>
            </div>
          ) : (
            <div className="space-y-3">
              {data.discrepancies.map((d, i) => (
                <div
                  key={i}
                  className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4"
                >
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <AlertTriangle size={14} className="text-amber-400 shrink-0" />
                        <span className="text-sm font-medium text-white">
                          {t('finance.appointment')} #{d.appointment_id}
                        </span>
                      </div>
                      <p className="text-sm text-white/60">{d.patient_name}</p>
                      {d.treatment_name && (
                        <p className="text-xs text-white/40">{d.treatment_name}</p>
                      )}
                      {d.professional_name && (
                        <p className="text-xs text-white/30 mt-0.5">
                          {t('agenda.professional')}: {d.professional_name}
                        </p>
                      )}
                      <p className="text-xs text-white/30 mt-1">
                        {new Date(d.appointment_date + 'T00:00:00').toLocaleDateString('es-AR')}
                      </p>
                      <p className="text-xs text-amber-400/60 mt-1">{d.issue}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-sm font-bold text-white">{formatCurrency(d.amount)}</p>
                      <div className="flex gap-2 mt-2">
                        <button
                          className="px-2.5 py-1 bg-blue-500/10 text-blue-400 rounded-lg text-xs font-medium hover:bg-blue-500/20 transition-colors"
                          title={t('reconciliation.resolve')}
                        >
                          {t('reconciliation.resolve')}
                        </button>
                        <button
                          onClick={() => setConfirmIgnore(d)}
                          disabled={ignoring === d.appointment_id}
                          className="px-2.5 py-1 bg-white/[0.04] text-white/40 rounded-lg text-xs hover:bg-white/[0.06] transition-colors disabled:opacity-30"
                          title={t('reconciliation.ignore')}
                        >
                          {ignoring === d.appointment_id ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            t('reconciliation.ignore')
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </GlassCard>

      {/* Ignore Confirmation Dialog */}
      {confirmIgnore && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#12121a] border border-white/[0.08] rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl">
            <div className="flex items-center gap-2 mb-3">
              <XCircle size={20} className="text-amber-400" />
              <h3 className="text-lg font-bold text-white">{t('reconciliation.confirm_ignore')}</h3>
            </div>
            <p className="text-sm text-white/50 mb-2">
              {confirmIgnore.patient_name} — {formatCurrency(confirmIgnore.amount)}
            </p>
            <p className="text-xs text-white/30 mb-6">{t('reconciliation.ignore')}</p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setConfirmIgnore(null)}
                className="px-4 py-2 bg-white/[0.04] text-white/60 rounded-xl hover:bg-white/[0.06] transition-colors text-sm"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => handleIgnore(confirmIgnore)}
                disabled={ignoring === confirmIgnore.appointment_id}
                className="px-4 py-2 bg-amber-500/20 text-amber-400 rounded-xl hover:bg-amber-500/30 transition-colors text-sm font-medium disabled:opacity-50 flex items-center gap-2"
              >
                {ignoring === confirmIgnore.appointment_id && <Loader2 size={14} className="animate-spin" />}
                {t('reconciliation.ignore')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
