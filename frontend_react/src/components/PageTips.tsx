import { useState, useEffect } from 'react';
import { X, Lightbulb, ArrowRight } from 'lucide-react';
import { useLocation } from 'react-router-dom';

interface Tip {
  id: string;
  message: string;
  position: 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right' | 'center';
  delay: number; // ms before showing
  duration: number; // ms before auto-hide
  icon?: string; // emoji
}

interface PageTipsConfig {
  [path: string]: Tip[];
}

const TIPS: PageTipsConfig = {
  '/': [
    { id: 'dash-1', message: 'Los KPIs se actualizan en tiempo real cuando el agente de IA agenda turnos o cobra pagos.', position: 'top-left', delay: 2000, duration: 6000, icon: '📊' },
    { id: 'dash-2', message: 'Revisá "Pagos Pendientes" para ver cuánto falta cobrar. Tocá Nova para gestionar cobros por voz.', position: 'bottom-right', delay: 10000, duration: 6000, icon: '💰' },
  ],
  '/agenda': [
    { id: 'agenda-1', message: 'Los puntos de colores en cada turno indican el estado de pago: verde=pagado, amarillo=parcial, rojo=pendiente.', position: 'top-left', delay: 2000, duration: 7000, icon: '🔴' },
    { id: 'agenda-2', message: 'Tocá cualquier turno para ver la facturación, el comprobante de pago y la anamnesis del paciente.', position: 'center', delay: 11000, duration: 6000, icon: '📋' },
    { id: 'agenda-3', message: 'Si ves "ALERTA" rojo en un turno, el paciente tiene condiciones médicas importantes. Revisá su ficha.', position: 'top-right', delay: 19000, duration: 6000, icon: '⚠️' },
  ],
  '/pacientes': [
    { id: 'pac-1', message: 'La columna "Próximo turno" muestra cuándo tiene turno cada paciente. "Balance" muestra deudas pendientes.', position: 'top-right', delay: 2000, duration: 7000, icon: '📅' },
    { id: 'pac-2', message: 'Podés importar pacientes masivamente desde Excel o CSV. Hasta 1000 pacientes por archivo.', position: 'top-left', delay: 11000, duration: 6000, icon: '📤' },
    { id: 'pac-3', message: 'Usá la búsqueda semántica (ícono cerebro) para buscar pacientes por condición médica: "diabetes", "embarazo", etc.', position: 'center', delay: 19000, duration: 6000, icon: '🧠' },
  ],
  '/chats': [
    { id: 'chat-1', message: 'Los chats se actualizan en tiempo real. El agente de IA responde automáticamente a pacientes por WhatsApp, Instagram y Facebook.', position: 'top-left', delay: 2000, duration: 7000, icon: '💬' },
    { id: 'chat-2', message: 'Tocá "Manual" para tomar el control de un chat. La IA se silencia 24 horas cuando un humano interviene.', position: 'center', delay: 11000, duration: 6000, icon: '🤝' },
    { id: 'chat-3', message: 'Si el candado aparece en un chat, la ventana de 24hs de WhatsApp está cerrada. Se necesita un template para contactar.', position: 'bottom-left', delay: 19000, duration: 6000, icon: '🔒' },
  ],
  '/tratamientos': [
    { id: 'trat-1', message: 'Cada tratamiento tiene un precio base que se usa para calcular el monto a cobrar en los turnos.', position: 'top-left', delay: 2000, duration: 6000, icon: '💵' },
    { id: 'trat-2', message: 'Asigná profesionales específicos a cada tratamiento. Si no asignás ninguno, todos pueden atenderlo.', position: 'center', delay: 10000, duration: 6000, icon: '👨‍⚕️' },
  ],
  '/marketing': [
    { id: 'mkt-1', message: 'Conectá tu cuenta de Meta Ads para ver el ROI real: cuánto invertiste vs cuántos pacientes convirtieron.', position: 'top-left', delay: 2000, duration: 7000, icon: '📈' },
    { id: 'mkt-2', message: 'Los leads se atribuyen automáticamente a la campaña/anuncio que los trajo. Filtrá por período para ver tendencias.', position: 'center', delay: 11000, duration: 6000, icon: '🎯' },
  ],
  '/configuracion': [
    { id: 'conf-1', message: 'Configurá los datos bancarios (CBU, Alias, Titular) para que el agente de IA pueda cobrar señas automáticamente.', position: 'top-left', delay: 2000, duration: 7000, icon: '🏦' },
    { id: 'conf-2', message: 'Las FAQs que cargues acá las usa el agente de IA para responder preguntas frecuentes de pacientes.', position: 'center', delay: 11000, duration: 6000, icon: '❓' },
  ],
  '/personal': [
    { id: 'staff-1', message: 'Cada profesional puede tener su propio precio de consulta y horarios independientes de la clínica.', position: 'top-left', delay: 2000, duration: 7000, icon: '👩‍⚕️' },
    { id: 'staff-2', message: 'La seña que paga el paciente es el 50% del precio de consulta del profesional que lo atiende.', position: 'center', delay: 10000, duration: 6000, icon: '💳' },
  ],
};

