# Sistema de Agentes de IA — ClinicForge

Documento de referencia completo del sistema de agentes de inteligencia artificial de ClinicForge. Cubre los tres engines de conversacion, herramientas, parsing de fechas, flujo de pagos y diferencias entre engines.

**Ultima actualizacion:** 2026-04-09

---

## 1. Arquitectura General

### 1.1 Diagrama de Flujo

```
Mensaje entrante (WhatsApp / Instagram / Facebook / Chatwoot)
        │
        ▼
  buffer_task.py  ─────────────────────────────────────────────────┐
  │  • Identifica tenant_id, phone_number                         │
  │  • Carga contexto del paciente (identidad, turnos, memoria)   │
  │  • Clasifica intent (keyword-based, <1ms)                     │
  │  • RAG: busqueda semantica de FAQs via pgvector               │
  │  • Inyecta feriados, plan de tratamiento, memorias            │
  │  • Determina greeting state                                   │
  │  • Detecta canal social (is_social_channel)                   │
  │                                                                │
  │  ┌─────────────────────┐                                      │
  │  │  engine_router.py   │                                      │
  │  │  get_engine_for_    │                                      │
  │  │  tenant(tenant_id)  │                                      │
  │  └────────┬────────────┘                                      │
  │           │                                                    │
  │     ┌─────┴──────┬──────────────┐                             │
  │     ▼            ▼              ▼                              │
  │  SoloEngine  MultiAgent    (Social mode)                      │
  │  (TORA)      Engine        Solo/Multi +                       │
  │  main.py     agents/       social_preamble                    │
  │              graph.py                                          │
  │     │            │              │                              │
  │     └────────────┴──────────────┘                              │
  │                  │                                             │
  │                  ▼                                             │
  │           Respuesta al paciente                                │
  └────────────────────────────────────────────────────────────────┘
```

### 1.2 Los 3 Engines

| Engine | Modulo | Descripcion |
|--------|--------|-------------|
| **SoloEngine** (`solo`) | `orchestrator_service/main.py` | Agente monolitico LangChain original (TORA). Usa `build_system_prompt` + 14 `DENTAL_TOOLS`. Default para todos los tenants. |
| **MultiAgentEngine** (`multi`) | `orchestrator_service/agents/` | Supervisor + 6 agentes especializados con `PatientContext` compartido. Opt-in por tenant. |
| **Social Agent** | `services/social_prompt.py` + `services/social_routes.py` | No es un engine separado: es un **preamble** que se prepende al prompt cuando el canal es Instagram o Facebook. Funciona sobre Solo o Multi. |

### 1.3 Circuit Breaker y Fallback

El `EngineRouter` implementa un circuit breaker por tenant:

- **Umbral:** 3 fallos consecutivos del MultiAgentEngine dentro de una ventana de 60 segundos.
- **Accion:** Se marca `is_tripped = True` y todas las peticiones se redirigen a `SoloEngine` durante **5 minutos** (300s).
- **Recuperacion:** Despues de 5 minutos, el circuit breaker se resetea y se vuelve a intentar con el engine configurado.

```python
# Constantes del circuit breaker
CIRCUIT_THRESHOLD = 3    # fallos para disparar
CIRCUIT_WINDOW    = 60   # ventana de fallos (segundos)
CIRCUIT_RECOVERY  = 300  # tiempo de fallback (5 minutos)
```

---

## 2. Engine Router

**Archivo:** `orchestrator_service/services/engine_router.py`

### 2.1 Como decide que engine usar

1. Lee `tenants.ai_engine_mode` de la base de datos (valores: `'solo'` | `'multi'`).
2. El valor por defecto es `'solo'`.
3. Solo el CEO del tenant puede cambiar el modo desde la UI (ConfigView, tab general).
4. Antes de activar `'multi'`, se ejecuta un health check (`GET /admin/ai-engine/health`) que prueba ambos engines en paralelo.

### 2.2 Cache: in-memory 60s + Redis pubsub

```python
class EngineRouter:
    CACHE_TTL = 60  # segundos

    async def _get_mode(self, tenant_id: int) -> str:
        # 1. Busca en cache in-memory
        if tenant_id in self._cache:
            mode, expiry = self._cache[tenant_id]
            if time.time() < expiry:
                return mode
        # 2. Cache miss → consulta DB
        mode = await self._load_mode_from_db(tenant_id)
        # 3. Actualiza cache
        self._cache[tenant_id] = (mode, time.time() + self.CACHE_TTL)
        return mode
```

**Invalidacion cross-proceso:** Cuando el endpoint `PATCH /admin/settings/clinic` actualiza `ai_engine_mode`, publica en el canal Redis `engine_router_invalidate`. Todos los procesos escuchan ese canal y eliminan la entrada del cache para ese tenant.

### 2.3 Clases de datos

```python
@dataclass
class TurnContext:
    tenant_id: int
    phone_number: str
    user_message: str
    thread_id: str
    extra: dict[str, Any] = field(default_factory=dict)

@dataclass
class TurnResult:
    output: str
    agent_used: str
    duration_ms: int
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ProbeResult:
    ok: bool
    latency_ms: int
    error: Optional[str] = None
    detail: Optional[str] = None
```

---

## 3. TORA Solo Engine (Legacy)

**Archivo principal:** `orchestrator_service/main.py`

### 3.1 System Prompt Completo

La funcion `build_system_prompt()` construye dinamicamente el prompt del agente. Acepta ~40 parametros y ensambla secciones condicionales.

#### Secciones del prompt

