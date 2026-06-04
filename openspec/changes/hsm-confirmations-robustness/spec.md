# Especificación Técnica: Robustez en Confirmaciones HSM (hsm-confirmations-robustness)

## 1. Contexto y Objetivos
- **Problema:** Los pacientes interactúan de formas diversas al recibir recordatorios de turnos (mensajes HSM). Algunos responden con sinónimos de confirmación exactos ("conservo", "asisto", "voy") que no están contemplados en el interceptor de botones rápidos del webhook (`chat_webhooks.py`). Otros responden en lenguaje natural o mencionan horas aproximadas (ej. "confirmo a las 3" para una cita a las 15:15). El sistema actual no intercepta estos sinónimos de forma rápida y el agente de IA no dispone de una herramienta específica para confirmar citas, lo que puede provocar que no se actualice el estado del turno o que se requiera la intervención de la secretaria.
- **Solución:** 
  1. **Expansión de Sinónimos en Webhook:** Ampliar la lista de botones rápidos detectados en `chat_webhooks.py` para incluir nuevos sinónimos exactos ("conservo", "asisto", "voy", "acepto", "confirmo" y sus variantes con emojis y tildes).
  2. **Nueva Tool en el Agente:** Desarrollar la herramienta `@tool async def confirm_appointment` en `main.py` para permitir que el agente confirme turnos directamente cuando se detecte la intención en lenguaje natural, con tolerancia a discrepancias de horarios aproximados.
- **KPIs:**
  - Tasa de confirmación automática de turnos HSM > 95%.
  - Reducción del 85% de derivaciones manuales a secretaría por temas de confirmación de turnos.
  - Cero incidencias de discrepancia horaria no aclarada con el paciente.

---

## 2. Esquemas de Datos

### Entradas de la Tool `confirm_appointment`
```typescript
interface ConfirmAppointmentRequest {
  appointment_id?: string;        // UUID del turno si se conoce (opcional)
  approximate_time?: string;      // Hora aproximada mencionada (ej: "15:00", "a las 3", "tarde")
  target_date?: string;           // Fecha mencionada (ej: "2026-06-05", "mañana", "lunes")
}
```

### Salidas de la Tool `confirm_appointment`
El retorno será un string descriptivo (JSON o formato de texto claro) consumible por el LLM:
- **Éxito (Sin discrepancia):** `SUCCESS: Turno del 2026-06-05 a las 15:15 hs confirmado. Profesional: Dra. Laura Delgado. Tratamiento: Consulta.`
- **Éxito (Con advertencia de discrepancia horaria):** `SUCCESS: Turno del 2026-06-05 a las 15:15 hs confirmado. Profesional: Dra. Laura Delgado. WARNING: El paciente mencionó las 15:00 hs, pero el turno está agendado a las 15:15 hs. Es obligatorio aclararle al paciente que el horario exacto es 15:15 hs.`
- **Error:** `ERROR: No se encontró ningún turno programado o pendiente en el futuro para este paciente.`

### Persistencia (Cambios en DB)
- No se requieren cambios en el esquema de base de datos.
- Se actualiza la fila de la tabla `appointments` correspondiente:
  - `status` pasa a `'confirmed'`
  - `updated_at` pasa a `NOW()`

---

## 3. Lógica de Negocio (Invariantes)

### Aislamiento de Datos (Multi-tenancy)
- **RESTRICCIÓN DE SEGURIDAD INVIOLABLE:** Toda consulta SQL de lectura o actualización para encontrar al paciente, buscar turnos o cambiar el estado del turno debe filtrar explícitamente por `tenant_id = $x` obtenido de `current_tenant_id.get()`. NUNCA se debe consultar o modificar datos de otros tenants.

### Expansión de Sinónimos en Webhook (`chat_webhooks.py`)
- Se expande el set `_CONFIRM_BUTTONS` en el interceptor de Quick Replies para realizar coincidencias exactas en minúsculas (sin espacios iniciales/finales):
  - Sinónimos requeridos: `"conservo"`, `"asisto"`, `"voy"`, `"acepto"`, `"confirmo"`.
  - Variantes a incluir: `"conservo ✅"`, `"asisto ✅"`, `"voy ✅"`, `"acepto ✅"`, `"confirmo ✅"`, `"sí, voy"`, `"si, voy"`, `"sí, asisto"`, `"si, asisto"`.
- SI se intercepta uno de estos textos exactos:
  - ENTONCES actualizar la base de datos, emitir evento Socket.IO, enviar notificación de Telegram y responder con mensaje de confirmación inmediato al paciente, saltando el pipeline de la IA.

### Comportamiento de la Tool `confirm_appointment` (`main.py`)
- SI se provee `appointment_id`:
  - ENTONCES buscar el turno por ese ID y validar pertenencia al `tenant_id`.
