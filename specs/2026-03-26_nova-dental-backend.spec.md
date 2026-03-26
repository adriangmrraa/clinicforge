# SPEC: Nova Dental Assistant — Backend (Fase 1)

**Fecha**: 2026-03-26
**Proyecto**: ClinicForge
**Dependencia**: Ninguna (primera fase)

---

## 1. ENDPOINTS REST

### Crear: `orchestrator_service/routes/nova_routes.py`

```python
router = APIRouter(prefix="/admin/nova", tags=["nova"])
```

---

### 1.1 GET `/admin/nova/context`

Retorna contexto de Nova para la pagina actual. Solo SQL, $0.

**Params**: `page` (string), `patient_id` (optional int)

**Multi-sede (CEO only)**:
- Accept optional query param `tenant_id` to get context for a specific sede
- Without `tenant_id`: return CONSOLIDATED context across all sedes
- New response field: `sedes: [{tenant_id, clinic_name, score, top_alert}]` (CEO only)

**Checks estaticos**:

| Check | Query | Tipo |
|-------|-------|------|
| Turnos sin confirmar hoy | `appointments WHERE status='scheduled' AND date=TODAY` | alert |
| Huecos en agenda (>2h libres) | Comparar slots ocupados vs working_hours | suggestion |
| Pacientes sin turno de control (>6 meses) | `patients WHERE last_visit < NOW() - 6 months` | suggestion |
| Recordatorios no enviados | `appointments WHERE reminder_sent=false AND date=TOMORROW` | alert |
| Facturacion pendiente | `appointments WHERE payment_status='pending' AND status='completed'` | warning |
| Turnos cancelados hoy | `appointments WHERE status='cancelled' AND date=TODAY` | info |
| Profesional sin agenda configurada | `professionals WHERE working_hours IS NULL` | warning |
| Pacientes nuevos sin anamnesis | `patients WHERE medical_history IS NULL AND created_at > 7d` | suggestion |
| FAQ sin respuestas | `clinic_faqs WHERE answer IS NULL OR answer = ''` | suggestion |

**Response**:
```json
{
    "page": "agenda",
    "checks": [
        {"type": "alert", "icon": "calendar", "message": "3 turnos sin confirmar para hoy", "action": "confirmar_turnos"},
        {"type": "suggestion", "icon": "clock", "message": "Hay un hueco de 3h en la agenda de manana", "action": "ver_agenda"}
    ],
    "health_score": 78,
    "stats": {
        "appointments_today": 12,
        "appointments_confirmed": 9,
        "patients_total": 234,
        "patients_new_month": 8,
        "pending_payments": 3,
        "cancellations_today": 1
    },
    "sedes": [
        {"tenant_id": 1, "clinic_name": "Sede Cordoba", "score": 82, "top_alert": "2 turnos sin confirmar"},
        {"tenant_id": 2, "clinic_name": "Sede Salta", "score": 65, "top_alert": "Google Calendar no conectado"}
    ],
    "daily_summary": null,
    "greeting": "Hoy tenes 12 turnos, 3 sin confirmar. Queres que te los muestre?"
}
```

**Greeting por pagina**:
- `agenda`: "Hoy tenes {N} turnos. {alerts}"
- `pacientes`: "Tenes {N} pacientes activos. Busco alguno?"
- `chats`: "{N} conversaciones activas. Alguna para revisar?"
- `dashboard`: "{greeting basado en score}"
- `tratamientos`: "Tenes {N} tipos de tratamiento configurados."
- `configuracion`: "Aca podes ajustar la configuracion de la clinica."
- `analytics`: "Queres que te haga un resumen de la semana?"

**Greeting basado en score**:
- score < 50: "La clinica necesita atencion. Lo mas urgente: {top_check}"
- score 50-80: "Va bien! Pero podes mejorar: {top_suggestion}"
- score > 80: "Todo en orden. En que te ayudo?"

---

### 1.2 GET `/admin/nova/health-check`

Health-check completo con score ponderado.

**Score (0-100)**:

