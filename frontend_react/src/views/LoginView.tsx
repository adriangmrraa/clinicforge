import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';
import {
  Lock, Mail, Shield, AlertCircle, CheckCircle,
  Info, User, Phone, Building2, Stethoscope, CalendarDays, BadgeCheck, ArrowRight, ChevronRight,
  Sparkles, Zap, BarChart3, MessageCircle, Eye, EyeOff
} from 'lucide-react';

const DEMO_EMAIL = 'gamarraadrian200@gmail.com';
const DEMO_PASSWORD = 'Wstg1793.';

const SPECIALTIES: { value: string; key: string }[] = [
  { value: 'Odontología General', key: 'specialty_general' },
  { value: 'Ortodoncia', key: 'specialty_orthodontics' },
  { value: 'Endodoncia', key: 'specialty_endodontics' },
  { value: 'Periodoncia', key: 'specialty_periodontics' },
  { value: 'Cirugía Oral', key: 'specialty_oral_surgery' },
  { value: 'Prótesis Dental', key: 'specialty_prosthodontics' },
  { value: 'Odontopediatría', key: 'specialty_pediatric' },
  { value: 'Implantología', key: 'specialty_implantology' },
  { value: 'Estética Dental', key: 'specialty_aesthetic' },
];

interface ClinicOption {
  id: number;
  clinic_name: string;
}

const TOOLTIPS: Record<string, string> = {
  email: 'Usa tu email profesional. Sera tu usuario de acceso.',
  password: 'Minimo 8 caracteres. Usa letras y numeros.',
  role: 'Profesional: acceso a agenda y pacientes. Secretaria: gestion de turnos. CEO: acceso total.',
  clinic: 'Selecciona la clinica donde trabajas. El CEO te debe aprobar.',
  specialty: 'Tu area de expertise. Aparecera en tu perfil publico.',
  phone: 'Para que la clinica pueda contactarte.',
  registration_id: 'Numero de matricula profesional. Opcional.',
  google_calendar: 'ID de tu calendario. Se configura despues desde el panel.',
};

/* ── Inline styles for CSS animations (no external CSS needed) ── */
const keyframesStyle = `
@keyframes float {
  0%, 100% { transform: translateY(0px) rotate(0deg); }
  33% { transform: translateY(-20px) rotate(1deg); }
  66% { transform: translateY(10px) rotate(-1deg); }
}
@keyframes float-delayed {
  0%, 100% { transform: translateY(0px) rotate(0deg); }
  33% { transform: translateY(15px) rotate(-1deg); }
  66% { transform: translateY(-25px) rotate(1deg); }
}
@keyframes shimmer {
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
}
@keyframes glow-pulse {
  0%, 100% { opacity: 0.4; }
  50% { opacity: 0.8; }
}
@keyframes slide-up {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes grid-fade {
  0%, 100% { opacity: 0.03; }
  50% { opacity: 0.06; }
}
@keyframes orbit {
  from { transform: rotate(0deg) translateX(140px) rotate(0deg); }
  to { transform: rotate(360deg) translateX(140px) rotate(-360deg); }
}
@keyframes count-up {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes img-fade-in {
  from { opacity: 0; transform: scale(1.08); }
  to { opacity: 1; transform: scale(1); }
}
@keyframes img-fade-out {
  from { opacity: 1; transform: scale(1); }
  to { opacity: 0; transform: scale(1.04); }
}
@keyframes ken-burns {
  0% { transform: scale(1); }
  100% { transform: scale(1.12); }
}
`;

