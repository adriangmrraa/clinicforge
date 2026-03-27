# ClinicForge MCP Server — Spec

## Objetivo

Servidor MCP (Model Context Protocol) que expone TODA la infraestructura de ClinicForge como recursos y herramientas estandarizadas. Permite que Nova (o cualquier LLM compatible) acceda a la data de la clínica de forma fluida, sin necesidad de 47+ tools individuales.

## Arquitectura

```
Nova (OpenAI Realtime)  →  MCP Client (bridge)  →  MCP Server  →  PostgreSQL
                                                        ↕
Claude / Cursor / etc.  →  MCP Client nativo    →  MCP Server  →  Redis / APIs externas
```

El MCP Server corre como proceso independiente (stdio o SSE) y se conecta a la misma DB de ClinicForge.

## Stack Técnico

- **Lenguaje:** Python 3.11+
- **Framework:** `mcp` SDK oficial de Anthropic (`pip install mcp`)
- **DB:** asyncpg (misma conexión que el orchestrator)
- **Transporte:** stdio (para Claude Code / Cursor) + SSE (para Nova bridge via HTTP)
- **Auth:** tenant_id obligatorio en cada request

## Estructura de Archivos

```
clinicforge/
  mcp_server/
    __init__.py
    server.py              # Entry point — MCP server con resources + tools
    db.py                  # Conexión asyncpg (reutiliza config del orchestrator)
    resources/
      __init__.py
      patients.py          # Resource: pacientes
      appointments.py      # Resource: turnos
      professionals.py     # Resource: profesionales
      treatments.py        # Resource: tratamientos
      analytics.py         # Resource: métricas y analytics
      marketing.py         # Resource: Meta Ads, leads, ROI
      conversations.py     # Resource: chats WhatsApp/IG/FB
      clinical.py          # Resource: registros clínicos, anamnesis, documentos
      config.py            # Resource: configuración de la clínica
    tools/
      __init__.py
      crud.py              # Tool: operaciones CRUD genéricas
      booking.py           # Tool: agendamiento inteligente (check + confirm + book)
      billing.py           # Tool: facturación y cobros
      messaging.py         # Tool: envío de WhatsApp/notificaciones
      anamnesis.py         # Tool: ficha médica por voz
    prompts/
      __init__.py
      nova_ceo.py          # Prompt template para CEO
      nova_professional.py # Prompt template para profesional
      nova_anamnesis.py    # Prompt template para paciente (ficha médica)
```

## Resources (Lectura de datos)

Los resources exponen datos como contexto que el LLM puede leer. No ejecutan acciones.

### 1. `clinicforge://patients`
```
URI: clinicforge://patients/{patient_id}
     clinicforge://patients?search={query}
     clinicforge://patients?status=active&limit=20

Devuelve: id, first_name, last_name, phone, dni, email, insurance,
          acquisition_source, medical_history, created_at
```

### 2. `clinicforge://appointments`
```
URI: clinicforge://appointments/today
     clinicforge://appointments/week
     clinicforge://appointments?date=2026-04-15
     clinicforge://appointments?patient_id=32
     clinicforge://appointments?professional_id=2&status=scheduled
     clinicforge://appointments/{appointment_id}

Devuelve: id, patient_name, professional_name, datetime, duration,
          treatment_type, status, payment_status, billing_amount, sede
```

### 3. `clinicforge://professionals`
```
URI: clinicforge://professionals
     clinicforge://professionals/{id}
     clinicforge://professionals/{id}/availability?date=2026-04-15

Devuelve: id, name, specialty, consultation_price, working_hours,
          google_calendar_id, is_active
```

### 4. `clinicforge://treatments`
```
URI: clinicforge://treatments
     clinicforge://treatments/{code}

Devuelve: code, name, duration, base_price, category, complexity,
          assigned_professionals, is_active
```

### 5. `clinicforge://analytics`
```
URI: clinicforge://analytics/summary?period=month
     clinicforge://analytics/professional/{id}?period=week
     clinicforge://analytics/revenue?period=quarter
     clinicforge://analytics/no-shows?period=month
     clinicforge://analytics/retention

Devuelve: métricas calculadas (turnos, completados, cancelaciones,
          no-shows, revenue, retention_rate, avg_ticket, etc.)
```

### 6. `clinicforge://marketing`
```
URI: clinicforge://marketing/roi?period=month
     clinicforge://marketing/leads?status=new
     clinicforge://marketing/campaigns
     clinicforge://marketing/cost-per-lead

Devuelve: inversión Meta Ads, leads por fuente, CPA, conversión, ROI
```

### 7. `clinicforge://conversations`
```
URI: clinicforge://conversations/recent?limit=10
     clinicforge://conversations/{phone}
     clinicforge://conversations/{phone}/messages?limit=20

Devuelve: phone, patient_name, channel (whatsapp/ig/fb), last_message,
          unread_count, status, messages
```

### 8. `clinicforge://clinical`
```
URI: clinicforge://clinical/anamnesis/{patient_id}
     clinicforge://clinical/records/{patient_id}
     clinicforge://clinical/documents/{patient_id}
     clinicforge://clinical/odontogram/{patient_id}

Devuelve: medical_history JSONB, clinical_records, documents list,
          odontogram data
```

