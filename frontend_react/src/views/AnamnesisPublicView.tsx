import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { HeartPulse, Pill, AlertTriangle, Scissors, Cigarette, Baby, Frown, Brain, Loader2, CheckCircle2, XCircle, Lock, Mic, MicOff, Volume2 } from 'lucide-react';
import api, { BACKEND_URL } from '../api/axios';

/* ── Checklist Options (dental standard) ── */
const DISEASE_OPTIONS = [
  'Diabetes', 'Hipertensión', 'Cardiopatía', 'Problemas de coagulación',
  'Hepatitis', 'HIV/SIDA', 'Osteoporosis', 'Tiroides', 'Epilepsia',
  'Asma', 'Enfermedad renal', 'Artritis reumatoidea',
];
const ALLERGY_OPTIONS = [
  'Penicilina', 'Amoxicilina', 'Latex', 'Anestesia local',
  'AINES (Ibuprofeno)', 'Aspirina', 'Metales',
];
const FEAR_OPTIONS = [
  'Agujas', 'Dolor', 'Ruido del torno', 'Asfixia/Ahogo',
  'Sangre', 'Anestesia', 'Estar en el sillón dental',
];

/* ── Nova Voice Indicator for Anamnesis ── */
type VoiceState = 'idle' | 'connecting' | 'listening' | 'processing' | 'speaking';