| Item | Peso | Criterio |
|------|------|----------|
| Tiene profesionales activos | 10 | `professionals WHERE is_active=true` |
| Profesional tiene horarios | 10 | `working_hours IS NOT NULL` |
| Tiene tipos de tratamiento | 10 | `treatment_types WHERE is_active=true` |
| Tiene pacientes registrados | 10 | `patients COUNT > 0` |
| Turnos recientes (7 dias) | 10 | `appointments WHERE date >= 7d ago` |
| Recordatorios enviados | 10 | `% reminder_sent = true` de turnos de manana |
| Sin facturacion pendiente | 10 | `appointments WHERE payment_status != 'pending'` |
| Google Calendar conectado | 10 | `google_oauth_tokens WHERE tenant_id = X` |
| Canal WhatsApp activo | 10 | `credentials WHERE category='ycloud'` |
| FAQ configuradas | 10 | `clinic_faqs COUNT > 3` |

**Multi-sede (CEO only)**:
- Add `consolidated_score` field: average health score across all sedes
- Add `per_sede` array: `[{tenant_id, clinic_name, score, checks[]}]`
- Staff users: unchanged (single tenant response)

**Response**:
```json
{
    "score": 72,
    "consolidated_score": 68,
    "per_sede": [
        {"tenant_id": 1, "clinic_name": "Sede Cordoba", "score": 82, "checks": []},
        {"tenant_id": 2, "clinic_name": "Sede Salta", "score": 54, "checks": [{"type": "warning", "message": "Google Calendar no conectado"}]}
    ],
    "checks": [
        {"type": "warning", "icon": "calendar", "message": "Google Calendar no conectado", "action": "conectar_gcal", "weight": 10},
        {"type": "suggestion", "icon": "file-text", "message": "Solo tenes 1 FAQ. Agrega mas para que el agente responda mejor", "action": "agregar_faqs", "weight": 10}
    ],
    "completed": [
        "Profesionales activos (3)",
        "Horarios configurados",
        "8 tipos de tratamiento",
        "234 pacientes registrados",
        "WhatsApp conectado"
    ],
    "top_priority": "Google Calendar no conectado",
    "stats": {
        "professionals": 3,
        "treatment_types": 8,
        "patients": 234,
        "appointments_week": 45,
        "pending_payments": 3
    }
}
```

---

### 1.3 POST `/admin/nova/session`

Crea sesion OpenAI Realtime para el widget de voz.

**Body**:
```json
{
    "page": "agenda",
    "context_summary": "12 turnos hoy, 3 sin confirmar. Paciente seleccionado: Maria Lopez (DNI 35.XXX.XXX)",
    "patient_id": 456
}
```

**Flow**:
1. Resolver API key (OPENAI_API_KEY)
2. Construir system prompt con contexto dental + tools + pagina + paciente
3. **Include current sede info in system prompt**
4. **For CEO: include list of sedes they manage in system prompt**
5. Generar session_id (uuid4)
6. Guardar config en Redis (TTL 360s)
7. Retornar session_id

**Response**: `{"session_id": "abc123", "page": "agenda"}`

---

### 1.4 GET `/admin/nova/daily-analysis`

Lee analisis diario de Redis (generado por cron).

**Response**:
```json
{
    "available": true,
    "analysis": {
        "turnos_totales": 45,
        "cancelaciones": 3,
        "nuevos_pacientes": 5,
        "temas_frecuentes": [
            {"tema": "Consultas de precio", "cantidad": 8},
            {"tema": "Disponibilidad urgente", "cantidad": 5},
            {"tema": "Cambios de turno", "cantidad": 4}
        ],
        "problemas": [
            "3 pacientes preguntaron por blanqueamiento y el agente no supo el precio",
            "2 derivaciones innecesarias por consultas de horarios"
        ],
        "sugerencias": [
            {"titulo": "Agregar precios de blanqueamiento", "detalle": "Actualizar FAQ con rango de precios para blanqueamiento ($X - $Y)"},
            {"titulo": "Regla de horarios", "detalle": "Agregar regla de atencion: Lunes a Viernes 9-18hs, Sabados 9-13hs"}
        ],
        "satisfaccion_estimada": 7,
        "resumen": "Semana activa con 45 turnos. 3 cancelaciones (6.6%). Los pacientes consultan mucho por precios que el agente no tiene configurados.",
        "analyzed_at": "2026-03-26T06:00:00Z"
    }
}
```

---

### 1.5 GET `/admin/nova/onboarding-status`

Returns onboarding progress for the current tenant. Checks:

