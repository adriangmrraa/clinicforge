// ============================================
// Financial Command Center — TypeScript Types
// ============================================

/**
 * T2.1: All TypeScript interfaces for the financial domain.
 * These match backend response shapes from the financial-command-center endpoints.
 */

// --- Liquidation Records ---

export interface LiquidationRecord {
  id: string;
  tenant_id: string;
  professional_id: number;
  professional_name: string;
  period_start: string;
  period_end: string;
  total_billed: number;
  total_paid: number;
  total_pending: number;
  commission_pct: number;
  commission_amount: number;
  payout_amount: number;
  status: 'draft' | 'generated' | 'approved' | 'paid';
  generated_at: string;
  approved_at?: string;
  paid_at?: string;
  generated_by: string;
  notes: Record<string, unknown>;
  treatment_groups?: TreatmentGroup[];
  payouts?: ProfessionalPayout[];
}

export interface ProfessionalPayout {
  id: string;
  liquidation_record_id: string;
  professional_id: number;
  amount: number;
  payment_method: 'transfer' | 'cash' | 'check';
  payment_date: string;
  reference_number?: string;
  notes?: string;
  created_at: string;
}

// --- Commission Configuration ---

export interface CommissionOverride {
  treatment_code: string;
  treatment_name?: string;
  commission_pct: number;
}

export interface ProfessionalCommission {
  professional_id: number;
  professional_name: string;
  default_commission_pct: number;
  per_treatment: CommissionOverride[];
}

// --- Financial Dashboard ---

export interface FinancialSummary {
  total_revenue: number;
  total_payouts: number;
  net_profit: number;
  total_billed: number;
  total_pending: number;
  liquidations_generated: number;
  liquidations_pending: number;
  liquidations_paid: number;
}

export interface RevenueByProfessional {
  professional_id: number;
  professional_name: string;
  specialty: string;
  total_billed: number;
  total_paid: number;
  total_pending: number;
  appointment_count: number;
  liquidation_count: number;
}

export interface RevenueByTreatment {
  treatment_code: string;
  treatment_name: string;
  total_billed: number;
  total_paid: number;
  appointment_count: number;
}

export interface DailyCashFlow {
  date: string;
  cash_received: number;
  card_received: number;
  total: number;
  payouts: number;
}

export interface MoMGrowth {
  current_revenue: number;
  previous_revenue: number;
  growth_pct: number;
  current_payouts: number;
  previous_payouts: number;
  payout_growth_pct: number;
}

export interface PendingCollection {
  patient_id: string;
  patient_name: string;
  patient_phone: string;
  appointment_id: string;
  treatment_name: string;
  amount_pending: number;
  days_overdue: number;
  professional_name?: string;
}

export interface DashboardData {
  summary: FinancialSummary;
  revenue_by_professional: RevenueByProfessional[];
  revenue_by_treatment: RevenueByTreatment[];
  daily_cash_flow: DailyCashFlow[];
  mom_growth: MoMGrowth;
  pending_collections: PendingCollection[];
}

// --- Reconciliation ---

export interface Discrepancy {
  type: string;
  appointment_id: string;
  patient_name: string;
  treatment_name?: string;
  amount: number;
  appointment_date: string;
  professional_name?: string;
  status: string;
  issue: string;
}

export interface ReconciliationData {
  total_patient_payments: number;
  total_professional_payouts: number;
  discrepancy_count: number;
  differences?: number;
  discrepancies: Discrepancy[];
}

// --- Liquidation Detail ---

export interface TreatmentSession {
  appointment_id: string;
  date: string;
  description: string;
  amount: number;
  payment_status: string;
}

export interface TreatmentGroup {
  patient_id: string;
  patient_name: string;
  treatment_code: string;
  treatment_name: string;
  sessions: TreatmentSession[];
  total: number;
}

export interface LiquidationDetail {
  liquidation: LiquidationRecord;
  treatment_groups: TreatmentGroup[];
  totals: {
    total_billed: number;
    total_paid: number;
    total_pending: number;
    commission_pct: number;
    commission_amount: number;
    payout_amount: number;
  };
}

// --- API Response Shapes ---

export interface LiquidationListResponse {
  liquidations: LiquidationRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface FinancialDashboardResponse {
  summary: FinancialSummary;
  revenue_by_professional: RevenueByProfessional[];
  revenue_by_treatment: RevenueByTreatment[];
  daily_cash_flow: DailyCashFlow[];
  mom_growth: MoMGrowth;
  top_treatments: RevenueByTreatment[];
  pending_collections: PendingCollection[];
}

export interface ReconciliationReport {
  period_start: string;
  period_end: string;
  total_patient_payments: number;
  total_professional_payouts: number;
  difference: number;
  discrepancies: Discrepancy[];
  discrepancy_count: number;
}

export interface GenerateBulkResponse {
  generated_count: number;
  skipped_count: number;
  liquidations: LiquidationRecord[];
}
