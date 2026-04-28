import { useState, useEffect } from 'react';
import { useTranslation } from '../context/LanguageContext';
import {
  Plus, Trash2, Loader2, Receipt, X, RefreshCw,
  Banknote, ArrowRightLeft, CreditCard, Check, AlertCircle,
  User, Mail, Download, Sparkles,
  CheckCircle2, Clock, Search, Edit2, Calendar
} from 'lucide-react';
import api from '../api/axios';

// ─── Types ──────────────────────────────────────────────────────────────────

type ViewState = 'loading' | 'empty' | 'appointments_only' | 'plan_view';

interface TreatmentPlan {
  id: string;
  name: string;
  status: 'draft' | 'approved' | 'in_progress' | 'completed' | 'cancelled';
  professional_id: number | null;
  professional_name: string | null;
  estimated_total: number;
  approved_total: number | null;
  approved_by: string | null;
  approved_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  items_count: number;
  paid_total: number;
  pending_total: number;
}

interface TreatmentPlanItem {
  id: string;
  treatment_type_code: string | null;
  treatment_type_name: string | null;
  custom_description: string | null;
  estimated_price: number;
  approved_price: number | null;
  status: 'pending' | 'in_progress' | 'completed' | 'cancelled';
  sort_order: number;
  appointments_count?: number;
}

interface TreatmentPlanPayment {
  id: string;
  amount: number;
  payment_method: 'cash' | 'transfer' | 'card';
  payment_date: string | null;
  recorded_by?: string | null;
  recorded_by_name?: string | null;
  notes: string | null;
  appointment_id?: number;
  installment_id?: string | null;
  installment_number?: number | null;
  payment_receipt_data?: {
    status?: 'verified' | 'pending' | 'review' | 'rejected';
    amount?: number;
  } | null;
}

interface TreatmentPlanInstallment {
  id: string;
  installment_number: number;
  amount: number;
  due_date: string;
  status: 'pending' | 'paid' | 'overdue';
  paid_at: string | null;
  payment_id: string | null;
}

interface TreatmentPlanDetail extends TreatmentPlan {
  items: TreatmentPlanItem[];
  payments: TreatmentPlanPayment[];
  installments?: TreatmentPlanInstallment[];
  installments_count?: number;
  installments_paid_count?: number;
  next_due_date?: string | null;
}

interface Professional {
  id: number;
  first_name: string;
  last_name: string;
  specialty: string | null;
}

interface TreatmentType {
  code: string;
  name: string;
  base_price: number;
}

interface AppointmentBilling {
  id: number | string;
  scheduled_at?: string | null;
  datetime?: string | null;
  professional_name: string | null;
  status: string;
  treatment_name?: string;
  treatment_code?: string;
  base_price?: number;
  billing_amount: number | null;
  payment_status: string | null;
  payment_receipt_data: {
    status?: 'verified' | 'pending' | 'review' | 'rejected';
    amount?: number;
  } | null;
  plan_item_id?: string | null;
}

interface TreatmentGroup {
  treatment_code: string;
  treatment_name: string;
  base_price: number;
  appointments: AppointmentBilling[];
  total_billed: number;
  total_paid: number;
  total_pending: number;
}

interface BillingSummary {
  has_active_plan: boolean;
  patient_email: string | null;
  appointments: AppointmentBilling[];
  treatment_groups: TreatmentGroup[];
  global_total_estimated: number;
  global_total_paid: number;
  global_total_pending: number;
}

interface BillingTabProps {
  patientId: number;
  refreshKey: number;
}

// ─── Lookup maps ────────────────────────────────────────────────────────────

const statusColors: Record<string, { bg: string; text: string }> = {
  draft: { bg: 'bg-white/10', text: 'text-white/60' },
  approved: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
  in_progress: { bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
  completed: { bg: 'bg-green-500/10', text: 'text-green-400' },
  cancelled: { bg: 'bg-red-500/10', text: 'text-red-400' },
};

const itemStatusColors: Record<string, { bg: string; text: string }> = {
  pending: { bg: 'bg-white/10', text: 'text-white/60' },
  in_progress: { bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
  completed: { bg: 'bg-green-500/10', text: 'text-green-400' },
  cancelled: { bg: 'bg-red-500/10', text: 'text-red-400' },
};

const apptStatusColors: Record<string, { bg: string; text: string }> = {
  scheduled: { bg: 'bg-blue-500/10', text: 'text-blue-400' },
  confirmed: { bg: 'bg-green-500/10', text: 'text-green-400' },
  completed: { bg: 'bg-green-500/10', text: 'text-green-400' },
  cancelled: { bg: 'bg-red-500/10', text: 'text-red-400' },
  pending: { bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
};

// ─── Utils ───────────────────────────────────────────────────────────────────

const formatCurrency = (amount: number | null | undefined, cur = 'ARS') =>
  new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: cur || 'ARS',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount || 0);

// ─── Sub-components ──────────────────────────────────────────────────────────

function PaymentReceiptBadge({ receipt }: { receipt: AppointmentBilling['payment_receipt_data'] }) {
  const { t } = useTranslation();
  if (!receipt) return null;

  const status = receipt.status || 'pending';

  if (status === 'verified') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-green-500/10 text-green-400">
        <CheckCircle2 size={10} />
        {t('billing.receipt_verified')}{receipt.amount ? ` (${formatCurrency(receipt.amount)})` : ''}
      </span>
    );
  }
  if (status === 'review') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-orange-500/10 text-orange-400">
        <Search size={10} />
        {t('billing.receipt_review')}
      </span>
    );
  }
  if (status === 'rejected') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-400">
        <X size={10} />
        {t('billing.rejected')}
      </span>
    );
  }
  // pending (default)
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs bg-yellow-500/10 text-yellow-400">
      <Clock size={10} />
      {t('billing.receipt_pending')}
    </span>
  );
}