### 9. `clinicforge://config`
```
URI: clinicforge://config/clinic
     clinicforge://config/working-hours
     clinicforge://config/bank
     clinicforge://config/integrations

Devuelve: clinic_name, address, working_hours, bank_cbu/alias/holder,
          calendar_provider, max_chairs, consultation_price
```

## Tools (Acciones)

Las tools ejecutan acciones que modifican datos.

### 1. `book_appointment`
```
Acción: Flujo completo de agendamiento
Input: patient_query, date, time, treatment_type, professional_name?
Lógica:
  1. Busca paciente (o crea si es nuevo)
  2. Verifica disponibilidad
  3. Soft-lock (confirm_slot)
  4. Inserta appointment
  5. Calcula seña si aplica
  6. Retorna confirmación con todos los datos
```

### 2. `modify_record`
```
Acción: CRUD genérico sobre cualquier tabla
Input: action (get/create/update/delete), table, filters?, data?, id?
Tables: patients, appointments, professionals, treatment_types, etc.
Seguridad: tenant_id obligatorio, CEO-only para tablas sensibles
```

### 3. `send_message`
```
Acción: Enviar WhatsApp/notificación
Input: patient_query (nombre o phone), message
Lógica: busca paciente → envía vía YCloud
```

### 4. `save_anamnesis`
```
Acción: Guardar ficha médica (merge con existente)
Input: patient_id, campo, valor
Campos: base_diseases, allergies, medication, surgeries, smoker, fears, etc.
```

### 5. `register_payment`
```
Acción: Registrar cobro
Input: appointment_id?, patient_query?, amount, method (cash/card/transfer)
Lógica: busca turno → registra pago → marca como completado
```

### 6. `analyze_data`
```
Acción: Análisis inteligente de datos
Input: question (lenguaje natural)
Lógica: interpreta la pregunta → construye query → ejecuta → resume
Ejemplos: "qué tratamiento genera más ingresos?", "cuál es mi peor día?"
```

## Prompts (Templates de contexto)

### 1. `nova-ceo`
```
Contexto: CEO operando la clínica
Incluye: resumen del día, turnos pendientes, métricas, alertas
Inyecta: datos de config, profesionales activos, tratamientos
```

### 2. `nova-professional`
```
Contexto: Profesional atendiendo pacientes
Incluye: agenda del día, próximo paciente, notas del paciente actual
Inyecta: solo datos del profesional autenticado
```

### 3. `nova-anamnesis`
```
Contexto: Paciente completando ficha médica por voz
Incluye: datos existentes del paciente, campos faltantes
Inyecta: nombre del paciente, clínica, profesional asignado
```

## Bridge Nova ↔ MCP

Nova usa OpenAI Realtime API que NO soporta MCP nativamente. Se necesita un bridge:

```python
# En el handler de Nova voice WebSocket:
# 1. Nova recibe audio → transcripción
# 2. Si necesita datos → el bridge traduce tool_call a MCP resource/tool
# 3. MCP server responde
# 4. Bridge inyecta resultado en la conversación de Nova

class NovaMCPBridge:
    def __init__(self, mcp_client):
        self.mcp = mcp_client

    async def handle_tool_call(self, tool_name, args, tenant_id):
        # Map Nova tool calls to MCP operations
        if tool_name == "obtener_registros":
            uri = f"clinicforge://{args['tabla']}?{args.get('filtros', '')}"
            return await self.mcp.read_resource(uri)
        elif tool_name == "book_appointment":
            return await self.mcp.call_tool("book_appointment", args)
        # ... etc
```

## Configuración

```json
// .claude/mcp.json (para Claude Code / Cursor)
{
  "mcpServers": {
    "clinicforge": {
      "command": "python",
      "args": ["mcp_server/server.py"],
      "env": {
        "POSTGRES_DSN": "postgresql://...",
        "REDIS_URL": "redis://...",
        "TENANT_ID": "1"
      }
    }
  }
}
```

## Ventajas sobre 47 Tools

| Aspecto | 47 Tools | MCP Server |
|---------|----------|------------|
| Contexto | Cada tool schema ocupa tokens | Resources se cargan bajo demanda |
| Flexibilidad | Una tool por acción | CRUD genérico + resources URI |
| Mantenimiento | Agregar tool = schema + dispatch + impl | Agregar resource = 1 archivo |
| Multi-cliente | Solo Nova | Nova + Claude Code + Cursor + cualquier MCP client |
| Filtros | Hardcoded en cada tool | URI query params flexibles |
| Caché | No | Redis cache por resource |
| Seguridad | Por tool | Centralizado en el server |

## Implementación — Fases

### Fase 1: Server base + Resources de lectura
- server.py con conexión DB
- Resources: patients, appointments, professionals, config
- Transporte: stdio
- Test con Claude Code

### Fase 2: Tools de escritura
- book_appointment, modify_record, send_message
- save_anamnesis, register_payment
- Seguridad por rol

### Fase 3: Bridge Nova
- NovaMCPBridge que traduce tool_calls a MCP
- Integración en el WebSocket handler de Nova
- Fallback a tools directas si MCP no responde

### Fase 4: Analytics + Marketing
- Resources de analytics y marketing
- analyze_data tool con NLP
- Cache en Redis (TTL por tipo de dato)

### Fase 5: Multi-tenant + Production
- Auth por tenant_id en cada request
- Rate limiting
- Logging y monitoring
- Deploy como servicio separado