| Field | Check | Source |
|-------|-------|--------|
| `has_professionals` | boolean | `professionals` table has active entries |
| `has_working_hours` | boolean | professionals have `working_hours` configured |
| `has_treatment_types` | boolean | `treatment_types` has active entries |
| `has_whatsapp` | boolean | `credentials WHERE category='ycloud'` |
| `has_google_calendar` | boolean | `google_oauth_tokens` exists |
| `has_faqs` | boolean | `clinic_faqs` count >= 3 |
| `has_bank_details` | boolean | tenant has `bank_cbu` or `bank_alias` |
| `has_consultation_price` | boolean | `tenant.consultation_price` is not null |

**Response**:
```json
{
    "has_professionals": true,
    "has_working_hours": true,
    "has_treatment_types": true,
    "has_whatsapp": false,
    "has_google_calendar": false,
    "has_faqs": false,
    "has_bank_details": true,
    "has_consultation_price": true,
    "completed_steps": 5,
    "total_steps": 8,
    "next_step": "whatsapp",
    "is_complete": false
}
```

---

### 1.6 POST `/admin/nova/onboarding/complete-step`

Validates and saves configuration for a specific onboarding step.

**Body**:
```json
{
    "step": "professionals",
    "data": {}
}
```

**Steps**: `"professionals"`, `"working_hours"`, `"treatment_types"`, `"whatsapp"`, `"google_calendar"`, `"faqs"`, `"bank_details"`, `"consultation_price"`

Each step validates and saves the relevant config. Returns updated onboarding status (same format as `GET /admin/nova/onboarding-status`).

**Response**: Same schema as `GET /admin/nova/onboarding-status` with updated values.

---

## 2. WEBSOCKET HANDLER

### Crear: WebSocket endpoint en `main.py`

**Ruta**: `WS /public/nova/realtime-ws/{session_id}`

**Nota**: Reusar patron de Platform AI Solutions (`onboarding_realtime_ws_inner`), adaptando tools.

### Configuracion OpenAI Realtime

```python
{
    "type": "session.update",
    "session": {
        "instructions": DENTAL_SYSTEM_PROMPT,
        "voice": "coral",
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_transcription": {"model": "whisper-1"},
        "tools": DENTAL_TOOLS,
        "tool_choice": "auto",
        "turn_detection": {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 800,
            "silence_duration_ms": 5000
        }
    }
}
```

### System Prompt de Nova Dental

```
IDIOMA OBLIGATORIO: Espanol argentino. Voseo (vos, sos, tenes). NUNCA cambies de idioma.

Sos Nova, la asistente inteligente de ClinicForge para la clinica "{clinic_name}".
Estas en la pagina: {page}. Rol del usuario: {role}.

PERSONALIDAD:
- Sos proactiva, directa y profesional
- Hablas con confianza pero con calidez
- Usas terminologia dental cuando corresponde
- Sos concisa: maximo 3 oraciones por respuesta
- Cada respuesta termina con una sugerencia o accion concreta

CONTEXTO ACTUAL:
{context_summary}

PACIENTE SELECCIONADO (si aplica):
{patient_context}

PERMISOS DEL ROL:
- CEO: acceso total
- Professional: sus pacientes, sus turnos, registros clinicos
- Secretary: pacientes, turnos, NO registros clinicos detallados

MULTI-SEDE (solo CEO):
- El CEO maneja multiples sedes/clinicas.
- Podes consultar datos consolidados con 'resumen_sedes' y comparar con 'comparar_sedes'.
- Para operar en una sede especifica, usa 'switch_sede' primero.
- Cuando el usuario pregunta por "todas las sedes" o "la clinica" (singular generico), consultar consolidado.
- Cuando pregunta por una sede especifica ("la sede Cordoba", "en Salta"), hacer switch primero.

ONBOARDING:
- Si el usuario es CEO y la sede actual tiene onboarding incompleto, mencionarlo proactivamente.
- "Veo que la sede {nombre} todavia no tiene {paso} configurado. Queres que te ayude?"
- Guiar paso a paso: profesionales -> horarios -> tratamientos -> WhatsApp -> GCal -> FAQs -> banco -> precio consulta.

REGLAS:
- Si el usuario pide algo fuera de su rol, deci "No tenes permiso para eso"
- NUNCA inventes datos de pacientes — siempre usa las tools
- Si no encontras un paciente, deci "No encontre a ese paciente"
- Fechas: usa formato argentino (dd/mm/yyyy)
- Horarios: formato 24h (14:00, no 2pm)
```

---

## 3. TOOLS (Function Calling)

### 24 tools organizadas por categoria

#### A. Pacientes (6 tools)

