/**
 * PageTips — Animated contextual hints that live permanently on each page.
 * Similar to Nova's wobble/ping animations, these highlight important data
 * and actions with constant subtle motion to give the page "life".
 *
 * Each page has floating animated badges/pills that point to key features.
 * They appear after a short delay and stay visible with gentle animations.
 * Can be dismissed individually, remembered per session.
 */
import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { useLocation } from 'react-router-dom';

interface PageHint {
  id: string;
  text: string;
  icon: string;
  position: string; // Tailwind positioning classes
  animation: 'wobble' | 'pulse' | 'bounce' | 'glow' | 'float';
  color: 'blue' | 'violet' | 'emerald' | 'amber' | 'rose';
  delay: number; // seconds before appearing
}

const COLOR_MAP = {
  blue: { bg: 'bg-blue-500/10', border: 'border-blue-500/20', text: 'text-blue-400', ping: 'border-blue-400/30' },
  violet: { bg: 'bg-violet-500/10', border: 'border-violet-500/20', text: 'text-violet-400', ping: 'border-violet-400/30' },
  emerald: { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400', ping: 'border-emerald-400/30' },
  amber: { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400', ping: 'border-amber-400/30' },
  rose: { bg: 'bg-rose-500/10', border: 'border-rose-500/20', text: 'text-rose-400', ping: 'border-rose-400/30' },
};

const ANIM_MAP = {
  wobble: 'animate-[hintWobble_4s_ease-in-out_infinite]',
  pulse: 'animate-pulse',
  bounce: 'animate-[hintBounce_3s_ease-in-out_infinite]',
  glow: 'animate-[hintGlow_3s_ease-in-out_infinite]',
  float: 'animate-[hintFloat_5s_ease-in-out_infinite]',
};

const HINTS: Record<string, PageHint[]> = {
  '/': [
    { id: 'dash-kpi', text: 'KPIs en vivo', icon: '📊', position: 'top-[140px] left-4 sm:left-8', animation: 'glow', color: 'blue', delay: 2 },
    { id: 'dash-pending', text: 'Pagos por cobrar', icon: '💰', position: 'top-[140px] right-4 sm:right-8', animation: 'pulse', color: 'amber', delay: 4 },
  ],
  '/agenda': [
    { id: 'ag-dots', text: '🟢 Pagado  🟡 Parcial  🔴 Pendiente', icon: '🎯', position: 'top-[85px] left-4 sm:left-[280px]', animation: 'float', color: 'blue', delay: 2 },
    { id: 'ag-alert', text: 'Alertas médicas activas', icon: '⚠️', position: 'top-[85px] right-4 sm:right-8', animation: 'bounce', color: 'rose', delay: 5 },
  ],
  '/pacientes': [
    { id: 'pac-cols', text: 'Próximo turno + Balance', icon: '📅', position: 'top-[160px] right-4 sm:right-8', animation: 'glow', color: 'emerald', delay: 2 },
    { id: 'pac-import', text: 'Importar desde Excel', icon: '📤', position: 'top-[85px] right-4 sm:right-[200px]', animation: 'wobble', color: 'violet', delay: 4 },
  ],
  '/chats': [
    { id: 'chat-live', text: 'Chats en tiempo real', icon: '💬', position: 'top-[85px] left-4 sm:left-[280px]', animation: 'pulse', color: 'blue', delay: 2 },
    { id: 'chat-manual', text: 'Tocá Manual para intervenir', icon: '🤝', position: 'top-[85px] right-4 sm:right-8', animation: 'float', color: 'amber', delay: 4 },
  ],
  '/tratamientos': [
    { id: 'trat-price', text: 'Precio base → Monto del turno', icon: '💵', position: 'top-[85px] right-4 sm:right-8', animation: 'glow', color: 'emerald', delay: 2 },
  ],
  '/marketing': [
    { id: 'mkt-roi', text: 'ROI en tiempo real', icon: '📈', position: 'top-[85px] left-4 sm:left-8', animation: 'float', color: 'violet', delay: 2 },
  ],
  '/configuracion': [
    { id: 'conf-bank', text: 'Datos bancarios → Cobro automático', icon: '🏦', position: 'top-[85px] left-4 sm:left-8', animation: 'glow', color: 'blue', delay: 2 },
  ],
  '/personal': [
    { id: 'staff-price', text: 'Precio por profesional → Seña 50%', icon: '👩‍⚕️', position: 'top-[85px] left-4 sm:left-8', animation: 'wobble', color: 'violet', delay: 2 },
  ],
};

export default function PageTips() {
  const location = useLocation();
  const path = location.pathname.replace(/\/$/, '') || '/';
  const hints = HINTS[path] || [];

  const [visibleHints, setVisibleHints] = useState<Set<string>>(new Set());
  const [dismissedHints, setDismissedHints] = useState<Set<string>>(new Set());

  // Reset on page change
  useEffect(() => {
    setVisibleHints(new Set());

    // Load dismissed from session
    const key = `hints_dismissed_${path}`;
    const stored = sessionStorage.getItem(key);
    setDismissedHints(stored ? new Set(JSON.parse(stored)) : new Set());

    // Schedule each hint to appear
    const timers = hints.map(hint => {
      return setTimeout(() => {
        setVisibleHints(prev => new Set(prev).add(hint.id));
      }, hint.delay * 1000);
    });

    return () => timers.forEach(clearTimeout);
  }, [path]);

  const dismiss = (id: string) => {
    setVisibleHints(prev => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
    setDismissedHints(prev => {
      const next = new Set(prev).add(id);
      const key = `hints_dismissed_${path}`;
      sessionStorage.setItem(key, JSON.stringify([...next]));
      return next;
    });
  };

  return (
    <>
      {hints.map(hint => {
        if (!visibleHints.has(hint.id) || dismissedHints.has(hint.id)) return null;
        const c = COLOR_MAP[hint.color];
        const anim = ANIM_MAP[hint.animation];

        return (
          <div
            key={hint.id}
            className={`fixed z-[80] ${hint.position} pointer-events-auto`}
            style={{ animation: 'hintAppear 0.5s cubic-bezier(0.16,1,0.3,1)' }}
          >
            <div className={`${anim} relative`}>
              {/* Ping ring */}
              <div className={`absolute inset-0 rounded-full border-2 ${c.ping} animate-[novaPing_3s_ease-out_infinite] pointer-events-none`} />

              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full ${c.bg} border ${c.border} backdrop-blur-xl shadow-lg cursor-default group`}>
                <span className="text-sm">{hint.icon}</span>
                <span className={`text-[11px] font-semibold ${c.text} whitespace-nowrap`}>{hint.text}</span>
                <button
                  onClick={() => dismiss(hint.id)}
                  className={`ml-1 p-0.5 rounded-full opacity-0 group-hover:opacity-100 hover:bg-white/[0.1] ${c.text} transition-all duration-200`}
                >
                  <X size={10} />
                </button>
              </div>
            </div>
          </div>
        );
      })}

      <style>{`
        @keyframes hintAppear {
          0% { opacity: 0; transform: scale(0.7) translateY(8px); }
          60% { opacity: 1; transform: scale(1.05) translateY(-2px); }
          100% { opacity: 1; transform: scale(1) translateY(0); }
        }
        @keyframes hintWobble {
          0%, 100% { transform: rotate(0deg) scale(1); }
          10% { transform: rotate(-3deg) scale(1.05); }
          20% { transform: rotate(3deg) scale(1.05); }
          30% { transform: rotate(-2deg) scale(1.02); }
          40%, 100% { transform: rotate(0deg) scale(1); }
        }
        @keyframes hintBounce {
          0%, 100% { transform: translateY(0); }
          50% { transform: translateY(-6px); }
        }
        @keyframes hintGlow {
          0%, 100% { filter: brightness(1); }
          50% { filter: brightness(1.3); }
        }
        @keyframes hintFloat {
          0%, 100% { transform: translateY(0) translateX(0); }
          25% { transform: translateY(-4px) translateX(2px); }
          75% { transform: translateY(2px) translateX(-2px); }
        }
      `}</style>
    </>
  );
}
