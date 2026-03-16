# Implementation Plan: Configuración Dinámica de Clínica, FAQs y System Prompt

**Spec:** `specs/2026-03-16_dynamic-clinic-config-faqs-prompt.spec.md`
**Fecha:** 2026-03-16

---

## Pre-Flight Report

**Skills Activas:** Sovereign Backend, Nexus UI, DB Surgeon, Spec Architect
**Riesgos:** Migración DB (mitigado con idempotencia), prompt regression (mitigado con preservación de directivas)
**Confidence Score:** 92% (Alta viabilidad — cambios bien definidos, stack conocido, patrones existentes para replicar)
**Bloqueos:** Ninguno detectado
**Recomendacion:** PROCEDER con /implement

---

## Orden de Ejecución

### PASO 1: DB Migration (db.py)
- [ ] Agregar patch al final de la evolution pipeline en `orchestrator_service/db.py`
- [ ] Columnas nuevas en tenants: address, google_maps_url, working_hours
- [ ] Crear tabla clinic_faqs con índice
- [ ] Todo idempotente (IF NOT EXISTS, DO $$ ... END $$)

### PASO 2: Backend — Endpoints tenants (admin_routes.py)
- [ ] Extender GET /admin/tenants para retornar address, google_maps_url, working_hours
- [ ] Extender PUT /admin/tenants/{id} para aceptar address, google_maps_url, working_hours

### PASO 3: Backend — CRUD FAQs (admin_routes.py)
- [ ] GET /admin/tenants/{tenant_id}/faqs
- [ ] POST /admin/tenants/{tenant_id}/faqs
- [ ] PUT /admin/faqs/{faq_id}
- [ ] DELETE /admin/faqs/{faq_id}
- [ ] Auth con Depends(verify_admin_token), tenant_id validado

### PASO 4: Backend — System Prompt (main.py)
- [ ] Refactorizar build_system_prompt: nuevos parámetros dinámicos
- [ ] Eliminar datos hardcodeados (nombre, dirección, horarios, FAQs)
- [ ] Generar secciones de horarios y FAQs dinámicamente
- [ ] Optimizar tokens (eliminar redundancias)
- [ ] Sanitizar ad_context
- [ ] Corregir ejemplos (sin signos de apertura)
- [ ] Eliminar placeholders, usar NULL

### PASO 5: Backend — Callers del prompt (main.py, buffer_task.py)
- [ ] Actualizar invocaciones de build_system_prompt para fetchear datos de clínica desde DB
- [ ] Fetchear FAQs del tenant
- [ ] Pasar working_hours, address, google_maps_url, faqs como parámetros

### PASO 6: Frontend — ClinicsView (ClinicsView.tsx)
- [ ] Expandir interfaz Clinica con nuevos campos
- [ ] Expandir modal de edición con dirección, Maps URL
- [ ] Agregar editor de horarios por día (replicar de UserApprovalView)
- [ ] Agregar botón "FAQs" por clínica

### PASO 7: Frontend — Modal FAQs (nuevo componente o inline en ClinicsView)
- [ ] Modal con lista de FAQs
- [ ] CRUD: crear, editar, eliminar FAQs
- [ ] Campos: categoría, pregunta, respuesta

### PASO 8: Frontend — i18n (locales/)
- [ ] Agregar claves en es.json, en.json, fr.json para todos los textos nuevos