```python
{
    "name": "buscar_paciente",
    "description": "Busca un paciente por nombre, apellido, DNI o telefono. Retorna datos basicos.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Nombre, apellido, DNI o telefono del paciente"}
        },
        "required": ["query"]
    }
}
# Implementacion: SELECT * FROM patients WHERE
#   first_name ILIKE '%{q}%' OR last_name ILIKE '%{q}%'
#   OR dni ILIKE '%{q}%' OR phone_number ILIKE '%{q}%'
# LIMIT 5

{
    "name": "ver_paciente",
    "description": "Ver ficha completa de un paciente: datos, historial, proximos turnos, obra social.",
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {"type": "integer", "description": "ID del paciente"}
        },
        "required": ["patient_id"]
    }
}

{
    "name": "registrar_paciente",
    "description": "Crea un paciente nuevo con datos basicos.",
    "parameters": {
        "type": "object",
        "properties": {
            "first_name": {"type": "string"},
            "last_name": {"type": "string"},
            "phone_number": {"type": "string"},
            "dni": {"type": "string"},
            "insurance_provider": {"type": "string", "description": "Obra social (OSDE, Swiss Medical, etc.)"},
            "insurance_id": {"type": "string", "description": "Numero de afiliado"}
        },
        "required": ["first_name", "last_name", "phone_number"]
    }
}

{
    "name": "actualizar_paciente",
    "description": "Actualiza datos de un paciente existente.",
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {"type": "integer"},
            "field": {"type": "string", "enum": ["phone_number", "email", "insurance_provider", "insurance_id", "notes", "preferred_schedule"]},
            "value": {"type": "string"}
        },
        "required": ["patient_id", "field", "value"]
    }
}

{
    "name": "historial_clinico",
    "description": "Ver registros clinicos de un paciente: diagnosticos, tratamientos, odontograma. Solo para profesionales.",
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {"type": "integer"}
        },
        "required": ["patient_id"]
    }
}
# CHECK: current_user.role in ('ceo', 'professional')

{
    "name": "registrar_nota_clinica",
    "description": "Agrega nota clinica al registro del paciente. Solo para profesionales.",
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {"type": "integer"},
            "diagnosis": {"type": "string"},
            "treatment_notes": {"type": "string"},
            "tooth_number": {"type": "integer", "description": "Numero de pieza dental (FDI)"},
            "tooth_status": {"type": "string", "enum": ["caries", "restoration", "extraction", "crown", "implant", "root_canal", "treatment_planned"]},
            "surface": {"type": "string", "enum": ["occlusal", "mesial", "distal", "buccal", "lingual"]}
        },
        "required": ["patient_id", "diagnosis"]
    }
}
```

#### B. Turnos (6 tools)

```python
{
    "name": "ver_agenda",
    "description": "Ver turnos de hoy o de una fecha especifica. Muestra horario, paciente, tipo, estado.",
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Fecha en formato YYYY-MM-DD. Default: hoy"},
            "professional_id": {"type": "integer", "description": "ID del profesional. Default: usuario actual"}
        }
    }
}

{
    "name": "proximo_paciente",
    "description": "Retorna el siguiente turno del dia para el profesional actual.",
    "parameters": {"type": "object", "properties": {}}
}
# SELECT * FROM appointments WHERE professional_id = X AND date = TODAY AND status IN ('scheduled','confirmed') AND time > NOW() ORDER BY time LIMIT 1

{
    "name": "verificar_disponibilidad",
    "description": "Verifica si hay disponibilidad para un tipo de tratamiento en una fecha.",
    "parameters": {
        "type": "object",
        "properties": {
            "date": {"type": "string", "description": "Fecha YYYY-MM-DD"},
            "treatment_type": {"type": "string", "description": "Tipo: checkup, cleaning, extraction, root_canal, etc."},
            "professional_id": {"type": "integer", "description": "Profesional especifico (opcional)"}
        },
        "required": ["date"]
    }
}
# Reusa gcal_service.py / check_availability existente

{
    "name": "agendar_turno",
    "description": "Agenda un turno para un paciente.",
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {"type": "integer"},
            "date": {"type": "string", "description": "Fecha YYYY-MM-DD"},
            "time": {"type": "string", "description": "Hora HH:MM (24h)"},
            "treatment_type": {"type": "string"},
            "professional_id": {"type": "integer"},
            "notes": {"type": "string"}
        },
        "required": ["patient_id", "date", "time", "treatment_type"]
    }
}

{
    "name": "cancelar_turno",
    "description": "Cancela un turno existente.",
    "parameters": {
        "type": "object",
        "properties": {
            "appointment_id": {"type": "string", "description": "UUID del turno"},
            "reason": {"type": "string"}
        },
        "required": ["appointment_id"]
    }
}

{
    "name": "confirmar_turnos",
    "description": "Confirma uno o todos los turnos pendientes del dia.",
    "parameters": {
        "type": "object",
        "properties": {
            "appointment_ids": {"type": "array", "items": {"type": "string"}, "description": "Lista de UUIDs. Vacio = confirmar todos los de hoy."}
        }
    }
}
```