// Position classes for each tip position
const POSITION_CLASSES: Record<string, string> = {
  'top-left': 'top-20 left-4 sm:left-8',
  'top-right': 'top-20 right-4 sm:right-24',
  'bottom-left': 'bottom-24 left-4 sm:left-8',
  'bottom-right': 'bottom-24 right-4 sm:right-24',
  'center': 'top-1/3 left-1/2 -translate-x-1/2',
};

export default function PageTips() {
  const location = useLocation();
  const [activeTip, setActiveTip] = useState<Tip | null>(null);
  const [tipIndex, setTipIndex] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  // Get current page path (normalize)
  const currentPath = location.pathname.replace(/\/$/, '') || '/';

  // Get tips for current page
  const pageTips = TIPS[currentPath] || [];

  useEffect(() => {
    // Reset on page change
    setActiveTip(null);
    setTipIndex(0);
    setDismissed(false);
  }, [currentPath]);

  useEffect(() => {
    if (dismissed || pageTips.length === 0 || tipIndex >= pageTips.length) return;

    // Check if tips were already shown for this page in this session
    const shownKey = `tips_shown_${currentPath}`;
    if (sessionStorage.getItem(shownKey)) return;

    const tip = pageTips[tipIndex];
    const showTimer = setTimeout(() => {
      setActiveTip(tip);
    }, tip.delay);

    return () => clearTimeout(showTimer);
  }, [tipIndex, dismissed, currentPath, pageTips]);

  useEffect(() => {
    if (!activeTip) return;

    const hideTimer = setTimeout(() => {
      setActiveTip(null);
      // Show next tip after a short gap
      setTimeout(() => {
        setTipIndex(prev => prev + 1);
      }, 1000);
    }, activeTip.duration);

    return () => clearTimeout(hideTimer);
  }, [activeTip]);

  const handleDismissAll = () => {
    setActiveTip(null);
    setDismissed(true);
    const shownKey = `tips_shown_${currentPath}`;
    sessionStorage.setItem(shownKey, '1');
  };

  const handleNext = () => {
    setActiveTip(null);
    setTimeout(() => {
      setTipIndex(prev => prev + 1);
    }, 300);
  };

  if (!activeTip) return null;

  return (
    <div
      className={`fixed z-[90] max-w-sm w-[calc(100%-2rem)] sm:w-auto ${POSITION_CLASSES[activeTip.position]}`}
      style={{ animation: 'tooltipIn 0.4s cubic-bezier(0.16,1,0.3,1)' }}
    >
      <div className="relative bg-[#0d1117]/95 backdrop-blur-2xl border border-white/[0.1] rounded-2xl shadow-2xl shadow-black/40 p-4 overflow-hidden">
        {/* Gradient accent top */}
        <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-blue-500 via-cyan-400 to-blue-500" />

        {/* Content */}
        <div className="flex items-start gap-3">
          <span className="text-xl shrink-0 mt-0.5">{activeTip.icon || '💡'}</span>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-white/90 leading-relaxed">{activeTip.message}</p>
            <div className="flex items-center gap-3 mt-3">
              {tipIndex < pageTips.length - 1 && (
                <button
                  onClick={handleNext}
                  className="flex items-center gap-1 text-[10px] font-bold text-blue-400 hover:text-blue-300 uppercase tracking-wider transition-colors"
                >
                  Siguiente <ArrowRight size={10} />
                </button>
              )}
              <button
                onClick={handleDismissAll}
                className="text-[10px] font-bold text-white/30 hover:text-white/60 uppercase tracking-wider transition-colors ml-auto"
              >
                Cerrar tips
              </button>
            </div>
          </div>
          <button
            onClick={handleDismissAll}
            className="shrink-0 p-1 rounded-full hover:bg-white/[0.08] text-white/30 hover:text-white/60 transition-all"
          >
            <X size={14} />
          </button>
        </div>

        {/* Progress dots */}
        <div className="flex items-center justify-center gap-1.5 mt-3">
          {pageTips.map((_, i) => (
            <div
              key={i}
              className={`h-1 rounded-full transition-all duration-300 ${
                i === tipIndex ? 'w-4 bg-blue-400' : i < tipIndex ? 'w-1.5 bg-blue-400/40' : 'w-1.5 bg-white/10'
              }`}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
