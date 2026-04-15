import { useState, useRef, useEffect, useCallback } from 'react';
import { Mic, Square, Trash2, Send, X, Activity } from 'lucide-react';
import api from '../../api/axios';

// ============================================
// TYPES
// ============================================

type RecorderState = 'idle' | 'recording' | 'preview' | 'sending';

export interface UploadedAttachment {
  type: string;
  url: string;
  file_name: string;
  size?: number;
}

interface VoiceRecorderProps {
  disabled?: boolean;
  onAudioReady: (attachment: UploadedAttachment) => Promise<void>;
  onTranscriptionFallback: (text: string) => void;
  onNotify?: (title: string, message: string, type?: 'info' | 'warning' | 'error') => void;
  onStateChange?: (active: boolean) => void;
  tenantId: number;
}

// ============================================
// HELPERS
// ============================================

function detectMimeType(): string {
  if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) return 'audio/webm;codecs=opus';
  if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) return 'audio/ogg;codecs=opus';
  return 'audio/mp4';
}

function mimeToExtension(mimeType: string): string {
  if (mimeType.startsWith('audio/webm')) return 'webm';
  if (mimeType.startsWith('audio/ogg')) return 'ogg';
  return 'mp4';
}

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60).toString().padStart(2, '0');
  const s = (seconds % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

// ============================================
// COMPONENT
// ============================================

export default function VoiceRecorder({
  disabled = false,
  onAudioReady,
  onTranscriptionFallback,
  onNotify,
  onStateChange,
  tenantId,
}: VoiceRecorderProps) {
  // Guard: browser support check (SSR-safe)
  const isSupported =
    typeof navigator !== 'undefined' &&
    !!navigator.mediaDevices?.getUserMedia &&
    typeof window !== 'undefined' &&
    !!window.MediaRecorder;

  const [recorderState, setRecorderState] = useState<RecorderState>('idle');
  const [elapsed, setElapsed] = useState(0);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [uploadedAttachment, setUploadedAttachment] = useState<UploadedAttachment | null>(null);
  const [transcriptionText, setTranscriptionText] = useState('');
  const [uploadReady, setUploadReady] = useState(false);
  const [uploadError, setUploadError] = useState(false);

  // Waveform bars state (5 bars)
  const [barHeights, setBarHeights] = useState<number[]>([4, 4, 4, 4, 4]);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const blobRef = useRef<Blob | null>(null);
  const mimeTypeRef = useRef<string>('audio/webm;codecs=opus');

  // Stable refs for callbacks — avoids stale closures inside recorder event
  // handlers (onstop, auto-stop timeout) without triggering re-renders.
  // Prop callbacks:
  const onStateChangeRef = useRef(onStateChange);
  const onNotifyRef = useRef(onNotify);
  useEffect(() => { onStateChangeRef.current = onStateChange; }, [onStateChange]);
  useEffect(() => { onNotifyRef.current = onNotify; }, [onNotify]);
  // Internal callbacks (declared here, populated below via useEffect updaters):
  const stopRecordingRef = useRef<() => void>(() => {});
  const uploadAndTranscribeRef = useRef<(blob: Blob) => void>(() => {});

  // ============================================
  // CLEANUP on unmount
  // ============================================
  useEffect(() => {
    return () => {
      stopWaveform();
      if (timerRef.current) clearInterval(timerRef.current);
      if (autoStopRef.current) clearTimeout(autoStopRef.current);
      if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop());
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ============================================
  // WAVEFORM
  // ============================================
  const startWaveform = useCallback((stream: MediaStream) => {
    try {
      const ctx = new AudioContext();
      audioContextRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 64;
      source.connect(analyser);
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);

      const tick = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        // Pick 5 representative bins for the 5 bars
        const step = Math.floor(dataArray.length / 5);
        const heights = Array.from({ length: 5 }, (_, i) => {
          const val = dataArray[i * step] ?? 0;
          // Map 0-255 to 4-32px
          return 4 + Math.round((val / 255) * 28);
        });
        setBarHeights(heights);
        animFrameRef.current = requestAnimationFrame(tick);
      };
      animFrameRef.current = requestAnimationFrame(tick);
    } catch {
      // Waveform is cosmetic — fail silently
    }
  }, []);

  const stopWaveform = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (audioContextRef.current) {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    analyserRef.current = null;
    setBarHeights([4, 4, 4, 4, 4]);
  }, []);

  // ============================================
  // START RECORDING
  // ============================================
  const startRecording = useCallback(async () => {
    if (disabled) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const mimeType = detectMimeType();
      mimeTypeRef.current = mimeType;
      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
        blobRef.current = blob;
        const url = URL.createObjectURL(blob);
        setBlobUrl(url);
        setRecorderState('preview');
        // Start parallel upload + transcription — use ref so we always call
        // the latest version even if tenantId changed between start and stop.
        uploadAndTranscribeRef.current(blob);
      };

      recorder.start(200); // collect data every 200ms
      setElapsed(0);
      setRecorderState('recording');
      onStateChangeRef.current?.(true);
      startWaveform(stream);

      // Timer
      timerRef.current = setInterval(() => {
        setElapsed(prev => prev + 1);
      }, 1000);

      // Auto-stop at 5 minutes — use refs so closures see current callbacks.
      autoStopRef.current = setTimeout(() => {
        stopRecordingRef.current();
        onNotifyRef.current?.('Grabación detenida', 'Límite máximo de 5 minutos alcanzado.', 'info');
      }, 300_000);
    } catch (err) {
      console.error('[VoiceRecorder] getUserMedia error:', err);
      onNotifyRef.current?.('Micrófono no disponible', 'Permiso de micrófono denegado. Habilitalo desde la configuración del navegador.', 'error');
    }
  }, [disabled, startWaveform]);

  // ============================================
  // STOP RECORDING
  // ============================================
  const stopRecording = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (autoStopRef.current) { clearTimeout(autoStopRef.current); autoStopRef.current = null; }
    stopWaveform();
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
  }, [stopWaveform]);

  // ============================================
  // CANCEL RECORDING
  // ============================================
  const cancelRecording = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (autoStopRef.current) { clearTimeout(autoStopRef.current); autoStopRef.current = null; }
    stopWaveform();
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      // Discard data
      mediaRecorderRef.current.ondataavailable = null;
      mediaRecorderRef.current.onstop = null;
      mediaRecorderRef.current.stop();
    }
    chunksRef.current = [];
    setElapsed(0);
    setRecorderState('idle');
    onStateChange?.(false);
  }, [stopWaveform, onStateChange]);

  // Keep stopRecordingRef current:
  useEffect(() => { stopRecordingRef.current = stopRecording; }, [stopRecording]);

  // ============================================
  // UPLOAD + TRANSCRIBE (parallel, at preview time)
  // ============================================
  const uploadAndTranscribe = useCallback(async (blob: Blob) => {
    setUploadReady(false);
    setUploadError(false);
    setUploadedAttachment(null);
    setTranscriptionText('');

    const ext = mimeToExtension(mimeTypeRef.current);
    const file = new File([blob], `audio_${Date.now()}.${ext}`, { type: blob.type });

    const uploadPromise = (async () => {
      const formData = new FormData();
      formData.append('file', file);
      const res = await api.post(`/admin/chat/upload?tenant_id=${tenantId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      return res.data as UploadedAttachment;
    })();

    const transcribePromise = (async () => {
      try {
        const formData = new FormData();
        formData.append('file', file);
        const res = await api.post('/admin/chat/transcribe', formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
        });
        return (res.data?.text as string) ?? '';
      } catch {
        return '';
      }
    })();

    try {
      const [attachment, transcription] = await Promise.all([uploadPromise, transcribePromise]);
      setUploadedAttachment(attachment);
      setTranscriptionText(transcription);
      setUploadReady(true);
    } catch (err) {
      console.error('[VoiceRecorder] upload error:', err);
      setUploadError(true);
    }
  }, [tenantId]);

  // Keep uploadAndTranscribeRef current:
  useEffect(() => { uploadAndTranscribeRef.current = uploadAndTranscribe; }, [uploadAndTranscribe]);

  // ============================================
  // SEND AUDIO
  // ============================================
  const handleSend = useCallback(async () => {
    if (!uploadedAttachment) return;
    setRecorderState('sending');
    try {
      await onAudioReady(uploadedAttachment);
      // Reset
      if (blobUrl) URL.revokeObjectURL(blobUrl);
      setBlobUrl(null);
      blobRef.current = null;
      setUploadedAttachment(null);
      setTranscriptionText('');
      setUploadReady(false);
      setUploadError(false);
      setElapsed(0);
      setRecorderState('idle');
      onStateChange?.(false);
    } catch (err) {
      console.error('[VoiceRecorder] send error:', err);
      // Fallback: paste transcription into input
      if (transcriptionText) {
        onTranscriptionFallback(transcriptionText);
      }
      if (blobUrl) URL.revokeObjectURL(blobUrl);
      setBlobUrl(null);
      blobRef.current = null;
      setUploadedAttachment(null);
      setUploadReady(false);
      setUploadError(false);
      setElapsed(0);
      setRecorderState('idle');
      onStateChange?.(false);
    }
  }, [uploadedAttachment, onAudioReady, onTranscriptionFallback, onStateChange, transcriptionText, blobUrl]);

  // ============================================
  // DELETE PREVIEW
  // ============================================
  const handleDelete = useCallback(() => {
    if (blobUrl) URL.revokeObjectURL(blobUrl);
    setBlobUrl(null);
    blobRef.current = null;
    setUploadedAttachment(null);
    setTranscriptionText('');
    setUploadReady(false);
    setUploadError(false);
    setElapsed(0);
    setRecorderState('idle');
    onStateChange?.(false);
  }, [blobUrl, onStateChange]);

  // ============================================
  // RENDER: not supported
  // ============================================
  if (!isSupported) return null;

  // ============================================
  // RENDER: idle
  // ============================================
  if (recorderState === 'idle') {
    return (
      <button
        type="button"
        onClick={startRecording}
        disabled={disabled}
        className="p-2 text-white/30 hover:text-medical-400 hover:bg-white/[0.04] rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        title="Grabar audio"
        aria-label="Grabar mensaje de voz"
      >
        <Mic size={20} />
      </button>
    );
  }

  // ============================================
  // RENDER: recording
  // ============================================
  if (recorderState === 'recording') {
    return (
      <div className="flex items-center gap-2 flex-1 bg-white/[0.04] border border-red-500/30 rounded-lg px-3 py-1.5">
        {/* Cancel */}
        <button
          type="button"
          onClick={cancelRecording}
          className="p-1 text-white/40 hover:text-white/80 hover:bg-white/[0.06] rounded-md transition-colors flex-shrink-0"
          title="Cancelar grabación"
          aria-label="Cancelar grabación"
        >
          <X size={16} />
        </button>

        {/* Pulsing mic */}
        <span className="relative flex-shrink-0">
          <span className="absolute inset-0 rounded-full bg-red-500/30 animate-ping" />
          <Mic size={18} className="relative text-red-400" />
        </span>

        {/* Waveform bars */}
        <div className="flex items-center gap-[3px] flex-shrink-0" aria-hidden>
          {barHeights.map((h, i) => (
            <div
              key={i}
              className="w-[3px] bg-red-400/70 rounded-full transition-all duration-75"
              style={{ height: `${h}px` }}
            />
          ))}
        </div>

        {/* Timer */}
        <span className="text-xs text-white/60 font-mono flex-shrink-0 ml-1">
          {formatElapsed(elapsed)}
        </span>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Stop button */}
        <button
          type="button"
          onClick={stopRecording}
          className="p-1.5 bg-red-500 hover:bg-red-600 text-white rounded-md transition-colors flex-shrink-0"
          title="Detener grabación"
          aria-label="Detener grabación"
        >
          <Square size={14} fill="currentColor" />
        </button>
      </div>
    );
  }

  // ============================================
  // RENDER: preview
  // ============================================
  if (recorderState === 'preview') {
    const sendDisabled = !uploadReady || uploadError;
    return (
      <div className="flex items-center gap-2 flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2">
        {/* Delete */}
        <button
          type="button"
          onClick={handleDelete}
          className="p-1.5 text-white/40 hover:text-red-400 hover:bg-white/[0.06] rounded-md transition-colors flex-shrink-0"
          title="Eliminar audio"
          aria-label="Eliminar audio grabado"
        >
          <Trash2 size={16} />
        </button>

        {/* Audio player + duration */}
        {blobUrl && (
          <audio
            src={blobUrl}
            controls
            className="flex-1 h-8 min-w-0"
            style={{ colorScheme: 'dark' }}
          />
        )}
        <span className="text-xs text-white/40 font-mono flex-shrink-0">{formatElapsed(elapsed)}</span>

        {/* Upload status hint */}
        {!uploadReady && !uploadError && (
          <span className="text-xs text-white/30 flex-shrink-0 whitespace-nowrap">
            <Activity size={12} className="inline animate-spin mr-1" />
            subiendo…
          </span>
        )}
        {uploadError && (
          <span className="text-xs text-red-400 flex-shrink-0 whitespace-nowrap">
            error al subir
          </span>
        )}

        {/* Send */}
        <button
          type="button"
          onClick={handleSend}
          disabled={sendDisabled}
          className="p-1.5 bg-green-600 hover:bg-green-700 text-white rounded-md transition-colors flex-shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
          title={sendDisabled ? 'Esperando carga…' : 'Enviar audio'}
          aria-label="Enviar mensaje de voz"
        >
          <Send size={16} />
        </button>
      </div>
    );
  }

  // ============================================
  // RENDER: sending
  // ============================================
  return (
    <div className="flex items-center gap-2 flex-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-3 py-2">
      <Activity size={16} className="text-white/40 animate-spin flex-shrink-0" />
      <span className="text-sm text-white/40 flex-1">Enviando audio…</span>
    </div>
  );
}
