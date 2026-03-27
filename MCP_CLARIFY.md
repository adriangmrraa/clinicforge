# MCP Server — Clarify Document

## Por que MCP

### Problema actual: 47 tools = caos controlado

Nova tiene 47 tools definidas en `nova_tools.py` (2787 lineas). Cada tool se envía como schema JSON a OpenAI Realtime API. Esto genera:

1. **Explosion de tokens de contexto**: Los 47 schemas se envían en cada sesión, ocupando ~4000 tokens antes de que el usuario diga una palabra.
2. **Redundancia masiva**: Hay tools específicas (`buscar_paciente`, `ver_paciente`, `actualizar_paciente`) que hacen lo mismo que las CRUD genéricas (`obtener_registros`, `actualizar_registro`). El modelo no sabe cuál usar.
3. **El modelo se pierde**: Con 47 opciones, OpenAI Realtime a veces elige la tool incorrecta o no elige ninguna. Ya tuviste el bug de que ignoraba todas cuando eran 43 (commit `9f29cdf`).
4. **Imposible de testear**: No hay tests. No hay forma de saber si las 47 tools funcionan sin probarlas una por una manualmente por voz.
5. **Acoplamiento a OpenAI**: Las tools están en formato OpenAI function calling. Si querés usar Claude, Gemini, o cualquier otro modelo, tenés que reescribir todo.

### Solución: MCP como capa universal

```
                                MCP Server (Python, asyncpg)
                                    |
                +-------------------+-------------------+
                |                   |                   |
          Claude Code          Nova Bridge          Cursor / IDE
          (stdio)              (SSE/HTTP)           (stdio)
                                    |
                            OpenAI Realtime
                            (solo 6-8 tools)
```

**El MCP server absorbe TODA la lógica de negocio.** Nova pasa de 47 tools a ~6-8 tools genéricas que llaman al MCP internamente. Cualquier otro cliente MCP (Claude Code, Cursor) obtiene acceso completo sin código extra.

---

## Auditoría de las 47 Tools Actuales

### Mapa completo: Tool → Destino MCP

