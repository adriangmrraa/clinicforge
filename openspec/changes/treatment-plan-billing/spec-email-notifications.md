# Spec: Email Notifications — Treatment Plan Billing

**Change**: treatment-plan-billing
**Module**: Email Notifications
**Status**: Draft
**Date**: 2026-04-03
**Depends on**: spec-backend.md, spec-ai-tools.md

---

## 1. Overview

Este spec cubre el sistema de notificaciones por email cuando se concreta un pago en un plan de tratamiento.

**Flujo básico:**
1. Se registra un pago (por IA desde WhatsApp o manualmente desde UI)
2. Si el paciente tiene email → se envía confirmación automáticamente
3. Si el paciente NO tiene email → el agente WhatsApp lo pide amablemente y luego envía

---

## 2. Precondiciones

### 2.1 Campo email en patients

Verificar que la tabla `patients` ya tiene el campo `email`. Si no existe, agregarlo en la migración:

```sql
ALTER TABLE patients ADD COLUMN email VARCHAR(255) NULL;
```

### 2.3 Sistema de email existente

El proyecto YA tiene un servicio de email completo en `orchestrator_service/email_service.py`:

```python
from email_service import email_service

# Métodos disponibles:
email_service.send_handoff_email(...)
email_service.send_payment_email(...)  # Para pagos de turnos
email_service.send_payment_verification_failed_email(...)
email_service.send_digital_record_email(...)
```

**Para pagos de planes**: Se debe AGREGAR un nuevo método al `EmailService`:
- `send_plan_payment_confirmation_email(...)` — específico para confirmaciones de planes
- O reutilizar `send_payment_email` adaptando los parámetros (el template actual requiere appointment_date, appointment_time, treatment — para planes necesita plan_name, approved_total, paid_total, pending_total)

---

## 3. FR-EMAIL-01: Confirmación de pago automática

### Trigger

Un pago se concreta cuando:
1. `verify_payment_receipt` verifica exitosamente un comprobante de WhatsApp y crea un `treatment_plan_payment`
2. Un usuario (CEO/Secretary) registra un pago manualmente vía API `POST /admin/treatment-plans/{plan_id}/payments`
3. Un usuario usa Nova con `registrar_pato_plan`

### Datos del email

| Campo | Valor |
|-------|-------|
| **From** | `{clinic_name} <no-reply@{tenant_domain}>` |
| **To** | `patients.email` |
| **Subject** | `Confirmación de pago - {clinic_name}` |

### Body del email (template)

```
Hola {patient_first_name},

Recibimos tu pago:

💰 Monto: ${amount}
💳 Método: {payment_method_display}
📅 Fecha: {payment_date}

Saldo de tu plan "{plan_name}":
- Total aprobado: ${approved_total}
- Pagado hasta ahora: ${paid_total}
- Saldo pendiente: ${pending_total}

{progress_bar_visual}

¿Dudas? Respondé este mail o escribinos por WhatsApp.

Saludos,
{clinic_name}
```

### payment_method_display

| Código | Texto |
|--------|-------|
| cash | Efectivo |
| transfer | Transferencia |
| card | Tarjeta de crédito/débito |
| insurance | Obra social |

### Implementación backend

**Nuevo endpoint (opcional - para reenvíos):**

```python
@router.post(
    "/patients/{patient_id}/send-payment-confirmation",
    tags=["Notificaciones"],
    summary="Reenviar confirmación de último pago",
)
async def send_payment_confirmation(
    patient_id: int,
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    # Obtener último payment del paciente
    # Obtener datos del plan
    # Obtener datos de la clínica
    # Enviar email
    return {"status": "sent", "email": patient_email}
```

**Servicio de email:**

Crear/editar `orchestrator_service/services/email_service.py`:

```python
async def send_payment_confirmation_email(
    tenant_id: int,
    patient_id: int,
    payment_id: UUID,
    db_pool,
) -> bool:
    """
    Envía email de confirmación de pago al paciente.
    Retorna True si envió, False si no tenía email o falló.
    """
    # 1. Obtener datos del paciente (incluir email)
    # 2. Si email es NULL → retornar False
    # 3. Obtener datos del plan y pagos
    # 4. Obtener datos de la clínica (clinic_name, email config)
    # 5. Renderizar template
    # 6. Enviar via SMTP
    # 7. Loggear resultado
```

### Integración en endpoints existentes

**EP-09 (registrar pago en plan):** después del INSERT exitoso, agregar:

```python
# Después de insertar el payment y sync con accounting_transactions
# ... código existente ...

# ENVIAR EMAIL DE CONFIRMACIÓN (async, no bloqueante)
try:
    await send_payment_confirmation_email(
        tenant_id=tenant_id,
        patient_id=plan["patient_id"],
        payment_id=payment_id,
        db_pool=db.pool
    )
except Exception as e:
    logger.warning(f"Email confirmation failed: {e}")  # No rompe la respuesta
```

**verify_payment_receipt en main.py:** agregar lógica de email tras verificación exitosa.

---