/* ── Showcase images — dental/clinic/tech themed ── */
const SHOWCASE_IMAGES = [
  'https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=800&q=80', // dental clinic modern
  'https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=800&q=80', // dentist working
  'https://images.unsplash.com/photo-1606811971618-4486d14f3f99?w=800&q=80', // dental tools
  'https://images.unsplash.com/photo-1576091160550-2173dba999ef?w=800&q=80', // medical tech
  'https://images.unsplash.com/photo-1551076805-e1869033e561?w=800&q=80', // doctor tablet
  'https://images.unsplash.com/photo-1559757175-5700dde675bc?w=800&q=80', // dental chair
  'https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=800&q=80', // medical tech
  'https://images.unsplash.com/photo-1631217868264-e5b90bb7e133?w=800&q=80', // modern clinic
  'https://images.unsplash.com/photo-1516549655169-df83a0774514?w=800&q=80', // healthcare
  'https://images.unsplash.com/photo-1530497610245-94d3c16cda28?w=800&q=80', // smile dental
];

/* ── Image Carousel with crossfade ── */
const ImageCarousel: React.FC = () => {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [nextIndex, setNextIndex] = useState(1);
  const [transitioning, setTransitioning] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setTransitioning(true);
      const next = (currentIndex + 1) % SHOWCASE_IMAGES.length;
      setNextIndex(next);

      setTimeout(() => {
        setCurrentIndex(next);
        setNextIndex((next + 1) % SHOWCASE_IMAGES.length);
        setTransitioning(false);
      }, 1200); // match transition duration
    }, 4000); // change every 4s

    return () => clearInterval(interval);
  }, [currentIndex]);

  return (
    <div className="absolute inset-0 overflow-hidden">
      {/* Current image */}
      <div
        className="absolute inset-0 transition-opacity duration-[1200ms] ease-in-out"
        style={{ opacity: transitioning ? 0 : 1 }}
      >
        <img
          src={SHOWCASE_IMAGES[currentIndex]}
          alt=""
          className="w-full h-full object-cover"
          style={{ animation: 'ken-burns 8s ease-out forwards' }}
          loading="eager"
        />
      </div>
      {/* Next image (fading in) */}
      <div
        className="absolute inset-0 transition-opacity duration-[1200ms] ease-in-out"
        style={{ opacity: transitioning ? 1 : 0 }}
      >
        <img
          src={SHOWCASE_IMAGES[nextIndex]}
          alt=""
          className="w-full h-full object-cover"
          style={{ animation: 'ken-burns 8s ease-out forwards' }}
          loading="eager"
        />
      </div>
      {/* Dark overlay for readability */}
      <div className="absolute inset-0 bg-gradient-to-r from-[#06060e]/90 via-[#06060e]/70 to-[#06060e]/95" />
      <div className="absolute inset-0 bg-gradient-to-t from-[#06060e]/80 via-transparent to-[#06060e]/60" />

      {/* Progress dots */}
      <div className="absolute bottom-6 left-12 flex gap-1.5 z-10">
        {SHOWCASE_IMAGES.map((_, i) => (
          <div
            key={i}
            className={`h-1 rounded-full transition-all duration-500 ${
              i === currentIndex
                ? 'w-6 bg-blue-400/80'
                : 'w-1.5 bg-white/15 hover:bg-white/25'
            }`}
          />
        ))}
      </div>
    </div>
  );
};

/* ── Floating particles on left panel ── */
const FloatingParticles: React.FC = () => (
  <div className="absolute inset-0 overflow-hidden pointer-events-none">
    {[...Array(6)].map((_, i) => (
      <div
        key={i}
        className="absolute rounded-full bg-blue-400/10"
        style={{
          width: `${6 + i * 4}px`,
          height: `${6 + i * 4}px`,
          left: `${15 + i * 14}%`,
          top: `${10 + i * 13}%`,
          animation: `float ${6 + i * 2}s ease-in-out infinite`,
          animationDelay: `${i * 0.7}s`,
        }}
      />
    ))}
  </div>
);