| # | Tool actual | Tipo | Destino MCP | Estado | Notas |
|---|------------|------|-------------|--------|-------|
| **A. Pacientes (7)** |
| 1 | `buscar_paciente` | READ | Resource `clinicforge://patients?search={q}` | OK | Funciona bien |
| 2 | `ver_paciente` | READ | Resource `clinicforge://patients/{id}` | OK | Incluye próximos turnos |
| 3 | `registrar_paciente` | WRITE | Tool `create_record(patients, ...)` | OK | Verifica duplicados |
| 4 | `actualizar_paciente` | WRITE | Tool `update_record(patients, ...)` | OK | Solo 6 campos permitidos |
| 5 | `historial_clinico` | READ | Resource `clinicforge://clinical/{patient_id}` | OK | Solo ceo/professional |
| 6 | `registrar_nota_clinica` | WRITE | Tool `create_record(clinical_records, ...)` | OK | Solo professional. Incluye odontograma |
| 7 | `eliminar_paciente` | WRITE | Tool `update_record(patients, status=archived)` | OK | Soft delete, solo CEO |
| **B. Turnos (9)** |
| 8 | `ver_agenda` | READ | Resource `clinicforge://appointments?date={d}` | OK | Auto-filtra por profesional |
| 9 | `proximo_paciente` | READ | Resource `clinicforge://appointments/next` | OK | Solo para profesionales |
| 10 | `verificar_disponibilidad` | READ | Resource `clinicforge://availability?date={d}&treatment={t}` | **BUG** | `target_date` es string, usa `datetime.strptime(target_date, "%Y-%m-%d")` en línea 1083, pero `target_date` ya es un `date` object del `_parse_date_str()`. Crashea silenciosamente y retorna `date.today()` |
| 11 | `agendar_turno` | WRITE | Tool `book_appointment(...)` | OK | No verifica conflictos de horario |
| 12 | `cancelar_turno` | WRITE | Tool `cancel_appointment(...)` | OK | |
| 13 | `confirmar_turnos` | WRITE | Tool `confirm_appointments(...)` | OK | Bulk o individual |
| 14 | `reprogramar_turno` | WRITE | Tool `reschedule_appointment(...)` | **BUG** | `apt_id` se pasa como string pero `appointments.id` es UUID. No hace `uuid.UUID(apt_id)`. Crash en asyncpg |
| 15 | `bloquear_agenda` | WRITE | Tool `create_record(google_calendar_blocks, ...)` | **BUG** | `start` y `end` se pasan como strings pero la columna espera timestamp. No convierte |
| 16 | `cambiar_estado_turno` | WRITE | Tool `update_record(appointments, ...)` | **BUG** | Mismo problema: `apt_id` string vs UUID |
| **C. Facturación (3)** |
| 17 | `listar_tratamientos` | READ | Resource `clinicforge://treatments` | OK | |
| 18 | `registrar_pago` | WRITE | Tool `register_payment(...)` | OK | Crea accounting_transaction |
| 19 | `facturacion_pendiente` | READ | Resource `clinicforge://billing/pending` | OK | |
| **D. Analytics (5)** |
| 20 | `resumen_semana` | READ | Resource `clinicforge://analytics/summary?period=week` | OK | Solo CEO |
| 21 | `rendimiento_profesional` | READ | Resource `clinicforge://analytics/professional/{id}` | OK | Solo CEO |
| 22 | `ver_estadisticas` | READ | Resource `clinicforge://analytics/summary?period={p}` | OK | Duplica funcionalidad con `resumen_semana` |
| 23 | `resumen_marketing` | READ | Resource `clinicforge://marketing/roi?period={p}` | OK | Solo CEO, depende de `meta_ad_insights` |
| 24 | `resumen_financiero` | READ | Resource `clinicforge://analytics/revenue?period={p}` | OK | Solo CEO |
| **E. Navegación (2)** |
| 25 | `ir_a_pagina` | ACTION | Tool `navigate(page)` | OK | Retorna JSON, no texto |
| 26 | `ir_a_paciente` | ACTION | Tool `navigate(patient, id)` | OK | |
| **F. Multi-sede (4)** |
| 27 | `resumen_sedes` | READ | Resource `clinicforge://sedes/summary` | OK | N+1 queries (1 por sede) |
| 28 | `comparar_sedes` | READ | Resource `clinicforge://sedes/compare?metric={m}` | OK | |
| 29 | `switch_sede` | ACTION | Tool `switch_context(tenant_id)` | OK | Retorna JSON |
| 30 | `onboarding_status` | READ | Resource `clinicforge://config/onboarding` | OK | 8 queries secuenciales, podría ser 1 |
| **G. Staff (10)** |
| 31 | `listar_profesionales` | READ | Resource `clinicforge://professionals` | OK | |
| 32 | `ver_configuracion` | READ | Resource `clinicforge://config/clinic` | **BUG** | Usa `row.get()` pero asyncpg `Record` no tiene `.get()`. Funciona por los campos que sí existen, pero `working_hours_start` / `working_hours_end` probablemente no existen como columnas (se usa `working_hours` JSONB) |
| 33 | `actualizar_configuracion` | WRITE | Tool `update_record(tenants, ...)` | **BUG** | Mismos campos inexistentes: `working_hours_start`, `working_hours_end` |
| 34 | `crear_tratamiento` | WRITE | Tool `create_record(treatment_types, ...)` | OK | Solo CEO |
| 35 | `editar_tratamiento` | WRITE | Tool `update_record(treatment_types, ...)` | OK | Solo CEO |
| 36 | `ver_chats_recientes` | READ | Resource `clinicforge://conversations/recent` | OK | |
| 37 | `enviar_mensaje` | WRITE | Tool `send_message(...)` | OK | Usa YCloud |
| 38 | `ver_faqs` | READ | Resource `clinicforge://config/faqs` | OK | |
| 39 | `eliminar_faq` | WRITE | Tool `delete_record(clinic_faqs, ...)` | OK | Hard delete, debería ser soft |
| 40 | `actualizar_faq` | WRITE | Tool `update_record(clinic_faqs, ...)` | OK | Usa ILIKE para match |
| **H. Anamnesis (2)** |
| 41 | `guardar_anamnesis` | WRITE | Tool `save_anamnesis(...)` | OK | Merge con existente |
| 42 | `ver_anamnesis` | READ | Resource `clinicforge://clinical/anamnesis/{patient_id}` | OK | |
| **I. Datos avanzados (1)** |
| 43 | `consultar_datos` | READ | **ELIMINAR** | OK pero redundante | Usa keyword matching en vez de query real. Las CRUD tools + resources hacen lo mismo mejor |
| **J. CRUD genérico (4)** |
| 44 | `obtener_registros` | READ | Resource `clinicforge://{tabla}?filtros` | **RIESGO** | Construye SQL dinámico. Sanitiza campo pero no valor. Filter injection posible |
| 45 | `actualizar_registro` | WRITE | Tool `update_record(tabla, id, campos)` | OK | |
| 46 | `crear_registro` | WRITE | Tool `create_record(tabla, datos)` | OK | |
| 47 | `contar_registros` | READ | Resource via count | **RIESGO** | Mismo problema de SQL dinámico |