| Seccion | Descripcion |
|---------|-------------|
| **Social Preamble** | Si `is_social_channel=True`, prepende el bloque de modo redes sociales (ver seccion 5). |
| **REGLA DE IDIOMA** | Fuerza el idioma de respuesta (es/en/fr). Default: espanol rioplatense con voseo. |
| **CONTEXTO DE ANUNCIO** | Inyecta info de Meta Ads si el lead llego por publicidad. |
| **CONTEXTO DEL PACIENTE** | Identidad, turnos previos/futuros, menores vinculados, memorias. |
| **REGLAS DE USO DEL CONTEXTO** | Reglas de como usar nombre registrado, DNI, ultimo turno, seguimiento post-tratamiento. |
| **REGLA SUPREMA DE HERRAMIENTAS** | Si una tool retorna exito, confirmar. Si retorna error, informar. NUNCA contradecir el resultado. |
| **REGLA ANTI-CONFIRMACION-FALSA** | Prohibido decir "turno confirmado" sin haber ejecutado `book_appointment` con respuesta exitosa. |
| **REGLA ANTI-MARKDOWN (WhatsApp)** | Prohibido usar `**`, `_`, `` ` ``, `#`, `[text](url)` en WhatsApp. Solo texto plano + emojis. |
| **GREETING** | Saludo diferenciado segun patient_status (ver abajo). |
| **IDENTIDAD Y TONO** | Nombre del bot, voseo rioplatense, personalidad calida, max 1-2 emojis. |
| **PROHIBICIONES** | 7 reglas estrictas: no diagnosticar, no repetir bio, no escalar innecesariamente, etc. |
| **INFORMACION DEL CONSULTORIO** | Direccion, horarios, sedes por dia (multi-sede), precio de consulta, feriados proximos. |
| **FLUJO DE IMPLANTES** | Flujo comercial de 3 pasos para leads de implantes/protesis. |
| **FLUJOS EMOCIONALES (F1-F8)** | 8 flujos especializados (ver tabla abajo). |
| **FAQs RELEVANTES** | FAQs recuperadas por RAG semantico (top-5 por cosine similarity). |
| **OBRAS SOCIALES** | Catalogo de insurance providers con coberturas y copagos. |
| **REGLAS DE DERIVACION** | Derivation rules por tratamiento/profesional. |
| **ADMISION** | Datos minimos: nombre + apellido + DNI. Prohibido pedir email, fecha nacimiento, ciudad. |
| **FLUJO DE AGENDAMIENTO (PASOS 1-10)** | Maquina de estados completa del booking (ver abajo). |
| **DATOS BANCARIOS** | CBU, alias, titular para cobro de sena. |
| **MEDIOS DE PAGO** | Metodos, financiacion, descuentos, criptomonedas. |
| **CONDICIONES ESPECIALES** | Embarazo, pediatricos, alto riesgo. |
| **POLITICA DE ATENCION Y QUEJAS** | Protocolo graduado de quejas (niveles 1-3). |
| **ANAMNESIS** | Link de ficha medica + reglas de envio automatico/manual. |
| **FAST TRACK** | Atajos para agendamiento rapido. |
| **ANTI-ALUCINACION** | NUNCA inventar disponibilidad, precios o nombres. |

#### Greeting Rules

| Estado del paciente | Saludo |
|---------------------|--------|
| `new_lead` | "Hola. Soy {bot_name}, la asistente virtual de {clinic_name}. {specialty_pitch}. En que tipo de consulta estas interesado?" |
| `patient_no_appointment` | "Hola. Soy {bot_name}... Necesitas agendar un turno o tenes alguna consulta?" |
| `patient_with_appointment` | "Hola. Soy {bot_name}... [Comentario personalizado sobre su proximo turno: fecha, hora, sede, tratamiento]" |
| Ya saludado en sesion | No repite saludo institucional. Responde directo. |

#### Flujo de Agendamiento (PASO 1-10)

| Paso | Accion |
|------|--------|
| **PASO 1** | Saludo segun tipo de paciente (GREETING). |
| **PASO 2** | Definir servicio. Validar con `list_services`. Mapear sinonimos coloquiales. |
| **PASO 2b** | Determinar para quien es el turno (si mismo / adulto tercero / menor). |
| **PASO 3** | Profesional asignado: 1 solo → informar. Varios → preguntar preferencia. Ninguno → buscar cualquiera. |
| **PASO 4** | Consultar disponibilidad con `check_availability`. Razonar fecha con 3 campos obligatorios (date_query, interpreted_date, search_mode). |
| **PASO 4b** | Reserva temporal con `confirm_slot` (soft-lock 120s). |
| **PASO 5** | Datos de admision: nombre + apellido + DNI (solo si paciente nuevo). |
| **PASO 6** | Agendar con `book_appointment`. |
| **PASO 7** | Confirmacion: presentar resultado tal cual. |
| **PASO 7b** | Sena: datos bancarios + monto (50% consulta del profesional). |
| **PASO 7c** | "Como nos conociste?" (solo para pacientes nuevos). |
| **PASO 8** | Link de ficha medica (anamnesis). |
| **PASO 9** | Instrucciones pre-turno (pacientes nuevos). |
| **PASO 10** | Seguimiento si no responde. |

#### Flujos Emocionales (F1-F8)

| Flujo | Trigger | Protocolo |
|-------|---------|-----------|
| **F1: Mala experiencia** | "no me fue bien", "me hicieron mal" | Validar → Normalizar → Posicionar profesional → CTA evaluacion |
| **F2: Urgencia/dolor** | "me duele", "urgencia", "emergencia" | Contener (sin precio ni direccion) → 1 pregunta → triage_urgency + check_availability |
| **F3: Estetico sin diagnostico** | "mejorar mi sonrisa", "quiero verme mejor" | Normalizar → Preguntar que quiere mejorar → CTA evaluacion |
| **F4: Obra social no reconocida** | OS no esta en insurance_providers | Respuesta oficial → Ofrecer particular → Mantener en flujo |
| **F5: Precio directo** | "cuanto sale", "precio", "presupuesto" | Construir valor → Precio consulta → CTA evaluacion |
| **F6: Perdida de dientes** | "perdi un diente", "no puedo masticar" | Conexion emocional → Alternativas → Posicionar especialista → CTA |
| **F7: Miedo al tratamiento** | "tengo miedo", "fobia", "no me animo" | Validar → Normalizar con prueba social → Diferencial (anestesia sin aguja) → CTA |
| **F8: Sin hueso / rechazado** | "no tengo hueso", "me rechazaron" | Validar → Alternativas sin prometer → Posicionar especialista → CTA |

#### Reglas Anti-Alucinacion

