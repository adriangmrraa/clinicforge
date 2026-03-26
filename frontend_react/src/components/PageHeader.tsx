import { ReactNode } from 'react';

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  icon?: ReactNode;
}

export default function PageHeader({ title, subtitle, action, icon }: PageHeaderProps) {
  return (
    <div className="mb-6 sm:mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-start gap-3 min-w-0">
          {icon && (
            <div className="hidden sm:flex shrink-0 w-10 h-10 items-center justify-center rounded-xl bg-blue-500/10 text-blue-400 border border-blue-500/20">
              {icon}
            </div>
          )}
          <div className="min-w-0 flex-1 border-l-4 border-blue-500 pl-3 sm:pl-4">
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
              {title}
            </h1>
            {subtitle && (
              <p className="text-white/40 text-sm sm:text-base mt-0.5 font-medium">
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
