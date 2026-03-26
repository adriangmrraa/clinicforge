# SPEC: Nova Dental Assistant — Frontend Widget (Fase 2)

**Fecha**: 2026-03-26
**Proyecto**: ClinicForge
**Dependencia**: Fase 1 (backend)

---

## 1. COMPONENTE: NovaWidget.tsx

### Crear: `frontend_react/src/components/NovaWidget.tsx`

Widget flotante presente en toda la plataforma (excepto login, anamnesis publica).

---

## 2. ESTRUCTURA UI

### 2.1 Boton Flotante

```
┌─────────────────────────────────────────────────────┐
│                                        [Nova ✨]    │  ← bottom-right, z-9998
│                                         badge: 2    │  ← rojo si hay alertas
│                                                     │
│           (cualquier pagina de ClinicForge)          │
└─────────────────────────────────────────────────────┘
```

- Posicion: `fixed bottom-6 right-6`
- Tamano: 56px (w-14 h-14)
- Gradiente: `from-violet-600 to-indigo-600`
- Pulse durante 10 segundos al cargar
- Badge rojo con numero de alertas criticas

### 2.2 Panel Abierto

```
┌──────────────────────────────────────┐
│ Nova ✨  [Sede Salta ▼]  Score: 78 X│
├────────┬─────────┬───────────────────┤
│  Chat  │  Salud  │     Insights      │
├────────┴─────────┴───────────────────┤
│                                      │
│  [Tab content area]                  │
│                                      │
│  420px width x 560px height          │
│                                      │
├──────────────────────────────────────┤
│  🎤 [Preguntale a Nova...] [Send]   │  ← solo en tab Chat
└──────────────────────────────────────┘
```

- Tamano: `w-80 lg:w-[420px] h-[560px]`
- Theme: dark `bg-[#0f0f17]`
- Border: `border-violet-500/20`
- 3 tabs: Chat, Salud, Insights

### 2.3 Sede Selector (solo CEO)

En el header del widget, entre el titulo y el score, se muestra un dropdown exclusivo para CEOs:

```
┌──────────────────────────────────────┐
│ Nova ✨  [Sede Salta ▼]  Score: 78 X│
├────────┬─────────┬───────────────────┤
```

Dropdown muestra todas las sedes con mini-score:
```
┌──────────────────────────────┐
│ ● Sede Salta         78/100 │  ← current (violet dot)
│   Sede Córdoba       65/100 │
│   Sede Neuquén       82/100 │
│ ─────────────────────────── │
│   📊 Ver todas las sedes    │  ← consolidated view
└──────────────────────────────┘
```

- Solo visible si `user.role === 'ceo'`
- Cambiar sede llama a `switch_sede` tool via API y recarga el contexto
- "Ver todas las sedes" cambia a modo consolidado (todas las sedes)
- Staff (professional/secretary): no se muestra dropdown, solo el nombre de la clinica

Implementacion:
```typescript
const [sedes, setSedes] = useState<Sede[]>([]);
const [currentSede, setCurrentSede] = useState<number | null>(null);

useEffect(() => {
    if (user?.role === 'ceo') {
        fetchApi('/admin/tenants').then(data => setSedes(data));
    }
}, []);

const switchSede = async (tenantId: number) => {
    localStorage.setItem('X-Tenant-ID', tenantId.toString());
    setCurrentSede(tenantId);
    // Reload nova context for new sede
    await loadNovaContext(tenantId);
};
```

---

## 3. TAB: CHAT

### 3.1 Quick Checks (top)

Muestra los 2 checks mas urgentes como cards clicables:

```
┌──────────────────────────────────────┐
│ 🔴 3 turnos sin confirmar hoy    →  │
│ ⚡ Hueco de 3h manana en agenda  →  │
└──────────────────────────────────────┘
```

