import React, { useState, useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import {
  X, ChevronRight, ChevronLeft, CheckCircle, Sparkles,
  Home, Calendar, Users, MessageSquare, ShieldCheck, BarChart3,
  Zap, Clock, User, Megaphone, Layout, Settings, Stethoscope,
  Target, BookOpen, Mic
} from 'lucide-react';

interface GuideStep {
  title: string;
  description: string;
  benefit: string;
  tip?: string;
}

interface PageGuide {
  icon: React.ReactNode;
  title: string;
  subtitle: string;
  steps: GuideStep[];
}

const GUIDES: Record<string, PageGuide> = {
  '/': {
    icon: <Home size={20} />,
    title: 'Dashboard',
    subtitle: 'Tu centro de mando en tiempo real',
    steps: [
      { title: 'KPIs en tiempo real', description: 'Turnos del dia, pacientes nuevos, ingresos y tasa de asistencia actualizados en vivo.', benefit: 'Decisiones rapidas sin buscar en multiples pantallas.', tip: 'Se actualizan automaticamente cuando la IA agenda turnos.' },
      { title: 'Actividad reciente', description: 'Ultimas acciones: turnos agendados, cancelaciones, derivaciones humanas y pacientes nuevos.', benefit: 'Sabe todo lo que pasa incluso fuera de horario.' },
      { title: 'Vista rapida de agenda', description: 'Resumen de turnos de hoy y manana con profesional asignado.', benefit: 'Planifica tu dia sin salir del dashboard.' },
      { title: 'Nova — Asistente de voz', description: 'El boton violeta flotante es Nova. Habla con ella para operar la clinica: agendar, consultar datos, navegar paginas, todo con la voz.', benefit: 'Manos libres: opera mientras atendes pacientes.', tip: 'Proba: "Que turnos hay hoy?", "Agendame turno para Gomez", "Cuanto facture este mes?"' },
    ],
  },
  '/agenda': {
    icon: <Calendar size={20} />,
    title: 'Agenda',
    subtitle: 'Gestion visual de turnos',
    steps: [
      { title: 'Calendario interactivo', description: 'Vista diaria, semanal y mensual. Click en horario vacio para crear turno manual.', benefit: 'Carga de trabajo por profesional de un vistazo.', tip: 'Click en horario vacio = turno manual rapido.' },
      { title: 'Filtro por profesional', description: 'Selecciona un profesional o "Todos" para ver agenda completa.', benefit: 'Cada profesional ve solo su agenda.' },
      { title: 'Mobile: Dia, Semana, Mes y Lista', description: '4 modos en mobile. Lista muestra todos los turnos cronologicos con scroll a pasados.', benefit: 'Navega facilmente entre vistas.' },
      { title: 'Badges de origen', description: 'Cada turno muestra quien lo agendo: Ventas IA (chatbot), Nova (voz), Manual o GCal.', benefit: 'Sabe de donde vienen tus turnos.' },
      { title: 'Edicion + facturacion', description: 'Click en turno: editar, reprogramar, cancelar, ver anamnesis, registrar pago.', benefit: 'Todo en un solo panel deslizable.' },
      { title: 'Google Calendar sync', description: 'Turnos se sincronizan con el GCal de cada profesional automaticamente.', benefit: 'El profesional ve turnos en su celular.' },
    ],
  },
  '/pacientes': {
    icon: <Users size={20} />,
    title: 'Pacientes',
    subtitle: 'Base de datos clinica completa',
    steps: [
      { title: 'Lista + busqueda', description: 'Todos los pacientes con busqueda instantanea por nombre, DNI o telefono.', benefit: 'Encontra cualquier paciente en segundos.', tip: 'Importa masivamente con CSV/Excel desde "Importar".' },
      { title: 'Ficha con 4 pestanas', description: 'Resumen (odontograma), Historia (registros clinicos), Archivos (documentos) y Anamnesis (ficha medica).', benefit: 'Todo en un solo lugar.' },
      { title: 'Odontograma interactivo', description: 'Diagrama FDI con 10 estados por diente. Toca para seleccionar, elige estado, boton flotante guarda. Animaciones y colores por patologia.', benefit: 'Registro visual rapido del estado bucal.' },
      { title: 'Galeria de documentos', description: 'Subi radiografias y estudios. Las imagenes de WhatsApp se guardan automaticamente en la ficha.', benefit: 'Material clinico centralizado.' },
      { title: 'Anamnesis digital', description: 'Link unico que la IA envia al agendar. El paciente completa su historial desde el celular.', benefit: 'Ahorra 10 min de consulta.' },
      { title: 'Historial clinico', description: 'Registros por visita con diagnostico, notas y datos del odontograma.', benefit: 'Contexto completo de cada atencion.' },
      { title: 'Importacion masiva', description: 'CSV/Excel con mapeo automatico. Detecta duplicados por telefono: saltar o actualizar.', benefit: 'Migra tu base en minutos.' },
    ],
  },
  '/chats': {
    icon: <MessageSquare size={20} />,
    title: 'Conversaciones',
    subtitle: 'WhatsApp, Instagram y Facebook unificados',
    steps: [
      { title: 'Bandeja unificada', description: 'WhatsApp (via YCloud), Instagram y Facebook en una sola bandeja con iconos por canal.', benefit: 'No necesitas 3 apps abiertas.' },
      { title: 'IA conversacional 24/7', description: 'Agente de ventas IA que agenda turnos, responde preguntas, hace triage, envia fichas medicas y cobra senas.', benefit: 'Atencion automatica las 24 horas.', tip: 'Recuerda preferencias del paciente y detecta si es nuevo o existente.' },
      { title: 'Verificacion de comprobantes', description: 'El paciente envia foto de transferencia → la IA analiza con vision: verifica titular y monto → confirma turno automaticamente.', benefit: 'Cobro de senas verificado sin revisar manualmente.' },
      { title: 'Modo manual + derivacion', description: '"Manual" silencia la IA por 24h para ese paciente. Urgencias o frustrados se derivan automaticamente con email al equipo.', benefit: 'Control total cuando lo necesites.' },
      { title: 'Panel del paciente', description: 'A la derecha: ficha, proximo turno, anamnesis, historial, booking terceros/menores.', benefit: 'Contexto completo mientras chateas.' },
      { title: 'Atribucion Meta Ads', description: 'Si el paciente llego por un anuncio de Meta, ves cual campaña y creativo lo trajo. First-touch: el primer ad queda registrado para siempre.', benefit: 'Sabe exactamente de donde vienen tus pacientes.' },
    ],
  },
  '/aprobaciones': {
    icon: <ShieldCheck size={20} />,
    title: 'Staff',
    subtitle: 'Control de acceso del equipo',
    steps: [
      { title: 'Solicitudes pendientes', description: 'Profesionales y secretarias se registran y esperan tu aprobacion.', benefit: 'Control total sobre quien accede.' },
      { title: 'Roles: CEO / Profesional / Secretaria', description: 'CEO: todo. Profesional: su agenda y pacientes. Secretaria: turnos de todos.', benefit: 'Cada rol ve solo lo que necesita.' },
      { title: 'Suspender acceso', description: 'Suspende temporalmente sin eliminar datos del profesional.', benefit: 'Gestion flexible del equipo.' },
    ],
  },
  '/sedes': {
    icon: <Stethoscope size={20} />,
    title: 'Sedes',
    subtitle: 'Clinicas, horarios y pagos',
    steps: [
      { title: 'Datos de la clinica', description: 'Nombre, direccion, Google Maps, telefono y logo. La IA usa todo esto para informar pacientes.', benefit: 'Info correcta en cada interaccion.' },
      { title: 'Horarios por dia', description: 'Configura dias y horarios de atencion. Diferentes horarios por dia, turnos manana/tarde.', benefit: 'La IA solo ofrece turnos dentro de estos horarios.' },
      { title: 'Multi-sede por dia', description: 'Operas en distintas ubicaciones? Configura sede + direccion + Maps por dia de la semana.', benefit: 'El paciente recibe la direccion correcta segun su dia.' },
      { title: 'Datos bancarios (senas)', description: 'CBU, alias y titular. La IA envia estos datos al paciente para transferir la sena (50%).', benefit: 'Cobro automatizado de senas.' },
      { title: 'Precio de consulta', description: 'Precio base que la IA informa. Override por profesional disponible en perfil.', benefit: 'Transparencia de precios automatica.' },
      { title: 'Sillones', description: 'Cuantos consultorios tenes para controlar turnos simultaneos.', benefit: 'Evita agendar mas de lo que podes atender.' },
    ],
  },
  '/analytics/professionals': {
    icon: <BarChart3 size={20} />,
    title: 'Analytics',
    subtitle: 'Rendimiento con datos reales',
    steps: [
      { title: 'KPIs por profesional', description: 'Turnos, asistencia, no-shows, retencion y facturacion por profesional.', benefit: 'Identifica quien rinde mas.' },
      { title: 'Tags inteligentes', description: 'Tags automaticos: "High Performance", "Retention Master", "Risk: Cancellations".', benefit: 'Alertas tempranas de problemas.' },
      { title: 'Filtros temporales', description: 'Rango de fechas y profesionales especificos.', benefit: 'Compara mes a mes o trimestre a trimestre.' },
      { title: 'Top tratamiento y dia', description: 'Tratamiento mas realizado y dia mas activo por profesional.', benefit: 'Optimiza la agenda con datos.' },
    ],
  },
  '/dashboard/status': {
    icon: <Zap size={20} />,
    title: 'IA & Tokens',
    subtitle: 'Consumo, costos y modelos',
    steps: [
      { title: 'Consumo por servicio', description: 'Tokens de: agente chat, Nova voz, memoria de pacientes, vision de comprobantes.', benefit: 'Controla costos por servicio.' },
      { title: 'Selector de modelos', description: 'Cambia modelo por servicio. Nova: gpt-4o-mini-realtime (economico) o gpt-4o-realtime (premium).', benefit: 'Balancea calidad vs costo.' },
      { title: 'Grafico diario', description: 'Barras de consumo por dia. Detecta picos y tendencias.', benefit: 'Anticipa costos.' },
    ],
  },
  '/tratamientos': {
    icon: <Clock size={20} />,
    title: 'Tratamientos',
    subtitle: 'Catalogo de servicios',
    steps: [
      { title: 'Catalogo completo', description: 'Tratamientos con codigo, nombre, duracion, precio y categoria.', benefit: 'La IA ofrece estos servicios a pacientes.' },
      { title: 'Duracion → agenda', description: 'La duracion determina cuanto espacio ocupa el turno en la agenda.', benefit: 'Sin solapamientos de turnos.' },
      { title: 'Profesionales asignados', description: 'Asigna quien puede hacer cada tratamiento. Sin asignar = todos pueden.', benefit: 'La IA agenda solo con el profesional correcto.', tip: 'La IA le dice al paciente: "Este tratamiento lo realiza Dr. X".' },
    ],
  },
  '/perfil': {
    icon: <User size={20} />,
    title: 'Mi Perfil',
    subtitle: 'Datos y configuracion personal',
    steps: [
      { title: 'Datos personales', description: 'Nombre, email, especialidad, telefono y matricula.', benefit: 'Aparece correctamente en confirmaciones.' },
      { title: 'Horario propio', description: 'Horarios de atencion por dia, independientes de la clinica.', benefit: 'No recibis turnos fuera de tu horario.' },
      { title: 'Precio propio', description: 'Si tu precio difiere del general, configuralo aca. Tiene prioridad.', benefit: 'Cada profesional su precio.' },
    ],
  },
  '/marketing': {
    icon: <Megaphone size={20} />,
    title: 'Marketing Hub',
    subtitle: 'ROI real de publicidad',
    steps: [
      { title: 'Atribucion first-touch', description: 'Cada paciente queda vinculado al primer anuncio de Meta que lo trajo. Se enriquece con Meta Graph API.', benefit: 'Retorno real por peso invertido.', tip: 'Los datos se cachean en Redis (48h TTL) para no saturar la API de Meta.' },
      { title: 'Metricas por campana', description: 'Inversion, CPA, CPL, impresiones, clicks, conversiones y ROI por campana y creativo.', benefit: 'Sabe que anuncio convierte mejor.' },
      { title: 'Conexion nativa Meta Ads', description: 'OAuth con Meta Business. Importa campanas, ad sets, ads, gastos y leads automaticamente.', benefit: 'Datos frescos sin carga manual.' },
      { title: 'Creativos individuales', description: 'Ve cada creativo (imagen/video) con su rendimiento: gasto, leads, costo por lead.', benefit: 'Escala lo que funciona, pausa lo que no.' },
      { title: 'YCloud + Chatwoot', description: 'YCloud conecta WhatsApp Business API. Los mensajes llegan al sistema y se procesan con IA. Chatwoot fue el motor original.', benefit: 'Infraestructura enterprise para mensajeria.' },
    ],
  },
  '/leads': {
    icon: <Target size={20} />,
    title: 'Leads',
    subtitle: 'Embudo de prospectos',
    steps: [
      { title: 'Lista con origen', description: 'Leads de Meta Ads, formularios, WhatsApp organico. Canal y campana visibles.', benefit: 'No pierdas ningun prospecto.' },
      { title: 'Estado de conversion', description: 'Nuevo → Contactado → En seguimiento → Convertido / Perdido. Filtra y exporta.', benefit: 'Embudo de ventas en tiempo real.' },
      { title: 'Recuperacion automatica', description: 'Detecta leads que escribieron sin agendar. Envia mensaje de recuperacion configurable.', benefit: 'Recupera pacientes sin esfuerzo.', tip: 'Ventana configurable por horas despues de la ultima interaccion.' },
    ],
  },
  '/templates': {
    icon: <Layout size={20} />,
    title: 'Automatizacion',
    subtitle: 'Reglas y plantillas HSM',
    steps: [
      { title: 'Recordatorios automaticos', description: 'Recordatorio de turno 24h antes. Reduce no-shows hasta 40%.', benefit: 'Menos ausencias automaticamente.' },
      { title: 'Reglas personalizadas', description: 'Mensajes por evento, canal y horario. Feedback post-cita automatico.', benefit: 'Automatiza toda comunicacion repetitiva.' },
      { title: 'Plantillas HSM (WhatsApp)', description: 'Templates aprobados por Meta para enviar fuera de la ventana de 24h.', benefit: 'Comunicate con pacientes inactivos.' },
      { title: 'Logs completos', description: 'Historial de envios: quien, cuando, canal, entregado/fallido.', benefit: 'Auditoria total.' },
    ],
  },
  '/configuracion': {
    icon: <Settings size={20} />,
    title: 'Configuracion',
    subtitle: 'Integraciones y ajustes',
    steps: [
      { title: 'WhatsApp via YCloud', description: 'Conecta tu numero de WhatsApp Business. YCloud es el proveedor de API: envia y recibe mensajes, audios, imagenes.', benefit: 'Tu clinica responde 24/7 por WhatsApp.', tip: 'YCloud soporta envio de templates HSM fuera de la ventana de 24h.' },
      { title: 'Google Calendar', description: 'OAuth con Google. Sincroniza turnos bidireccional con el calendario de cada profesional.', benefit: 'Turnos en el celular sin entrar a la app.' },
      { title: 'Meta Ads (Graph API)', description: 'Conecta tu Business Manager de Meta. Importa campanas, ad insights, leads y gastos via Graph API.', benefit: 'Marketing con datos reales en tiempo real.', tip: 'La atribucion first-touch vincula cada paciente al ad que lo trajo.' },
      { title: 'FAQs del chatbot', description: 'Preguntas frecuentes que la IA usa para responder. Mas FAQs = mejores respuestas.', benefit: 'IA informada sobre tu clinica.', tip: 'Nova puede agregar FAQs por voz.' },
      { title: 'Modelos de IA', description: 'Selecciona modelo para cada servicio: chat, Nova, memoria. Economico vs premium.', benefit: 'Control total sobre calidad y costo de IA.' },
    ],
  },
};

interface OnboardingGuideProps {
  isOpen: boolean;
  onClose: () => void;
}

const OnboardingGuide: React.FC<OnboardingGuideProps> = ({ isOpen, onClose }) => {
  const location = useLocation();
  const [currentStep, setCurrentStep] = useState(0);
  const [direction, setDirection] = useState<'next' | 'prev'>('next');
  const cardRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [swipeX, setSwipeX] = useState(0);
  const touchStartRef = useRef<{ x: number; y: number; time: number } | null>(null);
  const [completedPages, setCompletedPages] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('onboarding_completed') || '[]'); } catch { return []; }
  });

  const currentPath = Object.keys(GUIDES).find(path => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  }) || '/';

  const guide = GUIDES[currentPath];

  useEffect(() => { setCurrentStep(0); }, [currentPath]);

  // 3D tilt on mouse/touch
  const handlePointerMove = (e: React.PointerEvent) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width - 0.5) * 8;
    const y = ((e.clientY - rect.top) / rect.height - 0.5) * -8;
    setTilt({ x, y });
  };
  const handlePointerLeave = () => setTilt({ x: 0, y: 0 });

  // Swipe gesture
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY, time: Date.now() };
    setSwipeX(0);
  };
  const handleTouchMove = (e: React.TouchEvent) => {
    if (!touchStartRef.current) return;
    const dx = e.touches[0].clientX - touchStartRef.current.x;
    const dy = e.touches[0].clientY - touchStartRef.current.y;
    // Only track horizontal swipes
    if (Math.abs(dx) > Math.abs(dy)) {
      setSwipeX(dx * 0.4); // damped follow
    }
  };
  const handleTouchEnd = () => {
    if (!touchStartRef.current) return;
    const threshold = 50;
    if (swipeX < -threshold) {
      // Swiped left → next or close on last step
      if (currentStep < (guide?.steps.length || 1) - 1) {
        setDirection('next');
        setCurrentStep(s => s + 1);
      } else {
        // Last step — swipe left closes
        handleComplete();
      }
    } else if (swipeX > threshold) {
      // Swiped right → prev
      if (currentStep > 0) {
        setDirection('prev');
        setCurrentStep(s => s - 1);
      }
    }
    setSwipeX(0);
    touchStartRef.current = null;
  };

  if (!isOpen || !guide) return null;

  const step = guide.steps[currentStep];
  const isLastStep = currentStep === guide.steps.length - 1;
  const progress = ((currentStep + 1) / guide.steps.length) * 100;

  const goNext = () => {
    if (!isLastStep) { setDirection('next'); setCurrentStep(s => s + 1); }
  };
  const goPrev = () => {
    if (currentStep > 0) { setDirection('prev'); setCurrentStep(s => s - 1); }
  };
  const handleComplete = () => {
    const updated = [...new Set([...completedPages, currentPath])];
    setCompletedPages(updated);
    localStorage.setItem('onboarding_completed', JSON.stringify(updated));
    onClose();
  };

  const animClass = direction === 'next' ? 'animate-[cardSlideLeft_0.3s_ease-out]' : 'animate-[cardSlideRight_0.3s_ease-out]';

  return (
    <>
      <style>{`
        @keyframes modalIn { from { opacity:0; transform: scale(0.92) translateY(20px); } to { opacity:1; transform: scale(1) translateY(0); } }
        @keyframes cardSlideLeft { from { opacity:0; transform: translateX(40px); } to { opacity:1; transform: translateX(0); } }
        @keyframes cardSlideRight { from { opacity:0; transform: translateX(-40px); } to { opacity:1; transform: translateX(0); } }
      `}</style>

      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-[200]" onClick={onClose} />

      {/* Centered modal card */}
      <div className="fixed inset-0 z-[201] flex items-center justify-center p-4 pointer-events-none">
        <div
          ref={cardRef}
          onPointerMove={handlePointerMove}
          onPointerLeave={handlePointerLeave}
          className="pointer-events-auto w-full max-w-md bg-[#0c1018]/95 backdrop-blur-2xl border border-white/[0.08] rounded-3xl shadow-2xl shadow-black/40 overflow-hidden"
          style={{
            animation: 'modalIn 0.35s cubic-bezier(0.16,1,0.3,1)',
            transform: `perspective(800px) rotateY(${tilt.x}deg) rotateX(${tilt.y}deg)`,
            transition: 'transform 0.15s ease-out',
          }}
        >
          {/* Header */}
          <div className="px-5 pt-5 pb-3">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400">
                  {guide.icon}
                </div>
                <div>
                  <h2 className="text-base font-bold text-white leading-tight">{guide.title}</h2>
                  <p className="text-[11px] text-white/35">{guide.subtitle}</p>
                </div>
              </div>
              <button
                onClick={onClose}
                className="w-8 h-8 flex items-center justify-center rounded-full bg-white/[0.04] text-white/30 hover:bg-white/[0.08] hover:text-white/60 transition-all active:scale-90"
              >
                <X size={16} />
              </button>
            </div>

            {/* Progress */}
            <div className="flex items-center gap-2">
              <div className="flex-1 h-1 bg-white/[0.06] rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-500 ease-out" style={{ width: `${progress}%` }} />
              </div>
              <span className="text-[10px] font-bold text-white/25 tabular-nums">{currentStep + 1}/{guide.steps.length}</span>
            </div>
          </div>

          {/* Step content — swipeable */}
          <div
            className="px-5 pb-2 min-h-[240px] touch-pan-y select-none"
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
          >
            <div
              key={`${currentPath}-${currentStep}`}
              className={swipeX === 0 ? animClass : ''}
              style={{
                transform: swipeX !== 0 ? `translateX(${swipeX}px)` : undefined,
                opacity: swipeX !== 0 ? Math.max(0.3, 1 - Math.abs(swipeX) / 200) : undefined,
                transition: swipeX !== 0 ? 'none' : undefined,
              }}
            >
              {/* Step badge + title */}
              <div className="flex items-center gap-2 mb-3">
                <div className="w-6 h-6 rounded-md bg-blue-500 text-white flex items-center justify-center text-xs font-black shadow-md shadow-blue-500/25">
                  {currentStep + 1}
                </div>
                <h3 className="text-sm font-bold text-white">{step.title}</h3>
              </div>

              <p className="text-[13px] text-white/55 leading-relaxed mb-3">{step.description}</p>

              {/* Benefit card */}
              <div className="bg-emerald-500/[0.06] border border-emerald-500/15 rounded-xl p-3 mb-2 hover:bg-emerald-500/[0.10] transition-colors">
                <div className="flex items-start gap-2">
                  <Sparkles size={14} className="text-emerald-400 mt-0.5 shrink-0" />
                  <p className="text-xs text-emerald-300/70 leading-relaxed">{step.benefit}</p>
                </div>
              </div>

              {/* Tip */}
              {step.tip && (
                <div className="bg-amber-500/[0.06] border border-amber-500/15 rounded-xl p-3 hover:bg-amber-500/[0.10] transition-colors">
                  <div className="flex items-start gap-2">
                    <BookOpen size={14} className="text-amber-400 mt-0.5 shrink-0" />
                    <p className="text-xs text-amber-300/70 leading-relaxed">{step.tip}</p>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Dots + nav */}
          <div className="px-5 pb-5 pt-2">
            {/* Step dots */}
            <div className="flex items-center justify-center gap-1 mb-4">
              {guide.steps.map((_, i) => (
                <button
                  key={i}
                  onClick={() => { setDirection(i > currentStep ? 'next' : 'prev'); setCurrentStep(i); }}
                  className={`h-1 rounded-full transition-all duration-300 active:scale-90 ${
                    i === currentStep ? 'w-5 bg-blue-500' : i < currentStep ? 'w-1.5 bg-blue-500/30' : 'w-1.5 bg-white/[0.08]'
                  }`}
                />
              ))}
            </div>

            {/* Buttons */}
            <div className="flex items-center justify-between">
              <button
                onClick={goPrev}
                disabled={currentStep === 0}
                className="flex items-center gap-1 px-3 py-2 rounded-xl text-xs font-medium text-white/35 hover:bg-white/[0.04] transition-all disabled:opacity-0 disabled:pointer-events-none active:scale-95"
              >
                <ChevronLeft size={14} /> Anterior
              </button>

              {isLastStep ? (
                <button
                  onClick={handleComplete}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold bg-gradient-to-r from-blue-500 to-cyan-400 text-white shadow-md shadow-blue-500/20 hover:shadow-lg hover:shadow-blue-500/30 transition-all active:scale-95"
                >
                  <CheckCircle size={14} /> Entendido
                </button>
              ) : (
                <button
                  onClick={goNext}
                  className="flex items-center gap-1 px-4 py-2 rounded-xl text-xs font-semibold bg-white/[0.06] text-white/70 border border-white/[0.08] hover:bg-white/[0.10] transition-all active:scale-95"
                >
                  Siguiente <ChevronRight size={14} />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  );
};

export default OnboardingGuide;
