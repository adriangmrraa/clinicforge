# SPEC: Nova Dental Assistant — Voice Pipeline (Referencia Tecnica)

**Fecha**: 2026-03-26
**Proyecto**: ClinicForge
**Tipo**: Referencia tecnica para implementacion

---

## 1. OVERVIEW

Pipeline de voz bidireccional usando OpenAI Realtime API. El browser captura audio del mic, lo envia por WebSocket al orchestrator, que lo reenvía a OpenAI. Las respuestas vuelven por el mismo camino.

```
[Mic 48kHz] → [Resample 24kHz] → [PCM16] → [WS Browser→Server] → [Base64] → [OpenAI Realtime]
                                                                                      │
[Speaker 24kHz] ← [Float32] ← [PCM16] ← [WS Server→Browser] ← [Base64 decode] ←────┘
```

---

## 2. FORMATOS DE AUDIO

| Punto | Formato | Sample Rate |
|-------|---------|-------------|
| Mic (browser nativo) | Float32 | 48000 Hz (o 44100) |
| Envio al WS | PCM16 (Int16Array) | 24000 Hz |
| OpenAI Realtime input | PCM16 base64 | 24000 Hz |
| OpenAI Realtime output | PCM16 base64 | 24000 Hz |
| Recepcion del WS | PCM16 (ArrayBuffer) | 24000 Hz |
| Playback (browser) | Float32 | 24000 Hz |

---

## 3. CAPTURA DE AUDIO (Browser → Server)

### Paso 1: Pedir permiso de mic

```typescript
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
```

### Paso 2: AudioContext a sample rate NATIVO

```typescript
// IMPORTANTE: NO forzar sampleRate en el constructor
// Usar el sample rate nativo del dispositivo (48000 o 44100)
const captureCtx = new AudioContext();
const nativeSampleRate = captureCtx.sampleRate; // 48000 tipicamente
```

### Paso 3: ScriptProcessor para captura

```typescript
const source = captureCtx.createMediaStreamSource(stream);
const processor = captureCtx.createScriptProcessor(4096, 1, 1);

processor.onaudioprocess = (e) => {
    // GATE 1: Mic pausado manualmente
    if (micPausedRef.current) return;
    // GATE 2: Nova esta hablando (echo prevention)
    if (novaPlayingRef.current) return;
    // GATE 3: WS cerrado
    if (ws.readyState !== WebSocket.OPEN) return;

    const input = e.inputBuffer.getChannelData(0); // Float32 [-1, 1]

    // Resample: nativo (48kHz) → 24kHz
    const ratio = nativeSampleRate / 24000;
    const newLength = Math.floor(input.length / ratio);
    const resampled = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
        resampled[i] = input[Math.floor(i * ratio)];
    }

    // Float32 → PCM16
    const pcm16 = new Int16Array(resampled.length);
    for (let i = 0; i < resampled.length; i++) {
        pcm16[i] = Math.max(-32768, Math.min(32767, resampled[i] * 32768));
    }

    ws.send(pcm16.buffer); // Raw ArrayBuffer
};

source.connect(processor);
processor.connect(captureCtx.destination);
```

### Errores comunes (de Platform AI)

| Error | Causa | Fix |
|-------|-------|-----|
| Nova no escucha | AudioContext forzado a 16kHz | Usar sample rate nativo + resample a 24kHz |
| Audio distorsionado | Resample incorrecto | `ratio = native / 24000`, NO al reves |
| Mic no se pausa | Solo `track.enabled` toggle | Usar ref check en `onaudioprocess` |

---

## 4. PLAYBACK DE AUDIO (Server → Browser)

### Cola secuencial con nextPlayTime

```typescript
const playbackCtxRef = useRef<AudioContext | null>(null);
const nextPlayTimeRef = useRef(0);

const playRealtimeAudio = (arrayBuffer: ArrayBuffer) => {
    // Crear AudioContext fresco si es necesario
    if (!playbackCtxRef.current || playbackCtxRef.current.state === 'closed') {
        playbackCtxRef.current = new AudioContext({ sampleRate: 24000 });
        nextPlayTimeRef.current = 0;
    }

    const ctx = playbackCtxRef.current;

    // PCM16 → Float32
    const pcm16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / 32768;
    }

    // Crear buffer y programar
    const buffer = ctx.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);
    const src = ctx.createBufferSource();
    src.buffer = buffer;
    src.connect(ctx.destination);

    // CLAVE: Cola secuencial — cada chunk empieza donde termino el anterior
    const now = ctx.currentTime;
    const startTime = Math.max(now, nextPlayTimeRef.current);
    src.start(startTime);
    nextPlayTimeRef.current = startTime + buffer.duration;
};
```