- NUNCA inventar disponibilidad. Solo `check_availability` es fuente de verdad.
- NUNCA inventar precios. Solo `list_services` / `get_service_details` / `book_appointment`.
- NUNCA inventar nombres de profesionales ni tratamientos.
- Si un tratamiento no existe en `list_services`, mostrar los disponibles.
- Si `book_appointment` falla, reintentar con `check_availability` (max 2 reintentos).

### 3.2 Tools (DENTAL_TOOLS)

Las 14 herramientas principales del agente, definidas como funciones `@tool` en `main.py`:

| Tool | Parametros | Que hace |
|------|-----------|----------|
| `list_professionals` | (ninguno) | Lista profesionales activos del tenant con especialidad, horarios y precio de consulta. |
| `list_services` | `patient_term` (opcional) | Lista tratamientos activos con nombre, duracion, precio y profesionales asignados. Mapea sinonimos coloquiales. |
| `check_availability` | `date_query` (obligatorio), `interpreted_date` (obligatorio), `search_mode` (obligatorio), `professional_name`, `treatment_name`, `time_preference`, `specific_time` | Consulta disponibilidad REAL de turnos. Devuelve 2-3 opciones concretas con sede. |
| `confirm_slot` | `date_time`, `professional_name`, `treatment_name` | Reserva temporal (soft-lock 120s) via Redis mientras se recopilan datos. |
| `book_appointment` | `date_time`, `treatment_reason`, `first_name`, `last_name`, `dni`, `birth_date`, `email`, `city`, `acquisition_source`, `duration_minutes`, `professional_name`, `patient_phone`, `is_minor`, `interpreted_date` | Registra turno en la BD. Soporta para si mismo, tercero adulto y menor. |
| `list_my_appointments` | (ninguno) | Lista turnos futuros del paciente con estado de pago y sena. |
| `cancel_appointment` | `date_query` | Cancela un turno. La sena NO se devuelve. |
| `reschedule_appointment` | `original_date`, `new_date_time` | Reprograma un turno existente. |
| `triage_urgency` | `symptom_text` | Analiza urgencia de sintomas. Clasifica: URGENTE, MODERADA, BAJA. |
| `save_patient_anamnesis` | campos de historia clinica | Guarda ficha medica del paciente desde conversacion de chat. |
| `get_patient_anamnesis` | (ninguno) | Lee datos de anamnesis completada. |
| `save_patient_email` | `email`, `patient_phone` (opcional) | Guarda email del paciente. Soporta `patient_phone` para terceros. |
| `verify_payment_receipt` | `receipt_description`, `amount_detected`, `appointment_id` (opcional) | Verifica comprobante de transferencia via vision (OpenAI). |
| `derivhumano` | contexto de la queja/emergencia | Escala a humano. Activa silencio de 24h. Envia email a clinica y profesionales. |

### 3.3 Date Parsing System

**Funcion:** `parse_date(date_query: str) -> Optional[date]`

#### 7 Capas de Prioridad

| Capa | Nombre | Ejemplos | Resultado |
|------|--------|----------|-----------|
| **1** | Atajos exactos | "hoy", "manana", "pasado manana", "today", "tomorrow" | `date.today()`, `today + 1d`, `today + 2d` |
| **2** | ASAP / sin preferencia | "lo antes posible", "cuanto antes", "urgente", "primer turno", "asap" | `today + 1d` (manana) |
| **3** | dateutil parse (fuzzy) | "30 de abril", "jueves 30 de abril", "2026-04-30", "30/04", "4 de mayo" | Fecha parseada con `dayfirst=True` |
| **4** | Expresiones con mes | "para mayo", "fines de abril", "mitad de julio", "principio de junio" | 1, 25, 15 o 3 del mes (segun modificador) |
| **5** | Dia de semana solo | "jueves", "lunes", "viernes" | Proximo dia de esa semana |
| **6** | Frases relativas | "proxima semana", "mes que viene", "semana que viene" | Lunes proximo, dia 1 del mes siguiente |
| **7** | Fallback | Cualquier texto no reconocido | `None` (nunca inventa fechas) |

#### Manejo de "manana" (ambiguedad)

La palabra "manana" puede significar:
- **Dia** (tomorrow): "manana" → `today + 1d`
- **Horario** (morning): "por la manana" → time_preference, NO fecha

Logica de desambiguacion:
```
"manana" sin contexto de morning      → tomorrow
"por la manana" sin "manana" previo   → solo time preference
"manana por la manana"                → tomorrow + morning preference
```

#### Deteccion ISO en `check_availability`

Ademas de `parse_date()`, `check_availability` tiene prioridad sobre `interpreted_date`:

```python
# PRIORIDAD: interpreted_date del LLM > parse_date del texto
if interpreted_date:
    if re.match(r"^\d{4}-\d{2}-\d{2}$", id_str):
        target_date = date.fromisoformat(id_str)  # ISO: YYYY-MM-DD
    else:
        target_date = dateutil_parse(id_str, dayfirst=True).date()
```

#### Guardia de fecha pasada

En `book_appointment`:
```python
if apt_datetime < get_now_arg():
    return "No se pueden agendar turnos para horarios que ya pasaron."
```

En `check_availability`:
```python
if target_date < today_date:
    target_date = today_date  # Auto-avanza al hoy
```

#### Cross-validation (mes mencionado vs mes resuelto)

Si `date_query` menciona un mes explicito pero la fecha resuelta cayo en otro mes, se corrige:

```python
if mentioned_month and target_date.month != mentioned_month:
    target_date = target_date.replace(month=mentioned_month)
    if target_date < today_date_check:
        target_date = target_date.replace(year=target_date.year + 1)
```

### 3.4 Payment Flow

#### Calculo de sena

La sena es el **50% del valor de consulta del profesional** que atendera al paciente.

**Cadena de prioridad para el monto:**
1. `professionals.consultation_price` (precio del profesional asignado al turno)
2. `tenants.consultation_price` (precio general del tenant)
3. `treatment_types.base_price` (ultimo recurso)

#### Datos bancarios

