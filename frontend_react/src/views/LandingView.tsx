import React from 'react';
import { Link } from 'react-router-dom';
import { Shield, MessageCircle, LogIn, Sparkles, Calendar, BarChart3, Zap, ChevronDown } from 'lucide-react';

const WHATSAPP_NUMBER = '5493435256815';
const WHATSAPP_PREDEFINED_MESSAGE = 'Hola, quisiera consultar por turnos para limpieza dental.';
const WHATSAPP_URL = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(WHATSAPP_PREDEFINED_MESSAGE)}`;

export default function LandingView() {
  return (
    <div className="landing-root min-h-screen min-h-[100dvh] flex flex-col bg-gradient-to-b from-slate-50 via-white to-medical-50/20">
      {/* Safe area + padding móvil */}
      <main className="flex-1 flex flex-col items-center justify-center w-full px-4 py-8 sm:p-6 md:p-8 pb-12 sm:pb-16">
        <div className="w-full max-w-md sm:max-w-lg mx-auto space-y-6 sm:space-y-8">
          {/* Hero */}
          <header className="text-center pt-2 sm:pt-0">
            <div className="inline-flex items-center justify-center w-14 h-14 sm:w-16 sm:h-16 rounded-2xl bg-medical-600 text-white shadow-xl shadow-medical-600/25 mb-4 sm:mb-5 ring-4 ring-medical-600/10">
              <Shield size={28} className="sm:w-8 sm:h-8" strokeWidth={2} />
            </div>
            <p className="text-xs sm:text-sm font-semibold text-medical-600 uppercase tracking-widest mb-2">
              Plataforma para clínicas dentales
            </p>
            <h1 className="text-2xl sm:text-3xl md:text-4xl font-bold text-gray-900 tracking-tight leading-tight">
              Agenda, pacientes e IA en una sola app
            </h1>
            <p className="mt-3 sm:mt-4 text-sm sm:text-base text-gray-600 max-w-sm mx-auto leading-relaxed">
              Probá la plataforma en un clic. Sin tarjeta. Acceso inmediato a la demo.
            </p>
          </header>

          {/* CTA principal — arriba del pliegue en móvil */}
          <div className="space-y-3 sm:space-y-4">
            <Link
              to="/login?demo=1"
              className="landing-cta-primary flex items-center justify-center gap-3 w-full rounded-2xl py-4 sm:py-5 text-base sm:text-lg font-bold text-white bg-medical-600 hover:bg-medical-700 active:scale-[0.98] transition-all shadow-xl shadow-medical-600/25 hover:shadow-medical-600/30 min-h-[52px] sm:min-h-[56px] touch-manipulation"
            >
              <Zap size={22} className="shrink-0" />
              Probar app
            </Link>
            <p className="text-center text-xs text-gray-500 px-2">
              Te logueamos automáticamente en la cuenta demo (sin exponer credenciales en la interfaz)
            </p>
          </div>

          {/* Card glass: beneficios + credenciales */}
          <section className="landing-glass rounded-2xl sm:rounded-3xl border border-gray-200/80 shadow-card overflow-hidden">
            <div className="p-4 sm:p-6 space-y-4 sm:space-y-5">
              <h2 className="text-base sm:text-lg font-semibold text-gray-800 flex items-center gap-2">
                <Sparkles className="text-medical-600 shrink-0" size={20} />
                Qué incluye la demo
              </h2>
              <ul className="space-y-2.5 sm:space-y-3 text-gray-700 text-sm sm:text-base">
                <li className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-8 h-8 rounded-xl bg-medical-50 text-medical-600 shrink-0">
                    <Calendar size={16} />
                  </span>
                  <span>Agenda por sede y profesional, sincronizable con Google Calendar.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-8 h-8 rounded-xl bg-medical-50 text-medical-600 shrink-0">
                    <MessageCircle size={16} />
                  </span>
                  <span>Agente IA por WhatsApp: turnos, triaje y derivación a humano.</span>
                </li>
                <li className="flex items-start gap-3">
                  <span className="flex items-center justify-center w-8 h-8 rounded-xl bg-medical-50 text-medical-600 shrink-0">
                    <BarChart3 size={16} />
                  </span>
                  <span>Analíticas para CEO y profesionales.</span>
                </li>
              </ul>
              <details className="group">
                <summary className="flex items-center justify-between gap-2 py-2 cursor-pointer list-none text-sm font-medium text-gray-600 hover:text-gray-800 select-none touch-manipulation min-h-[44px]">
                  <span>Credenciales de prueba</span>
                  <ChevronDown size={18} className="shrink-0 transition-transform group-open:rotate-180 text-medical-600" />
                </summary>
                <div className="mt-2 pt-3 border-t border-gray-100 rounded-xl bg-gray-50/80 px-4 py-3 text-sm text-gray-700 font-mono">
                  <p><span className="text-gray-500">Email:</span> [REDACTED]</p>
                  <p className="mt-1"><span className="text-gray-500">Contraseña:</span> [REDACTED]</p>
                </div>
              </details>
            </div>
          </section>

          {/* CTAs secundarios */}
          <div className="space-y-3 sm:space-y-4">
            <a
              href={WHATSAPP_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center justify-center gap-3 w-full rounded-2xl py-3.5 sm:py-4 text-sm sm:text-base font-semibold border-2 border-medical-600 text-medical-600 bg-white hover:bg-medical-50 active:scale-[0.98] transition-all min-h-[48px] touch-manipulation"
            >
              <MessageCircle size={20} className="shrink-0" />
              Probar Agente IA por WhatsApp
            </a>
            <div className="pt-2">
              <Link
                to="/login"
                className="flex items-center justify-center gap-2 w-full rounded-xl py-3 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors min-h-[44px] touch-manipulation"
              >
                <LogIn size={18} />
                Iniciar sesión con mi cuenta
              </Link>
            </div>
          </div>
        </div>
      </main>

      <style>{`
        .landing-root {
          -webkit-tap-highlight-color: transparent;
        }
        .landing-glass {
          background: white;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
          transition: box-shadow 0.3s ease, border-color 0.3s ease;
        }
        .landing-glass:hover {
          box-shadow: 0 10px 25px -5px rgba(0, 89, 179, 0.08), 0 4px 10px -2px rgba(0, 0, 0, 0.04);
          border-color: rgba(0, 89, 179, 0.2);
        }
        .landing-cta-primary:active {
          transform: scale(0.98);
        }
        @media (max-width: 640px) {
          .landing-root {
            padding-bottom: env(safe-area-inset-bottom, 0);
          }
        }
      `}</style>
    </div>
  );
}
