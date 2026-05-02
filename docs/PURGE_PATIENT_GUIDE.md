# Guía: Borrar paciente completamente (PostgreSQL + Redis)

Procedimiento para eliminar TODO rastro de un número de teléfono/paciente de la base de datos y Redis.

## Variables

- `PHONE_SUFFIX`: últimos 10 dígitos del teléfono (ej: `2994529972`)
- `FULL_PHONE`: teléfono completo con prefijo (ej: `+5492994529972`)
- `TENANT_ID`: ID del tenant (ej: `1`)

---

## 1. PostgreSQL

Ejecutar como una transacción. Reemplazar `%PHONE_SUFFIX%` con los últimos 10 dígitos:

```sql
BEGIN;

-- Mensajes de chat
DELETE FROM chat_messages WHERE conversation_id IN
  (SELECT id FROM chat_conversations WHERE external_user_id LIKE '%PHONE_SUFFIX%');

-- Conversaciones
DELETE FROM chat_conversations WHERE external_user_id LIKE '%PHONE_SUFFIX%';

-- Context snapshots (multi-agent)
DELETE FROM patient_context_snapshots WHERE phone_number LIKE '%PHONE_SUFFIX%';

-- Audit log (multi-agent)
DELETE FROM agent_turn_log WHERE phone_number LIKE '%PHONE_SUFFIX%';

-- Automations
DELETE FROM automation_executions WHERE phone_number LIKE '%PHONE_SUFFIX%';
DELETE FROM automation_logs WHERE phone_number LIKE '%PHONE_SUFFIX%';

-- Memorias del paciente
DELETE FROM patient_memories WHERE patient_phone LIKE '%PHONE_SUFFIX%';

-- Leads de Meta (notas e historial primero por FK)
DELETE FROM lead_notes WHERE lead_id IN
  (SELECT id FROM meta_form_leads WHERE phone_number LIKE '%PHONE_SUFFIX%');
DELETE FROM lead_status_history WHERE lead_id IN
  (SELECT id FROM meta_form_leads WHERE phone_number LIKE '%PHONE_SUFFIX%');
DELETE FROM meta_form_leads WHERE phone_number LIKE '%PHONE_SUFFIX%';

-- Nullificar referencias en tablas que no se borran
UPDATE accounting_transactions SET patient_id = NULL
  WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%PHONE_SUFFIX%');
UPDATE automation_logs SET patient_id = NULL
  WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%PHONE_SUFFIX%');

-- Attribution history
DELETE FROM patient_attribution_history
  WHERE patient_id IN (SELECT id FROM patients WHERE phone_number LIKE '%PHONE_SUFFIX%');

-- Pacientes menores (guardian_phone)
DELETE FROM patients WHERE guardian_phone LIKE '%PHONE_SUFFIX%';

-- Paciente principal
DELETE FROM patients WHERE phone_number LIKE '%PHONE_SUFFIX%';

COMMIT;
```

### Notas PostgreSQL

- Se usa `LIKE '%SUFFIX%'` para matchear independientemente del formato del prefijo internacional.
- Los menores vinculados por `guardian_phone` se borran ANTES que el paciente principal.
- `accounting_transactions` y `automation_logs` no se borran, solo se desvinculan con `SET patient_id = NULL`.

---

## 2. Redis

Ya estando DENTRO de `redis-cli` (después de `AUTH`), ejecutar cada línea por separado.
**NO** escribir `redis-cli` antes de cada comando — ya estás dentro de la consola.

Reemplazar `TENANT_ID` y `FULL_PHONE` con los valores reales:

```
DEL "patient_ctx_working:TENANT_ID:FULL_PHONE"
DEL "convstate:TENANT_ID:FULL_PHONE"
DEL "greet:TENANT_ID:FULL_PHONE"
DEL "lead_ctx:TENANT_ID:PHONE_SUFFIX"
DEL "buffer:TENANT_ID:FULL_PHONE"
DEL "timer:TENANT_ID:FULL_PHONE"
DEL "active_task:TENANT_ID:FULL_PHONE"
DEL "payment_verify_cooldown:TENANT_ID:FULL_PHONE"
```

### Ejemplo real (tenant 1, phone +5492994529972)

```
DEL "patient_ctx_working:1:+5492994529972"
DEL "convstate:1:+5492994529972"
DEL "greet:1:+5492994529972"
DEL "lead_ctx:1:2994529972"
DEL "buffer:1:+5492994529972"
DEL "timer:1:+5492994529972"
DEL "active_task:1:+5492994529972"
DEL "payment_verify_cooldown:1:+5492994529972"
```

### Notas Redis

- `(integer) 0` = la key no existía (normal, no es error).
- `(integer) 1` = la key existía y se borró.
- `lead_ctx` usa solo dígitos sin `+549`, el resto usa el phone completo.
- `slot_lock` no se borra porque el phone es el VALUE, no la KEY (y tiene TTL corto de 30s).

---

## Formato de las keys Redis (referencia)

| Key | Formato | Fuente |
|-----|---------|--------|
| `patient_ctx_working` | `patient_ctx_working:{tenant}:{phone}` | `services/patient_context.py` |
| `convstate` | `convstate:{tenant}:{phone}` | `services/conversation_state.py` |
| `greet` | `greet:{tenant}:{phone}` | `services/greeting_state.py` |
| `lead_ctx` | `lead_ctx:{tenant}:{digits}` | `services/lead_context.py` |
| `buffer` | `buffer:{tenant}:{external_user_id}` | `services/relay.py` |
| `timer` | `timer:{tenant}:{external_user_id}` | `services/relay.py` |
| `active_task` | `active_task:{tenant}:{external_user_id}` | `services/relay.py` |
| `payment_verify_cooldown` | `payment_verify_cooldown:{tenant}:{phone}` | `services/payment_cooldown.py` |
