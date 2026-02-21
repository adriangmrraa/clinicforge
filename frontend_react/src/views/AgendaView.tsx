import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';
import timeGridPlugin from '@fullcalendar/timegrid';
import listPlugin from '@fullcalendar/list';
import resourceTimeGridPlugin from '@fullcalendar/resource-timegrid';
import AppointmentForm from '../components/AppointmentForm';
import MobileAgenda from '../components/MobileAgenda';
import { RefreshCw, Stethoscope } from 'lucide-react';
import AppointmentCard from '../components/AppointmentCard';
import api from '../api/axios';
import { addDays, subDays, startOfDay, endOfDay } from 'date-fns';
import { io, Socket } from 'socket.io-client';
import { BACKEND_URL } from '../api/axios';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../context/LanguageContext';

// ==================== TYPE DEFINITIONS ====================
export interface Appointment {
  id: string;
  patient_id: number;
  professional_id: number;
  appointment_datetime: string;
  end_datetime?: string;
  duration_minutes?: number;
  status: string;
  urgency_level?: string;
  source?: string;
  appointment_type: string;
  notes?: string;
  patient_name?: string;
  patient_phone?: string;
  professional_name?: string;
}

export interface GoogleCalendarBlock {
  id: string;
  google_event_id: string;
  title: string;
  description?: string;
  start_datetime: string;
  end_datetime: string;
  all_day?: boolean;
  professional_id?: number;
  sync_status?: string;
}

export interface Professional {
  id: number;
  first_name: string;
  last_name?: string;
  name?: string;
  email?: string;
  is_active: boolean;
}

export interface Patient {
  id: number;
  first_name: string;
  last_name: string;
  phone_number: string;
}

// ==================== SOURCE COLORS ====================
// Colors for appointment sources: AI (blue), Manual (green), GCalendar (gray)
const SOURCE_COLORS: Record<string, { hex: string; label: string; bgClass: string; textClass: string }> = {
  ai: {
    hex: '#3b82f6',
    label: 'AI',
    bgClass: 'bg-blue-100',
    textClass: 'text-blue-800'
  },
  manual: {
    hex: '#22c55e',
    label: 'Manual',
    bgClass: 'bg-green-100',
    textClass: 'text-green-800'
  },
  gcalendar: {
    hex: '#6b7280',
    label: 'GCalendar',
    bgClass: 'bg-gray-100',
    textClass: 'text-gray-800'
  },
};

// Mapeo de IDs de appointment_statuses a colores hexadecimales
// 1: scheduled, 2: confirmed, 3: in_progress, 4: completed, 5: cancelled, 6: no_show
const STATUS_COLORS: Record<number, { hex: string; label: string }> = {
  1: { hex: '#3b82f6', label: 'scheduled' },   // azul - Programado
  2: { hex: '#22c55e', label: 'confirmed' },   // verde - Confirmado
  3: { hex: '#eab308', label: 'in_progress' }, // amarillo - En progreso
  4: { hex: '#6b7280', label: 'completed' },   // gris - Completado
  5: { hex: '#ef4444', label: 'cancelled' },   // rojo - Cancelado
  6: { hex: '#f97316', label: 'no_show' },     // naranja - No asistido
};



// Get color based on appointment source (AI vs Manual)
const getSourceColor = (source: string | undefined): string => {
  if (!source) return SOURCE_COLORS.ai.hex; // Default to AI if no source
  return SOURCE_COLORS[source]?.hex || SOURCE_COLORS.ai.hex;
};




// Get source label (translated when t is provided)
const getSourceLabel = (source: string | undefined, t?: (k: string) => string): string => {
  if (t) {
    if (!source) return t('agenda.source_ai');
    const key = 'agenda.source_' + source;
    return (source === 'ai' || source === 'manual' || source === 'gcalendar') ? t(key) : source.toUpperCase();
  }
  if (!source) return 'AI';
  return SOURCE_COLORS[source]?.label || source.toUpperCase();
};




