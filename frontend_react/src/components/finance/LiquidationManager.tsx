import { useState, useEffect, useCallback } from 'react';
import {
  RefreshCw,
  Plus,
  Eye,
  CheckCircle,
  DollarSign,
  FileText,
  ChevronDown,
  ChevronRight,
  Download,
  Filter,
  AlertTriangle,
  X,
  Loader2,
} from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import api from '../../api/axios';
import GlassCard from '../GlassCard';
import LiquidationStatusBadge from './LiquidationStatusBadge';
import type { LiquidationRecord, TreatmentGroup, ProfessionalPayout } from '../../types/finance';

interface LiquidationManagerProps {
  periodStart: string;
  periodEnd: string;
  formatCurrency: (n: number) => string;
}

const PAGE_SIZE = 20;

export default function LiquidationManager({ periodStart, periodEnd, formatCurrency }: LiquidationManagerProps) {
  const { t } = useTranslation();
  const [liquidations, setLiquidations] = useState<LiquidationRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailData, setDetailData] = useState<{
    treatment_groups: TreatmentGroup[];
    payouts: ProfessionalPayout[];
  } | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [confirmAction, setConfirmAction] = useState<{
    id: string;
    action: 'approve' | 'paid';
    name: string;
  } | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState<string | null>(null);
  const [emailModal, setEmailModal] = useState<{
    id: string;
    name: string;
    email: string;
  } | null>(null);
  const [emailSending, setEmailSending] = useState(false);
  const [customEmail, setCustomEmail] = useState('');

  const fetchLiquidations = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        period_start: periodStart,
        period_end: periodEnd,
        page: String(page),
        page_size: String(PAGE_SIZE),
      });
      if (statusFilter !== 'all') {
        params.set('status', statusFilter);
      }
      const res = await api.get(`/admin/liquidations?${params}`);
      setLiquidations(res.data.liquidations || res.data);
      setTotalPages(res.data.total_pages || 1);
      setTotalCount(res.data.total || res.data.length || 0);
    } catch (err: any) {
      console.error('Error fetching liquidations:', err);
      setError(err.response?.data?.detail || 'Error al cargar liquidaciones');
    } finally {
      setLoading(false);
    }
  }, [periodStart, periodEnd, page, statusFilter]);

  useEffect(() => {
    fetchLiquidations();
  }, [fetchLiquidations]);

  const handleGenerateBulk = async () => {
    setGenerating(true);
    try {
      const res = await api.post('/admin/liquidations/generate-bulk', {
        period_start: periodStart,
        period_end: periodEnd,
      });
      const { generated_count, skipped_count } = res.data;
      let msg = '';
      if (generated_count > 0) msg += `${generated_count} ${t('liquidation.new_generated')}`;
      if (skipped_count > 0) msg += (msg ? '. ' : '') + `${skipped_count} ${t('liquidation.already_exists')}`;
      alert(msg || t('liquidation.generated_success'));
      fetchLiquidations();
    } catch (err: any) {
      console.error('Error generating liquidations:', err);
      alert(err.response?.data?.detail || 'Error al generar liquidaciones');
    } finally {
      setGenerating(false);
    }
  };

  const handleExpand = async (id: string) => {
    if (expandedId === id) {
      setExpandedId(null);
      setDetailData(null);
      return;
    }
    setExpandedId(id);
    setDetailData(null);
    try {
      const res = await api.get(`/admin/liquidations/${id}`);
      setDetailData({
        treatment_groups: res.data.treatment_groups || [],
        payouts: res.data.payouts || [],
      });
    } catch (err) {
      console.error('Error fetching liquidation detail:', err);
    }
  };

  const handleStatusUpdate = async (id: string, newStatus: 'approved' | 'paid') => {
    setUpdating(id);
    try {
      await api.patch(`/admin/liquidations/${id}`, { status: newStatus });
      setConfirmAction(null);
      fetchLiquidations();
    } catch (err: any) {
      console.error('Error updating status:', err);
      alert(err.response?.data?.detail || 'Error al actualizar estado');
    } finally {
      setUpdating(null);
    }
  };

  const handleDownloadPDF = async (id: string) => {
    setPdfLoading(id);
    try {
      const response = await api.get(`/admin/liquidations/${id}/pdf`, {
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `liquidacion_${id}.pdf`;
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

  const handleSendEmail = async () => {
    if (!emailModal) return;
    setEmailSending(true);
    try {
      const payload: { to_email?: string } = {};
      if (customEmail.trim()) {
        payload.to_email = customEmail.trim();
      }
      await api.post(`/admin/liquidations/${emailModal.id}/send-email`, payload);
      setEmailModal(null);
      setCustomEmail('');
      alert(t('liquidation.email_sent_success') || 'Liquidación enviada por email correctamente');
    } catch (err: any) {
      console.error('Error sending email:', err);
      alert(err.response?.data?.detail || 'Error al enviar email');
    } finally {
      setEmailSending(false);
    }
  };

  const openEmailModal = (liq: LiquidationRecord) => {
    setEmailModal({
      id: liq.id,
      name: liq.professional_name,
      email: '',
    });
    setCustomEmail('');
  };

  const handleExportCSV = () => {
    const headers = ['Profesional', 'Período', 'Facturado', 'Comisión %', 'Comisión $', 'Payout', 'Estado', 'Generado'];
    const rows = liquidations.map((l) => [
      l.professional_name,
      `${l.period_start} — ${l.period_end}`,
      l.total_billed,
      l.commission_pct,
      l.commission_amount,
      l.payout_amount,
      l.status,
      l.generated_at,
    ]);
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `liquidaciones_${periodStart}_${periodEnd}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const formatPeriod = (start: string, end: string) => {
    const d = new Date(start + 'T00:00:00');
    const months = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic'];
    return `${months[d.getMonth()]} ${d.getFullYear()}`;
  };

  if (error && liquidations.length === 0) {
    return (
      <GlassCard>
        <div className="p-8 text-center">
          <AlertTriangle size={32} className="text-amber-400 mx-auto mb-3" />
          <p className="text-white/60 mb-4">{error}</p>
          <button
            onClick={fetchLiquidations}
            className="px-4 py-2 bg-blue-500/20 text-blue-400 rounded-xl hover:bg-blue-500/30 transition-colors text-sm font-medium"
          >
            {t('common.error')} — {t('finance.retry')}
          </button>
        </div>
      </GlassCard>
    );
  }

  return (
    <div className="space-y-4">
      {/* Action Bar */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleGenerateBulk}
          disabled={generating}
          className="flex items-center gap-2 px-4 py-2.5 bg-primary hover:bg-primary/80 text-white rounded-xl text-sm font-medium transition-colors disabled:opacity-50"
        >
          {generating ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <RefreshCw size={16} />
          )}
          {generating ? t('liquidation.generating') : t('finance.generate_liquidations')}
        </button>

        <div className="flex items-center gap-2 ml-auto">
          <Filter size={14} className="text-white/30" />
          <select
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
            className="bg-white/[0.04] border border-white/[0.08] text-white text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-blue-500/40"
          >
            <option value="all">{t('liquidation.filter_all')}</option>
            <option value="draft">{t('finance.status_draft')}</option>
            <option value="generated">{t('finance.status_generated')}</option>
            <option value="approved">{t('finance.status_approved')}</option>
            <option value="paid">{t('finance.status_paid')}</option>
          </select>

          <button
            onClick={handleExportCSV}
            className="flex items-center gap-2 px-3 py-2 bg-white/[0.04] border border-white/[0.08] text-white/60 rounded-lg text-sm hover:bg-white/[0.06] transition-colors"
          >
            <Download size={14} />
            {t('liquidation.export_csv')}
          </button>
        </div>
      </div>

      {/* Loading State */}
      {loading && liquidations.length === 0 && (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="bg-white/[0.03] border border-white/[0.04] rounded-2xl p-4 animate-pulse">
              <div className="h-5 bg-white/[0.06] rounded w-32 mb-3" />
              <div className="h-4 bg-white/[0.06] rounded w-full" />
            </div>
          ))}
        </div>
      )}

      {/* Empty State */}
      {!loading && liquidations.length === 0 && (
        <GlassCard>
          <div className="p-8 text-center text-white/30">
            <FileText size={32} className="mx-auto mb-3 opacity-50" />
            <p className="text-sm">{t('liquidation.no_liquidations')}</p>
            <p className="text-xs mt-1">{t('liquidation.no_liquidations_desc')}</p>
          </div>
        </GlassCard>
      )}

      {/* Liquidation Table */}
      {!loading && liquidations.length > 0 && (
        <>
          <GlassCard hoverScale={false}>
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse min-w-[700px]">
                <thead>
                  <tr className="border-b border-white/[0.06]">
                    <th className="px-4 py-3 text-[11px] font-bold text-white/30 uppercase tracking-wider w-8"></th>
                    <th className="px-4 py-3 text-[11px] font-bold text-white/30 uppercase tracking-wider">
                      {t('approvals.full_name')}
                    </th>
                    <th className="px-4 py-3 text-[11px] font-bold text-white/30 uppercase tracking-wider">
                      {t('liquidation.period')}
                    </th>
                    <th className="px-4 py-3 text-[11px] font-bold text-white/30 uppercase tracking-wider text-right">
                      {t('liquidation.billed')}
                    </th>
                    <th className="px-4 py-3 text-[11px] font-bold text-white/30 uppercase tracking-wider text-center">
                      {t('finance.commission')}
                    </th>
                    <th className="px-4 py-3 text-[11px] font-bold text-white/30 uppercase tracking-wider text-right">
                      {t('liquidation.payout')}
                    </th>
                    <th className="px-4 py-3 text-[11px] font-bold text-white/30 uppercase tracking-wider text-center">
                      {t('billing.status')}
                    </th>
                    <th className="px-4 py-3 text-[11px] font-bold text-white/30 uppercase tracking-wider text-center">
                      {t('patients.actions')}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/[0.04]">
                  {liquidations.map((liq) => (
                    <>
                      <tr
                        key={liq.id}
                        className="hover:bg-white/[0.04] transition-colors cursor-pointer"
                        onClick={() => handleExpand(liq.id)}
                      >
                        <td className="px-4 py-3">
                          {expandedId === liq.id ? (
                            <ChevronDown size={14} className="text-white/40" />
                          ) : (
                            <ChevronRight size={14} className="text-white/30" />
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-sm font-medium text-white">{liq.professional_name}</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs text-white/50">{formatPeriod(liq.period_start, liq.period_end)}</span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span className="text-sm font-semibold text-white">{formatCurrency(liq.total_billed)}</span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <span className="text-sm text-white/60">{liq.commission_pct}%</span>
                            {liq.commission_pct === 0 && (
                              <AlertTriangle size={12} className="text-amber-400" title={t('liquidation.commission_warning')} />
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <span className="text-sm font-medium text-emerald-400">{formatCurrency(liq.payout_amount)}</span>
                        </td>
                        <td className="px-4 py-3 text-center">
                          <LiquidationStatusBadge status={liq.status} />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-center gap-1" onClick={(e) => e.stopPropagation()}>
                            <button
                              onClick={() => handleExpand(liq.id)}
                              className="p-1.5 hover:bg-white/[0.06] rounded-lg text-white/40 hover:text-white/70 transition-colors"
                              title={t('finance.see_detail')}
                            >
                              <Eye size={14} />
                            </button>
                            {(liq.status === 'draft' || liq.status === 'generated') && (
                              <button
                                onClick={() =>
                                  setConfirmAction({ id: liq.id, action: 'approve', name: liq.professional_name })
                                }
                                className="p-1.5 hover:bg-emerald-500/10 rounded-lg text-white/40 hover:text-emerald-400 transition-colors"
                                title={t('finance.approve')}
                              >
                                <CheckCircle size={14} />
                              </button>
                            )}
                            {liq.status === 'approved' && (
                              <button
                                onClick={() =>
                                  setConfirmAction({ id: liq.id, action: 'paid', name: liq.professional_name })
                                }
                                className="p-1.5 hover:bg-purple-500/10 rounded-lg text-white/40 hover:text-purple-400 transition-colors"
                                title={t('finance.mark_paid')}
                              >
                                <DollarSign size={14} />
                              </button>
                            )}
                            {(liq.status === 'generated' || liq.status === 'approved' || liq.status === 'paid') && (
                              <>
                                <button
                                  onClick={() => handleDownloadPDF(liq.id)}
                                  disabled={pdfLoading === liq.id}
                                  className="p-1.5 hover:bg-blue-500/10 rounded-lg text-white/40 hover:text-blue-400 transition-colors disabled:opacity-50"
                                  title={t('professional_liquidations.download_pdf')}
                                >
                                  {pdfLoading === liq.id ? (
                                    <Loader2 size={14} className="animate-spin" />
                                  ) : (
                                    <Download size={14} />
                                  )}
                                </button>
                                <button
                                  onClick={() => openEmailModal(liq)}
                                  className="p-1.5 hover:bg-purple-500/10 rounded-lg text-white/40 hover:text-purple-400 transition-colors"
                                  title={t('liquidation.send_email')}
                                >
                                  <FileText size={14} />
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* Expanded Detail */}
                      {expandedId === liq.id && detailData && (
                        <tr>
                          <td colSpan={8} className="bg-white/[0.02] px-4 py-4">
                            {/* Summary */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
                              <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                                <p className="text-[10px] text-white/30 uppercase">{t('liquidation.total_billed')}</p>
                                <p className="text-sm font-bold text-white">{formatCurrency(liq.total_billed)}</p>
                              </div>
                              <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                                <p className="text-[10px] text-white/30 uppercase">{t('liquidation.total_paid')}</p>
                                <p className="text-sm font-bold text-emerald-400">{formatCurrency(liq.total_paid)}</p>
                              </div>
                              <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                                <p className="text-[10px] text-white/30 uppercase">{t('finance.commission')}</p>
                                <p className="text-sm font-bold text-blue-400">
                                  {liq.commission_pct}% ({formatCurrency(liq.commission_amount)})
                                </p>
                              </div>
                              <div className="bg-white/[0.04] rounded-xl p-3 text-center">
                                <p className="text-[10px] text-white/30 uppercase">{t('liquidation.payout')}</p>
                                <p className="text-sm font-bold text-purple-400">{formatCurrency(liq.payout_amount)}</p>
                              </div>
                            </div>

                            {/* Treatment Groups */}
                            {detailData.treatment_groups.length > 0 && (
                              <div className="mb-4">
                                <h4 className="text-xs font-bold text-white/50 uppercase mb-2">
                                  {t('liquidation.detail_by_patient')}
                                </h4>
                                {detailData.treatment_groups.map((group, gi) => (
                                  <TreatmentGroupDetail
                                    key={gi}
                                    group={group}
                                    formatCurrency={formatCurrency}
                                  />
                                ))}
                              </div>
                            )}

                            {/* Payout History */}
                            {detailData.payouts.length > 0 && (
                              <div>
                                <h4 className="text-xs font-bold text-white/50 uppercase mb-2">
                                  {t('liquidation.payout_history')}
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
                              </div>
                            )}

                            {detailData.treatment_groups.length === 0 && detailData.payouts.length === 0 && (
                              <p className="text-center text-white/30 text-xs py-4">{t('liquidation.no_data')}</p>
                            )}
                          </td>
                        </tr>
                      )}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between text-xs text-white/40">
              <span>
                {t('leads.showing')} {(page - 1) * PAGE_SIZE + 1}-{Math.min(page * PAGE_SIZE, totalCount)}{' '}
                {t('leads.of')} {totalCount}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg disabled:opacity-30 hover:bg-white/[0.06] transition-colors"
                >
                  {t('common.back')}
                </button>
                <span className="px-3 py-1.5">
                  {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] rounded-lg disabled:opacity-30 hover:bg-white/[0.06] transition-colors"
                >
                  {t('leads.next', 'Siguiente')}
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Confirmation Dialog */}
      {confirmAction && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#12121a] border border-white/[0.08] rounded-2xl p-6 max-w-sm w-full mx-4 shadow-2xl">
            <h3 className="text-lg font-bold text-white mb-2">
              {confirmAction.action === 'approve' ? t('liquidation.confirm_approve') : t('liquidation.confirm_paid')}
            </h3>
            <p className="text-sm text-white/50 mb-6">
              {confirmAction.name} — {formatPeriod(
                liquidations.find((l) => l.id === confirmAction.id)?.period_start || '',
                liquidations.find((l) => l.id === confirmAction.id)?.period_end || ''
              )}
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setConfirmAction(null)}
                className="px-4 py-2 bg-white/[0.04] text-white/60 rounded-xl hover:bg-white/[0.06] transition-colors text-sm"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={() => handleStatusUpdate(confirmAction.id, confirmAction.action)}
                disabled={updating === confirmAction.id}
                className="px-4 py-2 bg-primary text-white rounded-xl hover:bg-primary/80 transition-colors text-sm font-medium disabled:opacity-50 flex items-center gap-2"
              >
                {updating === confirmAction.id && <Loader2 size={14} className="animate-spin" />}
                {confirmAction.action === 'approve' ? t('finance.approve') : t('finance.mark_paid')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Email Modal */}
      {emailModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[#12121a] border border-white/[0.08] rounded-2xl p-6 max-w-md w-full mx-4 shadow-2xl">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-white">
                {t('liquidation.send_email_title') || 'Enviar por Email'}
              </h3>
              <button
                onClick={() => { setEmailModal(null); setCustomEmail(''); }}
                className="p-1 hover:bg-white/[0.06] rounded-lg text-white/40 hover:text-white/70 transition-colors"
              >
                <X size={18} />
              </button>
            </div>
            <p className="text-sm text-white/50 mb-4">
              {t('liquidation.send_email_desc') || 'Enviar liquidación a'} <strong className="text-white">{emailModal.name}</strong>
            </p>
            <div className="mb-4">
              <label className="text-xs text-white/40 uppercase tracking-wider mb-1 block">
                {t('liquidation.email_recipient') || 'Email destinatario'}
              </label>
              <input
                type="email"
                value={customEmail}
                onChange={(e) => setCustomEmail(e.target.value)}
                placeholder={t('liquidation.email_placeholder') || 'Dejar vacío para usar email del profesional'}
                className="w-full bg-white/[0.04] border border-white/[0.08] text-white text-sm rounded-xl px-4 py-2.5 focus:outline-none focus:border-blue-500/40 placeholder:text-white/20"
              />
            </div>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => { setEmailModal(null); setCustomEmail(''); }}
                className="px-4 py-2 bg-white/[0.04] text-white/60 rounded-xl hover:bg-white/[0.06] transition-colors text-sm"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleSendEmail}
                disabled={emailSending}
                className="px-4 py-2 bg-primary text-white rounded-xl hover:bg-primary/80 transition-colors text-sm font-medium disabled:opacity-50 flex items-center gap-2"
              >
                {emailSending && <Loader2 size={14} className="animate-spin" />}
                {t('liquidation.send_email_btn') || 'Enviar'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Sub-component for treatment group detail in expanded row
function TreatmentGroupDetail({ group, formatCurrency }: { group: TreatmentGroup; formatCurrency: (n: number) => string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="bg-white/[0.02] border border-white/[0.04] rounded-xl mb-2 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-3 py-2.5 hover:bg-white/[0.04] transition-colors text-left flex items-center gap-2"
      >
        {open ? <ChevronDown size={14} className="text-white/30" /> : <ChevronRight size={14} className="text-white/30" />}
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
