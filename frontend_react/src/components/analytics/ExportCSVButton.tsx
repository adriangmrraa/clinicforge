import { Download } from 'lucide-react';
import { useTranslation } from '../../context/LanguageContext';
import type { LiquidationResponse, LiquidationSession } from '../../types/liquidation';

interface ExportCSVButtonProps {
  data: LiquidationResponse | null;
  disabled?: boolean;
}

function escapeCSV(value: string | number | null | undefined): string {
  const str = value == null ? '' : String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  if (isNaN(d.getTime())) return dateStr;
  const dd = String(d.getDate()).padStart(2, '0');
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const yyyy = d.getFullYear();
  return `${dd}/${mm}/${yyyy}`;
}

function paymentStatusLabel(status: LiquidationSession['payment_status']): string {
  switch (status) {
    case 'paid':    return 'Pagado';
    case 'partial': return 'Parcial';
    case 'pending': return 'Pendiente';
    default:        return status;
  }
}

export function ExportCSVButton({ data, disabled }: ExportCSVButtonProps) {
  const { t } = useTranslation();

  function handleExport() {
    if (!data || data.professionals.length === 0) return;

    const headers = [
      'Profesional',
      'Paciente',
      'Teléfono',
      'Tratamiento',
      'Fecha',
      'Monto',
      'Estado Pago',
      'Notas Facturación',
      'Notas Clínicas',
    ];

    const rows: string[] = [headers.map(escapeCSV).join(',')];

    for (const professional of data.professionals) {
      for (const group of professional.treatment_groups) {
        for (const session of group.sessions) {
          const row = [
            escapeCSV(professional.name),
            escapeCSV(group.patient_name),
            escapeCSV(group.patient_phone),
            escapeCSV(group.treatment_name),
            escapeCSV(formatDate(session.date)),
            escapeCSV(session.billing_amount),
            escapeCSV(paymentStatusLabel(session.payment_status)),
            escapeCSV(session.billing_notes),
            escapeCSV(session.clinical_notes),
          ];
          rows.push(row.join(','));
        }
      }
    }

    const csvContent = '\uFEFF' + rows.join('\r\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `liquidacion_${data.period.start}_${data.period.end}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <button
      onClick={handleExport}
      disabled={disabled || !data || data.professionals.length === 0}
      className="flex items-center gap-2 px-4 py-2 bg-white/[0.06] hover:bg-white/[0.1] text-white/70 rounded-lg text-sm font-medium transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
    >
      <Download size={16} />
      {t('liquidation.export_csv')}
    </button>
  );
}
