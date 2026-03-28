import { useState, useEffect, useCallback } from 'react';
import { X } from 'lucide-react';
import { useLocation } from 'react-router-dom';

interface PageHint {
  id: string;
  text: string;
  icon: string;
  color: 'blue' | 'violet' | 'emerald' | 'amber' | 'rose';
}

const COLOR_MAP = {
  blue: { bg: 'bg-blue-500/10', border: 'border-blue-500/20', text: 'text-blue-400' },
  violet: { bg: 'bg-violet-500/10', border: 'border-violet-500/20', text: 'text-violet-400' },
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400' },
  amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400' },
  rose: { bg: 'bg-rose-500/10', border: 'border-rose-500/20', text: 'text-rose-400' },
};

// One tip per page, shown inline below the header — never overlaps content
const HINTS: Record<string, PageHint> = {
  '/': { id: 'dash', text: 'Los KPIs se actualizan en vivo. "Pagos Pendientes" muestra cuánto falta cobrar.', icon: '📊', color: 'blue' },
  '/agenda': { id: 'agenda', text: '🟢 Pagado  🟡 Parcial  🔴 Pendiente — Tocá un turno para ver facturación.', icon: '🎯', color: 'blue' },
  '/pacientes': { id: 'pac', text: '"Próximo turno" y "Balance" muestran turnos y deudas de cada paciente.', icon: '📅', color: 'emerald' },
  '/chats': { id: 'chat', text: 'Chats en tiempo real. Tocá "Manual" para tomar el control de una conversación.', icon: '💬', color: 'violet' },
  '/tratamientos': { id: 'trat', text: 'El precio base se usa para calcular el monto a cobrar en turnos.', icon: '💵', color: 'emerald' },
  '/marketing': { id: 'mkt', text: 'Conectá Meta Ads para ver ROI: inversión vs pacientes convertidos.', icon: '📈', color: 'violet' },
  '/configuracion': { id: 'conf', text: 'Configurá datos bancarios para que la IA cobre señas automáticamente.', icon: '🏦', color: 'blue' },
  '/personal': { id: 'staff', text: 'Cada profesional tiene su precio. La seña es el 50% de ese valor.', icon: '👩‍⚕️', color: 'amber' },
};

const MAX_SHOWS = 5;
const VISIBLE_DURATION = 5000; // 5 seconds
const APPEAR_DELAY = 1500; // 1.5s after page load

function getShowCount(): number {
  try {
    return parseInt(localStorage.getItem('page_tips_count') || '0', 10);
  } catch { return 0; }
}

function incrementShowCount(): void {
  try {
    const count = getShowCount() + 1;
    localStorage.setItem('page_tips_count', String(count));
  } catch {}
}

export default function PageTips() {
  const location = useLocation();
  const path = location.pathname.replace(/\/$/, '') || '/';
  const hint = HINTS[path];

  const [visible, setVisible] = useState(false);
  const [exiting, setExiting] = useState(false);

  const dismiss = useCallback(() => {
    setExiting(true);
    setTimeout(() => {
      setVisible(false);
      setExiting(false);
    }, 300);
  }, []);

  useEffect(() => {
    setVisible(false);
    setExiting(false);

    if (!hint) return;
    if (getShowCount() >= MAX_SHOWS) return;

    const showTimer = setTimeout(() => {
      setVisible(true);
      incrementShowCount();
    }, APPEAR_DELAY);

    return () => clearTimeout(showTimer);
  }, [path, hint]);

  // Auto-dismiss after 3 seconds
  useEffect(() => {
    if (!visible || exiting) return;
    const hideTimer = setTimeout(dismiss, VISIBLE_DURATION);
    return () => clearTimeout(hideTimer);
  }, [visible, exiting, dismiss]);

  if (!visible || !hint) return null;

  const c = COLOR_MAP[hint.color];

  return (
    <>
      <div
        className="fixed z-[80] left-4 right-4 sm:left-auto sm:right-8 sm:max-w-md"
        style={{
          top: 'calc(env(safe-area-inset-top, 0px) + 56px)',
          animation: exiting ? 'tipSlideOut 0.3s ease-in forwards' : 'tipSlideIn 0.4s cubic-bezier(0.16,1,0.3,1)',
        }}
      >
        <div className={`flex items-center gap-2.5 px-4 py-2.5 rounded-xl ${c.bg} border ${c.border} backdrop-blur-xl shadow-lg shadow-black/20`}>
          <span className="text-base shrink-0">{hint.icon}</span>
          <p className={`text-[12px] leading-snug font-medium ${c.text} flex-1`}>{hint.text}</p>
          <button
            onClick={dismiss}
            className={`shrink-0 p-1 rounded-full hover:bg-white/[0.1] ${c.text} opacity-50 hover:opacity-100 transition-all`}
          >
            <X size={12} />
          </button>
        </div>
      </div>

      <style>{`
        @keyframes tipSlideIn {
          0% { opacity: 0; transform: translateY(-12px) scale(0.95); }
          100% { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes tipSlideOut {
          0% { opacity: 1; transform: translateY(0) scale(1); }
          100% { opacity: 0; transform: translateY(-8px) scale(0.97); }
        }
      `}</style>
    </>
  );
}
