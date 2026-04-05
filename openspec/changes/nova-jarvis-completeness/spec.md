# Spec: Nova Jarvis Completeness

## S1: Proactive Daily Summary

### Requirements
- Nuevo archivo `orchestrator_service/jobs/nova_morning.py`
- Job diario a las 7:30 AM (configurable por tenant en `system_config` key `NOVA_MORNING_HOUR`)
- Para CADA tenant con bot de Telegram activo:
  1. Leer análisis diario de Redis (`nova_daily:{tenant_id}`) si existe
  2. Si no existe o expiró, generar uno fresco con `nova_daily_analysis`
  3. Consultar: turnos de hoy (count + desglose), turnos sin confirmar, cobros pendientes, presupuestos vencidos
  4. Formatear como HTML atractivo para Telegram
  5. Enviar a todos los usuarios autorizados via `send_proactive_message()`
- Nueva función `send_proactive_message(tenant_id, html_text)` en `telegram_notifier.py`
  - Usa `_bots[tenant_id].bot.send_message()` para cada usuario autorizado
  - `parse_mode=HTML`
  - Fire-and-forget
- Registrar el job en `main.py` startup

### Formato del resumen matutino
```
☀️ <b>Buenos días! Resumen del día</b>

📅 <b>Agenda — {fecha}</b>
▸ {N} turnos programados
▸ {M} sin confirmar ⚠️
▸ Primer turno: {hora} — {paciente}
▸ Último turno: {hora} — {paciente}

💰 <b>Cobros pendientes</b>
▸ {X} turnos sin cobrar (${total})
▸ {Y} presupuestos con saldo pendiente

🦷 <b>Highlights</b>
▸ {insight del análisis diario si existe}

¿Necesitás que confirme los turnos o te prepare algo?
```

### Scenarios
```
DADO que son las 7:30 AM y tenant 1 tiene bot de Telegram activo
CUANDO el job se ejecuta
ENTONCES la doctora recibe el resumen del día en Telegram
Y puede responder directamente (ej: "Sí, confirmá todos")

DADO que no hay turnos hoy
CUANDO el job se ejecuta
ENTONCES envía "No hay turnos programados para hoy. Día libre! 🎉"

DADO que el tenant no tiene bot de Telegram
CUANDO el job se ejecuta para ese tenant
ENTONCES se salta sin error
```

---

## S2: Smart Alerts (Proactive)

### Requirements
- Nuevo archivo `orchestrator_service/jobs/smart_alerts.py`
- Job cada 4 horas (configurable) que evalúa alertas por tenant
- Alertas a evaluar:

| Alerta | Query | Umbral | Frecuencia máx |
|--------|-------|--------|-----------------|
| Turnos sin confirmar mañana | `appointments WHERE status='scheduled' AND date=mañana` | ≥1 | 1x/día (9 PM) |
| No-show detectado | `appointments WHERE status='no-show' AND date=hoy` | ≥1 | inmediato |
| Morosidad alta | `treatment_plans WHERE saldo > $50k AND days_since_last_payment > 30` | ≥1 | 1x/semana |
| Paciente recurrente no-show | `appointments WHERE patient_id=X AND status='no-show' GROUP BY patient_id HAVING count ≥ 3` | ≥3 | 1x |
| Turno próximo (1h) sin confirmar | `appointments WHERE status='scheduled' AND datetime BETWEEN now AND +1h` | ≥1 | 1x/turno |

- Cada alerta se envía via `send_proactive_message(tenant_id, formatted_alert)`
- Redis key `alert_sent:{tenant_id}:{alert_type}:{id}` con TTL para evitar duplicados
- Formato HTML con emoji de severidad: ⚠️ warning, 🔴 crítico, ℹ️ info

### Scenarios
```
DADO que mañana hay 5 turnos scheduled y ninguno confirmed
CUANDO el alert job corre a las 9 PM
ENTONCES envía "⚠️ 5 turnos sin confirmar para mañana. ¿Los confirmo?"
Y la doctora puede responder "Sí, confirmá todos"

DADO que García tiene 3+ no-shows en los últimos 60 días
CUANDO el alert job detecta el patrón
ENTONCES envía "🔴 García tiene 3 inasistencias. ¿Lo contactamos?"
Y marca como alerta enviada (no repetir)
```

---

## S3: Patient Memory — Dedicated Tools

### Requirements
- Agregar 2 tools a NOVA_TOOLS_SCHEMA:

`ver_memorias_paciente`:
- Params: `patient_id` (required)
- Busca por patient_id → obtiene phone → llama `get_memories(pool, phone, tenant_id)`
- Retorna lista formateada de memorias con categoría, importancia, fecha

`agregar_memoria_paciente`:
- Params: `patient_id` (required), `memoria` (required string), `categoria` (enum: salud/preferencia/miedo/familia/logistica/comportamiento/referencia/tratamiento/financiero/personal/general), `importancia` (int 1-10, default 7)
- Busca phone del paciente → llama `add_manual_memory(pool, phone, tenant_id, memoria, categoria)`
- Retorna confirmación

- Hook en `_process_and_respond` de telegram_bot.py: después de cada conversación exitosa, llamar `extract_and_store_memories()` en background (fire-and-forget) con el texto del usuario + respuesta de Nova
- Agregar instrucciones al prompt: "Cuando notés algo importante sobre un paciente que no va en la ficha médica → agregar_memoria_paciente"

### Scenarios
```
DADO que la doctora dice "García siempre llega 15 min tarde, anotalo"
CUANDO Nova procesa el mensaje
ENTONCES llama agregar_memoria_paciente(patient_id=X, memoria="Siempre llega 15 minutos tarde", categoria="comportamiento", importancia=6)
Y confirma "Anotado sobre García: siempre llega 15 min tarde"

DADO que la doctora dice "Preparame para el próximo paciente"
CUANDO Nova busca datos del paciente
ENTONCES también llama ver_memorias_paciente
Y incluye "⚠️ Este paciente es muy ansioso con agujas (memoria guardada 15/03)"
```

