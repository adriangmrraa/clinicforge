import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Sparkles, X, MessageSquare, Heart, BarChart3,
  Send, Mic, MicOff, Volume2, ChevronDown,
  CheckCircle2, Circle, AlertCircle, Lightbulb,
  ArrowRight, Pause, SkipForward, Building2
} from 'lucide-react';
import api, { BACKEND_URL, getCurrentTenantId } from '../api/axios';
import { useAuth } from '../context/AuthContext';

// ============================================
// TYPES
// ============================================

interface NovaCheck {
  id: string;
  type: 'alert' | 'warning' | 'suggestion' | 'info';
  message: string;
  action?: string;
  count?: number;
}

interface NovaContext {
  score: number;
  score_label: string;
  checks: NovaCheck[];
  completed: { label: string; detail?: string }[];
  pending: { label: string; action?: string; weight: number }[];
  stats: {
    appointments_today: number;
    total_patients: number;
    pending_payments: number;
    cancellations_today: number;
  };
  greeting: string;
}

interface NovaInsights {
  has_data: boolean;
  summary?: string;
  stats_line?: string;
  frequent_topics?: { topic: string; count: number }[];
  problems?: string[];
  suggestions?: { text: string; action?: string; applied?: boolean }[];
  cross_sede?: { comparisons: string[]; ranking: { sede: string; score: number }[] };
}

interface OnboardingStatus {
  completed: number;
  total: number;
  items: { label: string; completed: boolean; action?: string }[];
}

interface Sede {
  id: number;
  name: string;
  score?: number;
}

interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  timestamp: number;
}

interface ConsolidatedData {
  score: number;
  sedes: { name: string; score: number }[];
  alerts: { sede: string; message: string; type: string }[];
  stats: NovaContext['stats'];
}

type VoiceState = 'idle' | 'listening' | 'processing' | 'speaking';
type TabKey = 'chat' | 'salud' | 'insights';

// ============================================
// CONSTANTS
// ============================================

const ACTION_ROUTES: Record<string, string> = {
  confirmar_turnos: '/agenda',
  ver_agenda: '/agenda',
  conectar_gcal: '/configuracion',
  agregar_faqs: '/configuracion',
  ver_pacientes: '/pacientes',
  ver_tratamientos: '/tratamientos',
  facturacion_pendiente: '/agenda',
  ver_chats: '/chats',
  ver_analytics: '/analytics/professionals',
  configurar_horarios: '/configuracion',
  ver_marketing: '/marketing',
};

const CHECK_STYLES: Record<string, string> = {
  alert: 'bg-red-500/10 border-red-500/20 text-red-300',
  warning: 'bg-amber-500/10 border-amber-500/20 text-amber-300',
  suggestion: 'bg-cyan-500/10 border-cyan-500/20 text-cyan-300',
  info: 'bg-blue-500/10 border-blue-500/20 text-blue-300',
};

const HIDDEN_PATHS = ['/login', '/anamnesis', '/demo', '/privacy', '/terms'];

// ============================================
// HELPERS
// ============================================

const getScoreColor = (score: number): string => {
  if (score >= 80) return 'text-emerald-400';
  if (score >= 50) return 'text-amber-400';
  return 'text-red-400';
};

const getScoreBarColor = (score: number): string => {
  if (score >= 80) return 'bg-emerald-400';
  if (score >= 50) return 'bg-amber-400';
  return 'bg-red-400';
};

const getScoreLabel = (score: number): string => {
  if (score >= 80) return 'Tu clinica va excelente!';
  if (score >= 50) return 'Tu clinica va bien!';
  return 'Tu clinica necesita atencion';
};

const detectCurrentPage = (pathname: string): string => {
  if (pathname === '/') return 'dashboard';
  if (pathname.includes('sedes')) return 'sedes';
  if (pathname.includes('agenda')) return 'agenda';
  if (pathname.includes('paciente')) return 'pacientes';
  if (pathname.includes('chat')) return 'chats';
  if (pathname.includes('tratamiento')) return 'tratamientos';
  if (pathname.includes('analytics')) return 'analytics';
  if (pathname.includes('config')) return 'configuracion';
  if (pathname.includes('marketing')) return 'marketing';
  if (pathname.includes('leads')) return 'leads';
  return 'dashboard';
};

const msgId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

// ============================================
// COMPONENT
// ============================================