---

## Bugs Encontrados

### 1. `verificar_disponibilidad` — doble parseo de fecha (línea 1083)
```python
target_date = _parse_date_str(args.get("date", str(_today())))  # Returns date object
# ...
dt = datetime.strptime(target_date, "%Y-%m-%d").date()  # BUG: strptime on date object
```
`_parse_date_str()` retorna un `date` object, pero después `datetime.strptime(target_date, "%Y-%m-%d")` espera un string. Python convierte `date` a string vía `str()` que da `YYYY-MM-DD`, así que funciona por accidente. Pero es frágil.

### 2. `reprogramar_turno` — UUID no parseado (línea 2039)
```python
await db.pool.execute(
    "UPDATE appointments SET appointment_datetime = $1 ... WHERE id = $2",
    new_dt, apt_id, tenant_id,  # apt_id es string, appointments.id es UUID
)
```
asyncpg va a tirar `DataError: invalid input for query argument $2: '...' (expected UUID)`.

### 3. `bloquear_agenda` — timestamps como strings (línea 2187)
```python
await db.pool.execute(
    "INSERT INTO google_calendar_blocks ... VALUES ($1, $2, $3, $4, $5, 'manual', NOW())",
    tenant_id, prof_id, start, end, reason,  # start/end son strings
)
```
Si `start_time`/`end_time` son `timestamp` en la DB, asyncpg crashea.

### 4. `cambiar_estado_turno` — UUID no parseado (línea 2231)
Mismo bug que `reprogramar_turno`.

### 5. `ver_configuracion` — campos inexistentes (línea 2051)
```python
for field in ["working_hours_start", "working_hours_end", ...]:
    val = row.get(field)  # asyncpg Record no tiene .get()
```
asyncpg `Record` sí tiene `__getitem__` y `.get()` en versiones recientes, pero `working_hours_start` y `working_hours_end` probablemente no existen como columnas (la DB usa `working_hours` JSONB).

### 6. SQL Injection en CRUD genérico (líneas 2589, 2612)
```python
select_fields = campos if campos else "*"  # campos viene directo del modelo
query = f"SELECT {select_fields} FROM {tabla} WHERE tenant_id = $1"
```
Si el modelo pasa `campos = "1; DROP TABLE patients; --"` se ejecuta. La tabla está whitelisteada pero los campos no.

---

