import DateStrip from './DateStrip';
import type { Appointment, Professional, GoogleCalendarBlock } from '../views/AgendaView';
import { Clock, User, Phone, Lock } from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { useTranslation } from '../context/LanguageContext';

interface MobileAgendaProps {
    appointments: Appointment[];
    googleBlocks: GoogleCalendarBlock[];
    selectedDate: Date;
    onDateChange: (date: Date) => void;
    onEventClick: (event: any) => void;
    professionals: Professional[];
}

export default function MobileAgenda({
    appointments,
    googleBlocks,
    selectedDate,
    onDateChange,
    onEventClick,
    professionals
}: MobileAgendaProps) {
    const { t } = useTranslation();

    // Filter appointments for the selected date - FIX 4: Normalización robusta
    const dailyAppointments = appointments.filter(apt => {
        const aptDateString = format(parseISO(apt.appointment_datetime), 'yyyy-MM-dd');
        const selectedDateString = format(selectedDate, 'yyyy-MM-dd');
        return aptDateString === selectedDateString;
    });

    // Filter blocks for the selected date
    const dailyBlocks = googleBlocks.filter(block => {
        const blockDateString = format(parseISO(block.start_datetime), 'yyyy-MM-dd');
        const selectedDateString = format(selectedDate, 'yyyy-MM-dd');
        return blockDateString === selectedDateString;
    });

    // Unify and sort
    const allDailyEvents = [
        ...dailyAppointments.map(apt => ({ ...apt, uiType: 'appointment' })),
        ...dailyBlocks.map(block => ({ ...block, uiType: 'block' }))
    ].sort((a: any, b: any) => {
        const timeA = new Date(a.appointment_datetime || a.start_datetime).getTime();
        const timeB = new Date(b.appointment_datetime || b.start_datetime).getTime();
        return timeA - timeB;
    });

    const formatTime = (dateStr: string) => {
        return new Date(dateStr).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    };

    const getStatusColor = (status: string) => {
        // Simplified status colors for mobile border
        switch (status) {
            case 'confirmed': return 'border-l-green-500';
            case 'cancelled': return 'border-l-red-500';
            case 'completed': return 'border-l-gray-500';
            case 'no_show': return 'border-l-orange-500';
            default: return 'border-l-blue-500';
        }
    };

    return (
        <div className="flex flex-col flex-1 min-h-0">
            {/* Date Strip Navigation */}
            <DateStrip selectedDate={selectedDate} onDateSelect={onDateChange} />

            {/* Appointment List */}
            <div className="flex-1 overflow-y-auto p-4 pb-24 space-y-3 min-h-0">
                {allDailyEvents.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-48 text-white/20">
                        <Clock size={48} className="mb-2 opacity-30" />
                        <p className="text-sm text-white/40">{t('agenda.no_appointments_today')}</p>
                    </div>
                ) : (
                    allDailyEvents.map((evt: any) => (
                        <div
                            key={evt.id}
                            onClick={() => onEventClick({
                                event: {
                                    start: new Date(evt.appointment_datetime || evt.start_datetime),
                                    extendedProps: { ...evt, eventType: evt.uiType === 'block' ? 'gcalendar_block' : 'appointment' }
                                }
                            })}
                            className={`bg-white/[0.03] rounded-xl p-4 border-l-4 border border-white/[0.06] ${evt.uiType === 'block'
                                ? 'border-l-white/20'
                                : getStatusColor(evt.status)
                                } active:scale-[0.98] hover:bg-white/[0.05] transition-all touch-manipulation`}
                        >
                            <div className="flex justify-between items-start mb-2">
                                <div className="flex items-center gap-2">
                                    <span className="text-lg font-bold text-white">
                                        {formatTime(evt.appointment_datetime || evt.start_datetime)}
                                    </span>
                                    {evt.uiType === 'appointment' && (
                                        <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-white/[0.06] text-white/50">
                                            {evt.duration_minutes || 30} min
                                        </span>
                                    )}
                                </div>
                                {/* Status Badge */}
                                <span className={`text-[10px] uppercase font-bold tracking-wider px-2 py-1 rounded bg-white/[0.04] text-white/40`}>
                                    {evt.uiType === 'block' ? 'Bloqueado' : evt.status}
                                </span>
                            </div>

                            <div className="mb-1">
                                <h3 className="text-base font-semibold text-white line-clamp-1">
                                    {evt.uiType === 'block' ? (
                                        <span className="flex items-center gap-1.5 text-white/40">
                                            <Lock size={14} className="shrink-0" />
                                            Google: {evt.title}
                                        </span>
                                    ) : (
                                        evt.patient_name || 'Paciente sin nombre'
                                    )}
                                </h3>
                                {evt.uiType === 'appointment' && (
                                    <p className="text-sm text-white/40 line-clamp-1">
                                        {evt.appointment_type}
                                    </p>
                                )}
                            </div>

                            <div className="flex items-center gap-4 mt-3 pt-3 border-t border-white/[0.04]">
                                {/* Professional Name */}
                                <div className="flex items-center gap-1.5 text-white/30">
                                    <User size={14} />
                                    <span className="text-xs">
                                        Dr. {professionals.find((p: Professional) => p.id === evt.professional_id)?.last_name || '...'}
                                    </span>
                                </div>
                                {evt.uiType === 'appointment' && evt.patient_phone && (
                                    <div className="flex items-center gap-1.5 text-white/30">
                                        <Phone size={14} />
                                        <span className="text-xs">{evt.patient_phone}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    ))
                )}

                {/* Spacer for bottom FAB if exists, or just padding */}
                <div className="h-12"></div>
            </div>
        </div>
    );
}