#### C. Tratamientos y Facturacion (3 tools)

```python
{
    "name": "listar_tratamientos",
    "description": "Lista tipos de tratamiento disponibles con precios y duracion.",
    "parameters": {
        "type": "object",
        "properties": {
            "category": {"type": "string", "enum": ["prevention", "restorative", "surgical", "orthodontics", "emergency"]}
        }
    }
}

{
    "name": "registrar_pago",
    "description": "Registra pago de un turno completado.",
    "parameters": {
        "type": "object",
        "properties": {
            "appointment_id": {"type": "string"},
            "amount": {"type": "number"},
            "method": {"type": "string", "enum": ["cash", "card", "transfer", "insurance"]},
            "notes": {"type": "string"}
        },
        "required": ["appointment_id", "amount", "method"]
    }
}
# CHECK: current_user.role in ('ceo', 'secretary')

{
    "name": "facturacion_pendiente",
    "description": "Lista turnos completados sin pago.",
    "parameters": {"type": "object", "properties": {}}
}
```

#### D. Analytics y Configuracion (3 tools)

```python
{
    "name": "resumen_semana",
    "description": "Resumen de la semana: turnos, cancelaciones, pacientes nuevos, facturacion.",
    "parameters": {"type": "object", "properties": {}}
}
# CHECK: current_user.role in ('ceo')

{
    "name": "rendimiento_profesional",
    "description": "Metricas de un profesional: turnos completados, tasa cancelacion, retencion pacientes.",
    "parameters": {
        "type": "object",
        "properties": {
            "professional_id": {"type": "integer"},
            "period": {"type": "string", "enum": ["week", "month", "quarter"], "description": "Periodo de analisis"}
        },
        "required": ["professional_id"]
    }
}
# CHECK: current_user.role in ('ceo')

{
    "name": "actualizar_faq",
    "description": "Agrega o actualiza una FAQ de la clinica (usada por el agente de WhatsApp).",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {"type": "string"},
            "answer": {"type": "string"}
        },
        "required": ["question", "answer"]
    }
}
```

#### E. Navegacion (2 tools)

```python
{
    "name": "ir_a_pagina",
    "description": "Navega a una pagina de ClinicForge.",
    "parameters": {
        "type": "object",
        "properties": {
            "page": {"type": "string", "enum": ["agenda", "pacientes", "chats", "tratamientos", "analytics", "configuracion", "marketing", "leads"]}
        },
        "required": ["page"]
    }
}

{
    "name": "ir_a_paciente",
    "description": "Abre la ficha de un paciente especifico.",
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {"type": "integer"}
        },
        "required": ["patient_id"]
    }
}
```

#### F. Multi-sede (4 tools — CEO only)

```python
{
    "name": "resumen_sedes",
    "description": "Resumen consolidado de todas las sedes: turnos, pacientes, facturacion, score por sede. Solo CEO.",
    "parameters": {"type": "object", "properties": {}}
}
# Query: For each tenant in get_allowed_tenant_ids(): count appointments, patients, revenue, calculate health score

{
    "name": "comparar_sedes",
    "description": "Compara metricas entre sedes: cancelaciones, nuevos pacientes, facturacion, ocupacion. Solo CEO.",
    "parameters": {
        "type": "object",
        "properties": {
            "metric": {"type": "string", "enum": ["cancelaciones", "nuevos_pacientes", "facturacion", "ocupacion", "satisfaccion"]},
            "period": {"type": "string", "enum": ["hoy", "semana", "mes"]}
        },
        "required": ["metric"]
    }
}

{
    "name": "switch_sede",
    "description": "Cambia el contexto activo a otra sede. Solo CEO.",
    "parameters": {
        "type": "object",
        "properties": {
            "clinic_name": {"type": "string", "description": "Nombre de la sede (parcial, busca ILIKE)"}
        },
        "required": ["clinic_name"]
    }
}
# Implementation: Search tenants WHERE clinic_name ILIKE '%{name}%', update session context

{
    "name": "onboarding_status",
    "description": "Ver estado de configuracion/onboarding de la sede actual o una sede especifica.",
    "parameters": {
        "type": "object",
        "properties": {
            "clinic_name": {"type": "string", "description": "Nombre de sede (opcional, default: sede actual)"}
        }
    }
}
```