## Arquitectura MCP Propuesta (Refinada)

### Estructura final

```
clinicforge/
  mcp_server/
    __init__.py
    server.py              # Entry point — register resources + tools + prompts
    db.py                  # Pool asyncpg (compartido con orchestrator via DSN)
    auth.py                # Tenant resolution + role validation
    resources/
      __init__.py
      patients.py          # patients, patients/{id}, patients?search=
      appointments.py      # appointments/today, /week, /{id}, ?date=, /next
      professionals.py     # professionals, /{id}, /{id}/availability
      treatments.py        # treatments, /{code}
      clinical.py          # clinical/anamnesis/{pid}, /records/{pid}, /documents/{pid}
      analytics.py         # analytics/summary, /professional/{id}, /revenue
      marketing.py         # marketing/roi, /leads, /campaigns
      conversations.py     # conversations/recent, /{phone}, /{phone}/messages
      config.py            # config/clinic, /working-hours, /bank, /onboarding, /faqs
      sedes.py             # sedes/summary, /compare
      billing.py           # billing/pending
    tools/
      __init__.py
      records.py           # create_record, update_record, delete_record (CRUD unificado)
      booking.py           # book_appointment, cancel, reschedule, confirm, block_schedule
      billing.py           # register_payment
      messaging.py         # send_whatsapp
      anamnesis.py         # save_anamnesis (merge logic)
      navigation.py        # navigate (frontend routing)
      context.py           # switch_sede
    prompts/
      __init__.py
      nova_ceo.py          # System prompt + day summary
      nova_professional.py # Professional-scoped prompt
      nova_anamnesis.py    # Patient-facing anamnesis prompt
```

### De 47 tools a 13 tools MCP

| MCP Tool | Absorbe | Descripción |
|----------|---------|-------------|
| `create_record` | registrar_paciente, agendar_turno, registrar_nota_clinica, crear_tratamiento, crear_registro | CRUD create genérico |
| `update_record` | actualizar_paciente, actualizar_configuracion, editar_tratamiento, actualizar_faq, actualizar_registro, cambiar_estado_turno | CRUD update genérico |
| `delete_record` | eliminar_paciente, eliminar_faq | Soft/hard delete |
| `book_appointment` | agendar_turno, verificar_disponibilidad | Flujo completo: check availability → confirm slot → book |
| `cancel_appointment` | cancelar_turno | Con reason |
| `reschedule_appointment` | reprogramar_turno | Change datetime |
| `confirm_appointments` | confirmar_turnos | Bulk o individual |
| `block_schedule` | bloquear_agenda | Bloqueo de horario |
| `register_payment` | registrar_pago | Pago + accounting_transaction |
| `send_message` | enviar_mensaje | WhatsApp via YCloud |
| `save_anamnesis` | guardar_anamnesis | Merge con medical_history existente |
| `navigate` | ir_a_pagina, ir_a_paciente | Retorna JSON para frontend |
| `switch_sede` | switch_sede | Cambia contexto de tenant |

### De 47 tools a 20 resources MCP

Los resources reemplazan TODAS las tools de lectura:

| Resource URI | Absorbe |
|-------------|---------|
| `clinicforge://patients?search={q}` | buscar_paciente |
| `clinicforge://patients/{id}` | ver_paciente |
| `clinicforge://patients/{id}/history` | historial_clinico |
| `clinicforge://appointments?date={d}&professional_id={p}` | ver_agenda |
| `clinicforge://appointments/next?professional_id={p}` | proximo_paciente |
| `clinicforge://appointments/availability?date={d}&treatment={t}` | verificar_disponibilidad |
| `clinicforge://treatments?category={c}` | listar_tratamientos |
| `clinicforge://billing/pending` | facturacion_pendiente |
| `clinicforge://analytics/week` | resumen_semana |
| `clinicforge://analytics/professional/{id}?period={p}` | rendimiento_profesional |
| `clinicforge://analytics/stats?period={p}` | ver_estadisticas |
| `clinicforge://analytics/revenue?period={p}` | resumen_financiero |
| `clinicforge://marketing?period={p}` | resumen_marketing |
| `clinicforge://professionals` | listar_profesionales |
| `clinicforge://config/clinic` | ver_configuracion |
| `clinicforge://config/onboarding` | onboarding_status |
| `clinicforge://config/faqs` | ver_faqs |
| `clinicforge://conversations/recent?limit={n}` | ver_chats_recientes |
| `clinicforge://clinical/anamnesis/{patient_id}` | ver_anamnesis |
| `clinicforge://sedes/summary` | resumen_sedes |
| `clinicforge://sedes/compare?metric={m}&period={p}` | comparar_sedes |
| `clinicforge://{tabla}?filtros` | obtener_registros, contar_registros |

### Tools ELIMINADAS (redundantes)

| Tool | Razón de eliminación |
|------|---------------------|
| `consultar_datos` | Keyword matching genérico. Resources + CRUD lo hacen mejor |
| `obtener_registros` | Reemplazado por resources con URI params |
| `contar_registros` | Reemplazado por resource con `?count=true` |
| `ver_estadisticas` | Duplica `resumen_semana` con otra interfaz |

---

## Bridge Nova ↔ MCP (Cómo se conecta)

OpenAI Realtime API no habla MCP. Se necesita un bridge en el WebSocket handler:

```
Usuario habla  →  OpenAI Realtime  →  function_call("query_data", {resource: "patients?search=juan"})
                                              ↓
                                      Nova Bridge
                                              ↓
                                      MCP Client → MCP Server → asyncpg → PostgreSQL
                                              ↓
                                      Resultado → OpenAI conversation.item.create
                                              ↓
                                      OpenAI habla resultado al usuario
```

**Nova pasa de 47 tools a 3-4 tools puente:**

| Nova Tool (OpenAI) | Qué hace |
|--------------------|----------|
| `query_data` | Lee un resource MCP por URI. Ej: `query_data({uri: "patients/32"})` |
| `execute_action` | Ejecuta un tool MCP. Ej: `execute_action({tool: "book_appointment", args: {...}})` |
| `navigate` | Navegación frontend (se mantiene directo, no pasa por MCP) |
| `switch_context` | Cambia sede (se mantiene directo) |

**Ahorro de tokens**: De ~4000 tokens en schemas a ~400 tokens (4 schemas simples). 10x reducción.

---

## Plan de Testing

### Fase 1: Unit tests para cada tool actual (validar qué funciona HOY)

