import React from 'react';
// TODO: Add translation keys for title and labels

interface AttachmentSummaryProps {
  summary_text: string;
  attachments_count: number;
  attachments_types: string[];  // ['payment', 'clinical', 'payment']
  created_at: string;
}

const formatTypes = (types: string[]): string => {
  const counts = types.reduce((acc, type) => {
    acc[type] = (acc[type] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);
  
  return Object.entries(counts)
    .map(([type, count]) => {
      let label = type;
      if (type === 'payment') label = 'comprobantes de pago';
      if (type === 'clinical') label = 'documentos clínicos';
      return `${count} ${label}`;
    })
    .join(', ');
};

export const AttachmentSummaryCard: React.FC<AttachmentSummaryProps> = ({
  summary_text,
  attachments_count,
  attachments_types,
  created_at,
}) => {
  const typeSummary = formatTypes(attachments_types);
  const formattedDate = new Date(created_at).toLocaleDateString('es-AR', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });

  return (
    <div className="bg-white/[0.03] border border-white/[0.06] rounded-lg p-4 mt-4">
      <h4 className="font-semibold text-white text-sm mb-2">
        Análisis de Adjuntos Recibidos
      </h4>
      <p className="text-sm text-white/60 leading-relaxed">
        {summary_text}
      </p>
      <div className="mt-2 pt-2 border-t border-white/[0.06] text-xs text-white/40">
        {attachments_count} archivos • {typeSummary} • {formattedDate}
      </div>
    </div>
  );
};

export default AttachmentSummaryCard;