---

## S4: Real Page Context in Realtime

### Requirements
- Frontend (`NovaWidget.tsx`): enviar `context_summary` en `POST /admin/nova/session`:
  - En `/pacientes/:id`: incluir patient_id + nombre del paciente
  - En agenda con turno seleccionado: incluir appointment_id + datos del turno
  - Enviar siempre el patient_id si la URL lo contiene
- Backend (`nova_routes.py`): si `appointment_id` viene en el request:
  1. Fetch appointment data (patient, type, datetime, status)
  2. Inyectar como "TURNO SELECCIONADO" en el system prompt
- Backend: si `patient_id` viene (ya parcialmente implementado):
  1. Fetch patient data (ya hecho)
  2. También cargar `patient_memories` del paciente
  3. Inyectar memorias como "MEMORIAS DEL PACIENTE" en el prompt

### Scenarios
```
DADO que la doctora está en /pacientes/31 (Lucas Puig)
CUANDO abre Nova y dice "Cargale caries en la 16"
ENTONCES Nova ya sabe que es Lucas Puig (ID 31) sin buscar
Y ejecuta ver_odontograma(31) → modificar_odontograma(31, ...)

DADO que la doctora tiene seleccionado un turno de las 15:00
CUANDO dice "Cancelá este turno"
ENTONCES Nova ya tiene el appointment_id del turno seleccionado
Y cancela sin preguntar cuál turno
```

---

## S5: Speed Optimization

### Requirements

#### 5.1: OpenAI Client Singleton
- En `telegram_bot.py`: reemplazar `client = openai.AsyncOpenAI(...)` dentro de `_process_with_nova` con un module-level `_openai_client`
- Inicializar lazy: `if _openai_client is None: _openai_client = openai.AsyncOpenAI(...)`

#### 5.2: Tool Filtering por Página
- Nueva función `nova_tools_for_page(page: str) -> List[Dict]` en `nova_tools.py`
- Mapeo de tools por relevancia:

| Página | Tools prioritarias | Excluir |
|--------|-------------------|---------|
| `agenda` | ver_agenda, agendar_turno, cancelar_turno, reprogramar_turno, confirmar_turnos, cambiar_estado_turno, bloquear_agenda, proximo_paciente, buscar_paciente | ir_a_pagina, onboarding_status |
| `telegram` | TODAS (el CEO puede pedir cualquier cosa) | ir_a_pagina, ir_a_paciente, switch_sede |
| `patients` | buscar_paciente, ver_paciente, ver_odontograma, modificar_odontograma, ver_anamnesis, guardar_anamnesis | bloquear_agenda |

- Telegram siempre tiene TODAS las tools excepto las de navegación UI (ir_a_pagina, ir_a_paciente)
- Usar en `_process_with_nova`: `cc_tools = nova_tools_for_page("telegram")` en vez de `nova_tools_for_chat_completions()`

#### 5.3: System Prompt Cache
- Cache `build_nova_system_prompt()` en memoria por `(clinic_name, page, user_role, tenant_id)` con TTL de 5 minutos
- Usar `functools.lru_cache` o dict simple con timestamp
- Invalidar cuando se actualice la config del tenant

### Scenarios
```
DADO que la doctora envía 10 mensajes en 5 minutos por Telegram
CUANDO cada mensaje llama a _process_with_nova
ENTONCES el OpenAI client se reutiliza (no se crea uno nuevo cada vez)
Y el system prompt se lee de cache (no se regenera)
Y se envían ~60 tools en vez de 75 (sin tools de navegación UI)
```

---

## S6: Token Tracking Completo

### Requirements

#### 6.1: Telegram Nova Tracking
- En `telegram_bot.py`, después de CADA `client.chat.completions.create()`:
  ```python
  if response.usage:
      asyncio.create_task(track_service_usage(
          db_pool.pool, tenant_id, model_name,
          response.usage.prompt_tokens, response.usage.completion_tokens,
          source="telegram_nova", phone=""
      ))
  ```
- Hay 2 llamadas en el tool loop + 1 en max rounds fallback = 3 puntos de tracking

#### 6.2: Vision/Whisper Tracking (Telegram media)
- Después de `_transcribe_audio`: tracking con source="telegram_whisper", model="whisper-1"
- Después de `_analyze_image_bytes`: tracking con source="telegram_vision", model="gpt-4o"
- Después de `_analyze_pdf_bytes`: tracking con source="telegram_vision", model="gpt-4o"

#### 6.3: Digital Records Tracking
- En `digital_records_service.py`, `generate_narrative()` hace llamada a OpenAI
- Después de esa llamada: tracking con source="digital_records", model=el modelo usado

#### 6.4: Dashboard Service Breakdown
- Actualizar `get_service_breakdown()` en `token_tracker.py`:
  - `telegram_nova_` → "Nova Telegram"
  - `telegram_whisper_` → "Whisper (Telegram)"
  - `telegram_vision_` → "Vision (Telegram)"
  - `digital_records_` → "Fichas Digitales"

### Scenarios
```
DADO que la doctora envía un audio por Telegram y Nova responde
CUANDO se procesan los tokens
ENTONCES aparecen 2 registros: "Whisper (Telegram)" + "Nova Telegram"
Y ambos suman al total del tenant

DADO que se genera una ficha clínica de un paciente
CUANDO el admin ve métricas
ENTONCES ve "Fichas Digitales" como categoría separada con su costo
```
