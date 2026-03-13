import React, { type ReactNode, useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../context/LanguageContext';
import { io, Socket } from 'socket.io-client';
import { BACKEND_URL } from '../api/axios';
import { X, Wifi, WifiOff, Bell, UserPlus, Calendar, AlertTriangle } from 'lucide-react';
import MetaTokenBanner from './MetaTokenBanner';

interface LayoutProps {
  children: ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }: LayoutProps) => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { user } = useAuth();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const socketRef = useRef<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(true); // Default true to avoid flash
  const [isReconnecting, setIsReconnecting] = useState(false);

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
  useEffect(() => {
    if (!user) return;

    // Conectar socket si no existe
    if (!socketRef.current) {
      // Connect to root namespace (matching ChatsView.tsx logic)
      socketRef.current = io(BACKEND_URL, {
        reconnection: true,
        reconnectionAttempts: Infinity,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        randomizationFactor: 0.5
      });
    }

    const socket = socketRef.current;

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

    const handleAppointment = (data: { patient_name: string; id: string | number; tenant_id?: number }) => {
      if (data.tenant_id && user.tenant_id && data.tenant_id !== user.tenant_id) return;
      showNotification({
        show: true,
        type: 'appointment',
        name: data.patient_name,
        appointment_id: data.id,
        reason: 'Nuevo agendamiento realizado por la IA',
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
    };
  }, [user]);

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
    <div className="flex h-screen bg-gradient-to-br from-slate-50 to-blue-50 relative overflow-hidden">
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
        <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-4 lg:px-6 shadow-sm sticky top-0 z-30">
          <div className="flex items-center gap-3 lg:gap-4">
            {/* Hamburger Button for Mobile */}
            <button
              onClick={() => setIsMobileMenuOpen(true)}
              className="lg:hidden p-2 hover:bg-gray-100 rounded-lg text-gray-600"
            >
              <div className="w-6 h-5 flex flex-col justify-between">
                <span className="w-full h-0.5 bg-current rounded-full"></span>
                <span className="w-full h-0.5 bg-current rounded-full"></span>
                <span className="w-full h-0.5 bg-current rounded-full"></span>
              </div>
            </button>
            <h1 className="text-lg lg:text-xl font-semibold text-medical-900 truncate max-w-[150px] md:max-w-none">
              {t('layout.app_title')}
            </h1>
          </div>

          <div className="flex items-center gap-2 lg:gap-4">
            {/* Connection Status Chip */}
            <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] lg:text-xs font-medium transition-colors ${isReconnecting ? 'bg-orange-100 text-orange-700 animate-pulse' :
                isConnected ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
              }`}>
              {isReconnecting ? <WifiOff size={12} /> : <Wifi size={12} />}
              <span className="hidden xs:inline">
                {isReconnecting ? t('layout.status_reconnecting') :
                  isConnected ? t('layout.status_connected') : 'Offline'}
              </span>
            </div>

            {/* Tenant Selector - Hidden on small mobile */}
            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-gray-100 rounded-lg text-sm">
              <span className="text-gray-500">{t('layout.branch')}:</span>
              <span className="font-medium text-medical-900">{t('layout.branch_principal')}</span>
            </div>

            {/* User Menu */}
            <div className="flex items-center gap-2 lg:gap-3">
              <div className="hidden xs:flex flex-col items-end">
                <span className="text-xs lg:text-sm font-medium text-medical-900">{user?.email?.split('@')[0]}</span>
                <span className="text-[10px] lg:text-xs text-secondary uppercase leading-none">{user?.role}</span>
              </div>
              <div className="w-8 h-8 lg:w-9 lg:h-9 rounded-full bg-medical-600 flex items-center justify-center text-white font-semibold text-sm lg:text-lg border-2 border-white shadow-sm">
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