Colores por tipo:
- `alert`: `bg-red-500/10 border-red-500/20 text-red-300`
- `warning`: `bg-amber-500/10 border-amber-500/20 text-amber-300`
- `suggestion`: `bg-cyan-500/10 border-cyan-500/20 text-cyan-300`
- `info`: `bg-blue-500/10 border-blue-500/20 text-blue-300`

Click → navegar a la pagina correspondiente.

### 3.2 Mensajes

Historial de chat con burbujas:
- **Usuario**: `bg-violet-600 text-white` (derecha)
- **Nova**: `bg-white/5 border-white/5 text-slate-200` (izquierda)
- Loading: "Nova pensando..." con `animate-pulse`

### 3.3 Input (texto + voz)

```
┌──────────────────────────────────────┐
│ 🎤  [Preguntale a Nova...]  [Send]  │
└──────────────────────────────────────┘
```

- Boton mic (toggle): Inicia/detiene captura de voz
- Input text: Enviar con Enter
- Send button: `bg-violet-600`

### 3.4 Indicador de Voz

Cuando el mic esta activo:

```
┌──────────────────────────────────────┐
│    ●●● Escuchando...   [⏸ Pausar]  │
│    🔊 Nova hablando... [⏭ Cortar]  │
└──────────────────────────────────────┘
```

Estados: `idle` → `listening` → `processing` → `speaking` → `listening`

### 3.5 Onboarding Wizard

Cuando una sede nueva tiene onboarding incompleto, Nova muestra proactivamente una guia de configuracion como card en el tab Chat:

```
┌──────────────────────────────────────┐
│ 🚀 Configurar sede nueva            │
│                                      │
│ ████████░░░░░░░░  4/8 completados   │
│                                      │
│ ✅ Profesionales (3 activos)         │
│ ✅ Horarios configurados             │
│ ✅ Tratamientos (8 tipos)            │
│ ✅ WhatsApp conectado                │
│ 🔲 Google Calendar                   │
│ 🔲 FAQs (0 de 3 minimo)            │
│ 🔲 Datos bancarios                   │
│ 🔲 Precio de consulta               │
│                                      │
│ [Continuar configuracion →]          │
└──────────────────────────────────────┘
```

- Se muestra como card en el tab Chat cuando el onboarding esta incompleto
- Click "Continuar" → Nova inicia conversacion guiada para el siguiente paso
- Cada paso se puede completar via chat o redirigir a la pagina de configuracion correspondiente
- Cuando los 8 pasos estan completos, la card desaparece y muestra mensaje de celebracion

Implementacion:
```typescript
const [onboardingStatus, setOnboardingStatus] = useState(null);

useEffect(() => {
    fetchApi('/admin/nova/onboarding-status').then(setOnboardingStatus);
}, [currentSede]);
```

---

## 4. TAB: SALUD

### 4.1 Score Central

```
┌──────────────────────────────────────┐
│              78                       │
│     ████████████████░░░░░             │
│     Tu clinica va bien!               │
└──────────────────────────────────────┘
```

Color del score:
- >= 80: `text-emerald-400` (verde)
- 50-79: `text-amber-400` (amarillo)
- < 50: `text-red-400` (rojo)

### 4.2 Completado

```
✅ 3 profesionales activos
✅ Horarios configurados
✅ WhatsApp conectado
✅ 234 pacientes registrados
```

### 4.3 Pendiente

Cards clicables ordenadas por peso:

```
🔴 Google Calendar no conectado           [Conectar →]
💡 Solo tenes 1 FAQ configurada           [Agregar →]
ℹ️  Sin turnos en los ultimos 7 dias      [Ver agenda →]
```

### 4.4 Stats Grid

```
┌──────────┬──────────┐
│    12    │    234   │
│ Turnos   │ Pacientes│
│  hoy     │  totales │
├──────────┼──────────┤
│     3    │    1     │
│ Pagos    │ Cancel.  │
│pendientes│  hoy     │
└──────────┴──────────┘
```

