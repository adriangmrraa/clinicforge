import React from 'react';

interface MessagePreviewProps {
  text: string;
  buttons?: string[];
  variables?: Record<string, string>;
}

const SAMPLE_DATA: Record<string, string> = {
  nombre_paciente: 'María',
  apellido_paciente: 'López',
  tratamiento: 'Implante Simple',
  profesional: 'Dra. Laura Delgado',
  fecha_turno: '14/05',
  hora_turno: '10:00',
  dia_semana: 'lunes',
  sede: 'Sede Norte',
  nombre_clinica: 'Clínica Dra. Laura Delgado',
  precio: '$45.000',
  saldo_pendiente: '$22.500',
  first_name: 'María',
  last_name: 'López',
  treatment_name: 'Implante Simple',
  nombre_servicio: 'Implante Simple',
};

function substitutePreview(text: string, vars?: Record<string, string>): string {
  let result = text;
  const data = { ...SAMPLE_DATA, ...(vars || {}) };
  for (const [key, value] of Object.entries(data)) {
    result = result.replaceAll(`{{${key}}}`, value);
  }
  return result;
}

export default function MessagePreview({ text, buttons, variables }: MessagePreviewProps) {
  const rendered = substitutePreview(text || '', variables);

  return (
    <div className="bg-[#0b141a] rounded-xl p-4 max-w-[320px]">
      <div className="text-[10px] text-white/30 text-center mb-2">Vista previa WhatsApp</div>
      {rendered && (
        <div className="bg-[#005c4b] rounded-lg px-3 py-2 text-white text-sm leading-relaxed whitespace-pre-wrap ml-auto max-w-[280px]">
          {rendered}
          <div className="text-[10px] text-white/40 text-right mt-1">9:10 am</div>
        </div>
      )}
      {buttons && buttons.length > 0 && (
        <div className="mt-1 space-y-1 max-w-[280px] ml-auto">
          {buttons.map((btn, i) => (
            <div key={i} className="bg-[#1f2c34] text-[#53bdeb] text-center text-sm py-2 rounded-lg border border-white/[0.06]">
              {btn}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