```python
# tests/test_nova_tools.py
import pytest
from unittest.mock import AsyncMock, patch
from services.nova_tools import execute_nova_tool

@pytest.fixture
def mock_db():
    """Mock asyncpg pool for isolated testing."""
    with patch("services.nova_tools.db") as mock:
        mock.pool = AsyncMock()
        yield mock.pool

# --- A. Pacientes ---
@pytest.mark.asyncio
async def test_buscar_paciente_found(mock_db):
    mock_db.fetch.return_value = [
        {"id": 1, "first_name": "Juan", "last_name": "Perez",
         "phone_number": "+5493704123456", "dni": "12345678",
         "insurance_provider": "OSDE", "insurance_id": "123", "status": "active"}
    ]
    result = await execute_nova_tool("buscar_paciente", {"query": "Juan"}, tenant_id=1, user_role="ceo", user_id="abc")
    assert "Juan Perez" in result
    assert "ID 1" in result

@pytest.mark.asyncio
async def test_buscar_paciente_empty(mock_db):
    mock_db.fetch.return_value = []
    result = await execute_nova_tool("buscar_paciente", {"query": "zzz"}, tenant_id=1, user_role="ceo", user_id="abc")
    assert "No encontre" in result

@pytest.mark.asyncio
async def test_buscar_paciente_no_query(mock_db):
    result = await execute_nova_tool("buscar_paciente", {"query": ""}, tenant_id=1, user_role="ceo", user_id="abc")
    assert "Necesito" in result

# --- B. Turnos ---
@pytest.mark.asyncio
async def test_agendar_turno_missing_fields(mock_db):
    result = await execute_nova_tool("agendar_turno", {"patient_id": 1}, tenant_id=1, user_role="ceo", user_id="abc")
    assert "Necesito" in result

@pytest.mark.asyncio
async def test_cancelar_turno_invalid_uuid(mock_db):
    result = await execute_nova_tool("cancelar_turno", {"appointment_id": "not-a-uuid"}, tenant_id=1, user_role="ceo", user_id="abc")
    assert "invalido" in result

# --- Roles ---
@pytest.mark.asyncio
async def test_resumen_semana_not_ceo(mock_db):
    result = await execute_nova_tool("resumen_semana", {}, tenant_id=1, user_role="professional", user_id="abc")
    assert "permiso" in result

@pytest.mark.asyncio
async def test_registrar_pago_not_allowed(mock_db):
    result = await execute_nova_tool("registrar_pago", {"appointment_id": "x", "amount": 100, "method": "cash"}, tenant_id=1, user_role="professional", user_id="abc")
    assert "permiso" in result

# --- Unknown tool ---
@pytest.mark.asyncio
async def test_unknown_tool(mock_db):
    result = await execute_nova_tool("tool_inexistente", {}, tenant_id=1, user_role="ceo", user_id="abc")
    assert "no reconocida" in result
```

### Fase 2: Integration tests con DB real (docker-compose test)

```bash
# Ejecutar con DB de test
POSTGRES_DSN=postgresql://test:test@localhost:5432/clinicforge_test pytest tests/test_nova_tools_integration.py -v
```

### Fase 3: MCP server tests (usando mcp SDK test client)

```python
# tests/test_mcp_server.py
from mcp.client import ClientSession
from mcp.client.stdio import stdio_client

async def test_read_patients():
    async with stdio_client(["python", "mcp_server/server.py"]) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource("clinicforge://patients?search=juan")
            assert result.contents[0].text  # has data

async def test_book_appointment():
    async with stdio_client(["python", "mcp_server/server.py"]) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("book_appointment", {
                "patient_id": 1,
                "date": "2026-04-01",
                "time": "10:00",
                "treatment_type": "checkup"
            })
            assert "agendado" in result.content[0].text.lower()
```

---

## Seguridad: Lo que el MCP resuelve

| Problema actual | Solución MCP |
|----------------|-------------|
| SQL dinámico en CRUD (`SELECT {campos}`) | Resources con campos hardcoded por tipo |
| `tabla` en whitelist pero `campos` no | Cada resource define sus propios campos |
| `tenant_id` pasado como parámetro | MCP server lo resuelve del contexto de sesión |
| Sin rate limiting | MCP server con rate limiter por tenant |
| Sin audit log | MCP server logea cada request |
| Roles verificados en cada tool | MCP server middleware de roles |

---

## Fases de Implementación (Revisadas)

### Fase 1: MCP Server base + Resources de lectura (~3 días)
- `server.py` con registro de resources
- `db.py` con pool asyncpg
- `auth.py` con tenant/role resolution
- Resources: patients, appointments, professionals, treatments, config
- Transporte: stdio
- **Test**: Conectar desde Claude Code y hacer queries

### Fase 2: Tools de escritura (~2 días)
- `records.py` (CRUD genérico seguro)
- `booking.py` (book + cancel + reschedule + confirm)
- `billing.py` (register_payment)
- `anamnesis.py` (save_anamnesis)
- **Test**: Unit tests + Claude Code integration

### Fase 3: Resources avanzados (~2 días)
- analytics, marketing, sedes, conversations, clinical
- `billing/pending` resource
- Cache Redis por resource (TTL configurable)
- **Test**: Verificar datos con DB real