function NovaVoiceBar({ tenantId, token, patientName }: { tenantId: string; token: string; patientName: string }) {
  const [voiceState, setVoiceState] = useState<VoiceState>('idle');
  const wsRef = useRef<WebSocket | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const captureCtxRef = useRef<AudioContext | null>(null);
  const processorRef = useRef<ScriptProcessorNode | null>(null);
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef(0);
  const micPausedRef = useRef(false);
  const novaPlayingRef = useRef(false);

  const stopVoice = useCallback(() => {
    if (wsRef.current) { try { wsRef.current.close(); } catch {} wsRef.current = null; }
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null; }
    if (captureCtxRef.current?.state !== 'closed') { try { captureCtxRef.current?.close(); } catch {} }
    captureCtxRef.current = null;
    if (playbackCtxRef.current?.state !== 'closed') { try { playbackCtxRef.current?.close(); } catch {} }
    playbackCtxRef.current = null;
    nextPlayTimeRef.current = 0;
    micPausedRef.current = false;
    novaPlayingRef.current = false;
    setVoiceState('idle');
  }, []);

  const playAudio = useCallback((arrayBuffer: ArrayBuffer) => {
    if (!playbackCtxRef.current || playbackCtxRef.current.state === 'closed') {
      playbackCtxRef.current = new AudioContext({ sampleRate: 24000 });
      nextPlayTimeRef.current = 0;
    }
    const ctx = playbackCtxRef.current;
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

  const startVoice = useCallback(async () => {
    try {
      setVoiceState('connecting');
      // 1. Create PUBLIC session (no auth needed)
      const sessionResp = await api.post(`/public/anamnesis/${tenantId}/${token}/voice-session`);
      const sessionId = sessionResp.data.session_id;

      // 2. Get mic
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // 3. Connect WS (public endpoint)
      const wsUrl = `${BACKEND_URL.replace('http', 'ws')}/public/nova/voice?tenant_id=${tenantId}&token=${sessionId}&page=anamnesis`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setVoiceState('listening');
        // Start audio capture
        const captureCtx = new AudioContext();
        captureCtxRef.current = captureCtx;
        const source = captureCtx.createMediaStreamSource(stream);
        const processor = captureCtx.createScriptProcessor(4096, 1, 1);
        processorRef.current = processor;
        const nativeRate = captureCtx.sampleRate;

        processor.onaudioprocess = (e) => {
          if (micPausedRef.current || novaPlayingRef.current) return;
          if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;
          const input = e.inputBuffer.getChannelData(0);
          const ratio = nativeRate / 24000;
          const newLen = Math.floor(input.length / ratio);
          const resampled = new Float32Array(newLen);
          for (let i = 0; i < newLen; i++) resampled[i] = input[Math.floor(i * ratio)];
          const pcm16 = new Int16Array(resampled.length);
          for (let i = 0; i < resampled.length; i++) pcm16[i] = Math.max(-32768, Math.min(32767, resampled[i] * 32768));
          ws.send(pcm16.buffer);
        };
        source.connect(processor);
        processor.connect(captureCtx.destination);
      };

      ws.onmessage = (evt) => {
        if (evt.data instanceof ArrayBuffer || evt.data instanceof Blob) {
          if (!novaPlayingRef.current) {
            novaPlayingRef.current = true;
            micPausedRef.current = true;
            setVoiceState('speaking');
          }
          if (evt.data instanceof Blob) {
            evt.data.arrayBuffer().then(buf => playAudio(buf));
          } else {
            playAudio(evt.data);
          }
          return;
        }
        try {
          const msg = JSON.parse(evt.data);
          if (msg.type === 'nova_audio_done') {
            const ctx = playbackCtxRef.current;
            const remaining = ctx ? Math.max(0, (nextPlayTimeRef.current - ctx.currentTime) * 1000) : 0;
            setTimeout(() => {
              novaPlayingRef.current = false;
              micPausedRef.current = false;
              setVoiceState('listening');
            }, remaining + 300);
          } else if (msg.type === 'user_speech_started') {
            novaPlayingRef.current = false;
            micPausedRef.current = false;
            if (playbackCtxRef.current?.state !== 'closed') { try { playbackCtxRef.current?.close(); } catch {} }
            playbackCtxRef.current = null;
            nextPlayTimeRef.current = 0;
            setVoiceState('processing');
          } else if (msg.type === 'response_done') {
            setTimeout(() => {
              novaPlayingRef.current = false;
              micPausedRef.current = false;
              setVoiceState('listening');
            }, 500);
          }
        } catch {}
      };

      ws.onclose = () => stopVoice();
      ws.onerror = () => stopVoice();
    } catch {
      stopVoice();
    }
  }, [tenantId, patientName, playAudio, stopVoice]);

  const handleToggle = () => {
    if (voiceState === 'idle') startVoice();
    else stopVoice();
  };

  return (
    <button
      onClick={handleToggle}
      className={`w-full py-3 rounded-xl text-sm font-medium flex items-center justify-center gap-2.5 transition-all active:scale-[0.98] shadow-sm ${
        voiceState === 'idle'
          ? 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white hover:from-violet-700 hover:to-indigo-700'
          : voiceState === 'listening'
          ? 'bg-green-600 text-white'
          : voiceState === 'processing'
          ? 'bg-amber-600 text-white'
          : voiceState === 'speaking'
          ? 'bg-violet-600 text-white'
          : 'bg-gray-600 text-white'
      }`}
    >
      {voiceState === 'idle' && <><Mic size={16} /> Completar con voz</>}
      {voiceState === 'connecting' && <><Loader2 size={16} className="animate-spin" /> Conectando...</>}
      {voiceState === 'listening' && <><span className="relative flex h-3 w-3"><span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75"></span><span className="relative inline-flex rounded-full h-3 w-3 bg-white"></span></span> Escuchando...</>}
      {voiceState === 'processing' && <><Loader2 size={16} className="animate-spin" /> Procesando...</>}
      {voiceState === 'speaking' && <><Volume2 size={16} className="animate-pulse" /> Nova hablando...</>}
      {voiceState !== 'idle' && <span className="text-xs opacity-75 ml-1">(tocar para detener)</span>}
    </button>
  );
}


export default function AnamnesisPublicView() {
  const { tenantId, token } = useParams<{ tenantId: string; token: string }>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [patientName, setPatientName] = useState('');
  const [clinicName, setClinicName] = useState('');

  // DNI Lock state
  const [requiresDni, setRequiresDni] = useState(false);
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [dniInput, setDniInput] = useState('');
  const [dniError, setDniError] = useState('');
  const [verifying, setVerifying] = useState(false);

  // Form state
  const [baseDiseases, setBaseDiseases] = useState<string[]>([]);
  const [baseDiseasesOther, setBaseDiseasesOther] = useState('');
  const [medication, setMedication] = useState('');
  const [allergies, setAllergies] = useState<string[]>([]);
  const [allergiesOther, setAllergiesOther] = useState('');
  const [surgeries, setSurgeries] = useState('');
  const [isSmoker, setIsSmoker] = useState('');
  const [smokerAmount, setSmokerAmount] = useState('');
  const [pregnancy, setPregnancy] = useState('');
  const [negativeExperiences, setNegativeExperiences] = useState('');
  const [fears, setFears] = useState<string[]>([]);
  const [fearsOther, setFearsOther] = useState('');

  const prefillForm = (d: any) => {
    if (d.base_diseases) {
      const items = String(d.base_diseases).split(',').map((s: string) => s.trim());
      const known = items.filter((i: string) => DISEASE_OPTIONS.includes(i));
      const other = items.filter((i: string) => !DISEASE_OPTIONS.includes(i) && i !== 'Ninguna');
      setBaseDiseases(known);
      if (other.length) setBaseDiseasesOther(other.join(', '));
    }
    if (d.habitual_medication && d.habitual_medication !== 'Ninguna') setMedication(d.habitual_medication);
    if (d.allergies) {
      const items = String(d.allergies).split(',').map((s: string) => s.trim());
      const known = items.filter((i: string) => ALLERGY_OPTIONS.includes(i));
      const other = items.filter((i: string) => !ALLERGY_OPTIONS.includes(i) && i !== 'Ninguna');
      setAllergies(known);
      if (other.length) setAllergiesOther(other.join(', '));
    }
    if (d.previous_surgeries && d.previous_surgeries !== 'Ninguna') setSurgeries(d.previous_surgeries);
    if (d.is_smoker) setIsSmoker(d.is_smoker);
    if (d.smoker_amount) setSmokerAmount(d.smoker_amount);
    if (d.pregnancy_lactation) setPregnancy(d.pregnancy_lactation);
    if (d.negative_experiences && d.negative_experiences !== 'Ninguna') setNegativeExperiences(d.negative_experiences);
    if (d.specific_fears) {
      const items = String(d.specific_fears).split(',').map((s: string) => s.trim());
      const known = items.filter((i: string) => FEAR_OPTIONS.includes(i));
      const other = items.filter((i: string) => !FEAR_OPTIONS.includes(i) && i !== 'Ninguno');
      setFears(known);
      if (other.length) setFearsOther(other.join(', '));
    }
  };

  useEffect(() => {
    if (!tenantId || !token) return;
    (async () => {
      try {
        const resp = await api.get(`/public/anamnesis/${tenantId}/${token}`);
        setPatientName(resp.data.patient_name);
        setClinicName(resp.data.clinic_name);

        if (resp.data.requires_dni) {
          // Patient has DNI — require verification
          setRequiresDni(true);
        } else {
          // No DNI stored — open directly (and prefill if data exists)
          setIsUnlocked(true);
          prefillForm(resp.data.existing_data || {});
        }
      } catch {
        setError('Link inválido o expirado. Pedí un nuevo link al asistente por WhatsApp.');
      } finally {
        setLoading(false);
      }
    })();
  }, [tenantId, token]);

  const handleDniVerify = async () => {
    if (!dniInput.trim()) { setDniError('Ingresá tu DNI'); return; }
    setVerifying(true);
    setDniError('');
    try {
      const resp = await api.post(`/public/anamnesis/${tenantId}/${token}/verify`, { dni: dniInput.trim() });
      if (resp.data.verified) {
        setIsUnlocked(true);
        prefillForm(resp.data.existing_data || {});
      }
    } catch (err: any) {
      setDniError(err?.response?.data?.detail || 'DNI incorrecto. Verificá e intentá de nuevo.');
    } finally {
      setVerifying(false);
    }
  };

  const toggleCheck = (list: string[], setList: (v: string[]) => void, value: string) => {
    setList(list.includes(value) ? list.filter(i => i !== value) : [...list, value]);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tenantId || !token) return;
    setSubmitting(true);
    try {
      await api.post(`/public/anamnesis/${tenantId}/${token}`, {
        base_diseases: baseDiseases.length ? baseDiseases : ['Ninguna'],
        base_diseases_other: baseDiseasesOther || null,
        habitual_medication: medication || 'Ninguna',
        allergies: allergies.length ? allergies : ['Ninguna'],
        allergies_other: allergiesOther || null,
        previous_surgeries: surgeries || 'Ninguna',
        is_smoker: isSmoker || 'no',
        smoker_amount: smokerAmount || null,
        pregnancy_lactation: pregnancy || 'no_aplica',
        negative_experiences: negativeExperiences || 'Ninguna',
        specific_fears: fears.length ? fears : ['Ninguno'],
        specific_fears_other: fearsOther || null,
      });
      setSubmitted(true);
    } catch {
      setError('Error al guardar. Intentá de nuevo.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center">
        <Loader2 className="animate-spin text-blue-600" size={40} />
      </div>
    );
  }

  if (error && !patientName) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-red-50 to-white flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md text-center space-y-4">
          <XCircle className="mx-auto text-red-500" size={48} />
          <h1 className="text-xl font-bold text-gray-800">Link inválido</h1>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    );
  }

  if (submitted) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-green-50 to-white flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-md text-center space-y-4">
          <CheckCircle2 className="mx-auto text-green-500" size={48} />
          <h1 className="text-xl font-bold text-gray-800">Ficha médica guardada</h1>
          <p className="text-gray-600">Gracias {patientName}! Tu ficha fue guardada correctamente.</p>
          <p className="text-gray-500 text-sm">Podés avisarle al asistente por WhatsApp que ya completaste el formulario.</p>
        </div>
      </div>
    );
  }

  // DNI Lock Screen
  if (requiresDni && !isUnlocked) {
    return (
      <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white flex items-center justify-center p-6">
        <div className="bg-white rounded-2xl shadow-lg p-8 max-w-sm w-full space-y-6 text-center">
          <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto">
            <Lock size={28} className="text-blue-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-800">Ficha Médica Protegida</h1>
            <p className="text-sm text-gray-500 mt-1">{clinicName}</p>
            <p className="text-sm text-gray-600 mt-3">Hola {patientName}! Para acceder a tu ficha médica, ingresá tu DNI.</p>
          </div>
          <div className="space-y-3">
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              placeholder="Ingresá tu DNI (solo números)"
              className="w-full px-4 py-3 border border-gray-200 rounded-xl text-center text-lg font-mono tracking-wider focus:ring-2 focus:ring-blue-500 outline-none"
              value={dniInput}
              onChange={e => setDniInput(e.target.value.replace(/[^0-9]/g, ''))}
              onKeyDown={e => e.key === 'Enter' && handleDniVerify()}
              maxLength={10}
              autoFocus
            />
            {dniError && <p className="text-red-500 text-sm">{dniError}</p>}
            <button
              onClick={handleDniVerify}
              disabled={verifying || !dniInput.trim()}
              className="w-full py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {verifying ? <Loader2 size={18} className="animate-spin" /> : <Lock size={18} />}
              {verifying ? 'Verificando...' : 'Acceder a mi ficha'}
            </button>
          </div>
          <p className="text-xs text-gray-400">Tu información médica está protegida. Solo vos podés acceder con tu DNI.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-blue-50 to-white">
      {/* Header + Nova Voice (sticky) */}
      <div className="bg-white shadow-sm sticky top-0 z-10">
        <div className="max-w-lg mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-bold text-blue-900 flex items-center gap-2">
                <HeartPulse size={20} className="text-blue-600" />
                Ficha Médica
              </h1>
              <p className="text-sm text-gray-500">{clinicName} — {patientName}</p>
            </div>
          </div>
          <div className="mt-2">
            <NovaVoiceBar tenantId={tenantId || ''} token={token || ''} patientName={patientName} />
          </div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="max-w-lg mx-auto px-4 py-6 space-y-6">
        {error && (
          <div className="bg-red-50 text-red-600 p-3 rounded-xl text-sm">{error}</div>
        )}

        {/* Enfermedades de base */}
        <Section icon={<HeartPulse size={18} className="text-red-500" />} title="Enfermedades de base" subtitle="Seleccioná todas las que apliquen">
          <CheckboxGroup options={DISEASE_OPTIONS} selected={baseDiseases} toggle={(v) => toggleCheck(baseDiseases, setBaseDiseases, v)} />
          <input type="text" placeholder="Otra (especificar)" className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none" value={baseDiseasesOther} onChange={e => setBaseDiseasesOther(e.target.value)} />
        </Section>

        {/* Medicación habitual */}
        <Section icon={<Pill size={18} className="text-orange-500" />} title="Medicación habitual">
          <textarea placeholder="Ej: Metformina 850mg, Enalapril 10mg..." className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none min-h-[60px]" value={medication} onChange={e => setMedication(e.target.value)} />
        </Section>

        {/* Alergias */}
        <Section icon={<AlertTriangle size={18} className="text-red-600" />} title="Alergias" subtitle="Seleccioná todas las que apliquen">
          <CheckboxGroup options={ALLERGY_OPTIONS} selected={allergies} toggle={(v) => toggleCheck(allergies, setAllergies, v)} />
          <input type="text" placeholder="Otra alergia (especificar)" className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none" value={allergiesOther} onChange={e => setAllergiesOther(e.target.value)} />
        </Section>

        {/* Cirugías previas */}
        <Section icon={<Scissors size={18} className="text-gray-600" />} title="Cirugías previas">
          <textarea placeholder="Ej: Apendicectomía 2019, cesárea 2021..." className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none min-h-[60px]" value={surgeries} onChange={e => setSurgeries(e.target.value)} />
        </Section>

        {/* Fumador */}
        <Section icon={<Cigarette size={18} className="text-amber-600" />} title="Tabaquismo">
          <div className="flex gap-3">
            <RadioBtn label="No fumo" value="no" selected={isSmoker} onSelect={setIsSmoker} />
            <RadioBtn label="Sí, fumo" value="si" selected={isSmoker} onSelect={setIsSmoker} />
            <RadioBtn label="Ex fumador" value="ex" selected={isSmoker} onSelect={setIsSmoker} />
          </div>
          {(isSmoker === 'si' || isSmoker === 'ex') && (
            <input type="text" placeholder="Cuántos por día? (aprox)" className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none mt-2" value={smokerAmount} onChange={e => setSmokerAmount(e.target.value)} />
          )}
        </Section>

        {/* Embarazo */}
        <Section icon={<Baby size={18} className="text-pink-500" />} title="Embarazo / Lactancia">
          <div className="flex gap-3 flex-wrap">
            <RadioBtn label="No aplica" value="no_aplica" selected={pregnancy} onSelect={setPregnancy} />
            <RadioBtn label="Embarazada" value="embarazada" selected={pregnancy} onSelect={setPregnancy} />
            <RadioBtn label="En lactancia" value="lactancia" selected={pregnancy} onSelect={setPregnancy} />
          </div>
        </Section>

        {/* Experiencias negativas */}
        <Section icon={<Frown size={18} className="text-gray-500" />} title="Experiencias negativas en odontología">
          <textarea placeholder="Contanos si tuviste alguna mala experiencia previa..." className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none min-h-[60px]" value={negativeExperiences} onChange={e => setNegativeExperiences(e.target.value)} />
        </Section>

        {/* Miedos dentales */}
        <Section icon={<Brain size={18} className="text-purple-500" />} title="Miedos dentales" subtitle="Seleccioná todos los que apliquen">
          <CheckboxGroup options={FEAR_OPTIONS} selected={fears} toggle={(v) => toggleCheck(fears, setFears, v)} />
          <input type="text" placeholder="Otro miedo (especificar)" className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-blue-500 outline-none" value={fearsOther} onChange={e => setFearsOther(e.target.value)} />
        </Section>

        {/* Submit */}
        <button type="submit" disabled={submitting}
          className="w-full py-3.5 bg-blue-600 text-white font-bold rounded-xl hover:bg-blue-700 active:bg-blue-800 transition-all shadow-lg disabled:opacity-50 flex items-center justify-center gap-2 text-base">
          {submitting ? <Loader2 className="animate-spin" size={20} /> : <CheckCircle2 size={20} />}
          {submitting ? 'Guardando...' : 'Enviar ficha médica'}
        </button>

        <p className="text-center text-xs text-gray-400 pb-4">
          Tus datos están protegidos y solo serán visibles por tu profesional de salud.
        </p>
      </form>
    </div>
  );
}

