import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Calendar,
  Users,
  MessageSquare,
  Settings,
  ChevronLeft,
  ChevronRight,
  Stethoscope,
  BarChart3,
  Home,
  Clock,
  ShieldCheck,
  LogOut,
  User,
  X,
  Megaphone,
  Layout,
  Zap
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onCloseMobile?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle, onCloseMobile }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const [clinicName, setClinicName] = useState<string>(localStorage.getItem('CLINIC_NAME') || '');
  const [logoUrl, setLogoUrl] = useState<string>(localStorage.getItem('CLINIC_LOGO') || '');

  useEffect(() => {
    api.get('/admin/chat/tenants').then(res => {
      const tenants = res.data;
      if (tenants?.length > 0) {
        const name = tenants[0].name || tenants[0].clinic_name || '';
        setClinicName(name);
        localStorage.setItem('CLINIC_NAME', name);
      }
    }).catch(() => {});
    // Load logo
    const tid = localStorage.getItem('X-Tenant-ID') || '1';
    const logoPath = `/admin/public/tenant-logo/${tid}`;
    api.get(logoPath, { responseType: 'blob' }).then(res => {
      const url = URL.createObjectURL(res.data);
      setLogoUrl(url);
      localStorage.setItem('CLINIC_LOGO', logoPath);
      // Set favicon dynamically
      const link = document.querySelector("link[rel~='icon']") as HTMLLinkElement;
      if (link) { link.href = url; }
    }).catch(() => {
      localStorage.removeItem('CLINIC_LOGO');
    });
  }, []);

  const [tooltipId, setTooltipId] = useState<string | null>(null);
  const tooltipTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const menuItems = [
    { id: 'dashboard', labelKey: 'nav.dashboard' as const, icon: <Home size={18} />, emoji: '📊', path: '/', roles: ['ceo', 'professional', 'secretary'], hint: 'Centro de mando con KPIs en tiempo real de la clinica' },
    { id: 'agenda', labelKey: 'nav.agenda' as const, icon: <Calendar size={18} />, emoji: '🗓️', path: '/agenda', roles: ['ceo', 'professional', 'secretary'], hint: 'Agenda interactiva de turnos por profesional y sede' },
    { id: 'patients', labelKey: 'nav.patients' as const, icon: <Users size={18} />, emoji: '🦷', path: '/pacientes', roles: ['ceo', 'professional', 'secretary'], hint: 'Base de pacientes con ficha clinica, odontograma y anamnesis' },
    { id: 'chats', labelKey: 'nav.chats' as const, icon: <MessageSquare size={18} />, emoji: '💬', path: '/chats', roles: ['ceo', 'professional', 'secretary'], hint: 'Conversaciones de WhatsApp, Instagram y Facebook en un solo lugar' },
    { id: 'approvals', labelKey: 'nav.staff' as const, icon: <ShieldCheck size={18} />, emoji: '👥', path: '/aprobaciones', roles: ['ceo'], hint: 'Aprobar o suspender acceso de profesionales y secretarias' },
    { id: 'tenants', labelKey: 'nav.clinics' as const, icon: <ShieldCheck size={18} />, emoji: '🏥', path: '/sedes', roles: ['ceo'], hint: 'Configurar sedes, horarios por dia, direcciones y datos bancarios' },
    { id: 'analytics', labelKey: 'nav.strategy' as const, icon: <BarChart3 size={18} />, emoji: '📈', path: '/analytics/professionals', roles: ['ceo'], hint: 'Rendimiento de cada profesional: turnos, retención, facturación' },
    { id: 'tokens', labelKey: 'nav.tokens' as const, icon: <Zap size={18} />, emoji: '⚡', path: '/dashboard/status', roles: ['ceo'], hint: 'Consumo de IA por servicio, costos y seleccion de modelos' },
    { id: 'treatments', labelKey: 'nav.treatments' as const, icon: <Clock size={18} />, emoji: '🩺', path: '/tratamientos', roles: ['ceo', 'secretary'], hint: 'Tipos de tratamiento con precios, duracion e imagenes' },
    { id: 'profile', labelKey: 'nav.profile' as const, icon: <User size={18} />, emoji: '👤', path: '/perfil', roles: ['ceo', 'professional', 'secretary'], hint: 'Tu perfil y datos de cuenta' },
    { id: 'marketing', labelKey: 'nav.marketing' as const, icon: <Megaphone size={18} />, emoji: '📣', path: '/marketing', roles: ['ceo'], hint: 'ROI real de Meta Ads y Google Ads con atribución de pacientes' },
    { id: 'leads', labelKey: 'nav.leads' as const, icon: <Users size={18} />, emoji: '🎯', path: '/leads', roles: ['ceo'], hint: 'Leads de formularios de Meta con estado y seguimiento' },
    { id: 'templates', labelKey: 'nav.hsm' as const, icon: <Layout size={18} />, emoji: '📝', path: '/templates', roles: ['ceo'], hint: 'Plantillas HSM de WhatsApp y reglas de automatización' },
    { id: 'settings', labelKey: 'nav.settings' as const, icon: <Settings size={18} />, emoji: '⚙️', path: '/configuracion', roles: ['ceo'], hint: 'Configuración general, integraciones y credenciales' },
  ];

  const filteredItems = menuItems.filter(item => user && item.roles.includes(user.role));

  const isActive = (path: string) => {
    if (path === '/' && location.pathname !== '/') return false;
    return location.pathname === path;
  };

  return (
    <aside className="h-full bg-medical-900 text-white flex flex-col relative shadow-xl overflow-hidden">
      {/* Logo Area */}
      <div className={`h-16 flex items-center ${collapsed && !onCloseMobile ? 'justify-center' : 'px-6'} border-b border-medical-800 shrink-0`}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white/10 flex items-center justify-center shrink-0 overflow-hidden">
            {logoUrl ? (
              <img src={logoUrl} alt="Logo" className="w-full h-full object-cover rounded-lg" />
            ) : (
              <Stethoscope size={18} className="text-white" />
            )}
          </div>
          {(!collapsed || onCloseMobile) && (
            <span className="font-semibold text-lg truncate whitespace-nowrap">{clinicName || t('nav.app_name')}</span>
          )}
        </div>

        {/* Mobile Close Button - Visible only in drawer mode */}
        {onCloseMobile && (
          <button
            onClick={onCloseMobile}
            className="lg:hidden p-2 ml-auto text-gray-400 hover:text-white transition-colors"
            aria-label={t('nav.close_menu')}
          >
            <X size={24} />
          </button>
        )}
      </div>

      {/* Toggle Button (Desktop only) */}
      {!onCloseMobile && (
        <button
          onClick={onToggle}
          className="hidden lg:flex absolute -right-3 top-20 w-6 h-6 bg-white rounded-full shadow-lg items-center justify-center text-medical-900 hover:bg-gray-100 transition-all z-20"
          aria-label={collapsed ? t('nav.expand') : t('nav.collapse')}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      )}

      {/* Navigation */}
      <nav className={`flex-1 py-3 overflow-y-auto overflow-x-hidden ${collapsed && !onCloseMobile ? 'px-2' : 'px-2.5'}`}>
        {filteredItems.map((item) => (
          <div key={item.id} className="relative mb-0.5">
            <button
              onClick={() => {
                navigate(item.path);
                setTooltipId(null);
                onCloseMobile?.();
              }}
              onMouseEnter={() => {
                if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
                tooltipTimer.current = setTimeout(() => setTooltipId(item.id), 500);
              }}
              onMouseLeave={() => {
                if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
                setTooltipId(null);
              }}
              onTouchStart={() => {
                if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
                tooltipTimer.current = setTimeout(() => setTooltipId(item.id), 400);
              }}
              onTouchEnd={() => {
                if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
              }}
              className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl transition-all duration-200 group ${isActive(item.path)
                ? 'bg-white/15 text-white shadow-sm shadow-white/5'
                : 'text-gray-400 hover:bg-white/5 hover:text-white'
                }`}
              title={collapsed && !onCloseMobile ? t(item.labelKey) : undefined}
            >
              <span className="text-base leading-none shrink-0">{item.emoji}</span>
              {(!collapsed || onCloseMobile) && (
                <span className="font-medium text-[13px] truncate">{t(item.labelKey)}</span>
              )}
            </button>

            {/* Tooltip popup — appears on hover/long-press */}
            {tooltipId === item.id && (!collapsed || onCloseMobile) && item.hint && (
              <div
                className="absolute left-full top-0 ml-2 z-50 w-56 bg-slate-900 text-white rounded-xl px-3 py-2.5 shadow-xl border border-white/10 pointer-events-none animate-in fade-in slide-in-from-left-1 duration-150"
                style={{ animationDuration: '150ms' }}
              >
                <p className="text-[11px] font-semibold text-white/90 mb-0.5">{t(item.labelKey)}</p>
                <p className="text-[10px] text-white/60 leading-relaxed">{item.hint}</p>
                <div className="absolute right-full top-2.5 w-0 h-0 border-t-[5px] border-t-transparent border-r-[6px] border-r-slate-900 border-b-[5px] border-b-transparent" />
              </div>
            )}
          </div>
        ))}

        <button
          onClick={logout}
          className={`w-full flex items-center gap-2.5 px-2.5 py-2 rounded-xl transition-all duration-200 mt-3 text-red-400 hover:bg-red-500/10 group`}
          title={collapsed && !onCloseMobile ? t('nav.logout') : undefined}
        >
          <span className="text-base leading-none shrink-0">🚪</span>
          {(!collapsed || onCloseMobile) && <span className="font-medium text-[13px]">{t('nav.logout')}</span>}
        </button>
      </nav>

      {/* Footer Info */}
      {(!collapsed || onCloseMobile) && (
        <div className="p-4 border-t border-medical-800 bg-medical-900/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-medical-600 flex items-center justify-center text-xs font-medium uppercase shrink-0">
              {user?.email?.[0] || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate text-white">{user?.email}</p>
              <p className="text-[10px] text-gray-400 truncate uppercase tracking-wider font-semibold">{user?.role}</p>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
};

export default Sidebar;
