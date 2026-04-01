export interface LiquidationResponse {
  period: { start: string; end: string };
  totals: LiquidationTotals;
  professionals: LiquidationProfessional[];
}

export interface LiquidationTotals {
  billed: number;
  paid: number;
  pending: number;
  appointments: number;
  patients: number;
}

export interface LiquidationProfessional {
  id: number;
  name: string;
  specialty: string;
  summary: LiquidationTotals;
  treatment_groups: TreatmentGroup[];
}

export interface TreatmentGroup {
  patient_id: number;
  patient_name: string;
  patient_phone: string;
  treatment_code: string;
  treatment_name: string;
  sessions: LiquidationSession[];
  total_billed: number;
  total_paid: number;
  total_pending: number;
  session_count: number;
}

export interface LiquidationSession {
  appointment_id: string;
  date: string;
  status: string;
  billing_amount: number;
  payment_status: 'pending' | 'partial' | 'paid';
  billing_notes: string | null;
  clinical_notes: string | null;
}