Se inyectan en el prompt desde la configuracion del tenant:
- `bank_alias` — Alias bancario
- `bank_cbu` — CBU completo
- `bank_holder_name` — Nombre del titular

#### Flujo de verificacion

1. Paciente envia imagen/PDF de comprobante de transferencia.
2. `buffer_task.py` detecta que el paciente tiene turno con pago pendiente.
3. Inyecta contexto "PROBABLE COMPROBANTE DE PAGO".
4. El agente llama a `verify_payment_receipt`.
5. La tool usa vision (OpenAI) para verificar:
   - **Nombre del titular:** fuzzy match + CBU/alias check.
   - **Monto:** acepta overpayment (monto >= esperado).
6. Si OK: `payment_status → paid`, `appointment.status → confirmed`.
7. Si falla: explica el problema, pide correccion. Despues de 2 intentos fallidos → `derivhumano`.

#### Estados de pago

```
pending → paid (transferencia verificada OK)
pending → partial (monto insuficiente, registra lo recibido)
```

---

## 4. Multi-Agent Engine

**Directorio:** `orchestrator_service/agents/`

### 4.1 AgentState

**Archivo:** `agents/state.py`

```python
class AgentState(TypedDict, total=False):
    # Identity
    tenant_id: int
    phone_number: str
    thread_id: str
    turn_id: str

    # Input
    user_message: str

    # Patient context (loaded once per turn)
    patient_profile: dict
    chat_history: list[dict]
    working_state: dict

    # Model config (resolved once per turn from system_config)
    # Shape: {"model": str, "api_key": str, "base_url": Optional[str], "provider": str}
    model_config: dict

    # Graph control
    active_agent: str   # supervisor | reception | booking | triage | billing | anamnesis | handoff | END
    hop_count: int
    max_hops: int

    # Output accumulator
    agent_output: str
    tools_called: list[dict]
    handoff_reason: Optional[str]

    # Tenant-configured context blocks (built once per turn)
    tenant_context: dict[str, Any]

    # Social channel context (Instagram / Facebook)
    channel: str             # "whatsapp" | "instagram" | "facebook" | "chatwoot"
    is_social_channel: bool
    social_landings: Optional[dict]
    instagram_handle: Optional[str]
    facebook_page_id: Optional[str]

    # Metadata
    start_time: float
```

### 4.2 Supervisor Routing

**Archivo:** `agents/supervisor.py`

El `SupervisorAgent` usa **8 reglas deterministicas** (evaluadas en orden) y un **fallback LLM** cuando ninguna matchea.

#### Reglas deterministicas

| # | Regla | Patron regex | Agente destino |
|---|-------|-------------|----------------|
| 1 | Human override activo | `patient_profile.human_override_until` no es null | `handoff` |
| 2 | Hops exhausted | `hop_count >= max_hops (5)` | `handoff` |
| 3 | Emergencia / triage | `sangr[ae]`, `hinchaz[oó]n`, `trauma`, `accidente`, `dolor (agud\|intens\|fuert\|insoport)`, `urgen`, `emergen` | `triage` |
| 4 | Billing | `pag[oó]`, `seña`, `transfer`, `comprobante`, `cbu`, `alias` | `billing` |
| 5 | Anamnesis | `historia m[eé]dica`, `alergi`, `medicaci[oó]n`, `ficha`, `formulari` | `anamnesis` |
| 6 | Handoff | `hablar con (alguien\|humano\|persona\|secretar\|recepcion)`, `humano`, `queja` | `handoff` |
| 7 | Booking | `turno`, `agend`, `disponibilidad`, `reserv`, `cancel`, `reprogram` | `booking` |
| 8 | Greeting | `^(hola\|buenas\|buen d[ií]a\|buenas tardes\|buenas noches\|hi\|hey)[\s!\.]*$` | `reception` |

#### Fallback LLM

Si ninguna regla deterministico matchea:
1. Lee el prompt de `agents/prompts/supervisor.md`.
2. Usa el modelo configurado del tenant (via `state["model_config"]`).
3. Envia un mensaje al LLM pidiendo clasificacion.
4. Extrae la primera palabra de la respuesta.
5. Si es un agente valido (`reception`, `booking`, `triage`, `billing`, `anamnesis`, `handoff`) → lo retorna.
6. Si falla → retorna `"reception"` (fallback seguro).

### 4.3 Specialist Agents (6)

**Archivo:** `agents/specialists.py`

Cada agente es una subclase de `BaseAgent` que wrappea un `AgentExecutor` acotado (`max_iterations=4`) con un subconjunto de `DENTAL_TOOLS`.

#### ReceptionAgent

| Campo | Valor |
|-------|-------|
| **Nombre** | `reception` |
| **Tools** | `list_professionals`, `list_services` |
| **Rol** | Primera voz del paciente. Saludo diferenciado, respuesta a preguntas generales, derivacion limpia. |
| **Comportamiento clave** | Usa `patient_profile.is_new_lead` para saludo diferenciado. NO agenda turnos, NO hace triage, NO explica coberturas. Handoff implicito (sin nombrar agentes internos). |

#### BookingAgent

| Campo | Valor |
|-------|-------|
| **Nombre** | `booking` |
| **Tools** | `check_availability`, `confirm_slot`, `book_appointment`, `list_my_appointments`, `cancel_appointment`, `reschedule_appointment`, `list_services` |
| **Rol** | Ciclo completo de turnos: busqueda, confirmacion, booking, cancelacion, reprogramacion. |
| **Comportamiento clave** | Maquina de estados: OFRECER → CONFIRMAR → BOOKEAR. Soporta terceros y menores. Consulta feriados y sedes. Fallback inteligente a siguiente dia habil. |

#### TriageAgent

| Campo | Valor |
|-------|-------|
| **Nombre** | `triage` |
| **Tools** | `triage_urgency`, `derivhumano` |
| **Rol** | Evaluacion de urgencia de sintomas. Clasificacion y derivacion. |
| **Comportamiento clave** | SIEMPRE llama a `triage_urgency`. NUNCA diagnostica ni receta. Senales de emergencia → `derivhumano` inmediato. CRITICO: nunca dice "no es nada" ni "es gravisimo". |

