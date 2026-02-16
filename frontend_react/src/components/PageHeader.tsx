import { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  /** Optional icon (e.g. Building2, Stethoscope) to show beside title on mobile */
  icon?: ReactNode;
}

/**
 * Encabezado de página unificado: título, subtítulo y acción.
 * En mobile: layout apilado y compacto; en desktop: fila con acción alineada a la derecha.
 * Estética consistente en todas las vistas (Clínicas, Tratamientos, Pacientes, etc.).
 */
export default function PageHeader({ title, subtitle, action, icon }: PageHeaderProps) {
  return (
    <div className="mb-6 sm:mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          {icon && (
            <div className="hidden sm:flex shrink-0 w-10 h-10 items-center justify-center rounded-xl bg-medical-50 text-medical-600 border border-medical-100">
              {icon}
            </div>
          )}
          <div className="min-w-0 flex-1 border-l-4 border-medical-500 pl-3 sm:pl-4">
            <h1 className="text-xl sm:text-2xl font-bold text-slate-800 tracking-tight">
              {title}
            </h1>
            {subtitle && (
              <p className="text-slate-500 text-sm sm:text-base mt-0.5 font-medium">
                {subtitle}
              </p>
            )}
          </div>
        </div>
        {action && (
          <div className="shrink-0 flex justify-end sm:justify-start">
            {action}
          </div>
        )}
      </div>
    </div>
  );
}
