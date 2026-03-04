---
name: "DB Schema Surgeon"
description: "v8.0: Database & Persistence Master. Gestión de evolución segura, parches idempotentes y JSONB clínico."
trigger: "v8.0, sql, idempotent, schema, migration, database"
scope: "DATABASE"
auto-invoke: true
---

# DB Schema Surgeon - Dentalogic

# DB Schema Surgeon - Dentalogic

# Database & Persistence Master - Dentalogic v8.0

## 1. Evolución Segura e Idempotente (Maintenance Robot)
**REGLA DE ORO**: Se prohíbe la ejecución de SQL directo fuera del Evolution Pipeline.
- **Protocolo de Parches**: Todo cambio estructural debe realizarse mediante un parche asíncrono en `orchestrator_service/db.py`.
- **Bloques DO $$**: Uso mandatorio de bloques `DO $$` con lógica de verificación (`IF NOT EXISTS`, `IF EXISTS`) para garantizar la estabilidad tras múltiples reinicios.
- **Sincronización de Base**: Tras evolucionar el pipeline, se debe actualizar el archivo de cimiento `db/init/dentalogic_schema.sql` (o `001_schema.sql`) para nuevas instalaciones.

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