#### BillingAgent

| Campo | Valor |
|-------|-------|
| **Nombre** | `billing` |
| **Tools** | `verify_payment_receipt` |
| **Rol** | Precios, obras sociales, cuotas, verificacion de comprobantes de sena. |
| **Comportamiento clave** | Lee catalogos de insurance providers y formas de pago del tenant context. Verifica comprobantes con vision. NUNCA inventa precios ni ofrece descuentos no configurados. |

#### AnamnesisAgent

| Campo | Valor |
|-------|-------|
| **Nombre** | `anamnesis` |
| **Tools** | `save_patient_anamnesis`, `get_patient_anamnesis`, `save_patient_email` |
| **Rol** | Recoleccion de ficha medica: antecedentes, alergias, medicacion. |
| **Comportamiento clave** | Llama `get_patient_anamnesis` primero. Recolecta en bloques naturales (alergias → medicacion → antecedentes). Guarda incrementalmente. NUNCA interpreta datos medicos. |

#### HandoffAgent

| Campo | Valor |
|-------|-------|
| **Nombre** | `handoff` |
| **Tools** | `derivhumano` |
| **Rol** | Escalacion humana y quejas. Ultimo eslabon antes de intervencion humana. |
| **Comportamiento clave** | Protocolo graduado: Nivel 1 (empatizar + registrar) → Nivel 2 (remedio si configurado) → Nivel 3 (derivacion humana). Derivacion directa si: solicitud explicita, amenaza legal, emergencia. |

#### Registro de agentes (singletons)

```python
AGENTS: dict[str, BaseAgent] = {
    "reception": ReceptionAgent(),
    "booking":   BookingAgent(),
    "triage":    TriageAgent(),
    "billing":   BillingAgent(),
    "anamnesis": AnamnesisAgent(),
    "handoff":   HandoffAgent(),
}
```

### 4.4 Graph Execution

**Archivo:** `agents/graph.py`

#### Constantes

```python
MAX_HOPS = 5
TURN_TIMEOUT_S = 45
```

#### Flujo de `run_turn(ctx: TurnContext) -> TurnResult`

```
1. Cargar PatientContext
   └─ _load_patient_context(tenant_id, phone_number)
   └─ Retorna: profile dict + recent_turns (ultimos 20 mensajes)

2. Resolver modelo del tenant
   └─ model_resolver.resolve_tenant_model(tenant_id)
   └─ Lee system_config.OPENAI_MODEL (misma fuente que Solo)

3. Construir tenant context blocks
   └─ build_tenant_context_blocks(pool, tenant_id, ...)
   └─ Clasifica intent para inyeccion condicional

4. Armar AgentState inicial
   └─ Todos los campos del TypedDict

5. Human override check
   └─ Si patient_profile.human_override_until → retorna output vacio

6. Routing via Supervisor
   └─ _supervisor.route(state) → nombre del agente
   └─ 45s timeout global (asyncio.timeout)

7. Despacho al agente especializado
   └─ AGENTS[next_agent_name].run(state)
   └─ El agente modifica state["agent_output"]

8. Audit log (best-effort)
   └─ INSERT INTO agent_turn_log
   └─ Campos: tenant_id, phone, turn_id, agent_name, tools_called, duration_ms, model

9. Retornar TurnResult
   └─ output, agent_used, duration_ms, metadata
```

#### Health check probe()

La funcion `probe()` valida el grafo sin tocar DB ni LLM:

```python
async def probe() -> ProbeResult:
    fake_state = { "user_message": "hola", ... }
    next_agent = await _supervisor.route(fake_state)  # deterministic: → reception
    if next_agent in AGENTS:
        return ProbeResult(ok=True, ...)
```

### 4.5 Patient Context

**Servicio:** `services/patient_context.py`

#### Profile (PostgreSQL)

Carga en una sola query:
- Datos del paciente (`patients`)
- Historia medica (`medical_history`)
- Turnos futuros (`appointments` con status != cancelled)
- Ultimos 20 mensajes de chat (`chat_messages`)

#### Working State (Redis)

- Key: `patient_ctx_working:{tenant_id}:{phone}`
- TTL: 30 minutos
- Tipo: Redis hash
- Proposito: estado intermedio de la conversacion (slots ofrecidos, datos parciales)
- Fail-safe: perfil vacio en caso de error

---

## 5. Social Agent (Instagram / Facebook)

El Social Agent NO es un engine separado. Es un **preamble** que se prepende al system prompt cuando el canal es Instagram o Facebook.

**Archivos:**
- `services/social_prompt.py` — Generador del preamble
- `services/social_routes.py` — Definicion de CTA routes

### 5.1 Social Preamble (8 Reglas)

La funcion `build_social_preamble()` es una **funcion pura** (sin I/O, sin DB). Retorna un string con el bloque de instrucciones para redes sociales.

#### REGLA 1 — Booking Directo (sin WhatsApp redirect)

El agente PUEDE y DEBE agendar turnos directamente en Instagram/Facebook. **PROHIBIDO** ofrecer WhatsApp, sugerir continuar por WhatsApp, o cualquier variante de redireccion.

#### REGLA 2 — CTAs (Palabras Clave de Historias)

Cuando el lead envia una palabra clave especifica (respuesta a una historia de Instagram), el agente usa el pitch correspondiente, envia el link de la landing page y encamina a la evaluacion.

#### REGLA 3 — Otros Tratamientos

Si el lead pregunta por un tratamiento que NO esta en los CTAs, llama a `list_services`. NUNCA inventa precios ni servicios.

#### REGLA 4 — Deteccion Amigo vs Lead

La doctora tambien usa Instagram de forma personal. El agente distingue:

**Senales de AMIGO:**
- Saludo con "Lau" o "Laura" a secas (sin "Dra.")
- Tono muy informal, charla personal
- Emojis excesivos, risas, cercanía explicita
- No menciona ningun tratamiento, precio, turno ni servicio

**Senales de LEAD:**
- Pregunta por tratamientos, precios, turnos
- Describe un sintoma o problema bucal
- Usa lenguaje formal o neutro

