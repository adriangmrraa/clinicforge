---
name: Alembic Migration Architect
description: Especialista en la gestión de migraciones de base de datos con Alembic y modelos ORM SQLAlchemy en orchestrator_service.
---

# Alembic Migration Architect

Este Skill instruye al agente sobre cómo crear, extender y mantener el sistema de migraciones de base de datos con **Alembic**, que reemplaza al antiguo "Maintenance Robot". Las migraciones residen en `orchestrator_service/alembic/`.

## Propósito

Asegurar que **CADA NUEVO DESPLIEGUE** en un entorno limpio nazca funcional y que las **BASES EXISTENTES** se actualicen sin intervención humana:
1.  **Baseline**: Migración `001_a1b2c3d4e5f6_full_baseline.py` crea todas las tablas si no existen.
2.  **Evolution**: Nuevas migraciones incrementales para features y cambios de esquema.
3.  **Startup automático**: `start.sh` ejecuta `alembic upgrade head` en cada arranque.

## Reglas de Oro

1.  **Nunca SQL directo**:
    *   Todo cambio de esquema se crea como migración Alembic.
    *   Nunca ejecutar `ALTER TABLE` fuera del pipeline de migraciones.

2.  **Ubicación de la Lógica**:
    *   Configuración: `orchestrator_service/alembic.ini` y `alembic/env.py`.
    *   Migraciones: `orchestrator_service/alembic/versions/`.
    *   Modelos ORM: `orchestrator_service/models.py` (30 clases SQLAlchemy).

3.  **No Modificar Migraciones Antiguas**:
    *   Las migraciones son históricas e inmutables.
    *   Siempre crear una nueva migración para cambios adicionales.

4.  **DSN Normalization**:
    *   `env.py` convierte `postgresql+asyncpg://` (FastAPI async) a `postgresql://` (Alembic sync).
    *   Pool: `NullPool` para compatibilidad con Alembic.

5.  **Sincronización de Modelos**:
    *   Tras crear una migración, actualizar `models.py` para que refleje el estado actual del esquema.

## Guía de Implementación

### 1. Agregar una nueva columna/feature

```bash
# Desde orchestrator_service/
alembic revision -m "add ai_notes column to appointments"
```

Editar el archivo generado en `alembic/versions/`:

```python
def upgrade():
    op.add_column('appointments', sa.Column('ai_notes', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('appointments', 'ai_notes')
```

Actualizar `models.py`:
```python
class Appointment(Base):
    __tablename__ = 'appointments'
    # ... campos existentes ...
    ai_notes = Column(Text, nullable=True)  # NUEVO
```

### 2. Crear una nueva tabla

```python
def upgrade():
    op.create_table(
        'new_table',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
    )
    op.create_index('ix_new_table_tenant_id', 'new_table', ['tenant_id'])

def downgrade():
    op.drop_table('new_table')
```

### 3. Aplicar migraciones

```bash
# Aplicar todas las migraciones pendientes
alembic upgrade head

# Ver estado actual
alembic current

# Ver historial
alembic history
```

## Casos de Uso
- **Nuevas Tablas**: `op.create_table(...)` con `tenant_id` obligatorio.
- **Nuevos Índices**: `op.create_index(...)`.
- **Nuevas Columnas**: `op.add_column(...)`.
- **Seeds de Configuración**: Usar `op.execute("INSERT ... ON CONFLICT DO NOTHING")`.

## Startup Flow (start.sh)
1. Verifica si la BD tiene tabla `alembic_version`.
2. Si la BD existe pero no tiene `alembic_version`: `alembic stamp head` (marca como actualizada).
3. Si es nueva o tiene migraciones pendientes: `alembic upgrade head`.
4. Arranca uvicorn.
