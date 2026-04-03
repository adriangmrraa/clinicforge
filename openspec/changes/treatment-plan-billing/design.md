# Design: Treatment Plan Billing System

## Technical Approach

Sistema de presupuestos y facturación unificado a nivel plan de tratamiento. Backward compatible con el modelo existente de billing por turno (`appointments.billing_amount`) mediante discriminador estructural (`plan_item_id`). Cada pago en plan sincroniza atómicamente con `accounting_transactions`.

## Architecture Decisions

### Decision: UUID como PK + tenant_id redundante

| Choice | Alternatives | Rationale |
|--------|--------------|------------|
| UUID (`gen_random_uuid()`) | INT secuencial | Alineación con dirección del proyecto (appointments usa UUID); evita secuencias compartidas |
| `tenant_id` en tablas hijas | Heredar de padre | Patrón existente del proyecto; queries directas sin JOIN; seguridad anti-cross-tenant |

### Decision: FK conceptual treatment_type_code

| Choice | Alternatives | Rationale |
|--------|--------------|------------|
| Sin FOREIGN KEY | FK hard a `treatment_types` | Tipos pueden archivar; FK hard bloquearía bajas; `custom_description` permite ítems libres |

### Decision: Soft-delete planes, hard-delete items/pagos

| Choice | Alternatives | Rationale |
|--------|--------------|------------|
| Planes: `status='cancelled'` | Hard delete | Valor histórico para paciente |
| Items/Pagos: hard delete | Soft delete | Error de carga sin valor histórico |

### Decision: Sync síncrono con accounting_transactions

| Choice | Alternatives | Rationale |
|--------|--------------|------------|
| TRANSACCIÓN ÚNICA | Background task | Atomicidad crítica para métricas |

## Data Flow

