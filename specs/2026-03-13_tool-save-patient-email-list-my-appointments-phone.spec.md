# Tool save_patient_email + Corrección list_my_appointments + Normalización de teléfono

> Origen: Conversación usuario — email post-agendamiento, IA no conoce turnos del paciente, normalización profesional de teléfono.

## 1. Contexto y Objetivos

- **Problema 1:** No hay forma de guardar el email del paciente tras agendar (sin fricción). La regla es que el paciente se crea al agendar; el email es opcional post-confirmación.
- **Problema 2:** La IA no responde correctamente cuando preguntan "mis turnos" — o no invoca `list_my_appointments` o falla por mismatch de teléfono.
- **Problema 3:** Inconsistencia en formato de teléfono (E.164 con/sin +, espacios) genera fallos en comparaciones.
- **Solución:** Tool `save_patient_email`, refuerzo de prompt para turnos y email, normalización única por dígitos para comparaciones.
- **KPIs:** (1) Pacientes pueden dejar email post-turno sin fricción. (2) IA siempre responde sobre turnos invocando la tool. (3) Búsqueda por teléfono robusta a variaciones de formato.

## 2. Esquemas de Datos

### Entradas
- **save_patient_email:** `email: str` — email válido a guardar.
- **list_my_appointments:** Sin cambio de firma. Usa `current_customer_phone` y `current_tenant_id`.

### Salidas
- **save_patient_email:** Mensaje de confirmación o error (string).
- **list_my_appointments:** Lista de turnos o mensaje de error (sin cambio de contrato).

### Persistencia
- Sin cambio de esquema. `patients.email` ya existe. Solo UPDATE.

### Normalización de teléfono (estándar profesional)
- **E.164** es el estándar internacional (ITU-T). Para comparaciones en BD usamos **solo dígitos** (`re.sub(r'\D', '', phone)`) para ser robustos a `+54 9 11...`, `54911...`, `+54911...`.
- Comparación: `REGEXP_REPLACE(phone_number, '[^0-9]', '', 'g') = $digits_only` o equivalente en Python antes de query.

## 3. Lógica de Negocio

- **save_patient_email:** Solo actualiza email si el paciente existe (por phone + tenant). Validación básica de email. No crea paciente.
- **list_my_appointments:** Usar normalización por dígitos en la cláusula WHERE para `p.phone_number`.
- **Prompt:** (a) Después de PASO 7 confirmación, opcionalmente ofrecer "Si me pasás tu mail te mantenemos al tanto 😊"; (b) Cuando el paciente responda con email válido, llamar `save_patient_email`; (c) NUNCA responder preguntas sobre turnos sin llamar `list_my_appointments` primero.
- **SOBERANÍA:** Todas las queries incluyen `tenant_id`. Tools usan `current_tenant_id.get()`.

## 4. Stack y Restricciones

- **Backend:** `orchestrator_service/main.py` — nueva tool `save_patient_email`, modificar `list_my_appointments` (normalización + logs), `build_system_prompt` (instrucciones).
- **Frontend:** Ninguno.
- **DB:** Sin parches.

## 5. Criterios de Aceptación

- **save_patient_email:** DADO paciente con turno reciente, CUANDO responde con email válido, ENTONCES se actualiza `patients.email` y la IA responde confirmación.
- **list_my_appointments:** DADO paciente con turnos, CUANDO pregunta "mis turnos" o similar, ENTONCES la IA invoca la tool y devuelve la lista.
- **Normalización:** DADO teléfono almacenado como `+5491123456789` o `5491123456789`, ENTONCES la comparación encuentra al paciente correctamente.

## 6. Archivos Afectados

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `orchestrator_service/main.py` | MODIFY | Nueva tool `save_patient_email`; normalización y logs en `list_my_appointments`; instrucciones en prompt |
| `specs/2026-03-13_tool-save-patient-email-list-my-appointments-phone.spec.md` | CREATE | Esta spec |

## 7. Casos Borde

| Riesgo | Mitigación |
|--------|------------|
| Email inválido | Validar regex básico; si inválido, pedir de nuevo sin guardar |
| Paciente no existe | `save_patient_email` devuelve mensaje amigable |
| Phone vacío | `list_my_appointments` ya retorna mensaje si `current_customer_phone` es None |