## 4. FR-EMAIL-02: Solicitar email si no existe

### Contexto

Si el paciente no tiene email (`patients.email IS NULL`), el agente WhatsApp debe pedirlo antes de enviar la confirmación.

### Modificación en buffer_task.py

Agregar verificación antes de enviar la confirmación:

```python
# Después de verificar el comprobante y crear el payment
patient_email = await pool.fetchval(
    "SELECT email FROM patients WHERE id = $1 AND tenant_id = $2",
    patient_id, tenant_id
)

if not patient_email:
    # Paciente sin email → pedirlo
    media_context += (
        "El paciente no tiene email registrado. PARA ENVIAR LA CONFIRMACIÓN "
        "DEL PAGO, PREGUNTÁ AMABLEMENTE: '¿Me pasás tu email para mandarte la "
        "confirmación del pago?' Y LUEGO DE OBENERLO, usá tool para actualizar "
        "el email del paciente."
    )
    # NO enviar email todavía
else:
    # Enviar email normalmente (vía endpoint o service)
```

### Modificación en main.py - verify_payment_receipt

```python
async def verify_payment_receipt(...):
    # ... lógica existente ...
    
    if verification_success:
        # Crear el payment (ya sea de turno o plan)
        
        # Obtener email del paciente
        patient_email = await get_patient_email(patient_id, tenant_id)
        
        if patient_email:
            # Enviar confirmación
            await send_payment_confirmation_email(...)
        else:
            # Devolver flag para que el agente pida el email
            return {
                "success": True,
                "payment_created": True,
                "email_required": True,
                "message": "Pago verificado. El paciente necesita proporcionar email para recibir confirmación."
            }
```

### Tool para actualizar email del paciente

**Nova tool (nueva):**

```json
{
  "type": "function",
  "name": "actualizar_email_paciente",
  "description": "Guarda o actualiza el email de un paciente en su ficha",
  "parameters": {
    "type": "object",
    "properties": {
      "patient_id": {"type": "integer"},
      "email": {"type": "string", "format": "email"}
    },
    "required": ["patient_id", "email"]
  }
}
```

**Endpoint backend:**

```python
@router.put(
    "/patients/{patient_id}/email",
    tags=["Pacientes"],
    summary="Actualizar email del paciente",
)
async def update_patient_email(
    patient_id: int,
    body: {"email": str},
    user_data=Depends(verify_admin_token),
    tenant_id: int = Depends(get_resolved_tenant_id),
):
    # Validar formato de email
    # UPDATE patients SET email = $1 WHERE id = $2 AND tenant_id = $3
    # Retornar nuevo email
```

---

## 5. Flujo completo

### Flujo 1: Pago con email existente

```
1. Paciente envía comprobante por WhatsApp
2. Buffer task detecta plan con saldo pendiente
3. verify_payment_receipt verifica monto OK
4. Se crea treatment_plan_payment
5. Se detecta que patient.email existe
6. Se envía email de confirmación automáticamente
7. Agente dice: "Recibí tu comprobante, está verificado. 
   Te mandamos la confirmación a tu email."
```

### Flujo 2: Pago sin email - IA lo pide

```
1. Paciente envía comprobante por WhatsApp
2. Buffer task detecta plan con saldo pendiente
3. verify_payment_receipt verifica monto OK
4. Se crea treatment_plan_payment
5. Se detecta que patient.email es NULL
6. El agente recibe instrucciones: pedir email
7. Agente dice: "Recibí tu comprobante, está verificado. 
   ¿Me pasás tu email para mandarte la confirmación?"
8. Paciente responde con email
9. Nova o agente actualiza email del paciente
10. Se envía email de confirmación
```

---

## 6. Configuración SMTP por tenant

En la tabla `tenants` o `tenants.config`, almacenar:

```sql
-- En tenants.config (JSONB)
{
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "clinic@example.com",
  "smtp_password": "encrypted_password",
  "smtp_from_name": "Clínica Sonría"
}
```

O usar configuración global del sistema si todos los tenants comparten el mismo SMTP.

---

## 7. Criterios de aceptación

- [ ] Cuando se registra un pago y el paciente tiene email → se envía confirmación
- [ ] Cuando se registra un pago y el paciente NO tiene email → el agente pide el email
- [ ] El email contiene: monto, método, saldo del plan, datos de la clínica
- [ ] El sistema usa el SMTP existente o crea uno básico
- [ ] Nova puede actualizar el email del paciente con tool dedicada
- [ ] Se puede reenviar confirmación desde admin

---

## 8. Archivos afectados

| Archivo | Acción |
|---------|--------|
| `services/email_service.py` | Crear/modificar |
| `services/buffer_task.py` | Modificar - detectar email faltante |
| `main.py` | Modificar verify_payment_receipt |
| `nova_tools.py` | Agregar tool `actualizar_email_paciente` |
| `admin_routes.py` | Agregar endpoint PUT /patients/{id}/email |
| `locales/{es,en,fr}.json` | Agregar plantillas de email |

---

*Fin del spec de email notifications.*