### 4.5 Vista Consolidada Multi-Sede (CEO)

Cuando el CEO tiene seleccionado "Ver todas las sedes", el tab Salud cambia a vista consolidada:

```
┌──────────────────────────────────────┐
│         SCORE CONSOLIDADO            │
│              75                       │
│     ████████████████░░░░░             │
│                                      │
│ POR SEDE:                            │
│ ┌─ Sede Salta          78 ████████ ─┐│
│ ├─ Sede Neuquén         82 █████████─┤│
│ └─ Sede Córdoba         65 ██████── ─┘│
│                                      │
│ ALERTAS GLOBALES:                    │
│ 🔴 Sede Córdoba: 5 turnos sin       │
│    confirmar                         │
│ 🟡 Sede Salta: Google Calendar      │
│    no conectado                      │
│                                      │
│ STATS GLOBALES:                      │
│ ┌──────────┬──────────┐             │
│ │    34    │    580   │             │
│ │ Turnos   │ Pacientes│             │
│ │  hoy     │  totales │             │
│ ├──────────┼──────────┤             │
│ │     8    │    2     │             │
│ │ Pagos    │ Cancel.  │             │
│ │pendientes│  hoy     │             │
│ └──────────┴──────────┘             │
└──────────────────────────────────────┘
```

---

## 5. TAB: INSIGHTS

### 5.1 Sin Datos

```
┌──────────────────────────────────────┐
│          📊 Sin datos de hoy         │
│                                      │
│   Nova analiza las interacciones     │
│   automaticamente cada 12 horas.     │
│   Los insights aparecen aca cuando   │
│   haya actividad.                    │
└──────────────────────────────────────┘
```

### 5.2 Con Datos

```
┌──────────────────────────────────────┐
│ 📊 Resumen del dia                   │
│ "Semana activa con 45 turnos. 3      │
│  cancelaciones. Los pacientes        │
│  consultan mucho por precios."       │
│ 45 turnos · Satisfaccion: 7/10      │
├──────────────────────────────────────┤
│ TEMAS FRECUENTES                     │
│ ┌─ Consultas de precio        8x ─┐ │
│ ├─ Disponibilidad urgente     5x ─┤ │
│ └─ Cambios de turno           4x ─┘ │
├──────────────────────────────────────┤
│ ⚠️ PROBLEMAS DETECTADOS             │
│ ┌ "3 pacientes preguntaron por     │ │
│ │  blanqueamiento y el agente      │ │
│ │  no supo el precio"              │ │
│ └──────────────────────────────────┘ │
├──────────────────────────────────────┤
│ 💡 SUGERENCIAS                       │
│ ┌ Agregar precios de blanqueamiento │ │
│ │ "Actualizar FAQ con rango de     │ │
│ │  precios ($X - $Y)"             │ │
│ │         [Aplicar sugerencia]     │ │
│ └──────────────────────────────────┘ │
└──────────────────────────────────────┘
```

### 5.3 Aplicar Sugerencia

Click → llama a `actualizar_faq` tool via chat → muestra "Aplicada ✓"

### 5.4 Vista Consolidada Multi-Sede (CEO)

Cuando el CEO visualiza en modo consolidado:
- Seccion de comparacion cross-sede
- "Sede Córdoba tuvo 60% mas cancelaciones que Salta esta semana"
- Desglose por sede de temas frecuentes

---

## 6. TOAST NOTIFICATION

Al entrar a la plataforma, si hay alertas criticas:

```
┌──────────────────────────────────────┐
│ ✨ Nova: 3 turnos sin confirmar     │
│         para hoy.                    │
│         [Ver detalles]          [X]  │
└──────────────────────────────────────┘
```

- Posicion: `fixed bottom-24 left-6`
- Auto-dismiss: 8 segundos
- 1 vez por sesion (`sessionStorage`)
- Click "Ver detalles" → abre widget