**Override:** Cualquier palabra clave de CTA → siempre LEAD.
**En duda:** tratar como LEAD (mas seguro comercialmente).

**Respuesta a amigo:** Breve, casual, calido, en voseo. NO llama ninguna tool. NO agenda. NO activa human_override.

#### REGLA 5 — Etica Medica

Si el paciente describe un caso medico especifico por DM → NO diagnosticar. Responder con mensaje etico sobre evaluacion presencial y ofrecer turno.

#### REGLA 6 — Herramientas Prohibidas

- **NUNCA** llamar `triage_urgency` en Instagram/Facebook. El triaje NO se hace por DM.
- Si hay urgencia → `derivhumano` directo.

**Herramientas permitidas:**
`list_services`, `list_professionals`, `check_availability`, `confirm_slot`, `book_appointment`, `reschedule_appointment`, `cancel_appointment`, `list_my_appointments`, `save_patient_email`, `save_patient_anamnesis`, `get_patient_anamnesis`, `verify_payment_receipt`, `derivhumano`

#### REGLA 7 — Formato y Markdown

Chatwoot renderiza markdown en Instagram/Facebook. Se puede usar **negritas**, _cursivas_, listas con `-`, y links normales. A diferencia de WhatsApp, el markdown esta habilitado.

#### REGLA 8 — Idioma y Tono

Espanol rioplatense con voseo natural ("tenes", "queres", "agendate", "podes"). Calido, profesional, directo. **NO usar "usted".**

### 5.2 CTA Routes

**Archivo:** `services/social_routes.py`

```python
@dataclass
class CTARoute:
    group: str           # Identificador unico
    keywords: list[str]  # Keywords normalizados (sin acentos, uppercase)
    pitch_template: str  # Template del pitch con {landing_url}
    landing_url_key: str # Key en tenant.social_landings
```

| Ruta | Keywords | Pitch (resumen) | Landing |
|------|----------|-----------------|---------|
| **blanqueamiento** | BLANQUEAMIENTO, BLANQUEAR, BEYOND, DIAMANTE | Tecnologia BEYOND, aclara cuidando esmalte, evaluacion necesaria. Link a landing de blanqueamiento. | `blanqueamiento` |
| **implantes** | IMPLANTES, IMPLANTE, CIMA, RISA | Planificacion 3D, implantes de alta gama, casos complejos con poco hueso. Evaluacion presencial indispensable. | `main` |
| **lift** | LIFT | Refrescamiento Natural: mejor aspecto sin perder esencia. Plan segun proporciones unicas. Valoracion facial. | `main` |
| **evaluacion** | EVALUACION, CIRUGIA, CONSULTA | Punto de partida: evaluacion diagnostica para armar plan de tratamiento. | `main` |

**Matching:** Accent-insensitive, case-insensitive via NFKD normalization.

```python
def get_route_for_text(text: str) -> Optional[CTARoute]:
    normalized_text = _normalize(text)  # NFKD + strip diacritics + UPPER
    for route in CTA_ROUTES:
        for kw in route.keywords:
            if _normalize(kw) in normalized_text:
                return route
    return None
```

---

## 6. Context Assembly (buffer_task)

**Archivo:** `orchestrator_service/services/buffer_task.py` (lineas ~940-1100)

El `buffer_task` es el orquestador de contexto que prepara TODO antes de invocar al engine.

### 6.1 Treatment Plan Context

Si el paciente tiene un presupuesto activo, se inyecta:
- Total del presupuesto, monto pagado, pendiente
- Cuotas y descuentos configurados
- Condiciones de pago

```python
# Ejemplo de inyeccion
"PRESUPUESTO ACTIVO: $150.000"
"  Pagado: $75.000"
"  Pendiente: $75.000"
"  Cuotas: 3 ($25.000/cuota)"
```

### 6.2 Patient Memories

Recupera memorias persistentes del paciente via `format_memories_for_prompt()`. Se usa el texto del mensaje actual como query para relevancia semantica.

### 6.3 RAG (pgvector Semantic FAQ Search)

```python
from services.embedding_service import format_all_context_with_rag

rag_context = await format_all_context_with_rag(tenant_id, user_text, faqs)
# Retorna:
#   faqs_section:        Top-5 FAQs por cosine similarity
#   insurance_section:   Obras sociales relevantes
#   derivation_section:  Reglas de derivacion relevantes
#   instructions_section: Instrucciones de tratamiento relevantes
```

**Fallback:** Si `format_all_context_with_rag` falla, intenta el RAG legacy (`format_faqs_with_rag`, solo FAQs). Si tambien falla, usa inyeccion estatica de las primeras 20 FAQs.

### 6.4 Feriados

```python
from services.holiday_service import get_upcoming_holidays
holidays = await get_upcoming_holidays(pool, tenant_id, days_ahead=30)
```

Se inyectan los proximos 7 feriados con estado (CERRADO o HORARIO ESPECIAL + rango).

### 6.5 Intent Classification

Clasificacion basada en keywords (<1ms):

```python
intent_tags = classify_intent(messages)
```

Tags posibles: `implant`, `payment`, `media`, etc. Se usan para inyeccion condicional de secciones del prompt (solo se inyectan las secciones relevantes al intent detectado).

### 6.6 Greeting State

```python
from services.greeting_state import has_greeted
is_greeting_pending = not await has_greeted(tenant_id, phone)
```

Evita repetir el saludo institucional si ya se saludo en la sesion. Si el check falla, fallback conservador: saludar.

---

## 7. Procesamiento de Agenda

### 7.1 check_availability

**Signature:**
```python
@tool
async def check_availability(
    date_query: str,           # Texto del paciente sobre la fecha (OBLIGATORIO)
    interpreted_date: str,     # Fecha YYYY-MM-DD del LLM (OBLIGATORIO)
    search_mode: str,          # "exact" | "week" | "month" | "open" (OBLIGATORIO)
    professional_name: Optional[str] = None,
    treatment_name: Optional[str] = None,
    time_preference: Optional[str] = None,  # "mañana" | "tarde"
    specific_time: Optional[str] = None,    # "16:30" formato HH:MM
)
```