export const NovaWidget: React.FC = () => {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // --- UI State ---
  const [isOpen, setIsOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<TabKey>('chat');
  const [showPulse, setShowPulse] = useState(true);
  const [toastVisible, setToastVisible] = useState(false);
  const [toastMessage, setToastMessage] = useState('');
  const [toastChecked, setToastChecked] = useState(false);

  // --- Data State ---
  const [novaCtx, setNovaCtx] = useState<NovaContext | null>(null);
  const [insights, setInsights] = useState<NovaInsights | null>(null);
  const [onboarding, setOnboarding] = useState<OnboardingStatus | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [isThinking, setIsThinking] = useState(false);
  const [consolidated, setConsolidated] = useState<ConsolidatedData | null>(null);

  // --- Sede State (CEO only) ---
  const [sedes, setSedes] = useState<Sede[]>([]);
  const [currentSede, setCurrentSede] = useState<number | null>(null);
  const [sedeDropdownOpen, setSedeDropdownOpen] = useState(false);
  const [consolidatedMode, setConsolidatedMode] = useState(false);

  // --- Voice State ---
  const [voiceActive, setVoiceActive] = useState(false);
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const [micPaused, setMicPaused] = useState(false);

  // --- Refs ---
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const captureCtxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef(0);
  const micPausedRef = useRef(false);
  const novaPlayingRef = useRef(false);
  const transcriptBufferRef = useRef('');
  const sedeDropdownRef = useRef<HTMLDivElement>(null);

  const isCeo = user?.role === 'ceo';
  const currentPage = detectCurrentPage(location.pathname);

  // ============================================
  // DATA FETCHING
  // ============================================

  const loadNovaContext = useCallback(async (tenantId?: number) => {
    try {
      const params: Record<string, string> = { page: currentPage };
      if (tenantId) params.tenant_id = tenantId.toString();
      const { data } = await api.get('/admin/nova/context', { params });
      setNovaCtx(data);
    } catch (err) {
      console.error('[Nova] Failed to load context:', err);
    }
  }, [currentPage]);

  const loadInsights = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/nova/daily-analysis');
      setInsights(data);
    } catch {
      setInsights({ has_data: false });
    }
  }, []);

  const loadOnboarding = useCallback(async () => {
    try {
      const { data } = await api.get('/admin/nova/onboarding-status');
      setOnboarding(data);
    } catch {
      setOnboarding(null);
    }
  }, []);

  const loadConsolidated = useCallback(async () => {
    if (!isCeo) return;
    try {
      const { data } = await api.get('/admin/nova/health-check');
      setConsolidated(data);
    } catch {
      setConsolidated(null);
    }
  }, [isCeo]);

  // Load sedes for CEO
  useEffect(() => {
    if (isCeo) {
      api.get('/admin/tenants').then(({ data }) => {
        const list = Array.isArray(data) ? data : data.tenants || [];
        setSedes(list.map((t: any) => ({ id: t.id, name: t.name, score: t.nova_score })));
      }).catch(() => {});
    }
  }, [isCeo]);

  // Load context when widget opens or sede changes
  useEffect(() => {
    if (!isOpen) return;
    loadNovaContext(currentSede ?? undefined);
    loadInsights();
    loadOnboarding();
    if (consolidatedMode) loadConsolidated();
  }, [isOpen, currentSede, consolidatedMode, loadNovaContext, loadInsights, loadOnboarding, loadConsolidated]);

  // Send session info on page change
  useEffect(() => {
    if (!isOpen) return;
    const patientMatch = location.pathname.match(/\/pacientes\/(\d+)/);
    api.post('/admin/nova/session', {
      page: currentPage,
      patient_id: patientMatch ? patientMatch[1] : undefined,
    }).catch(() => {});
  }, [isOpen, currentPage, location.pathname]);

  // Stop pulse after 10 seconds
  useEffect(() => {
    const timer = setTimeout(() => setShowPulse(false), 10000);
    return () => clearTimeout(timer);
  }, []);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isThinking]);

  // Close sede dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (sedeDropdownRef.current && !sedeDropdownRef.current.contains(e.target as Node)) {
        setSedeDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  // ============================================
  // TOAST NOTIFICATION
  // ============================================

  useEffect(() => {
    if (toastChecked) return;
    setToastChecked(true);
    const shown = sessionStorage.getItem('nova_toast_shown');
    if (shown) return;

    api.get('/admin/nova/context', { params: { page: currentPage } }).then(({ data }) => {
      const criticals = (data.checks || []).filter((c: NovaCheck) => c.type === 'alert');
      if (criticals.length > 0) {
        setToastMessage(criticals[0].message);
        setToastVisible(true);
        sessionStorage.setItem('nova_toast_shown', '1');
        setTimeout(() => setToastVisible(false), 8000);
      }
    }).catch(() => {});
  }, [toastChecked, currentPage]);

  // ============================================
  // CHAT LOGIC
  // ============================================

  const ensureWsConnection = useCallback(async (): Promise<WebSocket | null> => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return wsRef.current;
    }
    try {
      const { data: session } = await api.post('/admin/nova/session', { page: currentPage });
      const sessionId = session.session_id || session.id;
      const wsBase = BACKEND_URL.replace(/^http/, 'ws');
      const token = localStorage.getItem('access_token') || '';
      const ws = new WebSocket(`${wsBase}/public/nova/realtime-ws/${sessionId}?token=${token}`);
      wsRef.current = ws;

      return new Promise((resolve) => {
        ws.onopen = () => resolve(ws);
        ws.onerror = () => resolve(null);
        ws.onmessage = (evt) => {
          if (typeof evt.data !== 'string') return;
          try {
            const msg = JSON.parse(evt.data);
            if (msg.type === 'transcript' && msg.role === 'assistant') {
              transcriptBufferRef.current += msg.text;
            }
            if (msg.type === 'response_done') {
              if (transcriptBufferRef.current) {
                setMessages(prev => [...prev, {
                  id: msgId(), role: 'assistant', text: transcriptBufferRef.current, timestamp: Date.now(),
                }]);
                transcriptBufferRef.current = '';
              }
              setIsThinking(false);

              // Refresh context after responses
              loadNovaContext(currentSede ?? undefined);
            }
            if (msg.type === 'error') {
              setMessages(prev => [...prev, {
                id: msgId(), role: 'assistant', text: msg.message || 'Error de conexion.', timestamp: Date.now(),
              }]);
              setIsThinking(false);
            }
          } catch { /* ignore parse errors */ }
        };
        ws.onclose = () => { wsRef.current = null; };
      });
    } catch {
      return null;
    }
  }, [currentPage, currentSede, loadNovaContext]);

  const sendMessage = useCallback(async (text: string) => {
    if (!text.trim()) return;
    const userMsg: ChatMessage = { id: msgId(), role: 'user', text: text.trim(), timestamp: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    setInputText('');
    setIsThinking(true);

    try {
      const ws = await ensureWsConnection();
      if (!ws) {
        throw new Error('No WebSocket connection');
      }
      ws.send(JSON.stringify({
        type: 'conversation.item.create',
        item: { type: 'message', role: 'user', content: [{ type: 'input_text', text: text.trim() }] },
      }));
      ws.send(JSON.stringify({ type: 'response.create' }));
      transcriptBufferRef.current = '';
    } catch {
      setMessages(prev => [
        ...prev,
        { id: msgId(), role: 'assistant', text: 'Error de conexion. Intenta de nuevo.', timestamp: Date.now() },
      ]);
      setIsThinking(false);
    }
  }, [ensureWsConnection]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage(inputText);
    }
  };

  // ============================================
  // VOICE PIPELINE
  // ============================================

  const playRealtimeAudio = useCallback((arrayBuffer: ArrayBuffer) => {
    if (!playbackCtxRef.current || playbackCtxRef.current.state === 'closed') {
      playbackCtxRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({ sampleRate: 24000 });
      nextPlayTimeRef.current = 0;
    }
    const ctx = playbackCtxRef.current;
    if (ctx.state === 'suspended') ctx.resume().catch(() => {});

    const pcm16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) float32[i] = pcm16[i] / 32768;

    const buffer = ctx.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);

    const startTime = Math.max(ctx.currentTime, nextPlayTimeRef.current);
    src.start(startTime);
    nextPlayTimeRef.current = startTime + buffer.duration;
  }, []);

  const cancelPlayback = useCallback(() => {
    if (playbackCtxRef.current && playbackCtxRef.current.state !== 'closed') {
      try { playbackCtxRef.current.close(); } catch (_) { /* ignore */ }
    }
    playbackCtxRef.current = null;
    nextPlayTimeRef.current = 0;
    novaPlayingRef.current = false;
    if (!micPaused) micPausedRef.current = false;
  }, [micPaused]);

  const stopRealtimeAudio = useCallback(() => {
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null; }
    if (captureCtxRef.current && captureCtxRef.current.state !== 'closed') {
      captureCtxRef.current.close();
    }
    captureCtxRef.current = null;
    cancelPlayback();
    novaPlayingRef.current = false;
    micPausedRef.current = false;
    setVoiceState('idle');
    setVoiceActive(false);
    setMicPaused(false);
  }, [cancelPlayback]);

  const startVoice = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const captureCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      captureCtxRef.current = captureCtx;
      if (captureCtx.state === 'suspended') captureCtx.resume().catch(() => {});
      const nativeSampleRate = captureCtx.sampleRate;

      // Build WS URL
      const wsBase = BACKEND_URL.replace(/^http/, 'ws');
      const tenantId = getCurrentTenantId() || '1';
      const token = localStorage.getItem('access_token') || '';
      const wsUrl = `${wsBase}/public/nova/voice?tenant_id=${tenantId}&token=${token}&page=${currentPage}`;

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        setVoiceActive(true);
        setVoiceState('listening');

        const source = captureCtx.createMediaStreamSource(stream);
        const processor = captureCtx.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;

        processor.onaudioprocess = (e) => {
          if (micPausedRef.current) return;
          if (novaPlayingRef.current) return;
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

          const input = e.inputBuffer.getChannelData(0);
          const ratio = nativeSampleRate / 24000;
          const newLength = Math.floor(input.length / ratio);
          const resampled = new Float32Array(newLength);
          for (let i = 0; i < newLength; i++) {
            resampled[i] = input[Math.floor(i * ratio)];
          }

          const pcm16 = new Int16Array(resampled.length);
          for (let i = 0; i < resampled.length; i++) {
            pcm16[i] = Math.max(-32768, Math.min(32767, resampled[i] * 32768));
          }
          wsRef.current!.send(pcm16.buffer);
        };

        source.connect(processor);
        processor.connect(captureCtx.destination);
      };

      ws.onmessage = (evt) => {
        // Binary = audio chunk from Nova
        if (evt.data instanceof ArrayBuffer) {
          if (!novaPlayingRef.current) {
            novaPlayingRef.current = true;
            micPausedRef.current = true;
            setVoiceState('speaking');
          }
          playRealtimeAudio(evt.data);
          return;
        }

        // Text = JSON control message
        try {
          const msg = JSON.parse(evt.data as string);

          if (msg.type === 'transcript') {
            if (msg.role === 'user') {
              transcriptBufferRef.current = '';
              setMessages(prev => [...prev, {
                id: msgId(), role: 'user', text: msg.text, timestamp: Date.now(),
              }]);
            } else if (msg.role === 'assistant') {
              transcriptBufferRef.current += msg.text;
            }
          }

          if (msg.type === 'nova_audio_done') {
            const ctx = playbackCtxRef.current;
            const remainingMs = ctx
              ? Math.max(0, (nextPlayTimeRef.current - ctx.currentTime) * 1000)
              : 0;
            setTimeout(() => {
              novaPlayingRef.current = false;
              if (!micPausedRef.current || !micPaused) {
                micPausedRef.current = false;
              }
              setVoiceState('listening');
            }, remainingMs + 300);
          }

          if (msg.type === 'response_done') {
            if (transcriptBufferRef.current) {
              setMessages(prev => [...prev, {
                id: msgId(), role: 'assistant', text: transcriptBufferRef.current, timestamp: Date.now(),
              }]);
              transcriptBufferRef.current = '';
            }
            setTimeout(() => {
              novaPlayingRef.current = false;
              if (!micPaused) micPausedRef.current = false;
              setVoiceState('listening');
            }, 500);
          }

          if (msg.type === 'user_speech_started') {
            novaPlayingRef.current = false;
            micPausedRef.current = false;
            cancelPlayback();
            setVoiceState('listening');
          }

          if (msg.type === 'error') {
            console.error('[Nova Voice] Server error:', msg.message);
          }
        } catch {
          // Ignore parse errors
        }
      };

      ws.onerror = () => {
        console.error('[Nova Voice] WebSocket error');
        stopRealtimeAudio();
      };

      ws.onclose = () => {
        stopRealtimeAudio();
      };
    } catch (err) {
      console.error('[Nova Voice] Failed to start:', err);
      stopRealtimeAudio();
    }
  }, [currentPage, micPaused, playRealtimeAudio, cancelPlayback, stopRealtimeAudio]);

  const toggleVoice = () => {
    if (voiceActive) {
      stopRealtimeAudio();
    } else {
      startVoice();
    }
  };

  const toggleMicPause = () => {
    const next = !micPaused;
    setMicPaused(next);
    micPausedRef.current = next;
  };

  // Auto-start voice when widget opens, cleanup on close
  useEffect(() => {
    if (isOpen && !voiceActive) {
      const t = setTimeout(() => startVoice(), 500);
      return () => clearTimeout(t);
    }
    if (!isOpen && voiceActive) {
      stopRealtimeAudio();
    }
  }, [isOpen, voiceActive, stopRealtimeAudio]);

  // Cleanup on unmount
  useEffect(() => {
    return () => { stopRealtimeAudio(); };
  }, [stopRealtimeAudio]);

  // ============================================
  // SEDE SWITCHING (CEO)
  // ============================================

  const switchSede = (tenantId: number) => {
    localStorage.setItem('X-Tenant-ID', tenantId.toString());
    setCurrentSede(tenantId);
    setConsolidatedMode(false);
    setSedeDropdownOpen(false);
    loadNovaContext(tenantId);
  };

  const viewAllSedes = () => {
    setConsolidatedMode(true);
    setCurrentSede(null);
    setSedeDropdownOpen(false);
    loadConsolidated();
  };

  // ============================================
  // ACTION ROUTING
  // ============================================

  const handleCheckAction = (action?: string) => {
    if (!action) return;
    const route = ACTION_ROUTES[action];
    if (route) {
      navigate(route);
      setIsOpen(false);
    }
  };

  const applySuggestion = async (suggestion: { text: string; action?: string }, index: number) => {
    try {
      await api.post('/admin/nova/apply-suggestion', {
        type: 'faq',
        question: suggestion.text,
        answer: suggestion.action || suggestion.text,
      });
      setInsights(prev => {
        if (!prev?.suggestions) return prev;
        const updated = [...prev.suggestions];
        updated[index] = { ...updated[index], applied: true };
        return { ...prev, suggestions: updated };
      });
    } catch {
      // Silent fail
    }
  };

  // ============================================
  // RENDER HELPERS
  // ============================================

  const currentSedeName = sedes.find(s => s.id === currentSede)?.name || 'Todas las sedes';
  const alertCount = novaCtx?.checks?.filter(c => c.type === 'alert').length || 0;

  const renderScoreCircle = (score: number, size: 'lg' | 'sm' = 'lg') => {
    const dim = size === 'lg' ? 'w-24 h-24' : 'w-10 h-10';
    const textSize = size === 'lg' ? 'text-3xl' : 'text-sm';
    return (
      <div className={`${dim} rounded-full border-4 ${score >= 80 ? 'border-emerald-400' : score >= 50 ? 'border-amber-400' : 'border-red-400'} flex items-center justify-center`}>
        <span className={`${textSize} font-bold ${getScoreColor(score)}`}>{score}</span>
      </div>
    );
  };

  // ============================================
  // TAB: CHAT
  // ============================================

  const renderChatTab = () => (
    <div className="flex flex-col h-full">
      {/* Quick checks */}
      {novaCtx?.checks && novaCtx.checks.length > 0 && (
        <div className="p-3 space-y-2 border-b border-white/5 flex-shrink-0">
          {novaCtx.checks.slice(0, 2).map((check) => (
            <button
              key={check.id}
              onClick={() => handleCheckAction(check.action)}
              className={`w-full text-left p-2.5 rounded-lg border text-sm flex items-center justify-between transition-colors hover:brightness-125 ${CHECK_STYLES[check.type] || CHECK_STYLES.info}`}
            >
              <span>{check.message}</span>
              <ArrowRight className="w-4 h-4 flex-shrink-0 ml-2 opacity-60" />
            </button>
          ))}
        </div>
      )}

      {/* Onboarding card */}
      {onboarding && onboarding.completed < onboarding.total && (
        <div className="p-3 border-b border-white/5 flex-shrink-0">
          <div className="bg-violet-500/10 border border-violet-500/20 rounded-lg p-3">
            <div className="flex items-center gap-2 mb-2">
              <Sparkles className="w-4 h-4 text-violet-400" />
              <span className="text-sm font-medium text-violet-300">Configurar sede nueva</span>
            </div>
            <div className="w-full bg-white/10 rounded-full h-2 mb-3">
              <div
                className="bg-violet-500 h-2 rounded-full transition-all"
                style={{ width: `${(onboarding.completed / onboarding.total) * 100}%` }}
              />
            </div>
            <p className="text-xs text-slate-400 mb-2">{onboarding.completed}/{onboarding.total} completados</p>
            <div className="space-y-1.5">
              {onboarding.items.map((item, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  {item.completed ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  ) : (
                    <Circle className="w-3.5 h-3.5 text-slate-500" />
                  )}
                  <span className={item.completed ? 'text-slate-400 line-through' : 'text-slate-300'}>{item.label}</span>
                </div>
              ))}
            </div>
            <button
              onClick={() => sendMessage('Continuar configuracion')}
              className="mt-3 w-full text-xs bg-violet-600 hover:bg-violet-500 text-white py-1.5 rounded-md transition-colors flex items-center justify-center gap-1"
            >
              Continuar configuracion <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-3">
        {messages.length === 0 && novaCtx?.greeting && (
          <div className="bg-white/5 border border-white/5 rounded-lg p-3 text-sm text-slate-200">
            {novaCtx.greeting}
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[80%] rounded-lg p-2.5 text-sm whitespace-pre-wrap ${
                msg.role === 'user'
                  ? 'bg-violet-600 text-white rounded-br-sm'
                  : 'bg-white/5 border border-white/5 text-slate-200 rounded-bl-sm'
              }`}
            >
              {msg.text}
            </div>
          </div>
        ))}
        {isThinking && (
          <div className="flex justify-start">
            <div className="bg-white/5 border border-white/5 rounded-lg p-2.5 text-sm text-slate-400 animate-pulse rounded-bl-sm">
              Nova pensando...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Voice state indicator */}
      {voiceActive && voiceState !== 'idle' && (
        <div className="px-3 py-2 border-t border-white/5 flex items-center justify-between flex-shrink-0">
          {voiceState === 'listening' && (
            <>
              <div className="flex items-center gap-2 text-violet-300 text-xs">
                <span className="flex gap-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                </span>
                Escuchando...
              </div>
              <button onClick={toggleMicPause} className="text-xs text-slate-400 hover:text-white flex items-center gap-1">
                <Pause className="w-3 h-3" /> Pausar
              </button>
            </>
          )}
          {voiceState === 'processing' && (
            <div className="flex items-center gap-2 text-amber-300 text-xs">
              <span className="animate-spin w-3 h-3 border border-amber-300 border-t-transparent rounded-full" />
              Procesando...
            </div>
          )}
          {voiceState === 'speaking' && (
            <>
              <div className="flex items-center gap-2 text-cyan-300 text-xs">
                <Volume2 className="w-3.5 h-3.5" /> Nova hablando...
              </div>
              <button onClick={cancelPlayback} className="text-xs text-slate-400 hover:text-white flex items-center gap-1">
                <SkipForward className="w-3 h-3" /> Cortar
              </button>
            </>
          )}
        </div>
      )}

      {/* Input bar */}
      <div className="p-3 border-t border-white/5 flex items-center gap-2 flex-shrink-0">
        <button
          onClick={toggleVoice}
          className={`w-9 h-9 rounded-full flex items-center justify-center transition-colors flex-shrink-0 ${
            voiceActive
              ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
              : 'bg-white/5 text-slate-400 hover:bg-white/10 hover:text-white'
          }`}
          title={voiceActive ? 'Detener voz' : 'Activar voz'}
        >
          {voiceActive ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
        </button>
        <input
          type="text"
          value={inputText}
          onChange={(e) => setInputText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Preguntale a Nova..."
          className="flex-1 bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20"
        />
        <button
          onClick={() => sendMessage(inputText)}
          disabled={!inputText.trim() || isThinking}
          className="w-9 h-9 rounded-full bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:hover:bg-violet-600 flex items-center justify-center transition-colors flex-shrink-0"
        >
          <Send className="w-4 h-4 text-white" />
        </button>
      </div>
    </div>
  );

  // ============================================
  // TAB: SALUD
  // ============================================

  const renderSaludTab = () => {
    // Consolidated view for CEO
    if (consolidatedMode && consolidated) {
      return (
        <div className="h-full overflow-y-auto p-4 space-y-5">
          {/* Consolidated score */}
          <div className="flex flex-col items-center gap-2">
            <p className="text-xs text-slate-500 uppercase tracking-wider">Score Consolidado</p>
            {renderScoreCircle(consolidated.score)}
          </div>

          {/* Per-sede scores */}
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Por Sede</p>
            <div className="space-y-2">
              {consolidated.sedes.map((s) => (
                <div key={s.name} className="flex items-center gap-3">
                  <span className="text-sm text-slate-300 w-32 truncate">{s.name}</span>
                  <div className="flex-1 bg-white/5 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${getScoreBarColor(s.score)}`}
                      style={{ width: `${s.score}%` }}
                    />
                  </div>
                  <span className={`text-sm font-medium w-8 text-right ${getScoreColor(s.score)}`}>{s.score}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Global alerts */}
          {consolidated.alerts.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Alertas Globales</p>
              <div className="space-y-2">
                {consolidated.alerts.map((a, i) => (
                  <div key={i} className={`p-2 rounded-lg border text-xs ${CHECK_STYLES[a.type] || CHECK_STYLES.info}`}>
                    <span className="font-medium">{a.sede}:</span> {a.message}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Global stats */}
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'Turnos hoy', value: consolidated.stats.appointments_today },
              { label: 'Pacientes totales', value: consolidated.stats.total_patients },
              { label: 'Pagos pendientes', value: consolidated.stats.pending_payments },
              { label: 'Cancel. hoy', value: consolidated.stats.cancellations_today },
            ].map((s) => (
              <div key={s.label} className="bg-white/5 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-white">{s.value}</p>
                <p className="text-xs text-slate-400">{s.label}</p>
              </div>
            ))}
          </div>
        </div>
      );
    }

    if (!novaCtx) {
      return (
        <div className="h-full flex items-center justify-center">
          <span className="text-sm text-slate-500 animate-pulse">Cargando...</span>
        </div>
      );
    }

    return (
      <div className="h-full overflow-y-auto p-4 space-y-5">
        {/* Score circle */}
        <div className="flex flex-col items-center gap-2">
          {renderScoreCircle(novaCtx.score)}
          <p className="text-sm text-slate-400">{novaCtx.score_label || getScoreLabel(novaCtx.score)}</p>
        </div>

        {/* Completed items */}
        {novaCtx.completed && novaCtx.completed.length > 0 && (
          <div>
            <div className="space-y-1.5">
              {novaCtx.completed.map((item, i) => (
                <div key={i} className="flex items-center gap-2 text-sm">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                  <span className="text-slate-300">{item.label}</span>
                  {item.detail && <span className="text-slate-500 text-xs ml-auto">{item.detail}</span>}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pending items */}
        {novaCtx.pending && novaCtx.pending.length > 0 && (
          <div className="space-y-2">
            {novaCtx.pending.map((item, i) => (
              <button
                key={i}
                onClick={() => handleCheckAction(item.action)}
                className="w-full text-left p-2.5 bg-white/5 border border-white/5 rounded-lg text-sm text-slate-300 hover:bg-white/10 transition-colors flex items-center justify-between"
              >
                <span>{item.label}</span>
                {item.action && <ArrowRight className="w-4 h-4 text-slate-500" />}
              </button>
            ))}
          </div>
        )}

        {/* Stats grid */}
        {novaCtx.stats && (
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: 'Turnos hoy', value: novaCtx.stats.appointments_today },
              { label: 'Pacientes totales', value: novaCtx.stats.total_patients },
              { label: 'Pagos pendientes', value: novaCtx.stats.pending_payments },
              { label: 'Cancel. hoy', value: novaCtx.stats.cancellations_today },
            ].map((s) => (
              <div key={s.label} className="bg-white/5 rounded-lg p-3 text-center">
                <p className="text-xl font-bold text-white">{s.value}</p>
                <p className="text-xs text-slate-400">{s.label}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  // ============================================
  // TAB: INSIGHTS
  // ============================================

  const renderInsightsTab = () => {
    if (!insights || !insights.has_data) {
      return (
        <div className="h-full flex flex-col items-center justify-center text-center p-6">
          <BarChart3 className="w-10 h-10 text-slate-600 mb-3" />
          <p className="text-sm font-medium text-slate-400">Sin datos de hoy</p>
          <p className="text-xs text-slate-500 mt-1 max-w-[240px]">
            Nova analiza las interacciones automaticamente cada 12 horas. Los insights aparecen aca cuando haya actividad.
          </p>
        </div>
      );
    }

    return (
      <div className="h-full overflow-y-auto p-4 space-y-4">
        {/* Summary */}
        {insights.summary && (
          <div className="bg-white/5 border border-white/5 rounded-lg p-3">
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-1.5">Resumen del dia</p>
            <p className="text-sm text-slate-200">{insights.summary}</p>
            {insights.stats_line && (
              <p className="text-xs text-slate-400 mt-2">{insights.stats_line}</p>
            )}
          </div>
        )}

        {/* Frequent topics */}
        {insights.frequent_topics && insights.frequent_topics.length > 0 && (
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Temas Frecuentes</p>
            <div className="space-y-1.5">
              {insights.frequent_topics.map((t, i) => (
                <div key={i} className="flex items-center justify-between bg-white/5 rounded-lg px-3 py-2">
                  <span className="text-sm text-slate-300">{t.topic}</span>
                  <span className="text-xs text-slate-500 font-medium">{t.count}x</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Problems */}
        {insights.problems && insights.problems.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <AlertCircle className="w-3.5 h-3.5 text-amber-400" />
              <p className="text-xs text-amber-400 uppercase tracking-wider">Problemas Detectados</p>
            </div>
            <div className="space-y-2">
              {insights.problems.map((p, i) => (
                <div key={i} className="bg-amber-500/5 border border-amber-500/10 rounded-lg p-3 text-sm text-amber-200">
                  {p}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Suggestions */}
        {insights.suggestions && insights.suggestions.length > 0 && (
          <div>
            <div className="flex items-center gap-1.5 mb-2">
              <Lightbulb className="w-3.5 h-3.5 text-cyan-400" />
              <p className="text-xs text-cyan-400 uppercase tracking-wider">Sugerencias</p>
            </div>
            <div className="space-y-2">
              {insights.suggestions.map((s, i) => (
                <div key={i} className="bg-cyan-500/5 border border-cyan-500/10 rounded-lg p-3">
                  <p className="text-sm text-cyan-200">{s.text}</p>
                  {!s.applied ? (
                    <button
                      onClick={() => applySuggestion(s, i)}
                      className="mt-2 text-xs bg-cyan-600 hover:bg-cyan-500 text-white px-3 py-1 rounded transition-colors"
                    >
                      Aplicar sugerencia
                    </button>
                  ) : (
                    <span className="mt-2 inline-block text-xs text-emerald-400">Aplicada</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Cross-sede (CEO consolidated) */}
        {consolidatedMode && insights.cross_sede && (
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Comparativa entre Sedes</p>
            <div className="space-y-2">
              {insights.cross_sede.comparisons.map((c, i) => (
                <div key={i} className="bg-white/5 border border-white/5 rounded-lg p-3 text-sm text-slate-300">
                  {c}
                </div>
              ))}
            </div>
            {insights.cross_sede.ranking.length > 0 && (
              <div className="mt-3 space-y-1.5">
                {insights.cross_sede.ranking.map((r, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="text-xs text-slate-500 w-4">{i + 1}.</span>
                    <span className="text-sm text-slate-300 flex-1">{r.sede}</span>
                    <span className={`text-sm font-medium ${getScoreColor(r.score)}`}>{r.score}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // ============================================
  // VISIBILITY CHECK
  // ============================================

  if (HIDDEN_PATHS.some(p => location.pathname.startsWith(p))) return null;

  // ============================================
  // MAIN RENDER
  // ============================================

  const tabs: { key: TabKey; label: string; icon: React.ReactNode }[] = [
    { key: 'chat', label: 'Chat', icon: <MessageSquare className="w-3.5 h-3.5" /> },
    { key: 'salud', label: 'Salud', icon: <Heart className="w-3.5 h-3.5" /> },
    { key: 'insights', label: 'Insights', icon: <BarChart3 className="w-3.5 h-3.5" /> },
  ];

  return (
    <>
      {/* Toast notification */}
      {toastVisible && (
        <div className="fixed bottom-24 left-6 z-[9999] max-w-sm animate-in slide-in-from-left">
          <div className="bg-[#1a1a2e] border border-violet-500/20 rounded-lg shadow-xl p-4 flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-violet-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm text-white">Nova: {toastMessage}</p>
              <button
                onClick={() => { setToastVisible(false); setIsOpen(true); setActiveTab('chat'); }}
                className="text-xs text-violet-400 hover:text-violet-300 mt-1"
              >
                Ver detalles
              </button>
            </div>
            <button onClick={() => setToastVisible(false)} className="text-slate-500 hover:text-white">
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}

      {/* Floating button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className={`fixed bottom-6 right-6 z-[9998] w-14 h-14 rounded-full bg-gradient-to-br from-violet-600 to-indigo-600 shadow-lg shadow-violet-500/25 flex items-center justify-center text-white hover:scale-105 active:scale-95 transition-transform ${
            showPulse ? 'animate-pulse' : ''
          }`}
          style={{ bottom: 'max(1.5rem, env(safe-area-inset-bottom))' }}
        >
          <Sparkles className="w-6 h-6" />
          {alertCount > 0 && (
            <span className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-500 text-white text-[10px] font-bold flex items-center justify-center">
              {alertCount > 9 ? '9+' : alertCount}
            </span>
          )}
        </button>
      )}

      {/* Panel */}
      {isOpen && (
        <>
        <div className="lg:hidden fixed inset-0 bg-black/60 z-[9997] backdrop-blur-sm" onClick={() => setIsOpen(false)} />
        <div className="fixed inset-0 lg:inset-auto lg:bottom-6 lg:right-6 z-[9998] lg:w-[420px] lg:h-[560px] bg-[#0f0f17] lg:border lg:border-violet-500/20 lg:rounded-2xl shadow-2xl shadow-black/50 flex flex-col overflow-hidden" style={{ maxHeight: '-webkit-fill-available' }}>
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-white/5 flex-shrink-0">
            <div className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-violet-400" />
              <span className="text-sm font-semibold text-white">Nova</span>
            </div>

            {/* Sede selector (CEO only) */}
            {isCeo && sedes.length > 0 && (
              <div className="relative" ref={sedeDropdownRef}>
                <button
                  onClick={() => setSedeDropdownOpen(!sedeDropdownOpen)}
                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-white bg-white/5 px-2 py-1 rounded-md transition-colors"
                >
                  <Building2 className="w-3 h-3" />
                  <span className="max-w-[100px] truncate">{consolidatedMode ? 'Todas' : currentSedeName}</span>
                  <ChevronDown className="w-3 h-3" />
                </button>
                {sedeDropdownOpen && (
                  <div className="absolute top-full mt-1 left-0 w-56 bg-[#1a1a2e] border border-white/10 rounded-lg shadow-xl py-1 z-50">
                    {sedes.map((s) => (
                      <button
                        key={s.id}
                        onClick={() => switchSede(s.id)}
                        className="w-full text-left px-3 py-2 text-xs hover:bg-white/5 flex items-center justify-between transition-colors"
                      >
                        <div className="flex items-center gap-2">
                          {currentSede === s.id && !consolidatedMode && (
                            <span className="w-1.5 h-1.5 rounded-full bg-violet-400" />
                          )}
                          <span className={`${currentSede === s.id && !consolidatedMode ? 'text-white' : 'text-slate-400'}`}>
                            {s.name}
                          </span>
                        </div>
                        {s.score != null && (
                          <span className={`text-xs ${getScoreColor(s.score)}`}>{s.score}/100</span>
                        )}
                      </button>
                    ))}
                    <div className="border-t border-white/5 mt-1 pt-1">
                      <button
                        onClick={viewAllSedes}
                        className="w-full text-left px-3 py-2 text-xs text-violet-400 hover:bg-white/5 flex items-center gap-2 transition-colors"
                      >
                        <BarChart3 className="w-3 h-3" /> Ver todas las sedes
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            <div className="flex items-center gap-2">
              {/* Score badge */}
              {novaCtx && (
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full bg-white/5 ${getScoreColor(novaCtx.score)}`}>
                  {novaCtx.score}
                </span>
              )}
              <button
                onClick={() => setIsOpen(false)}
                className="text-slate-500 hover:text-white transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-white/5 flex-shrink-0">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex-1 py-2.5 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
                  activeTab === tab.key
                    ? 'text-violet-400 border-b-2 border-violet-400'
                    : 'text-slate-500 hover:text-slate-300'
                }`}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>

          {/* Tab content */}
          <div className="flex-1 min-h-0">
            {activeTab === 'chat' && renderChatTab()}
            {activeTab === 'salud' && renderSaludTab()}
            {activeTab === 'insights' && renderInsightsTab()}
          </div>
        </div>
        </>
      )}
    </>
  );
};