/* ── Tooltip component ── */
const Tooltip: React.FC<{ text: string }> = ({ text }) => {
  const [show, setShow] = useState(false);
  return (
    <span className="relative inline-block ml-1.5 align-middle">
      <button
        type="button"
        className="text-white/30 hover:text-cyan-400 transition-colors duration-300"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
        onClick={() => setShow(!show)}
      >
        <Info size={13} />
      </button>
      {show && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 rounded-xl bg-[#0d1117] border border-white/10 px-3.5 py-2.5 text-xs text-white/70 shadow-2xl shadow-black/40" style={{ animation: 'slide-up 0.2s ease-out' }}>
          {text}
          <span className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-[#0d1117]" />
        </span>
      )}
    </span>
  );
};

/* ── Step indicator for registration ── */
const STEPS = ['Datos', 'Rol y sede', 'Perfil'];

const StepIndicator: React.FC<{ current: number }> = ({ current }) => (
  <div className="flex items-center justify-center gap-1 mb-6">
    {STEPS.map((label, i) => (
      <React.Fragment key={label}>
        {i > 0 && (
          <div className={`w-8 h-px mx-1 transition-all duration-500 ${i <= current ? 'bg-gradient-to-r from-blue-500 to-cyan-400' : 'bg-white/10'}`} />
        )}
        <div className="flex items-center gap-1.5">
          <div
            className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-bold transition-all duration-500 ${
              i < current
                ? 'bg-gradient-to-r from-blue-500 to-cyan-400 text-white shadow-lg shadow-blue-500/25'
                : i === current
                  ? 'bg-gradient-to-r from-blue-500 to-cyan-400 text-white shadow-lg shadow-blue-500/25 ring-2 ring-blue-400/30'
                  : 'bg-white/5 text-white/30 border border-white/10'
            }`}
          >
            {i < current ? <CheckCircle size={14} /> : i + 1}
          </div>
          <span className={`text-[11px] font-medium hidden sm:inline transition-all duration-300 ${i <= current ? 'text-white/80' : 'text-white/25'}`}>
            {label}
          </span>
        </div>
      </React.Fragment>
    ))}
  </div>
);

/* ── Feature card for branding side ── */
const FEATURES = [
  { icon: Sparkles, text: 'Odontograma digital', desc: 'Registro clinico inteligente' },
  { icon: Zap, text: 'Agente IA 24/7', desc: 'Atencion automatizada' },
  { icon: BarChart3, text: 'Analytics en tiempo real', desc: 'Metricas que importan' },
  { icon: MessageCircle, text: 'Omnicanal', desc: 'WhatsApp + Instagram + Facebook' },
];

/* ── Stat counter ── */
const STATS = [
  { value: '20+', label: 'Profesionales' },
  { value: '5K+', label: 'Pacientes' },
  { value: '99.9%', label: 'Uptime' },
];

/* ── Main Component ── */
const LoginView: React.FC = () => {
  const { login } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [isRegistering, setIsRegistering] = useState(false);
  const [registerSuccess, setRegisterSuccess] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [role, setRole] = useState('professional');
  const [tenantId, setTenantId] = useState<number | ''>('');
  const [specialty, setSpecialty] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [registrationId, setRegistrationId] = useState('');
  const [googleCalendarId, setGoogleCalendarId] = useState('');
  const [clinics, setClinics] = useState<ClinicOption[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [mounted, setMounted] = useState(false);
  const formRef = useRef<HTMLDivElement>(null);

  const from = location.state?.from?.pathname || "/";
  const isDemo = new URLSearchParams(location.search).get('demo') === '1';

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (isDemo) {
      setEmail(DEMO_EMAIL);
      setPassword(DEMO_PASSWORD);
    }
  }, [isDemo]);

  useEffect(() => {
    if (isRegistering) {
      api.get<ClinicOption[]>('/auth/clinics')
        .then((res) => setClinics(res.data || []))
        .catch(() => setClinics([]));
    }
  }, [isRegistering]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await api.post('/auth/login', { email, password });
      login(response.data.access_token, response.data.user);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || t('login.login_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await api.post('/auth/login', { email: DEMO_EMAIL, password: DEMO_PASSWORD });
      login(response.data.access_token, response.data.user);
      navigate(from, { replace: true });
    } catch (err: any) {
      setError(err.response?.data?.detail || t('login.login_error'));
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setMessage(null);
    if ((role === 'professional' || role === 'secretary') && !tenantId) {
      setError(t('login.clinic_required'));
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/register', {
        email,
        password,
        role,
        first_name: firstName,
        last_name: lastName,
        tenant_id: role === 'professional' || role === 'secretary' ? Number(tenantId) : null,
        specialty: role === 'professional' ? (specialty || null) : null,
        phone_number: phoneNumber || null,
        registration_id: registrationId || null,
        google_calendar_id: role === 'professional' ? (googleCalendarId || null) : null,
      });
      setMessage(t('login.register_success'));
      setRegisterSuccess(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || t('login.register_error'));
    } finally {
      setLoading(false);
    }
  };

  const getRegisterStep = (): number => {
    if (role === 'professional') return 2;
    if (role === 'secretary') return 1;
    return 1;
  };

  const inputBase = "w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/20 focus:border-blue-500/60 focus:bg-white/[0.06] focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:shadow-lg focus:shadow-blue-500/5 transition-all duration-300";
  const inputWithIcon = "w-full pl-11 pr-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white placeholder-white/20 focus:border-blue-500/60 focus:bg-white/[0.06] focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:shadow-lg focus:shadow-blue-500/5 transition-all duration-300";
  const selectClass = "w-full px-4 py-3 bg-white/[0.04] border border-white/[0.08] rounded-xl text-white focus:border-blue-500/60 focus:bg-white/[0.06] focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all duration-300 appearance-none";
  const labelClass = "block text-xs font-medium text-white/50 mb-1.5 tracking-wide uppercase";

  return (
    <>
      <style>{keyframesStyle}</style>
      <div className="flex min-h-screen bg-[#06060e]">

        {/* ═══════════════ LEFT SIDE — BRANDING ═══════════════ */}
        <div className="hidden lg:flex lg:w-[55%] relative overflow-hidden flex-col justify-between p-12">
          {/* Background image carousel */}
          <ImageCarousel />

          {/* Animated grid overlay */}
          <div
            className="absolute inset-0"
            style={{
              backgroundImage: 'linear-gradient(rgba(59,130,246,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(59,130,246,0.03) 1px, transparent 1px)',
              backgroundSize: '60px 60px',
              animation: 'grid-fade 8s ease-in-out infinite',
            }}
          />

          {/* Gradient orbs */}
          <div className="absolute top-1/4 left-1/4 w-[500px] h-[500px] bg-gradient-to-r from-blue-600/15 to-cyan-500/10 rounded-full blur-[120px]" style={{ animation: 'float 12s ease-in-out infinite' }} />
          <div className="absolute bottom-1/3 right-1/4 w-[400px] h-[400px] bg-gradient-to-r from-violet-600/10 to-blue-500/10 rounded-full blur-[100px]" style={{ animation: 'float-delayed 15s ease-in-out infinite' }} />
          <div className="absolute top-2/3 left-1/2 w-[300px] h-[300px] bg-gradient-to-r from-cyan-500/8 to-emerald-500/5 rounded-full blur-[80px]" style={{ animation: 'float 10s ease-in-out infinite', animationDelay: '3s' }} />

          <FloatingParticles />

          {/* Content */}
          <div className="relative z-10 flex flex-col justify-between h-full">
            {/* Top — Logo */}
            <div style={{ animation: 'slide-up 0.6s ease-out' }}>
              <div className="flex items-center gap-3.5 mb-2">
                <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-blue-500 via-blue-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20">
                  <Shield size={22} className="text-white" />
                </div>
                <div>
                  <h1 className="text-2xl font-bold text-white tracking-tight">Dentalogic</h1>
                  <p className="text-[10px] font-medium text-blue-400/60 tracking-[0.2em] uppercase">Clinical Intelligence</p>
                </div>
              </div>
            </div>

            {/* Center — Hero text + features */}
            <div className="flex-1 flex flex-col justify-center max-w-lg" style={{ animation: 'slide-up 0.8s ease-out' }}>
              <h2 className="text-[42px] font-bold text-white leading-[1.1] mb-4 tracking-tight">
                El futuro de la
                <br />
                <span
                  className="bg-clip-text text-transparent"
                  style={{
                    backgroundImage: 'linear-gradient(135deg, #60a5fa, #22d3ee, #a78bfa)',
                    backgroundSize: '200% auto',
                    animation: 'shimmer 4s linear infinite',
                  }}
                >
                  gestion dental
                </span>
              </h2>
              <p className="text-white/40 text-lg leading-relaxed mb-10 max-w-sm">
                Inteligencia artificial que transforma cada interaccion con tus pacientes.
              </p>

              {/* Feature grid */}
              <div className="grid grid-cols-2 gap-3 mb-10">
                {FEATURES.map((feat, i) => (
                  <div
                    key={feat.text}
                    className="group p-4 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-blue-500/20 hover:bg-white/[0.04] transition-all duration-500 cursor-default"
                    style={{ animation: 'slide-up 0.6s ease-out', animationDelay: `${0.1 * i}s`, animationFillMode: 'both' }}
                  >
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500/10 to-cyan-500/10 flex items-center justify-center mb-3 group-hover:from-blue-500/20 group-hover:to-cyan-500/20 transition-all duration-500">
                      <feat.icon size={18} className="text-blue-400 group-hover:text-cyan-300 transition-colors duration-500" />
                    </div>
                    <p className="text-white/80 text-sm font-medium mb-0.5">{feat.text}</p>
                    <p className="text-white/30 text-xs">{feat.desc}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Bottom — Stats + social proof */}
            <div style={{ animation: 'slide-up 1s ease-out' }}>
              <div className="flex items-center gap-8 mb-6">
                {STATS.map((stat, i) => (
                  <div key={stat.label} style={{ animation: 'count-up 0.5s ease-out', animationDelay: `${1.2 + i * 0.15}s`, animationFillMode: 'both' }}>
                    <p className="text-2xl font-bold text-white tracking-tight">{stat.value}</p>
                    <p className="text-white/30 text-xs font-medium tracking-wide">{stat.label}</p>
                  </div>
                ))}
              </div>

              <div className="flex items-center gap-3 pt-5 border-t border-white/[0.06]">
                {/* Avatar stack */}
                <div className="flex -space-x-2">
                  {['bg-blue-500', 'bg-cyan-500', 'bg-violet-500', 'bg-emerald-500'].map((bg, i) => (
                    <div key={i} className={`w-7 h-7 rounded-full ${bg} border-2 border-[#0a0f1e] flex items-center justify-center`}>
                      <span className="text-[10px] text-white font-bold">{['D', 'A', 'M', 'R'][i]}</span>
                    </div>
                  ))}
                </div>
                <p className="text-white/35 text-xs">
                  Profesionales que ya <span className="text-blue-400/70 font-medium">transformaron</span> su practica
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* ═══════════════ RIGHT SIDE — FORM ═══════════════ */}
        <div className="w-full lg:w-[45%] flex flex-col justify-center items-center px-6 py-8 relative overflow-y-auto">
          {/* Subtle background glow */}
          <div className="absolute top-0 right-0 w-96 h-96 bg-blue-600/5 rounded-full blur-[120px] pointer-events-none" />

          {/* Mobile branding header */}
          <div className="lg:hidden mb-8 text-center" style={{ animation: mounted ? 'slide-up 0.5s ease-out' : 'none' }}>
            <div className="flex items-center justify-center gap-2.5 mb-2">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-400 flex items-center justify-center shadow-lg shadow-blue-500/20">
                <Shield size={20} className="text-white" />
              </div>
              <h1 className="text-2xl font-bold text-white tracking-tight">Dentalogic</h1>
            </div>
            <p className="text-white/30 text-xs tracking-[0.15em] uppercase font-medium">Clinical Intelligence</p>
          </div>

          <div ref={formRef} className="w-full max-w-[400px]" style={{ animation: mounted ? 'slide-up 0.6s ease-out' : 'none' }}>

            {/* ── Register success state ── */}
            {registerSuccess ? (
              <div className="relative rounded-2xl overflow-hidden" style={{ animation: 'slide-up 0.4s ease-out' }}>
                <div className="absolute inset-0 bg-gradient-to-b from-green-500/5 to-transparent pointer-events-none" />
                <div className="relative bg-white/[0.03] backdrop-blur-xl border border-white/[0.08] rounded-2xl p-8 text-center">
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-green-500/15 to-emerald-500/10 flex items-center justify-center mx-auto mb-5 ring-1 ring-green-500/20">
                    <CheckCircle size={28} className="text-green-400" />
                  </div>
                  <h2 className="text-xl font-bold text-white mb-2">Solicitud enviada</h2>
                  <p className="text-white/40 text-sm mb-8 leading-relaxed">
                    El CEO de tu clinica debe aprobar tu acceso.
                    <br />Te notificaremos por email.
                  </p>
                  <button
                    onClick={() => {
                      setRegisterSuccess(false);
                      setIsRegistering(false);
                      setError(null);
                      setMessage(null);
                    }}
                    className="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 text-white text-sm font-semibold hover:shadow-lg hover:shadow-blue-500/20 transition-all duration-300 flex items-center justify-center gap-2"
                  >
                    Ir al login
                    <ArrowRight size={16} />
                  </button>
                </div>
              </div>
            ) : (
              /* ── Main form card ── */
              <div className="relative rounded-2xl overflow-hidden">
                {/* Card glow ring */}
                <div className="absolute -inset-px rounded-2xl bg-gradient-to-b from-white/[0.08] via-transparent to-transparent pointer-events-none" />

                <div className="relative bg-white/[0.02] backdrop-blur-xl border border-white/[0.06] rounded-2xl p-7">
                  {/* Header */}
                  <div className="text-center mb-6">
                    <h2 className="text-xl font-bold text-white mb-1 tracking-tight">
                      {isRegistering ? t('login.request_access') : t('login.title')}
                    </h2>
                    <p className="text-white/35 text-sm">
                      {isRegistering ? 'Completa tus datos para solicitar acceso' : t('login.welcome')}
                    </p>
                  </div>

                  {/* Step indicator for register */}
                  {isRegistering && !isDemo && <StepIndicator current={getRegisterStep()} />}

                  {/* Alerts */}
                  {error && (
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-red-500/8 border border-red-500/15 mb-5" style={{ animation: 'slide-up 0.3s ease-out' }}>
                      <AlertCircle size={16} className="text-red-400 shrink-0" />
                      <span className="text-red-400/90 text-sm">{error}</span>
                    </div>
                  )}

                  {message && !registerSuccess && (
                    <div className="flex items-center gap-3 p-3 rounded-xl bg-green-500/8 border border-green-500/15 mb-5" style={{ animation: 'slide-up 0.3s ease-out' }}>
                      <CheckCircle size={16} className="text-green-400 shrink-0" />
                      <span className="text-green-400/90 text-sm">{message}</span>
                    </div>
                  )}

                  <form onSubmit={isRegistering ? handleRegister : isDemo ? handleDemoLogin : handleLogin} className="space-y-3.5">
                    {/* Demo mode */}
                    {isDemo && !isRegistering && (
                      <div className="space-y-4">
                        <p className="text-sm text-white/50 text-center">{t('login_extra.demo_ready')}</p>
                        <button
                          type="submit"
                          disabled={loading}
                          className="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 to-cyan-500 text-white text-sm font-semibold hover:shadow-lg hover:shadow-blue-500/20 transition-all duration-300 disabled:opacity-50"
                        >
                          {loading ? t('login.processing') : 'Entrar a la demo'}
                        </button>
                        <div className="text-center">
                          <Link to="/login" className="text-sm text-cyan-400/70 hover:text-white transition-colors duration-300">
                            {t('login_extra.sign_in_link')}
                          </Link>
                        </div>
                      </div>
                    )}

                    {/* Register: name fields */}
                    {!isDemo && isRegistering && (
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className={labelClass}>
                            {t('login.first_name')}
                          </label>
                          <input
                            type="text"
                            value={firstName}
                            onChange={(e) => setFirstName(e.target.value)}
                            placeholder="Juan"
                            required
                            className={inputBase}
                          />
                        </div>
                        <div>
                          <label className={labelClass}>
                            {t('login.last_name')}
                          </label>
                          <input
                            type="text"
                            value={lastName}
                            onChange={(e) => setLastName(e.target.value)}
                            placeholder="Perez"
                            className={inputBase}
                          />
                        </div>
                      </div>
                    )}

                    {/* Email & Password (non-demo) */}
                    {!isDemo && (
                      <>
                        <div>
                          <label className={labelClass}>
                            {t('login.email')}
                            <Tooltip text={TOOLTIPS.email} />
                          </label>
                          <div className="relative">
                            <Mail size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/20" />
                            <input
                              type="email"
                              value={email}
                              onChange={(e) => setEmail(e.target.value)}
                              placeholder="dr.perez@clinica.com"
                              required
                              className={inputWithIcon}
                            />
                          </div>
                        </div>

                        <div>
                          <label className={labelClass}>
                            {t('login.password')}
                            <Tooltip text={TOOLTIPS.password} />
                          </label>
                          <div className="relative">
                            <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-white/20" />
                            <input
                              type={showPassword ? 'text' : 'password'}
                              value={password}
                              onChange={(e) => setPassword(e.target.value)}
                              placeholder="••••••••"
                              required
                              className={`${inputWithIcon} pr-11`}
                            />
                            <button
                              type="button"
                              onClick={() => setShowPassword(!showPassword)}
                              className="absolute right-3.5 top-1/2 -translate-y-1/2 text-white/20 hover:text-white/50 transition-colors"
                            >
                              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                            </button>
                          </div>
                        </div>

                        {/* Role select */}
                        {isRegistering && (
                          <div>
                            <label className={labelClass}>
                              {t('login.role')}
                              <Tooltip text={TOOLTIPS.role} />
                            </label>
                            <select value={role} onChange={(e) => setRole(e.target.value)} className={selectClass}>
                              <option value="professional">{t('login.role_professional')}</option>
                              <option value="secretary">{t('login.role_secretary')}</option>
                              <option value="ceo">{t('login.role_ceo')}</option>
                            </select>
                          </div>
                        )}

                        {/* Clinic select */}
                        {isRegistering && (role === 'professional' || role === 'secretary') && (
                          <div>
                            <label className={labelClass}>
                              {t('login.clinic')} <span className="text-blue-400/80">*</span>
                              <Tooltip text={TOOLTIPS.clinic} />
                            </label>
                            <select
                              value={tenantId}
                              onChange={(e) => setTenantId(e.target.value === '' ? '' : Number(e.target.value))}
                              required={role === 'professional' || role === 'secretary'}
                              className={selectClass}
                            >
                              <option value="">{t('login.choose_clinic')}</option>
                              {clinics.map((c) => (
                                <option key={c.id} value={c.id}>{c.clinic_name}</option>
                              ))}
                            </select>
                            {clinics.length === 0 && (
                              <p className="text-[11px] mt-1.5 text-white/30">{t('login.no_clinics')}</p>
                            )}
                          </div>
                        )}

                        {/* Professional fields */}
                        {isRegistering && role === 'professional' && (
                          <>
                            <div>
                              <label className={labelClass}>
                                {t('login.specialty')}
                                <Tooltip text={TOOLTIPS.specialty} />
                              </label>
                              <select value={specialty} onChange={(e) => setSpecialty(e.target.value)} className={selectClass}>
                                <option value="">{t('login.select_specialty')}</option>
                                {SPECIALTIES.map((s) => (
                                  <option key={s.value} value={s.value}>{t('approvals.' + s.key)}</option>
                                ))}
                              </select>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                              <div>
                                <label className={labelClass}>
                                  {t('login.phone')}
                                  <Tooltip text={TOOLTIPS.phone} />
                                </label>
                                <input
                                  type="text"
                                  value={phoneNumber}
                                  onChange={(e) => setPhoneNumber(e.target.value)}
                                  placeholder="+54 11 1234-5678"
                                  className={inputBase}
                                />
                              </div>
                              <div>
                                <label className={labelClass}>
                                  {t('login.registration_id')}
                                  <Tooltip text={TOOLTIPS.registration_id} />
                                </label>
                                <input
                                  type="text"
                                  value={registrationId}
                                  onChange={(e) => setRegistrationId(e.target.value)}
                                  placeholder={t('login.placeholder_optional')}
                                  className={inputBase}
                                />
                              </div>
                            </div>
                            <div>
                              <label className={labelClass}>
                                Google Calendar ID
                                <Tooltip text={TOOLTIPS.google_calendar} />
                              </label>
                              <input
                                type="text"
                                value={googleCalendarId}
                                onChange={(e) => setGoogleCalendarId(e.target.value)}
                                placeholder={t('login.placeholder_calendar')}
                                className={inputBase}
                              />
                            </div>
                          </>
                        )}

                        {/* Secretary phone */}
                        {isRegistering && role === 'secretary' && (
                          <div>
                            <label className={labelClass}>
                              {t('login.phone')}
                              <Tooltip text={TOOLTIPS.phone} />
                            </label>
                            <input
                              type="text"
                              value={phoneNumber}
                              onChange={(e) => setPhoneNumber(e.target.value)}
                              placeholder={t('login.placeholder_optional')}
                              className={inputBase}
                            />
                          </div>
                        )}

                        {/* Submit button */}
                        <button
                          type="submit"
                          disabled={loading}
                          className="group w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 via-blue-500 to-cyan-500 text-white text-sm font-semibold hover:shadow-xl hover:shadow-blue-500/25 hover:brightness-110 active:scale-[0.98] transition-all duration-300 disabled:opacity-40 disabled:hover:shadow-none flex items-center justify-center gap-2 mt-1"
                        >
                          {loading ? (
                            <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                          ) : (
                            <>
                              {isRegistering ? t('login.submit_register') : t('login.submit_login')}
                              <ArrowRight size={16} className="group-hover:translate-x-0.5 transition-transform duration-300" />
                            </>
                          )}
                        </button>
                      </>
                    )}
                  </form>

                  {/* Toggle login/register */}
                  {!isDemo && (
                    <div className="mt-6 text-center">
                      <button
                        type="button"
                        className="text-white/30 hover:text-blue-400 text-sm transition-colors duration-300"
                        onClick={() => {
                          setIsRegistering(!isRegistering);
                          setError(null);
                          setMessage(null);
                          setRegisterSuccess(false);
                        }}
                      >
                        {isRegistering ? t('login.have_account') : t('login.request_access_link')}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Bottom text */}
            <p className="text-center text-white/15 text-[11px] mt-6 tracking-wide">
              Powered by Dentalogic AI
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default LoginView;
