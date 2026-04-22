import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useLocation } from 'react-router-dom';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';
import timeGridPlugin from '@fullcalendar/timegrid';
import listPlugin from '@fullcalendar/list';
import resourceTimeGridPlugin from '@fullcalendar/resource-timegrid';
import AppointmentForm from '../components/AppointmentForm';
import MobileAgenda from '../components/MobileAgenda';
import HolidayDetailModal from '../components/HolidayDetailModal';
import { RefreshCw, Stethoscope, Download, FileText, Image, Loader2, Printer } from 'lucide-react';
import AppointmentCard from '../components/AppointmentCard';
import api from '../api/axios';
import { addDays, subDays, startOfDay, endOfDay } from 'date-fns';
import { getSocket } from '../services/socket';
import type { Socket } from 'socket.io-client';
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
  appointment_name?: string;
  patient_source?: string;
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

export interface Holiday {
  id?: string;
  date: string;
  name: string;
  holiday_type?: string;
  is_recurring?: boolean;
  country_code?: string;
  custom_hours_start?: string | null;
  custom_hours_end?: string | null;
  custom_hours?: { start: string; end: string } | null;
}

// ==================== SOURCE COLORS ====================
// Colors for appointment sources: AI/Ventas IA (blue), Manual (green), Nova (purple), GCalendar (gray)
const SOURCE_COLORS: Record<string, { hex: string; label: string; bgClass: string; textClass: string }> = {
  ai: {
    hex: '#3b82f6',
    label: 'Ventas IA',
    bgClass: 'bg-blue-500/10',
    textClass: 'text-blue-400'
  },
  nova: {
    hex: '#a855f7',
    label: 'Nova',
    bgClass: 'bg-purple-500/10',
    textClass: 'text-purple-400'
  },
  manual: {
    hex: '#22c55e',
    label: 'Manual',
    bgClass: 'bg-green-500/10',
    textClass: 'text-green-400'
  },
  gcalendar: {
    hex: '#6b7280',
    label: 'GCalendar',
    bgClass: 'bg-white/[0.06]',
    textClass: 'text-white/50'
  },
};

// STATUS_COLORS removed as it was unused



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
    return (source === 'ai' || source === 'nova' || source === 'manual' || source === 'gcalendar') ? t(key) : source.toUpperCase();
  }
  if (!source) return 'AI';
  return SOURCE_COLORS[source]?.label || source.toUpperCase();
};