```
Frontend ──POST /payments──► FastAPI Endpoint (EP-09)
                                  │
                         Transaction Block
                         1. INSERT treatment_plan_payments
                         2. INSERT accounting_transactions
                         3. UPDATE plan status (if first payment)
                                  │
                                  ▼
                            PostgreSQL
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `alembic/versions/018_treatment_plan_billing.py` | Create | 3 tablas + columna appointments.plan_item_id |
| `admin_routes.py` | Modify | 12 endpoints CRUD (EP-01 a EP-12) |
| `services/metrics_service.py` | Modify | `_get_billing_revenue()` — agregar fuente plan |
| `analytics_service.py` | Modify | `get_professionals_liquidation()` — agrupar por plan_id |
| `nova_tools.py` | Modify | 3 tools nuevas + modificar 3 existentes |
| `main.py` | Modify | `verify_payment_receipt` — detectar plan activo |
| `buffer_task.py` | Modify | Detección comprobantes con plan pendiente |
| `BillingTab.tsx` | Create | Componente Tab 6 completo |
| `PatientDetail.tsx` | Modify | Agregar tab billing + socket listeners |
| `locales/{es,en,fr}.json` | Modify | Agregar ~45 claves namespace billing |

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | Helpers: `_resolve_patient`, cálculos totales | pytest con mock |
| Integration | Endpoints CRUD | pytest + test DB |
| E2E | Flujo UI → API → DB → métricas | Playwright |

### Tests críticos
- `test_pending_payments_no_double_count`: turno con plan_item_id > 0 → solo计入 plan source
- `test_registrar_pago_atomic`: accounting_transactions fail → rollback total

## Migration / Rollout

1. Pre-deploy: verificar migration 017 aplicada
2. Deploy: `alembic upgrade head`
3. Rollback: `alembic downgrade 017` (destructivo — requiere backup)

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Doble-conteo métricas | Regla: `plan_item_id IS NOT NULL` excluye de `billing_amount`; sync atómico |
| Inconsistencia estimated_total | Recálculo en cada INSERT/UPDATE/DELETE de ítem |
| Migración rompe dashboard | BACKWARD COMPATIBLE: queries legacy intactas |

## Open Questions

- [ ] ¿Soporte pagos con tarjeta directamente en UI? — Futuro
- [ ] ¿PDF del presupuesto? — Out of scope
- [ ] ¿Cómo manejar devoluciones? — Sin tabla refunds por ahora
- [ ] ¿Usar servicio de email existente o crear nuevo? — Usar existente (email_service.py)

---

## Email Notifications

### Sistema de confirmación de pagos por email

**Trigger:** Se envía cuando se concreta un pago (verificado por IA o registrado manualmente).

**Arquitectura de decisiones:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Servicio de email | Reutilizar `email_service.py` existente | Ya tiene métodos para pagos de turnos; agregar nuevo método para planes |
| Template | En `locales/{es,en,fr}.json` + HTML opcional | Sistema i18n existente |
| Integración | Async after payment creation | No bloquea respuesta API |
| Email faltante | Agente WhatsApp lo pide | Flujo natural mediante tool `actualizar_email_paciente` |

**Flujo:**
1. Payment creado en `treatment_plan_payments`
2. Verificar si `patients.email` existe
3. Si existe → enviar inmediatamente via `send_payment_confirmation_email()`
4. Si NULL → devolver flag `email_required` para que el agente pida el email

**Servicios:**
- `email_service.py` — método `send_payment_confirmation_email()`
- Plantillas en `locales/{es,en,fr}.json`

**Herramientas Nova:**
- `actualizar_email_paciente` — guardar email del paciente

**Endpoints:**
- `PUT /admin/patients/{id}/email` — actualizar email
- `POST /admin/patients/{id}/send-payment-confirmation` — reenviar confirmación

---

## Welcome Emails

### Sistema de emails de bienvenida a nuevos usuarios

**Trigger:** Se envía cuando se crea un nuevo usuario (profesional, secretaria o CEO) con `status=active`.

**Arquitectura de decisiones:**

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Punto de integración | `auth_routes.py` (register) + `admin_routes.py` (create_professional) | Todos los flujos de creación pasan por estos puntos |
| Template | HTML dedicado por rol + i18n | Contenido diferente según role (professional/secretary/ceo) |
| Envío | Async after user creation | No bloquea respuesta API |
| Estado | Solo usuarios `active` | Usuarios `pending` no reciben hasta aprobación |

**Templates por rol:**

| Rol | Subject | Contenido clave |
|-----|---------|-----------------|
| professional | "Bienvenido a {clinic_name} - Tu acceso al sistema" | Credenciales + link agenda + datos clínica |
| secretary | "Bienvenida a {clinic_name} - Tu acceso como Secretaría" | Credenciales + funcionalidades disponibles |
| ceo/admin | "Bienvenido a {clinic_name} - Acceso como Administrador" | Credenciales + dashboard + configuraciones |

**Variables dinámicas:**
- `{user_first_name}`, `{user_email}`, `{login_url}`
- `{clinic_name}`, `{clinic_address}`, `{clinic_phone}`, `{support_email}`

**Integración:**
- `auth_routes.py` — después de `/register` exitoso
- `admin_routes.py` — después de `create_professional` con `is_active=TRUE`

**Servicio:**
- `email_service.py` — método `send_welcome_email(role)` con selección de template según rol

---

## File Changes (Actualizado)

| File | Action | Description |
|------|--------|-------------|
| `alembic/versions/018_treatment_plan_billing.py` | Create | 3 tablas + columna appointments.plan_item_id |
| `admin_routes.py` | Modify | 12 endpoints CRUD (EP-01 a EP-12) + PUT /patients/{id}/email |
| `services/metrics_service.py` | Modify | `_get_billing_revenue()` — agregar fuente plan |
| `analytics_service.py` | Modify | `get_professionals_liquidation()` — agrupar por plan_id |
| `nova_tools.py` | Modify | 3 tools nuevas + modificar 3 existentes + `actualizar_email_paciente` |
| `main.py` | Modify | `verify_payment_receipt` — detectar plan activo + email |
| `buffer_task.py` | Modify | Detección comprobantes con plan pendiente + email |
| `services/email_service.py` | Modify | Agregar `send_payment_confirmation_email()` y `send_welcome_email()` |
| `auth_routes.py` | Modify | Integrar `send_welcome_email()` en `/register` |
| `BillingTab.tsx` | Create | Componente Tab 6 completo |
| `PatientDetail.tsx` | Modify | Agregar tab billing + socket listeners |
| `locales/{es,en,fr}.json` | Modify | Agregar ~45 claves namespace billing + templates email |

---

## Testing Strategy (Email)

| Layer | What | Approach |
|-------|------|----------|
| Unit | `send_payment_confirmation_email()` con mock SMTP | pytest con mock |
| Integration | Endpoint `/patients/{id}/send-payment-confirmation` | pytest + test DB |
| E2E | Flujo: comprobante → payment → email enviado | Playwright + mailhog |
