import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import {
  X, ChevronRight, ChevronLeft, CheckCircle, Sparkles,
  Home, Calendar, Users, MessageSquare, ShieldCheck, BarChart3,
  Zap, Clock, User, Megaphone, Layout, Settings, Stethoscope,
  Target, BookOpen, Mic, FileText, CreditCard, Upload, Brain,
  Globe, Bell, Shield
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
    icon: <Home size={22} />,
    title: 'Dashboard',
    subtitle: 'Tu centro de mando en tiempo real',
    steps: [
      {
        title: 'KPIs en tiempo real',
        description: 'Ves los numeros mas importantes de tu clinica de un vistazo: turnos del dia, pacientes nuevos, ingresos y tasa de asistencia.',
        benefit: 'Toma decisiones rapidas sin tener que buscar en multiples pantallas.',
        tip: 'Los numeros se actualizan automaticamente cuando la IA agenda turnos.',
      },
      {
        title: 'Actividad reciente',
        description: 'Muestra las ultimas acciones: turnos agendados, pacientes nuevos, cancelaciones y derivaciones humanas.',
        benefit: 'Nunca te pierdas nada de lo que pasa en tu clinica, incluso fuera de horario.',
      },
      {
        title: 'Vista rapida de agenda',
        description: 'Resumen de los turnos de hoy y manana con el profesional asignado.',
        benefit: 'Planifica tu dia sin salir del dashboard.',
      },
      {
        title: 'Nova — Tu asistente de voz',
        description: 'El boton flotante violeta en la esquina inferior es Nova, tu copiloto de IA. Habla con ella para agendar, consultar datos o navegar la plataforma sin tocar la pantalla.',
        benefit: 'Manos libres: opera tu clinica con la voz mientras atendes pacientes.',
        tip: 'Proba diciendo: "Que turnos hay hoy?" o "Agendame turno para Gomez".',
      },
    ],
  },
  '/agenda': {
    icon: <Calendar size={22} />,
    title: 'Agenda',
    subtitle: 'Gestion visual de turnos por profesional',
    steps: [
      {
        title: 'Vista de calendario',
        description: 'Agenda interactiva con vista diaria, semanal y mensual. Cada turno muestra paciente, tratamiento y duracion.',
        benefit: 'Ve de un vistazo la carga de trabajo de cada profesional.',
        tip: 'Hace click en un horario vacio para crear un turno manual rapido.',
      },
      {
        title: 'Filtro por profesional',
        description: 'Selecciona un profesional para ver solo sus turnos, o "Todos" para ver la agenda completa.',
        benefit: 'Cada profesional puede ver solo su propia agenda.',
      },
      {
        title: 'Vista mobile: Dia, Semana, Mes y Lista',
        description: 'En mobile tenes 4 modos: Dia (strip de fechas), Semana (agrupado por dia), Mes (grilla calendario) y Lista (todos los turnos cronologicos).',
        benefit: 'Navega facilmente entre vistas segun lo que necesites ver.',
      },
      {
        title: 'Edicion de turnos',
        description: 'Click en un turno para ver detalles, editar, reprogramar o cancelar. Incluye info del paciente, ficha medica y facturacion.',
        benefit: 'Gestiona cambios de ultimo momento sin complicaciones.',
        tip: 'Los turnos tienen badge de origen: Ventas IA (chatbot), Nova (voz), Manual o GCal.',
      },
      {
        title: 'Sincronizacion con Google Calendar',
        description: 'Si esta configurado, los turnos se sincronizan automaticamente con el Google Calendar del profesional.',
        benefit: 'El profesional ve sus turnos en su celular sin entrar a la plataforma.',
      },
      {
        title: 'Estados y facturacion',
        description: 'Cada turno tiene estado (scheduled, confirmed, completed) y datos de pago (pendiente, pagado, monto). Marca como completado para activar feedback automatico.',
        benefit: 'Control de asistencia y cobros en un solo lugar.',
      },
    ],
  },
  '/pacientes': {
    icon: <Users size={22} />,
    title: 'Pacientes',
    subtitle: 'Base de datos clinica completa',
    steps: [
      {
        title: 'Lista de pacientes',
        description: 'Todos los pacientes registrados con nombre, telefono, DNI, email y fecha de creacion. Busqueda instantanea.',
        benefit: 'Encontra cualquier paciente en segundos.',
        tip: 'Podes importar pacientes masivamente con CSV/Excel desde el boton "Importar".',
      },
      {
        title: 'Ficha del paciente',
        description: 'Click en un paciente para ver su ficha completa con 4 pestanas: Resumen, Historia, Archivos y Anamnesis.',
        benefit: 'Toda la info clinica en un solo lugar, accesible antes de cada consulta.',
      },
      {
        title: 'Odontograma interactivo',
        description: 'En la pestaña Resumen, el odontograma FDI permite registrar el estado de cada pieza dental: caries, restauracion, extraccion, implante, etc. con colores y animaciones.',
        benefit: 'Registro visual rapido del estado bucal. Se guarda automaticamente.',
        tip: 'Toca un diente para seleccionarlo, luego elige el estado. El boton flotante guarda los cambios.',
      },
      {
        title: 'Galeria de documentos',
        description: 'En la pestaña Archivos, subi radiografias, estudios y documentos del paciente. Las imagenes de WhatsApp se guardan automaticamente.',
        benefit: 'Todo el material clinico del paciente en un solo lugar.',
      },
      {
        title: 'Anamnesis digital',
        description: 'Cada paciente tiene un link unico de anamnesis que la IA envia automaticamente al agendar. El paciente completa su historial medico desde el celular.',
        benefit: 'Ahorra 10 minutos de consulta porque el paciente llega con la ficha completa.',
      },
      {
        title: 'Historial clinico',
        description: 'En la pestaña Historia, ve todos los registros clinicos con diagnosticos, notas y datos del odontograma por visita.',
        benefit: 'Contexto completo de cada atencion pasada.',
      },
      {
        title: 'Importacion masiva',
        description: 'Importa pacientes desde CSV o Excel con mapeo automatico de columnas. Detecta duplicados por telefono y te deja elegir: saltar o actualizar.',
        benefit: 'Migra tu base de pacientes existente en minutos.',
      },
    ],
  },
  '/chats': {
    icon: <MessageSquare size={22} />,
    title: 'Conversaciones',
    subtitle: 'WhatsApp, Instagram y Facebook en un solo lugar',
    steps: [
      {
        title: 'Bandeja unificada',
        description: 'Todas las conversaciones de WhatsApp, Instagram y Facebook en una sola bandeja. Ves el canal de cada conversacion con su icono.',
        benefit: 'No necesitas tener 3 apps abiertas. Todo llega aca.',
      },
      {
        title: 'IA conversacional',
        description: 'La IA responde automaticamente a los pacientes: agenda turnos, responde preguntas, hace triage de urgencias y envia fichas medicas.',
        benefit: 'Atencion 24/7 sin que vos tengas que estar conectada.',
        tip: 'La IA recuerda preferencias del paciente y detecta si es nuevo, existente o tiene turno.',
      },
      {
        title: 'Verificacion de comprobantes',
        description: 'Cuando un paciente envia una foto de un comprobante de transferencia, la IA lo analiza con vision: verifica titular, monto y confirma el turno automaticamente.',
        benefit: 'Cobro de senas verificado automaticamente, sin revisar cada comprobante.',
      },
      {
        title: 'Modo manual',
        description: 'Podes tomar control de cualquier conversacion con el boton "Manual". La IA se silencia por 24 horas para ese paciente.',
        benefit: 'Interveni cuando sea necesario sin que la IA interfiera.',
      },
      {
        title: 'Derivacion humana',
        description: 'Cuando la IA detecta una urgencia o el paciente pide hablar con una persona, te llega una notificacion y un email con todo el contexto.',
        benefit: 'Nunca te pierdas un caso critico.',
      },
      {
        title: 'Panel lateral del paciente',
        description: 'Al lado derecho de cada conversacion ves la ficha del paciente: proximo turno, anamnesis, historial y datos de contacto.',
        benefit: 'Contexto completo mientras hablas con el paciente.',
      },
    ],
  },
  '/aprobaciones': {
    icon: <ShieldCheck size={22} />,
    title: 'Staff',
    subtitle: 'Control de acceso de tu equipo',
    steps: [
      {
        title: 'Solicitudes pendientes',
        description: 'Cuando un profesional o secretaria se registra, su solicitud aparece aca para que la apruebes o rechaces.',
        benefit: 'Control total sobre quien accede a la plataforma.',
      },
      {
        title: 'Roles y permisos',
        description: 'CEO: acceso total. Profesional: ve su agenda y pacientes. Secretaria: gestiona turnos de todos.',
        benefit: 'Cada rol ve solo lo que necesita.',
      },
      {
        title: 'Suspender acceso',
        description: 'Podes suspender temporalmente el acceso de un miembro del equipo sin eliminar sus datos.',
        benefit: 'Gestion flexible del equipo.',
      },
    ],
  },
  '/sedes': {
    icon: <Stethoscope size={22} />,
    title: 'Sedes',
    subtitle: 'Configuracion de clinicas y horarios',
    steps: [
      {
        title: 'Datos de la clinica',
        description: 'Nombre, direccion, Google Maps, logo, telefono y datos bancarios para cobro de senas.',
        benefit: 'La IA usa estos datos para informar a los pacientes automaticamente.',
      },
      {
        title: 'Horarios por dia',
        description: 'Configura en que dias y horarios atiende la clinica. Podes tener diferentes horarios por dia y multiples turnos (manana y tarde).',
        benefit: 'La IA solo ofrece turnos dentro de estos horarios.',
      },
      {
        title: 'Multi-sede',
        description: 'Si operas en distintas ubicaciones segun el dia, configura la sede por dia con su direccion y link de Maps.',
        benefit: 'El paciente recibe automaticamente la direccion correcta segun el dia de su turno.',
      },
      {
        title: 'Precio de consulta',
        description: 'Configura el precio base de consulta. La IA lo informa automaticamente cuando el paciente pregunta. Podes configurar precio por profesional tambien.',
        benefit: 'Transparencia de precios sin intervencion manual.',
      },
      {
        title: 'Datos bancarios para senas',
        description: 'Configura CBU, alias y nombre del titular. La IA envia estos datos al paciente despues de agendar para que transfiera la sena (50% del precio).',
        benefit: 'Cobro automatizado de senas por transferencia bancaria.',
      },
      {
        title: 'Cantidad de sillones',
        description: 'Configura cuantos sillones/consultorios tiene la sede para controlar turnos simultaneos.',
        benefit: 'Evita agendar mas pacientes de los que podes atender al mismo tiempo.',
      },
    ],
  },
  '/analytics/professionals': {
    icon: <BarChart3 size={22} />,
    title: 'Analytics Estrategico',
    subtitle: 'Rendimiento de tu equipo con datos reales',
    steps: [
      {
        title: 'KPIs por profesional',
        description: 'Turnos totales, tasa de asistencia, no-shows, retencion de pacientes y facturacion estimada por cada profesional.',
        benefit: 'Identifica quien rinde mas y quien necesita atencion.',
      },
      {
        title: 'Tags inteligentes',
        description: 'El sistema asigna automaticamente tags como "High Performance", "Retention Master" o "Risk: Cancellations" basado en los datos reales.',
        benefit: 'Alertas tempranas de problemas y reconocimiento de excelencia.',
      },
      {
        title: 'Filtros de periodo',
        description: 'Selecciona rango de fechas y profesionales especificos para analizar.',
        benefit: 'Compara rendimiento mes a mes o trimestre a trimestre.',
      },
      {
        title: 'Tratamiento top y dia mas activo',
        description: 'Ve cual es el tratamiento que mas hace cada profesional y que dia de la semana tiene mas actividad.',
        benefit: 'Optimiza la agenda sabiendo cuando y que se demanda mas.',
      },
    ],
  },
  '/dashboard/status': {
    icon: <Zap size={22} />,
    title: 'Consumo de IA',
    subtitle: 'Tokens, costos y seleccion de modelos',
    steps: [
      {
        title: 'Consumo por servicio',
        description: 'Ve cuantos tokens consume cada servicio de IA: agente conversacional, memoria de pacientes, vision de comprobantes y Nova (voz).',
        benefit: 'Controla costos y optimiza el uso de IA.',
      },
      {
        title: 'Selector de modelos',
        description: 'Cambia el modelo de IA que usa cada servicio: agente de chat, Nova voz y extraccion de memoria. Modelos mas baratos para tareas simples.',
        benefit: 'Balancea calidad vs costo segun tu presupuesto.',
        tip: 'Nova puede usar gpt-4o-mini-realtime (economico) o gpt-4o-realtime (premium).',
      },
      {
        title: 'Grafico de uso diario',
        description: 'Ve el consumo de tokens dia a dia en un grafico de barras. Detecta picos de uso y tendencias.',
        benefit: 'Anticipa costos y ajusta modelos si se dispara el consumo.',
      },
    ],
  },
  '/tratamientos': {
    icon: <Clock size={22} />,
    title: 'Tratamientos',
    subtitle: 'Catalogo de servicios de tu clinica',
    steps: [
      {
        title: 'Lista de tratamientos',
        description: 'Todos los tratamientos disponibles con nombre, codigo, duracion, precio y categoria (prevencion, restauracion, cirugia, etc.).',
        benefit: 'La IA usa esta lista para ofrecer servicios a los pacientes.',
      },
      {
        title: 'Duracion y precio',
        description: 'Cada tratamiento tiene una duracion que determina cuanto espacio ocupa en la agenda, y un precio que la IA muestra al paciente.',
        benefit: 'Turnos correctamente dimensionados, sin solapamientos.',
      },
      {
        title: 'Asignacion de profesionales',
        description: 'Asigna que profesionales pueden realizar cada tratamiento. Si no asignas ninguno, todos pueden.',
        benefit: 'La IA solo ofrece turnos con el profesional correcto para cada tratamiento.',
        tip: 'La IA verifica la asignacion antes de agendar y le dice al paciente quien lo atendera.',
      },
      {
        title: 'Crear y editar',
        description: 'Agrega nuevos tratamientos, modifica precios, cambia duracion o desactiva los que ya no ofreces.',
        benefit: 'Mantene tu catalogo actualizado para que la IA siempre informe correctamente.',
      },
    ],
  },
  '/perfil': {
    icon: <User size={22} />,
    title: 'Mi Perfil',
    subtitle: 'Tus datos y configuracion personal',
    steps: [
      {
        title: 'Datos personales',
        description: 'Tu nombre, email, especialidad, telefono y matricula profesional.',
        benefit: 'Mantene tus datos actualizados para que aparezcan correctamente en confirmaciones.',
      },
      {
        title: 'Horario laboral propio',
        description: 'Configura tus propios horarios de atencion por dia, independientes de la clinica. La IA respeta estos horarios al ofrecer turnos.',
        benefit: 'No recibis turnos fuera de tu horario personal.',
      },
      {
        title: 'Precio de consulta propio',
        description: 'Si tu precio de consulta es diferente al de la clinica, configuralo aca. Tiene prioridad sobre el precio general.',
        benefit: 'Cada profesional puede tener su propio precio.',
      },
    ],
  },
  '/marketing': {
    icon: <Megaphone size={22} />,
    title: 'Marketing Hub',
    subtitle: 'ROI real de tus campanas publicitarias',
    steps: [
      {
        title: 'Atribucion de pacientes',
        description: 'Ve de que anuncio de Meta llego cada paciente. First-touch attribution: el primer anuncio que trajo al paciente queda registrado permanentemente.',
        benefit: 'Sabe exactamente cuanto retorno genera cada peso invertido en publicidad.',
      },
      {
        title: 'Metricas por campana',
        description: 'Inversion, costo por lead, costo por paciente convertido, impresiones, clicks y ROI por campana.',
        benefit: 'Deja de adivinar que anuncios funcionan. Los datos te lo dicen.',
      },
      {
        title: 'Conexion nativa con Meta Ads',
        description: 'Conecta tu cuenta de Meta Ads para importar automaticamente datos de campanas, creativos, gastos y leads.',
        benefit: 'Los datos se actualizan solos, sin carga manual.',
        tip: 'Nova puede consultarte cuanto gastaste en Meta Ads si le preguntas.',
      },
      {
        title: 'Campanas y creativos',
        description: 'Ve cada campana activa con sus creativos, nombres, gasto y rendimiento individual.',
        benefit: 'Identifica que creativo convierte mejor y escala lo que funciona.',
      },
    ],
  },
  '/leads': {
    icon: <Target size={22} />,
    title: 'Leads',
    subtitle: 'Seguimiento de prospectos',
    steps: [
      {
        title: 'Lista de leads',
        description: 'Todos los contactos que llegaron por Meta Ads, formularios o redes sociales, con su estado de conversion y canal de origen.',
        benefit: 'No pierdas ningun prospecto. Cada contacto tiene seguimiento.',
      },
      {
        title: 'Estado de conversion',
        description: 'Cada lead tiene un estado: nuevo, contactado, en seguimiento, convertido o perdido. Filtra y exporta por estado.',
        benefit: 'Visualiza tu embudo de ventas en tiempo real.',
      },
      {
        title: 'Recuperacion automatica',
        description: 'El sistema detecta leads que escribieron pero no agendaron, y envia mensajes de recuperacion automaticos.',
        benefit: 'Recupera pacientes que se iban a perder, sin esfuerzo manual.',
        tip: 'La ventana de recuperacion se configura por horas despues de la ultima interaccion.',
      },
    ],
  },
  '/templates': {
    icon: <Layout size={22} />,
    title: 'Automatizacion & HSM',
    subtitle: 'Reglas automaticas y plantillas de mensajes',
    steps: [
      {
        title: 'Reglas del sistema',
        description: 'Recordatorios de turno (24h antes), recuperacion de leads y feedback post-cita. Funcionan automaticamente.',
        benefit: 'Reduce no-shows hasta un 40% con recordatorios automaticos.',
      },
      {
        title: 'Reglas personalizadas',
        description: 'Crea tus propias reglas de automatizacion: mensajes por evento, canal, horario y tipo de mensaje.',
        benefit: 'Automatiza cualquier comunicacion repetitiva.',
      },
      {
        title: 'Plantillas HSM',
        description: 'Gestiona las plantillas de WhatsApp Business (HSM) para enviar mensajes fuera de la ventana de 24 horas.',
        benefit: 'Comunicate con pacientes que no escribieron recientemente.',
      },
      {
        title: 'Logs de envio',
        description: 'Historial completo de mensajes automaticos enviados: quien, cuando, por que canal y si fue entregado.',
        benefit: 'Auditoria completa de las automatizaciones.',
      },
    ],
  },
  '/configuracion': {
    icon: <Settings size={22} />,
    title: 'Configuracion',
    subtitle: 'Integraciones y ajustes avanzados',
    steps: [
      {
        title: 'WhatsApp (YCloud)',
        description: 'Conecta tu numero de WhatsApp Business via YCloud para que la IA reciba y envie mensajes automaticamente.',
        benefit: 'Tu clinica responde 24/7 por WhatsApp.',
      },
      {
        title: 'Google Calendar',
        description: 'Conecta Google Calendar para sincronizar turnos con el calendario personal de cada profesional.',
        benefit: 'Los profesionales ven sus turnos en su celular sin entrar a la plataforma.',
      },
      {
        title: 'Meta Ads',
        description: 'Conecta tu cuenta de Meta Business para importar datos de campanas, gastos y leads automaticamente.',
        benefit: 'Marketing con datos reales, sin carga manual.',
      },
      {
        title: 'FAQs del chatbot',
        description: 'Agrega preguntas frecuentes para que la IA las use al responder pacientes. Cuantas mas tengas, mejor responde.',
        benefit: 'La IA da respuestas precisas sobre temas especificos de tu clinica.',
        tip: 'Nova tambien puede agregar FAQs por voz: "Agrega una FAQ sobre horarios".',
      },
      {
        title: 'Configuracion de IA',
        description: 'Ajusta modelos, tono e idioma del agente. Selecciona modelo economico o premium segun necesidad.',
        benefit: 'Personaliza la IA a la identidad de tu clinica.',
      },
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
  const [completedPages, setCompletedPages] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem('onboarding_completed') || '[]');
    } catch { return []; }
  });

  const currentPath = Object.keys(GUIDES).find(path => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  }) || '/';

  const guide = GUIDES[currentPath];

  useEffect(() => {
    setCurrentStep(0);
  }, [currentPath]);

  if (!isOpen || !guide) return null;

  const step = guide.steps[currentStep];
  const isLastStep = currentStep === guide.steps.length - 1;

  const handleComplete = () => {
    const updated = [...new Set([...completedPages, currentPath])];
    setCompletedPages(updated);
    localStorage.setItem('onboarding_completed', JSON.stringify(updated));
    onClose();
  };

  const progress = ((currentStep + 1) / guide.steps.length) * 100;

  return (
    <>
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[200]" onClick={onClose} />

      <div
        className="fixed inset-y-0 right-0 w-full sm:w-[420px] bg-[#0a0e1a] border-l border-white/[0.06] shadow-2xl z-[201] flex flex-col"
        style={{ animation: 'slideInRight 0.3s cubic-bezier(0.16,1,0.3,1)' }}
      >
        {/* Header */}
        <div className="p-5 border-b border-white/[0.06] shrink-0">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400">
                {guide.icon}
              </div>
              <div>
                <h2 className="text-lg font-bold text-white">{guide.title}</h2>
                <p className="text-xs text-white/40">{guide.subtitle}</p>
              </div>
            </div>
            <button onClick={onClose} className="p-2 hover:bg-white/[0.06] rounded-xl transition-colors text-white/30 hover:text-white/60">
              <X size={20} />
            </button>
          </div>

          {/* Progress bar */}
          <div className="flex items-center gap-3">
            <div className="flex-1 h-1.5 bg-white/[0.06] rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-blue-500 to-cyan-400 rounded-full transition-all duration-500"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-white/30">{currentStep + 1}/{guide.steps.length}</span>
          </div>
        </div>

        {/* Step Content */}
        <div className="flex-1 overflow-y-auto p-5">
          <div key={currentStep} style={{ animation: 'fadeSlideUp 0.3s ease-out' }}>
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-blue-500 text-white flex items-center justify-center text-sm font-bold shadow-lg shadow-blue-500/20">
                {currentStep + 1}
              </div>
              <h3 className="text-base font-bold text-white">{step.title}</h3>
            </div>

            <p className="text-sm text-white/60 leading-relaxed mb-4">
              {step.description}
            </p>

            {/* Benefit */}
            <div className="bg-emerald-500/[0.07] border border-emerald-500/20 rounded-xl p-4 mb-4">
              <div className="flex items-start gap-2">
                <Sparkles size={16} className="text-emerald-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider mb-1">Beneficio</p>
                  <p className="text-sm text-emerald-300/80">{step.benefit}</p>
                </div>
              </div>
            </div>

            {/* Tip */}
            {step.tip && (
              <div className="bg-amber-500/[0.07] border border-amber-500/20 rounded-xl p-4">
                <div className="flex items-start gap-2">
                  <BookOpen size={16} className="text-amber-400 mt-0.5 shrink-0" />
                  <div>
                    <p className="text-[10px] font-bold text-amber-400 uppercase tracking-wider mb-1">Tip</p>
                    <p className="text-sm text-amber-300/80">{step.tip}</p>
                  </div>
                </div>
              </div>
            )}

            {/* Step dots */}
            <div className="flex items-center justify-center gap-1.5 mt-6">
              {guide.steps.map((_, i) => (
                <button
                  key={i}
                  onClick={() => setCurrentStep(i)}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    i === currentStep ? 'w-6 bg-blue-500' : i < currentStep ? 'w-1.5 bg-blue-500/40' : 'w-1.5 bg-white/[0.10]'
                  }`}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Navigation */}
        <div className="p-5 border-t border-white/[0.06] shrink-0 flex items-center justify-between">
          <button
            onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
            disabled={currentStep === 0}
            className="flex items-center gap-1 px-4 py-2 rounded-xl text-sm font-medium text-white/40 hover:bg-white/[0.06] transition-colors disabled:opacity-20 disabled:pointer-events-none"
          >
            <ChevronLeft size={16} /> Anterior
          </button>

          {isLastStep ? (
            <button
              onClick={handleComplete}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold bg-gradient-to-r from-blue-500 to-cyan-400 text-white hover:shadow-lg hover:shadow-blue-500/20 transition-all active:scale-95"
            >
              <CheckCircle size={16} /> Entendido
            </button>
          ) : (
            <button
              onClick={() => setCurrentStep(currentStep + 1)}
              className="flex items-center gap-1 px-5 py-2.5 rounded-xl text-sm font-semibold bg-white/[0.08] text-white border border-white/[0.10] hover:bg-white/[0.12] transition-all active:scale-95"
            >
              Siguiente <ChevronRight size={16} />
            </button>
          )}
        </div>
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); }
          to { transform: translateX(0); }
        }
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </>
  );
};

export default OnboardingGuide;