#### Generacion de slots

1. Resuelve la fecha objetivo (prioridad: `interpreted_date` > `parse_date(date_query)`).
2. Auto-avanza si el dia esta cerrado (clinica o profesional) — busca el proximo dia valido.
3. Genera slots libres con `generate_free_slots()` considerando:
   - Working hours del tenant (por dia de la semana)
   - Working hours del profesional (override por dia)
   - Turnos existentes en la BD
   - Bloqueos de Google Calendar
   - Duracion del tratamiento
   - Max chairs del tenant (sillones concurrentes)
4. Para modo `exact`: slots del dia + 1 comodin de otro dia.
5. Para modo `week`/`month`/`open`: distribuye en multiples dias (+7 dias).

#### Seleccion representativa (`_pick_from_slots`)

```python
def _pick_from_slots(slots: List[str], max_picks: int = 3, specific_time: Optional[str] = None) -> List[str]:
```

Algoritmo:
1. **Prioridad specific_time:** Si el paciente pidio una hora exacta y esta disponible, va primero. Si no esta disponible, busca el mas cercano (dentro de 30 min).
2. **Opcion A:** Primer slot de manana (< 13:00).
3. **Opcion B:** Primer slot de tarde (>= 13:00).
4. **Opcion C:** Comodin del bloque mas largo (slot del medio).
5. Si aun faltan, agrega el ultimo slot disponible.

Retorna hasta `max_picks` slots (default 3).

#### Auto-advance logic

Si el dia objetivo esta cerrado, es feriado, o el profesional no atiende ese dia:
- Itera dia por dia (+1) hasta encontrar un dia valido.
- Maximo 7 dias de busqueda adicional.
- Saltea feriados marcados como CERRADO.
- Usa horario especial en feriados con atencion.

#### Past-time filtering para "hoy"

Si `target_date == today`, filtra los slots que ya pasaron segun la hora actual.

### 7.2 confirm_slot

```python
@tool
async def confirm_slot(
    date_time: str,
    professional_name: Optional[str] = None,
    treatment_name: Optional[str] = None,
)
```

- Reserva temporal via **Redis** con TTL de **120 segundos**.
- Key: `slot_lock:{tenant_id}:{professional_id}:{datetime_iso}`
- Si otro paciente intenta el mismo slot dentro de los 120s, la tool retorna conflicto.
- Estado conceptual: `SLOT_LOCKED`

### 7.3 book_appointment

```python
@tool
async def book_appointment(
    date_time: str,
    treatment_reason: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    dni: Optional[str] = None,
    # ... (14 parametros en total)
    interpreted_date: Optional[str] = None,
)
```

#### Flujo interno

1. **Resolver telefono del paciente:**
   - Para si mismo: `current_customer_phone.get()`
   - Para menor: `{parent_phone}-M{N}` con `guardian_phone = parent_phone`
   - Para tercero adulto: telefono proporcionado

2. **Resolver fecha/hora:**
   - Prioridad: `interpreted_date` (YYYY-MM-DD) + hora extraida de `date_time`
   - Fallback: `parse_datetime(date_time)` completo

3. **Guardia de fecha pasada:**
   ```python
   if apt_datetime < get_now_arg():
       return "No se pueden agendar turnos para horarios que ya pasaron."
   ```

4. **Guardia de feriados:**
   - Feriado cerrado → rechaza
   - Feriado con horario especial → valida que la hora este en el rango

5. **Resolucion de tratamiento:**
   ```sql
   SELECT * FROM treatment_types
   WHERE tenant_id = $1 AND is_active = true
     AND (name ILIKE '%{treatment}%' OR code ILIKE '%{treatment}%')
   ORDER BY
     CASE WHEN LOWER(name) = LOWER($2) THEN 0 ELSE 1 END,  -- exact match first
     name ASC
   LIMIT 1
   ```

6. **Asignacion de profesional:**
   - Si se especifico: buscar por nombre (ILIKE)
   - Si no: asignar al primero disponible que atienda ese tratamiento

7. **Chair limit check:**
   - Cuenta turnos existentes en el mismo datetime
   - Si >= `tenants.max_chairs`, rechaza

8. **INSERT en appointments + emision Socket.IO:**
   ```python
   await sio.emit("NEW_APPOINTMENT", appointment_data, room=f"tenant_{tenant_id}")
   ```

9. **Generacion del bloque de sena:**
   - Si hay bank_holder_name configurado y hay precio → genera `[INTERNAL_SENA_DATA]...[/INTERNAL_SENA_DATA]`
   - El agente DEBE presentar esos datos al paciente

### 7.4 Date Parsing — Escenarios Testeados

| Entrada | Capa | Resultado |
|---------|------|-----------|
| "hoy" | 1 | `date.today()` |
| "manana" | 1 | `today + 1d` |
| "pasado manana" | 1 | `today + 2d` |
| "tomorrow" | 1 | `today + 1d` |
| "manana por la manana" | 1 | `today + 1d` (fecha) + time_preference "manana" |
| "lo antes posible" | 2 | `today + 1d` |
| "cuanto antes" | 2 | `today + 1d` |
| "primer turno" | 2 | `today + 1d` |
| "cualquier dia" | 2 | `today + 1d` |
| "urgente" | 2 | `today + 1d` |
| "30 de abril" | 3 | `2026-04-30` |
| "jueves 30 de abril" | 3 | `2026-04-30` |
| "4 de mayo" | 3 | `2026-05-04` |
| "2026-04-30" | 3 | `2026-04-30` (ISO directo) |
| "30/04" | 3 | `2026-04-30` (dayfirst) |
| "15" (sin mes, pasado) | 3 | dia 15 del MES SIGUIENTE |
| "para mayo" | 4 | `2026-05-01` |
| "fines de abril" | 4 | `2026-04-25` |
| "mitad de julio" | 4 | `2026-07-15` |
| "principio de junio" | 4 | `2026-06-03` |
| "mediados de agosto" | 4 | `2026-08-15` |
| "jueves" | 5 | Proximo jueves |
| "lunes" | 5 | Proximo lunes |
| "viernes" | 5 | Proximo viernes |
| "proxima semana" | 6 | Proximo lunes (si < 2 dias → +7) |
| "semana que viene" | 6 | Proximo lunes |
| "mes que viene" | 6 | Dia 1 del mes siguiente |
| "fines del mes que viene" | 6 | Dia 25 del mes siguiente |
| "cualquier cosa incomprensible" | 7 | `None` |