### Fase 4: Nova Bridge (~2 días)
- Bridge class en `main.py`
- Nova tools reducidas a 3-4 (query_data, execute_action, navigate, switch_context)
- Fallback a tools directas si MCP falla
- **Test**: Sesión de voz end-to-end

### Fase 5: Prompts + Producción (~1 día)
- Prompts MCP (nova_ceo, nova_professional, nova_anamnesis)
- Logging y monitoring
- Deploy como servicio en Docker Compose
- Documentación de configuración

---

## Resumen Ejecutivo

| Métrica | Hoy (47 tools) | Con MCP |
|---------|----------------|---------|
| Tools enviadas a OpenAI | 47 schemas (~4000 tokens) | 3-4 schemas (~400 tokens) |
| Líneas de código tools | 2787 (1 archivo) | ~1500 (modular, 12 archivos) |
| Bugs conocidos | 6 | 0 (se corrigen en MCP) |
| Tests | 0 | ~40 unit + ~15 integration |
| Modelos compatibles | Solo OpenAI Realtime | OpenAI + Claude + Gemini + cualquier MCP client |
| Tiempo para agregar tabla | Editar nova_tools.py + schema + dispatcher | 1 resource file |
| SQL injection risk | Sí (CRUD genérico) | No (campos hardcoded por resource) |

---

## Clarificaciones y Preguntas Abiertas

### 1. Nova no tiene la inteligencia de ventas

**Problema detectado**: Nova agenda turnos sin preguntar tratamiento (asume "consulta" por defecto), no valida que el treatment_type sea un code válido de la DB, y no sigue ningún flujo estructurado. El agente de WhatsApp tiene un flujo de 10 pasos con validación estricta que Nova no tiene.

**Acción tomada**: Se inyectó un flujo de agendamiento obligatorio en el prompt de Nova que:
- SIEMPRE pregunta tratamiento si no se especificó
- SIEMPRE llama `listar_tratamientos` para obtener codes válidos
- Usa el CODE (no el nombre) en `agendar_turno`
- Valida profesional asignado al tratamiento

**Pregunta**: Debería Nova tener acceso al mismo flujo de seña (50% depósito) y post-booking (ficha médica, "cómo nos conociste") que tiene el agente de WhatsApp? O eso es solo para pacientes que llegan por chat?

### 2. book_appointment de Nova vs WhatsApp — son diferentes

**Problema**: El agente de WhatsApp usa `book_appointment` (de main.py, LangChain tool) que:
- Verifica disponibilidad
- Soft-lock con `confirm_slot`
- Calcula seña
- Genera link de anamnesis
- Incluye sede y precio en la confirmación

Nova usa `agendar_turno` (de nova_tools.py) que:
- NO verifica conflictos de horario
- NO hace soft-lock
- NO calcula seña
- NO genera link de anamnesis
- NO incluye sede ni precio

**Pregunta**: Cuando se migre a MCP, debería haber UN SOLO `book_appointment` tool con toda la lógica? O Nova necesita una versión simplificada (porque el CEO ya está dentro del sistema y no necesita seña ni anamnesis)?

### 3. Roles y permisos en MCP

**Estado actual**: Los roles (ceo, professional, secretary) se validan dentro de cada tool function. No hay middleware centralizado.

**Pregunta**: En el MCP server, debería haber un middleware que valide roles antes de ejecutar cualquier tool/resource? Ejemplo: un `professional` no debería poder leer `clinicforge://analytics/revenue` ni ejecutar `update_record(tenants, ...)`.

**Propuesta**: Tabla de permisos:
| Rol | Resources permitidos | Tools permitidos |
|-----|---------------------|------------------|
| ceo | Todos | Todos |
| professional | patients, appointments, clinical, professionals(self), treatments, config/clinic | create_record(clinical_records), update_record(appointments.status), save_anamnesis |
| secretary | patients, appointments, conversations, billing/pending | create_record(patients), register_payment, send_message |

