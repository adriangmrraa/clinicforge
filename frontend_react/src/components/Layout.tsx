import React, { type ReactNode, useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../context/LanguageContext';
import { getSocket, disconnectSocket } from '../services/socket';
import { setTenantId, getCurrentTenantId } from '../api/axios';
import api from '../api/axios';
import { X, Wifi, WifiOff, Bell, UserPlus, Calendar, AlertTriangle, HelpCircle } from 'lucide-react';
import MetaTokenBanner from './MetaTokenBanner';
import { NovaWidget } from './NovaWidget';
import OnboardingGuide from './OnboardingGuide';
import PageTips from './PageTips';

interface LayoutProps {
  children: ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }: LayoutProps) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { user } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [isConnected, setIsConnected] = useState(true);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [novaTooltip, setNovaTooltip] = useState(false);
  const [guideTooltip, setGuideTooltip] = useState(false);
  const tooltipShownRef = useRef(false);

  // Tenant selector state (CEO multi-clinic)
  const [tenants, setTenants] = useState<{ id: number; clinic_name: string }[]>([]);
  const [activeTenantId, setActiveTenantId] = useState<string>(getCurrentTenantId() || '');

  useEffect(() => {
    if (user?.role === 'ceo') {
      api.get('/admin/chat/tenants').then(res => {
        const list = Array.isArray(res.data) ? res.data : [];
        setTenants(list);
        // If no tenant selected yet, default to first
        if (!activeTenantId && list.length > 0) {
          const defaultId = String(list[0].id);
          setActiveTenantId(defaultId);
          setTenantId(defaultId);
        }
      }).catch(() => {});
    }
  }, [user?.role]);

  const handleTenantChange = (newTenantId: string) => {
    setActiveTenantId(newTenantId);
    setTenantId(newTenantId);
    // Dispatch event so all views can react to tenant change
    window.dispatchEvent(new CustomEvent('tenant-changed', { detail: { tenantId: newTenantId } }));
    // Reload current page to refresh data for new tenant
    window.location.reload();
  };

  // Notification State
  const [notification, setNotification] = useState<{
    show: boolean;
    type: 'handoff' | 'new_patient' | 'urgency' | 'appointment';
    phone?: string;
    reason?: string;
    name?: string;
    id?: string | number;
    urgency_level?: string;
    appointment_id?: string | number;
  } | null>(null);

  // Global Socket Listener for Handoffs
  // Tooltip sequence: Nova at 3s, Guide at 8s — only once per session
  useEffect(() => {
    if (tooltipShownRef.current) return;
    const alreadyShown = sessionStorage.getItem('tooltips_shown');
    if (alreadyShown) return;
    tooltipShownRef.current = true;

    const t1 = setTimeout(() => { setNovaTooltip(true); }, 3000);
    const t2 = setTimeout(() => { setNovaTooltip(false); }, 7000);
    const t3 = setTimeout(() => { setGuideTooltip(true); }, 8000);
    const t4 = setTimeout(() => { setGuideTooltip(false); sessionStorage.setItem('tooltips_shown', '1'); }, 12000);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4); };
  }, []);

  useEffect(() => {
    if (!user) return;

    const socket = getSocket();

    const onConnect = () => {
      setIsConnected(true);
      setIsReconnecting(false);
    };

    const onDisconnect = () => {
      setIsConnected(false);
    };

    const onReconnectAttempt = () => {
      setIsReconnecting(true);
    };

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);
    socket.on('reconnect_attempt', onReconnectAttempt);
    socket.on('reconnect', onConnect);

    // Listener
    // Listener
    // --- NOTIFICATION HANDLERS ---
    
    const showNotification = (notif: typeof notification) => {
      if (!notif) return;
      setNotification(notif);
      
      // Auto-ocultar a los 10 segundos (Requerimiento Spec v7.6)
      setTimeout(() => {
        setNotification((prev: any) => (prev?.id === notif?.id ? null : prev));
      }, 10000);

      // Reproducir sonido diferenciado
      try {
        const isCritical = notif.type === 'urgency' && notif.urgency_level === 'emergency';
        const audioPath = isCritical ? '/assets/critical_alert.mp3' : '/assets/notification.mp3';
        const audio = new Audio(audioPath);
        audio.play().catch(_e => { });
      } catch (e) { }
    };

    const handleHandoff = (data: { phone_number: string; reason: string; tenant_id?: number }) => {
      if (data.tenant_id && user.tenant_id && data.tenant_id !== user.tenant_id) return;
      showNotification({
        show: true,
        type: 'handoff',
        phone: data.phone_number,
        reason: data.reason,
        id: Date.now()
      });
    };

    const handleNewPatient = (data: { name: string; phone_number: string; channel: string; tenant_id?: number }) => {
      if (data.tenant_id && user.tenant_id && data.tenant_id !== user.tenant_id) return;
      showNotification({
        show: true,
        type: 'new_patient',
        name: data.name,
        phone: data.phone_number,
        reason: `Nuevo lead vía ${data.channel}`,
        id: Date.now()
      });
    };

    const handleUrgency = (data: { patient_name: string; urgency_level: string; urgency_reason: string; phone_number: string; tenant_id?: number }) => {
      if (data.tenant_id && user.tenant_id && data.tenant_id !== user.tenant_id) return;
      showNotification({
        show: true,
        type: 'urgency',
        name: data.patient_name,
        phone: data.phone_number,
        reason: data.urgency_reason,
        urgency_level: data.urgency_level,
        id: Date.now()
      });
    };

    const handleAppointment = (data: { patient_name: string; id: string | number; tenant_id?: number; source?: string }) => {
      if (data.tenant_id && user.tenant_id && data.tenant_id !== user.tenant_id) return;
      const reason = data.source === 'manual'
        ? t('common.notification_appointment_manual')
        : t('common.notification_appointment_ai');
      showNotification({
        show: true,
        type: 'appointment',
        name: data.patient_name,
        appointment_id: data.id,
        reason,
        id: Date.now()
      });
    };

    socket.on('HUMAN_HANDOFF', handleHandoff);
    socket.on('NEW_PATIENT', handleNewPatient);
    socket.on('PATIENT_UPDATED', handleUrgency);
    socket.on('NEW_APPOINTMENT', handleAppointment);

    return () => {
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('reconnect_attempt', onReconnectAttempt);
      socket.off('reconnect', onConnect);
      socket.off('HUMAN_HANDOFF', handleHandoff);
      socket.off('NEW_PATIENT', handleNewPatient);
      socket.off('PATIENT_UPDATED', handleUrgency);
      socket.off('NEW_APPOINTMENT', handleAppointment);
      // NOTE: do NOT call disconnectSocket() here — the singleton stays alive
      // Call disconnectSocket() only on explicit logout
    };
  }, [user]);

  // Disconnect socket on logout (called externally via window event or AuthContext)
  useEffect(() => {
    const onLogout = () => disconnectSocket();
    window.addEventListener('auth:logout', onLogout);
    return () => window.removeEventListener('auth:logout', onLogout);
  }, []);

  const handleNotificationClick = () => {
    if (!notification) return;

    switch (notification.type) {
      case 'appointment':
        navigate('/agenda', { state: { openAppointmentId: notification.appointment_id } });
        break;
      case 'urgency':
      case 'handoff':
        navigate('/chats', { state: { selectPhone: notification.phone } });
        break;
      case 'new_patient':
        navigate('/leads');
        break;
      default:
        break;
    }
    setNotification(null);
  };

  return (
    <div className="flex h-screen bg-[#06060e] relative overflow-hidden">
      {/* Mobile Backdrop */}
      {isMobileMenuOpen && (
        <div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar - Desktop and Mobile Drawer */}
      <div className={`
        fixed lg:relative inset-y-0 left-0 z-50 transition-all duration-300 transform
        w-72 lg:w-auto
        ${isMobileMenuOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full lg:translate-x-0 shadow-none'}
        ${sidebarCollapsed ? 'lg:w-16' : 'lg:w-64'}
      `}>
        <Sidebar
          collapsed={sidebarCollapsed}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          onCloseMobile={() => setIsMobileMenuOpen(false)}
        />
      </div>

      {/* Main Content */}
      <main
        className={`flex-1 flex flex-col transition-all duration-300 w-full min-w-0 h-screen overflow-hidden`}
      >
        <MetaTokenBanner />
        {/* Top Header */}
        <header className="h-14 bg-[#0a0e1a]/80 backdrop-blur-xl border-b border-white/[0.06] flex items-center justify-between px-4 lg:px-6 sticky top-0 z-30">
          <div className="flex items-center gap-3 lg:gap-4">
            <button
              onClick={() => setIsMobileMenuOpen(true)}
              className="lg:hidden p-2 hover:bg-white/[0.06] rounded-lg text-white/50"
            >
              <div className="w-5 h-4 flex flex-col justify-between">
                <span className="w-full h-0.5 bg-current rounded-full"></span>
                <span className="w-full h-0.5 bg-current rounded-full"></span>
                <span className="w-full h-0.5 bg-current rounded-full"></span>
              </div>
            </button>
            <h1 className="text-base lg:text-lg font-semibold text-white/90 truncate max-w-[150px] md:max-w-none tracking-tight">
              {localStorage.getItem('CLINIC_NAME') || t('layout.app_title')}
            </h1>
          </div>

          <div className="flex items-center gap-2 lg:gap-3">
            {/* Guide Button — animated attention-grabber */}
            <div className="relative">
              <button
                onClick={() => { setShowGuide(true); setGuideTooltip(false); }}
                className="guide-btn relative flex items-center justify-center w-9 h-9 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 hover:bg-blue-500/25 hover:scale-110 active:scale-90 transition-all duration-200"
                title="Guia de la pagina"
              >
                <HelpCircle size={18} className="guide-icon" />
                <span className="absolute inset-0 rounded-full border-2 border-blue-400/40 animate-[guidePing_3s_ease-out_infinite]" />
              </button>
              {/* Tooltip popup */}
              {guideTooltip && (
                <div
                  className="absolute top-12 right-0 w-52 px-3 py-2 rounded-xl bg-blue-500/90 backdrop-blur-md text-white text-[11px] leading-snug shadow-xl shadow-blue-500/20 pointer-events-none"
                  style={{ animation: 'tooltipIn 0.4s cubic-bezier(0.16,1,0.3,1)' }}
                >
                  <div className="absolute -top-1.5 right-4 w-3 h-3 bg-blue-500/90 rotate-45" />
                  Toca aca para ver una guia de esta pagina y aprender que hace cada funcion
                </div>
              )}
            </div>

            {/* Connection Status Chip */}
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] lg:text-xs font-medium transition-colors ${isReconnecting ? 'bg-orange-500/10 text-orange-400 animate-pulse' :
                isConnected ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
              }`}>
              {isReconnecting ? <WifiOff size={12} /> : <Wifi size={12} />}
              <span className="hidden xs:inline">
                {isReconnecting ? t('layout.status_reconnecting') :
                  isConnected ? t('layout.status_connected') : 'Offline'}
              </span>
            </div>

            {/* Tenant Selector */}
            {user?.role === 'ceo' && tenants.length > 1 ? (
              <select
                value={activeTenantId}
                onChange={(e) => handleTenantChange(e.target.value)}
                className="hidden sm:block px-3 py-1.5 bg-white/[0.04] rounded-lg text-sm border border-white/[0.06] text-white/70 font-medium outline-none focus:ring-2 focus:ring-indigo-500/30 cursor-pointer"
              >
                {tenants.map(t => (
                  <option key={t.id} value={String(t.id)} className="bg-[#0d1117] text-white">
                    {t.clinic_name}
                  </option>
                ))}
              </select>
            ) : (
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-white/[0.04] rounded-lg text-sm border border-white/[0.06]">
                <span className="text-white/30">{t('layout.branch')}:</span>
                <span className="font-medium text-white/70">{tenants.length === 1 ? tenants[0].clinic_name : t('layout.branch_principal')}</span>
              </div>
            )}

            {/* User Menu */}
            <div className="flex items-center gap-2 lg:gap-3">
              <div className="hidden xs:flex flex-col items-end">
                <span className="text-xs lg:text-sm font-medium text-white/80">{user?.email?.split('@')[0]}</span>
                <span className="text-[10px] lg:text-xs text-white/30 uppercase leading-none">{user?.role}</span>
              </div>
              <div className="w-8 h-8 lg:w-9 lg:h-9 rounded-lg bg-white/[0.08] flex items-center justify-center text-white/70 font-semibold text-sm lg:text-base">
                {user?.email?.[0].toUpperCase() || 'U'}
              </div>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 min-h-0 bg-transparent overflow-y-auto scroll-smooth">
          {children}
        </div>
      </main>

      {/* Page Tips — contextual animated tips per page */}
      <PageTips />

      {/* Nova AI Widget */}
      <NovaWidget />

      {/* Nova tooltip — positioned near the floating button */}
      {novaTooltip && (
        <div
          className="fixed z-[9999] pointer-events-none"
          style={{ bottom: 'calc(max(1.5rem, env(safe-area-inset-bottom)) + 60px)', right: '1.5rem' }}
        >
          <div
            className="w-56 px-3 py-2.5 rounded-xl bg-violet-500/90 backdrop-blur-md text-white text-[11px] leading-snug shadow-xl shadow-violet-500/20"
            style={{ animation: 'tooltipIn 0.4s cubic-bezier(0.16,1,0.3,1)' }}
          >
            Soy Nova, tu asistente de voz. Toca para hablarme y operar la clinica sin tocar la pantalla
            <div className="absolute -bottom-1.5 right-5 w-3 h-3 bg-violet-500/90 rotate-45" />
          </div>
        </div>
      )}

      {/* Onboarding Guide */}
      <OnboardingGuide isOpen={showGuide} onClose={() => setShowGuide(false)} />

      {/* GLOBAL PREMIUM NOTIFICATION TOAST */}
      {notification && (
        <div
          className={`fixed bottom-6 right-6 z-[100] max-w-sm w-full animate-in slide-in-from-right-10 duration-500 overflow-hidden cursor-pointer group`}
          onClick={handleNotificationClick}
        >
          {/* Glassmorphic Background with Gradient Border */}
          <div className={`relative p-[1px] rounded-2xl shadow-2xl transition-transform duration-300 hover:scale-[1.02] active:scale-[0.98]
            ${notification.type === 'urgency' ? 'bg-gradient-to-r from-red-500 via-rose-500 to-red-600' : 
              (notification.type === 'appointment' || notification.type === 'new_patient') ? 'bg-gradient-to-r from-emerald-500 via-green-500 to-emerald-600' : 
              'bg-gradient-to-r from-blue-500 via-indigo-500 to-blue-600'}`}>
            
            <div className="bg-white/95 backdrop-blur-xl rounded-[15px] p-4 flex items-start gap-4">
              {/* Animated Icon Container */}
              <div className={`relative flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center shadow-inner overflow-hidden
                ${notification.type === 'urgency' ? 'bg-red-50 text-red-600' : 
                  (notification.type === 'appointment' || notification.type === 'new_patient') ? 'bg-emerald-50 text-emerald-600' : 
                  'bg-blue-50 text-blue-600'}`}>
                
                {/* Background Glow Implementation */}
                <div className={`absolute inset-0 opacity-20 animate-pulse
                  ${notification.type === 'urgency' ? 'bg-red-400' : 
                    (notification.type === 'appointment' || notification.type === 'new_patient') ? 'bg-emerald-400' : 
                    'bg-blue-400'}`} />

                {notification.type === 'urgency' ? <AlertTriangle className="h-6 w-6 relative z-10 animate-bounce" /> : 
                 notification.type === 'appointment' ? <Calendar className="h-6 w-6 relative z-10" /> : 
                 notification.type === 'new_patient' ? <UserPlus className="h-6 w-6 relative z-10" /> : 
                 <Bell className="h-6 w-6 relative z-10" />}
              </div>

              {/* Content Area */}
              <div className="flex-1 min-w-0">
                <div className="flex justify-between items-start">
                  <span className={`text-[10px] font-black uppercase tracking-[0.15em] mb-1 block
                    ${notification.type === 'urgency' ? 'text-red-500' : 
                      (notification.type === 'appointment' || notification.type === 'new_patient') ? 'text-emerald-600' : 
                      'text-blue-600'}`}>
                    {notification.type === 'urgency' ? 'Urgent Alert' : 
                     notification.type === 'appointment' ? 'New Booking' : 
                     notification.type === 'new_patient' ? 'New Patient' : 
                     'Notification'}
                  </span>
                  <button
                    onClick={(e: React.MouseEvent) => { e.stopPropagation(); setNotification(null); }}
                    className="text-gray-400 hover:text-gray-600 p-1 -mt-1 -mr-1 transition-colors rounded-full hover:bg-gray-100"
                  >
                    <X size={14} />
                  </button>
                </div>
                
                <h3 className="text-sm font-bold text-slate-900 truncate">
                  {notification.name || notification.phone}
                </h3>
                
                <p className="mt-1 text-xs text-slate-600 font-medium line-clamp-2 leading-relaxed opacity-80">
                  {notification.reason}
                </p>

                {/* Interactive Indicator */}
                <div className="mt-3 flex items-center gap-1.5">
                  <div className={`h-1 w-1 rounded-full animate-ping
                    ${notification.type === 'urgency' ? 'bg-red-500' : 
                      (notification.type === 'appointment' || notification.type === 'new_patient') ? 'bg-emerald-500' : 
                      'bg-blue-500'}`} />
                  <span className="text-[10px] font-semibold text-slate-400 uppercase tracking-tighter group-hover:text-slate-600 transition-colors">
                    Click para gestionar
                  </span>
                </div>
              </div>
            </div>

            {/* Shine effect on hover */}
            <div className="absolute inset-0 pointer-events-none bg-gradient-to-tr from-transparent via-white/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-700 -translate-x-full group-hover:translate-x-full" />
          </div>
        </div>
      )}
    </div>
  );
};

export default Layout;
