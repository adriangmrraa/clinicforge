import React from 'react';
import { CheckCircle, Clock, AlertTriangle, CloudOff, User, HelpCircle } from 'lucide-react';
import type { EventContentArg } from '@fullcalendar/core';

interface ExtendedProps {
    eventType: 'appointment' | 'gcalendar_block';
    source?: 'ai' | 'manual';
    status?: string; // scheduled, confirmed, in_progress, completed, cancelled, no_show
    patient_name?: string;
    patient_phone?: string;
    professional_name?: string;
    appointment_type?: string;
    notes?: string;
    urgency_level?: string;
}

// Status Visual Configuration
const STATUS_STYLES: Record<string, { bg: string; border: string; text: string; icon: React.ElementType }> = {
    confirmed: {
        bg: 'bg-emerald-500/10',
        border: 'border-l-emerald-500',
        text: 'text-emerald-900',
        icon: CheckCircle
    },
    scheduled: {
        bg: 'bg-blue-500/10',
        border: 'border-l-blue-500',
        text: 'text-blue-900',
        icon: Clock
    },
    pending: {
        bg: 'bg-amber-500/10',
        border: 'border-l-amber-500',
        text: 'text-amber-900',
        icon: HelpCircle
    },
    in_progress: {
        bg: 'bg-purple-500/10',
        border: 'border-l-purple-500',
        text: 'text-purple-900',
        icon: Clock
    },
    completed: {
        bg: 'bg-slate-500/10',
        border: 'border-l-slate-500',
        text: 'text-slate-900',
        icon: CheckCircle
    },
    cancelled: {
        bg: 'bg-red-500/10',
        border: 'border-l-red-500',
        text: 'text-red-900',
        icon: AlertTriangle
    },
    no_show: {
        bg: 'bg-orange-500/10',
        border: 'border-l-orange-500',
        text: 'text-orange-900',
        icon: AlertTriangle
    },
    // Urgency overrides
    emergency: {
        bg: 'bg-rose-500/10',
        border: 'border-l-rose-500',
        text: 'text-rose-900',
        icon: AlertTriangle
    }
};

export const AppointmentCard: React.FC<EventContentArg> = (eventInfo) => {
    const props = eventInfo.event.extendedProps as ExtendedProps;
    const { eventType, status, appointment_type, professional_name, urgency_level } = props;
    const isGCal = eventType === 'gcalendar_block';

    // --- GCal Block Rendering ---
    if (isGCal) {
        return (
            <div className="flex flex-col h-full p-1.5 rounded-lg border-l-4 border-l-gray-400 bg-gray-50/80 backdrop-blur-sm overflow-hidden shadow-sm hover:shadow-md transition-all duration-200"
                style={{ backgroundImage: 'repeating-linear-gradient(45deg, transparent, transparent 10px, rgba(0,0,0,0.03) 10px, rgba(0,0,0,0.03) 20px)' }}>
                <div className="flex items-center gap-1.5 text-gray-500 font-semibold text-[10px] uppercase tracking-wider mb-1 opacity-70">
                    <CloudOff size={10} />
                    <span>GCalendar</span>
                </div>
                <div className="font-medium text-xs text-gray-700 truncate leading-tight">
                    {eventInfo.event.title.replace('🔒 ', '')}
                </div>
            </div>
        );
    }

    // --- Appointment Rendering ---

    // Determine styles (Urgency takes precedence)
    const styleKey = (urgency_level === 'high' || urgency_level === 'emergency') ? 'emergency' : (status || 'scheduled');
    const styles = STATUS_STYLES[styleKey] || STATUS_STYLES.scheduled;
    const StatusIcon = styles.icon;

    return (
        <div className={`
      flex flex-col h-full w-full p-2 
      rounded-xl border-l-4 ${styles.border} ${styles.bg}
      shadow-sm hover:shadow-md hover:scale-[1.02] 
      transition-all duration-200 cursor-pointer overflow-hidden
      ${urgency_level === 'emergency' ? 'animate-pulse-soft' : ''}
    `}>
            {/* Top: Time & Status Icon */}
            <div className="flex justify-between items-start mb-0.5">
                <span className={`text-[10px] font-mono opacity-60 ${styles.text}`}>
                    {eventInfo.timeText}
                </span>
                <StatusIcon size={12} className={`opacity-80 ${styles.text}`} />
            </div>

            {/* Center: Patient Name */}
            <div className={`font-semibold text-xs truncate leading-snug mb-1 ${styles.text}`}>
                {eventInfo.event.title.split(' - ')[0]}
            </div>

            {/* Bottom: Badge & Professional */}
            <div className="mt-auto flex flex-col gap-1">

                {/* Treatment Badge */}
                <div className="flex">
                    <span className="inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-medium bg-white/60 backdrop-blur-sm text-slate-700 truncate max-w-full">
                        {appointment_type || 'Consulta'}
                    </span>
                </div>

                {/* Professional (Desktop only mostly) */}
                {professional_name && (
                    <div className="flex items-center gap-1 text-[9px] opacity-70 truncate">
                        <User size={8} />
                        <span className="truncate">Dr. {professional_name.split(' ')[0]}</span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AppointmentCard;
