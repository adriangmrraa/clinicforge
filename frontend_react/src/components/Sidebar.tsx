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
  Zap,
  TrendingUp,
  Wallet,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../context/LanguageContext';
import api from '../api/axios';

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  onCloseMobile?: () => void;
}

// Subtle, tenue background images per section — dental/tech/clinic themed
const CARD_IMAGES: Record<string, string> = {
  dashboard: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=400&q=60',
  agenda: 'https://images.unsplash.com/photo-1506784983877-45594efa4cbe?w=400&q=60',
  patients: 'https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=400&q=60',
  chats: 'https://images.unsplash.com/photo-1577563908411-5077b6dc7624?w=400&q=60',
  approvals: 'https://images.unsplash.com/photo-1521791136064-7986c2920216?w=400&q=60',
  tenants: 'https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=400&q=60',
  analytics: 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400&q=60',
  tokens: 'https://images.unsplash.com/photo-1620712943543-bcc4688e7485?w=400&q=60',
  treatments: 'https://images.unsplash.com/photo-1606811971618-4486d14f3f99?w=400&q=60',
  'my-liquidations': 'https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=400&q=60',
  profile: 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=400&q=60',
  marketing: 'https://images.unsplash.com/photo-1533750349088-cd871a92f312?w=400&q=60',
  leads: 'https://images.unsplash.com/photo-1552664730-d307ca884978?w=400&q=60',
  templates: 'https://images.unsplash.com/photo-1586281380349-632531db7ed4?w=400&q=60',
  settings: 'https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=400&q=60',
};

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle, onCloseMobile }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const [clinicName, setClinicName] = useState<string>(localStorage.getItem('CLINIC_NAME') || '');
  const [logoUrl, setLogoUrl] = useState<string>(localStorage.getItem('CLINIC_LOGO') || '');
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [touchedId, setTouchedId] = useState<string | null>(null);

  useEffect(() => {
    api.get('/admin/chat/tenants').then(res => {
      const tenants = res.data;
      if (tenants?.length > 0) {
        const name = tenants[0].name || tenants[0].clinic_name || '';
        setClinicName(name);
        localStorage.setItem('CLINIC_NAME', name);
      }
    }).catch(() => {});
    const tid = localStorage.getItem('X-Tenant-ID') || '1';
    const logoPath = `/admin/public/tenant-logo/${tid}`;
    api.get(logoPath, { responseType: 'blob' }).then(res => {
      const url = URL.createObjectURL(res.data);
      setLogoUrl(url);
      localStorage.setItem('CLINIC_LOGO', logoPath);
      const link = document.querySelector("link[rel~='icon']") as HTMLLinkElement;
      if (link) { link.href = url; }
    }).catch(() => {
      localStorage.removeItem('CLINIC_LOGO');
    });
  }, []);

  // Preload images
  useEffect(() => {
    Object.values(CARD_IMAGES).forEach(src => {
      const img = new Image();
      img.src = src;
    });
  }, []);

  // Listen for logo updates from ConfigView
  useEffect(() => {
    const handleLogoUpdated = (event: CustomEvent<{ tenant_id: number }>) => {
      const currentTenantId = localStorage.getItem('X-Tenant-ID');
      // Only refresh if the updated logo belongs to the currently viewed tenant
      if (currentTenantId && parseInt(currentTenantId) === event.detail.tenant_id) {
        // Re‑fetch logo with cache busting
        const logoPath = `/admin/public/tenant-logo/${currentTenantId}?t=${Date.now()}`;
        api.get(logoPath, { responseType: 'blob' })
          .then(res => {
            const url = URL.createObjectURL(res.data);
            setLogoUrl(url);
            localStorage.setItem('CLINIC_LOGO', logoPath);
            const link = document.querySelector("link[rel~='icon']") as HTMLLinkElement;
            if (link) link.href = url;
          })
          .catch(() => {
            // Logo may have been removed; clear local storage
            localStorage.removeItem('CLINIC_LOGO');
            setLogoUrl('');
          });
      }
    };
    // Cast to any because TypeScript doesn't know about detail typing
    window.addEventListener('tenant-logo-updated', handleLogoUpdated as EventListener);
    return () => window.removeEventListener('tenant-logo-updated', handleLogoUpdated as EventListener);
  }, []);

  const [tooltipId, setTooltipId] = useState<string | null>(null);
  const tooltipTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const menuItems = [
    { id: 'dashboard', labelKey: 'nav.dashboard' as const, icon: <Home size={17} />, path: '/', roles: ['ceo', 'professional', 'secretary'], hint: 'Centro de mando con KPIs en tiempo real de la clinica' },
    { id: 'agenda', labelKey: 'nav.agenda' as const, icon: <Calendar size={17} />, path: '/agenda', roles: ['ceo', 'professional', 'secretary'], hint: 'Agenda interactiva de turnos por profesional y sede' },
    { id: 'patients', labelKey: 'nav.patients' as const, icon: <Users size={17} />, path: '/pacientes', roles: ['ceo', 'professional', 'secretary'], hint: 'Base de pacientes con ficha clinica, odontograma y anamnesis' },
    { id: 'chats', labelKey: 'nav.chats' as const, icon: <MessageSquare size={17} />, path: '/chats', roles: ['ceo', 'professional', 'secretary'], hint: 'Conversaciones de WhatsApp, Instagram y Facebook en un solo lugar' },
    { id: 'approvals', labelKey: 'nav.staff' as const, icon: <ShieldCheck size={17} />, path: '/aprobaciones', roles: ['ceo'], hint: 'Aprobar o suspender acceso de profesionales y secretarias' },
    { id: 'tenants', labelKey: 'nav.clinics' as const, icon: <Stethoscope size={17} />, path: '/sedes', roles: ['ceo'], hint: 'Configurar sedes, horarios por dia, direcciones y datos bancarios' },
    { id: 'analytics', labelKey: 'nav.strategy' as const, icon: <BarChart3 size={17} />, path: '/analytics/professionals', roles: ['ceo'], hint: 'Rendimiento de cada profesional: turnos, retención, facturación' },
    { id: 'tokens', labelKey: 'nav.tokens' as const, icon: <Zap size={17} />, path: '/dashboard/status', roles: ['ceo'], hint: 'Consumo de IA por servicio, costos y seleccion de modelos' },
    { id: 'treatments', labelKey: 'nav.treatments' as const, icon: <Clock size={17} />, path: '/tratamientos', roles: ['ceo', 'secretary'], hint: 'Tipos de tratamiento con precios, duracion e imagenes' },
    { id: 'my-liquidations', labelKey: 'nav.my_liquidations' as const, icon: <Wallet size={17} />, path: '/mis-liquidaciones', roles: ['professional'], hint: 'Tus liquidaciones, comisiones y estado de pagos' },
    { id: 'profile', labelKey: 'nav.profile' as const, icon: <User size={17} />, path: '/perfil', roles: ['ceo', 'professional', 'secretary'], hint: 'Tu perfil y datos de cuenta' },
    { id: 'marketing', labelKey: 'nav.marketing' as const, icon: <Megaphone size={17} />, path: '/marketing', roles: ['ceo'], hint: 'ROI real de Meta Ads y Google Ads con atribución de pacientes' },
    { id: 'roi', labelKey: 'nav.roi' as const, icon: <TrendingUp size={17} />, path: '/roi', roles: ['ceo'], hint: 'Dashboard de ROI con atribución, tendencias y campañas top' },
    { id: 'leads', labelKey: 'nav.leads' as const, icon: <Users size={17} />, path: '/leads', roles: ['ceo'], hint: 'Leads de formularios de Meta con estado y seguimiento' },
    { id: 'templates', labelKey: 'nav.hsm' as const, icon: <Layout size={17} />, path: '/templates', roles: ['ceo'], hint: 'Plantillas HSM de WhatsApp y reglas de automatización' },
    { id: 'settings', labelKey: 'nav.settings' as const, icon: <Settings size={17} />, path: '/configuracion', roles: ['ceo'], hint: 'Configuración general, integraciones y credenciales' },
  ];

  const filteredItems = menuItems.filter(item => user && item.roles.includes(user.role));

  const isActive = (path: string) => {
    if (path === '/' && location.pathname !== '/') return false;
    return location.pathname === path;
  };

  const isHovered = (id: string) => hoveredId === id || touchedId === id;

  return (
    <aside className="h-full bg-[#0a0e1a] text-white flex flex-col relative shadow-2xl overflow-hidden">
      {/* Logo Area */}
      <div className={`h-16 flex items-center ${collapsed && !onCloseMobile ? 'justify-center' : 'px-5'} border-b border-white/[0.06] shrink-0`}>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-white/[0.08] flex items-center justify-center shrink-0 overflow-hidden">
            {logoUrl ? (
              <img src={logoUrl} alt="Logo" className="w-full h-full object-cover rounded-lg" />
            ) : (
              <Stethoscope size={17} className="text-white/70" />
            )}
          </div>
          {(!collapsed || onCloseMobile) && (
            <span className="font-semibold text-[15px] truncate whitespace-nowrap text-white/90 tracking-tight">{clinicName || t('nav.app_name')}</span>
          )}
        </div>

        {onCloseMobile && (
          <button
            onClick={onCloseMobile}
            className="lg:hidden p-2 ml-auto text-white/40 hover:text-white transition-colors"
            aria-label={t('nav.close_menu')}
          >
            <X size={22} />
          </button>
        )}
      </div>

      {/* Toggle Button (Desktop only) */}
      {!onCloseMobile && (
        <button
          onClick={onToggle}
          className="hidden lg:flex absolute -right-3 top-20 w-6 h-6 bg-white/90 rounded-full shadow-lg items-center justify-center text-[#0a0e1a] hover:bg-white transition-all z-20"
          aria-label={collapsed ? t('nav.expand') : t('nav.collapse')}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
        </button>
      )}

      {/* Navigation */}
      <nav className={`flex-1 py-3 overflow-y-auto overflow-x-hidden ${collapsed && !onCloseMobile ? 'px-1.5' : 'px-2'}`}>
        {filteredItems.map((item) => {
          const active = isActive(item.path);
          const hovered = isHovered(item.id);
          const showImage = hovered || active;

          return (
            <div key={item.id} className="relative mb-1">
              <button
                onClick={() => {
                  navigate(item.path);
                  setTooltipId(null);
                  setTouchedId(null);
                  onCloseMobile?.();
                }}
                onMouseEnter={() => {
                  setHoveredId(item.id);
                  if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
                  tooltipTimer.current = setTimeout(() => setTooltipId(item.id), 600);
                }}
                onMouseLeave={() => {
                  setHoveredId(null);
                  if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
                  setTooltipId(null);
                }}
                onTouchStart={() => {
                  setTouchedId(item.id);
                  if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
                  tooltipTimer.current = setTimeout(() => setTooltipId(item.id), 500);
                }}
                onTouchEnd={() => {
                  setTimeout(() => setTouchedId(null), 300);
                  if (tooltipTimer.current) clearTimeout(tooltipTimer.current);
                }}
                className={`
                  w-full relative overflow-hidden rounded-xl transition-all duration-300 ease-out group
                  ${collapsed && !onCloseMobile ? 'h-10' : 'h-11'}
                  ${active
                    ? 'ring-1 ring-white/[0.12] shadow-lg shadow-white/[0.03]'
                    : 'hover:ring-1 hover:ring-white/[0.06]'
                  }
                `}
                style={{
                  transform: showImage ? 'scale(1.03)' : 'scale(1)',
                  transition: 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1), box-shadow 0.3s ease',
                }}
                title={collapsed && !onCloseMobile ? t(item.labelKey) : undefined}
              >
                {/* Background image — fades in on hover/active */}
                <div
                  className="absolute inset-0 bg-cover bg-center transition-opacity duration-500 ease-out"
                  style={{
                    backgroundImage: `url(${CARD_IMAGES[item.id] || ''})`,
                    opacity: showImage ? 0.12 : 0,
                  }}
                />

                {/* Dark overlay to keep text readable */}
                <div className={`absolute inset-0 transition-all duration-500 ${
                  active
                    ? 'bg-white/[0.08]'
                    : showImage
                      ? 'bg-white/[0.04]'
                      : 'bg-transparent'
                }`} />

                {/* Subtle gradient edge */}
                {showImage && (
                  <div className="absolute inset-0 bg-gradient-to-r from-blue-500/[0.06] to-transparent pointer-events-none" />
                )}

                {/* Content */}
                <div className={`relative h-full flex items-center gap-2.5 ${collapsed && !onCloseMobile ? 'justify-center px-0' : 'px-3'}`}>
                  <span className={`shrink-0 transition-all duration-300 ${
                    active ? 'text-white' : 'text-white/40 group-hover:text-white/80'
                  }`}>
                    {item.icon}
                  </span>
                  {(!collapsed || onCloseMobile) && (
                    <span className={`font-medium text-[13px] truncate transition-all duration-300 ${
                      active ? 'text-white' : 'text-white/50 group-hover:text-white/85'
                    }`}>
                      {t(item.labelKey)}
                    </span>
                  )}

                  {/* Active indicator — thin left bar */}
                  {active && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-[2px] h-5 bg-blue-400 rounded-r-full" />
                  )}
                </div>
              </button>

              {/* Tooltip popup */}
              {tooltipId === item.id && (!collapsed || onCloseMobile) && item.hint && (
                <div
                  className="absolute left-full top-0 ml-3 z-50 w-56 bg-[#0d1117] text-white rounded-xl px-3.5 py-2.5 shadow-2xl border border-white/[0.08] pointer-events-none"
                  style={{
                    animation: 'sidebar-tooltip-in 0.15s ease-out',
                  }}
                >
                  <p className="text-[11px] font-semibold text-white/80 mb-0.5">{t(item.labelKey)}</p>
                  <p className="text-[10px] text-white/40 leading-relaxed">{item.hint}</p>
                  <div className="absolute right-full top-3 w-0 h-0 border-t-[5px] border-t-transparent border-r-[6px] border-r-[#0d1117] border-b-[5px] border-b-transparent" />
                </div>
              )}
            </div>
          );
        })}

        {/* Logout */}
        <button
          onClick={logout}
          onMouseEnter={() => setHoveredId('logout')}
          onMouseLeave={() => setHoveredId(null)}
          className="w-full relative overflow-hidden rounded-xl h-11 mt-3 group transition-all duration-300"
          style={{
            transform: hoveredId === 'logout' ? 'scale(1.03)' : 'scale(1)',
            transition: 'transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1)',
          }}
          title={collapsed && !onCloseMobile ? t('nav.logout') : undefined}
        >
          <div className={`absolute inset-0 transition-all duration-300 ${hoveredId === 'logout' ? 'bg-red-500/[0.08]' : 'bg-transparent'}`} />
          <div className={`relative h-full flex items-center gap-2.5 ${collapsed && !onCloseMobile ? 'justify-center px-0' : 'px-3'}`}>
            <span className="shrink-0 text-red-400/60 group-hover:text-red-400 transition-colors duration-300"><LogOut size={17} /></span>
            {(!collapsed || onCloseMobile) && <span className="font-medium text-[13px] text-red-400/60 group-hover:text-red-400 transition-colors duration-300">{t('nav.logout')}</span>}
          </div>
        </button>
      </nav>

      {/* Footer Info */}
      {(!collapsed || onCloseMobile) && (
        <div className="p-4 border-t border-white/[0.06] shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-white/[0.06] flex items-center justify-center text-xs font-medium uppercase shrink-0 text-white/50">
              {user?.email?.[0] || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-medium truncate text-white/70">{user?.email}</p>
              <p className="text-[10px] text-white/25 truncate uppercase tracking-wider font-semibold">{user?.role}</p>
            </div>
          </div>
        </div>
      )}

      {/* Animation keyframes */}
      <style>{`
        @keyframes sidebar-tooltip-in {
          from { opacity: 0; transform: translateX(-4px); }
          to { opacity: 1; transform: translateX(0); }
        }
      `}</style>
    </aside>
  );
};

export default Sidebar;
