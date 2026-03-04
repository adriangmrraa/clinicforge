---
description: 
---

# Workflow: Crear Nueva Feature en Dentalogic

Este workflow define el proceso para implementar nuevas funcionalidades siguiendo la arquitectura plana y el protocolo "Gala".

## 1. Análisis Técnico
Antes de codear, validá:
- [ ] **Base de Datos**: ¿Requiere nuevas tablas en PostgreSQL? (Usar `asyncpg` directo en `db.py`).
- [ ] **Google Calendar**: ¿Involucra turnos? (Integrar con `gcal_service.py`).
- [ ] **WhatsApp**: ¿Requiere nuevas respuestas de la IA? (Ajustar prompt en `main.py`).

## 2. Implementación Backend (Orchestrator)

### 2.1. Base de Datos
Agregá las tablas necesarias vía SQL puro.
```python
# db.py o script temporal
await db.pool.execute("CREATE TABLE IF NOT EXISTS...")
```

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