export default function AgendaView() {
  const { user } = useAuth();
  const { t, language } = useTranslation();
  const location = useLocation();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [googleBlocks, setGoogleBlocks] = useState<GoogleCalendarBlock[]>([]);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [professionals, setProfessionals] = useState<Professional[]>([]);
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<Appointment | null>(null);
  const [selectedHoliday, setSelectedHoliday] = useState<Holiday | null>(null);
  // Keep selectedEvent in sync when appointments reload (e.g., after PAYMENT_CONFIRMED socket event)
  useEffect(() => {
    if (selectedEvent && appointments.length > 0) {
      const fresh = appointments.find((a: Appointment) => a.id === selectedEvent.id);
      if (fresh && JSON.stringify(fresh) !== JSON.stringify(selectedEvent)) {
        setSelectedEvent(fresh);
      }
    }
  }, [appointments]);
  const [selectedProfessionalId, setSelectedProfessionalId] = useState<string>(() => {
    if (user?.role === 'professional' && user?.professional_id) {
      return user.professional_id.toString();
    }
    return 'all';
  });
  const [isMobile, setIsMobile] = useState(window.innerWidth < 768);
  const [currentView, setCurrentView] = useState(() => {
    // Intentar recuperar vista guardada, sino usar responsive default
    const savedView = localStorage.getItem('agendaView');
    if (savedView) return savedView;
    return window.innerWidth >= 1024 ? 'timeGridWeek' : (window.innerWidth >= 768 ? 'resourceTimeGridDay' : 'timeGridDay');
  });
  const [showExportMenu, setShowExportMenu] = useState(false);
  const [exporting, setExporting] = useState(false);

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
  // Debounce para datesSet
  const datesSetTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Guardián de rango: solo hace fetch si el rango de fechas, vista o filtro de profesional cambió realmente
  const lastFetchedRangeRef = useRef<{ startISO: string; endISO: string; professionalId: string; viewType?: string } | null>(null);
  // Ref estable a fetchData para usarlo en socket handlers sin re-suscribir en cada cambio
  const fetchDataRef = useRef<typeof fetchData | null>(null);
  // Guard para saltar el efecto de filtro en el primer render (el init ya hace el fetch)
  const filterInitialRenderRef = useRef(true);
  // Rango visible actual (para indicador de UI)
  const [visibleRangeStr, setVisibleRangeStr] = useState<string>('');
  // AbortController para cancelar requests en vuelo al navegar rápido entre meses/vistas
  const fetchAbortControllerRef = useRef<AbortController | null>(null);
  // Cache de datos estáticos entre cambios de vista (se invalidan por TTL o por eventos socket)
  const CACHE_TTL = 5 * 60 * 1000; // 5 minutos
  const HOLIDAYS_CACHE_TTL = 24 * 60 * 60 * 1000; // 24 horas
  const professionalsCache = useRef<{ data: any[]; fetchedAt: number }>({ data: [], fetchedAt: 0 });
  const patientsCache = useRef<{ data: any[]; fetchedAt: number }>({ data: [], fetchedAt: 0 });
  const holidaysCache = useRef<{ data: any[]; fetchedAt: number }>({ data: [], fetchedAt: 0 });

  const [formData, setFormData] = useState({
    patient_id: '',
    professional_id: '',
    appointment_datetime: '',
    appointment_type: 'checkup',
    notes: '',
  });

  // Fetch Google Calendar blocks
  const fetchGoogleBlocks = useCallback(async (startDate: string, endDate: string, professionalId?: string | null, signal?: AbortSignal) => {
    try {
      const params: any = { start_date: startDate, end_date: endDate };
      if (professionalId && professionalId !== 'all') {
        params.professional_id = professionalId;
      }
      const response = await api.get('/admin/calendar/blocks', { params, signal });
      return response.data;
    } catch (error: any) {
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return [];
      console.error('Error fetching Google Calendar blocks:', error);
      return [];
    }
  }, []);



  // handleViewChange removed as it was unused

  // Mobile Detection only
  useEffect(() => {
    const handleResize = () => {
      if (calendarRef.current) {
        const calendarApi = calendarRef.current.getApi();
        if (window.innerWidth < 768) {
          if (calendarApi.view.type !== 'listDay') {
            calendarApi.changeView('listDay');
            setCurrentView('listDay');
            localStorage.setItem('agendaView', 'listDay');
          }
        } else {
          if (calendarApi.view.type === 'listDay') {
            const defaultView = window.innerWidth >= 1024 ? 'timeGridWeek' : (window.innerWidth >= 768 ? 'resourceTimeGridDay' : 'timeGridDay');
            calendarApi.changeView(defaultView);
            setCurrentView(defaultView);
            localStorage.setItem('agendaView', defaultView);
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
    // Cancelar cualquier fetch en vuelo antes de iniciar uno nuevo.
    // Esto evita la race condition donde navegar rápido entre meses/vistas deja
    // el spinner colgado o sobreescribe datos correctos con datos de un rango viejo.
    if (fetchAbortControllerRef.current) {
      fetchAbortControllerRef.current.abort();
    }
    const abortController = new AbortController();
    fetchAbortControllerRef.current = abortController;

    try {
      if (!isBackground) setLoading(true);
      else setIsBackgroundSyncing(true);

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
        // Fallback: rango amplio cuando el calendario aún no está montado (p. ej. init)
        const baseDate = selectedDate || new Date();
        startDate = startOfDay(subDays(baseDate, 60));
        endDate = endOfDay(addDays(baseDate, 90));
      }

      const startDateStr = startDate.toISOString();
      const endDateStr = endDate.toISOString();

      // Fetch professionals and patients con cache TTL — no cambian entre cambios de vista
      const now = Date.now();
      let fetchedProfessionals: any[];
      let fetchedPatients: any[];

      if (now - professionalsCache.current.fetchedAt > CACHE_TTL || now - patientsCache.current.fetchedAt > CACHE_TTL) {
        const [professionalsRes, patientsRes] = await Promise.all([
          api.get('/admin/professionals'),
          api.get('/admin/patients'),
        ]);
        fetchedProfessionals = professionalsRes.data.filter((p: Professional) => p.is_active);
        fetchedPatients = patientsRes.data;
        professionalsCache.current = { data: fetchedProfessionals, fetchedAt: now };
        patientsCache.current = { data: fetchedPatients, fetchedAt: now };
      } else {
        fetchedProfessionals = professionalsCache.current.data;
        fetchedPatients = patientsCache.current.data;
      }
      setProfessionals(fetchedProfessionals);
      setPatients(fetchedPatients);

      const profFilter = user?.role === 'professional'
        ? user?.professional_id?.toString() ?? null
        : selectedProfessionalId;

      // Guard: if professional user has no professional_id, abort to prevent leaking all appointments
      if (user?.role === 'professional' && !profFilter) {
        console.warn('Professional user without professional_id — aborting fetch');
        if (!isBackground) setLoading(false);
        else setIsBackgroundSyncing(false);
        return;
      }

      const params: any = { start_date: startDateStr, end_date: endDateStr };
      if (profFilter && profFilter !== 'all') {
        params.professional_id = profFilter;
      }

      // Holidays con cache de 24h — los feriados raramente cambian entre vistas
      let fetchedHolidays: any[];
      if (now - holidaysCache.current.fetchedAt > HOLIDAYS_CACHE_TTL) {
        const [appointmentsRes, blocksRes, holidaysRes] = await Promise.all([
          api.get('/admin/appointments', { params, signal: abortController.signal }),
          fetchGoogleBlocks(startDateStr, endDateStr, profFilter, abortController.signal),
          api.get('/admin/holidays', { params: { days: 365 }, signal: abortController.signal }),
        ]);

        // Si fue abortado entre el disparo y la resolución, no actualizar el estado
        if (abortController.signal.aborted) return;

        fetchedHolidays = holidaysRes.data?.upcoming || [];
        holidaysCache.current = { data: fetchedHolidays, fetchedAt: now };

        const newAppointments = appointmentsRes.data;
        setAppointments(newAppointments);
        eventsRef.current = newAppointments;
        setGoogleBlocks(blocksRes || []);
      } else {
        fetchedHolidays = holidaysCache.current.data;

        const [appointmentsRes, blocksRes] = await Promise.all([
          api.get('/admin/appointments', { params, signal: abortController.signal }),
          fetchGoogleBlocks(startDateStr, endDateStr, profFilter, abortController.signal),
        ]);

        // Si fue abortado entre el disparo y la resolución, no actualizar el estado
        if (abortController.signal.aborted) return;

        const newAppointments = appointmentsRes.data;
        setAppointments(newAppointments);
        eventsRef.current = newAppointments;
        setGoogleBlocks(blocksRes || []);
      }
      setHolidays(fetchedHolidays);
      // Los eventos se pasan via prop `events={calendarEvents}` — no manipular el calendario directamente
      // para evitar el loop datesSet → fetchData → re-render → datesSet
    } catch (error: any) {
      // Ignorar silenciosamente errores de abort — son intencionales (navegación rápida)
      if (error?.name === 'AbortError' || error?.code === 'ERR_CANCELED') return;
      console.error('Error fetching data:', error);
    } finally {
      // Solo limpiar el loading si este fetch es el activo (no fue reemplazado por uno más nuevo)
      if (fetchAbortControllerRef.current === abortController) {
        if (!isBackground) setLoading(false);
        else setIsBackgroundSyncing(false);
      }
    }
  }, [fetchGoogleBlocks, selectedProfessionalId, user?.role, user?.professional_id]);

  // Mantener ref estable para que los handlers de socket siempre llamen la versión más reciente
  useEffect(() => {
    fetchDataRef.current = fetchData;
  }, [fetchData]);

  // === EFECTO 1: Inicialización — corre UNA SOLA VEZ al montar ===
  useEffect(() => {
    const initializeAgenda = async () => {
      // Fire and forget calendar sync so it doesn't block the UI
      if (user?.role === 'ceo' || user?.role === 'secretary' || user?.role === 'professional') {
        api.post('/admin/calendar/sync').catch(() => { /* Continúa silenciosamente */ });
      }

      // Fetch DB data immediately
      await fetchDataRef.current?.();
    };
    initializeAgenda();
    return () => { fetchAbortControllerRef.current?.abort(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Intencionalmente vacío: solo al montar

  // === EFECTO 2: Socket.IO — corre UNA SOLA VEZ, sin depender de fetchData ===
  useEffect(() => {
    socketRef.current = getSocket();

    // Debounced background refresh — multiple rapid socket events only trigger ONE fetch
    let agendaRefreshTimer: ReturnType<typeof setTimeout> | null = null;
    const debouncedAgendaRefresh = () => {
      if (agendaRefreshTimer) clearTimeout(agendaRefreshTimer);
      agendaRefreshTimer = setTimeout(() => fetchDataRef.current?.(true), 2000);
    };
    socketRef.current.on('NEW_APPOINTMENT', debouncedAgendaRefresh);
    socketRef.current.on('APPOINTMENT_UPDATED', debouncedAgendaRefresh);
    socketRef.current.on('PAYMENT_CONFIRMED', debouncedAgendaRefresh);
    socketRef.current.on('BILLING_UPDATED', debouncedAgendaRefresh);
    socketRef.current.on('RECORD_UPDATED', debouncedAgendaRefresh);
    socketRef.current.on('APPOINTMENT_DELETED', (deletedAppointmentId: string) => {
      setAppointments(prevAppointments => {
        const updated = prevAppointments.filter(apt => apt.id !== deletedAppointmentId);
        eventsRef.current = updated;
        return updated;
      });
      if (calendarRef.current) {
        const calendarApi = calendarRef.current.getApi();
        const existingEvent = calendarApi.getEventById(deletedAppointmentId);
        if (existingEvent) existingEvent.remove();
      }
    });

    return () => {
      // Remove event handlers only — do NOT disconnect the singleton
      if (socketRef.current) {
        socketRef.current.off('NEW_APPOINTMENT', debouncedAgendaRefresh);
        socketRef.current.off('APPOINTMENT_UPDATED', debouncedAgendaRefresh);
        socketRef.current.off('PAYMENT_CONFIRMED', debouncedAgendaRefresh);
        socketRef.current.off('BILLING_UPDATED', debouncedAgendaRefresh);
        socketRef.current.off('RECORD_UPDATED', debouncedAgendaRefresh);
        socketRef.current.off('APPOINTMENT_DELETED');
      }
      if (agendaRefreshTimer) clearTimeout(agendaRefreshTimer);
      if (datesSetTimerRef.current) clearTimeout(datesSetTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Intencionalmente vacío: socket se conecta una sola vez

  // FIX 2: Memoized filtered appointments and blocks
  const filteredAppointments = useMemo(() => {
    let list = appointments;
    // Filtrar cancelados (Protocolo Platinum: no molestar visualmente)
    list = list.filter((apt: Appointment) => apt.status !== 'cancelled');
    
    if (!selectedProfessionalId || selectedProfessionalId === 'all') return list;
    return list.filter((apt: Appointment) => apt.professional_id?.toString() === selectedProfessionalId);
  }, [appointments, selectedProfessionalId]);

  const filteredBlocks = useMemo(() => {
    if (!selectedProfessionalId || selectedProfessionalId === 'all') return googleBlocks;
    return googleBlocks.filter((block: GoogleCalendarBlock) => block.professional_id?.toString() === selectedProfessionalId);
  }, [googleBlocks, selectedProfessionalId]);

  // Holidays shown to all users (not filtered by professional)
  const filteredHolidays = holidays;

  // Professional user: lock filter to their id (fallback for old sessions without professional_id in JWT)
  useEffect(() => {
    if (user?.role === 'professional' && user?.professional_id && professionals.length > 0) {
      const myId = user.professional_id.toString();
      if (selectedProfessionalId !== myId) {
        setSelectedProfessionalId(myId);
      }
    }
  }, [user?.role, user?.professional_id, professionals]);

  // === EFECTO 3: Cambio de filtro de profesional — invalida el guardián de rango y re-fetchea ===
  useEffect(() => {
    // Saltar el primer render: el init ya hace el fetch inicial
    if (filterInitialRenderRef.current) {
      filterInitialRenderRef.current = false;
      return;
    }
    // Invalidar caché de rango para que datesSet no bloquee el siguiente fetch
    lastFetchedRangeRef.current = null;
    // Fetchear el rango actual del calendario con el nuevo filtro
    if (calendarRef.current) {
      const calApi = calendarRef.current.getApi();
      fetchData(false, calApi.view.activeStart, calApi.view.activeEnd);
    } else {
      fetchData();
    }
    // fetchData está en deps porque aquí es una acción explícita del usuario (no loop)
  }, [selectedProfessionalId, fetchData]);

  // FIX: Refetch on mobile when selectedDate changes to ensure data is available
  useEffect(() => {
    if (isMobile && selectedDate) {
      fetchData(true); // Background fetch to avoid flickering
    }
  }, [selectedDate, isMobile]);

  // Handle deep linking from notifications
  useEffect(() => {
    const state = location.state as { openAppointmentId?: string | number };
    if (state?.openAppointmentId && appointments.length > 0) {
      const aptId = state.openAppointmentId.toString();
      const apt = appointments.find(a => a.id.toString() === aptId);
      if (apt) {
        setSelectedEvent(apt);
        setSelectedDate(new Date(apt.appointment_datetime));
        setShowModal(true);
        // Limpiar el estado para evitar re-aperturas no deseadas
        window.history.replaceState({}, document.title);
      }
    }
  }, [location.state, appointments]);

  // Measure toolbar height for sticky offset (DLD-29 fix)
  useEffect(() => {
    const measure = () => {
      const toolbar = document.querySelector('.fc-header-toolbar');
      if (toolbar) {
        const h = toolbar.getBoundingClientRect().height;
        document.documentElement.style.setProperty('--fc-toolbar-height', `${h}px`);
      }
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [currentView]);

  // Calendar events transformer
  const calendarEvents = useMemo(() => [
    ...filteredAppointments.map((apt) => ({
      id: apt.id,
      title: `${apt.patient_name} - ${apt.appointment_type}`,
      start: apt.appointment_datetime,
      end: apt.end_datetime || undefined,
      backgroundColor: 'transparent',
      borderColor: 'transparent',
      extendedProps: { ...apt, eventType: 'appointment' },
      resourceId: apt.professional_id?.toString() || '0',
    })),
    ...filteredBlocks.map((block) => ({
      id: block.id,
      title: `🔒 ${block.title}`,
      start: block.start_datetime,
      end: block.end_datetime,
      allDay: block.all_day || false,
      backgroundColor: 'transparent',
      borderColor: 'transparent',
      extendedProps: { ...block, eventType: 'gcalendar_block' },
      resourceId: block.professional_id?.toString() || undefined,
    })),
    ...filteredHolidays.map((holiday) => ({
      id: holiday.id || `holiday-${holiday.date}`,
      title: `🎉 ${holiday.name}`,
      start: holiday.date,
      allDay: true,
      backgroundColor: '#ef4444', // Red for holidays
      borderColor: '#ef4444',
      textColor: '#ffffff',
      extendedProps: { ...holiday, eventType: 'holiday' },
    })),
  ], [filteredAppointments, filteredBlocks, filteredHolidays]);

  // Dynamic slot time range — never hide appointments outside 08:00-20:00
  const { dynamicSlotMin, dynamicSlotMax } = useMemo(() => {
    const DEFAULT_MIN = 8; // 08:00
    const DEFAULT_MAX = 20; // 20:00
    let earliest = DEFAULT_MIN;
    let latest = DEFAULT_MAX;

    for (const apt of filteredAppointments) {
      const d = new Date(apt.appointment_datetime);
      const h = d.getHours();
      const endH = apt.end_datetime
        ? new Date(apt.end_datetime).getHours() + (new Date(apt.end_datetime).getMinutes() > 0 ? 1 : 0)
        : h + 1;
      if (h < earliest) earliest = h;
      if (endH > latest) latest = endH;
    }
    for (const block of filteredBlocks) {
      if (block.all_day) continue;
      const sh = new Date(block.start_datetime).getHours();
      const ehRaw = new Date(block.end_datetime);
      const eh = ehRaw.getHours() + (ehRaw.getMinutes() > 0 ? 1 : 0);
      if (sh < earliest) earliest = sh;
      if (eh > latest) latest = eh;
    }

    // Clamp: never go below 00:00 or above 24:00, add 1h padding
    const padMin = Math.max(0, earliest - 1);
    const padMax = Math.min(24, latest + 1);
    return {
      dynamicSlotMin: `${String(padMin).padStart(2, '0')}:00:00`,
      dynamicSlotMax: `${String(padMax).padStart(2, '0')}:00:00`,
    };
  }, [filteredAppointments, filteredBlocks]);

  // Map professionals to resources (professional user: only their column)
  const resources = useMemo(() => {
    const list = user?.role === 'professional' && user?.professional_id
      ? professionals.filter((p: Professional) => p.id === user.professional_id)
      : professionals;
    const mapped = list.map((p: Professional) => ({
      id: p.id.toString(),
      title: `Dr. ${p.first_name} ${p.last_name || ''}`,
      eventColor: '#3b82f6',
    }));
    // Add catch-all resource for appointments without a professional assigned
    // so they don't disappear in resourceTimeGridDay view
    const hasUnassigned = filteredAppointments.some(apt => !apt.professional_id);
    if (hasUnassigned) {
      mapped.push({ id: '0', title: 'Sin asignar', eventColor: '#6b7280' });
    }
    return mapped;
  }, [professionals, user?.role, user?.professional_id, filteredAppointments]);

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

  const getExportParams = () => {
    const calApi = calendarRef.current?.getApi();
    const view = calApi?.view;
    const start = view?.activeStart?.toISOString()?.split('T')[0];
    const end = view?.activeEnd?.toISOString()?.split('T')[0];
    if (!start || !end) return null;
    const params = new URLSearchParams({ start_date: start, end_date: end });
    if (selectedProfessionalId !== 'all') params.append('professional_id', selectedProfessionalId);
    return { start, end, params };
  };

  const handleExport = async (format: 'pdf' | 'png') => {
    setShowExportMenu(false);
    setExporting(true);
    try {
      const ep = getExportParams();
      if (!ep) return;
      ep.params.set('format', format);

      const resp = await api.get(`/admin/agenda/export?${ep.params.toString()}`, { responseType: 'blob' });
      const blob = new Blob([resp.data], { type: format === 'pdf' ? 'application/pdf' : 'image/png' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `agenda_semanal_${ep.start}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Error exporting agenda:', err);
    } finally {
      setExporting(false);
    }
  };

  const handlePrint = async () => {
    setShowExportMenu(false);
    setExporting(true);
    try {
      const ep = getExportParams();
      if (!ep) return;
      ep.params.set('format', 'pdf');

      const resp = await api.get(`/admin/agenda/export?${ep.params.toString()}`, { responseType: 'blob' });
      const blob = new Blob([resp.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const printWindow = window.open(url);
      if (printWindow) {
        printWindow.addEventListener('load', () => { printWindow.print(); });
      }
    } catch (err) {
      console.error('Error printing agenda:', err);
    } finally {
      setExporting(false);
    }
  };

  const handleEventClick = (info: any) => {
    const eventType = info.event.extendedProps.eventType;
    
    // Check if it's a holiday
    if (eventType === 'holiday') {
      const holiday = info.event.extendedProps as Holiday;
      setSelectedHoliday(holiday);
      return;
    }
    
    // Check if it's a Google Calendar block
    if (eventType === 'gcalendar_block') {
      alert(`${t('agenda.google_block')}:\n\n${info.event.title}\n${new Date(info.event.start).toLocaleString(language)} - ${new Date(info.event.end).toLocaleString(language)}`);
      return;
    }

    setSelectedEvent(info.event.extendedProps);
    setSelectedDate(info.event.start);
    setShowModal(true);
  };

  const handleEventDrop = async (info: any) => {
    // Guard: only handle appointment events
    const eventType = info.event.extendedProps?.eventType;
    if (eventType !== 'appointment' && eventType !== undefined) {
      info.revert();
      return;
    }

    const apt = info.event.extendedProps;
    const appointmentId = apt?.id || info.event.id;

    if (!appointmentId) {
      info.revert();
      return;
    }

    try {
      // Get new datetime from the dropped position
      const newDatetime = info.event.start.toISOString();

      // Check if professional changed (resource drag in resourceTimeGridDay)
      let professionalId = apt?.professional_id;
      const newResources = info.event.getResources?.();
      if (newResources && newResources.length > 0) {
        professionalId = parseInt(newResources[0].id, 10);
      }

      await api.put(`/admin/appointments/${appointmentId}`, {
        patient_id: apt?.patient_id,
        professional_id: professionalId,
        appointment_datetime: newDatetime,
        appointment_type: apt?.appointment_type,
        duration_minutes: apt?.duration_minutes || 30,
        notes: apt?.notes || '',
        check_collisions: false,
      });

      // Refresh data to sync state
      fetchData(true);
    } catch (err) {
      info.revert();
      console.error('Drag save error:', err);
      alert(t('agenda.drag_save_error'));
    }
  };

  const handleEventResize = async (info: any) => {
    const eventType = info.event.extendedProps?.eventType;
    if (eventType !== 'appointment' && eventType !== undefined) {
      info.revert();
      return;
    }

    const apt = info.event.extendedProps;
    const appointmentId = apt?.id || info.event.id;

    if (!appointmentId) {
      info.revert();
      return;
    }

    try {
      const start = info.event.start;
      const end = info.event.end;
      const newDuration = Math.round((end.getTime() - start.getTime()) / 60000);

      await api.put(`/admin/appointments/${appointmentId}`, {
        patient_id: apt?.patient_id,
        professional_id: apt?.professional_id,
        appointment_datetime: start.toISOString(),
        appointment_type: apt?.appointment_type,
        duration_minutes: newDuration,
        notes: apt?.notes || '',
        check_collisions: false,
      });

      fetchData(true);
    } catch (err) {
      info.revert();
      console.error('Resize save error:', err);
      alert(t('agenda.drag_save_error'));
    }
  };

  const handleSave = async (data: any) => {
    // Capturar rango visible antes de operaciones async para refetch correcto
    const cal = calendarRef.current?.getApi();
    let rangeStart = cal?.view?.activeStart;
    let rangeEnd = cal?.view?.activeEnd;

    try {
      if (selectedEvent) {
        await api.put(`/admin/appointments/${selectedEvent.id}`, data);
      } else {
        await api.post('/admin/appointments', {
          ...data,
          status: 'confirmed',
          source: 'manual',
        });
        // Al crear, ampliar el rango de refetch para incluir la fecha del turno nuevo
        // (si la vista actual no la muestra, p.ej. semana 14-20 y turno el 26)
        const newDate = data.appointment_datetime ? new Date(data.appointment_datetime) : null;
        if (newDate && rangeStart && rangeEnd) {
          rangeStart = newDate < rangeStart ? startOfDay(newDate) : rangeStart;
          rangeEnd = newDate > rangeEnd ? endOfDay(addDays(newDate, 1)) : rangeEnd;
        }
      }
      // Refetch con rango explícito para que el turno nuevo aparezca de inmediato
      await fetchData(false, rangeStart ?? undefined, rangeEnd ?? undefined);
      setShowModal(false);
    } catch (error: any) {
      throw error; // Propagate to form for error display
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm(t('agenda.confirm_delete'))) return;
    try {
      // Borrado físico (Protocolo Platinum: limpieza total de agenda)
      await api.delete(`/admin/appointments/${id}`);
      await fetchData();
      setShowModal(false);
    } catch (error) {
      alert(t('agenda.alert_cancel_error'));
    }
  };

  return (
    <div className="agenda-print-root flex flex-col h-screen overflow-hidden bg-transparent">
      {/* Header - Fixed, non-scrollable */}
      <div className="flex-shrink-0 px-4 lg:px-6 pt-4 lg:pt-6">
        {/* Header */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center gap-4 mb-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center w-full lg:w-auto gap-4">
            <div className="border-l-4 border-blue-500 pl-3 sm:pl-4 min-w-0">
              <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">{t('agenda.title')}</h1>
              <p className="text-xs sm:text-sm text-white/50 mt-0.5">{t('agenda.subtitle')}</p>
              {visibleRangeStr && (
                <p className="text-xs text-white/30 mt-1" title={t('agenda.range_hint')}>
                  {filteredAppointments.length} {t('agenda.appointments_in_view')} • {visibleRangeStr}
                </p>
              )}
            </div>

            {/* Professional Filter (CEO/Secretary only) - Mobile Stacking */}
            {(user?.role === 'ceo' || user?.role === 'secretary') && (
              <div className="flex items-center gap-2 bg-white/[0.04] px-3 py-2 rounded-xl border border-white/[0.08] w-full sm:w-auto">
                <Stethoscope size={16} className="text-blue-400 shrink-0" />
                <select
                  value={selectedProfessionalId}
                  onChange={(e) => setSelectedProfessionalId(e.target.value)}
                  className="bg-transparent border-none text-xs font-medium focus:ring-0 outline-none text-white cursor-pointer w-full"
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
            <div className="flex gap-2 sm:gap-3 bg-white/[0.04] px-3 py-1.5 rounded-full border border-white/[0.06]">
              <div className="flex items-center gap-1">
                <div className="w-2.5 h-2.5 rounded-full bg-blue-500"></div>
                <span className="text-[10px] text-white/50">{t('agenda.source_ai')}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2.5 h-2.5 rounded-full bg-purple-500"></div>
                <span className="text-[10px] text-white/50">{t('agenda.source_nova')}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2.5 h-2.5 rounded-full bg-green-500"></div>
                <span className="text-[10px] text-white/50">{t('agenda.source_manual')}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-2.5 h-2.5 rounded-full bg-gray-500"></div>
                <span className="text-[10px] text-white/50">{t('agenda.source_gcalendar')}</span>
              </div>
            </div>

            <div className="flex items-center gap-2 ml-auto lg:ml-0">
              {/* Pulse Indicator */}
              {isBackgroundSyncing && (
                <div className="flex items-center justify-center w-8 h-8">
                  <RefreshCw size={16} className="text-blue-500 animate-spin opacity-60" />
                </div>
              )}

              {/* Export Button */}
              <div className="relative">
                <button
                  onClick={() => setShowExportMenu(!showExportMenu)}
                  disabled={exporting}
                  title="Descargar agenda"
                  className="print:hidden flex items-center justify-center w-8 h-8 rounded-lg bg-white/[0.04] border border-white/[0.08] text-white/50 hover:bg-white/[0.08] hover:text-white transition-colors disabled:opacity-50"
                >
                  {exporting ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
                </button>
                {showExportMenu && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setShowExportMenu(false)} />
                    <div className="absolute right-0 top-10 z-50 bg-[#1a1f2e] border border-white/[0.1] rounded-lg shadow-xl py-1 min-w-[180px]">
                      <button
                        onClick={() => handleExport('pdf')}
                        className="w-full px-4 py-2 text-left text-sm text-white/80 hover:bg-white/[0.06] flex items-center gap-2"
                      >
                        <FileText size={14} /> Descargar PDF
                      </button>
                      <button
                        onClick={() => handleExport('png')}
                        className="w-full px-4 py-2 text-left text-sm text-white/80 hover:bg-white/[0.06] flex items-center gap-2"
                      >
                        <Image size={14} /> Descargar imagen (PNG)
                      </button>
                      <div className="border-t border-white/[0.06] my-1" />
                      <button
                        onClick={handlePrint}
                        className="w-full px-4 py-2 text-left text-sm text-white/80 hover:bg-white/[0.06] flex items-center gap-2"
                      >
                        <Printer size={14} /> Imprimir
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>

          </div>
        </div>
      </div>

      {/* Mobile View or Desktop Calendar — OUTSIDE the flex-shrink-0 header */}
      {isMobile ? (
        <div className="flex-1 min-h-0 overflow-y-auto overscroll-contain">
          <MobileAgenda
              appointments={filteredAppointments}
              googleBlocks={filteredBlocks}
              selectedDate={selectedDate || new Date()}
              onDateChange={(date) => {
                setSelectedDate(date);
                if (calendarRef.current) calendarRef.current.getApi().gotoDate(date);
              }}
              onEventClick={handleEventClick}
              onNewAppointment={(date) => handleDateClick({ date })}
              professionals={professionals}
              holidays={holidays}
              onHolidaySave={() => fetchData()}
            />
        </div>
      ) : (
        <div className="flex-1 min-h-0 px-4 lg:px-6 pb-4 lg:pb-6">
            <div className="h-[calc(100vh-140px)] bg-white/[0.03] backdrop-blur-lg md:backdrop-blur-2xl border border-white/[0.06] shadow-2xl rounded-2xl md:rounded-3xl p-2 sm:p-4 overflow-hidden flex flex-col">
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
            background-color: rgba(255,255,255,0.02) !important;
            opacity: 0.5 !important;
          }

          .fc-timegrid-col.fc-day-past {
            background-color: rgba(255,255,255,0.02) !important;
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

          /* ===== STICKY HEADERS — semana/día ===== */
          /* FC maneja sticky internamente con stickyHeaderDates={true} + height="100%" */

          /* Toolbar de navegación (flechas, título, botones de vista) */
          .fc .fc-toolbar.fc-header-toolbar {
            background-color: #0d1117 !important;
            margin-bottom: 0 !important;
            padding: 8px 0 8px 0 !important;
            border-bottom: 1px solid rgba(255,255,255,0.06) !important;
          }

          /* Header de columnas de días — FC lo hace sticky, solo ponemos bg color */
          .fc .fc-scrollgrid-section-header > td,
          .fc thead .fc-scrollgrid-section > td {
            background-color: #0d1117 !important;
          }

          /* Eje de tiempo (labels 08:00, 09:00...) en la columna izquierda — sticky horizontal */
          .fc .fc-timegrid-axis {
            background-color: #0d1117 !important;
          }

          /* Fix gap entre toolbar y grilla en vista Semana (DLD-34) */
          .fc .fc-scrollgrid {
            border-spacing: 0 !important;
          }

          /* ===== DARK MODE OVERRIDES FOR FULLCALENDAR ===== */
          .fc {
            --fc-border-color: rgba(255,255,255,0.06);
            --fc-page-bg-color: transparent;
            --fc-neutral-bg-color: rgba(255,255,255,0.04);
            --fc-list-event-hover-bg-color: rgba(255,255,255,0.04);
            --fc-today-bg-color: rgba(59,130,246,0.08);
            --fc-highlight-color: rgba(59,130,246,0.12);
            --fc-non-business-color: rgba(255,255,255,0.02);
            --fc-bg-event-opacity: 0.15;
            --fc-neutral-text-color: rgba(255,255,255,0.5);
            --fc-event-text-color: #fff;
            color: rgba(255,255,255,0.85);
          }

          /* Toolbar buttons */
          .fc .fc-button-primary {
            background-color: rgba(255,255,255,0.04) !important;
            border-color: rgba(255,255,255,0.08) !important;
            color: rgba(255,255,255,0.7) !important;
          }
          .fc .fc-button-primary:hover {
            background-color: rgba(255,255,255,0.08) !important;
            color: #fff !important;
          }
          .fc .fc-button-primary.fc-button-active,
          .fc .fc-button-primary:not(:disabled).fc-button-active {
            background-color: #fff !important;
            color: #0a0e1a !important;
            border-color: #fff !important;
          }
          .fc .fc-today-button {
            background-color: rgba(255,255,255,0.04) !important;
            border-color: rgba(255,255,255,0.08) !important;
            color: rgba(255,255,255,0.7) !important;
          }
          .fc .fc-today-button:hover {
            background-color: rgba(255,255,255,0.08) !important;
            color: #fff !important;
          }
          .fc .fc-today-button:disabled {
            opacity: 0.3 !important;
          }

          /* Toolbar title */
          .fc .fc-toolbar-title {
            color: #fff !important;
          }

          /* Column headers (day names) */
          .fc .fc-col-header-cell {
            background-color: rgba(255,255,255,0.04) !important;
            border-color: rgba(255,255,255,0.06) !important;
          }
          .fc .fc-col-header-cell-cushion {
            color: rgba(255,255,255,0.7) !important;
          }

          /* Time slot labels */
          .fc .fc-timegrid-slot-label-cushion {
            color: rgba(255,255,255,0.5) !important;
          }

          /* Day number in month view */
          .fc .fc-daygrid-day-number {
            color: rgba(255,255,255,0.7) !important;
          }

          /* List view — disable sticky date headers to prevent stacking overlap */
          .fc .fc-list-day-cushion {
            background-color: rgba(255,255,255,0.04) !important;
          }
          .fc .fc-list-day > th,
          .fc .fc-list-sticky .fc-list-day > th,
          .fc .fc-list-table th {
            position: relative !important;
            z-index: auto !important;
          }
          .fc .fc-list-day-cushion a {
            color: #fff !important;
          }
          .fc .fc-list-event td {
            border-color: rgba(255,255,255,0.06) !important;
          }
          .fc .fc-list-event:hover td {
            background-color: rgba(255,255,255,0.04) !important;
          }
          .fc .fc-list-event-title a {
            color: rgba(255,255,255,0.85) !important;
          }
          .fc .fc-list-event-time {
            color: rgba(255,255,255,0.5) !important;
          }

          /* Resource labels */
          .fc .fc-resource-cell {
            background-color: rgba(255,255,255,0.04) !important;
            color: rgba(255,255,255,0.7) !important;
          }

          /* Scrollbar dark */
          .fc ::-webkit-scrollbar {
            width: 6px;
          }
          .fc ::-webkit-scrollbar-track {
            background: transparent;
          }
          .fc ::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.1);
            border-radius: 3px;
          }

          /* More link */
          .fc .fc-daygrid-more-link {
            color: rgba(255,255,255,0.6) !important;
          }

          /* Popover */
          .fc .fc-popover {
            background: #0d1117 !important;
            border-color: rgba(255,255,255,0.06) !important;
          }
          .fc .fc-popover-header {
            background: rgba(255,255,255,0.04) !important;
            color: #fff !important;
          }

        `}</style>

              {/* Siempre montar el calendario para que las flechas y la vista no reviertan al hacer fetch */}
              <div className="relative flex-1 min-h-0 overflow-hidden">
                {loading && appointments.length === 0 && (
                  <div className="absolute inset-0 flex items-center justify-center bg-[#0d1117]/80 z-10 rounded-2xl">
                    <div className="flex flex-col items-center gap-4">
                      <RefreshCw className="w-12 h-12 text-blue-400 animate-spin" />
                      <p className="text-white/50 font-medium">{t('common.loading')}</p>
                    </div>
                  </div>
                )}
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
                  stickyHeaderDates={true}
                  slotDuration="00:15:00"
                  slotLabelInterval="01:00"
                  initialDate={new Date()}
                  firstDay={1} // Lunes como primer día de semana (0=Dom, 1=Lun)
                  timeZone="local"
                  locale={language}
                  buttonText={{
                    today: t('agenda.today'),
                    month: t('agenda.month'),
                    week: t('agenda.week'),
                    day: t('agenda.day'),
                    year: t('agenda.year'),
                    three_years: t('agenda.three_years'),
                    list: t('agenda.list')
                  }}
                  views={{
                    listYear: {
                      type: 'list',
                      duration: { years: 1 },
                      buttonText: t('agenda.year')
                    },
                    listThreeYears: {
                      type: 'list',
                      duration: { years: 3 },
                      buttonText: t('agenda.three_years')
                    }
                  }}
                  allDayText={t('agenda.all_day')}
                  headerToolbar={{
                    left: window.innerWidth < 768 ? 'prev,next' : 'prev,next today',
                    center: 'title',
                    right: window.innerWidth < 768
                      ? 'timeGridDay,dayGridMonth,listYear'
                      : (window.innerWidth < 1024 
                          ? 'timeGridWeek,dayGridMonth,listYear,listThreeYears' 
                          : 'resourceTimeGridDay,timeGridWeek,dayGridMonth,listYear,listThreeYears'),
                  }}
                  height="100%"
                  selectAllow={(selectInfo) => {
                    const now = new Date();
                    return selectInfo.start >= now;
                  }}
                  events={calendarEvents}
                  datesSet={(dateInfo) => {
                    setCurrentView(dateInfo.view.type);
                    localStorage.setItem('agendaView', dateInfo.view.type);
                    // Kill sticky on list view after data loads
                    if (dateInfo.view.type.startsWith('list')) {
                      requestAnimationFrame(() => {
                        const table = dateInfo.view.el?.querySelector('.fc-list-sticky');
                        if (table) table.classList.remove('fc-list-sticky');
                      });
                    }
                    const fmt = (d: Date) => d.toLocaleDateString(language === 'es' ? 'es-AR' : language === 'fr' ? 'fr-FR' : 'en-US', { day: 'numeric', month: 'short', year: 'numeric' });
                    setVisibleRangeStr(`${fmt(dateInfo.start)} – ${fmt(dateInfo.end)}`);

                    // Guardián de rango: solo fetchea si el usuario realmente navegó (cambio de vista
                    // o flechas). FullCalendar dispara datesSet también en re-renders internos con
                    // el mismo rango — este guard los ignora silenciosamente.
                    if (datesSetTimerRef.current) clearTimeout(datesSetTimerRef.current);
                    datesSetTimerRef.current = setTimeout(() => {
                      const newStart = dateInfo.start.toISOString();
                      const newEnd = dateInfo.end.toISOString();
                      const last = lastFetchedRangeRef.current;
                      const sameRange = last &&
                        last.startISO === newStart &&
                        last.endISO === newEnd &&
                        last.professionalId === selectedProfessionalId &&
                        last.viewType === dateInfo.view.type;
                      if (sameRange) return; // Re-render interno — no hacer fetch
                      lastFetchedRangeRef.current = {
                        startISO: newStart,
                        endISO: newEnd,
                        professionalId: selectedProfessionalId,
                        viewType: dateInfo.view.type,
                      };
                      // Llamar via ref para usar siempre el closure más fresco de fetchData,
                      // evitando que selectedProfessionalId quede stale en el callback de datesSet
                      fetchDataRef.current?.(false, dateInfo.start, dateInfo.end);
                    }, 200);
                  }}
                  viewDidMount={(viewInfo) => {
                    setCurrentView(viewInfo.view.type);
                    localStorage.setItem('agendaView', viewInfo.view.type);
                    // Kill sticky on list view date headers — FullCalendar sets inline
                    // position:sticky via JS which causes headers to stack on scroll
                    if (viewInfo.view.type.startsWith('list')) {
                      const table = viewInfo.el?.querySelector('.fc-list-sticky');
                      if (table) table.classList.remove('fc-list-sticky');
                    }
                  }}
                  dateClick={handleDateClick}
                  eventClick={handleEventClick}
                  slotEventOverlap={false}
                  slotMinTime={dynamicSlotMin}
                  slotMaxTime={dynamicSlotMax}
                  eventContent={(eventInfo) => <AppointmentCard {...eventInfo} />}
                  eventDrop={handleEventDrop}
                  eventResize={handleEventResize}
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
              </div>
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

      {/* Holiday Detail Modal */}
      <HolidayDetailModal
        holiday={selectedHoliday}
        isOpen={!!selectedHoliday}
        onClose={() => setSelectedHoliday(null)}
        onSaved={() => { setSelectedHoliday(null); fetchData(); }}
      />
    </div>
  );
}