---

## 8. Procesamiento de Pagos

### 8.1 verify_payment_receipt

La tool recibe la imagen/PDF del comprobante y usa **OpenAI Vision** para extraer:
- Nombre del titular de la transferencia
- Monto transferido
- CBU/alias destino (si visible)

### 8.2 Verificacion de titular

**Fuzzy match:** Compara el nombre extraido contra `tenants.bank_holder_name` con tolerancia a:
- Variantes de nombre (con/sin segundo nombre)
- Mayusculas/minusculas
- Acentos

**CBU/alias check:** Si el comprobante muestra CBU o alias, verifica que coincida con los datos del tenant.

### 8.3 Verificacion de monto

- Monto exacto → OK
- Monto mayor (overpayment) → OK (se acepta siempre)
- Monto menor → FALLO. Informa cuanto falta y los datos bancarios para completar.
- Monto no legible → Pide comprobante mas claro.

### 8.4 Estados y confirmacion

| Verificacion | payment_status | appointment.status |
|-------------|---------------|-------------------|
| OK (monto >= esperado) | `paid` | `confirmed` |
| Parcial (monto < esperado) | `partial` | sin cambio |
| Fallo (titular no coincide) | sin cambio | sin cambio |
| 2 intentos fallidos | sin cambio | → `derivhumano` |

---

## 9. Tabla Resumen de Diferencias entre Engines

| Aspecto | TORA Solo | Multi-Agent | Social |
|---------|-----------|-------------|--------|
| **Tipo** | Engine monolitico | Engine multi-agente | Preamble sobre Solo/Multi |
| **Routing** | N/A (prompt unico) | Supervisor: 8 reglas deterministicas + LLM fallback | N/A (usa el routing del engine base) |
| **Tools** | 14 DENTAL_TOOLS completas | Subsets por agente (2-7 tools cada uno) | Whitelist (sin `triage_urgency`) |
| **Modelo** | `system_config.OPENAI_MODEL` | Mismo (via `model_resolver`) | Mismo |
| **Prompt** | `build_system_prompt()` (~1000 lineas) | Prompt especializado por agente + tenant blocks | `build_system_prompt()` + `build_social_preamble()` |
| **Date parsing** | `parse_date()` compartido | Mismas tools (heredadas de main.py) | Mismas tools (heredadas) |
| **Context loading** | En `buffer_task.py` | `PatientContext` + `tenant_context_blocks` | Depende del engine base |
| **Audit** | Logs estandar | `agent_turn_log` table por turno | Depende del engine base |
| **Max iterations** | Configurable via LangChain | 4 por agente, 5 hops max | Depende del engine base |
| **Timeout** | 60s (BFF proxy) | 45s (`asyncio.timeout`) | Depende del engine base |
| **Circuit breaker** | N/A (es el fallback) | 3 fallos → 5min fallback a Solo | N/A |
| **Health check** | `probe()` envia "pong" al LLM | `probe()` routing deterministico sin LLM | N/A |
| **Canal** | WhatsApp, Web | WhatsApp, Web | Instagram, Facebook |
| **Amigo vs Lead** | N/A | N/A | Deteccion heuristica (REGLA 4) |
| **CTA routes** | N/A | N/A | 4 rutas con keywords y pitches |
| **Markdown** | Prohibido (WhatsApp) | Prohibido (WhatsApp) | Habilitado (Chatwoot renderiza) |
| **Triage** | `triage_urgency` disponible | TriageAgent con `triage_urgency` | PROHIBIDO (solo presencial + `derivhumano`) |

---

## Apendice A: Modelo de seleccion

Ambos engines usan la **misma fuente de verdad** para el modelo:

```
system_config.OPENAI_MODEL  →  configurable desde UI (Tokens & Metrics)
```

- **Default:** `gpt-5.4-mini` (definido en `DEFAULT_OPENAI_MODEL`)
- **DeepSeek:** auto-detecta modelos `deepseek-chat`, `deepseek-reasoner` y switchea API key + base URL.
- **NUNCA** se hardcodea un modelo en el codigo de los agentes.

## Apendice B: Migraciones relevantes

| Migracion | Descripcion |
|-----------|-------------|
| `031_ai_engine_mode_column.py` | Agrega `tenants.ai_engine_mode TEXT NOT NULL DEFAULT 'solo'` |
| `032_multi_agent_tables.py` | Agrega `patient_context_snapshots` y `agent_turn_log` |

## Apendice C: Archivos clave

| Archivo | Proposito |
|---------|-----------|
| `orchestrator_service/main.py` | TORA Solo: prompt, tools, agent setup |
| `orchestrator_service/agents/supervisor.py` | Supervisor routing (8 regex + LLM) |
| `orchestrator_service/agents/specialists.py` | 6 agentes especializados |
| `orchestrator_service/agents/graph.py` | `run_turn()` entry point + `probe()` |
| `orchestrator_service/agents/state.py` | `AgentState` TypedDict |
| `orchestrator_service/agents/model_resolver.py` | Resolucion de modelo por tenant |
| `orchestrator_service/services/engine_router.py` | Dispatcher con circuit breaker |
| `orchestrator_service/services/social_prompt.py` | Preamble para Instagram/Facebook |
| `orchestrator_service/services/social_routes.py` | CTA routes (keywords + pitches) |
| `orchestrator_service/services/buffer_task.py` | Context assembly + engine dispatch |
| `orchestrator_service/services/patient_context.py` | Loader de perfil (PG) + working state (Redis) |
| `orchestrator_service/services/embedding_service.py` | RAG: pgvector embeddings |
| `orchestrator_service/routes/ai_engine_health.py` | Health check endpoint |
