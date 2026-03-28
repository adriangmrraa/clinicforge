import { useState, useMemo, useEffect, useRef } from 'react';
import DateStrip from './DateStrip';
import type { Appointment, Professional, GoogleCalendarBlock } from '../views/AgendaView';
import { Clock, User, Phone, Lock, CalendarDays, CalendarRange, List, ListOrdered } from 'lucide-react';
import { format, parseISO, startOfWeek, endOfWeek, startOfMonth, endOfMonth, eachDayOfInterval, isWithinInterval, isSameDay, isAfter, addYears } from 'date-fns';
import { es } from 'date-fns/locale';
import { useTranslation } from '../context/LanguageContext';

type ViewMode = 'day' | 'week' | 'month' | 'list';

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
    const [viewMode, setViewMode] = useState<ViewMode>('day');
    const todayRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (viewMode === 'list' && todayRef.current) {
            setTimeout(() => {
                todayRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }, 300);
        }
    }, [viewMode]);

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'confirmed': return 'border-l-green-500';
            case 'cancelled': return 'border-l-red-500';
            case 'completed': return 'border-l-gray-500';
            case 'no-show': return 'border-l-orange-500';
            default: return 'border-l-blue-500';
        }
    };

    const formatTime = (dateStr: string) => {
        return new Date(dateStr).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    };

    // Build unified events
    const allEvents = useMemo(() => {
        return [
            ...appointments.map(apt => ({ ...apt, uiType: 'appointment' as const })),
            ...googleBlocks.map(block => ({ ...block, uiType: 'block' as const }))
        ].sort((a: any, b: any) => {
            const timeA = new Date(a.appointment_datetime || a.start_datetime).getTime();
            const timeB = new Date(b.appointment_datetime || b.start_datetime).getTime();
            return timeA - timeB;
        });
    }, [appointments, googleBlocks]);

    // Filter events based on view mode
    const filteredEvents = useMemo(() => {
        if (viewMode === 'day') {
            return allEvents.filter((evt: any) => {
                const evtDate = parseISO(evt.appointment_datetime || evt.start_datetime);
                return isSameDay(evtDate, selectedDate);
            });
        } else if (viewMode === 'week') {
            const weekStart = startOfWeek(selectedDate, { weekStartsOn: 1 });
            const weekEnd = endOfWeek(selectedDate, { weekStartsOn: 1 });
            return allEvents.filter((evt: any) => {
                const evtDate = parseISO(evt.appointment_datetime || evt.start_datetime);
                return isWithinInterval(evtDate, { start: weekStart, end: weekEnd });
            });
        } else if (viewMode === 'month') {
            const monthStart = startOfMonth(selectedDate);
            const monthEnd = endOfMonth(selectedDate);
            return allEvents.filter((evt: any) => {
                const evtDate = parseISO(evt.appointment_datetime || evt.start_datetime);
                return isWithinInterval(evtDate, { start: monthStart, end: monthEnd });
            });
        } else {
            // LIST view: show ALL events (no date filtering)
            return allEvents;
        }
    }, [allEvents, selectedDate, viewMode]);

    // Group events by date for week/month view
    const groupedEvents = useMemo(() => {
        if (viewMode === 'day') return null;
        const groups: Record<string, any[]> = {};
        filteredEvents.forEach((evt: any) => {
            const dateKey = format(parseISO(evt.appointment_datetime || evt.start_datetime), 'yyyy-MM-dd');
            if (!groups[dateKey]) groups[dateKey] = [];
            groups[dateKey].push(evt);
        });
        return groups;
    }, [filteredEvents, viewMode]);

    // Month calendar grid
    const monthDays = useMemo(() => {
        if (viewMode !== 'month') return [];
        const start = startOfMonth(selectedDate);
        const end = endOfMonth(selectedDate);
        return eachDayOfInterval({ start, end });
    }, [selectedDate, viewMode]);

    // Count events per day for month grid
    const eventCountByDay = useMemo(() => {
        const counts: Record<string, number> = {};
        allEvents.forEach((evt: any) => {
            const dateKey = format(parseISO(evt.appointment_datetime || evt.start_datetime), 'yyyy-MM-dd');
            counts[dateKey] = (counts[dateKey] || 0) + 1;
        });
        return counts;
    }, [allEvents]);

    // List view: all future events from now, grouped by date, up to 3 years
    const listEvents = useMemo(() => {
        if (viewMode !== 'list') return {};
        const now = new Date();
        const limit = addYears(now, 3);
        const future = allEvents.filter((evt: any) => {
            const evtDate = parseISO(evt.appointment_datetime || evt.start_datetime);
            return isAfter(evtDate, now) && !isAfter(evtDate, limit);
        });
        const groups: Record<string, any[]> = {};
        future.forEach((evt: any) => {
            const dateKey = format(parseISO(evt.appointment_datetime || evt.start_datetime), 'yyyy-MM-dd');
            if (!groups[dateKey]) groups[dateKey] = [];
            groups[dateKey].push(evt);
        });
        return groups;
    }, [allEvents, viewMode]);

    const views: { id: ViewMode; icon: any; label: string }[] = [
        { id: 'day', icon: CalendarDays, label: t('agenda.view_day') },
        { id: 'week', icon: CalendarRange, label: t('agenda.view_week') },
        { id: 'month', icon: List, label: t('agenda.view_month') },
        { id: 'list', icon: ListOrdered, label: t('agenda.view_list') },
    ];

    // Render a single event card
    const renderEventCard = (evt: any, compact = false) => (
        <div
            key={evt.id}
            onClick={() => onEventClick({
                event: {
                    start: new Date(evt.appointment_datetime || evt.start_datetime),
                    extendedProps: { ...evt, eventType: evt.uiType === 'block' ? 'gcalendar_block' : 'appointment' }
                }
            })}
            className={`bg-white/[0.03] rounded-xl ${compact ? 'p-3' : 'p-4'} border-l-4 border border-white/[0.06] ${evt.uiType === 'block'
                ? 'border-l-white/20'
                : getStatusColor(evt.status)
                } active:scale-[0.98] hover:bg-white/[0.05] transition-all duration-200 touch-manipulation`}
        >
            <div className="flex justify-between items-start mb-1">
                <div className="flex items-center gap-2">
                    <span className={`${compact ? 'text-sm' : 'text-lg'} font-bold text-white`}>
                        {formatTime(evt.appointment_datetime || evt.start_datetime)}
                    </span>
                    {evt.uiType === 'appointment' && (
                        <span className="text-[10px] font-medium px-1.5 py-0.5 rounded-full bg-white/[0.06] text-white/50">
                            {evt.duration_minutes || 30}m
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-1.5">
                    {/* Payment status dot */}
                    {evt.payment_status === 'paid' && <div className="w-2 h-2 rounded-full bg-emerald-400" />}
                    {evt.payment_status === 'partial' && <div className="w-2 h-2 rounded-full bg-amber-400" />}
                    {evt.payment_status === 'pending' && evt.billing_amount > 0 && <div className="w-2 h-2 rounded-full bg-red-400 animate-pulse" />}
                    <span className="text-[9px] uppercase font-bold tracking-wider px-1.5 py-0.5 rounded bg-white/[0.04] text-white/40">
                        {evt.uiType === 'block' ? 'Bloqueado' : evt.status}
                    </span>
                </div>
            </div>

            <div className="mb-1">
                <h3 className={`${compact ? 'text-sm' : 'text-base'} font-semibold text-white line-clamp-1`}>
                    {evt.uiType === 'block' ? (
                        <span className="flex items-center gap-1.5 text-white/40">
                            <Lock size={12} className="shrink-0" />
                            {evt.title}
                        </span>
                    ) : (
                        evt.patient_name || 'Paciente sin nombre'
                    )}
                </h3>
                {evt.uiType === 'appointment' && !compact && (
                    <p className="text-sm text-white/40 line-clamp-1">{evt.appointment_type}</p>
                )}
            </div>

            {!compact && (
                <div className="flex items-center gap-4 mt-2 pt-2 border-t border-white/[0.04]">
                    <div className="flex items-center gap-1.5 text-white/30">
                        <User size={13} />
                        <span className="text-xs">
                            Dr. {professionals.find((p: Professional) => p.id === evt.professional_id)?.last_name || '...'}
                        </span>
                    </div>
                    {evt.uiType === 'appointment' && evt.patient_phone && (
                        <div className="flex items-center gap-1.5 text-white/30">
                            <Phone size={13} />
                            <span className="text-xs">{evt.patient_phone}</span>
                        </div>
                    )}
                </div>
            )}
        </div>
    );

    return (
        <div className="flex flex-col flex-1 min-h-0">
            {/* View mode toggle */}
            <div className="flex items-center gap-1 px-4 pt-3 pb-2">
                {views.map(v => {
                    const active = viewMode === v.id;
                    const Icon = v.icon;
                    return (
                        <button
                            key={v.id}
                            onClick={() => setViewMode(v.id)}
                            className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all duration-200
                                ${active
                                    ? 'bg-white/[0.08] text-white border border-white/[0.12]'
                                    : 'text-white/40 hover:text-white/60 hover:bg-white/[0.04]'
                                }
                            `}
                        >
                            <Icon size={14} />
                            {v.label}
                        </button>
                    );
                })}
            </div>

            {/* Date Strip — only in day mode */}
            {viewMode === 'day' && (
                <DateStrip selectedDate={selectedDate} onDateSelect={onDateChange} />
            )}

            {/* Week/Month nav */}
            {viewMode !== 'day' && (
                <div className="flex items-center justify-between px-4 py-2">
                    <button
                        onClick={() => {
                            const d = new Date(selectedDate);
                            d.setDate(d.getDate() - (viewMode === 'week' ? 7 : 30));
                            onDateChange(d);
                        }}
                        className="p-2 rounded-lg hover:bg-white/[0.06] text-white/50 transition-colors"
                    >
                        ←
                    </button>
                    <span className="text-sm font-semibold text-white capitalize">
                        {viewMode === 'week'
                            ? `${format(startOfWeek(selectedDate, { weekStartsOn: 1 }), 'd MMM', { locale: es })} — ${format(endOfWeek(selectedDate, { weekStartsOn: 1 }), 'd MMM', { locale: es })}`
                            : format(selectedDate, 'MMMM yyyy', { locale: es })
                        }
                    </span>
                    <button
                        onClick={() => {
                            const d = new Date(selectedDate);
                            d.setDate(d.getDate() + (viewMode === 'week' ? 7 : 30));
                            onDateChange(d);
                        }}
                        className="p-2 rounded-lg hover:bg-white/[0.06] text-white/50 transition-colors"
                    >
                        →
                    </button>
                </div>
            )}

            {/* Content area */}
            <div className="flex-1 overflow-y-auto p-4 pb-24 space-y-3 min-h-0">
                {/* ===== DAY VIEW ===== */}
                {viewMode === 'day' && (
                    filteredEvents.length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-48 text-white/20">
                            <Clock size={48} className="mb-2 opacity-30" />
                            <p className="text-sm text-white/40">{t('agenda.no_appointments_today')}</p>
                        </div>
                    ) : (
                        filteredEvents.map((evt: any) => renderEventCard(evt))
                    )
                )}

                {/* ===== WEEK VIEW ===== */}
                {viewMode === 'week' && (
                    groupedEvents && Object.keys(groupedEvents).length === 0 ? (
                        <div className="flex flex-col items-center justify-center h-48 text-white/20">
                            <CalendarRange size={48} className="mb-2 opacity-30" />
                            <p className="text-sm text-white/40">{t('agenda.no_appointments_week')}</p>
                        </div>
                    ) : (
                        groupedEvents && Object.entries(groupedEvents)
                            .sort(([a], [b]) => a.localeCompare(b))
                            .map(([dateKey, events]) => (
                                <div key={dateKey}>
                                    <div className="flex items-center gap-2 mb-2 mt-1">
                                        <span className="text-xs font-bold text-white/50 uppercase">
                                            {format(parseISO(dateKey), 'EEE d MMM', { locale: es })}
                                        </span>
                                        <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/[0.06] text-white/40 font-semibold">
                                            {events.length}
                                        </span>
                                        <div className="flex-1 h-px bg-white/[0.06]" />
                                    </div>
                                    <div className="space-y-2 mb-4">
                                        {events.map((evt: any) => renderEventCard(evt, true))}
                                    </div>
                                </div>
                            ))
                    )
                )}

                {/* ===== MONTH VIEW ===== */}
                {viewMode === 'month' && (
                    <>
                        {/* Month grid */}
                        <div className="grid grid-cols-7 gap-1 mb-4">
                            {['L', 'M', 'X', 'J', 'V', 'S', 'D'].map(d => (
                                <div key={d} className="text-center text-[10px] font-bold text-white/30 py-1">{d}</div>
                            ))}
                            {/* Padding for first day */}
                            {monthDays.length > 0 && Array.from({ length: (monthDays[0].getDay() + 6) % 7 }).map((_, i) => (
                                <div key={`pad-${i}`} />
                            ))}
                            {monthDays.map(day => {
                                const dateKey = format(day, 'yyyy-MM-dd');
                                const count = eventCountByDay[dateKey] || 0;
                                const isSelected = isSameDay(day, selectedDate);
                                const isToday = isSameDay(day, new Date());
                                return (
                                    <button
                                        key={dateKey}
                                        onClick={() => {
                                            onDateChange(day);
                                            setViewMode('day');
                                        }}
                                        className={`relative flex flex-col items-center py-2 rounded-lg transition-all duration-200 active:scale-90
                                            ${isSelected ? 'bg-blue-600 text-white' : isToday ? 'bg-blue-500/10 text-blue-400' : 'text-white/50 hover:bg-white/[0.06]'}
                                        `}
                                    >
                                        <span className="text-sm font-semibold">{day.getDate()}</span>
                                        {count > 0 && (
                                            <div className="flex gap-0.5 mt-0.5">
                                                {Array.from({ length: Math.min(count, 3) }).map((_, i) => (
                                                    <div key={i} className={`w-1 h-1 rounded-full ${isSelected ? 'bg-white/70' : 'bg-blue-400/60'}`} />
                                                ))}
                                            </div>
                                        )}
                                    </button>
                                );
                            })}
                        </div>

                        {/* Events for selected day below grid */}
                        {(() => {
                            const dayKey = format(selectedDate, 'yyyy-MM-dd');
                            const dayEvents = allEvents.filter((evt: any) => {
                                const evtKey = format(parseISO(evt.appointment_datetime || evt.start_datetime), 'yyyy-MM-dd');
                                return evtKey === dayKey;
                            });
                            return dayEvents.length > 0 ? (
                                <div className="space-y-2">
                                    <div className="text-xs font-bold text-white/50 uppercase mb-2">
                                        {format(selectedDate, 'EEEE d', { locale: es })} — {dayEvents.length} {dayEvents.length === 1 ? 'turno' : 'turnos'}
                                    </div>
                                    {dayEvents.map((evt: any) => renderEventCard(evt, true))}
                                </div>
                            ) : (
                                <div className="text-center py-4 text-white/30 text-sm">
                                    {t('agenda.no_appointments_today')}
                                </div>
                            );
                        })()}
                    </>
                )}

                {/* ===== LIST VIEW ===== */}
                {viewMode === 'list' && (() => {
                    const now = new Date();
                    const limit = addYears(now, 3);
                    // ALL events (past + future) sorted chronologically
                    const allSorted = allEvents
                        .filter((evt: any) => {
                            const evtDate = parseISO(evt.appointment_datetime || evt.start_datetime);
                            return !isAfter(evtDate, limit);
                        })
                        .sort((a: any, b: any) => {
                            const ta = new Date(a.appointment_datetime || a.start_datetime).getTime();
                            const tb = new Date(b.appointment_datetime || b.start_datetime).getTime();
                            return ta - tb;
                        });

                    // Group by date
                    const groups: Record<string, { events: any[]; isPast: boolean }> = {};
                    allSorted.forEach((evt: any) => {
                        const evtDate = parseISO(evt.appointment_datetime || evt.start_datetime);
                        const dateKey = format(evtDate, 'yyyy-MM-dd');
                        if (!groups[dateKey]) {
                            groups[dateKey] = { events: [], isPast: !isAfter(evtDate, now) && !isSameDay(evtDate, now) };
                        }
                        groups[dateKey].events.push(evt);
                    });

                    const sortedKeys = Object.keys(groups).sort();
                    // Find first future date to auto-scroll
                    const todayKey = format(now, 'yyyy-MM-dd');
                    const firstFutureIdx = sortedKeys.findIndex(k => k >= todayKey);

                    if (sortedKeys.length === 0) {
                        return (
                            <div className="flex flex-col items-center justify-center h-48 text-white/20">
                                <ListOrdered size={48} className="mb-2 opacity-30" />
                                <p className="text-sm text-white/40">{t('agenda.no_appointments_week')}</p>
                            </div>
                        );
                    }

                    return sortedKeys.map((dateKey, idx) => {
                        const { events, isPast } = groups[dateKey];
                        const isToday = dateKey === todayKey;
                        return (
                            <div key={dateKey} id={`list-${dateKey}`} ref={isToday ? todayRef : undefined} className={isPast ? 'opacity-50' : ''}>
                                {/* Today marker */}
                                {isToday && idx > 0 && (
                                    <div className="flex items-center gap-2 my-3">
                                        <div className="flex-1 h-px bg-blue-500/30" />
                                        <span className="text-[10px] font-bold text-blue-400 uppercase tracking-wider px-2">Hoy</span>
                                        <div className="flex-1 h-px bg-blue-500/30" />
                                    </div>
                                )}
                                {/* First future marker if no today events */}
                                {!isToday && idx === firstFutureIdx && firstFutureIdx > 0 && (
                                    <div className="flex items-center gap-2 my-3">
                                        <div className="flex-1 h-px bg-green-500/30" />
                                        <span className="text-[10px] font-bold text-green-400 uppercase tracking-wider px-2">{t('agenda.view_list')}</span>
                                        <div className="flex-1 h-px bg-green-500/30" />
                                    </div>
                                )}
                                <div className="flex items-center gap-2 mb-2 mt-1">
                                    <span className={`text-xs font-bold uppercase ${isToday ? 'text-blue-400' : isPast ? 'text-white/30' : 'text-white/50'}`}>
                                        {format(parseISO(dateKey), 'EEE d MMM yyyy', { locale: es })}
                                    </span>
                                    <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-white/[0.06] text-white/40 font-semibold">
                                        {events.length}
                                    </span>
                                    <div className="flex-1 h-px bg-white/[0.06]" />
                                </div>
                                <div className="space-y-2 mb-4">
                                    {events.map((evt: any) => renderEventCard(evt, true))}
                                </div>
                            </div>
                        );
                    });
                })()}

                <div className="h-12" />
            </div>
        </div>
    );
}