**Multi-sede awareness for existing tools**: All existing tools (`buscar_paciente`, `ver_agenda`, etc.) already work with `tenant_id` isolation. For CEO:
- Tools operate on the CURRENT sede context (set by `switch_sede` or default)
- `resumen_sedes` and `comparar_sedes` work CROSS-sede
- Tool results include sede name when relevant

---

## 4. EVENTOS WS (Client <-> Server)

### Server -> Client

| Evento | Formato | Descripcion |
|--------|---------|-------------|
| Audio bytes | `ArrayBuffer (PCM16)` | Audio de Nova |
| `transcript` | `{type:"transcript", role:"assistant", text:"..."}` | Texto de Nova (streaming) |
| `transcript` | `{type:"transcript", role:"user", text:"..."}` | Transcripcion del usuario |
| `response_done` | `{type:"response_done"}` | Nova termino de responder |
| `nova_audio_done` | `{type:"nova_audio_done"}` | Audio de Nova termino (unmute mic) |
| `user_speech_started` | `{type:"user_speech_started"}` | Usuario empezo a hablar (barge-in) |
| `tool_call` | `{type:"tool_call", name:"...", args:{}, result:{}}` | Tool ejecutada (para UI) |

### Client -> Server

| Evento | Formato | Descripcion |
|--------|---------|-------------|
| Audio bytes | `ArrayBuffer (PCM16 24kHz)` | Mic del usuario |
| Text message | `{type:"text_message", text:"..."}` | Mensaje de texto (chat mode) |

---

## 5. REGISTRAR EN main.py

```python
# En lifespan(), despues de los imports de routers existentes:
from routes.nova_routes import router as nova_router
app.include_router(nova_router)

# WebSocket endpoint
@app.websocket("/public/nova/realtime-ws/{session_id}")
async def nova_realtime_ws(websocket: WebSocket, session_id: str):
    await nova_realtime_ws_handler(websocket, session_id)
```

---

## 6. NGINX PROXY (agregar a nginx.conf del frontend)

```nginx
# Nova Realtime WebSocket
location /api/public/nova/ {
    proxy_pass http://orchestrator:8000/public/nova/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_read_timeout 600s;
}
```

---

## 7. VERIFICACION

1. `GET /admin/nova/context?page=agenda` -> checks + greeting + stats
2. `GET /admin/nova/health-check` -> score + checks ponderados
3. `POST /admin/nova/session` -> session_id valido
4. WS connection -> session.created de OpenAI
5. Enviar audio -> recibir transcripcion + audio respuesta
6. "Quien es mi proximo paciente?" -> tool `proximo_paciente` ejecutada -> respuesta correcta
7. "Agenda turno para Maria Lopez" -> tool `agendar_turno` -> turno creado en DB
8. "Registra caries en pieza 36" -> tool `registrar_nota_clinica` -> registro guardado
9. Profesional no puede ejecutar `resumen_semana` (solo CEO)
10. Secretaria no puede ejecutar `historial_clinico`
11. `GET /admin/nova/onboarding-status` -> returns correct boolean checks and progress
12. `POST /admin/nova/onboarding/complete-step` with `{"step": "faqs", "data": {...}}` -> saves and returns updated status
13. CEO: `GET /admin/nova/context` without `tenant_id` -> consolidated context with `sedes` array
14. CEO: `GET /admin/nova/context?tenant_id=2` -> context scoped to specific sede
15. CEO: `GET /admin/nova/health-check` -> includes `consolidated_score` and `per_sede`
16. CEO: tool `resumen_sedes` -> returns cross-sede summary
17. CEO: tool `comparar_sedes` with `metric=facturacion` -> comparison table across sedes
18. CEO: tool `switch_sede` with `clinic_name=Cordoba` -> switches context, subsequent tools scoped to that sede
19. CEO: tool `onboarding_status` -> returns onboarding for current or named sede
20. Staff user: no access to multi-sede tools (403)
