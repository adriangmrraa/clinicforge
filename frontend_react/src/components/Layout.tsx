import React, { type ReactNode, useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../context/LanguageContext';
import { io, Socket } from 'socket.io-client';
import { BACKEND_URL } from '../api/axios';
import { AlertCircle, X, Wifi, WifiOff } from 'lucide-react';
import MetaTokenBanner from './MetaTokenBanner';

interface LayoutProps {
  children: ReactNode;
}

export const Layout: React.FC<LayoutProps> = ({ children }) => {
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
    phone: string;
    reason: string;
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
    const handleHandoff = (data: { phone_number: string; reason: string }) => {

      // Mostrar notificación
      setNotification({
        show: true,
        phone: data.phone_number,
        reason: data.reason
      });

      // Auto-ocultar a los 5 segundos
      setTimeout(() => {
        setNotification(null);
      }, 5000);

      // Reproducir sonido (opcional, si el navegador lo permite)
      try {
        const audio = new Audio('/assets/notification.mp3');
        // Fallback or generic sound logic here if asset missing
        audio.play().catch(_e => { });
      } catch (e) { }
    };

    socket.on('HUMAN_HANDOFF', handleHandoff);

    return () => {
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('reconnect_attempt', onReconnectAttempt);
      socket.off('reconnect', onConnect);
      socket.off('HUMAN_HANDOFF', handleHandoff);
    };
  }, [user]);

  const handleNotificationClick = () => {
    if (notification) {
      // Navegar al chat seleccionando el teléfono
      navigate('/chats', { state: { selectPhone: notification.phone } });
      setNotification(null);
    }
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

      {/* GLOBAL NOTIFICATION TOAST */}
      {notification && (
        <div
          className="fixed bottom-6 right-6 z-50 max-w-sm w-full bg-white rounded-lg shadow-xl border-l-4 border-orange-500 p-4 transform transition-all duration-300 ease-in-out cursor-pointer hover:bg-gray-50"
          onClick={handleNotificationClick}
        >
          <div className="flex items-start gap-3">
            <div className="flex-shrink-0">
              <AlertCircle className="h-6 w-6 text-orange-500" />
            </div>
            <div className="flex-1">
              <h3 className="text-sm font-medium text-gray-900">🔔 {t('layout.notification_handoff')}</h3>
              <p className="mt-1 text-sm text-gray-500 line-clamp-2">
                {notification.phone}. {t('layout.notification_reason')}: {notification.reason}
              </p>
              <div className="mt-2 text-xs text-orange-600 font-medium">
                {t('layout.click_to_open_chat')}
              </div>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setNotification(null); }}
              className="text-gray-400 hover:text-gray-600"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Layout;