- SI NO se provee `appointment_id`:
  - ENTONCES buscar el paciente asociado al teléfono actual (`current_customer_phone.get()`) en el tenant.
  - Buscar los turnos del paciente en estado `'scheduled'` o `'pending'` con fecha futura (`appointment_datetime > NOW()`).
  - SI se especifica `target_date`:
    - Filtrar únicamente los turnos que caigan en esa fecha.
  - SI hay múltiples turnos y se especifica `approximate_time`:
    - Emparejar con el turno cuyo horario sea más cercano a la hora mencionada.
- SI se confirma el turno correctamente:
  - ENTONCES actualizar su estado a `'confirmed'`.
  - SI existe discrepancia entre `approximate_time` y el horario agendado (ej. diferencia > 0 minutos):
    - ENTONCES incluir en el retorno de la tool una advertencia (`WARNING`) indicando que el agente debe recordarle al paciente que el horario oficial exacto de la cita es el registrado en la base de datos.
- SI no se encuentra ningún turno próximo en estado programado o pendiente:
  - ENTONCES retornar: `ERROR: No se encontró ningún turno programado o pendiente en el futuro para este paciente.` Esto evita alucinaciones del agente.

### Notificaciones y Tiempo Real
Toda confirmación exitosa (vía webhook o vía tool del agente) debe realizar:
1. **Emisión de Socket.IO:** Emitir el evento `APPOINTMENT_UPDATED` a la sala `tenant:{tenant_id}`.
2. **Notificación de Telegram:** Invocar `fire_telegram_notification` con tipo `APPOINTMENT_UPDATED`, indicando el origen del cambio (`source: "whatsapp_button"` o `source: "agent_tool"`).

---

## 4. Stack y Restricciones
- **FastAPI / Python:** Uso de decorador `@tool` para registrar en el agente.
- **SQL / asyncpg:** Consultas preparadas directas utilizando el pool de conexiones (`db.pool`).
- **Socket.IO:** Acceso al cliente Socket.IO a través de `main.sio` o `app.state.sio`.
- **Telegram Notifier:** Integración con `services.telegram_notifier`.
- **i18n:** Mensajes interactivos pre-armados en español rioplatense natural.

---

## 5. Criterios de Aceptación (Gherkin)

### Escenario 1: Coincidencia exacta de nuevos sinónimos en el webhook
- **DADO** que un paciente tiene un turno agendado en estado `'scheduled'` para mañana a las 14:00 hs
- **CUANDO** el paciente envía un mensaje de WhatsApp que contiene exactamente `"asisto"` o `"conservo"` o `"voy"`
- **ENTONCES** el webhook intercepta el mensaje sin invocar a la IA
- **Y** actualiza el estado del turno en la base de datos a `'confirmed'`
- **Y** emite el evento Socket.IO `APPOINTMENT_UPDATED` a la sala del tenant
- **Y** dispara la notificación de Telegram con `source = 'whatsapp_button'`
- **Y** responde al paciente confirmándole que su turno está asegurado para mañana a las 14:00 hs

### Escenario 2: Confirmación en lenguaje natural procesada por el agente de IA
- **DADO** que un paciente tiene un turno agendado en estado `'scheduled'` para el lunes a las 09:30 hs
- **CUANDO** el paciente envía el mensaje `"Sí, perfecto, nos vemos el lunes ahí estaré"`
- **ENTONCES** el webhook delega el mensaje al agente de IA
- **Y** el agente invoca la tool `confirm_appointment` con `target_date = "lunes"`
- **Y** la tool actualiza el turno a `'confirmed'` y devuelve éxito
- **Y** el agente responde al paciente confirmando amablemente la cita para las 09:30 hs

### Escenario 3: Confirmación con discrepancia horaria aproximada
- **DADO** que un paciente tiene un turno agendado en estado `'scheduled'` para mañana a las 18:45 hs
- **CUANDO** el paciente envía el mensaje `"Hola, confirmo que voy mañana a las 7 de la tarde"`
- **ENTONCES** el agente invoca la tool `confirm_appointment` con `approximate_time = "19:00"` y `target_date = "mañana"`
- **Y** la tool localiza y confirma la cita de las 18:45 hs
- **Y** retorna éxito con la advertencia: `WARNING: El paciente mencionó las 19:00, pero el turno oficial es a las 18:45.`
- **Y** el agente responde al paciente confirmando el turno pero aclarando explícitamente: `"Excelente, quedó confirmado. Te recordamos que tu horario agendado es a las 18:45 hs."`

### Escenario 4: Robustez y error ante la ausencia de turnos futuros
- **DADO** que un paciente no tiene ningún turno en estado `'scheduled'` o `'pending'` para fechas futuras
- **CUANDO** el paciente envía el mensaje `"Quiero confirmar el turno"`
- **ENTONCES** el agente invoca la tool `confirm_appointment`
- **Y** la tool retorna: `ERROR: No se encontró ningún turno programado o pendiente en el futuro para este paciente.`
- **Y** el agente le informa al paciente de manera clara y profesional que no registra turnos futuros pendientes y le ofrece coordinar uno nuevo.
