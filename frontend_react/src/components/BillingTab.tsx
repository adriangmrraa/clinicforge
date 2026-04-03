import { useState, useEffect, useRef } from 'react';
import { useTranslation } from '../context/LanguageContext';
import {
  Plus, Trash2, Edit2, Loader2, Receipt, X,
  Banknote, ArrowRightLeft, CreditCard, Check, AlertCircle,
  FileText, Calendar, User, ChevronDown
} from 'lucide-react';
import api from '../api/axios';

// Types
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
  payment_date: string;
  recorded_by_name: string | null;
  notes: string | null;
  appointment_id?: number;
}

interface TreatmentPlanDetail extends TreatmentPlan {
  items: TreatmentPlanItem[];
  payments: TreatmentPlanPayment[];
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

interface BillingTabProps {
  patientId: number;
  refreshKey: number;
}

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

const formatCurrency = (amount: number) => {
  return new Intl.NumberFormat('es-AR', {
    style: 'currency',
    currency: 'ARS',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(amount);
};

export default function BillingTab({ patientId, refreshKey }: BillingTabProps) {
  const { t } = useTranslation();
  
  // State
  const [plans, setPlans] = useState<TreatmentPlan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [planDetail, setPlanDetail] = useState<TreatmentPlanDetail | null>(null);
  const [loadingPlans, setLoadingPlans] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modal visibility
  const [showCreatePlan, setShowCreatePlan] = useState(false);
  const [showAddItem, setShowAddItem] = useState(false);
  const [showRegisterPayment, setShowRegisterPayment] = useState(false);
  const [showApprovePlan, setShowApprovePlan] = useState(false);

  // Inline edit state (items)
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [editingItemPrice, setEditingItemPrice] = useState<string>('');

  // Inline edit state (plan name)
  const [editingPlanName, setEditingPlanName] = useState(false);
  const [planNameDraft, setPlanNameDraft] = useState('');

  // Inline delete confirmations
  const [deletingItemId, setDeletingItemId] = useState<string | null>(null);
  const [deletingPaymentId, setDeletingPaymentId] = useState<string | null>(null);

  // Form data
  const [newPlanData, setNewPlanData] = useState({ name: '', professional_id: '', notes: '' });
  const [newItemData, setNewItemData] = useState({ treatment_type_code: '', custom_description: '', estimated_price: '' });
  const [newPaymentData, setNewPaymentData] = useState({ amount: '', payment_method: 'cash', payment_date: new Date().toISOString().split('T')[0], notes: '' });
  const [approveData, setApproveData] = useState({ approved_total: '' });

  // Data for modals
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [treatmentTypes, setTreatmentTypes] = useState<TreatmentType[]>([]);

  // Load plans on mount and refresh
  useEffect(() => {
    loadPlans();
  }, [patientId, refreshKey]);

  // Load plan detail when selected
  useEffect(() => {
    if (selectedPlanId) {
      loadPlanDetail(selectedPlanId);
    } else {
      setPlanDetail(null);
    }
  }, [selectedPlanId]);

  const loadPlans = async () => {
    try {
      setLoadingPlans(true);
      setError(null);
      const res = await api.get(`/admin/patients/${patientId}/treatment-plans`);
      setPlans(res.data);
      
      // Auto-select if only 1 plan
      if (res.data.length === 1 && !selectedPlanId) {
        setSelectedPlanId(res.data[0].id);
      }
    } catch (err) {
      console.error('Error loading plans:', err);
      setError(t('billing.error_load'));
    } finally {
      setLoadingPlans(false);
    }
  };

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

  // Calculate totals
  const estimatedTotal = planDetail?.estimated_total || 0;
  const approvedTotal = planDetail?.approved_total || estimatedTotal;
  const paidTotal = planDetail?.payments?.reduce((sum, p) => sum + p.amount, 0) || 0;
  const pendingTotal = Math.max(approvedTotal - paidTotal, 0);
  const progressPercent = approvedTotal > 0 ? Math.min((paidTotal / approvedTotal) * 100, 100) : 0;

  // Handlers
  const handleCreatePlan = async () => {
    if (!newPlanData.name.trim()) return;
    try {
      const payload: any = {
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
    } catch (err) {
      console.error('Error creating plan:', err);
      setError(t('billing.error_save'));
    }
  };

  const handleAddItem = async () => {
    if (!newItemData.treatment_type_code || !planDetail) return;
    try {
      const payload: any = {
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
      await api.post(`/admin/treatment-plans/${planDetail.id}/payments`, {
        amount: parseFloat(newPaymentData.amount),
        payment_method: newPaymentData.payment_method,
        payment_date: newPaymentData.payment_date,
        notes: newPaymentData.notes || null,
      });
      setShowRegisterPayment(false);
      setNewPaymentData({ amount: '', payment_method: 'cash', payment_date: new Date().toISOString().split('T')[0], notes: '' });
      await loadPlanDetail(planDetail.id);
    } catch (err) {
      console.error('Error registering payment:', err);
      setError(t('billing.error_save'));
    }
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

  const handleUpdateItemPrice = async (itemId: string) => {
    if (!editingItemPrice || !planDetail) return;
    try {
      await api.patch(`/admin/treatment-plan-items/${itemId}`, {
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

  // Loading skeleton
  if (loadingPlans) {
    return (
      <div className="space-y-4">
        <div className="h-12 bg-white/[0.04] rounded animate-pulse" />
        <div className="h-48 bg-white/[0.04] rounded animate-pulse" />
        <div className="h-64 bg-white/[0.04] rounded animate-pulse" />
      </div>
    );
  }

  // Empty state - no plans
  if (plans.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-center">
        <Receipt size={48} className="text-white/20 mb-4" />
        <h3 className="text-lg font-medium text-white mb-2">{t('billing.no_plans')}</h3>
        <button
          onClick={openCreatePlanModal}
          className="flex items-center gap-2 bg-primary text-white px-4 py-2 rounded-lg hover:bg-primary-dark transition-colors"
        >
          <Plus size={18} />
          {t('billing.create_first')}
        </button>
        
        {showCreatePlan && (
          <Modal onClose={() => setShowCreatePlan(false)}>
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
                onClick={handleCreatePlan}
                disabled={!newPlanData.name.trim()}
                className="w-full bg-primary text-white py-2 rounded-lg hover:bg-primary-dark disabled:opacity-50"
              >
                {t('billing.create_first')}
              </button>
            </div>
          </Modal>
        )}
      </div>
    );
  }

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

      {/* Plan Selector Bar */}
      <div className="flex items-center gap-4">
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
          className="flex items-center gap-2 bg-white/[0.06] text-white border border-white/[0.08] px-4 py-2 rounded-lg hover:bg-white/[0.1]"
        >
          <Plus size={18} />
          {t('billing.new_plan')}
        </button>
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

            {/* Approve Button */}
            {planDetail.status === 'draft' && (
              <button
                onClick={() => { setApproveData({ approved_total: String(planDetail.estimated_total) }); setShowApprovePlan(true); }}
                className="mb-4 bg-blue-500/10 text-blue-400 border border-blue-500/20 px-4 py-2 rounded-lg text-sm hover:bg-blue-500/20"
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
                <p className="text-[10px] text-white/40 uppercase font-bold">{t('billing.approved_total')}</p>
                <p className="text-base font-bold text-white">{approvedTotal > 0 ? formatCurrency(approvedTotal) : t('billing.no_approved_total')}</p>
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
                              <div className="flex items-center gap-1">
                                <input
                                  type="number"
                                  value={editingItemPrice}
                                  onChange={(e) => setEditingItemPrice(e.target.value)}
                                  onKeyDown={(e) => e.key === 'Enter' && handleUpdateItemPrice(item.id)}
                                  className="w-24 px-2 py-1 bg-white/[0.04] border border-white/[0.08] rounded text-white text-sm"
                                  autoFocus
                                />
                                <button onClick={() => handleUpdateItemPrice(item.id)} className="text-green-400">
                                  <Check size={14} />
                                </button>
                              </div>
                            ) : (
                              <span
                                className="text-sm text-white cursor-pointer hover:text-primary"
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
                                onKeyDown={(e) => e.key === 'Enter' && handleUpdateItemPrice(item.id)}
                                className="w-20 px-2 py-0.5 bg-white/[0.04] border border-white/[0.08] rounded text-white text-xs"
                                autoFocus
                              />
                              <button onClick={() => handleUpdateItemPrice(item.id)} className="text-green-400">
                                <Check size={12} />
                              </button>
                            </div>
                          ) : (
                            <p
                              className="text-white cursor-pointer hover:text-primary"
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

          {/* Payments Section */}
          <div className="bg-white/[0.02] border border-white/[0.06] rounded-xl p-4">
            <div className="flex justify-between items-center mb-4">
              <h4 className="text-sm font-semibold text-white">{t('billing.payments')}</h4>
              <button
                onClick={() => { setNewPaymentData({ ...newPaymentData, amount: String(pendingTotal) }); setShowRegisterPayment(true); }}
                disabled={planDetail.status === 'cancelled'}
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
                        <th className="text-left py-3 px-2">{t('billing.notes')}</th>
                        <th className="w-10"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {planDetail.payments.map((payment) => (
                        <tr key={payment.id} className="border-b border-white/[0.04] hover:bg-white/[0.02]">
                          <td className="py-3 px-2 text-sm text-white">
                            {new Date(payment.payment_date).toLocaleDateString('es-AR')}
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
                            {payment.recorded_by_name || '-'}
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
                          {new Date(payment.payment_date).toLocaleDateString('es-AR')} — {t(`billing.method.${payment.payment_method}`)}
                        </p>
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
        </>
      )}

      {/* Modals */}
      {showCreatePlan && (
        <Modal onClose={() => setShowCreatePlan(false)}>
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
              onClick={handleCreatePlan}
              disabled={!newPlanData.name.trim()}
              className="w-full bg-primary text-white py-2 rounded-lg hover:bg-primary-dark disabled:opacity-50"
            >
              {t('billing.create_first')}
            </button>
          </div>
        </Modal>
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
                  const selected = treatmentTypes.find(t => t.code === e.target.value);
                  setNewItemData({
                    ...newItemData,
                    treatment_type_code: e.target.value,
                    estimated_price: selected ? String(selected.base_price) : '',
                  });
                }}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="">{t('billing.select_treatment')}</option>
                {treatmentTypes.map((t) => (
                  <option key={t.code} value={t.code}>{t.name} — ${t.base_price}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm text-white/60 mb-1">{t('billing.custom_description')}</label>
              <input
                type="text"
                value={newItemData.custom_description}
                onChange={(e) => setNewItemData({ ...newItemData, custom_description: e.target.value })}
                placeholder={t('billing.custom_description_placeholder')}
                className="w-full px-3 py-2 bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-white/30 focus:outline-none focus:ring-2 focus:ring-primary"
              />
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
              className="w-full bg-primary text-white py-2 rounded-lg hover:bg-primary-dark disabled:opacity-50"
            >
              {t('billing.add_treatment')}
            </button>
          </div>
        </Modal>
      )}

      {showRegisterPayment && (
        <Modal onClose={() => setShowRegisterPayment(false)}>
          <h3 className="text-lg font-semibold text-white mb-4">{t('billing.register_payment')}</h3>
          <div className="space-y-4">
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
                    className={`flex-1 flex items-center justify-center gap-1 py-2 rounded-lg text-sm ${
                      newPaymentData.payment_method === method
                        ? 'bg-primary text-white'
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
            <button
              onClick={handleRegisterPayment}
              disabled={!newPaymentData.amount}
              className="w-full bg-primary text-white py-2 rounded-lg hover:bg-primary-dark disabled:opacity-50"
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
              className="w-full bg-primary text-white py-2 rounded-lg hover:bg-primary-dark disabled:opacity-50"
            >
              {t('billing.approve_plan')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}

// Simple Modal component
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