---
name: "DB Schema Surgeon"
description: "v8.1: Database & Persistence Master. Alembic migrations, modelos ORM SQLAlchemy y JSONB clínico."
trigger: "v8.1, sql, alembic, schema, migration, database, orm, models"
scope: "DATABASE"
auto-invoke: true
---

# Database & Persistence Master - Dentalogic v8.1

## 1. Evolución Segura con Alembic
**REGLA DE ORO**: Se prohíbe la ejecución de SQL directo. Todo cambio de esquema se gestiona vía Alembic.
- **Pipeline de Migraciones**: Todo cambio estructural debe crearse como una migración Alembic en `orchestrator_service/alembic/versions/`.
- **Crear migración**: `alembic revision -m "add column X to table Y"` → implementar `upgrade()` y `downgrade()`.
- **Modelos ORM**: Actualizar siempre `orchestrator_service/models.py` (30 clases SQLAlchemy) para que refleje el estado actual del esquema.
- **Baseline**: La migración `001_a1b2c3d4e5f6_full_baseline.py` usa `CREATE TABLE IF NOT EXISTS` para idempotencia en la instalación inicial.
- **Startup automático**: `start.sh` detecta si la BD ya existe (`alembic stamp head`) o es nueva (`alembic upgrade head`).

## 2. Multi-tenancy & Aislamiento Legal
- **Filtro tenant_id**: Todas las tablas core (`patients`, `professionals`, `appointments`, etc.) **DEBEN** incluir y filtrar por `tenant_id` en cada consulta de lectura o escritura.
- **Aislamiento Técnico**: Este campo es el único garante de la privacidad de datos clínicos entre diferentes consultorios.

## 3. Uso Estratégico de JSONB (Flexibilidad Clínica)
Preferir JSONB para datos semi-estructurados o con alta variabilidad:
- `patients.medical_history`: Almacena la anamnesis completa y alertas médicas críticas (alergias, patologías).
- `professionals.working_hours`: Configuración de agenda semanal (slots y habilitación por día).
- `clinical_records.odontogram`: Datos estructurados del estado dental (diente, superficie, estado).

## 4. Persistencia & Optimización
- **Búsqueda Ultrarrápida**: Garantizar índices operativos en `phone_number` y `dni` dentro de la tabla `patients`.
- **Persistencia de Memoria**: Vincular `chat_messages` con `patient_id` para mantener el contexto clínico a largo plazo en el Orchestrator.
- **Deduplicación con Redis**: Utilizar Redis para locks efímeros y deduplicación de webhooks (2 min) antes de confirmar escrituras en PostgreSQL.

## 5. Lógica de Negocio en Datos
- **Conversión Lead-Paciente**: El `status` en DB (`guest` vs `active`) dispara los protocolos de recolección de datos obligatorios para citas.
- **Protocolo Omega Prime**: El sistema de DB debe asegurar la auto-activación del primer usuario CEO registrado para evitar bloqueos iniciales de acceso.

---
*Nexus v8.0 - Senior Database & Persistence Architect Protocol*