### 4. Transporte: stdio vs SSE vs HTTP

**Para Claude Code / Cursor**: stdio (estándar MCP, ya funciona)
**Para Nova**: Necesita bridge porque OpenAI Realtime no habla MCP

**Pregunta**: El MCP server debería exponer SSE (Server-Sent Events) para que Nova se conecte vía HTTP? O es mejor mantener el bridge como un proceso interno que habla stdio con el MCP?

**Trade-off**:
- SSE: Nova se conecta directo, pero necesita auth HTTP, CORS, etc.
- stdio bridge: Más simple, el bridge vive dentro del orchestrator, pero agrega un proceso hijo.

### 5. Testing — cómo validar las 47 tools hoy

**Problema del usuario**: "No sé si todas las tools funcionan porque son muchas, no sé cómo testearlas"

**Propuesta de testing inmediato** (antes del MCP):

**Tier 1 — Validación de schema** (automatizable):
- Verificar que cada tool en `NOVA_TOOLS_SCHEMA` tiene un handler en `execute_nova_tool`
- Verificar que cada handler existe como función `_nombre_tool`
- Verificar tipos de parámetros (ej: `appointment_id` debería ser UUID, no string libre)

**Tier 2 — Unit tests con mock DB** (ver sección de testing arriba):
- Probar cada tool con inputs válidos e inválidos
- Verificar validación de roles
- Verificar que tools con UUID parsean correctamente (bugs #2, #4)

**Tier 3 — Integration tests con DB real**:
- Docker compose con DB de test
- Seed data: 1 tenant, 2 professionals, 5 patients, 10 appointments
- Ejecutar cada tool y verificar resultado

### 6. Datos que Nova debería conocer del contexto de ventas

El agente de WhatsApp tiene acceso dinámico a:
- `clinic_name`, `working_hours`, `consultation_price`, `bank_cbu/alias/holder_name`
- FAQs del chatbot
- Contexto del paciente (historial, turnos, memories)
- Precios por tratamiento y por profesional
- Sede por día de la semana

**Nova YA tiene** (via tools): tratamientos, profesionales, config, agenda, analytics.

**Nova NO tiene** (y debería tener en el MCP):
- Precio por profesional (`professionals.consultation_price`)
- Asignación tratamiento-profesional (qué profesional puede hacer qué)
- Sede por día de la semana (para informar al agendar)
- FAQs (ya tiene `ver_faqs` pero no las usa proactivamente)

### 7. CRUD genérico — mantener o eliminar en MCP?

**Estado actual**: Las 4 tools CRUD (`obtener_registros`, `actualizar_registro`, `crear_registro`, `contar_registros`) dan acceso directo a toda la DB con SQL dinámico.

**Riesgo**: SQL injection (campos no sanitizados), el modelo puede hacer queries ineficientes o destructivas.

**Propuesta para MCP**:
- ELIMINAR las tools CRUD genéricas
- Reemplazar con resources tipados (cada resource sabe qué campos devolver)
- Para updates: tools específicas con validación de campos por tabla
- Para queries avanzadas: `analyze_data` tool que construye queries seguras internamente

**Pregunta**: Hay algún caso de uso donde el CEO necesite acceso CRUD libre a cualquier tabla que no se cubra con resources + tools específicos?

### 8. Nomenclatura de sources (resuelto)

**Acción tomada**: Se agregó el source `nova` como cuarto tipo de origen de turnos:
- `ai` → "Ventas IA" (turnos agendados por el chatbot de WhatsApp/IG/FB)
- `nova` → "Nova" (turnos agendados por el asistente de voz interno)
- `manual` → "Manual" (turnos creados manualmente por el staff)
- `gcalendar` → "GCal" (bloques sincronizados de Google Calendar)

Color: purple (#a855f7). Badge visible en el modal de edición de turno.
