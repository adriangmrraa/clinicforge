import { useState, useEffect, useCallback } from 'react';
import { FileText, Calendar, TrendingUp, DollarSign, Percent, Download, Loader2, AlertTriangle } from 'lucide-react';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';
import GlassCard from '../components/GlassCard';
import LiquidationStatusBadge from '../components/finance/LiquidationStatusBadge';
import type { LiquidationRecord, TreatmentGroup, ProfessionalPayout } from '../types/finance';

/**
 * T4.2: ProfessionalLiquidationsView
 * Self-service portal for logged-in professionals to view their own liquidations.
 * Read-only: no approve, generate, or edit actions.
 * Fetches from GET /my/liquidations (JWT auth, not admin token).
 */

export default function ProfessionalLiquidationsView() {
  const { t } = useTranslation();
  const [liquidations, setLiquidations] = useState<LiquidationRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<{
    treatment_groups: TreatmentGroup[];
    payouts: ProfessionalPayout[];
  } | null>(null);
  const [pdfLoading, setPdfLoading] = useState<string | null>(null);

  // Period filter (default: current month)
  const today = new Date();
  const defaultStart = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-01`;
  const defaultEnd = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(new Date(today.getFullYear(), today.getMonth() + 1, 0).getDate()).padStart(2, '0')}`;
  const [periodStart, setPeriodStart] = useState(defaultStart);
  const [periodEnd, setPeriodEnd] = useState(defaultEnd);

  // Summary calculations
  const totalBilled = liquidations.reduce((sum, l) => sum + l.total_billed, 0);
  const totalPaid = liquidations.reduce((sum, l) => sum + l.total_paid, 0);
  const totalCommission = liquidations.reduce((sum, l) => sum + l.commission_amount, 0);
  const totalToCollect = liquidations.reduce((sum, l) => sum + l.payout_amount, 0);

  const fetchLiquidations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (periodStart) params.set('period_start', periodStart);
      if (periodEnd) params.set('period_end', periodEnd);

      const res = await api.get(`/my/liquidations?${params}`);
      setLiquidations(res.data.liquidations || []);
    } catch (err: any) {
      console.error('Error fetching my liquidations:', err);
      setError(err.response?.data?.detail || 'Error al cargar tus liquidaciones');
    } finally {
      setLoading(false);
    }
  }, [periodStart, periodEnd]);

  useEffect(() => {
    fetchLiquidations();
  }, [fetchLiquidations]);

  const handleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      setDetailData(null);
      return;
    }
    setExpandedId(id);
    setDetailData(null);
    try {
      const res = await api.get(`/my/liquidations/${id}`);
      setDetailData({
        treatment_groups: res.data.treatment_groups || [],
        payouts: res.data.payouts || [],
      });
    } catch (err) {
      console.error('Error fetching liquidation detail:', err);
    }
  };

  const handleDownloadPDF = async (id: string) => {
    setPdfLoading(id);
    try {
      const response = await api.get(`/my/liquidations/${id}/pdf`, {
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `mi-liquidacion-${id}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('Error downloading PDF:', err);
      alert(err.response?.data?.detail || 'Error al descargar PDF');
    } finally {
      setPdfLoading(null);
    }
  };

  const formatCurrency = (n: number) => {
    return new Intl.NumberFormat('es-AR', {
      style: 'currency',
      currency: 'ARS',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(n);
  };

  const formatPeriod = (start: string, end: string) => {
    const d = new Date(start + 'T00:00:00');
    const months = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'];
    return `${months[d.getMonth()]} ${d.getFullYear()}`;
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      {/* Header */}
      <div className="shrink-0 px-6 py-5 border-b border-white/[0.06]">
        <h1 className="text-xl font-bold text-white">{t('professional_liquidations.title', 'Mis Liquidaciones')}</h1>
        <p className="text-sm text-white/40 mt-1">
          {t('professional_liquidations.subtitle', 'Consultá el estado de tus liquidaciones y comisiones')}
        </p>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {/* Period Filter */}
        <GlassCard>
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex items-center gap-2">
              <Calendar size={16} className="text-white/30" />
              <label className="text-xs text-white/40 uppercase tracking-wider">Desde</label>
              <input
                type="date"
                value={periodStart}
                onChange={(e) => setPeriodStart(e.target.value)}
                className="bg-white/[0.04] border border-white/[0.08] text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500/40"
              />
            </div>
            <div className="flex items-center gap-2">
              <Calendar size={16} className="text-white/30" />
              <label className="text-xs text-white/40 uppercase tracking-wider">Hasta</label>
              <input
                type="date"
                value={periodEnd}
                onChange={(e) => setPeriodEnd(e.target.value)}
                className="bg-white/[0.04] border border-white/[0.08] text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500/40"
              />
            </div>
            <button
              onClick={fetchLiquidations}
              disabled={loading}
              className="ml-auto flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/80 text-white rounded-xl text-sm font-medium transition-colors disabled:opacity-50"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : <TrendingUp size={14} />}
              {t('common.filter', 'Filtrar')}
            </button>
          </div>
        </GlassCard>

        {/* Summary Cards */}
        {!loading && liquidations.length > 0 && (
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <GlassCard>
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-blue-500/10 rounded-xl">
                  <DollarSign size={20} className="text-blue-400" />
                </div>
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">{t('professional_liquidations.total_billed', 'Total Facturado')}</p>
                  <p className="text-lg font-bold text-white">{formatCurrency(totalBilled)}</p>
                </div>
              </div>
            </GlassCard>

            <GlassCard>
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-emerald-500/10 rounded-xl">
                  <TrendingUp size={20} className="text-emerald-400" />
                </div>
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">{t('professional_liquidations.total_collected', 'Total Cobrado')}</p>
                  <p className="text-lg font-bold text-emerald-400">{formatCurrency(totalPaid)}</p>
                </div>
              </div>
            </GlassCard>

            <GlassCard>
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-amber-500/10 rounded-xl">
                  <Percent size={20} className="text-amber-400" />
                </div>
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">{t('professional_liquidations.commission_retained', 'Comisión Retenida')}</p>
                  <p className="text-lg font-bold text-amber-400">{formatCurrency(totalCommission)}</p>
                </div>
              </div>
            </GlassCard>

            <GlassCard>
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-purple-500/10 rounded-xl">
                  <DollarSign size={20} className="text-purple-400" />
                </div>
                <div>
                  <p className="text-[10px] text-white/30 uppercase tracking-wider">{t('professional_liquidations.to_collect', 'A Cobrar')}</p>
                  <p className="text-lg font-bold text-purple-400">{formatCurrency(totalToCollect)}</p>
                </div>
              </div>
            </GlassCard>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="space-y-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className="bg-white/[0.03] border border-white/[0.04] rounded-2xl p-4 animate-pulse">
                <div className="h-5 bg-white/[0.06] rounded w-32 mb-3" />
                <div className="h-4 bg-white/[0.06] rounded w-full" />
              </div>
            ))}
          </div>
        )}

        {/* Error State */}
        {error && liquidations.length === 0 && (
          <GlassCard>
            <div className="p-8 text-center">
              <AlertTriangle size={32} className="text-amber-400 mx-auto mb-3" />
              <p className="text-white/60 mb-4">{error}</p>
              <button
                onClick={fetchLiquidations}
                className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-xl hover:bg-blue-500/30 transition-colors text-sm font-medium"
              >
                {t('common.retry', 'Reintentar')}
              </button>
            </div>
          </GlassCard>
        )}

        {/* Empty State */}
        {!loading && liquidations.length === 0 && !error && (
          <GlassCard>
            <div className="p-8 text-center text-white/30">
              <FileText size={32} className="mx-auto mb-3 opacity-50" />
              <p className="text-sm">{t('professional_liquidations.no_liquidations', 'No tenés liquidaciones aún')}</p>
              <p className="text-xs mt-1">{t('professional_liquidations.no_liquidations_desc', 'Las liquidaciones se generan mensualmente')}</p>
            </div>
          </GlassCard>
        )}

        {/* Liquidation Cards List */}
        {!loading && liquidations.length > 0 && (
          <div className="space-y-3">
            {liquidations.map((liq) => (
              <div key={liq.id}>
                <GlassCard hoverScale={false}>
                  <div className="flex flex-wrap items-center gap-4">
                    {/* Period + Status */}
                    <div className="flex-1 min-w-[180px]">
                      <div className="flex items-center gap-2 mb-1">
                        <Calendar size={14} className="text-white/30" />
                        <span className="text-sm font-semibold text-white">
                          {formatPeriod(liq.period_start, liq.period_end)}
                        </span>
                      </div>
                      <LiquidationStatusBadge status={liq.status} />
                    </div>

                    {/* Financial Summary */}
                    <div className="flex flex-wrap items-center gap-4 text-sm">
                      <div className="text-center">
                        <p className="text-[10px] text-white/30 uppercase">{t('liquidation.billed', 'Facturado')}</p>
                        <p className="font-bold text-white">{formatCurrency(liq.total_billed)}</p>
                      </div>
                      <div className="text-center">
                        <p className="text-[10px] text-white/30 uppercase">{t('finance.commission', 'Comisión')}</p>
                        <p className="font-bold text-amber-400">
                          {liq.commission_pct}% ({formatCurrency(liq.commission_amount)})
                        </p>
                      </div>
                      <div className="text-center">
                        <p className="text-[10px] text-white/30 uppercase">{t('professional_liquidations.to_collect', 'A Cobrar')}</p>
                        <p className="font-bold text-purple-400">{formatCurrency(liq.payout_amount)}</p>
                      </div>
                      {liq.paid_at && (
                        <div className="text-center">
                          <p className="text-[10px] text-white/30 uppercase">{t('professional_liquidations.paid_on', 'Pagado el')}</p>
                          <p className="font-medium text-emerald-400 text-xs">
                            {new Date(liq.paid_at + 'T00:00:00').toLocaleDateString('es-AR')}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleExpand(liq.id)}
                        className="p-2 hover:bg-white/[0.06] rounded-lg text-white/40 hover:text-white/70 transition-colors"
                        title={t('finance.see_detail', 'Ver detalle')}
                      >
                        <FileText size={16} />
                      </button>
                      {(liq.status === 'generated' || liq.status === 'approved' || liq.status === 'paid') && (
                        <button
                          onClick={() => handleDownloadPDF(liq.id)}
                          disabled={pdfLoading === liq.id}
                          className="p-2 hover:bg-blue-500/10 rounded-lg text-white/40 hover:text-blue-400 transition-colors disabled:opacity-50"
                          title={t('professional_liquidations.download_pdf', 'Descargar PDF')}
                        >
                          {pdfLoading === liq.id ? (
                            <Loader2 size={16} className="animate-spin" />
                          ) : (
                            <Download size={16} />
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </GlassCard>

                {/* Expanded Detail */}
                {expandedId === liq.id && detailData && (
                  <div className="ml-4 mt-2 mb-2 space-y-3">
                    {/* Summary */}
                    <GlassCard>
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                          <p className="text-[10px] text-white/30 uppercase">{t('liquidation.total_billed', 'Facturado')}</p>
                          <p className="text-sm font-bold text-white">{formatCurrency(liq.total_billed)}</p>
                        </div>
                        <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                          <p className="text-[10px] text-white/30 uppercase">{t('liquidation.total_paid', 'Cobrado')}</p>
                          <p className="text-sm font-bold text-emerald-400">{formatCurrency(liq.total_paid)}</p>
                        </div>
                        <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                          <p className="text-[10px] text-white/30 uppercase">{t('finance.commission', 'Comisión')}</p>
                          <p className="text-sm font-bold text-blue-400">
                            {liq.commission_pct}% ({formatCurrency(liq.commission_amount)})
                          </p>
                        </div>
                        <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                          <p className="text-[10px] text-white/30 uppercase">{t('professional_liquidations.to_collect', 'A Cobrar')}</p>
                          <p className="text-sm font-bold text-purple-400">{formatCurrency(liq.payout_amount)}</p>
                        </div>
                      </div>
                    </GlassCard>

                    {/* Treatment Groups */}
                    {detailData.treatment_groups.length > 0 && (
                      <GlassCard>
                        <h4 className="text-xs font-bold text-white/50 uppercase mb-3">
                          {t('liquidation.detail_by_patient', 'Detalle por Paciente')}
                        </h4>
                        <div className="space-y-2">
                          {detailData.treatment_groups.map((group, gi) => (
                            <TreatmentGroupCard
                              key={gi}
                              group={group}
                              formatCurrency={formatCurrency}
                            />
                          ))}
                        </div>
                      </GlassCard>
                    )}

                    {/* Payout History */}
                    {detailData.payouts.length > 0 && (
                      <GlassCard>
                        <h4 className="text-xs font-bold text-white/50 uppercase mb-3">
                          {t('liquidation.payout_history', 'Historial de Pagos')}
                        </h4>
                        <div className="space-y-2">
                          {detailData.payouts.map((payout) => (
                            <div
                              key={payout.id}
                              className="flex items-center justify-between bg-white/[0.03] rounded-lg px-3 py-2 text-xs"
                            >
                              <span className="text-white/50">
                                {new Date(payout.payment_date + 'T00:00:00').toLocaleDateString('es-AR')}
                              </span>
                              <span className="text-white/60 capitalize">{payout.payment_method}</span>
                              {payout.reference_number && (
                                <span className="text-white/30 font-mono">{payout.reference_number}</span>
                              )}
                              <span className="text-emerald-400 font-semibold">
                                {formatCurrency(payout.amount)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </GlassCard>
                    )}

                    {detailData.treatment_groups.length === 0 && detailData.payouts.length === 0 && (
                      <GlassCard>
                        <p className="text-center text-white/30 text-xs py-4">{t('liquidation.no_data', 'Sin datos disponibles')}</p>
                      </GlassCard>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Sub-component: Treatment group card (collapsed/expandable)
 */
function TreatmentGroupCard({ group, formatCurrency }: { group: TreatmentGroup; formatCurrency: (n: number) => string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="bg-white/[0.02] border border-white/[0.04] rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-3 py-2.5 hover:bg-white/[0.04] transition-colors text-left flex items-center gap-2"
      >
        <span className={`text-white/30 transition-transform ${open ? 'rotate-90' : ''}`}>▸</span>
        <span className="text-sm font-medium text-white">{group.patient_name}</span>
        <span className="text-xs text-white/40">
          {group.treatment_name} — {group.sessions.length} {group.sessions.length === 1 ? 'sesión' : 'sesiones'}
        </span>
        <span className="ml-auto text-sm font-semibold text-white">{formatCurrency(group.total)}</span>
      </button>
      {open && (
        <div className="px-3 pb-3 space-y-1">
          {group.sessions.map((session, si) => (
            <div key={si} className="flex items-center justify-between text-xs py-1.5 border-t border-white/[0.03]">
              <span className="text-white/40">
                {new Date(session.date + 'T00:00:00').toLocaleDateString('es-AR')}
              </span>
              <span className="text-white/50">{session.description}</span>
              <span className="text-white/60">{formatCurrency(session.amount)}</span>
              <span
                className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                  session.payment_status === 'paid'
                    ? 'bg-emerald-500/10 text-emerald-400'
                    : session.payment_status === 'partial'
                    ? 'bg-amber-500/10 text-amber-400'
                    : 'bg-white/[0.06] text-white/40'
                }`}
              >
                {session.payment_status}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
