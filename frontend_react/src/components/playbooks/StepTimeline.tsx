import React from 'react';
import {
  Send, Clock, MessageSquare, Bell, RefreshCw, GitBranch,
  Settings, FileText, CheckCircle2
} from 'lucide-react';

interface Step {
  id?: number;
  step_order: number;
  step_label?: string;
  action_type: string;
  delay_minutes: number;
}

interface StepTimelineProps {
  steps: Step[];
  activeStepOrder?: number;
  onStepClick?: (order: number) => void;
}

const ACTION_ICONS: Record<string, React.ReactNode> = {
  send_template: <Send size={14} />,
  send_text: <MessageSquare size={14} />,
  send_instructions: <FileText size={14} />,
  wait: <Clock size={14} />,
  wait_response: <RefreshCw size={14} />,
  branch: <GitBranch size={14} />,
  notify_team: <Bell size={14} />,
  update_status: <Settings size={14} />,
};

const ACTION_COLORS: Record<string, string> = {
  send_template: 'bg-green-500',
  send_text: 'bg-blue-500',
  send_instructions: 'bg-purple-500',
  wait: 'bg-gray-500',
  wait_response: 'bg-amber-500',
  branch: 'bg-pink-500',
  notify_team: 'bg-red-500',
  update_status: 'bg-indigo-500',
};

const ACTION_LABELS: Record<string, string> = {
  send_template: 'Plantilla HSM',
  send_text: 'Texto libre',
  send_instructions: 'Instrucciones',
  wait: 'Esperar',
  wait_response: 'Esperar respuesta',
  branch: 'Ramificar',
  notify_team: 'Notificar equipo',
  update_status: 'Actualizar estado',
};

function formatDelay(minutes: number): string {
  if (minutes === 0) return 'Inmediato';
  if (minutes < 60) return `${minutes}min`;
  if (minutes < 1440) return `${Math.round(minutes / 60)}h`;
  return `${Math.round(minutes / 1440)}d`;
}

export default function StepTimeline({ steps, activeStepOrder, onStepClick }: StepTimelineProps) {
  if (steps.length === 0) {
    return (
      <div className="text-center text-white/30 py-6 text-sm">
        No hay pasos configurados
      </div>
    );
  }

  return (
    <div className="relative">
      {steps.map((step, idx) => {
        const isActive = activeStepOrder === step.step_order;
        const isLast = idx === steps.length - 1;
        const color = ACTION_COLORS[step.action_type] || 'bg-gray-500';

        return (
          <div key={step.step_order} className="flex items-start gap-3 relative">
            {/* Connector line */}
            {!isLast && (
              <div className="absolute left-[15px] top-[32px] w-[2px] h-[calc(100%-16px)] bg-white/10" />
            )}

            {/* Node */}
            <div
              className={`w-[32px] h-[32px] rounded-full flex items-center justify-center shrink-0 text-white z-10 cursor-pointer transition-all
                ${color} ${isActive ? 'ring-2 ring-white/50 scale-110' : 'opacity-70 hover:opacity-100'}`}
              onClick={() => onStepClick?.(step.step_order)}
            >
              {ACTION_ICONS[step.action_type] || <CheckCircle2 size={14} />}
            </div>

            {/* Content */}
            <div
              className={`pb-4 flex-1 cursor-pointer ${isActive ? '' : 'opacity-60 hover:opacity-80'}`}
              onClick={() => onStepClick?.(step.step_order)}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white">
                  {step.step_label || ACTION_LABELS[step.action_type] || step.action_type}
                </span>
                {step.delay_minutes > 0 && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.08] text-white/50">
                    ⏱ {formatDelay(step.delay_minutes)}
                  </span>
                )}
              </div>
              <div className="text-xs text-white/40 mt-0.5">
                Paso {step.step_order + 1} · {ACTION_LABELS[step.action_type] || step.action_type}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