### Errores comunes (de Platform AI)

| Error | Causa | Fix |
|-------|-------|-----|
| Voces superpuestas | Chunks played simultaneamente | `nextPlayTimeRef` para cola secuencial |
| Audio cortado | AudioContext cerrado prematuramente | Solo cerrar en `cancelPlayback()` |
| Silencio entre chunks | Gap en scheduling | `Math.max(now, nextPlayTime)` sin padding extra |

---

## 5. ECHO PREVENTION (3 CAPAS)

### El problema

Nova habla → audio sale por parlantes → mic lo capta → OpenAI lo procesa como input del usuario → Nova responde a su propio audio → LOOP INFINITO.

### Solucion: 3 capas de proteccion

#### Capa 1: Auto-mute al recibir audio

```typescript
ws.onmessage = (evt) => {
    if (evt.data instanceof ArrayBuffer) {
        // Nova empezo a hablar → silenciar mic
        if (!novaPlayingRef.current) {
            novaPlayingRef.current = true;
            micPausedRef.current = true;
        }
        playRealtimeAudio(evt.data);
    }
};
```

#### Capa 2: Auto-unmute cuando Nova termina

El server envia `nova_audio_done` cuando OpenAI emite `response.audio.done`:

```typescript
if (msg.type === 'nova_audio_done') {
    // Esperar que el ultimo chunk termine de reproducirse
    const ctx = playbackCtxRef.current;
    const remainingMs = ctx
        ? Math.max(0, (nextPlayTimeRef.current - ctx.currentTime) * 1000)
        : 0;

    setTimeout(() => {
        novaPlayingRef.current = false;
        if (!micPaused) { // No pisar mute manual
            micPausedRef.current = false;
        }
    }, remainingMs + 300); // 300ms buffer de seguridad
}
```

#### Capa 3: Safety net en response_done

```typescript
if (msg.type === 'response_done') {
    // ... guardar transcript ...

    // Unmute despues de un delay corto
    setTimeout(() => {
        novaPlayingRef.current = false;
        if (!micPaused) micPausedRef.current = false;
    }, 500);
}
```

### Refs necesarias

```typescript
const micPausedRef = useRef(false);      // Mute manual (boton)
const novaPlayingRef = useRef(false);    // Auto-mute (echo prevention)
```

### Doble-check en onaudioprocess

```typescript
processor.onaudioprocess = (e) => {
    if (micPausedRef.current || novaPlayingRef.current) return;
    // ... resto del procesamiento ...
};
```

---

## 6. BARGE-IN (Usuario interrumpe a Nova)

### Server-side: forward evento de VAD

```python
# En openai_to_client():
elif etype == "input_audio_buffer.speech_started":
    await websocket.send_text(json.dumps({"type": "user_speech_started"}))
```

### Client-side: cancelar playback + unmute

```typescript
if (msg.type === 'user_speech_started') {
    novaPlayingRef.current = false;
    micPausedRef.current = false;
    cancelPlayback();
}

const cancelPlayback = () => {
    if (playbackCtxRef.current?.state !== 'closed') {
        try { playbackCtxRef.current.close(); } catch(e) {}
    }
    playbackCtxRef.current = null;
    nextPlayTimeRef.current = 0;
    novaPlayingRef.current = false;
    if (!micPaused) micPausedRef.current = false;
};
```

---

## 7. VAD (Voice Activity Detection) — TUNING

### Configuracion recomendada para dental

```python
"turn_detection": {
    "type": "server_vad",
    "threshold": 0.5,           # Sensibilidad moderada
    "prefix_padding_ms": 800,   # Capturar contexto antes del habla
    "silence_duration_ms": 5000  # 5 segundos de silencio antes de cortar
}
```

### Por que estos valores

| Parametro | Valor | Razon |
|-----------|-------|-------|
| `threshold` | 0.5 | 0.8 era demasiado sensible — ruido ambiente de consultorio (turbina, succion) triggeaba falsos positivos |
| `prefix_padding_ms` | 800 | Los profesionales empiezan a hablar mientras terminan un procedimiento — necesitan mas contexto previo |
| `silence_duration_ms` | 5000 | Dentistas hacen pausas largas mientras trabajan — 3000ms cortaba prematuramente |

### Para la secretaria (sesiones cortas, respuestas rapidas)