---

## 7. VOICE PIPELINE (Client-Side)

### 7.1 Audio Capture

```typescript
// 1. Pedir permiso de mic
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

// 2. AudioContext a sample rate nativo (48kHz)
const audioCtx = new AudioContext();
const source = audioCtx.createMediaStreamSource(stream);
const processor = audioCtx.createScriptProcessor(4096, 1, 1);

// 3. En onaudioprocess: resamplear 48kHz → 24kHz
processor.onaudioprocess = (e) => {
    if (micPausedRef.current || novaPlayingRef.current) return; // Echo prevention

    const input = e.inputBuffer.getChannelData(0);
    const ratio = nativeSampleRate / 24000;
    const resampled = new Float32Array(Math.floor(input.length / ratio));
    for (let i = 0; i < resampled.length; i++) {
        resampled[i] = input[Math.floor(i * ratio)];
    }

    // Convertir a PCM16
    const pcm16 = new Int16Array(resampled.length);
    for (let i = 0; i < resampled.length; i++) {
        pcm16[i] = Math.max(-32768, Math.min(32767, resampled[i] * 32768));
    }
    ws.send(pcm16.buffer);
};
```

### 7.2 Audio Playback (cola secuencial)

```typescript
const playRealtimeAudio = (arrayBuffer: ArrayBuffer) => {
    if (!playbackCtx || playbackCtx.state === 'closed') {
        playbackCtx = new AudioContext({ sampleRate: 24000 });
        nextPlayTime = 0;
    }

    // PCM16 → Float32
    const pcm16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(pcm16.length);
    for (let i = 0; i < pcm16.length; i++) float32[i] = pcm16[i] / 32768;

    // Encolar secuencialmente
    const buffer = playbackCtx.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);
    const src = playbackCtx.createBufferSource();
    src.buffer = buffer;
    src.connect(playbackCtx.destination);

    const startTime = Math.max(playbackCtx.currentTime, nextPlayTime);
    src.start(startTime);
    nextPlayTime = startTime + buffer.duration;
};
```

### 7.3 Echo Prevention (3 capas)

```
CAPA 1: Auto-mute al recibir audio de Nova
─────────────────────────────────────────
ws.onmessage = (evt) => {
    if (evt.data instanceof ArrayBuffer) {
        novaPlayingRef.current = true;   // Flag: Nova habla
        micPausedRef.current = true;     // Silenciar mic
        playRealtimeAudio(evt.data);
    }
};

CAPA 2: Auto-unmute cuando Nova termina
─────────────────────────────────────────
if (msg.type === 'nova_audio_done') {
    // Esperar que termine el ultimo chunk
    const remaining = (nextPlayTime - playbackCtx.currentTime) * 1000;
    setTimeout(() => {
        novaPlayingRef.current = false;
        micPausedRef.current = false;    // Reactivar mic
    }, remaining + 300);
}

CAPA 3: Barge-in (usuario interrumpe)
─────────────────────────────────────────
if (msg.type === 'user_speech_started') {
    novaPlayingRef.current = false;
    micPausedRef.current = false;
    cancelPlayback();  // Cerrar AudioContext + resetear cola
}
```

### 7.4 Barge-In

```typescript
const cancelPlayback = () => {
    if (playbackCtx && playbackCtx.state !== 'closed') {
        playbackCtx.close();
    }
    playbackCtx = null;
    nextPlayTime = 0;
    novaPlayingRef.current = false;
    micPausedRef.current = false;
};
```

---

## 8. ACTION ROUTING

Mapeo de acciones de checks a rutas de ClinicForge:

```typescript
const ACTION_ROUTES: Record<string, string> = {
    'confirmar_turnos': '/agenda',
    'ver_agenda': '/agenda',
    'conectar_gcal': '/configuracion',
    'agregar_faqs': '/configuracion',
    'ver_pacientes': '/pacientes',
    'ver_tratamientos': '/tratamientos',
    'facturacion_pendiente': '/agenda',  // (appointment billing inline)
    'ver_chats': '/chats',
    'ver_analytics': '/analytics/professionals',
    'configurar_horarios': '/configuracion',
    'ver_marketing': '/marketing',
};
```

