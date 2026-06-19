# 🧠 Arquitectura del Agente IA — Integración Backend + Prompt + DB

> Documento de referencia completo sobre cómo funciona el agente de IA en conjunto con el backend, la base de datos, Redis y el frontend. Cada concepto está destripado al máximo detalle para entender, mantener y evolucionar el sistema.
>
> Versión: v8.2+ | Proyecto: ClinicForge | Fecha: 2026-06-09

---

## Índice

- [Parte 0 — Arquitectura General](#parte-0--arquitectura-general)
- [Parte I — Booking Engine (La Máquina de Turnos)](#parte-i--booking-engine-la-máquina-de-turnos)
  - [I.A — Fecha Mínima para Turnos](#ia--fecha-mínima-para-turnos)
  - [I.B — Días de Espera de Obra Social](#ib--días-de-espera-de-obra-social)
  - [I.C — check_availability (Tool)](#ic---check_availability-tool)
  - [I.D — confirm_slot (Tool)](#id---confirm_slot-tool)
  - [I.E — book_appointment (Tool)](#ie---book_appointment-tool)
  - [I.F — conversation_state (Redis)](#if---conversation_state-redis)
- [Parte II — Resolución de Paciente](#parte-ii--resolución-de-paciente)
  - [II.A — linked_patient_id](#iia---linked_patient_id)
  - [II.B — get_patient_id_by_context()](#iib---get_patient_id_by_context)
  - [II.C — find_patient (Tool)](#iic---find_patient-tool)
  - [II.D — Auto-link post booking](#iid---auto-link-post-booking)
  - [II.E — lead_context (Redis)](#iie---lead_context-redis)
- [Parte III — Catálogo de Tools](#parte-iii--catálogo-de-tools)
- [Parte IV — System Prompt: Sección por Sección](#parte-iv--system-prompt-sección-por-sección)
- [Parte V — Referencia Rápida de Base de Datos](#parte-v--referencia-rápida-de-base-de-datos)
- [Parte VI — Referencia Rápida de Redis](#parte-vi--referencia-rápida-de-redis)

---

# Parte 0 — Arquitectura General

## 0.1 Ciclo de Vida de un Mensaje

```
WhatsApp/IG/FB
      │
      ▼
  meta_webhooks.py / chat_endpoint()
      │
      ▼
  buffer_task.py
      │  ├── Resuelve tenant_id (de la URL o del webhook)
      │  ├── Resuelve paciente:
      │  │     1. linked_patient_id de chat_conversations
      │  │     2. current_patient_id ContextVar
      │  │     3. lead_context (Redis)
      │  ├── Inyecta contexto dinámico al prompt:
      │  │     • 📅 FECHA MÍNIMA PARA TURNOS
      │  │     • 🏥 HORARIOS DE ATENCIÓN
      │  │     • 📋 SEDE PARA HOY
      │  │     • 🎄 FERIADOS PRÓXIMOS
      │  │     • 👤 CONTEXTO DEL PACIENTE
      │  │     • 📝 [CONTEXTO DE LEAD]
      │  │     • 🩺 PROFESIONAL ASIGNADO
      │  │     • 📊 DATOS BANCARIOS
      │  └── Setea ContextVars (current_tenant_id, current_customer_phone, current_patient_id)
      │
      ▼
  build_nova_system_prompt()
      │  ├── Toma la plantilla base del system prompt
      │  ├── Inyecta todas las secciones dinámicas
      │  └── Devuelve el prompt completo para el LLM
      │
      ▼
  LLM (OpenAI / Anthropic / etc.)
      │  ├── Procesa el mensaje del paciente + prompt
      │  ├── Decide qué tool llamar (o responde directamente)
      │  └── Devuelve respuesta + tool calls
      │
      ▼
  Ejecución de Tool(s)
      │  ├── Cada tool corre en el backend
      │  ├── Lee/escribe DB, Redis, APIs externas
      │  └── Devuelve resultado estructurado
      │
      ▼
  Respuesta al paciente
      ├── Formateada según el canal (WhatsApp: sin markdown)
      └── Enviada vía WhatsApp API / IG / FB
```

## 0.2 ContextVars (El Pegamento del Sistema)

Tres variables de contexto por request, implementadas como `ContextVar` de Python (thread-local, heredadas por corrutinas):

### `current_tenant_id`

```
Tipo:     int
Origen:   Detectado del dominio/subdominio en la URL del webhook
          o del tenant_id en el payload
Set en:   buffer_task.py (cada mensaje)
Usado en: TODAS las tools — filtro obligatorio en toda query SQL
          Si falta → las tools devuelven error
Propósito: Aislamiento multi-tenant. Cada clínica ve SOLO sus datos.
```

### `current_customer_phone`

```
Tipo:     str (número normalizado, ej: "5492991234567")
Origen:   Del mensaje entrante (WhatsApp From, IG sender, FB sender)
Set en:   buffer_task.py (cada mensaje)
Usado en: TODAS las tools que necesitan identificar al paciente/chatter
          Es el FALLBACK cuando no hay linked_patient_id
Propósito: Identificar de quién es el chat en cada mensaje.
```

### `current_patient_id`

```
Tipo:     int | None
Origen:   Resuelto por buffer_task.py:
          1. linked_patient_id de chat_conversations (PRIORIDAD MÁXIMA)
          2. Buscar paciente por current_customer_phone
          3. None si no existe
Set en:   buffer_task.py (cada mensaje)
Usado en: get_patient_id_by_context() — que a su vez usan TODAS las tools
          de lectura (list_my_appointments, get_patient_anamnesis, etc.)
Propósito: El paciente "activo" para este mensaje. Puede ser distinto
           del que envía el mensaje (si hay un tercero vinculado).
```

## 0.3 Cómo se Construye el Prompt Dinámicamente

El prompt NO es estático. Cada mensaje recibe un prompt recién armado con datos frescos de DB + Redis.

### `build_nova_system_prompt()` (main.py ~línea 13295)

Esta función recibe:
- `tenant_id`
- `channel` (whatsapp, instagram, facebook)
- `clinic_data` (de `tenants` table)
- Contextos dinámicos ya inyectados por `buffer_task`

Y produce **un prompt monolítico** de ~2000-3000 líneas con:

1. **Identidad del agente** (quién es, cómo responde, tono)
2. **Rol de ventas** (proactividad, conversión)
3. **Reglas de flujo** (cómo manejar cada situación)
4. **Tool descriptions** (listado completo de herramientas)
5. **Contexto dinámico**:
   - `📅 FECHA MÍNIMA PARA TURNOS: 16/06/2026`
   - `🏥 HORARIOS DE ATENCIÓN`
   - `📋 SEDE PARA HOY: Salta 147`
   - `🎄 FERIADOS PRÓXIMOS`
   - `👤 CONTEXTO DEL PACIENTE: Nombre, teléfono, últ. turno, próx. turno`
   - `📝 [CONTEXTO DE LEAD]: OS registrada, nombre, DNI`
   - `🩺 PROFESIONAL ASIGNADO: Dr. X`
   - `📊 DATOS BANCARIOS: Alias, CBU`
   - `## REGLAS DE DERIVACIÓN`

### `specialists.py` — BookingAgent Prompt

Un prompt separado para el agente especializado en booking (cuando el sistema usa multi-agente). Similar pero más enfocado en el flujo de agendamiento. Tiene su propia:
- Máquina de estados de booking
- Reglas de terceros y menores
- Reglas de feriados y sede
- Gestión de cancelación/reprogramación

---

# Parte I — Booking Engine (La Máquina de Turnos)

## I.A — Fecha Mínima para Turnos

### ¿Qué es?

Es un valor configurable por clínica que establece la fecha más temprana desde la cual se pueden ofrecer turnos. Por ejemplo, si la fecha mínima es `16/06/2026`, ningún slot antes de esa fecha será ofrecido por el agente.

La lógica completa es: **la fecha real mínima es el máximo entre la fecha configurada y (hoy + días de espera de la OS)**.

```
fecha_real_minima = max(fecha_config, today + os_waiting_days)
```

### Dónde se guarda

```
Tabla:    tenants
Columna:  config (Tipo: JSONB)
Campo:    config.min_date (Formato: "YYYY-MM-DD" | null)
Ejemplo:  {"min_date": "2026-06-16", ...otros campos...}
NULL significa: sin restricción (se puede agendar desde hoy)
```

### Cómo se modificada desde la UI

```
Ruta:    /configuracion (ConfigView)
Acción:  CEO escribe una fecha en el input "Fecha mínima para turnos"
API:     PATCH /admin/settings/clinic → body: {"min_date": "2026-06-16"}
Backend: Actualiza tenants.config → JSONB → set min_date
Frecuencia: Casos excepcionales. Ej: la doctora viaja una semana,
           entonces se setea una fecha mínima para no tomar turnos hasta que vuelva.
```

### Cómo se inyecta al prompt

**Archivo**: `orchestrator_service/services/buffer_task.py`

Paso a paso:

1. Se lee `tenants.config` de la DB
2. Se extrae `config.get("min_date")`
3. Si existe y es una fecha futura válida:
   ```python
   min_date_str = f"📅 FECHA MÍNIMA PARA TURNOS: {min_date}\nNo ofrecer turnos antes de esta fecha."
   ```
4. Se inyecta en el prompt ANTES de las tool descriptions

**¿Qué ve la IA en el prompt?**
```
📅 FECHA MÍNIMA PARA TURNOS: 16/06/2026
No ofrecer turnos antes de esta fecha.
Los días de espera de la obra social se COMBINAN con la fecha mínima:
la fecha más temprana disponible es el máximo entre la fecha mínima
y (hoy + días de espera de la OS).
```

**¿Qué hace la IA con esto?**
- Cuando llama `check_availability`, pasa la fecha mínima como contexto
- `check_availability` NO acepta una fecha antes de la mínima (filtra en backend)
- La IA no debería pedir fechas antes de la mínima (pero si lo hace, la tool filtra)

### Cómo se combina con OS en el backend

En `check_availability` (main.py ~línea 2094):

```python
# Si el paciente especificó obra social (insurance_provider + insurance_days):
min_date_os = today + timedelta(days=insurance_days)  # ej: 3 días hábiles
# Si hay min_date_config:
min_date_config = parse_date(config.get("min_date"))  # ej: 16/06/2026
# La fecha real es el MÁXIMO:
effective_min_date = max(min_date_os, min_date_config, today)
```

### Reglas en el prompt sobre esto

**En main.py (~línea 10716)**:
```
## FECHA MÍNIMA PARA TURNOS
- RESPETAR la fecha mínima configurada para la clínica.
- Los días de espera de la obra social se COMBINAN con la fecha mínima.
- La fecha más temprana disponible es: max(fecha_mínima, hoy + días OS).
```

**En specialists.py (~línea 291)**:
```
Si en el prompt hay un bloque "# 📅 FECHA MÍNIMA PARA TURNOS", RESPETÁ esa fecha.
- Los días de espera de la obra social se COMBINAN con la fecha mínima:
  la fecha más temprana disponible es el máximo entre la fecha mínima
  y (hoy + días de espera de la OS).
```

### Impacto visual en el flujo

```
Lead: "Quiero turno para mañana"
  → check_availability con date_query="mañana"
  → Backend calcula: mañana = 10/06, min_date = 16/06
  → 10/06 < 16/06 → Backend NO devuelve slots para mañana
  → Devuelve slots desde 16/06 en adelante
  → IA responde: "A partir del 16/06 tenemos disponibilidad..."
```

---

## I.B — Días de Espera de Obra Social

### ¿Qué es?

Cada obra social tiene configurado un número de `waiting_days` (días de espera). Esto significa que cuando un paciente tiene esa OS, no se le pueden dar turnos antes de `hoy + waiting_days`.

### Dónde se guarda

```
Tabla:    insurance_config
Columnas:
  • id (SERIAL PK)
  • tenant_id (FK a tenants, filtro obligatorio)
  • insurance_provider (VARCHAR, ej: "Swiss Medical", "OSDE")
  • waiting_days (INTEGER, ej: 3 para Swiss Medical, 0 para particular)
  • is_active (BOOLEAN)
```

### Cómo se usa

**Paso 1**: La IA identifica la obra social del paciente.

```
Lead: "Tengo Swiss Medical"
  → IA llama check_insurance_coverage("Swiss Medical")
```

**Paso 2**: `check_insurance_coverage` busca en DB.

```sql
SELECT waiting_days, is_active 
FROM insurance_config 
WHERE tenant_id = $1 
  AND insurance_provider ILIKE $2 
  AND is_active = true;
```

**Paso 3**: Guarda el resultado en `lead_context`.

```python
from services.lead_context import merge as lead_ctx_merge
await lead_ctx_merge(tenant_id, chat_phone, {
    "insurance_provider": "Swiss Medical",
    "insurance_days": "3"
})
```

Esto persiste en Redis con TTL 24h. El campo `insurance_provider` queda disponible para todo el resto de la conversación.

**Paso 4**: `book_appointment` recupera de `lead_context`.

En book_appointment (main.py ~línea 3686):

```python
from services.lead_context import get as lead_ctx_get
lead_data = await lead_ctx_get(tenant_id, chat_phone)
lead_insurance = lead_data.get("insurance_provider")
lead_days_str = lead_data.get("insurance_days")  # "3"
if lead_days_str:
    insurance_days = int(lead_days_str)
    # Combina con fecha mínima
    earliest = max(today + timedelta(days=insurance_days), min_date_config, today)
```

**Paso 5**: La fecha mínima combinada se pasa a `check_availability`.

El agente puede pasar `insurance_days=3` como parámetro a `check_availability`, y la tool filtra los slots automáticamente.

### ¿Qué pasa si el paciente es PARTICULAR?

Si dice "particular" o "no tengo obra social":
- `check_insurance_coverage` no se llama (no hace falta)
- La IA lo sabe por el contexto
- `waiting_days = 0`
- Solo aplica la `min_date_config`

### ¿Qué pasa si tiene una OS no configurada?

`check_insurance_coverage` devuelve algo como:
```
"No trabajamos con [OS]. Aceptamos pacientes particulares o con [lista de OS].
¿Querés pagar como particular o tenés alguna otra cobertura?"
```

---

## I.C — check_availability (Tool)

### Nombre y Propósito

```
Nombre:   check_availability
Propósito: Consultar disponibilidad real de turnos para un día/tratamiento.
           NO agenda nada — solo MUESTRA opciones.
Ubicación: main.py ~línea 1899
Decorador: @tool (LangChain)
```

### Parámetros — Cada Uno Explicado

#### `treatment_reason: str` (OBLIGATORIO)

```
Qué es:   El nombre del tratamiento que el paciente quiere.
Origen:   Normalizado por resolve_canonical_treatment() contra treatment_types.
          Puede ser el nombre exacto de la BD o un término del paciente.
          Si el paciente dice "consulta" → se resuelve al treatment_type "Consulta".
Procesamiento backend:
  1. Se pasa por resolve_canonical_treatment() (main.py ~línea 1831)
  2. Busca en treatment_types por nombre exacto, ILIKE, o término popular
  3. Si hay match exacto: usa ese nombre canónico
  4. Si hay múltiples matches: devuelve sugerencias
  5. Si no hay match: devuelve list_services para que la IA muestre opciones
Uso en prompt:
  "Siempre usar el nombre exacto de list_services"
```

#### `date_query: str` (OPCIONAL, pero recomendado)

```
Qué es:   Texto libre con la fecha que pide el paciente.
          Ej: "mañana", "lunes", "martes 16", "junio", "la próxima semana"
Procesamiento backend:
  1. Pasa por parse_datetime() con interpretable_date opcional
  2. Resuelve fechas relativas ("mañana", "pasado mañana")
  3. Resuelve días de semana ("lunes" → próximo lunes)
  4. Resuelve fechas parciales ("junio" → todo junio, "16" → 16 del mes actual)
  5. Si NO se pasa: busca en modo ASAP (próximos 7 días)
Nota crítica:
  "Si el paciente pregunta por un día específico PERO no hay slots,
  la IA debe ofrecer alternativas sin que el paciente lo pida."
```

#### `time_preference: str` (OPCIONAL)

```
Qué es:   Preferencia horaria del paciente.
Valores:  "mañana" (antes de 12:00), "tarde" (12:00-18:00), "noche" (después de 18:00)
          o None si no especifica.
Uso backend:
  Filtra los slots generados para que solo incluyan los del rango solicitado.
Importante:
  Si el paciente NO da preferencia, se ofrecen slots en TODOS los horarios.
```

#### `professional_name: str` (OPCIONAL)

```
Qué es:   Profesional específico que pide el paciente.
          Si NO se pasa, se buscan slots con TODOS los profesionales activos
          para ese tratamiento en la sede del día.
Procesamiento:
  - Busca en professionals por nombre/apellido dentro del tenant
  - Cruza con treatment_type_assignments (qué profesionales dan ese tratamiento)
  - Filtra por profesionales activos (users.status = 'active')
```

#### `insurance_provider: str` (OPCIONAL)

```
Qué es:   Nombre de la obra social, si ya se sabe.
          Normalmente ya está en lead_context.insurance_provider.
Uso backend:
  - Busca los waiting_days en insurance_config
  - Combina con min_date para calcular effective_min_date
  - No filtra slots por OS (eso se hace en book_appointment)
  - Solo afecta la fecha mínima
```

#### `insurance_days: int` (OPCIONAL)

```
Qué es:   Días de espera de la OS (si ya se obtuvo con check_insurance_coverage).
Uso:      Se suma a today para calcular la fecha mínima.
```

#### `interpretable_date: str` (OPCIONAL)

```
Qué es:   Una fecha en formato ISO (YYYY-MM-DD) que la IA ya resolvió.
          La IA puede pasar anchor_date="2026-06-16" para evitar que
          el backend re-interprete la fecha relativa.
Propósito:
  Cuando la IA dice "mañana" pero ya pasó la medianoche o el contexto
  cambió, el anchor_date evita que se recalcule mal.
Ejemplo:
  Paciente dijo "martes" → IA llama check_availability con
  date_query="martes", interpretable_date="2026-06-16"
```

#### `anchor_date: str` (OPCIONAL)

```
Qué es:   Fecha base YYYY-MM-DD desde la cual se resuelven fechas relativas.
          Por defecto es today. Sirve para cuando el paciente dijo "la semana
          que viene" y ya pasaron varios mensajes.
```

### Backend Paso a Paso

```
check_availability(treatment_reason, date_query, ...)
│
├── 1. Obtener tenant_id, phone de ContextVars
│
├── 2. Normalizar tratamiento vía resolve_canonical_treatment()
│   ├── Buscar en treatment_types por nombre exacto
│   ├── Buscar por ILIKE
│   ├── Buscar por términos populares (treatment_type_popular_terms)
│   └── Si no hay match → devolver list_services con "No encontré ese tratamiento"
│
├── 3. Resolver profesionales que dan ese tratamiento
│   ├── SELECT p.* FROM professionals p
│   │   JOIN treatment_type_assignments tta ON tta.professional_id = p.id
│   │   WHERE p.tenant_id = $1 AND tta.treatment_type_id = $2 AND p.is_active
│   └── Si professional_name fue pasado: filtrar por ese profesional
│
├── 4. Limpiar términos de búsqueda
│   └── sanitize_terms() — remueve "quiero", "necesito", "para", etc.
│
├── 5. Obtener feriados del mes
│   ├── SELECT * FROM feriados WHERE tenant_id = $1 AND date >= today
│   └── Marcar días CERRADO y HORARIO ESPECIAL
│
├── 6. Obtener horarios de atención
│   ├── SELECT * FROM tenant_working_hours WHERE tenant_id = $1
│   │   AND day_of_week IN (lunes, martes, ...)
│   └── Ajustar por feriados (si es feriado CERRADO → saltar)
│
├── 7. Calcular effective_min_date
│   ├── min_date_os = today + insurance_days (si hay OS)
│   ├── min_date_config = tenants.config.min_date
│   └── effective_min_date = max(min_date_os, min_date_config, today)
│
├── 8. Generar slots
│   ├── Para cada profesional + día:
│   │   ├── Obtener bloque horario del día
│   │   ├── Generar slots de 15/30 min según configuración
│   │   ├── Restar turnos ya ocupados (appointments con ese prof/día/hora)
│   │   └── Restar bloques locales (appointments bloque)
│   ├── Limitar a ~3-5 slots para no abrumar
│   └── Formatear como opciones numeradas
│
├── 9. Guardar en Redis
│   ├── Key: slot_offer:{tenant_id}:{phone}
│   ├── Value: JSON [{date, time, professional, treatment}, ...]
│   ├── TTL: 300 segundos (5 minutos)
│   └── Esto permite que confirm_slot lea las opciones exactas
│
└── 10. Devolver resultado formateado
    ├── ✅ Si hay slots:
    │   "1️⃣ Martes 16/06 — 11:30 hs (Dr. García)
    │    2️⃣ Martes 16/06 — 14:00 hs (Dr. García)
    │    3️⃣ Miércoles 17/06 — 13:00 hs (Dra. López)"
    └── ❌ Si no hay:
        "No encontré disponibilidad para [fecha]. 
         Próximas fechas con turnos: [alternativas]."
```

### Base de Datos (Lecturas)

| Tabla | Columnas | Propósito |
|-------|----------|-----------|
| `treatment_types` | id, name, duration_minutes, is_active, is_available_for_booking | Resolver nombre canónico del tratamiento |
| `treatment_type_popular_terms` | treatment_type_id, term | Términos de búsqueda populares |
| `treatment_type_assignments` | treatment_type_id, professional_id | Qué profesionales dan cada tratamiento |
| `professionals` | id, first_name, last_name, is_active | Datos del profesional |
| `users` | id, status = 'active' | Estado del profesional |
| `appointments` | id, tenant_id, professional_id, date, time, status | Turnos existentes para no duplicar |
| `feriados` | id, tenant_id, date, type (CERRADO/ESPECIAL), description | Días no laborables |
| `tenant_working_hours` | id, tenant_id, day_of_week, open_time, close_time, is_active | Horarios de atención |
| `tenants` | id, config->>'min_date' | Fecha mínima configurada |
| `insurance_config` | insurance_provider, waiting_days | Días de espera por OS |

### Redis

| Key | Value | TTL | Propósito |
|-----|-------|-----|-----------|
| `slot_offer:{tenant_id}:{phone}` | JSON array de slots | 300s | Guardar slots ofrecidos para confirm_slot |

### System Prompt (referencias)

**En main.py — PROACTIVIDAD (~línea 11005)**:
```
• Paciente dice tratamiento o quiere sacar turno → PREGUNTAR obra social PRIMERO
  antes de check_availability. NUNCA llamar check_availability sin saber si es
  particular o tiene OS.
• Paciente dice "buscame fecha"/"agendame"/"dale" → EJECUTAR, no preguntar.
• Paciente dice "cualquiera"/"no tengo preferencia" → elegí próximo día hábil y ejecutá.
```

**En main.py — REGLAS PRIMORDIALES (~línea 10716)**:
```
## 📅 FECHA MÍNIMA PARA TURNOS
- RESPETAR la fecha mínima configurada para la clínica.
- Los días de espera de la obra social se COMBINAN con la fecha mínima.
- La fecha más temprana disponible es: max(fecha_mínima, hoy + días OS).
```

**En main.py — FLUJO CORRECTO (~línea 11019)**:
```
• SIEMPRE: check_availability → paciente elige → datos si faltan (nombre, DNI)
  → confirm_slot → book_appointment. NUNCA reservar antes de tener los datos.
```

**En specialists.py — BookingAgent (~línea 276)**:
```
# NUNCA uses check_availability sin saber primero si el paciente es particular
# o de obra social.
# Antes de ofrecer turnos, preguntá SIEMPRE si tiene cobertura médica
# (obra social) o es particular.
```

### Errores Posibles

```
❌ "No encontré ese tratamiento en el sistema."
   → La IA debe llamar list_services para mostrar opciones

❌ "No hay profesionales disponibles para ese tratamiento."
   → La IA debe ofrecer ayuda general o derivar

❌ "No encontré disponibilidad para [fecha]. Próximas fechas con turnos: [alternativas]."
   → La IA debe presentar las alternativas sin preguntar "querés que busque otra fecha?"

❌ "No se encontraron feriados para la fecha solicitada."
   → No es error, es informativo
```

---

## I.D — confirm_slot (Tool)

### Nombre y Propósito

```
Nombre:   confirm_slot
Propósito: Reserva temporalmente un slot por 10 minutos (600s) usando Redis lock.
           Garantiza que nadie más tome ese slot mientras la IA recolecta datos
           restantes y llama a book_appointment.
Ubicación: main.py ~línea 6987
Decorador: @tool (LangChain)
FLUJO CORRECTO: check_availability → paciente elige → pedir datos (nombre, DNI)
                → confirm_slot → book_appointment
```

### Parámetros

#### `slot_index: int` (RECOMENDADO)

```
Qué es:   Número de la opción que el paciente eligió (1, 2, 3...).
          De las opciones que la IA ofreció con check_availability.
Procesamiento backend:
  1. Lee de Redis: slot_offer:{tenant_id}:{phone} → JSON array
  2. Accede por índice: offered[slot_index - 1]
  3. Obtiene date + time exactos
  4. Crea lock: slot_lock:{tenant_id}:{prof_id}:{date}:{time} = phone
Ventaja:  DETERMINISTA — usa exactamente lo que se ofreció, sin reinterpretación.
          Siempre que sea posible, la IA DEBE usar slot_index.
```

#### `interpreted_date: str` (ALTERNATIVA)

```
Qué es:   Fecha ISO YYYY-MM-DD que la IA ya interpretó.
          Ej: "2026-06-16"
Uso:      Si no se pasa slot_index, se usa esta fecha + el date_time.
          El backend parsea la fecha y busca disponibilidad para ese día.
          Menos preciso que slot_index porque no garantiza que sea exactamente
          el slot ofrecido.
```

#### `date_time: str` (FALLBACK)

```
Qué es:   Texto libre con la fecha/hora.
          Ej: "16/06 11:30", "martes a las 3"
Uso:      Último recurso. El backend usa parse_datetime() para interpretar.
          Alias de: slot_index que es la forma correcta.
          Si se usa interpreted_date, este campo lleva la hora.
```

#### `anchor_date: str` (RECOMENDADO)

```
Qué es:   Fecha base resuelta desde check_availability.
          Ej: si check_availability resolvió "mañana" → "2026-06-05"
Propósito: Evitar que se recalcule una fecha relativa si el contexto cambió.
           Se guarda en conversation_state via set_anchor_date() para que
           book_appointment también lo use.
```

#### `professional_name: str` (OPCIONAL)

```
Qué es:   Profesional elegido.
Uso:      Parte del lock key: slot_lock:{tenant_id}:{prof_id}:{date}:{time}
```

#### `treatment_name: str` (OPCIONAL)

```
Qué es:   Tratamiento definido.
Uso:      Informativo, se guarda en conversation_state.
```

### Backend Paso a Paso

```
confirm_slot(slot_index=1, ...)
│
├── 1. Obtener tenant_id, phone de ContextVars
│
├── 2. Guardar anchor_date en conversation_state (si se pasó)
│   └── conv_state:{tenant_id}:{phone}.anchor_date = "2026-06-16"
│
├── 3. Resolver fecha/hora con prioridad:
│   ├── PRIORIDAD 1: slot_index
│   │   ├── Leer slot_offer:{tenant_id}:{phone} de Redis
│   │   ├── offered[slot_index - 1] → {date, time, professional, treatment}
│   │   └── apt_datetime = parse(f"{date} {time}")
│   │
│   ├── PRIORIDAD 2: interpreted_date
│   │   ├── Parsear interpreted_date como ISO date
│   │   ├── Extraer hora de date_time si existe
│   │   └── apt_datetime = combine(interpreted_date, parsed_time)
│   │
│   └── PRIORIDAD 3: parse_datetime(date_time)
│       ├── Resolver fecha relativa ("mañana", "lunes")
│       └── apt_datetime = resultado
│
├── 4. Validar que no sea una fecha pasada
│   └── apt_datetime <= now → error PAST
│
├── 5. Crear Redis lock
│   ├── lock_key = slot_lock:{tenant_id}:{prof_id}:{date}:{time}
│   ├── Usar SET NX (solo si no existe)
│   ├── Si ya existe y es del mismo phone → refrescar TTL
│   ├── Si ya existe y es de OTRO phone → error UNAVAILABLE
│   ├── TTL: 600 segundos (10 minutos)
│   └── Si Redis no disponible → warning + book_appointment usará DB fallback
│
├── 6. Setear conversation_state
│   └── state = BOOKING (para tracking)
│
└── 7. Devolver resultado
    ├── ✅ "✅ Turno reservado temporalmente: Martes 16/06 a las 11:30.
    │         Tenés 10 minutos para confirmar el turno."
    └── ❌ "❌ Ese horario ya no está disponible. ¿Querés que busque otro?"
```

### Redis

| Key | Value | TTL | Propósito |
|-----|-------|-----|-----------|
| `slot_lock:{tenant_id}:{prof_id}:{date}:{time}` | `phone` (teléfono que reserva) | 600s | Lock del slot para evitar doble booking |
| `slot_offer:{tenant_id}:{phone}` | JSON array | 300s | (lectura) Para resolver slot_index |

### System Prompt (referencias)

**En main.py — ANTI-CONFIRMACIÓN-FALSA (~línea 10296)**:
```
• PROHIBIDO decir "turno confirmado" después de 'confirm_slot' — esa tool solo
  RESERVA temporalmente por 5 minutos (300s).
```

**En main.py — FLUJO CORRECTO (~línea 11019)**:
```
• SIEMPRE: check_availability → paciente elige → datos si faltan (nombre, DNI)
  → confirm_slot → book_appointment. NUNCA reservar antes de tener los datos.
```

### Errores

```
❌ "❌ No pude identificar tu número para reservar el turno."
   → phone ContextVar no disponible

❌ "❌ Ese horario ya no está disponible."
   → Slot tomado por otro paciente (lock exists with different phone)
   → IA debe re-checkear disponibilidad

⚠️ "El horario se reservó pero hubo un problema con el sistema de confirmación."
   → Redis caído (non-blocking, warning log)
   → book_appointment usará DB conflict detection como fallback
```

---

## I.E — book_appointment (Tool)

### ⚠️ LA TOOL MÁS IMPORTANTE DEL SISTEMA

```
Nombre:   book_appointment
Propósito: AGENDA definitivamente un turno en la base de datos.
           Es la ÚNICA forma de confirmar un turno. Todo lo anterior
           (check_availability, confirm_slot) son pasos preparatorios.
Ubicación: main.py ~línea 3511 → línea ~5103
           (~1600 líneas de código — la función más grande del sistema)
Decorador: @tool (LangChain)
Formato de éxito: ✅ Turno confirmado para [paciente]:...
Formato de error:  [BOOK_ERROR:CODE] mensaje [ACTION:instrucción]
```

### Parámetros — TODOS Explicados en Detalle

#### `date_time: str` (OBLIGATORIO)

```
Tipo:     str
Formato:  Texto libre ("16/06 11:30", "martes 16 a las 11:30")
          o "slot_index:1" para usar el índice exacto.
Procesamiento:
  Si coincide con "slot_index:\d+" → se extrae slot_index y se resuelve
  desde slot_offer:{tenant_id}:{phone} en Redis (igual que confirm_slot).
  Si no → se parsea con parse_datetime().
Backend:
  1. Si hay slot_index → resuelve fecha/hora exacta desde Redis offer
  2. Si no → parse_datetime con fallback a anchor_date de conversation_state
  3. Se normaliza a datetime con timezone activo
```

#### `treatment_reason: str` (OBLIGATORIO)

```
Tipo:     str
Formato:  Nombre exacto del tratamiento de la BD (ej: "Consulta de Cirugía S")
          La IA debe usar el nombre canónico de list_services.
Backend:
  1. Se pasa por resolve_canonical_treatment() para normalizar
  2. Si hay conversation_state.offered_treatment → puede override
     (si la IA pasó un nombre distinto al que se ofreció, se corrige)
```

#### `first_name: str` (OPCIONAL — pero crítico)

```
Tipo:     str | None
Propósito: Nombre del paciente para quien es el turno.
           Para self-booking: el nombre del lead.
           Para terceros: el nombre del tercero.
Backend:
  1. Se guarda en lead_context via lead_ctx_merge
  2. Si el paciente no existe en DB → se usa para crearlo
  3. Si el paciente ya existe → se ignora (no se sobreescribe)
```

#### `last_name: str` (OPCIONAL)

```
Tipo:     str | None
Propósito: Apellido del paciente.
Backend:  Mismo comportamiento que first_name.
```

#### `dni: str` (OPCIONAL)

```
Tipo:     str | None
Propósito: DNI del paciente. Se usa para:
           1. Buscar paciente existente (por DNI, más preciso que phone)
           2. Crear paciente nuevo si no existe
           3. Validar unicidad (no duplicar pacientes)
Backend:
  Si se pasa DNI + el paciente NO existe → se crea con ese DNI
  Si se pasa DNI + el paciente YA existe (mismo tenant) → se asocia
```

#### `birth_date: str` (OPCIONAL)

```
Tipo:     str | None (formato: YYYY-MM-DD, DD/MM/YYYY, o texto libre)
Propósito: Fecha de nacimiento del paciente para la ficha médica.
Backend:
  Se parsea con parse_datetime() para normalizar a ISO.
  Se guarda en patients.birth_date.
```

#### `patient_phone: str` (OPCIONAL — CLAVE PARA TERCEROS)

```
Tipo:     str | None
Propósito: CUANDO SE USA → booking para un TERCERO ADULTO.
           El teléfono de la persona para quien es el turno.
           DIFERENTE del chat_phone (que es quien está escribiendo).
EFECTO:   is_third_party = True
Backend:
  1. El paciente para el turno se busca/crea con ESTE teléfono
  2. El lead_context se guarda contra el chat_phone (quien escribe)
  3. auto-link: después de agendar, linked_patient_id = paciente creado/buscado
Ejemplo:
  Lead escribe desde +5492991234567 pero quiere turno para su mamá
  con teléfono +5492997654321 → patient_phone="+5492997654321"
```

#### `is_minor: bool` (OPCIONAL)

```
Tipo:     bool | None (default: False)
Propósito: El turno es para un MENOR DE EDAD.
EFECTO:   is_third_party = True
           Sobreescribe patient_phone con un teléfono sintético
           vinculado al tutor.
Backend:
  1. Pide minor_first_name + minor_last_name (sin DNI ni teléfono)
  2. Genera un patient_id sintético vinculado al tutor
  3. guardian_phone = [chat_phone, resolved_patient_phone]
     (el menor queda vinculado a AMBOS teléfonos)
  4. is_minor se guarda en appointments para referencia futura
```

#### `minor_first_name: str` (OPCIONAL, necesario si is_minor=True)

```
Tipo:     str | None
Propósito: Nombre del menor.
```

#### `minor_last_name: str` (OPCIONAL, necesario si is_minor=True)

```
Tipo:     str | None
Propósito: Apellido del menor.
```

#### `is_art: bool` (OPCIONAL)

```
Tipo:     bool | None (default: False)
Propósito: El turno es para TÉCNICAS DE REPRODUCCIÓN ASISTIDA (ART).
EFECTO:   is_third_party = True
           Requiere partner_name + partner_dni.
Backend:
  Crea un registro especial en appointments con tipo ART.
```

#### `partner_name: str` (OPCIONAL, necesario si is_art=True)

```
Tipo:     str | None
Propósito: Nombre de la pareja para ART.
```

#### `partner_dni: str` (OPCIONAL, necesario si is_art=True)

```
Tipo:     str | None
Propósito: DNI de la pareja para ART.
```

#### `professional_name: str` (OPCIONAL)

```
Tipo:     str | None
Propósito: Profesional específico para el turno.
Backend:
  Si no se pasa → se usa el profesional del slot en Redis offer
  (el mismo que check_availability ofreció).
```

#### `slot_index: int` (RECOMENDADO)

```
Tipo:     int | None (1-based)
Propósito: Igual que en confirm_slot — el número de opción que eligió el paciente.
           Garantiza que se agende EXACTAMENTE el slot ofrecido.
Backend:
  Lee de Redis slot_offer:{tenant_id}:{phone} y resuelve date+time exactos.
  Si no se pasa → usa date_time + parse_datetime (menos preciso).
```

#### `interpreted_date: str` (ALTERNATIVA a slot_index)

```
Tipo:     str | None
Propósito: Fecha ISO YYYY-MM-DD ya interpretada por la IA.
```

#### `anchor_date: str` (RECOMENDADO)

```
Tipo:     str | None
Propósito: Fecha base para resolver fechas relativas.
           Se lee de conversation_state si se pasó en confirm_slot.
```

### Backend Paso a Paso (Cada Uno con su Explicación)

```
book_appointment(date_time, treatment_reason, first_name, ...)
│
├── 🔴 PASO 1: Resolver slot_index
│   ├── Si date_time empieza con "slot_index:" → extraer número
│   ├── Si slot_index se pasó directamente → usar ese
│   ├── Leer slot_offer:{tenant_id}:{phone} de Redis
│   ├── Resolver fecha/hora exacta del offer[slot_index - 1]
│   └── Si falla → usar date_time directo + parse_datetime
│   ├── DB: no toca
│   ├── Redis: LECTURA slot_offer
│   └── Error: BOOK_ERROR:NOT_OFFERED si slot_index no coincide
│
├── 🔴 PASO 2: Tratamiento override
│   ├── Leer conversation_state.offered_treatment
│   ├── Si el treatment_reason pasado por la IA difiere del ofrecido
│   │   y hay un conversation_state → usar el ofrecido
│   ├── Esto corrige errores de la IA cuando pasa un nombre distinto
│   ├── DB: no toca
│   ├── Redis: LECTURA conv_state:{tenant_id}:{phone}
│   └── Log: warning level cuando ocurre
│
├── 🔴 PASO 3: DUPLICATE_BOOKING check
│   ├── Leer conversation_state.last_booked_appointment_id
│   ├── Si existe → YA HAY UN TURNO CONFIRMADO en esta conversación
│   ├── Devolver DUPLICATE_BOOKING: no agendar otro a menos que
│   │   el paciente lo solicite explícitamente
│   ├── DB: no toca
│   ├── Redis: LECTURA conv_state
│   └── Error: "DUPLICATE_BOOKING: El paciente ya tiene un turno confirmado..."
│
├── 🔴 PASO 4: Anti-loop — booking_attempts counter
│   ├── Incrementar booking_attempts en Redis
│   ├── Si attempts > MAX_BOOKING_ATTEMPTS (3) → BLOQUEADO
│   ├── Devolver BOOK_ERROR:CONFIRM_REQUIRED
│   ├── DB: no toca
│   ├── Redis: INCR booking_attempts:{tenant_id}:{phone}
│   └── Error: [BOOK_ERROR:CONFIRM_REQUIRED] + ACTION derivhumano
│
├── 🔴 PASO 5: Guardar en lead_context
│   ├── Guardar first_name, last_name, dni, treatment_reason
│   ├── Usar lead_ctx_merge con skip_if_exists
│   │   (no sobreescribe datos que ya existen)
│   ├── DB: no toca
│   ├── Redis: HSET lead_ctx:{tenant_id}:{phone}
│   └── TTL: 24h (se resetea en cada write)
│
├── 🔴 PASO 6: Recuperar obra social de lead_context
│   ├── Leer lead_ctx:{tenant_id}:{chat_phone}
│   ├── Extraer insurance_provider + insurance_days
│   ├── Si hay OS → calcular effective_min_date con waiting_days
│   ├── Si no hay OS → usar solo min_date_config
│   ├── DB: no toca
│   ├── Redis: LECTURA lead_ctx
│   └── Log: qué OS se recuperó
│
├── 🔴 PASO 7: Resolver paciente (¿quién es?)
│   ├── Si patient_phone está presente → BUSCAR/CREAR con ESE teléfono
│   │   (TERCERO ADULTO)
│   ├── Si is_minor → GENERAR teléfono sintético + vincular a tutor
│   │   (MENOR)
│   ├── Si is_art → CREAR con datos de la pareja
│   │   (ART)
│   ├── Si nada de lo anterior → BUSCAR/CREAR con chat_phone
│   │   (SELF-BOOKING)
│   ├── Búsqueda: por phone_number O por dni (el que esté disponible)
│   ├── Creación: INSERT en patients con datos recolectados
│   ├── DB: SELECT patients (lectura), INSERT patients (solo si nuevo)
│   └── Log: "BOOK PATIENT: existing=ID" o "BOOK PATIENT: NEW"
│
├── 🔴 PASO 8: Resolver profesional y slot exacto
│   ├── Si professional_name → buscar por nombre en professionals
│   ├── Si slot_index → leer slot_offer de Redis
│   ├── Encontrar profesional_id + slot exacto
│   ├── Verificar que el profesional esté activo
│   ├── DB: SELECT professionals (lectura)
│   ├── Redis: LECTURA slot_offer (posible)
│   └── Error: BOOK_ERROR:UNAVAILABLE si el prof no está activo
│
├── 🔴 PASO 9: DB conflict detection (doble check)
│   ├── Buscar en appointments si ya existe un turno para
│   │   ese tenant_id + professional_id + date + time
│   ├── Si existe → BOOK_ERROR:UNAVAILABLE
│   ├── Si no existe → refresh del slot_lock en Redis (extiende TTL)
│   ├── DB: SELECT appointments (verificar conflicto)
│   ├── Redis: refresh slot_lock TTL (si existe)
│   └── Error: [BOOK_ERROR:UNAVAILABLE]
│
├── 🔴 PASO 10: Calcular costo y seña
│   ├── Leer treatment_price de treatment_types o price_list
│   ├── Si el tratamiento requiere seña (config.seña_percentage)
│   │   → calcular seña = treatment_price * seña_percentage
│   ├── Si el paciente tiene OS → verificar coseguro
│   │   (insurance_config puede tener coseguro fijo o porcentaje)
│   ├── DB: SELECT treatment_types, price_list, insurance_config
│   └── Guardar en variables locales (sena_block, price_line)
│
├── 🔴 PASO 11: INSERT en appointments
│   ├── appointment {
│   │     tenant_id,
│   │     patient_id (resuelto en paso 7),
│   │     professional_id (resuelto en paso 8),
│   │     treatment_type_id,
│   │     date,
│   │     time,
│   │     status: 'confirmed',
│   │     is_minor (si aplica),
│   │     created_at: NOW()
│   │   }
│   ├── DB: INSERT appointments
│   └── Log: appointment_id generado
│
├── 🔴 PASO 12: Generar link de anamnesis
│   ├── Generar UUID único para la ficha pre-odontológica
│   ├── Guardar en patient_anamnesis con patient_id + appointment_id
│   ├── La URL se incluye en la respuesta para que la IA la envíe
│   └── DB: INSERT patient_anamnesis
│
├── 🔴 PASO 13: Setear conversation_state
│   ├── state = "PAYMENT_PENDING" si hay seña
│   ├── state = "BOOKED" si no hay seña
│   ├── last_booked_appointment_id = apt_id
│   ├── DB: no toca
│   ├── Redis: HSET conv_state:{tenant_id}:{phone}
│   └── Non-blocking: si falla → solo warning log
│
├── 🔴 PASO 14: Auto-link tercero (F4 — solo si is_third_party)
│   ├── Buscar chat_conversations por tenant_id + chat_phone
│   ├── UPDATE chat_conversations SET linked_patient_id = third_party_id
│   ├── DB: SELECT + UPDATE chat_conversations
│   └── Non-blocking: si falla → warning log
│   └── Log: "🔗 Auto-linked third party {phone} to conversation {id}"
│
├── 🔴 PASO 15: Limpiar offer + lead_context
│   ├── Redis: DELETE slot_offer:{tenant_id}:{phone}
│   ├── lead_ctx_clear(tenant_id, phone) si el lead se vuelve paciente
│   └── Non-blocking: warning log si falla
│
└── 🔴 PASO 16: Devolver resultado
    ├── ✅ Self: "✅ Turno confirmado para [paciente]:..."
    ├── ✅ Third-party: "✅ Turno confirmado para [tercero] (solicitado por [interlocutor]):..."
    └── ❌ Error: [BOOK_ERROR:CODE] mensaje [ACTION:instrucción]
```

### Los 8 BOOK_ERROR + DUPLICATE_BOOKING

Cada error tiene un código, un mensaje para el paciente, una causa técnica, y una acción que la IA DEBE ejecutar.

#### `BOOK_ERROR:UNAVAILABLE`

```
Mensaje:   "Ese horario ya no está disponible"
Causa:     Otro paciente tomó el slot entre check_availability y book_appointment.
           O el slot nunca existió (confirm_slot no se llamó).
Acción prompt (AI): Fresh check_availability; do NOT retry same slot.
Prompt retry: Llamá check_availability DE NUEVO para ese día.
Reintentos: Hasta 2. Al 3ero → derivhumano.
```

#### `BOOK_ERROR:EXPIRED`

```
Mensaje:   "La reserva temporal venció"
Causa:     confirm_slot lock expiró (pasaron más de 10 minutos).
Acción prompt (AI): Fresh check_availability; if 2nd EXPIRED → derivhumano.
```

#### `BOOK_ERROR:CHAIRS_FULL`

```
Mensaje:   "No hay más turnos para ese tratamiento hoy"
Causa:     Todos los slots del día están ocupados.
Acción prompt (AI): Ofrecer otro día.
```

#### `BOOK_ERROR:DUPLICATE`

```
Mensaje:   "Ya tenés un turno para ese día y horario"
Causa:     El paciente ya tiene un turno en ese exacto horario.
Acción prompt (AI): Informar al paciente.
```

#### `BOOK_ERROR:PAST`

```
Mensaje:   "No se puede reservar en el pasado"
Causa:     La fecha/hora del turno ya pasó.
Acción prompt (AI): Pedir una fecha futura.
```

#### `BOOK_ERROR:HOLIDAY`

```
Mensaje:   "Ese día es feriado"
Causa:     El día está marcado como feriado CERRADO en la BD.
Acción prompt (AI): Ofrecer el siguiente día hábil.
```

#### `BOOK_ERROR:NOT_OFFERED`

```
Mensaje:   "Ese horario no fue parte de las opciones"
Causa:     La IA pasó un slot_index que no coincide con lo ofrecido.
           O la fecha no estaba entre las opciones.
Acción prompt (AI): Volver a check_availability con la fecha correcta.
```

#### `BOOK_ERROR:CONFIRM_REQUIRED`

```
Mensaje:   "Debés llamar confirm_slot antes de book_appointment"
Causa:     Se excedió el máximo de intentos de booking (3).
           Es un ANTI-LOOP para evitar que la IA llame book_appointment
           infinitamente sin éxito.
Acción prompt (AI): "Call derivhumano with motivo='No se pudo agendar
                     después de 3 intentos'. NO sigas intentando agendar."
Es estado: Es el fusible final. Si se dispara, la IA DEBE derivar a humano.
```

#### `DUPLICATE_BOOKING` (no es BOOK_ERROR, es un check separado)

```
Mensaje:   "DUPLICATE_BOOKING: El paciente ya tiene un turno confirmado..."
Causa:     La IA intenta agendar cuando conversation_state ya tiene
           last_booked_appointment_id (ya hay un turno en esta conversación).
           Previene que la IA agende dos turnos para el mismo paciente
           en la misma conversación.
Acción prompt (AI): "Respondé la consulta del paciente. No agendes otro turno
                     a menos que el paciente lo solicite explícitamente."
```

### Redis (Todas las claves que toca)

| Key | Operación | TTL | Propósito en book_appointment |
|-----|-----------|-----|-------------------------------|
| `slot_offer:{tenant_id}:{phone}` | LECTURA + DELETE | 300s | Resolver slot_index |
| `slot_lock:{tenant_id}:{prof_id}:{date}:{time}` | LECTURA (+ refresh) | 600s | Verificar disponibilidad |
| `booking_attempts:{tenant_id}:{phone}` | INCR + LECTURA | Persistente | Anti-loop (max 3) |
| `conv_state:{tenant_id}:{phone}` | WRITE | Persistente | Setear BOOKED/PAYMENT_PENDING |
| `lead_ctx:{tenant_id}:{phone}` | LECTURA + WRITE + DELETE | 24h | Recuperar/guardar OS + datos |

### DB (Lo que escribe)

```sql
-- Si el paciente es NUEVO:
INSERT INTO patients (tenant_id, first_name, last_name, phone_number, dni, birth_date)
VALUES ($1, $2, $3, $4, $5, $6);

-- Si el paciente ya existe pero faltan datos:
UPDATE patients SET first_name = $1, last_name = $2 WHERE id = $3;

-- El turno:
INSERT INTO appointments (tenant_id, patient_id, professional_id, treatment_type_id,
                          appointment_date, appointment_time, status, is_minor)
VALUES ($1, $2, $3, $4, $5, $6, 'confirmed', $7)
RETURNING id;

-- La ficha médica:
INSERT INTO patient_anamnesis (tenant_id, patient_id, appointment_id, token)
VALUES ($1, $2, $3, $4);

-- Auto-link (solo si es tercero):
UPDATE chat_conversations SET linked_patient_id = $1
WHERE tenant_id = $2 AND phone_number = $3;
```

### System Prompt (referencias directas)

**RE-INTENTO INTELIGENTE (~línea 11682)**:
```
RE-INTENTO INTELIGENTE (BOOKING FAILURES):
• Si book_appointment devuelve ❌, ⚠️, o [BOOK_ERROR:...] por turno ocupado o conflicto:
  1) Llamá check_availability DE NUEVO para ese día (la disponibilidad pudo cambiar).
  2) Presentá las nuevas opciones al paciente.
  3) NO adivinés horarios. NO iterés hora por hora.
• Si falla por datos incorrectos (DNI inválido, nombre vacío): pedí SOLO el dato
  que falló, no todos de nuevo.
• Máximo 2 reintentos automáticos. Al 3er fallo → llamá
  derivhumano("No pude agendar tras 2 intentos").
```

**ANTI-CONFIRMACIÓN-FALSA (~línea 10296)**:
```
REGLA ANTI-CONFIRMACIÓN-FALSA (CRÍTICO):
• PROHIBIDO decir "tu turno está confirmado" o "nos vemos" sin haber ejecutado
  'book_appointment' y recibido ✅.
• PROHIBIDO decir "turno confirmado" después de 'check_availability' — esa tool
  solo MUESTRA opciones, no agenda.
• PROHIBIDO decir "turno confirmado" después de 'confirm_slot' — esa tool solo
  RESERVA temporalmente por 5 minutos (300s).
• La ÚNICA forma de confirmar un turno es ejecutar 'book_appointment' y recibir
  ✅ en la respuesta.
• Si la respuesta de 'book_appointment' contiene [INTERNAL_SEÑA_DATA], DEBÉS
  presentar los datos bancarios OBLIGATORIAMENTE.
• Si decís "confirmado" sin haber recibido ✅ de book_appointment, estás MINTIENDO
  al paciente.
```

**MÁQUINA DE ESTADOS DEL BOOKING (specialists.py ~línea 301)**:
```
# MÁQUINA DE ESTADOS DEL BOOKING (REGLA DURA)
Estado 1 → OFRECER: llamás check_availability UNA SOLA VEZ con el tratamiento
Estado 2 → ELEGIR: el paciente selecciona un horario
Estado 3 → DATOS: pedís nombre + apellido + DNI si no los tenés
Estado 4 → RESERVAR (confirm_slot): reservás temporalmente el turno
Estado 5 → AGENDAR (book_appointment): guardás el turno definitivamente
```

---

## I.F — conversation_state (Redis)

### ¿Qué es?

Un hash en Redis que guarda el estado actual de la conversación para tracking y anti-loop.

### Key

```
conv_state:{tenant_id}:{phone}
Ej: conv_state:1:5492991234567
```

### Campos del Hash

| Campo | Tipo | Propósito | Quién lo escribe |
|-------|------|-----------|------------------|
| `state` | string | Estado actual: IDLE, BOOKING, BOOKED, PAYMENT_PENDING | book_appointment, confirm_slot, check_availability |
| `last_booked_appointment_id` | int | ID del último turno agendado en esta conversación | book_appointment |
| `booking_attempts` | int | Contador de intentos de booking | book_appointment (via increment_booking_attempts) |
| `offered_treatment` | string | Nombre del tratamiento que se ofreció en check_availability | check_availability |
| `anchor_date` | string | Fecha base YYYY-MM-DD para resolver fechas relativas | confirm_slot (set_anchor_date) |
| `last_derivhumano_at` | datetime | Cuándo se llamó a derivhumano por última vez | derivhumano |
| `human_override_until` | datetime | Hasta cuándo está bloqueado el chat por intervención humana | derivhumano |
| `failed_slots` | JSON | Lista de slots que fallaron (para evitar re-ofrecerlos) | book_appointment (append_failed_slot) |

### Estados

```
IDLE → BOOKING → BOOKED → (fin)
                  BOOKED → IDLE (si se cancela)
                  PAYMENT_PENDING → BOOKED (si paga)
                  PAYMENT_PENDING → IDLE (si no paga y expira)
```

### TTL

No tiene TTL fijo. Los campos se actualizan en cada operación.

---

# Parte II — Resolución de Paciente

## II.A — linked_patient_id

### ¿Qué es?

Es el mecanismo que permite que un chat de WhatsApp esté **vinculado a un paciente específico**, distinto del dueño del teléfono del chat.

### Dónde se guarda

```
Tabla:    chat_conversations
Columna:  linked_patient_id (FK → patients.id, NULLABLE)
```

### Cómo se vincula

**Desde la UI** (ChatsView):
1. El staff (CEO/secretaria) hace clic en "Vincular Paciente" en el panel derecho
2. Se abre un modal de búsqueda de pacientes
3. Selecciona un paciente existente
4. API: PATCH `/admin/chat/link` con `{phone, patient_id}`
5. Backend: UPDATE `chat_conversations SET linked_patient_id = $1`

**Automáticamente** desde book_appointment (F4):
1. La IA agenda un turno para un tercero (patient_phone pasado)
2. `book_appointment` detecta `is_third_party = True`
3. Busca `chat_conversations` por `tenant_id + chat_phone`
4. UPDATE `chat_conversations SET linked_patient_id = third_party_patient_id`
5. Non-blocking: si falla, solo warning log

**Desde admin_routes** (~línea 12400+):
- GET `/admin/chat/context/{phone}`: Devuelve linked_patient_id + datos del paciente
- Este endpoint tiene PRIORIDAD para linked_patient_id sobre phone lookup

### Cómo se usa en el prompt

En **buffer_task.py** (~línea 1200):

```python
# 1. Buscar linked_patient_id
conv = await db.pool.fetchrow(
    "SELECT linked_patient_id FROM chat_conversations WHERE tenant_id = $1 AND phone_number = $2",
    tenant_id, phone
)
if conv and conv['linked_patient_id']:
    patient_id = conv['linked_patient_id']
    # Setear ContextVar
    from agents.context import set_current_patient_id
    set_current_patient_id(patient_id)
    # Buscar datos del paciente vinculado
    patient = await db.pool.fetchrow(
        "SELECT * FROM patients WHERE id = $1 AND tenant_id = $2",
        patient_id, tenant_id
    )
    # Inyectar en el prompt como CONTEXTO DEL PACIENTE
    prompt_context = f"""
    📋 PACIENTE VINCULADO AL CHAT:
    • Nombre: {patient['first_name']} {patient['last_name']}
    • Teléfono: {patient['phone_number']}
    ...
    """
```

### Prioridad en la resolución

```
1. current_patient_id (ContextVar) → seteado por buffer_task
   → viene de linked_patient_id de chat_conversations
2. Si no hay linked_patient_id → buscar paciente por current_customer_phone
3. Si no existe el paciente → None → todas las tools de lectura devuelven
   "No tengo suficiente información sobre el paciente"
```

### Efecto en el prompt

La IA ve un bloque `[CONTEXTO DEL PACIENTE]` al inicio de su prompt que incluye:

```
REGLAS DE USO DEL CONTEXTO DEL PACIENTE:
• Si tiene "Nombre registrado" → usá su nombre en el saludo.
• Si tiene "ÚLTIMO TURNO" → mencionarlo si corresponde.
• Si tiene "SEGUIMIENTO POST-TRATAMIENTO" → preguntar cómo sigue.
• Si tiene "PRÓXIMO TURNO" → mencionarlo.
• Si tiene "HIJOS/MENORES" → recordar que puede agendar para sus hijos.
• SIEMPRE llamar a 'list_my_appointments' para info exacta. NUNCA de memoria.
• Si tiene "DNI registrado" y "Email" → no volver a pedir.
• Si tiene "PROFESIONAL ASIGNADO" → usar ESE profesional.
```

### Regla en el prompt para el agente

En `main.py` (~línea 10270):
```
• Si tiene "HIJOS/MENORES" → recordar que puede agendar para sus hijos.
```

---

## II.B — get_patient_id_by_context()

### ¿Qué es?

Un helper centralizado que usan TODAS las tools del agente para determinar **qué paciente es el sujeto de la acción**. No es una tool, es un utility interno.

### Código (común en las tools)

```python
async def get_patient_id_by_context() -> Optional[int]:
    """
    Resuelve el patient_id con esta prioridad:
    1. current_patient_id (ContextVar) — viene de linked_patient_id
    2. Buscar paciente por current_customer_phone (el que escribe)
    3. None si no existe
    """
    from agents.context import current_patient_id as ctx_patient_id
    pid = ctx_patient_id.get()
    if pid:
        return pid
    
    # Fallback: buscar por teléfono del chat
    tenant_id = current_tenant_id.get()
    phone = current_customer_phone.get()
    if tenant_id and phone:
        row = await db.pool.fetchrow(
            "SELECT id FROM patients WHERE tenant_id = $1 AND phone_number = $2",
            tenant_id, phone
        )
        return row['id'] if row else None
    
    return None
```

### Tools que lo usan (lista completa)

| Tool | Propósito | Sin paciente |
|------|-----------|-------------|
| `list_my_appointments` | Listar turnos del paciente | "No tengo información..." |
| `get_patient_anamnesis` | Leer ficha médica | "No tengo información..." |
| `get_patient_clinical_history` | Leer historia clínica | "No tengo información..." |
| `get_patient_odontogram` | Leer odontograma | "No tengo información..." |
| `get_patient_payment_status` | Leer estado de pagos | "No tengo información..." |
| `cancel_appointment` | Cancelar turno | "No tengo información..." |
| `reschedule_appointment` | Reprogramar turno | "No tengo información..." |
| `save_patient_anamnesis` | Guardar ficha | Crea nuevo paciente |
| `save_patient_email` | Guardar email | Crea nuevo paciente |
| `save_patient_birth_date` | Guardar fecha nac. | Crea nuevo paciente |
| `link_payment_to_patient` | Vincular pago | "No tengo información..." |
| `verify_payment_receipt` | Verificar comprobante | "No tengo información..." |
| `list_patient_documents` | Listar documentos | "No tengo información..." |

### Impacto del linked_patient_id en las tools

Cuando el chat está vinculado a un tercero (linked_patient_id seteado):

```
Chat de Juan Pérez (+5492991234567) vinculado a María López (patient_id=42)

Juan escribe: "¿Mi mamá tiene turno la semana que viene?"
  → buffer_task: linked_patient_id = 42 (María)
  → current_patient_id = 42
  → list_my_appointments() → get_patient_id_by_context() = 42
  → SQL: SELECT * FROM appointments WHERE patient_id = 42
  → Devuelve los turnos de MARÍA, no los de Juan
```

---

## II.C — find_patient (Tool)

### Nombre y Propósito

```
Nombre:   find_patient
Propósito: Buscar pacientes en el sistema por nombre, apellido, DNI o teléfono.
           Permite a la IA verificar si un tercero ya está registrado antes de
           agendarle un turno.
Ubicación: main.py ~línea 3462
Decorador: @tool (LangChain)
Creada en: SDD multi-persona-booking-flow (F5)
```

### Parámetros

#### `query: str` (OBLIGATORIO)

```
Qué es:   Texto de búsqueda. Puede ser nombre, apellido, DNI o número de teléfono.
          La IA pasa lo que el lead le dijo.
Ejemplos: "María López", "López", "33384513", "2997654321"
```

### Backend

```python
tenant_id = current_tenant_id.get()
like_pattern = f"%{query}%"
rows = await db.pool.fetch(
    """
    SELECT id, first_name, last_name, phone_number, dni 
    FROM patients 
    WHERE tenant_id = $1 
      AND (first_name ILIKE $2 OR last_name ILIKE $2 
           OR phone_number ILIKE $2 OR dni ILIKE $2)
    ORDER BY first_name
    LIMIT 10
    """,
    tenant_id, like_pattern
)
```

### DB

```sql
SELECT id, first_name, last_name, phone_number, dni 
FROM patients 
WHERE tenant_id = $1 
  AND (first_name ILIKE '%lópez%' OR last_name ILIKE '%lópez%' 
       OR phone_number ILIKE '%lópez%' OR dni ILIKE '%lópez%')
ORDER BY first_name
LIMIT 10;
```

### Formato de respuesta

```
✅ Pacientes encontrados:
• ID:42 — María López | 📞 5492997654321 | DNI: 33384513
• ID:55 — Juan López | 📞 5492991112233

❌ No se encontraron pacientes con ese criterio de búsqueda.
```

### System Prompt

En las REGLAS DE AGENDAMIENTO PARA TERCEROS (~línea 10274):
```
• PASOS para booking de tercero:
  4. Usá `find_patient(nombre)` para buscar si el tercero ya existe en el sistema
  5. Si existe → podés consultar sus datos
  6. Si NO existe → pedí los datos que faltan para registrarlo
```

En specialists.py (~línea 332):
```
- Usá `find_patient(nombre)` para verificar si el tercero ya existe en el sistema.
```

### Errores

```
❌ "Error: No se pudo identificar la clínica actual."
   → ContextVar tenant_id no disponible

❌ "No se encontraron pacientes con ese criterio de búsqueda."
   → No hay match → la IA debe pedir más datos
```

---

## II.D — Auto-link post booking

### ¿Qué es?

Un bloque de código inyectado en `book_appointment` que, después de agendar exitosamente un turno para un tercero, vincula automáticamente a ese tercero al chat.

### Código (main.py ~línea 5038)

```python
# Auto-link third party to conversation for future context
if phone and is_third_party:
    try:
        conv = await db.pool.fetchrow(
            "SELECT id FROM chat_conversations WHERE tenant_id = $1 AND phone_number = $2",
            tenant_id, chat_phone
        )
        if conv:
            await db.pool.execute(
                """UPDATE chat_conversations SET linked_patient_id = 
                   (SELECT id FROM patients WHERE tenant_id = $1 AND phone_number = $2) 
                   WHERE id = $3""",
                tenant_id, phone, conv['id']
            )
            logger.info(f"🔗 Auto-linked third party {phone} to conversation {conv['id']}")
    except Exception as link_err:
        logger.warning(f"Auto-link failed (non-blocking): {link_err}")
```

### Flujo completo

```
1. Lead escribe desde +5492991234567
2. Lead: "Quiero turno para mi mamá, se llama María López, teléfono 2997654321"
3. IA llama book_appointment con patient_phone="2997654321"
4. is_third_party = True (porque patient_phone está presente)
5. Backend agenda el turno para María López (la busca/crea)
6. 🔴 Auto-link:
   - Busca chat_conversations WHERE phone_number = "5492991234567"
   - UPDATE linked_patient_id = patient_id de María López
7. Próximo mensaje del lead:
   - buffer_task lee linked_patient_id = María
   - current_patient_id = María
   - TODAS las tools ahora resuelven a María
8. Si el lead vuelve a pedir algo para sí mismo:
   - La IA debe preguntar "¿Esto es para vos o para mamá?"
```

### System Prompt

```
• DESPUÉS de agendar al tercero exitosamente → queda VINCULADO al chat.
  Las próximas consultas serán sobre EL/ella, no sobre vos.
• Si después de vincular al tercero el paciente vuelve a pedir algo para sí mismo
  → preguntá "¿Esto es para vos o para [nombre]?"
```

### Riesgos

```
⚠️ Si el chat ya tenía un linked_patient_id, se SOBREESCRIBE.
   → El auto-link siempre pisa el valor anterior.
   → Si el staff vinculó manualmente a Juan, y la IA agenda a María,
     el chat queda vinculado a María.
⚠️ Es non-blocking: si falla, el turno igual se agendó.
   → El paciente tiene el turno pero no queda vinculado.
   → La IA sigue resolviendo por teléfono del chat.
```

---

## II.E — lead_context (Redis)

### ¿Qué es?

Un hash en Redis que acumula datos estructurados del lead a lo largo de la conversación. Persiste información que la IA va descubriendo (nombre, DNI, obra social, etc.) para no perder contexto entre mensajes.

### Archivo

```
services/lead_context.py (170 líneas)
```

### Key

```
lead_ctx:{tenant_id}:{phone_digits}
Ej: lead_ctx:1:5492991234567
TTL: 86400 segundos (24 horas) — se resetea en cada escritura
```

### Campos

| Campo | Tipo | Quién lo escribe | Propósito |
|-------|------|-------------------|-----------|
| `treatment_name` | string | check_availability | Tratamiento que el lead quiere |
| `professional_name` | string | check_availability / IA | Profesional que el lead prefiere |
| `first_name` | string | book_appointment, save_patient_email | Nombre del lead |
| `last_name` | string | book_appointment, save_patient_email | Apellido del lead |
| `dni` | string | book_appointment | DNI del lead |
| `email` | string | save_patient_email | Email del lead |
| `date_query` | string | check_availability | Fecha que pidió el lead |
| `interpreted_date` | string | check_availability | Fecha interpretada por el backend |
| `search_mode` | string | check_availability | "specific_date" o "asap" |
| `channel` | string | buffer_task | Canal de origen (whatsapp, ig, fb) |
| `booking_type` | string | IA / tool | "self", "third_party", "minor" |
| `minor_first_name` | string | book_appointment | Nombre del menor (si aplica) |
| `minor_last_name` | string | book_appointment | Apellido del menor |
| `minor_dni` | string | book_appointment | DNI del menor |
| `insurance_provider` | string | check_insurance_coverage | Obra social del lead |
| `insurance_days` | string | check_insurance_coverage | Días de espera de la OS |
| `first_seen_at` | datetime | lead_ctx.merge | Cuándo se creó |
| `last_updated_at` | datetime | lead_ctx.merge | Última actualización |

### API del servicio

```python
# MERGE: Escribe campos (no sobreescribe si skip_if_exists)
async def merge(tenant_id: int, identifier: str, fields: Dict[str, str],
                skip_if_exists_fields: Optional[List[str]] = None) -> None:
    """
    - Filter out empty values
    - Handle skip-if-exists: read current values, don't overwrite
    - Always update last_updated_at
    - Set first_seen_at if new
    - Reset TTL to 24h
    """

# GET: Lee todos los campos
async def get(tenant_id: int, identifier: str) -> Dict[str, str]:
    """
    - Returns {} on failure or missing key (never raises)
    - Non-blocking: warning log on error
    """

# CLEAR: Elimina el hash (cuando el lead se vuelve paciente)
async def clear(tenant_id: int, identifier: str) -> None:
    """
    - Called after successful book_appointment
    - Non-blocking: warning log on error
    """

# FORMAT: Produce el bloque [CONTEXTO DE LEAD] para el prompt
def format_for_prompt(data: Dict[str, str]) -> str:
    """
    Output:
    [CONTEXTO DE LEAD — datos acumulados de la conversación]
    • Nombre: Juan
    • Apellido: Pérez
    • DNI: 33384513
    • Obra social / Prepaga: Swiss Medical
    [/CONTEXTO DE LEAD]
    """
```

### Dónde se escribe

| Tool / Proceso | Campos que escribe |
|----------------|-------------------|
| `check_insurance_coverage` | insurance_provider |
| `check_availability` | treatment_name, professional_name, date_query, interpreted_date, search_mode |
| `book_appointment` | first_name, last_name, dni, minor_first_name, minor_last_name, booking_type |
| `save_patient_email` | email, first_name, last_name |
| `save_patient_birth_date` | birth_date |
| `buffer_task` | channel |

### Dónde se lee

| Proceso | Propósito |
|---------|-----------|
| `buffer_task` (~línea 1222) | Lo formatea e inyecta al prompt como `[CONTEXTO DE LEAD]` |
| `book_appointment` (~línea 3686) | Recupera insurance_provider para calcular fecha mínima |

### Inyección al prompt

En `buffer_task.py`:

```python
from services.lead_context import get as lead_ctx_get, format_for_prompt
lead_data = await lead_ctx_get(tenant_id, phone)
if lead_data:
    prompt_context = format_for_prompt(lead_data)
    # Se inyecta en el prompt como un bloque más
```

La IA ve al inicio de CADA mensaje:

```
[CONTEXTO DE LEAD — datos acumulados de la conversación]
• Nombre: Juan
• Apellido: Pérez
• DNI: 33384513
• Obra social / Prepaga: Swiss Medical
• Tratamiento de interés: Consulta
[/CONTEXTO DE LEAD]
```

Esto evita que la IA pregunte DOS VECES los mismos datos.

### Flujo de limpieza

```python
# Después de book_appointment exitoso:
if nuevo_paciente:
    await lead_ctx_clear(tenant_id, chat_phone)
    # El lead ahora es paciente, ya no necesita lead_context
```

---

# Parte III — Catálogo de Tools

> Esta sección cubre las tools principales que no son parte del Booking Engine.
> Cada tool sigue el mismo formato: propósito, parámetros, backend, DB, prompt, errores.

## III.A — check_insurance_coverage

```
Nombre:   check_insurance_coverage
Propósito: Verificar si la clínica trabaja con una obra social específica
           y obtener los días de espera.
Ubicación: main.py ~línea 8349
```

### Parámetros

| Parámetro | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `insurance_provider` | str | SÍ | Nombre de la obra social (ej: "Swiss Medical", "OSDE") |

### Backend

```python
# Buscar en insurance_config
row = await db.pool.fetchrow(
    "SELECT waiting_days, is_active FROM insurance_config WHERE tenant_id = $1 AND insurance_provider ILIKE $2",
    tenant_id, insurance_provider
)
if row and row['is_active']:
    # Guardar en lead_context
    await lead_ctx_merge(tenant_id, phone, {
        "insurance_provider": insurance_provider,
        "insurance_days": str(row['waiting_days'])
    })
    return f"✅ Trabajamos con {insurance_provider}. Tiene {row['waiting_days']} días de espera."
else:
    return f"⚠️ No trabajamos con {insurance_provider}. Aceptamos: [lista de OS activas]."
```

### DB

```sql
SELECT insurance_provider, waiting_days 
FROM insurance_config 
WHERE tenant_id = 1 AND is_active = true;
-- Devuelve: Swiss Medical (3), OSDE (0), Particular (0), etc.
```

### System Prompt

```
• Obras sociales: SIEMPRE llamá check_insurance_coverage cuando el paciente
  mencione el nombre de su obra social. NUNCA respondas genéricamente
  "trabajamos con tu obra social" — confirmá específicamente por nombre
  usando la respuesta de la tool.
```

### Errores

```
⚠️ "No trabajamos con [OS]. Aceptamos: [lista]."
   → La IA debe ofrecer las OS disponibles o preguntar si es particular.

❌ "No se pudo verificar la obra social."
   → Error interno (non-blocking)
```

## III.B — derivhumano

```
Nombre:   derivhumano
Propósito: Escalar la conversación a un humano. Es la última instancia.
           También bloquea el chat por 24h (human_override_until).
Ubicación: main.py ~línea 6156
```

### Parámetros

| Parámetro | Tipo | Obligatorio | Descripción |
|-----------|------|-------------|-------------|
| `reason` | str | SÍ | Motivo exacto de la derivación |

### Backend

```python
# Guardar en conversation_state
# Setear human_override_until = NOW() + 24h
# Marcar en patients.human_override_until
# Esto previene que la IA siga respondiendo en ese chat por 24h
```

### DB

```sql
UPDATE patients SET human_override_until = $1 
WHERE tenant_id = $2 AND phone_number = $3;
UPDATE chat_conversations SET human_override_until = $1
WHERE tenant_id = $2 AND phone_number = $3;
```

### Redis

```
conv_state update: last_derivhumano_at = NOW()
```

### System Prompt (reglas de escalación ~línea 11026)

```
SÍ ESCALAR (llamar derivhumano):
• Solicitud explícita del paciente de hablar con un humano
• Emergencia médica real (dolor muy fuerte, accidente)
• Amenaza o violencia
• Paciente existente no migrado
• 3er fallo de book_appointment (anti-loop)
• Urgencia sin disponibilidad
• Mala experiencia en esta clínica

NO ESCALAR (PROHIBIDO):
• Por miedo, mala experiencia, precio, obra social desconocida, frustración
• "Déjame consultarlo" o "Lo voy a pensar"
• Paciente que pide información de precios
• Ante cualquier duda, la IA debe intentar resolver antes de derivar
```

## III.C — list_my_appointments

```
Nombre:   list_my_appointments
Propósito: Listar los turnos del paciente activo.
Ubicación: main.py ~línea 5347
Parámetros: date_from (opcional), date_to (opcional), status (opcional)
Resolución: get_patient_id_by_context() → patient_id
DB: SELECT * FROM appointments WHERE patient_id = $1 AND tenant_id = $2 ...
```

## III.D — cancel_appointment

```
Nombre:   cancel_appointment
Propósito: Cancelar un turno del paciente.
Ubicación: main.py ~línea 5431
Parámetros: date_query (obligatorio — qué turno cancelar)
Resolución: get_patient_id_by_context() → patient_id
DB: UPDATE appointments SET status = 'cancelled' WHERE id = $1
Google Calendar: Si calendar_provider = 'google', también cancela el evento GCal
```

## III.E — reschedule_appointment

```
Nombre:   reschedule_appointment
Propósito: Reprogramar un turno existente.
Ubicación: main.py ~línea 5578
Parámetros: original_date (obligatorio), new_date_time (obligatorio), interpreted_date
Flujo: 1) Cancelar original → 2) Buscar nuevo slot → 3) Crear nuevo appointment
DB: UPDATE status='cancelled' + INSERT nuevo appointment
```

## III.F — triage_urgency

```
Nombre:   triage_urgency
Propósito: Clasificar la urgencia de los síntomas del paciente.
Ubicación: main.py ~línea 5045
Parámetros: symptoms (obligatorio)
Salida: Nivel (emergency/high/normal/low) + acción recomendada
Uso: NO reemplaza al criterio médico. Solo orienta a la IA sobre cómo responder.
```

---

# Parte IV — System Prompt: Sección por Sección

> Cada bloque del system prompt, con su ubicación exacta, qué logra,
> con qué interactúa del backend, y riesgo de modificación.

## IV.A — REGLAS PRIMORDIALES (~línea 10716)

### Ubicación

```
main.py ~línea 10716 (Inicio del bloque de instrucciones principales)
```

### Contenido resumido

- Cobertura médica: preguntar SIEMPRE antes de ofrecer turnos
- Fecha mínima: respetar la configurada + combinación con OS
- Booking para terceros y menores
- Profesional asignado: prioridad

### Interacción con backend

```python
# Se inyectan dinámicamente desde buffer_task:
# 📅 FECHA MÍNIMA PARA TURNOS: 16/06/2026
# 🏥 HORARIOS DE ATENCIÓN
# 📋 SEDE PARA HOY
# 🎄 FERIADOS PRÓXIMOS
```

### Riesgo de modificación

```
ALTO. Si se quita la regla de "preguntar OS primero", la IA vuelve a
ofrecer slots sin cobertura, rompiendo el flujo. Esto fue exactamente
el bug de la línea 10927 (INMEDIATO) que ya corregimos.
```

## IV.B — PROACTIVIDAD (~línea 11005)

### Ubicación

```
main.py ~línea 11005
```

### Contenido

```
PROACTIVIDAD (LO MÁS IMPORTANTE):
Sos AGENTE DE VENTAS. Cada mensaje tuyo: ejecutar tool O hacer 1 pregunta. Nada más.
• Paciente dice tratamiento → PREGUNTAR obra social PRIMERO antes de check_availability.
• Paciente dice "buscame fecha" → EJECUTAR, no preguntar.
• Paciente dice "cualquiera" → elegí próximo día hábil y ejecutá.
• PROHIBIDO: "te gustaría agendar?", "estoy aquí para ayudarte!", 2+ preguntas sin tool.
• PROHIBIDO preguntar "¿Querés que te busque turno?" — si pidió turno, BUSCÁ.
• Obras sociales: SIEMPRE check_insurance_coverage.
• Disponibilidad y Cobertura: Ver REGLAS PRIMORDIALES.
• PROHIBIDO cierre duro. Usá cierre consultivo.
```

### Interacción con backend

- Determina CUÁNDO se llaman las tools
- Si la IA sigue estas reglas, el flujo es correcto
- Si las ignora → da vueltas, no agenda, deriva

### Riesgo de modificación

```
MUY ALTO. Es el bloque que más impacto tiene en el comportamiento.
Si se vuelve a poner "check_availability INMEDIATO" (como estaba antes),
el flujo se rompe. Cualquier cambio acá debe ser cuidadoso.
```

## IV.C — ANTI-CONFIRMACIÓN-FALSA (~línea 10296)

### Ubicación

```
main.py ~línea 10296
```

### Contenido

(ya detallado en I.E — ver arriba)

### Riesgo de modificación

```
ALTO. Sin esta sección, la IA podría decir "turno confirmado" después
de check_availability, generando falsas expectativas en el paciente.
```

## IV.D — RE-INTENTO INTELIGENTE (~línea 11682)

### Ubicación

```
main.py ~línea 11682 (en las descripciones de tool, cerca del final del prompt)
```

### Contenido

(ya detallado en I.E — ver arriba)

### Interacción con backend

```python
# Lee BOOK_ERROR:CODE del resultado de book_appointment
# Determina si re-checkear disponibilidad o pedir datos faltantes
# Después de 3 intentos → derivhumano
```

### Riesgo de modificación

```
MEDIO. Si se quita, la IA podría quedarse en loop infinito llamando
book_appointment, o derivar en el primer error sin intentar de nuevo.
```

## IV.E — REGLAS DE AGENDAMIENTO PARA TERCEROS (~línea 10274)

### Ubicación

```
main.py ~línea 10274
```

### Contenido

(ya detallado en II.C — ver arriba)

### Riesgo de modificación

```
MEDIO-ALTO. Sin estas reglas, la IA no sabe cómo manejar "es para mi mamá".
Deriva a humano en vez de agendar al tercero.
```

## IV.F — CONTEXTO DEL PACIENTE (~línea 10194)

### Ubicación

```
main.py ~línea 10194
```

### Contenido

(ya detallado en II.A — ver arriba)

### Interacción con backend

```python
# Se inyecta dinámicamente desde buffer_task con datos REALES de DB:
# SELECT * FROM patients WHERE id = current_patient_id
# SELECT * FROM appointments WHERE patient_id = X ORDER BY date DESC
```

### Riesgo de modificación

```
BAJO-MEDIO. Es mayormente informativo. Si se quita, la IA pierde
contexto valioso pero el flujo de booking sigue funcionando.
```

## IV.G — REGLA SUPREMA DE TOOLS (~línea 10289)

### Ubicación

```
main.py ~línea 10289
```

### Contenido

```
REGLA SUPREMA DE HERRAMIENTAS (TOOLS) — LEER 3 VECES:
• Cuando una herramienta (tool) retorna un resultado, ESE ES EL RESULTADO REAL.
  No lo contradigas.
• Si una tool retorna "✅ ..." → la acción FUE EXITOSA. Confirmá al paciente.
• Si una tool retorna "⚠️ ..." o "❌ ..." → la acción FALLÓ. Informá el error.
• NUNCA digas "hubo un error" si la tool retornó éxito.
• NUNCA inventes respuestas sobre acciones que NO ejecutaste.
```

### Riesgo de modificación

```
ALTO. Sin esta regla, la IA podría ignorar resultados de tools
y alucinar respuestas.
```

## IV.H — MÁQUINA DE ESTADOS DEL BOOKING (specialists.py ~línea 301)

### Ubicación

```
agents/specialists.py ~línea 301
```

### Contenido

```
# MÁQUINA DE ESTADOS DEL BOOKING (REGLA DURA)
Estado 1 → OFRECER: llamás check_availability UNA SOLA VEZ
Estado 2 → ELEGIR: el paciente selecciona un horario
Estado 3 → DATOS: pedís nombre + apellido + DNI
Estado 4 → RESERVAR (confirm_slot): reservás temporalmente
Estado 5 → AGENDAR (book_appointment): guardás definitivamente
```

### Interacción con backend

- Es la guía de FLUJO para el BookingAgent
- Si se respeta → nunca hay loops ni errores de secuencia
- Garantiza que confirm_slot se llame antes de book_appointment

---

# Parte V — Referencia Rápida de Base de Datos

## Tablas que el Agente Toca

### `tenants`

| Columna | Tipo | Propósito | Tool que la usa |
|---------|------|-----------|-----------------|
| `id` | SERIAL PK | Identificador único de clínica | TODAS (filtro tenant_id) |
| `config` | JSONB | Configuración: min_date, calendar_provider, ui_language | buffer_task, check_availability, book_appointment |
| `clinic_name` | VARCHAR | Nombre de la clínica | build_nova_system_prompt (saludo) |

### `patients`

| Columna | Tipo | Propósito | Tool que la usa |
|---------|------|-----------|-----------------|
| `id` | SERIAL PK | ID único del paciente | TODAS (vía get_patient_id_by_context) |
| `tenant_id` | INT FK | Clínica a la que pertenece | TODAS |
| `first_name` | VARCHAR | Nombre | book_appointment, lead_context |
| `last_name` | VARCHAR | Apellido | book_appointment, lead_context |
| `phone_number` | VARCHAR | Teléfono | find_patient, get_patient_id_by_context, book_appointment |
| `dni` | VARCHAR | DNI | find_patient, book_appointment |
| `birth_date` | DATE | Fecha de nacimiento | book_appointment |
| `email` | VARCHAR | Email | save_patient_email |
| `human_override_until` | TIMESTAMP | Bloqueo por derivación a humano | derivhumano |
| `status` | VARCHAR | Estado del paciente | buffer_task |

### `appointments`

| Columna | Tipo | Propósito | Tool que la usa |
|---------|------|-----------|-----------------|
| `id` | SERIAL PK | ID del turno | book_appointment, cancel_appointment, reschedule_appointment |
| `tenant_id` | INT FK | Clínica | TODAS |
| `patient_id` | INT FK | Paciente | TODAS |
| `professional_id` | INT FK | Profesional | check_availability, book_appointment |
| `treatment_type_id` | INT FK | Tratamiento | check_availability, book_appointment |
| `appointment_date` | DATE | Fecha del turno | check_availability, book_appointment |
| `appointment_time` | TIME | Hora del turno | check_availability, book_appointment |
| `status` | VARCHAR | confirmed/cancelled | cancel_appointment, list_my_appointments |
| `is_minor` | BOOLEAN | Es menor de edad | book_appointment |
| `lock_source` | VARCHAR | Cómo se lockeó (redis/db_fallback) | book_appointment |

### `chat_conversations`

| Columna | Tipo | Propósito | Tool que la usa |
|---------|------|-----------|-----------------|
| `id` | SERIAL PK | ID de la conversación | book_appointment (auto-link) |
| `tenant_id` | INT FK | Clínica | buffer_task, admin_routes |
| `phone_number` | VARCHAR | Teléfono del chat | buffer_task, admin_routes |
| `linked_patient_id` | INT FK | Paciente vinculado (puede ser distinto del que escribe) | buffer_task, admin_routes, book_appointment |
| `human_override_until` | TIMESTAMP | Bloqueo por derivación | derivhumano |

### `professionals`

| Columna | Tipo | Propósito | Tool que la usa |
|---------|------|-----------|-----------------|
| `id` | SERIAL PK | ID del profesional | check_availability, book_appointment |
| `tenant_id` | INT FK | Clínica | TODAS |
| `first_name` | VARCHAR | Nombre | check_availability, list_professionals |
| `last_name` | VARCHAR | Apellido | check_availability, list_professionals |
| `is_active` | BOOLEAN | Está activo | check_availability |

### `treatment_types`

| Columna | Tipo | Propósito | Tool que la usa |
|---------|------|-----------|-----------------|
| `id` | SERIAL PK | ID del tratamiento | resolve_canonical_treatment, book_appointment |
| `name` | VARCHAR | Nombre canónico | check_availability, list_services |
| `is_active` | BOOLEAN | Está activo | check_availability |
| `is_available_for_booking` | BOOLEAN | Se puede reservar online | check_availability |
| `duration_minutes` | INT | Duración del turno | check_availability (generación de slots) |

### `insurance_config`

| Columna | Tipo | Propósito | Tool que la usa |
|---------|------|-----------|-----------------|
| `id` | SERIAL PK | ID | — |
| `tenant_id` | INT FK | Clínica | check_insurance_coverage |
| `insurance_provider` | VARCHAR | Nombre de la OS | check_insurance_coverage |
| `waiting_days` | INT | Días de espera | check_insurance_coverage, check_availability, book_appointment |
| `is_active` | BOOLEAN | Activa | check_insurance_coverage |

### `feriados`

| Columna | Tipo | Propósito | Tool que la usa |
|---------|------|-----------|-----------------|
| `id` | SERIAL PK | ID | — |
| `tenant_id` | INT FK | Clínica | check_availability |
| `date` | DATE | Fecha del feriado | check_availability |
| `type` | VARCHAR | CERRADO o ESPECIAL | check_availability |
| `description` | VARCHAR | Descripción | check_availability |

### `tenant_working_hours`

| Columna | Tipo | Propósito | Tool que la usa |
|---------|------|-----------|-----------------|
| `id` | SERIAL PK | ID | — |
| `tenant_id` | INT FK | Clínica | check_availability |
| `day_of_week` | INT | 0=Domingo...6=Sábado | check_availability |
| `open_time` | TIME | Hora de apertura | check_availability |
| `close_time` | TIME | Hora de cierre | check_availability |
| `is_active` | BOOLEAN | Activo | check_availability |

---

# Parte VI — Referencia Rápida de Redis

## Todos los Keys

### `slot_offer:{tenant_id}:{phone}`

```
Propósito: Guardar los slots que check_availability ofreció.
           Permite que confirm_slot y book_appointment resuelvan
           exactamente el slot que el paciente eligió.
Valor:    JSON array de objetos:
          [{"date": "2026-06-16", "time": "11:30",
            "professional": "Dr. García", "treatment": "Consulta"},
           {"date": "2026-06-16", "time": "14:00", ...}]
TTL:      300 segundos (5 minutos)
Operación: SET (check_availability), GET (confirm_slot, book_appointment)
```

### `slot_lock:{tenant_id}:{prof_id}:{date}:{time}`

```
Propósito: Lock temporal de un slot. Garantiza que nadie más tome
           el mismo slot mientras el paciente confirma.
Valor:    phone del paciente que reserva (string)
TTL:      600 segundos (10 minutos)
Operación: SET NX (confirm_slot), GET (confirm_slot, book_appointment),
           EXPIRE (refrescar TTL)
```

### `booking_attempts:{tenant_id}:{phone}`

```
Propósito: Contador de intentos de book_appointment por conversación.
           Anti-loop: después de 3 intentos, se bloquea.
Valor:    integer (contador)
TTL:      Persistente (se crea en el primer intento, se incrementa)
Operación: INCR (book_appointment), GET (book_appointment)
Reset:    Se resetea cuando hay un book_appointment exitoso
          (o cuando se cancela la conversación)
```

### `conv_state:{tenant_id}:{phone}`

```
Propósito: Estado general de la conversación. Hash con múltiples campos.
Valor:    Hash con campos: state, last_booked_appointment_id,
          booking_attempts, offered_treatment, anchor_date,
          last_derivhumano_at, human_override_until
TTL:      Persistente mientras la conversación está activa
Operación: HSET, HGET, HGETALL, HDEL
```

### `lead_ctx:{tenant_id}:{phone}`

```
Propósito: Datos acumulados del lead durante la conversación.
Valor:    Hash con campos: first_name, last_name, dni, email,
          insurance_provider, insurance_days, treatment_name,
          professional_name, minor_first_name, minor_last_name,
          booking_type, date_query, interpreted_date, search_mode,
          first_seen_at, last_updated_at
TTL:      86400 segundos (24 horas) — se resetea en cada HSET
Operación: HSET (merge), HGETALL (get), DEL (clear)
```

---

# Apéndice: Diagramas de Flujo

## Flujo de Booking Correcto

```
┌──────────────┐
│ Lead dice    │
│ tratamiento  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ ¿Tiene OS?   │◄──── check_insurance_coverage
│ (IA pregunta)│      (guarda en lead_context)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ check_avail- │──── min_date + OS_days = effective_min
│ ability      │──── slots filtrados → Redis slot_offer
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Lead elige   │
│ slot (1, 2…) │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ ¿Faltan      │
│ datos?       │──── Si: pedir nombre/DNI
│ (nombre,DNI) │──── No: seguir
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ confirm_slot │──── Redis lock (10 min)
│ (slot_index) │──── conv_state = BOOKING
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ book_appoint- │──── INSERT appointments
│ ment          │──── lead_ctx_clear
│               │──── conv_state = BOOKED/PAYMENT_PENDING
│               │──── auto-link (si tercero)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ ✅ Turno     │
│ confirmado   │
└──────────────┘
```

## Flujo de Resolución de Paciente

```
Mensaje entrante
       │
       ▼
┌──────────────────────┐
│ 1. linked_patient_id │──── chat_conversations
│    existe?           │
└──────┬───────┬───────┘
       │ SÍ    │ NO
       │       ▼
       │    ┌──────────────────────┐
       │    │ 2. Buscar paciente   │
       │    │    por phone del     │
       │    │    chat              │
       │    └──────┬───────┬───────┘
       │           │ SÍ    │ NO
       │           │       ▼
       │           │    ┌──────────────────┐
       │           │    │ 3. None (no hay  │
       │           │    │    paciente)     │
       │           │    └──────────────────┘
       ▼           ▼
┌──────────────────────────┐
│ current_patient_id set   │
│ Inyectar contexto en     │
│ el prompt:               │
│ • CONTEXTO DEL PACIENTE  │
│ • [CONTEXTO DE LEAD]     │
│ • linked_patient_name    │
│ • linked/desvinculado    │
└──────────────────────────┘
```

---

> Fin del documento.
>
> Este archivo es una base para entender, mantener y evolucionar el agente IA.
> Creado: 2026-06-09 — Última actualización: 2026-06-09