function TreatmentGroupCard({ group }: { group: TreatmentGroup }) {
  const { t } = useTranslation();

  return (
    <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-white">{group.treatment_name}</h4>
        <span className="text-xs text-white/40">{group.appointments.length} turno{group.appointments.length !== 1 ? 's' : ''}</span>
      </div>

      {/* Appointment rows */}
      <div className="space-y-2 mb-4">
        {group.appointments.map((appt) => {
          const rawDate = appt.scheduled_at || appt.datetime;
          const apptDate = rawDate ? new Date(rawDate) : null;
          const isValidDate = apptDate && !isNaN(apptDate.getTime());
          const statusStyle = apptStatusColors[appt.status] || { bg: 'bg-white/10', text: 'text-white/50' };
          return (
            <div key={appt.id} className="flex flex-wrap items-center gap-2 py-2 border-b border-white/[0.04] last:border-0">
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-white/70">
                    {isValidDate
                      ? apptDate.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })
                      : 'Sin fecha'}
                  </span>
                  {appt.professional_name && (
                    <span className="text-xs text-white/40">{appt.professional_name}</span>
                  )}
                  <span className={`px-2 py-0.5 rounded-full text-[10px] ${statusStyle.bg} ${statusStyle.text}`}>
                    {appt.status}
                  </span>
                </div>
                {appt.payment_receipt_data && (
                  <div className="mt-1">
                    <PaymentReceiptBadge receipt={appt.payment_receipt_data} />
                  </div>
                )}
              </div>
              {appt.billing_amount != null && (
                <span className="text-sm font-medium text-white/80 flex-shrink-0">
                  {formatCurrency(appt.billing_amount)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Group totals */}
      <div className="grid grid-cols-3 gap-2 pt-2 border-t border-white/[0.06]">
        <div>
          <p className="text-[10px] text-white/30 uppercase font-bold mb-0.5">{t('billing.estimated_total')}</p>
          <p className="text-xs text-white font-medium">{formatCurrency(group.total_billed)}</p>
        </div>
        <div>
          <p className="text-[10px] text-white/30 uppercase font-bold mb-0.5">{t('billing.paid')}</p>
          <p className="text-xs text-green-400 font-medium">{formatCurrency(group.total_paid)}</p>
        </div>
        <div>
          <p className="text-[10px] text-white/30 uppercase font-bold mb-0.5">{t('billing.pending')}</p>
          <p className={`text-xs font-medium ${group.total_pending > 0 ? 'text-amber-400' : 'text-green-400'}`}>
            {formatCurrency(group.total_pending)}
          </p>
        </div>
      </div>
    </div>
  );
}

// ─── Main component ──────────────────────────────────────────────────────────

export default function BillingTab({ patientId, refreshKey }: BillingTabProps) {
  const { t } = useTranslation();

  // ── View state
  const [viewState, setViewState] = useState<ViewState>('loading');
  const [billingData, setBillingData] = useState<BillingSummary | null>(null);

  // ── Plan state (plan_view)
  const [plans, setPlans] = useState<TreatmentPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [planDetail, setPlanDetail] = useState<TreatmentPlanDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  // ── UI
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  // ── Modal visibility
  const [showCreatePlan, setShowCreatePlan] = useState(false);
  const [showAddItem, setShowAddItem] = useState(false);
  const [showRegisterPayment, setShowRegisterPayment] = useState(false);
  const [showApprovePlan, setShowApprovePlan] = useState(false);
  const [showEmailModal, setShowEmailModal] = useState(false);
  const [showTreatmentPicker, setShowTreatmentPicker] = useState(false);
  const [selectedTreatmentCodes, setSelectedTreatmentCodes] = useState<string[]>([]);

  // ── Inline edit state (items)
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [editingItemPrice, setEditingItemPrice] = useState<string>('');

  // ── Inline edit state (plan name)
  const [editingPlanName, setEditingPlanName] = useState(false);
  const [planNameDraft, setPlanNameDraft] = useState('');

  // ── Inline edit state (approved total)
  const [editingApprovedTotal, setEditingApprovedTotal] = useState(false);
  const [approvedTotalDraft, setApprovedTotalDraft] = useState('');

  // ── Inline delete confirmations
  const [deletingItemId, setDeletingItemId] = useState<string | null>(null);
  const [deletingPaymentId, setDeletingPaymentId] = useState<string | null>(null);

  // ── Budget config state
  const [budgetConfig, setBudgetConfig] = useState<{
    payment_conditions: string;
    discount_pct: string;
    discount_amount: string;
    installments: string;
    installments_amount: string;
    currency: string;
    financed_total: string;
  }>({ payment_conditions: '', discount_pct: '', discount_amount: '', installments: '', installments_amount: '', currency: 'ARS', financed_total: '' });
  const [savingBudgetConfig, setSavingBudgetConfig] = useState(false);

  // ── Form data
  const [newPlanData, setNewPlanData] = useState({ name: '', professional_id: '', notes: '' });
  const [newItemData, setNewItemData] = useState({ treatment_type_code: '', custom_description: '', estimated_price: '' });
  const [newPaymentData, setNewPaymentData] = useState({ amount: '', payment_method: 'cash', payment_date: new Date().toISOString().split('T')[0], notes: '', installment_id: '' });
  const [approveData, setApproveData] = useState({ approved_total: '' });

  // ── Modal support data
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [treatmentTypes, setTreatmentTypes] = useState<TreatmentType[]>([]);

  // ── PDF/Email
  const [generatingPdf, setGeneratingPdf] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailTo, setEmailTo] = useState('');

  // ── Generate plan loading
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [syncingAppointments, setSyncingAppointments] = useState(false);

  // ── Installments
  const [showGenerateInstallments, setShowGenerateInstallments] = useState(false);
  const [generateInstallmentsData, setGenerateInstallmentsData] = useState({ count: '3', start_date: new Date().toISOString().split('T')[0], frequency: 'monthly' });
  const [generatingInstallments, setGeneratingInstallments] = useState(false);

  // ─── Mount: fetch billing-summary FIRST, then decide state ───────────────

  useEffect(() => {
    setSelectedPlanId(null);
    setPlanDetail(null);
    loadBillingSummary();
  }, [patientId, refreshKey]);

  const loadBillingSummary = async () => {
    try {
      setViewState('loading');
      setError(null);
      const res = await api.get(`/admin/patients/${patientId}/billing-summary`);
      const data: BillingSummary = res.data;
      setBillingData(data);

      if (data.has_active_plan) {
        // Load plans then show plan_view
        await loadPlans();
        // viewState will be set inside loadPlans after data arrives
      } else if (data.appointments && data.appointments.length > 0) {
        setViewState('appointments_only');
      } else {
        setViewState('empty');
      }
    } catch (err) {
      console.error('Error loading billing summary:', err);
      // Fallback: try loading plans directly (backward compat)
      await loadPlans();
    }
  };

  // ─── Load plan list ───────────────────────────────────────────────────────

  const loadPlans = async () => {
    try {
      const res = await api.get(`/admin/patients/${patientId}/treatment-plans`);
      setPlans(res.data);

      if (res.data.length > 0) {
        setViewState('plan_view');
        if (res.data.length === 1 && !selectedPlanId) {
          setSelectedPlanId(res.data[0].id);
        }
      } else {
        setViewState('empty');
      }
    } catch (err) {
      console.error('Error loading plans:', err);
      setError(t('billing.error_load'));
      setViewState('empty');
    }
  };

  // ─── Load plan detail on selection ───────────────────────────────────────

  useEffect(() => {
    if (selectedPlanId) {
      loadPlanDetail(selectedPlanId);
    } else {
      setPlanDetail(null);
    }
  }, [selectedPlanId]);

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  const loadPlanDetail = async (planId: string) => {
    try {
      setLoadingDetail(true);
      const res = await api.get(`/admin/treatment-plans/${planId}`);
      setPlanDetail(res.data);
    } catch (err) {
      console.error('Error loading plan detail:', err);
    } finally {
      setLoadingDetail(false);
    }
  };

  // ─── Parse budget config from plan notes ────────────────────────────────

  useEffect(() => {
    if (planDetail?.notes) {
      try {
        const parsed = JSON.parse(planDetail.notes);
        setBudgetConfig({
          payment_conditions: parsed.payment_conditions || '',
          discount_pct: parsed.discount_pct != null ? String(parsed.discount_pct) : '',
          discount_amount: parsed.discount_amount != null ? String(parsed.discount_amount) : '',
          installments: parsed.installments != null ? String(parsed.installments) : '',
          installments_amount: parsed.installments_amount != null ? String(parsed.installments_amount) : '',
          currency: parsed.currency || 'ARS',
          financed_total: parsed.financed_total != null ? String(parsed.financed_total) : '',
        });
      } catch {
        setBudgetConfig({ payment_conditions: '', discount_pct: '', discount_amount: '', installments: '', installments_amount: '', currency: 'ARS', financed_total: '' });
      }
    } else {
      setBudgetConfig({ payment_conditions: '', discount_pct: '', discount_amount: '', installments: '', installments_amount: '', currency: 'ARS', financed_total: '' });
    }
  }, [planDetail?.notes]);

  // ─── Computed totals (plan_view) ─────────────────────────────────────────

  const estimatedTotal = planDetail?.estimated_total || 0;
  const _baseApproved = planDetail?.approved_total || estimatedTotal;
  const _financedTotal = budgetConfig.financed_total ? parseFloat(budgetConfig.financed_total) : 0;
  const approvedTotal = _financedTotal > 0 ? _financedTotal : _baseApproved;
  const paidTotal = planDetail?.payments?.reduce((sum, p) => sum + p.amount, 0) || 0;
  const pendingTotal = Math.max(approvedTotal - paidTotal, 0);
  const progressPercent = approvedTotal > 0 ? Math.min((paidTotal / approvedTotal) * 100, 100) : 0;

  // ─── Auto-calc installments_amount when installments change ──────────────

  useEffect(() => {
    const numInstallments = parseInt(budgetConfig.installments);
    if (numInstallments > 0 && approvedTotal > 0) {
      const perInstallment = Math.round(approvedTotal / numInstallments);
      setBudgetConfig(prev => ({ ...prev, installments_amount: String(perInstallment) }));
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [budgetConfig.installments, approvedTotal]);

  // ─── Handlers ─────────────────────────────────────────────────────────────

  const handleCreatePlan = async () => {
    if (!newPlanData.name.trim()) return;
    try {
      const payload: Record<string, unknown> = {
        name: newPlanData.name,
        notes: newPlanData.notes || null,
      };
      if (newPlanData.professional_id) {
        payload.professional_id = parseInt(newPlanData.professional_id);
      }
      const res = await api.post(`/admin/patients/${patientId}/treatment-plans`, payload);
      setShowCreatePlan(false);
      setNewPlanData({ name: '', professional_id: '', notes: '' });
      await loadPlans();
      setSelectedPlanId(res.data.id);
      setViewState('plan_view');
    } catch (err) {
      console.error('Error creating plan:', err);
      setError(t('billing.error_save'));
    }
  };

  const handleAddItem = async () => {
    if (!newItemData.treatment_type_code || !planDetail) return;
    try {
      const payload: Record<string, unknown> = {
        treatment_type_code: newItemData.treatment_type_code,
        custom_description: newItemData.custom_description || null,
      };
      if (newItemData.estimated_price) {
        payload.estimated_price = parseFloat(newItemData.estimated_price);
      }
      await api.post(`/admin/treatment-plans/${planDetail.id}/items`, payload);
      setShowAddItem(false);
      setNewItemData({ treatment_type_code: '', custom_description: '', estimated_price: '' });
      await loadPlanDetail(planDetail.id);
    } catch (err) {
      console.error('Error adding item:', err);
      setError(t('billing.error_save'));
    }
  };

  const handleRegisterPayment = async () => {
    if (!newPaymentData.amount || !planDetail) return;
    try {
      const payload: Record<string, unknown> = {
        amount: parseFloat(newPaymentData.amount),
        payment_method: newPaymentData.payment_method,
        payment_date: newPaymentData.payment_date,
        notes: newPaymentData.notes || null,
      };
      if (newPaymentData.installment_id) {
        payload.installment_id = newPaymentData.installment_id;
      }
      await api.post(`/admin/treatment-plans/${planDetail.id}/payments`, payload);
      setShowRegisterPayment(false);
      setNewPaymentData({ amount: '', payment_method: 'cash', payment_date: new Date().toISOString().split('T')[0], notes: '', installment_id: '' });
      await loadPlanDetail(planDetail.id);
    } catch (err: any) {
      console.error('Error registering payment:', err);
      const detail = err?.response?.data?.detail;
      setPaymentError(detail ?? t('billing.error_save'));
    }
  };

  const handleGenerateInstallments = async () => {
    if (!planDetail) return;
    try {
      setGeneratingInstallments(true);
      await api.post(`/admin/treatment-plans/${planDetail.id}/installments/generate`, {
        count: parseInt(generateInstallmentsData.count),
        start_date: generateInstallmentsData.start_date,
        frequency: generateInstallmentsData.frequency,
      });
      setShowGenerateInstallments(false);
      setSuccess(t('installment.generated_success'));
      await loadPlanDetail(planDetail.id);
    } catch (err: unknown) {
      console.error('Error generating installments:', err);
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || t('billing.error_save'));
    } finally {
      setGeneratingInstallments(false);
    }
  };

  const openPaymentModalForInstallment = (installment: TreatmentPlanInstallment) => {
    setNewPaymentData({
      amount: String(installment.amount),
      payment_method: 'cash',
      payment_date: new Date().toISOString().split('T')[0],
      notes: '',
      installment_id: installment.id,
    });
    setPaymentError(null);
    setShowRegisterPayment(true);
  };

  const handleApprovePlan = async () => {
    if (!approveData.approved_total || !planDetail) return;
    try {
      await api.patch(`/admin/treatment-plans/${planDetail.id}`, {
        status: 'approved',
        approved_total: parseFloat(approveData.approved_total),
      });
      setShowApprovePlan(false);
      setApproveData({ approved_total: '' });
      await loadPlanDetail(planDetail.id);
    } catch (err) {
      console.error('Error approving plan:', err);
      setError(t('billing.error_save'));
    }
  };

  const handleUpdatePlanName = async () => {
    if (!planNameDraft.trim() || !planDetail) return;
    try {
      await api.patch(`/admin/treatment-plans/${planDetail.id}`, { name: planNameDraft });
      setEditingPlanName(false);
      await loadPlanDetail(planDetail.id);
    } catch (err) {
      console.error('Error updating plan name:', err);
      setError(t('billing.error_save'));
    }
  };

  const handleUpdateApprovedTotal = async () => {
    if (!approvedTotalDraft || !planDetail) return;
    try {
      await api.patch(`/admin/treatment-plans/${planDetail.id}`, {
        approved_total: parseFloat(approvedTotalDraft),
      });
      setEditingApprovedTotal(false);
      await loadPlanDetail(planDetail.id);
    } catch (err) {
      console.error('Error updating approved total:', err);
      setError(t('billing.error_save'));
    }
  };

  const handleUpdateItemPrice = async (itemId: string) => {
    if (!editingItemPrice || !planDetail) return;
    try {
      await api.put(`/admin/treatment-plan-items/${itemId}`, {
        approved_price: parseFloat(editingItemPrice),
      });
      setEditingItemId(null);
      setEditingItemPrice('');
      await loadPlanDetail(planDetail.id);
    } catch (err) {
      console.error('Error updating item price:', err);
      setError(t('billing.error_save'));
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    if (!planDetail) return;
    try {
      await api.delete(`/admin/treatment-plan-items/${itemId}`);
      setDeletingItemId(null);
      await loadPlanDetail(planDetail.id);
    } catch (err) {
      console.error('Error deleting item:', err);
      setError(t('billing.error_save'));
    }
  };

  const handleDeletePayment = async (paymentId: string) => {
    if (!planDetail) return;
    try {
      await api.delete(`/admin/treatment-plan-payments/${paymentId}`);
      setDeletingPaymentId(null);
      await loadPlanDetail(planDetail.id);
    } catch (err) {
      console.error('Error deleting payment:', err);
      setError(t('billing.error_save'));
    }
  };

  const openAddItemModal = async () => {
    if (treatmentTypes.length === 0) {
      try {
        const res = await api.get('/admin/treatment-types');
        setTreatmentTypes(res.data);
      } catch (err) {
        console.error('Error loading treatment types:', err);
      }
    }
    setShowAddItem(true);
  };

  const openCreatePlanModal = async () => {
    if (professionals.length === 0) {
      try {
        const res = await api.get('/admin/professionals');
        setProfessionals(res.data);
      } catch (err) {
        console.error('Error loading professionals:', err);
      }
    }
    setShowCreatePlan(true);
  };

  const openTreatmentPicker = () => {
    // Get unlinked treatments from billing data
    const unlinked = (billingData?.appointments || []).filter((a: AppointmentBilling) => !a.plan_item_id);
    const codes = [...new Set(unlinked.map((a: AppointmentBilling) => a.treatment_code || 'sin_tipo'))];
    setSelectedTreatmentCodes(codes as string[]); // all selected by default
    setShowTreatmentPicker(true);
  };

  const handleGeneratePlanFromAppointments = async (treatmentCodes?: string[]) => {
    try {
      setGeneratingPlan(true);
      setError(null);
      setShowTreatmentPicker(false);
      const payload: Record<string, unknown> = {};
      if (treatmentCodes && treatmentCodes.length > 0) {
        payload.treatment_codes = treatmentCodes;
      }
      await api.post(`/admin/patients/${patientId}/generate-plan-from-appointments`, payload);
      await loadBillingSummary();
    } catch (err: unknown) {
      console.error('Error generating plan:', err);
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || t('billing.error_save'));
    } finally {
      setGeneratingPlan(false);
    }
  };

  const handleSyncAppointments = async () => {
    if (!planDetail) return;
    try {
      setSyncingAppointments(true);
      setError(null);
      const res = await api.post(`/admin/treatment-plans/${planDetail.id}/sync-appointments`);
      if (res.data.status === 'no_changes') {
        setError(t('billing.sync_no_changes') || 'Todos los turnos ya están vinculados');
      }
      await loadPlanDetail(planDetail.id);
      await loadBillingSummary();
    } catch (err: unknown) {
      console.error('Error syncing appointments:', err);
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || t('billing.error_save'));
    } finally {
      setSyncingAppointments(false);
    }
  };

  const handleGeneratePdf = async () => {
    if (!planDetail) return;
    try {
      setGeneratingPdf(true);
      const res = await api.post(
        `/admin/treatment-plans/${planDetail.id}/generate-pdf`,
        {},
        { responseType: 'blob' }
      );
      const url = URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `presupuesto-${planDetail.name.replace(/\s+/g, '-')}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error generating PDF:', err);
      setError(t('billing.error_save'));
    } finally {
      setGeneratingPdf(false);
    }
  };

  const handleSendEmail = async () => {
    if (!planDetail || !emailTo.trim()) return;
    try {
      setSendingEmail(true);
      await api.post(`/admin/treatment-plans/${planDetail.id}/send-email`, { email: emailTo });
      setShowEmailModal(false);
      setSuccess(t('billing.email_sent_success'));
    } catch (err: any) {
      console.error('Error sending email:', err);
      const detail = err?.response?.data?.detail || t('billing.error_save');
      setError(detail);
    } finally {
      setSendingEmail(false);
    }
  };

  const openEmailModal = () => {
    setEmailTo(billingData?.patient_email || '');
    setShowEmailModal(true);
  };

  const handleSaveBudgetConfig = async () => {
    if (!planDetail) return;
    try {
      setSavingBudgetConfig(true);
      await api.patch(`/admin/treatment-plans/${planDetail.id}`, {
        payment_conditions: budgetConfig.payment_conditions || null,
        discount_pct: budgetConfig.discount_pct ? parseFloat(budgetConfig.discount_pct) : 0,
        discount_amount: budgetConfig.discount_amount ? parseFloat(budgetConfig.discount_amount) : 0,
        installments: budgetConfig.installments ? parseInt(budgetConfig.installments) : null,
        installments_amount: budgetConfig.installments_amount ? parseFloat(budgetConfig.installments_amount) : null,
        currency: budgetConfig.currency || 'ARS',
        financed_total: budgetConfig.financed_total ? parseFloat(budgetConfig.financed_total) : null,
      });
      await loadPlanDetail(planDetail.id);
      setSuccess(t('billing.config_saved'));
    } catch (err: any) {
      console.error('Error saving budget config:', err);
      const detail = err?.response?.data?.detail || t('billing.error_save');
      setError(detail);
    } finally {
      setSavingBudgetConfig(false);
    }
  };

  // ─── Render: loading ──────────────────────────────────────────────────────

  if (viewState === 'loading') {
    return (
      <div className="space-y-4">
        <div className="h-12 bg-white/[0.04] rounded animate-pulse" />
        <div className="h-48 bg-white/[0.04] rounded animate-pulse" />
        <div className="h-64 bg-white/[0.04] rounded animate-pulse" />
      </div>
    );
  }

  // ─── Render: empty (no appointments, no plan) ─────────────────────────────

  if (viewState === 'empty') {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Receipt size={48} className="text-white/20 mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">{t('billing.no_activity')}</h3>
        <p className="text-sm text-white/40 mb-6 max-w-xs">{t('billing.no_activity_desc')}</p>
        <button
          onClick={openCreatePlanModal}
          className="flex items-center gap-2 bg-white text-[#0a0e1a] px-4 py-2 rounded-lg hover:opacity-90 transition-opacity font-medium"
        >
          <Plus size={18} />
          {t('billing.create_first')}
        </button>

        {error && (
          <div className="mt-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg p-3 text-sm flex items-center gap-2 w-full max-w-sm">
            <AlertCircle size={16} />
            {error}
            <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">
              <X size={16} />
            </button>
          </div>
        )}

        {showCreatePlan && <CreatePlanModal
          newPlanData={newPlanData}
          setNewPlanData={setNewPlanData}
          professionals={professionals}
          onCreate={handleCreatePlan}
          onClose={() => setShowCreatePlan(false)}
          t={t}
        />}
      </div>
    );
  }

  // ─── Render: appointments_only ────────────────────────────────────────────

  if (viewState === 'appointments_only' && billingData) {
    const groups = billingData.treatment_groups || [];

    return (
      <div className="space-y-6">
        {/* Error banner */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg p-3 text-sm flex items-center gap-2">
            <AlertCircle size={16} />
            {error}
            <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">
              <X size={16} />
            </button>
          </div>
        )}

        {/* Section title */}
        <h3 className="text-sm font-semibold text-white/60 uppercase tracking-wider">
          {t('billing.appointments_summary')}
        </h3>

        {/* Treatment group cards */}
        {groups.length > 0 ? (
          <div className="space-y-4">
            {groups.map((group) => (
              <TreatmentGroupCard key={group.treatment_code} group={group} />
            ))}
          </div>
        ) : (
          /* Flat list fallback when no treatment groups */
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4 space-y-2">
            {billingData.appointments.map((appt) => {
              const rawDate = appt.scheduled_at || (appt as any).datetime;
              const apptDate = rawDate ? new Date(rawDate) : null;
              const isValidDate = apptDate && !isNaN(apptDate.getTime());
              const statusStyle = apptStatusColors[appt.status] || { bg: 'bg-white/10', text: 'text-white/50' };
              return (
                <div key={appt.id} className="flex flex-wrap items-center gap-2 py-2 border-b border-white/[0.04] last:border-0">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-xs text-white/70">
                        {isValidDate
                          ? apptDate.toLocaleDateString('es-AR', { day: '2-digit', month: 'short', year: 'numeric' })
                          : 'Sin fecha'}
                      </span>
                      {appt.professional_name && (
                        <span className="text-xs text-white/40">{appt.professional_name}</span>
                      )}
                      <span className={`px-2 py-0.5 rounded-full text-[10px] ${statusStyle.bg} ${statusStyle.text}`}>
                        {appt.status}
                      </span>
                    </div>
                    {appt.payment_receipt_data && (
                      <div className="mt-1">
                        <PaymentReceiptBadge receipt={appt.payment_receipt_data} />
                      </div>
                    )}
                  </div>
                  {appt.billing_amount != null && (
                    <span className="text-sm font-medium text-white/80">
                      {formatCurrency(appt.billing_amount)}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* Global totals */}
        <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-[10px] text-white/40 uppercase font-bold mb-1">{t('billing.total_estimated')}</p>
              <p className="text-base font-bold text-white">{formatCurrency(billingData.global_total_estimated)}</p>
            </div>
            <div>
              <p className="text-[10px] text-white/40 uppercase font-bold mb-1">{t('billing.paid')}</p>
              <p className="text-base font-bold text-green-400">{formatCurrency(billingData.global_total_paid)}</p>
              {billingData.global_total_estimated > 0 && (
                <p className="text-[10px] text-white/30">
                  ({Math.round((billingData.global_total_paid / billingData.global_total_estimated) * 100)}%)
                </p>
              )}
            </div>
            <div>
              <p className="text-[10px] text-white/40 uppercase font-bold mb-1">{t('billing.pending')}</p>
              <p className={`text-base font-bold ${billingData.global_total_pending > 0 ? 'text-amber-400' : 'text-green-400'}`}>
                {formatCurrency(billingData.global_total_pending)}
              </p>
            </div>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={openTreatmentPicker}
            disabled={generatingPlan}
            className="flex-1 flex items-center justify-center gap-2 bg-white text-[#0a0e1a] px-5 py-3 rounded-xl hover:opacity-90 transition-opacity font-semibold text-sm disabled:opacity-50"
          >
            {generatingPlan ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Sparkles size={18} />
            )}
            {t('billing.generate_from_appointments')}
          </button>

          <button
            onClick={openCreatePlanModal}
            className="sm:flex-none flex items-center justify-center gap-2 bg-white/[0.06] text-white/70 border border-white/[0.08] px-4 py-3 rounded-xl hover:bg-white/[0.1] transition-colors text-sm"
          >
            <Plus size={16} />
            {t('billing.create_empty')}
          </button>
        </div>

        {showCreatePlan && <CreatePlanModal
          newPlanData={newPlanData}
          setNewPlanData={setNewPlanData}
          professionals={professionals}
          onCreate={handleCreatePlan}
          onClose={() => setShowCreatePlan(false)}
          t={t}
        />}
      </div>
    );
  }

  // ─── Render: plan_view ────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Error banner */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg p-3 text-sm flex items-center gap-2">
          <AlertCircle size={16} />
          {error}
          <button onClick={() => setError(null)} className="ml-auto text-red-400 hover:text-red-300">
            <X size={16} />
          </button>
        </div>
      )}
      {success && (
        <div className="bg-green-500/10 border border-green-500/20 text-green-400 rounded-lg p-3 text-sm flex items-center gap-2">
          <CheckCircle2 size={16} />
          {success}
          <button onClick={() => setSuccess(null)} className="ml-auto text-green-400 hover:text-green-300">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Plan Selector Bar */}
      <div className="flex flex-wrap items-center gap-3">
        {plans.length > 1 && (
          <select
            value={selectedPlanId || ''}
            onChange={(e) => setSelectedPlanId(e.target.value)}
            className="flex-1 px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary"
          >
            {plans.map((plan) => (
              <option key={plan.id} value={plan.id}>
                {plan.name} — {t(`billing.status.${plan.status}`)}
              </option>
            ))}
          </select>
        )}
        <button
          onClick={openCreatePlanModal}
          className="flex items-center gap-2 bg-white/[0.06] text-white border border-white/[0.08] px-4 py-2 rounded-lg hover:bg-white/[0.1] transition-colors"
        >
          <Plus size={18} />
          {t('billing.new_plan')}
        </button>
        {billingData?.appointments?.some((a: AppointmentBilling) => !a.plan_item_id) && (
          <button
            onClick={openTreatmentPicker}
            disabled={generatingPlan}
            className="flex items-center gap-2 bg-blue-500/10 text-blue-400 border border-blue-500/20 px-4 py-2 rounded-lg hover:bg-blue-500/20 transition-colors disabled:opacity-50 text-sm"
          >
            {generatingPlan ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
            {t('billing.generate_unlinked') || 'Presupuestar turnos sin asignar'}
          </button>
        )}
      </div>

      {/* Plan Detail */}
      {planDetail && (
        <>
          {/* Plan Header Card */}
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
            {/* Name & Status */}
            <div className="flex items-center justify-between mb-4">
              {editingPlanName ? (
                <div className="flex items-center gap-2 flex-1">
                  <input
                    type="text"
                    value={planNameDraft}
                    onChange={(e) => setPlanNameDraft(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleUpdatePlanName()}
                    onBlur={handleUpdatePlanName}
                    className="flex-1 px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-white text-lg font-semibold"
                    autoFocus
                  />
                  <button onClick={handleUpdatePlanName} className="text-green-400">
                    <Check size={18} />
                  </button>
                </div>
              ) : (
                <h3
                  className="text-lg font-semibold text-white cursor-pointer hover:text-primary"
                  onClick={() => { setPlanNameDraft(planDetail.name); setEditingPlanName(true); }}
                >
                  {planDetail.name}
                </h3>
              )}
              <span className={`px-3 py-1 rounded-full text-xs font-medium ${statusColors[planDetail.status]?.bg} ${statusColors[planDetail.status]?.text}`}>
                {t(`billing.status.${planDetail.status}`)}
              </span>
            </div>

            {/* Professional */}
            {planDetail.professional_name && (
              <div className="flex items-center gap-2 text-white/60 text-sm mb-4">
                <User size={14} />
                {planDetail.professional_name}
              </div>
            )}

            {/* PDF + Email buttons */}
            <div className="flex flex-wrap gap-2 mb-4">
              <button
                onClick={handleGeneratePdf}
                disabled={generatingPdf}
                className="flex items-center gap-2 bg-white/[0.06] text-white/70 border border-white/[0.08] px-3 py-1.5 rounded-lg text-sm hover:bg-white/[0.1] transition-colors disabled:opacity-50"
              >
                {generatingPdf ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Download size={14} />
                )}
                {generatingPdf ? t('billing.generating_pdf') : t('billing.generate_pdf')}
              </button>

              <button
                onClick={openEmailModal}
                className="flex items-center gap-2 bg-white/[0.06] text-white/70 border border-white/[0.08] px-3 py-1.5 rounded-lg text-sm hover:bg-white/[0.1] transition-colors"
              >
                <Mail size={14} />
                {t('billing.send_email')}
              </button>

              <button
                onClick={handleSyncAppointments}
                disabled={syncingAppointments}
                className="flex items-center gap-2 bg-blue-500/10 text-blue-400 border border-blue-500/20 px-3 py-1.5 rounded-lg text-sm hover:bg-blue-500/20 transition-colors disabled:opacity-50"
              >
                {syncingAppointments ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <RefreshCw size={14} />
                )}
                {t('billing.sync_appointments') || 'Sincronizar turnos'}
              </button>
            </div>

            {/* Approve Button */}
            {planDetail.status === 'draft' && (
              <button
                onClick={() => { setApproveData({ approved_total: String(planDetail.estimated_total) }); setShowApprovePlan(true); }}
                className="mb-4 bg-blue-500/10 text-blue-400 border border-blue-500/20 px-4 py-2 rounded-lg text-sm hover:bg-blue-500/20 transition-colors"
              >
                {t('billing.approve_plan')}
              </button>
            )}

            {/* KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-3">
                <p className="text-[10px] text-white/40 uppercase font-bold">{t('billing.estimated_total')}</p>
                <p className="text-base font-bold text-white">{formatCurrency(estimatedTotal)}</p>
              </div>
              <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-3">
                <span className="text-[10px] font-bold text-white/40 uppercase flex items-center gap-1 mb-0.5">
                  {t('billing.approved_total')}
                  <Edit2 size={10} className="text-white/20" />
                </span>
                {editingApprovedTotal ? (
                  <input
                    type="number"
                    value={approvedTotalDraft}
                    onChange={(e) => setApprovedTotalDraft(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleUpdateApprovedTotal();
                      if (e.key === 'Escape') setEditingApprovedTotal(false);
                    }}
                    onBlur={handleUpdateApprovedTotal}
                    className="w-full px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-white text-base font-bold focus:outline-none focus:ring-1 focus:ring-primary"
                    autoFocus
                  />
                ) : (
                  <p
                    onClick={() => {
                      setEditingApprovedTotal(true);
                      setApprovedTotalDraft(String(planDetail.approved_total || planDetail.estimated_total || ''));
                    }}
                    className="text-base font-bold text-white cursor-pointer hover:text-primary transition-colors"
                    title={t('billing.click_to_edit') || 'Click para editar'}
                  >
                    {approvedTotal > 0 ? formatCurrency(approvedTotal) : t('billing.no_approved_total')}
                  </p>
                )}
              </div>
              <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-3">
                <p className="text-[10px] text-white/40 uppercase font-bold">{t('billing.paid')}</p>
                <p className="text-base font-bold text-green-400">{formatCurrency(paidTotal)}</p>
              </div>
              <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-3">
                <p className="text-[10px] text-white/40 uppercase font-bold">{t('billing.pending')}</p>
                <p className={`text-base font-bold ${pendingTotal > 0 ? 'text-amber-400' : 'text-green-400'}`}>
                  {pendingTotal > 0 ? formatCurrency(pendingTotal) : t('billing.paid_complete')}
                </p>
              </div>
            </div>
          </div>

          {/* Progress Bar */}
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
            <div className="flex justify-between text-sm text-white/60 mb-2">
              <span>{formatCurrency(paidTotal)} / {formatCurrency(approvedTotal)} ({Math.round(progressPercent)}%)</span>
              {paidTotal >= approvedTotal && approvedTotal > 0 && (
                <span className="text-green-400 font-medium">{t('billing.paid_complete')}</span>
              )}
            </div>
            <div className="bg-white/[0.06] rounded-full h-2">
              <div
                className="bg-green-500 rounded-full h-2 transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>

          {/* Items Section */}
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
            <div className="flex justify-between items-center mb-4">
              <h4 className="text-sm font-semibold text-white">{t('billing.treatments')}</h4>
              <button
                onClick={openAddItemModal}
                className="flex items-center gap-1 text-primary text-sm hover:text-primary-dark"
              >
                <Plus size={16} />
                {t('billing.add_treatment')}
              </button>
            </div>

            {loadingDetail ? (
              <div className="h-32 bg-white/[0.04] rounded animate-pulse" />
            ) : planDetail.items.length === 0 ? (
              <p className="text-white/40 text-center py-4">{t('billing.no_items')}</p>
            ) : (
              <>
                {/* Desktop table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-[10px] font-bold text-white/40 uppercase border-b border-white/[0.04]">
                        <th className="text-left py-3 px-2">{t('billing.treatment')}</th>
                        <th className="text-right py-3 px-2">{t('billing.estimated_price')}</th>
                        <th className="text-right py-3 px-2">{t('billing.approved_price')}</th>
                        <th className="text-center py-3 px-2">{t('billing.appointments_count')}</th>
                        <th className="text-center py-3 px-2">{t('billing.status_item')}</th>
                        <th className="w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {planDetail.items.map((item) => (
                        <tr key={item.id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                          <td className="py-3 px-2 text-sm text-white">
                            {item.custom_description || item.treatment_type_name || item.treatment_type_code}
                          </td>
                          <td className="py-3 px-2 text-sm text-white/60 text-right">
                            {formatCurrency(item.estimated_price)}
                          </td>
                          <td className="py-3 px-2 text-right">
                            {editingItemId === item.id ? (
                              <div className="flex items-center gap-1.5">
                                <input
                                  type="number"
                                  value={editingItemPrice}
                                  onChange={(e) => setEditingItemPrice(e.target.value)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') handleUpdateItemPrice(item.id);
                                    if (e.key === 'Escape') { setEditingItemId(null); setEditingItemPrice(''); }
                                  }}
                                  className="w-24 px-2 py-1 bg-white/[0.06] border border-blue-500/50 rounded text-white text-sm focus:border-blue-400 focus:ring-1 focus:ring-blue-400/30 outline-none"
                                  autoFocus
                                />
                                <button onClick={() => handleUpdateItemPrice(item.id)} className="p-1 rounded bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-colors" title={t('billing.confirm')}>
                                  <Check size={14} />
                                </button>
                                <button onClick={() => { setEditingItemId(null); setEditingItemPrice(''); }} className="p-1 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors" title={t('billing.cancel')}>
                                  <X size={14} />
                                </button>
                              </div>
                            ) : (
                              <span
                                className="text-sm text-white cursor-pointer hover:text-blue-400 transition-colors border-b border-dashed border-white/20 hover:border-blue-400/50 pb-0.5"
                                onClick={() => { setEditingItemId(item.id); setEditingItemPrice(String(item.approved_price || item.estimated_price)); }}
                              >
                                {formatCurrency(item.approved_price || item.estimated_price)}
                              </span>
                            )}
                          </td>
                          <td className="py-3 px-2 text-sm text-white/60 text-center">
                            {item.appointments_count || 0}
                          </td>
                          <td className="py-3 px-2 text-center">
                            <span className={`px-2 py-0.5 rounded-full text-xs ${itemStatusColors[item.status]?.bg} ${itemStatusColors[item.status]?.text}`}>
                              {t(`billing.item_status.${item.status}`)}
                            </span>
                          </td>
                          <td className="py-3 px-2">
                            {deletingItemId === item.id ? (
                              <div className="flex items-center gap-1">
                                <button
                                  onClick={() => handleDeleteItem(item.id)}
                                  className="text-red-400 text-xs hover:underline"
                                >
                                  {t('billing.delete_item_confirm')}
                                </button>
                                <button onClick={() => setDeletingItemId(null)} className="text-white/40">
                                  <X size={14} />
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setDeletingItemId(item.id)}
                                className="text-white/40 hover:text-red-400"
                              >
                                <Trash2 size={16} />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile cards */}
                <div className="md:hidden space-y-3">
                  {planDetail.items.map((item) => (
                    <div key={item.id} className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-3">
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex-1 min-w-0">
                          <p className="text-white text-sm font-medium truncate">
                            {item.custom_description || item.treatment_type_name || item.treatment_type_code}
                          </p>
                          <span className={`inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full ${itemStatusColors[item.status]?.bg} ${itemStatusColors[item.status]?.text}`}>
                            {t(`billing.item_status.${item.status}`)}
                          </span>
                        </div>
                        <div className="ml-2 flex-shrink-0">
                          {deletingItemId === item.id ? (
                            <div className="flex items-center gap-1">
                              <button
                                onClick={() => handleDeleteItem(item.id)}
                                className="text-red-400 text-xs hover:underline"
                              >
                                {t('billing.delete_item_confirm')}
                              </button>
                              <button onClick={() => setDeletingItemId(null)} className="text-white/40">
                                <X size={14} />
                              </button>
                            </div>
                          ) : (
                            <button
                              onClick={() => setDeletingItemId(item.id)}
                              className="text-white/40 hover:text-red-400"
                            >
                              <Trash2 size={16} />
                            </button>
                          )}
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div>
                          <span className="text-white/30">{t('billing.estimated_price')}</span>
                          <p className="text-white/50">{formatCurrency(item.estimated_price)}</p>
                        </div>
                        <div>
                          <span className="text-white/30">{t('billing.approved_price')}</span>
                          {editingItemId === item.id ? (
                            <div className="flex items-center gap-1 mt-0.5">
                              <input
                                type="number"
                                value={editingItemPrice}
                                onChange={(e) => setEditingItemPrice(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') handleUpdateItemPrice(item.id);
                                  if (e.key === 'Escape') { setEditingItemId(null); setEditingItemPrice(''); }
                                }}
                                className="w-20 px-2 py-0.5 bg-white/[0.06] border border-blue-500/50 rounded text-white text-xs focus:border-blue-400 focus:ring-1 focus:ring-blue-400/30 outline-none"
                                autoFocus
                              />
                              <button onClick={() => handleUpdateItemPrice(item.id)} className="p-0.5 rounded bg-green-500/20 text-green-400 hover:bg-green-500/30 transition-colors">
                                <Check size={12} />
                              </button>
                              <button onClick={() => { setEditingItemId(null); setEditingItemPrice(''); }} className="p-0.5 rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors">
                                <X size={12} />
                              </button>
                            </div>
                          ) : (
                            <p
                              className="text-white cursor-pointer hover:text-blue-400 transition-colors border-b border-dashed border-white/20 hover:border-blue-400/50 pb-0.5 inline-block"
                              onClick={() => { setEditingItemId(item.id); setEditingItemPrice(String(item.approved_price || item.estimated_price)); }}
                            >
                              {item.approved_price ? formatCurrency(item.approved_price) : '-'}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Budget Configuration Section */}
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
            <h4 className="text-sm font-semibold text-white mb-4">{t('billing.budget_config')}</h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs text-white/40 mb-1">{t('billing.currency') || 'Moneda'}</label>
                <select
                  value={budgetConfig.currency}
                  onChange={(e) => setBudgetConfig({ ...budgetConfig, currency: e.target.value })}
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-primary appearance-none cursor-pointer"
                >
                  <option value="ARS">$ ARS — Peso Argentino</option>
                  <option value="USD">USD — Dólar</option>
                  <option value="PYG">₲ PYG — Guaraní</option>
                  <option value="EUR">€ EUR — Euro</option>
                  <option value="BRL">R$ BRL — Real</option>
                  <option value="CLP">$ CLP — Peso Chileno</option>
                  <option value="UYU">$U UYU — Peso Uruguayo</option>
                  <option value="MXN">MX$ MXN — Peso Mexicano</option>
                </select>
              </div>
              <div className="sm:col-span-1 lg:col-span-2">
                <label className="block text-xs text-white/40 mb-1">{t('billing.payment_conditions')}</label>
                <input
                  type="text"
                  value={budgetConfig.payment_conditions}
                  onChange={(e) => setBudgetConfig({ ...budgetConfig, payment_conditions: e.target.value })}
                  placeholder="Ej: Válido por 30 días"
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-xs text-white/40 mb-1">{t('billing.discount_pct')}</label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.5"
                  value={budgetConfig.discount_pct}
                  onChange={(e) => setBudgetConfig({ ...budgetConfig, discount_pct: e.target.value })}
                  placeholder="0"
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-xs text-white/40 mb-1">{t('billing.discount_amount')}</label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={budgetConfig.discount_amount}
                  onChange={(e) => setBudgetConfig({ ...budgetConfig, discount_amount: e.target.value })}
                  placeholder="0"
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-xs text-white/40 mb-1">{t('billing.installments')}</label>
                <input
                  type="number"
                  min="1"
                  max="48"
                  value={budgetConfig.installments}
                  onChange={(e) => setBudgetConfig({ ...budgetConfig, installments: e.target.value })}
                  placeholder="1"
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-xs text-white/40 mb-1">{t('billing.financed_total') || 'Total financiado'}</label>
                <input
                  type="number"
                  min="0"
                  step="100"
                  value={budgetConfig.financed_total}
                  onChange={(e) => setBudgetConfig({ ...budgetConfig, financed_total: e.target.value })}
                  placeholder="Si hay recargo por cuotas"
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div>
                <label className="block text-xs text-white/40 mb-1">{t('billing.installments_amount')}</label>
                <div className="px-3 py-2 bg-white/[0.02] border border-white/[0.06] rounded-lg text-white/60 text-sm">
                  {budgetConfig.installments_amount ? formatCurrency(parseFloat(budgetConfig.installments_amount)) : '—'}
                </div>
              </div>
            </div>
            <div className="mt-4 flex justify-end">
              <button
                onClick={handleSaveBudgetConfig}
                disabled={savingBudgetConfig}
                className="flex items-center gap-2 bg-primary hover:bg-primary/80 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
              >
                {savingBudgetConfig ? (
                  <Loader2 size={14} className="animate-spin" />
                ) : (
                  <Check size={14} />
                )}
                {t('billing.save_config')}
              </button>
            </div>
          </div>

          {/* Payments Section */}
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
            <div className="flex justify-between items-center mb-4">
              <h4 className="text-sm font-semibold text-white">{t('billing.payments')}</h4>
              <button
                onClick={() => { setPaymentError(null); setNewPaymentData({ ...newPaymentData, amount: String(pendingTotal), installment_id: '' }); setShowRegisterPayment(true); }}
                disabled={planDetail.status !== 'approved' && planDetail.status !== 'in_progress'}
                className="flex items-center gap-1 text-primary text-sm hover:text-primary-dark disabled:opacity-50"
              >
                <Plus size={16} />
                {t('billing.register_payment')}
              </button>
            </div>

            {planDetail.payments.length === 0 ? (
              <p className="text-white/40 text-center py-4">{t('billing.no_payments')}</p>
            ) : (
              <>
                {/* Desktop table */}
                <div className="hidden md:block overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-[10px] font-bold text-white/40 uppercase border-b border-white/[0.04]">
                        <th className="text-left py-3 px-2">{t('billing.date')}</th>
                        <th className="text-right py-3 px-2">{t('billing.amount')}</th>
                        <th className="text-left py-3 px-2">{t('billing.method_label')}</th>
                        <th className="text-left py-3 px-2">{t('billing.recorded_by')}</th>
                        <th className="text-left py-3 px-2">{t('billing.receipt')}</th>
                        <th className="text-left py-3 px-2">{t('billing.notes')}</th>
                        <th className="w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {planDetail.payments.map((payment) => (
                        <tr key={payment.id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                          <td className="py-3 px-2 text-sm text-white">
                            {payment.payment_date ? new Date(payment.payment_date).toLocaleDateString('es-AR') : '—'}
                          </td>
                          <td className="py-3 px-2 text-sm text-white text-right font-medium">
                            {formatCurrency(payment.amount)}
                          </td>
                          <td className="py-3 px-2">
                            <div className="flex items-center gap-1 text-sm text-white">
                              {payment.payment_method === 'cash' && <Banknote size={14} />}
                              {payment.payment_method === 'transfer' && <ArrowRightLeft size={14} />}
                              {payment.payment_method === 'card' && <CreditCard size={14} />}
                              {t(`billing.method.${payment.payment_method}`)}
                            </div>
                          </td>
                          <td className="py-3 px-2 text-sm text-white/60">
                            {payment.recorded_by || payment.recorded_by_name || '-'}
                          </td>
                          <td className="py-3 px-2">
                            {payment.payment_receipt_data ? (
                              <PaymentReceiptBadge receipt={payment.payment_receipt_data} />
                            ) : (
                              <span className="text-white/30 text-xs">—</span>
                            )}
                          </td>
                          <td className="px-3 py-2 text-white/50 text-xs max-w-[120px] truncate" title={payment.notes || ''}>
                            {payment.notes || '-'}
                          </td>
                          <td className="py-3 px-2">
                            {deletingPaymentId === payment.id ? (
                              <div className="flex items-center gap-1">
                                <button
                                  onClick={() => handleDeletePayment(payment.id)}
                                  className="text-red-400 text-xs hover:underline"
                                >
                                  {t('billing.delete_payment_confirm')}
                                </button>
                                <button onClick={() => setDeletingPaymentId(null)} className="text-white/40">
                                  <X size={14} />
                                </button>
                              </div>
                            ) : (
                              <button
                                onClick={() => setDeletingPaymentId(payment.id)}
                                className="text-white/40 hover:text-red-400"
                              >
                                <Trash2 size={16} />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile payment cards */}
                <div className="md:hidden space-y-2">
                  {planDetail.payments.map((payment) => (
                    <div key={payment.id} className="bg-white/[0.02] border border-white/[0.06] rounded-lg p-3 flex justify-between items-center">
                      <div className="flex-1 min-w-0">
                        <p className="text-white text-sm font-medium">{formatCurrency(payment.amount)}</p>
                        <p className="text-white/40 text-xs">
                          {payment.payment_date ? new Date(payment.payment_date).toLocaleDateString('es-AR') : '—'} — {t(`billing.method.${payment.payment_method}`)}
                        </p>
                        {payment.payment_receipt_data && (
                          <div className="mt-1">
                            <PaymentReceiptBadge receipt={payment.payment_receipt_data} />
                          </div>
                        )}
                        {payment.notes && <p className="text-white/30 text-xs truncate mt-1">{payment.notes}</p>}
                      </div>
                      <div className="ml-2 flex-shrink-0">
                        {deletingPaymentId === payment.id ? (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handleDeletePayment(payment.id)}
                              className="text-red-400 text-xs hover:underline"
                            >
                              {t('billing.delete_payment_confirm')}
                            </button>
                            <button onClick={() => setDeletingPaymentId(null)} className="text-white/40">
                              <X size={14} />
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setDeletingPaymentId(payment.id)}
                            className="text-white/40 hover:text-red-400"
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
          {/* Installments Section */}
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
            <div className="flex justify-between items-center mb-4">
              <h4 className="text-sm font-semibold text-white">{t('installment.title')}</h4>
              {(!planDetail.installments || planDetail.installments.length === 0) &&
                (planDetail.status === 'approved' || planDetail.status === 'in_progress') && (
                <button
                  onClick={() => setShowGenerateInstallments(true)}
                  disabled={planDetail.status === 'cancelled'}
                  className="flex items-center gap-1 text-primary text-sm hover:text-primary-dark disabled:opacity-50"
                >
                  <Plus size={16} />
                  {t('installment.generate')}
                </button>
              )}
            </div>

            {!planDetail.installments || planDetail.installments.length === 0 ? (
              <p className="text-white/40 text-center py-4">{t('installment.no_installments')}</p>
            ) : (
              <div className="space-y-2">
                {planDetail.installments.map((inst) => {
                  const dueDate = new Date(inst.due_date);
                  const dueDateStr = isNaN(dueDate.getTime())
                    ? inst.due_date
                    : dueDate.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });

                  const badgeClass =
                    inst.status === 'paid'
                      ? 'bg-green-500/10 text-green-400'
                      : inst.status === 'overdue'
                      ? 'bg-red-500/10 text-red-400'
                      : 'bg-amber-500/10 text-amber-400';

                  const statusLabel =
                    inst.status === 'paid'
                      ? t('installment.paid')
                      : inst.status === 'overdue'
                      ? t('installment.overdue')
                      : t('installment.pending');

                  return (
                    <div
                      key={inst.id}
                      className="flex flex-wrap items-center gap-3 py-2.5 px-3 bg-white/[0.02] border border-white/[0.06] rounded-lg"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-white font-medium">
                          {t('installment.cuota')} {inst.installment_number} {t('installment.of')} {planDetail.installments_count ?? planDetail.installments!.length}
                        </p>
                        <div className="flex items-center gap-1 mt-0.5 text-xs text-white/50">
                          <Calendar size={11} />
                          {t('installment.due_date')}: {dueDateStr}
                        </div>
                      </div>
                      <span className="text-sm font-semibold text-white">{formatCurrency(inst.amount)}</span>
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badgeClass}`}>
                        {statusLabel}
                      </span>
                      {(inst.status === 'pending' || inst.status === 'overdue') && (
                        <button
                          onClick={() => openPaymentModalForInstallment(inst)}
                          className="flex items-center gap-1 text-xs bg-white/[0.06] border border-white/[0.08] text-white/70 px-2 py-1 rounded-lg hover:bg-white/[0.1] transition-colors"
                        >
                          <Banknote size={12} />
                          {t('installment.pay_installment')}
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </>
      )}

      {/* ── Modals ─────────────────────────────────────────────────────────── */}

      {showCreatePlan && (
        <CreatePlanModal
          newPlanData={newPlanData}
          setNewPlanData={setNewPlanData}
          professionals={professionals}
          onCreate={handleCreatePlan}
          onClose={() => setShowCreatePlan(false)}
          t={t}
        />
      )}

      {showAddItem && (
        <Modal onClose={() => setShowAddItem(false)}>
          <h3 className="text-lg font-semibold text-white mb-4">{t('billing.add_treatment')}</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('billing.select_treatment')}</label>
              <select
                value={newItemData.treatment_type_code}
                onChange={(e) => {
                  const selected = treatmentTypes.find((tt) => tt.code === e.target.value);
                  setNewItemData({
                    ...newItemData,
                    treatment_type_code: e.target.value,
                    estimated_price: selected ? String(selected.base_price) : '',
                  });
                }}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">{t('billing.select_treatment')}</option>
                {treatmentTypes.map((tt) => (
                  <option key={tt.code} value={tt.code}>{tt.name} — ${tt.base_price}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('billing.custom_description')}</label>
              <textarea
                rows={3}
                value={newItemData.custom_description}
                onChange={(e) => setNewItemData({ ...newItemData, custom_description: e.target.value })}
                placeholder={t('billing.custom_description_placeholder')}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
              ></textarea>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('billing.estimated_price')}</label>
              <input
                type="number"
                value={newItemData.estimated_price}
                onChange={(e) => setNewItemData({ ...newItemData, estimated_price: e.target.value })}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <button
              onClick={handleAddItem}
              disabled={!newItemData.treatment_type_code}
              className="w-full bg-white text-[#0a0e1a] py-2 rounded-lg hover:opacity-90 disabled:opacity-50 font-medium"
            >
              {t('billing.add_treatment')}
            </button>
          </div>
        </Modal>
      )}

      {showRegisterPayment && (
        <Modal onClose={() => { setShowRegisterPayment(false); setNewPaymentData({ amount: '', payment_method: 'cash', payment_date: new Date().toISOString().split('T')[0], notes: '', installment_id: '' }); }}>
          <h3 className="text-lg font-semibold text-white mb-4">{t('billing.register_payment')}</h3>
          <div className="space-y-4">
            {/* Installment selector — only when plan has installments */}
            {planDetail?.installments && planDetail.installments.length > 0 && (
              <div>
                <label className="block text-sm text-white/60 mb-1">{t('installment.select_installment')}</label>
                <select
                  value={newPaymentData.installment_id}
                  onChange={(e) => {
                    const instId = e.target.value;
                    const inst = planDetail.installments?.find((i) => i.id === instId);
                    setNewPaymentData({
                      ...newPaymentData,
                      installment_id: instId,
                      amount: inst ? String(inst.amount) : newPaymentData.amount,
                    });
                  }}
                  className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary"
                >
                  <option value="">{t('installment.free_payment')}</option>
                  {planDetail.installments
                    .filter((i) => i.status === 'pending' || i.status === 'overdue')
                    .map((i) => {
                      const due = new Date(i.due_date);
                      const dueFmt = isNaN(due.getTime()) ? i.due_date : due.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit', year: 'numeric' });
                      return (
                        <option key={i.id} value={i.id}>
                          {t('installment.cuota')} {i.installment_number} — {formatCurrency(i.amount)} — {t('installment.due_date')} {dueFmt}
                        </option>
                      );
                    })}
                </select>
              </div>
            )}
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('billing.amount')}</label>
              <input
                type="number"
                value={newPaymentData.amount}
                onChange={(e) => setNewPaymentData({ ...newPaymentData, amount: e.target.value })}
                placeholder={formatCurrency(pendingTotal)}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <p className="text-xs text-white/40 mt-1">{t('billing.pending_balance_helper')} {formatCurrency(pendingTotal)}</p>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-2">{t('billing.method_label')}</label>
              <div className="flex gap-2">
                {(['cash', 'transfer', 'card'] as const).map((method) => (
                  <button
                    key={method}
                    onClick={() => setNewPaymentData({ ...newPaymentData, payment_method: method })}
                    className={`flex-1 flex items-center justify-center gap-1 py-2 rounded-lg text-sm transition-colors ${
                      newPaymentData.payment_method === method
                        ? 'bg-white text-[#0a0e1a] font-medium'
                        : 'bg-white/[0.06] text-white/60 border border-white/[0.08]'
                    }`}
                  >
                    {method === 'cash' && <Banknote size={16} />}
                    {method === 'transfer' && <ArrowRightLeft size={16} />}
                    {method === 'card' && <CreditCard size={16} />}
                    {t(`billing.method.${method}`)}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('billing.payment_date')}</label>
              <input
                type="date"
                value={newPaymentData.payment_date}
                onChange={(e) => setNewPaymentData({ ...newPaymentData, payment_date: e.target.value })}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-xs text-white/40 mb-1">{t('billing.notes')}</label>
              <textarea
                value={newPaymentData.notes}
                onChange={(e) => setNewPaymentData({ ...newPaymentData, notes: e.target.value })}
                className="w-full bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2 text-white text-sm"
                rows={2}
                placeholder={t('billing.notes_placeholder') || 'Notas opcionales...'}
              />
            </div>
            {paymentError && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg p-3 text-sm">
                {paymentError}
              </div>
            )}
            <button
              onClick={handleRegisterPayment}
              disabled={!newPaymentData.amount || parseFloat(newPaymentData.amount) <= 0}
              className="w-full bg-white text-[#0a0e1a] py-2 rounded-lg hover:opacity-90 disabled:opacity-50 font-medium"
            >
              {t('billing.register_payment')}
            </button>
          </div>
        </Modal>
      )}

      {showApprovePlan && planDetail && (
        <Modal onClose={() => setShowApprovePlan(false)}>
          <h3 className="text-lg font-semibold text-white mb-2">{t('billing.approve_plan')}</h3>
          <p className="text-sm text-white/60 mb-4">{t('billing.approve_confirm')}</p>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('billing.approved_total')}</label>
              <input
                type="number"
                value={approveData.approved_total}
                onChange={(e) => setApproveData({ ...approveData, approved_total: e.target.value })}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <button
              onClick={handleApprovePlan}
              disabled={!approveData.approved_total}
              className="w-full bg-white text-[#0a0e1a] py-2 rounded-lg hover:opacity-90 disabled:opacity-50 font-medium"
            >
              {t('billing.approve_plan')}
            </button>
          </div>
        </Modal>
      )}

      {showEmailModal && (
        <Modal onClose={() => setShowEmailModal(false)}>
          <h3 className="text-lg font-semibold text-white mb-4">{t('billing.send_email_title')}</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('billing.send_email_to')}</label>
              <input
                type="email"
                value={emailTo}
                onChange={(e) => setEmailTo(e.target.value)}
                placeholder="email@paciente.com"
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <button
              onClick={handleSendEmail}
              disabled={sendingEmail || !emailTo.trim()}
              className="w-full flex items-center justify-center gap-2 bg-white text-[#0a0e1a] py-2 rounded-lg hover:opacity-90 disabled:opacity-50 font-medium"
            >
              {sendingEmail ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Mail size={16} />
              )}
              {t('billing.send_email')}
            </button>
          </div>
        </Modal>
      )}

      {/* Treatment Picker Modal */}
      {showTreatmentPicker && (() => {
        const unlinked = (billingData?.appointments || []).filter((a: AppointmentBilling) => !a.plan_item_id);
        const groupMap: Record<string, { code: string; name: string; count: number; total: number; hasPaid: boolean }> = {};
        unlinked.forEach((a: AppointmentBilling) => {
          const code = a.treatment_code || 'sin_tipo';
          if (!groupMap[code]) {
            groupMap[code] = { code, name: a.treatment_name || code, count: 0, total: 0, hasPaid: false };
          }
          groupMap[code].count += 1;
          groupMap[code].total += (a.billing_amount || 0);
          if (a.payment_status === 'paid') groupMap[code].hasPaid = true;
        });
        const groups = Object.values(groupMap);

        const toggleCode = (code: string) => {
          setSelectedTreatmentCodes(prev =>
            prev.includes(code) ? prev.filter(c => c !== code) : [...prev, code]
          );
        };

        const selectAll = () => setSelectedTreatmentCodes(groups.map(g => g.code));
        const selectNone = () => setSelectedTreatmentCodes([]);

        return (
          <Modal onClose={() => setShowTreatmentPicker(false)}>
            <h3 className="text-lg font-semibold text-white mb-2">
              {t('billing.select_treatments') || 'Seleccionar tratamientos'}
            </h3>
            <p className="text-sm text-white/50 mb-4">
              {t('billing.select_treatments_desc') || 'Elegí qué tratamientos incluir en el presupuesto'}
            </p>

            {/* Select all / none */}
            <div className="flex gap-3 mb-3">
              <button onClick={selectAll} className="text-xs text-blue-400 hover:text-blue-300">
                {t('billing.select_all') || 'Seleccionar todos'}
              </button>
              <button onClick={selectNone} className="text-xs text-white/40 hover:text-white/60">
                {t('billing.select_none') || 'Ninguno'}
              </button>
            </div>

            {/* Treatment checkboxes */}
            <div className="space-y-2 mb-6 max-h-60 overflow-y-auto">
              {groups.map((g) => (
                <label
                  key={g.code}
                  className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                    selectedTreatmentCodes.includes(g.code)
                      ? 'bg-blue-500/10 border-blue-500/30'
                      : 'bg-white/[0.02] border-white/[0.06] hover:bg-white/[0.04]'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={selectedTreatmentCodes.includes(g.code)}
                    onChange={() => toggleCode(g.code)}
                    className="w-4 h-4 rounded border-white/20 bg-white/[0.04] text-blue-500 focus:ring-blue-500/30"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white">{g.name}</p>
                    <p className="text-xs text-white/40">
                      {g.count} turno{g.count !== 1 ? 's' : ''}
                      {g.total > 0 && ` · ${formatCurrency(g.total)}`}
                      {g.hasPaid && ' · Tiene pagos verificados'}
                    </p>
                  </div>
                </label>
              ))}
              {groups.length === 0 && (
                <p className="text-sm text-white/40 text-center py-4">
                  {t('billing.no_unlinked') || 'No hay turnos sin presupuesto asignado'}
                </p>
              )}
            </div>

            {/* Actions */}
            <div className="flex gap-3">
              <button
                onClick={() => setShowTreatmentPicker(false)}
                className="flex-1 py-2 rounded-lg border border-white/[0.08] text-white/60 hover:bg-white/[0.04] transition-colors text-sm"
              >
                {t('billing.cancel') || 'Cancelar'}
              </button>
              <button
                onClick={() => handleGeneratePlanFromAppointments(selectedTreatmentCodes)}
                disabled={selectedTreatmentCodes.length === 0 || generatingPlan}
                className="flex-1 flex items-center justify-center gap-2 bg-white text-[#0a0e1a] py-2 rounded-lg hover:opacity-90 disabled:opacity-50 font-medium text-sm"
              >
                {generatingPlan ? (
                  <Loader2 size={16} className="animate-spin" />
                ) : (
                  <Sparkles size={16} />
                )}
                {t('billing.create_budget') || 'Crear presupuesto'} ({selectedTreatmentCodes.length})
              </button>
            </div>
          </Modal>
        );
      })()}

      {/* Generate Installments Modal */}
      {showGenerateInstallments && (
        <Modal onClose={() => setShowGenerateInstallments(false)}>
          <h3 className="text-lg font-semibold text-white mb-4">{t('installment.generate_title')}</h3>
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('installment.count')}</label>
              <input
                type="number"
                min="1"
                max="24"
                value={generateInstallmentsData.count}
                onChange={(e) => setGenerateInstallmentsData({ ...generateInstallmentsData, count: e.target.value })}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('installment.start_date')}</label>
              <input
                type="date"
                value={generateInstallmentsData.start_date}
                onChange={(e) => setGenerateInstallmentsData({ ...generateInstallmentsData, start_date: e.target.value })}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('installment.frequency')}</label>
              <select
                value={generateInstallmentsData.frequency}
                onChange={(e) => setGenerateInstallmentsData({ ...generateInstallmentsData, frequency: e.target.value })}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="monthly">{t('installment.monthly')}</option>
                <option value="biweekly">{t('installment.biweekly')}</option>
                <option value="weekly">{t('installment.weekly')}</option>
              </select>
            </div>
            <button
              onClick={handleGenerateInstallments}
              disabled={generatingInstallments || !generateInstallmentsData.count || !generateInstallmentsData.start_date}
              className="w-full flex items-center justify-center gap-2 bg-white text-[#0a0e1a] py-2 rounded-lg hover:opacity-90 disabled:opacity-50 font-medium"
            >
              {generatingInstallments ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Calendar size={16} />
              )}
              {t('installment.generate')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ─── CreatePlanModal (extracted — used in all 3 states) ───────────────────────

interface CreatePlanModalProps {
  newPlanData: { name: string; professional_id: string; notes: string };
  setNewPlanData: (d: { name: string; professional_id: string; notes: string }) => void;
  professionals: Professional[];
  onCreate: () => void;
  onClose: () => void;
  t: (key: string) => string;
}

function CreatePlanModal({ newPlanData, setNewPlanData, professionals, onCreate, onClose, t }: CreatePlanModalProps) {
  return (
    <Modal onClose={onClose}>
      <h3 className="text-lg font-semibold text-white mb-4">{t('billing.new_plan')}</h3>
      <div className="space-y-4">
        <div>
          <label className="block text-sm text-white/60 mb-1">{t('billing.plan_name')}</label>
          <input
            type="text"
            value={newPlanData.name}
            onChange={(e) => setNewPlanData({ ...newPlanData, name: e.target.value })}
            placeholder={t('billing.plan_name_placeholder')}
            className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <div>
          <label className="block text-sm text-white/60 mb-1">{t('billing.professional')}</label>
          <select
            value={newPlanData.professional_id}
            onChange={(e) => setNewPlanData({ ...newPlanData, professional_id: e.target.value })}
            className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary"
          >
            <option value="">{t('billing.no_professional')}</option>
            {professionals.map((p) => (
              <option key={p.id} value={p.id}>{p.first_name} {p.last_name}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="block text-sm text-white/60 mb-1">{t('billing.notes')}</label>
          <textarea
            value={newPlanData.notes}
            onChange={(e) => setNewPlanData({ ...newPlanData, notes: e.target.value })}
            rows={3}
            className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
        <button
          onClick={onCreate}
          disabled={!newPlanData.name.trim()}
          className="w-full bg-white text-[#0a0e1a] py-2 rounded-lg hover:opacity-90 disabled:opacity-50 font-medium"
        >
          {t('billing.create_first')}
        </button>
      </div>
    </Modal>
  );
}

// ─── Modal base component ─────────────────────────────────────────────────────

function Modal({ children, onClose }: { children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-end md:items-center justify-center p-0 md:p-4">
      <div className="bg-[#0d1117] border border-white/[0.08] rounded-t-2xl md:rounded-xl w-full md:w-auto md:max-w-md p-6 relative">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-white/40 hover:text-white/70"
        >
          <X size={20} />
        </button>
        {children}
      </div>
    </div>
  );
}