Se podria usar un perfil diferente:
```python
# Perfil "secretary" (opcional, future)
"silence_duration_ms": 3000  # Secretaria no necesita pausas tan largas
```

---

## 8. SERVER-SIDE EVENTS (OpenAI → Client)

### Eventos que el server DEBE forward

```python
async for message in openai_ws:
    event = json.loads(message)
    etype = event.get("type", "")

    # Audio chunks → forward como binary
    if etype == "response.audio.delta":
        audio_b64 = event.get("delta", "")
        if audio_b64:
            await websocket.send_bytes(base64.b64decode(audio_b64))

    # Nova termino de enviar audio → signal para unmute mic
    elif etype == "response.audio.done":
        await websocket.send_text(json.dumps({"type": "nova_audio_done"}))

    # Transcript de Nova (streaming)
    elif etype == "response.audio_transcript.delta":
        text = event.get("delta", "")
        if text:
            await websocket.send_text(json.dumps({
                "type": "transcript", "role": "assistant", "text": text
            }))

    # Transcript del usuario (despues de STT)
    elif etype == "conversation.item.input_audio_transcription.completed":
        text = event.get("transcript", "")
        if text:
            await websocket.send_text(json.dumps({
                "type": "transcript", "role": "user", "text": text
            }))

    # Usuario empezo a hablar (VAD) → signal para barge-in
    elif etype == "input_audio_buffer.speech_started":
        await websocket.send_text(json.dumps({"type": "user_speech_started"}))

    # Respuesta completa → signal para flush transcript
    elif etype == "response.done":
        await websocket.send_text(json.dumps({"type": "response_done"}))

    # Tool call → ejecutar + forward resultado
    elif etype == "response.function_call_arguments.done":
        # ... tool execution logic ...
```

---

## 9. CLEANUP (al cerrar widget o desconectar)

```typescript
const stopRealtimeAudio = () => {
    // 1. Cerrar WS
    if (wsRef.current) { wsRef.current.close(); wsRef.current = null; }
    // 2. Parar mic
    if (streamRef.current) { streamRef.current.getTracks().forEach(t => t.stop()); streamRef.current = null; }
    // 3. Desconectar processor
    if (processorRef.current) { processorRef.current.disconnect(); processorRef.current = null; }
    // 4. Cerrar capture AudioContext
    if (captureCtxRef.current) { captureCtxRef.current.close(); captureCtxRef.current = null; }
    // 5. Cancelar playback
    cancelPlayback();
    // 6. Reset refs
    novaPlayingRef.current = false;
    micPausedRef.current = false;
};
```

---

## 10. NGINX CONFIG (WebSocket proxy)

```nginx
# En el server block del frontend:

# Nova Realtime WebSocket
location /api/public/nova/ {
    proxy_pass http://orchestrator:8000/public/nova/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;
}
```

---

## 11. CHECKLIST PRE-DEPLOY

- [ ] `OPENAI_API_KEY` configurada en env (ya deberia existir)
- [ ] `websockets` package instalado en orchestrator (`pip install websockets`)
- [ ] nginx.conf actualizado con proxy WS
- [ ] Widget no aparece en rutas publicas (`/login`, `/anamnesis`, `/demo`)
- [ ] Test: hablar → Nova responde → sin eco
- [ ] Test: pausar 5 segundos → Nova NO corta
- [ ] Test: interrumpir a Nova → audio se cancela limpio
- [ ] Test: tool call → resultado correcto (buscar paciente, ver agenda)
- [ ] Test: profesional no puede usar tools de CEO
- [ ] Max session 5 minutos → WS se cierra limpio

---

## 12. LECCIONES DE PLATFORM AI SOLUTIONS

Estos bugs ya fueron resueltos en Platform AI. Evitarlos desde el inicio:

| Bug | Causa | Prevencion |
|-----|-------|-----------|
| STT no funciona | AudioContext forzado a 16kHz | SIEMPRE usar sample rate nativo + resample |
| Audio se superpone | Sin cola de playback | `nextPlayTimeRef` obligatorio |
| Loop de eco | Mic capta audio de Nova | 3 capas de echo prevention |
| Corte prematuro | `silence_duration_ms: 1000` | Usar 5000ms para profesionales |
| Nova habla frances | System prompt vacio | Forzar idioma en primera linea del prompt |
| WS 403 | Middleware bloquea `/admin/` WS | Usar `/public/` path para WS |
| Mic no se pausa | Solo `track.enabled` | Check ref en `onaudioprocess` |
| Session expired | Redis TTL muy corto | 360s TTL + renovacion |
