---
name: "Sovereign Backend Engineer"
description: "v8.1: Senior Backend Architect & Python Expert. Lógica JIT v2, multi-tenancy, Alembic migrations y BFF service."
trigger: "v8.1, backend, JIT, tenancy, alembic, migrations, bff, tools"
scope: "BACKEND"
auto-invoke: true
---

# Sovereign Backend Engineer - Dentalogic v8.1

## 1. Evolución de Datos & Migraciones (Alembic)
**REGLA DE ORO**: Nunca proporciones o ejecutes SQL directo. Todo cambio de esquema pasa por Alembic.
- **Alembic Pipeline**: Todo cambio estructural debe implementarse como una migración en `orchestrator_service/alembic/versions/`.
- **Crear migración**: `alembic revision -m "descripción del cambio"` → editar el archivo generado con `op.add_column()`, `op.create_table()`, etc.
- **Aplicar**: `alembic upgrade head` (se ejecuta automáticamente en startup vía `start.sh`).
- **Modelos ORM**: Mantener sincronizados los modelos en `orchestrator_service/models.py` (30 clases SQLAlchemy).
- **Baseline**: La migración `001_a1b2c3d4e5f6_full_baseline.py` cubre las 28+ tablas existentes.

## 1b. BFF Service (Backend-for-Frontend)
- **Arquitectura**: El frontend se comunica con el orchestrator a través del BFF service (`bff_service/`, puerto 3000).
- **Flujo**: `Frontend (React :4173) → BFF (Express :3000) → Orchestrator (FastAPI :8000)`.
- **Tecnología**: Node.js + Express + Axios (proxy reverso con manejo de CORS y timeout de 60s).
- **Health check**: `GET /health` → `{ status: 'ok', service: 'bff-interface', mode: 'proxy' }`.

## 2. Multi-tenancy & Esquema Dental
Es obligatorio el aislamiento estricto de datos:
- **Tablas Core**: `patients`, `professionals`, `appointments`, `clinical_records`, `accounting_transactions`, `daily_cash_flow`.
- **Filtro tenant_id**: Todas las queries SQL **DEBEN** incluir el filtro `tenant_id`. No asumas nunca contexto global.
- **Tipado JSONB**: Dominio de la estructura de `medical_history` y de `working_hours` (0-6 days) en PostgreSQL.

## 3. Sincronización JIT v2 (Google Calendar)
La lógica de sincronización híbrida debe ser robusta:
- **Mirroring en Vivo**: Consultar Google Calendar en tiempo real durante el `check_availability`.
- **Normalización**: Limpiar nombres (quitar "Dr.", "Dra.") para matching exacto con calendarios externos.
- **Deduping**: Filtrar eventos de GCal que ya existen localmente como `appointments` mediante el `google_calendar_event_id`.

## 4. Protocolo Clínico de la IA (Tools)
Las herramientas del agente deben actuar como gatekeepers:
1. **check_availability**: Valida primero los `working_hours` (BD) y luego GCal.
2. **Lead-to-Patient Conversion**: `book_appointment` debe denegar la reserva si un usuario `guest` no ha proporcionado: **Nombre Completo, DNI, Obra Social y Teléfono**.
3. **Triaje y Derivación**: Clasificación NLP obligatoria antes de ofrecer turnos de urgencia.

## 5. Seguridad & Infraestructura
- **Auth Layer**: Manejo de JWT (HS256) diferenciando roles: `ceo`, `professional`, `secretary`.
- **INTERNAL_API_TOKEN**: Uso mandatorio para la comunicación entre `whatsapp_service` y `orchestrator_service`.
- **Gatekeeper Flow**: Usuarios nuevos nacen `pending`. La activación (`active`) es responsabilidad única del rol `ceo`.
- **Protocolo Omega**: Logs de emergencia para links de activación si el SMTP no está disponible.

## 6. Sincronización Real-Time (WebSockets)
Garantizar que el Frontend esté siempre al día:
- **Emitir Eventos**: Emitir `NEW_APPOINTMENT` o `APPOINTMENT_UPDATED` vía Socket.IO tras cualquier mutación exitosa en la base de datos de turnos.

## 7. WhatsApp Service (Pipeline)
- **Transcripción**: Integración Whisper para audios.
- **Deduplicación**: Cache de 2 minutos en Redis para evitar procesar webhooks duplicados.
- **Buffering**: Agrupar mensajes en ráfaga para mejorar el contexto del LLM.

---
*Nexus v8.0 - Senior Backend Architect & Python Expert Protocol*