/* ── UI Components ── */
function Section({ icon, title, subtitle, children }: { icon: React.ReactNode; title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
      <div>
        <h2 className="font-semibold text-gray-800 flex items-center gap-2">{icon} {title}</h2>
        {subtitle && <p className="text-xs text-gray-400 mt-0.5 ml-7">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function CheckboxGroup({ options, selected, toggle }: { options: string[]; selected: string[]; toggle: (v: string) => void }) {
  return (
    <div className="grid grid-cols-2 gap-2">
      {options.map(opt => (
        <label key={opt} className={`flex items-center gap-2 p-2.5 rounded-xl border cursor-pointer transition-all touch-manipulation
          ${selected.includes(opt) ? 'bg-blue-50 border-blue-300 text-blue-800' : 'bg-gray-50 border-gray-200 text-gray-700 hover:bg-gray-100'}`}>
          <input type="checkbox" checked={selected.includes(opt)} onChange={() => toggle(opt)} className="w-4 h-4 rounded border-gray-300 text-blue-600" />
          <span className="text-sm">{opt}</span>
        </label>
      ))}
    </div>
  );
}

function RadioBtn({ label, value, selected, onSelect }: { label: string; value: string; selected: string; onSelect: (v: string) => void }) {
  const isActive = selected === value;
  return (
    <button type="button" onClick={() => onSelect(value)}
      className={`px-4 py-2 rounded-xl text-sm font-medium transition-all touch-manipulation border
        ${isActive ? 'bg-blue-600 text-white border-blue-600' : 'bg-gray-50 text-gray-700 border-gray-200 hover:bg-gray-100'}`}>
      {label}
    </button>
  );
}
