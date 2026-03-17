---
description: 
---

# Workflow: Crear Nueva Feature en Dentalogic

Este workflow define el proceso para implementar nuevas funcionalidades siguiendo la arquitectura plana y el protocolo "Gala".

## 1. Análisis Técnico
Antes de codear, validá:
- [ ] **Base de Datos**: ¿Requiere nuevas tablas/columnas en PostgreSQL? (Crear migración Alembic).
- [ ] **Google Calendar**: ¿Involucra turnos? (Integrar con `gcal_service.py`).
- [ ] **WhatsApp**: ¿Requiere nuevas respuestas de la IA? (Ajustar prompt en `main.py`).
- [ ] **BFF Service**: ¿El frontend necesita acceder al nuevo endpoint? (Ya rutea automáticamente vía proxy).

## 2. Implementación Backend (Orchestrator)

### 2.1. Base de Datos
Creá una migración Alembic para los cambios de esquema.
```bash
# Desde orchestrator_service/
alembic revision -m "create new_table for feature X"
```
```python
# En el archivo de migración generado:
def upgrade():
    op.create_table('new_table',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        # ... más columnas
    )

def downgrade():
    op.drop_table('new_table')
```
Actualizar `orchestrator_service/models.py` con la nueva clase ORM.

### 2.2. Lógica de Negocio
Implementá la funcionalidad en `orchestrator_service/`. Si es administrativa, usá `admin_routes.py`.

## 3. Implementación Frontend
Actualizá la UI en `frontend_react/`.
- Usar `axios` desde `src/api/axios.ts`.
- Mantener el diseño **Glassmorphism**.

## 4. Verificación "Sovereign"
- [ ] Validar que no haya fugas de datos (Isolation).
- [ ] Probar el flujo completo: WhatsApp -> Orquestador -> GCal.
- [ ] Verificar que el personal de la clínica reciba las notificaciones correctas.