---

## 9. INTEGRACION EN LAYOUT

### Modificar: `frontend_react/src/components/Layout.tsx`

```tsx
import { NovaWidget } from './NovaWidget';

// Dentro del Layout return:
<div className="flex min-h-screen">
    <Sidebar />
    <main className="flex-1 overflow-y-auto">
        <Outlet />
    </main>
    <NovaWidget />  {/* <-- Agregar aca */}
</div>
```

### Exclusiones

No mostrar el widget en:
- `/login`
- `/anamnesis/:tenantId/:token` (pagina publica)
- `/demo` (landing page)

```typescript
const location = useLocation();
const hiddenPaths = ['/login', '/anamnesis', '/demo', '/privacy', '/terms'];
if (hiddenPaths.some(p => location.pathname.startsWith(p))) return null;
```

---

## 10. PAGE DETECTION

```typescript
const currentPage = (() => {
    const path = location.pathname;
    if (path === '/') return 'dashboard';
    if (path.includes('sedes')) return 'sedes';
    if (path.includes('agenda')) return 'agenda';
    if (path.includes('paciente')) return 'pacientes';
    if (path.includes('chat')) return 'chats';
    if (path.includes('tratamiento')) return 'tratamientos';
    if (path.includes('analytics')) return 'analytics';
    if (path.includes('config')) return 'configuracion';
    if (path.includes('marketing')) return 'marketing';
    if (path.includes('leads')) return 'leads';
    return 'dashboard';
})();
```

---

## 11. CONTEXTO ENRIQUECIDO POR PAGINA

Cuando se abre Nova, incluir contexto segun la pagina:

| Pagina | Contexto extra |
|--------|---------------|
| `sedes` | Lista de sedes con scores (CEO) |
| `dashboard` | Consolidado multi-sede si es CEO |
| `agenda` | Turnos del dia, proximo paciente, huecos |
| `pacientes/:id` | Ficha del paciente seleccionado (nombre, ultima visita, obra social) |
| `chats` | Conversacion activa (si hay una abierta) |
| `analytics` | Metricas de la semana |
| `configuracion` | Estado de integraciones (Google, WhatsApp, Meta) |

Para `/pacientes/:id`: extraer `patient_id` de la URL y enviarlo en el POST `/admin/nova/session`.

---

## 12. DEPENDENCIAS NPM

Todas ya existentes en el proyecto:
- `lucide-react` (iconos)
- `react-router-dom` (useLocation, useNavigate)
- No se necesitan dependencias nuevas

---

## 13. VERIFICACION

1. Widget flotante visible en `/`, `/agenda`, `/pacientes`, `/chats`, `/configuracion`
2. Widget NO visible en `/login`, `/anamnesis/*`, `/demo`
3. Click → panel se abre con animacion
4. Tab Chat → greeting contextual correcto
5. Tab Salud → score + checks + stats
6. Tab Insights → "Sin datos" o analisis del dia
7. Toast al entrar si hay alertas
8. Mic → audio se envia → Nova responde por voz
9. Echo prevention: no hay loop de audio
10. Barge-in: interrumpir Nova funciona limpio
11. Tool call → UI refleja resultado (badge, card, navegacion)
12. Responsive: funciona en 320px+ mobile
13. Sede selector visible solo para CEO, dropdown funciona correctamente
14. Cambio de sede recarga contexto de Nova
15. "Ver todas las sedes" muestra vista consolidada en Salud e Insights
16. Onboarding wizard aparece en Chat cuando sede tiene configuracion incompleta
17. Completar los 8 pasos de onboarding oculta la card y muestra celebracion