export default function AgendaView() {
  const { user } = useAuth();
  const { t, language } = useTranslation();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [googleBlocks, setGoogleBlocks] = useState<GoogleCalendarBlock[]>([]);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<Appointment | null>(null);
  const [selectedProfessionalId, setSelectedProfessionalId] = useState<string>('all');
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [currentView] = useState(window.innerWidth >= 1024 ? 'timeGridWeek' : (window.innerWidth >= 768 ? 'resourceTimeGridDay' : 'timeGridDay'));

  // Mobile Detection
  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const calendarRef = useRef<FullCalendar>(null);
  const socketRef = useRef<Socket | null>(null);
  const eventsRef = useRef<Appointment[]>([]);
  const [isBackgroundSyncing, setIsBackgroundSyncing] = useState(false);
  // Debounce para datesSet: evita fetches duplicados en renders rápidos del calendario
  const datesSetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Flag para evitar fetches concurrentes desde datesSet mientras ya hay uno en curso
  const isFetchingRef = useRef(false);

  const [formData, setFormData] = useState({
    patient_id: '',
    professional_id: '',
    appointment_datetime: '',
    appointment_type: 'checkup',
    notes: '',
  });

  // Fetch Google Calendar blocks
  const fetchGoogleBlocks = useCallback(async (startDate: string, endDate: string, professionalId?: string) => {
    try {
      const params: any = { start_date: startDate, end_date: endDate };
      if (professionalId && professionalId !== 'all') {
        params.professional_id = professionalId;
      }
      const response = await api.get('/admin/calendar/blocks', { params });
      return response.data;
    } catch (error) {
      console.error('Error fetching Google Calendar blocks:', error);
      return [];
    }
  }, []);



  // Mobile Detection only
  useEffect(() => {
    const handleResize = () => {
      if (calendarRef.current) {
        const calendarApi = calendarRef.current.getApi();
        if (window.innerWidth < 768) {
          if (calendarApi.view.type !== 'listDay') {
            calendarApi.changeView('listDay');
          }
        } else {
          if (calendarApi.view.type === 'listDay') {
            calendarApi.changeView('timeGridWeek');
          }
        }
      }
    };

    // Initial check
    handleResize();
    window.addEventListener('resize', handleResize);

    return () => window.removeEventListener('resize', handleResize);
  }, []); // Run once on mount




  // Fetch clinic settings
  const fetchClinicSettings = useCallback(async () => {
    try {
      await api.get('/admin/settings/clinic');
      // Values are now hardcoded in the calendar view per FIX 1
    } catch (error) {
      console.error('Error fetching clinic settings:', error);
    }
  }, []);

  // Fetch all data
  // explicitStart/explicitEnd: fechas pasadas directamente desde datesSet para evitar leer
  // calendarRef en el momento incorrecto (puede tener la vista anterior).
  const fetchData = useCallback(async (
    isBackground: boolean = false,
    explicitStart?: Date,
    explicitEnd?: Date
  ) => {
    try {
      if (!isBackground) setLoading(true);
      else setIsBackgroundSyncing(true);

      // Fetch settings first if needed or concurrently
      fetchClinicSettings();

      // Prioridad: fechas explícitas → calendarRef → fallback mobile
      let startDate: Date;
      let endDate: Date;

      if (explicitStart && explicitEnd) {
        startDate = explicitStart;
        endDate = explicitEnd;
      } else if (calendarRef.current) {
        const calendarApi = calendarRef.current.getApi();
        startDate = calendarApi.view.activeStart;
        endDate = calendarApi.view.activeEnd;
      } else {
        // Fallback for mobile view where FullCalendar is unmounted
        const baseDate = selectedDate || new Date();
        startDate = startOfDay(subDays(baseDate, 7));
        endDate = endOfDay(addDays(baseDate, 7));
      }

      const startDateStr = startDate.toISOString();
      const endDateStr = endDate.toISOString();

      // Fetch professionals first to resolve filter (CEO: selectedProfessionalId; professional: only their id)
      const [professionalsRes, patientsRes] = await Promise.all([
        api.get('/admin/professionals'),
        api.get('/admin/patients'),
      ]);
      const fetchedProfessionals = professionalsRes.data.filter((p: Professional) => p.is_active);
      setProfessionals(fetchedProfessionals);
      setPatients(patientsRes.data);

      const profFilter = user?.role === 'professional'
        ? fetchedProfessionals.find((p: Professional) => p.email === user.email)?.id?.toString() || 'all'
        : selectedProfessionalId;

      const params: any = { start_date: startDateStr, end_date: endDateStr };
      if (profFilter !== 'all') {
        params.professional_id = profFilter;
      }

      const [appointmentsRes, blocksRes] = await Promise.all([
        api.get('/admin/appointments', { params }),
        fetchGoogleBlocks(startDateStr, endDateStr, profFilter),
      ]);

      const newAppointments = appointmentsRes.data;
      setAppointments(newAppointments);
      eventsRef.current = newAppointments;
      setGoogleBlocks(blocksRes || []);
      // Los eventos se pasan via prop `events={calendarEvents}` — no manipular el calendario directamente
      // para evitar el loop datesSet → fetchData → re-render → datesSet
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      if (!isBackground) setLoading(false);
      else setIsBackgroundSyncing(false);
      isFetchingRef.current = false;
    }
  }, [fetchGoogleBlocks, selectedProfessionalId, user?.role, user?.email]);

  // Setup WebSocket connection and listeners
  useEffect(() => {
    const initializeAgenda = async () => {
      // 1. First, run auto-sync if user has permissions
      if (user?.role === 'ceo' || user?.role === 'secretary' || user?.role === 'professional') {
        try {
          await api.post('/admin/calendar/sync');
          // Delay to ensure backend DB write completes
          await new Promise(resolve => setTimeout(resolve, 800));
        } catch (error) {
          // Continue with data fetch even if sync fails
        }
      }

      // 2. Now fetch all data (includes synced GCal blocks)
      await fetchData();
    };

    initializeAgenda();

    // Setup WebSocket connection
    socketRef.current = io(BACKEND_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
    });

    // Connection status handlers
    socketRef.current.on('connect', () => {
    });

    socketRef.current.on('disconnect', () => {
    });

    socketRef.current.on('connect_error', () => {
    });

    // Listen for NEW_APPOINTMENT events - Real-time omnipresent sync
    socketRef.current.on('NEW_APPOINTMENT', () => {

      // Trigger complete re-fetch from sources (DB + GCal blocks)
      fetchData(true);
    });

    // Listen for APPOINTMENT_UPDATED events - Real-time updates
    socketRef.current.on('APPOINTMENT_UPDATED', () => {

      // Trigger complete re-fetch for consistency
      fetchData(true);
    });

    // Listen for APPOINTMENT_DELETED events
    socketRef.current.on('APPOINTMENT_DELETED', (deletedAppointmentId: string) => {

      setAppointments(prevAppointments => {
        const updated = prevAppointments.filter(apt => apt.id !== deletedAppointmentId);
        eventsRef.current = updated;
        return updated;
      });


      // Remove event from calendar
      if (calendarRef.current) {
        const calendarApi = calendarRef.current.getApi();
        const existingEvent = calendarApi.getEventById(deletedAppointmentId);
        if (existingEvent) {
          existingEvent.remove();
        }
      }
    });

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
      }
      if (datesSetTimerRef.current) clearTimeout(datesSetTimerRef.current);
    };
  }, [fetchData]);

  // FIX 2: Memoized filtered appointments and blocks
  const filteredAppointments = useMemo(() => {
    if (!selectedProfessionalId || selectedProfessionalId === 'all') return appointments;
    return appointments.filter((apt: Appointment) => apt.professional_id.toString() === selectedProfessionalId);
  }, [appointments, selectedProfessionalId]);

  const filteredBlocks = useMemo(() => {
    if (!selectedProfessionalId || selectedProfessionalId === 'all') return googleBlocks;
    return googleBlocks.filter((block: GoogleCalendarBlock) => block.professional_id?.toString() === selectedProfessionalId);
  }, [googleBlocks, selectedProfessionalId]);

  // Professional user: lock filter to their id once we have professionals
  useEffect(() => {
    if (user?.role === 'professional' && user?.email && professionals.length > 0) {
      const myId = professionals.find((p: Professional) => p.email === user.email)?.id?.toString();
      if (myId && selectedProfessionalId !== myId) {
        setSelectedProfessionalId(myId);
      }
    }
  }, [user?.role, user?.email, professionals]);

  // Refetch when professional filter changes (CEO/secretary change dropdown)
  useEffect(() => {
    fetchData();
  }, [selectedProfessionalId]);

  // FIX: Refetch on mobile when selectedDate changes to ensure data is available
  useEffect(() => {
    if (isMobile && selectedDate) {
      fetchData(true); // Background fetch to avoid flickering
    }
  }, [selectedDate, isMobile]);

  // Calendar events transformer
  const calendarEvents = [
    ...filteredAppointments.map((apt) => ({
      id: apt.id,
      title: `${apt.patient_name} - ${apt.appointment_type}`,
      start: apt.appointment_datetime,
      end: apt.end_datetime || undefined,
      backgroundColor: getSourceColor(apt.source),
      borderColor: getSourceColor(apt.source),
      extendedProps: { ...apt, eventType: 'appointment' },
      resourceId: apt.professional_id.toString(),
    })),
    ...filteredBlocks.map((block) => ({
      id: block.id,
      title: `🔒 ${block.title}`,
      start: block.start_datetime,
      end: block.end_datetime,
      allDay: block.all_day || false,
      backgroundColor: SOURCE_COLORS.gcalendar.hex,
      borderColor: SOURCE_COLORS.gcalendar.hex,
      extendedProps: { ...block, eventType: 'gcalendar_block' },
      resourceId: block.professional_id?.toString() || undefined,
    })),
  ];

  // Map professionals to resources (professional user: only their column)
  const resources = useMemo(() => {
    const list = user?.role === 'professional' && user?.email
      ? professionals.filter((p: Professional) => p.email === user.email)
      : professionals;
    return list.map((p: Professional) => ({
      id: p.id.toString(),
      title: `Dr. ${p.first_name} ${p.last_name || ''}`,
      eventColor: '#3b82f6',
    }));
  }, [professionals, user?.role, user?.email]);

  const handleDateClick = (info: { date: Date }) => {
    // Prevenir agendamiento en fechas/horas pasadas
    const now = new Date();
    if (info.date < now) {
      alert('⚠️ ' + t('agenda.alert_past_date'));
      return;
    }

    // Para datetime-local input, necesitamos YYYY-MM-DDTHH:mm en hora LOCAL
    const localDate = new Date(info.date.getTime() - info.date.getTimezoneOffset() * 60000);
    const localIso = localDate.toISOString().slice(0, 16);

    setSelectedDate(info.date);
    setSelectedEvent(null);
    setFormData({
      patient_id: '',
      professional_id: professionals[0]?.id?.toString() || '',
      appointment_datetime: localIso,
      appointment_type: 'checkup',
      notes: '',
    });
    setShowModal(true);
  };

  const handleEventClick = (info: any) => {
    // Check if it's a Google Calendar block
    if (info.event.extendedProps.eventType === 'gcalendar_block') {
      alert(`Bloqueo de Google Calendar:\n\n${info.event.title}\n${new Date(info.event.start).toLocaleString()} - ${new Date(info.event.end).toLocaleString()}`);
      return;
    }

    setSelectedEvent(info.event.extendedProps);
    setSelectedDate(info.event.start);
    setShowModal(true);
  };

  const handleSave = async (data: any) => {
    try {
      if (selectedEvent) {
        // Update
        await api.put(`/admin/appointments/${selectedEvent.id}`, data);
      } else {
        // Create
        await api.post('/admin/appointments', {
          ...data,
          status: 'confirmed',
          source: 'manual',
        });
      }
      await fetchData();
      setShowModal(false);
    } catch (error: any) {
      throw error; // Propagate to form for error display
    }
  };

  const handleDelete = async (id: string) => {
    try {
      // Soft delete/cancel
      await api.put(`/admin/appointments/${id}/status`, { status: 'cancelled' });
      await fetchData();
      setShowModal(false);
    } catch (error) {
      alert(t('agenda.alert_cancel_error'));
    }
  };

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-transparent">
      {/* Header - Fixed, non-scrollable */}
      <div className="flex-shrink-0 px-4 lg:px-6 pt-4 lg:pt-6">
        {/* Header */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 mb-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center w-full lg:w-auto gap-4">
            <div className="border-l-4 border-medical-500 pl-3 sm:pl-4 min-w-0">
              <h1 className="text-xl sm:text-2xl font-bold text-slate-800 tracking-tight">{t('agenda.title')}</h1>
              <p className="text-xs sm:text-sm text-slate-600 mt-0.5">{t('agenda.subtitle')}</p>
            </div>

            {/* Professional Filter (CEO/Secretary only) - Mobile Stacking */}
            {(user?.role === 'ceo' || user?.role === 'secretary') && (
              <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-xl shadow-sm border border-gray-100 w-full sm:w-auto">
                <Stethoscope size={16} className="text-medical-600 shrink-0" />
                <select
                  value={selectedProfessionalId}
                  onChange={(e) => setSelectedProfessionalId(e.target.value)}
                  className="bg-transparent border-none text-xs font-medium focus:ring-0 outline-none text-medical-900 cursor-pointer w-full"
                >
                  <option value="all">{t('agenda.all_professionals')}</option>
                  {professionals.map(p => (
                    <option key={p.id} value={p.id.toString()}>
                      Dr. {p.first_name} {p.last_name || ''}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Connection Status & Controls */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-4 w-full lg:w-auto">
            {/* Source Legend - Compact on Mobile */}
            <div className="flex gap-2 sm:gap-3 bg-white px-3 py-1.5 rounded-full border border-gray-50">
              <div className="flex items-center gap-1">
                <div className="w-2.5 h-2.5 rounded-full bg-blue-500"></div>
                <span className="text-[10px] text-gray-600">{t('agenda.source_ai')}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2.5 h-2.5 rounded-full bg-green-500"></div>
                <span className="text-[10px] text-gray-600">{t('agenda.source_manual')}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2.5 h-2.5 rounded-full bg-gray-500"></div>
                <span className="text-[10px] text-gray-600">{t('agenda.source_gcalendar')}</span>
              </div>
            </div>

            <div className="flex items-center gap-2 ml-auto lg:ml-0">
              {/* Pulse Indicator */}
              {isBackgroundSyncing && (
                <div className="flex items-center justify-center w-8 h-8">
                  <RefreshCw size={16} className="text-blue-500 animate-spin opacity-60" />
                </div>
              )}
            </div>

            {/* Pulse Indicator */}

          </div>
        </div>

        {/* Mobile View or Desktop Calendar */}
        {isMobile ? (
          <div className="flex-1 min-h-0">
            <MobileAgenda
              appointments={filteredAppointments}
              googleBlocks={filteredBlocks}
              selectedDate={selectedDate || new Date()}
              onDateChange={(date) => {
                setSelectedDate(date);
                // Sync calendar ref if it ever gets remounted or for consistency
                if (calendarRef.current) calendarRef.current.getApi().gotoDate(date);
              }}
              onEventClick={handleEventClick}
              professionals={professionals}
            />
          </div>
        ) : (
          <div className="flex-1 min-h-0 px-4 lg:px-6 pb-4 lg:pb-6 overflow-hidden">
            <div className="h-[calc(100vh-180px)] bg-white/60 backdrop-blur-lg md:backdrop-blur-2xl border border-white/40 shadow-2xl rounded-2xl md:rounded-3xl p-2 sm:p-4 overflow-y-auto">
              {/* Calendar */}

              {/* Custom FullCalendar Styles for Spacious TimeGrid */}
              <style>{`
          /* Aumentar altura de slots de tiempo en vista semanal/diaria */
          .fc-timegrid-slot {
            height: 70px !important;
            min-height: 70px !important;
          }
          
          /* Hacer eventos más visibles y tipo tarjeta */
          .fc-timegrid-event {
            border-radius: 8px !important;
            padding: 6px !important;
            min-height: 60px !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1) !important;
          }
          
          /* Aumentar espacio entre eventos */
          .fc-timegrid-event-harness {
            margin: 2px 4px !important;
          }
          
          /* Mejorar la visualización del label de hora */
          .fc-timegrid-slot-label {
            font-size: 14px !important;
            font-weight: 600 !important;
            padding: 8px !important;
          }
          
          /* Opacar días pasados visualmente */
          .fc-day-past {
            background-color: #f9fafb !important;
            opacity: 0.5 !important;
          }
          
          .fc-timegrid-col.fc-day-past {
            background-color: #f9fafb !important;
          }
          
          .fc-event-past {
            opacity: 0.7 !important;
            filter: grayscale(0.5);
          }
          
          /* Indicador de tiempo actual más visible */
          .fc-now-indicator-line {
            border-color: #ef4444 !important;
            border-width: 2px !important;
            z-index: 10 !important;
          }
          
          .fc-now-indicator-line::before {
            content: '';
            position: absolute;
            left: 0;
            top: -4px;
            width: 10px;
            height: 10px;
            background: #ef4444;
            border-radius: 50%;
            box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
          }

          /* Glowing indicator arrow */
          .fc-now-indicator-arrow {
            margin-top: -6px !important;
            border-width: 6px 0 6px 8px !important;
            border-color: transparent transparent transparent #ef4444 !important;
            filter: drop-shadow(0 0 4px rgba(239, 68, 68, 0.8));
          }
          /* Glowing dot on axis */
          .fc-now-indicator-arrow::after {
            content: '';
            position: absolute;
            top: -4px;
            left: -12px;
            width: 8px;
            height: 8px;
            background-color: #ef4444;
            border-radius: 50%;
            box-shadow: 0 0 10px #ef4444;
            animation: pulse-red 2s infinite;
          }

          @keyframes pulse-red {
            0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
            100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
          }
        `}</style>

              {loading && appointments.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <div className="flex flex-col items-center gap-4">
                    <RefreshCw className="w-12 h-12 text-blue-500 animate-spin" />
                    <p className="text-gray-500 font-medium">{t('common.loading')}</p>
                  </div>
                </div>
              ) : (
                <FullCalendar
                  ref={calendarRef}
                  plugins={[dayGridPlugin, interactionPlugin, timeGridPlugin, resourceTimeGridPlugin, listPlugin]}
                  schedulerLicenseKey="GPL-My-Project-Is-Open-Source"
                  initialView={currentView}
                  resources={resources}
                  editable={true}
                  selectable={true}
                  selectMirror={true}
                  dayMaxEvents={true}
                  weekends={true}
                  nowIndicator={true}
                  slotDuration="00:15:00"
                  slotLabelInterval="01:00"
                  initialDate={new Date()}
                  headerToolbar={{
                    left: window.innerWidth < 768 ? 'prev,next' : 'prev,next today',
                    center: 'title',
                    right: window.innerWidth < 768
                      ? 'timeGridDay,dayGridMonth'
                      : (window.innerWidth < 1024 ? 'timeGridWeek,dayGridMonth' : 'resourceTimeGridDay,timeGridWeek,dayGridMonth'),
                  }}
                  height="100%"
                  selectAllow={(selectInfo) => {
                    const now = new Date();
                    return selectInfo.start >= now;
                  }}
                  events={calendarEvents}
                  datesSet={(dateInfo) => {
                    // Debounce: esperar 150ms antes de hacer fetch para evitar llamadas
                    // duplicadas cuando FullCalendar re-renderiza internamente al recibir eventos.
                    // Las fechas se pasan explícitamente para evitar leer calendarRef desactualizado.
                    if (datesSetTimerRef.current) clearTimeout(datesSetTimerRef.current);
                    datesSetTimerRef.current = setTimeout(() => {
                      if (!isFetchingRef.current) {
                        isFetchingRef.current = true;
                        fetchData(false, dateInfo.start, dateInfo.end);
                      }
                    }, 150);
                  }}
                  dateClick={handleDateClick}
                  eventClick={handleEventClick}
                  slotEventOverlap={false}
                  slotMinTime="08:00:00"
                  slotMaxTime="20:00:00"
                  locale={language}
                  buttonText={{
                    today: t('agenda.today'),
                    month: t('agenda.month'),
                    week: t('agenda.week'),
                    day: t('agenda.day'),
                    list: t('agenda.title')
                  }}
                  allDayText={t('agenda.all_day')}
                  eventContent={(eventInfo) => <AppointmentCard {...eventInfo} />}
                  eventDidMount={(info) => {
                    const { eventType, source, patient_phone, professional_name, notes } = info.event.extendedProps;

                    if (eventType === 'gcalendar_block') {
                      const startDate = info.event.start;
                      if (startDate) {
                        info.el.title = `🔒 ${info.event.title}\n${startDate.toLocaleString()}`;
                      }
                    } else {
                      const tooltipContent = `
                ${info.event.title}
                ${source ? `\n📍 ${t('agenda.origin')}: ${getSourceLabel(source, t)}` : ''}
                ${patient_phone ? `\n📞 ${patient_phone}` : ''}
                ${professional_name ? `\n👨‍⚕️ Dr. ${professional_name}` : ''}
                ${notes ? `\n📝 ${notes}` : ''}
              `.trim();
                      info.el.title = tooltipContent;
                    }
                  }}
                />
              )}
            </div>
          </div>
        )}

        {/* Clinical Inspector Drawer */}
        <AppointmentForm
          isOpen={showModal}
          onClose={() => setShowModal(false)}
          initialData={selectedEvent || {
            patient_id: parseInt(formData.patient_id || '0'),
            professional_id: parseInt(formData.professional_id || '0'),
            appointment_datetime: formData.appointment_datetime,
            appointment_type: formData.appointment_type,
            notes: formData.notes,
            duration_minutes: 30
          }}
          professionals={professionals}
          patients={patients}
          onSubmit={handleSave}
          onDelete={handleDelete}
          isEditing={!!selectedEvent}
        />
      </div>
    </div>
  );
}
