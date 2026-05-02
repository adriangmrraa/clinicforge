# Flujo Completo de Agendamiento — ClinicForge AI Agent (TORA/Paula)

**Fecha:** 2026-05-01
**Estado:** Documentación del flujo ACTUAL en código
**Propósito:** Referencia completa del proceso de booking del agente IA, paso a paso, con ejemplos reales y casos de usuario.

---

## Resumen del Flujo

```
Paciente escribe → Saludo → Definir servicio → Modalidad (particular/OS) → Profesional
→ check_availability → Paciente elige slot → Pedir datos (nombre, DNI)
→ confirm_slot (lock 5min) → book_appointment → Confirmación + Anamnesis + Seña
```

---

## Máquina de Estados (Redis)

```
IDLE → OFFERED_SLOTS → SLOT_LOCKED → BOOKED / PAYMENT_PENDING → PAYMENT_VERIFIED
```

| Estado | Qué significa | Quién lo setea | TTL |
|--------|---------------|----------------|-----|
| `IDLE` | Sin flujo activo | Default / reset | — |
| `OFFERED_SLOTS` | Se ofrecieron 2 opciones de turno | `check_availability` | 30 min |
| `SLOT_LOCKED` | Paciente eligió, slot reservado | `confirm_slot` | 30 min |
| `BOOKED` | Turno confirmado sin seña | `book_appointment` | 30 min |
| `PAYMENT_PENDING` | Turno confirmado, esperando seña | `book_appointment` | 30 min |
| `PAYMENT_VERIFIED` | Pago verificado | `verify_payment_receipt` | 30 min |

**Redis keys involucradas:**

| Key | Formato | TTL | Propósito |
|-----|---------|-----|-----------|
| `convstate:{tenant}:{phone_digits}` | JSON | 30 min | Estado actual de la conversación |
| `slot_offer:{tenant}:{phone}` | JSON array | 30 min | Slots ofrecidos por check_availability |
| `slot_lock:{tenant}:{prof_id}:{date}:{time}` | phone string | 5 min | Lock de un slot específico |
| `greet:{tenant}:{phone}` | "1" | 4 horas | Flag de saludo ya enviado |

**IMPORTANTE:** `convstate` normaliza el phone a solo dígitos (sin `+`). `slot_offer` usa el phone tal cual viene (con `+`).

---

## PASO 1: SALUDO E IDENTIDAD

El agente detecta el tipo de paciente y saluda diferente:

### Caso A — Lead nuevo (primera vez)

**Mensaje del paciente:** "Hola"

**Respuesta del agente:**
```
Hola 😊
Soy Paula, la asistente virtual de Clínica Dra. Laura Delgado.
Somos especialistas en cirugía maxilofacial, implantes y ortodoncia.
¿En qué te puedo ayudar?
```

**Mensaje del paciente:** "Quiero un turno me duele la muela"

**Respuesta del agente (directa, sin saludo largo):**
```
Hola 😊 Soy Paula, la asistente virtual de Clínica Dra. Laura Delgado.
Entiendo, vamos a ayudarte a resolverlo lo antes posible.
Hace cuánto tiempo estás con dolor y si notás inflamación?
```

### Caso B — Paciente existente sin turno futuro

**Respuesta del agente:**
```
Hola 😊
Soy Paula, la asistente virtual de Clínica Dra. Laura Delgado.
¿Necesitás agendar un turno o tenés alguna consulta?
```

### Caso C — Paciente con turno futuro

**Respuesta del agente:**
```
Hola 😊
Soy Paula, la asistente virtual de Clínica Dra. Laura Delgado.
Veo que tenés un turno de Consulta el Miércoles 07/05 a las 10:00 con la Dra. Laura.
¿Necesitás algo respecto a ese turno o tenés otra consulta?
```

---

## PASO 2: DEFINIR SERVICIO

El agente identifica qué tratamiento necesita el paciente.

### Caso normal

**Paciente:** "Quiero un turno para limpieza"
**Agente:** *(llama `list_services` internamente para validar que "limpieza" existe)*

Si el término coloquial matchea un servicio → continúa.
Si no matchea → muestra los servicios disponibles.

### Caso triage (urgencia/dolor)

**Paciente:** "Me duele mucho la muela"
**Agente:**
```
Entiendo, vamos a ayudarte a resolverlo lo antes posible.
Hace cuánto tiempo estás con dolor y si notás inflamación?
```

**Triggers de triage:** dolor, inflamación, sangrado, accidente, traumatismo, "se me cayó", "se me rompió", "se me partió", "urgente", "emergencia", "no puedo comer", "fiebre".

El agente llama `triage_urgency` + `check_availability("Consulta")` directamente. Máximo 2 mensajes antes de ofrecer turno.

---

## PASO 2b: PARA QUIÉN ES EL TURNO

Solo si hay ambigüedad.

**Paciente:** "Necesito un turno para mi hijo"
**Agente:** "¿Cuántos años tiene?"

Tres escenarios posibles:
- **Para sí mismo** → flujo normal
- **Para adulto tercero** → pide teléfono del tercero, crea paciente separado
- **Para menor** → `is_minor=true`, phone auto-generado como `parent_phone-M1`

---

## PASO 2c: MODALIDAD DE ATENCIÓN

**Agente:** "¿Te vas a atender de forma particular o con obra social/cobertura médica?"

### Responde PARTICULAR
→ Agendar normalmente en el próximo turno disponible.

### Responde OBRA SOCIAL
→ **REGLA TEMPORAL:** Solo agendar a partir del 15 de mayo 2026.

**Agente:**
```
Por un tema técnico en el consultorio, los turnos con obra social
se están agendando a partir del 15 de mayo.
¿Te parece bien esa fecha o preferís una fecha posterior?
```

---

## PASO 3: PROFESIONAL ASIGNADO

Depende de la configuración del tratamiento:

### Un solo profesional asignado
**Agente:** "Este tratamiento lo realiza la Dra. Laura."
*(No pregunta preferencia, usa ese profesional directo)*

### Varios profesionales asignados
**Agente:** "Este tratamiento lo realizan la Dra. Laura y el Dr. Gómez. ¿Preferís alguno/a?"
- Si elige uno → `check_availability` con ese profesional
- Si dice "cualquiera" → `check_availability` sin profesional (asigna el primero disponible)

### Sin profesionales asignados
**Agente:** "¿Tenés preferencia de profesional?" o asigna el primero disponible.

---

## PASO 4: CONSULTAR DISPONIBILIDAD

El agente llama `check_availability` con los parámetros:

| Parámetro | Obligatorio | Ejemplo |
|-----------|-------------|---------|
| `date_query` | Sí | "mitad de mayo", "mañana" |
| `interpreted_date` | Sí | "2026-05-04" (calculado por el LLM) |
| `search_mode` | Sí | "exact", "week", "month", "open" |
| `treatment_name` | No | "Consulta", "Limpieza Profunda" |
| `professional_name` | No | "Laura Delgado" |
| `time_preference` | No | "mañana", "tarde" |
| `specific_time` | No | "16:30" |
| `exclude_days` | No | "viernes,lunes" |

### Respuesta típica del agente (2 opciones):

```
Te quedan estas opciones:
1️⃣ Lunes 04/05 — 13:00 hs
2️⃣ Miércoles 06/05 — 12:00 hs

Cuál te queda mejor?
```

### Qué pasa internamente:
1. Busca slots libres según el `search_mode`
2. Filtra por profesional, horario, días excluidos
3. Devuelve máximo 2-3 opciones concretas
4. **Setea estado:** `OFFERED_SLOTS` con el array de slots
5. **Guarda en Redis:** `slot_offer:{tenant}:{phone}` con `[{date, time}, ...]` (TTL 30 min)
6. Agrega `[BOOK_HINT: ...]` con el nombre del tratamiento para que `book_appointment` lo use

---

## PASO 4 → SELECCIÓN DEL PACIENTE (STATE_GUARD)

Acá es donde el `STATE_GUARD` de `buffer_task.py` interviene.

### Caso A — Paciente selecciona (FUNCIONA)

**Estado actual:** `OFFERED_SLOTS`
**Paciente:** "El lunes" / "La opción 1" / "El 1" / "Dale" / "Ese"

**Detección:** `_detect_selection_intent()` detecta la selección con 60+ patrones regex.

**El STATE_GUARD inyecta un hint al LLM:**
```
[STATE_HINT: El paciente ya tiene opciones de turno ofrecidas.
SLOTS OFRECIDOS:
  Opción 1: Lunes 04/05 — 13:00 hs [ISO: 2026-05-04 13:00]
  Opción 2: Miércoles 06/05 — 12:00 hs [ISO: 2026-05-06 12:00]

INSTRUCCIONES CRÍTICAS:
- El paciente está SELECCIONANDO uno de los turnos ofrecidos.
- DEBES llamar confirm_slot con slot_index=N
- NO llamés check_availability de nuevo.]
```

**El LLM debería llamar:** `confirm_slot(slot_index=1)`

### Caso B — Paciente rechaza (FUNCIONA)

**Estado actual:** `OFFERED_SLOTS`
**Paciente:** "No puedo ninguno de esos" / "Tenés algo el viernes?" / "Prefiero otro día"

**Detección:** `_detect_research_intent()` detecta rechazo con 33+ patrones.

**El STATE_GUARD inyecta hint de re-búsqueda:**
```
[STATE_HINT: El paciente ya tenía opciones de turno ofrecidas pero las RECHAZÓ.
INSTRUCCIONES: Llamar check_availability con la nueva preferencia.]
```

### Caso C — Pregunta lateral (FUNCIONA)

**Estado actual:** `OFFERED_SLOTS`
**Paciente:** "¿Cuánto sale la consulta?" / "¿Dónde queda?"

**Detección:** No matchea ni selección ni rechazo.

**El STATE_GUARD inyecta hint de clarificación:**
```
[STATE_HINT: El paciente tiene opciones de turno PENDIENTES.
INSTRUCCIONES:
1. Respondé la pregunta normalmente.
2. DESPUÉS recordale las opciones: 'Y respecto al turno, ¿te queda mejor el 1️⃣ o el 2️⃣?']
```

### Caso D — Estado SLOT_LOCKED (BUG ACTUAL — SIN GUARD)

**Estado actual:** `SLOT_LOCKED`
**Paciente:** "Mi DNI es 12345678" / "Rodolfo es mi nombre"

**Lo que pasa:** El STATE_GUARD solo chequea `OFFERED_SLOTS`. Para `SLOT_LOCKED` no hay handler → **el LLM no recibe contexto del slot reservado** → llama `check_availability` de nuevo → loop infinito.

---

## PASO 4b: DATOS DE ADMISIÓN

El agente necesita recolectar datos del paciente ANTES de confirmar:

### Paciente nuevo (sin datos)
**Agente:** "Para reservarte el turno necesito tu nombre y apellido."
**Paciente:** "Rodolfo González"
**Agente:** "Perfecto, Rodolfo. Y tu DNI, solo números?"
**Paciente:** "35789456"

### Paciente existente (ya tiene datos)
→ **Salta este paso completo.** Ya tiene nombre y DNI en la base.

### Regla crítica
- Pedir **DE A UN DATO POR MENSAJE** (nombre primero, DNI después)
- **NUNCA** pedir teléfono (ya lo tiene del WhatsApp)
- **NUNCA** pedir fecha de nacimiento, email o ciudad (solo si el paciente los da espontáneamente)

---

## PASO 4c: RESERVA TEMPORAL (confirm_slot)

Después de tener los datos, el LLM llama `confirm_slot`:

| Parámetro | Preferencia | Ejemplo |
|-----------|-------------|---------|
| `slot_index` | Recomendado | `1` (primera opción ofrecida) |
| `interpreted_date` | Alternativa | `"2026-05-04"` |
| `date_time` | Fallback | `"lunes 04/05 a las 13:00"` |
| `professional_name` | Opcional | `"Laura Delgado"` |
| `treatment_name` | Opcional | `"Consulta"` |

### Qué hace internamente:
1. Resuelve el slot por prioridad: `slot_index` → `interpreted_date` → `date_time`
2. Si usa `slot_index`: lee `slot_offer:{tenant}:{phone}` de Redis, convierte 1-based a 0-based
3. Crea lock en Redis: `slot_lock:{tenant}:{prof_id}:{date}:{time}` con TTL 5 minutos
4. **Setea estado:** `SLOT_LOCKED` con datos del slot
5. Retorna al LLM: `"✅ Turno de las 13:00 del Lunes 04/05 reservado. Procedé a confirmar con book_appointment."`

### Respuesta del agente al paciente:
*(El agente NO le dice al paciente que el slot está "reservado temporalmente". Simplemente procede a llamar `book_appointment` inmediatamente.)*

---

## PASO 6: AGENDAR (book_appointment)

El LLM llama `book_appointment` inmediatamente después de `confirm_slot`:

| Parámetro | Obligatorio | Ejemplo |
|-----------|-------------|---------|
| `date_time` | Sí | "13:00" |
| `treatment_reason` | Sí | "Consulta" |
| `first_name` | Sí (nuevos) | "Rodolfo" |
| `last_name` | Sí (nuevos) | "González" |
| `dni` | Sí (nuevos) | "35789456" |
| `slot_index` | Recomendado | `1` |
| `interpreted_date` | Recomendado | "2026-05-04" |
| `professional_name` | Opcional | "Laura Delgado" |
| `patient_phone` | Solo terceros | "+5491155667788" |
| `is_minor` | Solo menores | `true` |
| `is_art` | Solo ART | `true` |

### Validaciones internas:
1. **R1 — Slot ofrecido:** Verifica que el slot pedido exista en `slot_offer:{tenant}:{phone}`. Si no → `"AVAILABILITY_EXPIRED"` o `"SLOT_NOT_OFFERED"`.
2. **Conflicto de horario:** Verifica que no haya otra cita en ese horario con ese profesional.
3. **Slot lock:** Verifica que el `slot_lock` sea del mismo paciente.

### Post-booking:
- **Setea estado:** `PAYMENT_PENDING` (si tiene seña) o `BOOKED` (si no tiene)
- Genera token de anamnesis si no existe
- Calcula seña (50% del precio del profesional o del tenant)

---

## PASO 7: CONFIRMACIÓN

### Ejemplo — Booking exitoso SIN seña:

**Agente:**
```
✅ Turno confirmado para Rodolfo González:
🦷 Consulta
📅 Lunes 04/05 a las 13:00
👩‍⚕️ Con Laura
📍 Consultorio Central — Av. San Martín 1234

Para completar tu ficha médica antes de la consulta, ingresá acá:
https://app.dralauradelgado.com/anamnesis/1/abc-123-uuid

Recordá traer DNI y llegar 10 min antes.
```

### Ejemplo — Booking exitoso CON seña:

**Agente:**
```
✅ Turno confirmado para Rodolfo González:
🦷 Limpieza Profunda
📅 Miércoles 06/05 a las 12:00
👩‍⚕️ Con Laura
📍 Consultorio Central — Av. San Martín 1234
💰 Consulta: $15.000

Para confirmar tu turno, necesitamos una seña de $7.500.

Datos para transferencia:
Alias: clinica.delgado
CBU: 0000003100012345678901
Titular: Laura Delgado

Una vez que hagas la transferencia, enviame el comprobante por acá
y lo verificamos al instante 😊

Para completar tu ficha médica:
https://app.dralauradelgado.com/anamnesis/1/abc-123-uuid
```

---

## ESCENARIOS COMPLETOS

### Escenario 1: Flujo feliz (paciente nuevo, sin complicaciones)

```
👤 Hola, quiero un turno para consulta
🤖 Hola 😊 Soy Paula, la asistente virtual de Clínica Dra. Laura Delgado.
   ¿Te vas a atender de forma particular o con obra social?

👤 Particular
🤖 Este tratamiento lo realiza la Dra. Laura.
   Te busco disponibilidad...

   Te quedan estas opciones:
   1️⃣ Lunes 04/05 — 13:00 hs
   2️⃣ Miércoles 06/05 — 12:00 hs
   Cuál te queda mejor?

👤 El lunes
🤖 Para reservarte el turno necesito tu nombre completo.

👤 Rodolfo González
🤖 Perfecto, Rodolfo. Y tu DNI, solo números?

👤 35789456
🤖 ✅ Turno confirmado para Rodolfo González:
   🦷 Consulta
   📅 Lunes 04/05 a las 13:00
   👩‍⚕️ Con Laura
   📍 Consultorio Central

   Para completar tu ficha médica:
   https://app.dralauradelgado.com/anamnesis/1/abc-uuid

   Recordá traer DNI y llegar 10 min antes.
```

**Tools llamadas:** `list_services` → `check_availability` → `confirm_slot(slot_index=1)` → `book_appointment(slot_index=1, ...)`

---

### Escenario 2: Paciente existente (ya tiene datos)

```
👤 Hola necesito un turno para limpieza
🤖 Hola 😊 Soy Paula.
   ¿Te atendés de forma particular o con obra social?

👤 Particular
🤖 Te busco disponibilidad para Limpieza Profunda...

   1️⃣ Jueves 08/05 — 10:00 hs
   2️⃣ Viernes 09/05 — 15:00 hs
   Cuál te queda mejor?

👤 El jueves
🤖 ✅ Turno confirmado para María López:
   🦷 Limpieza Profunda
   📅 Jueves 08/05 a las 10:00
   👩‍⚕️ Con Laura
   💰 Consulta: $15.000

   Para confirmar, necesitamos una seña de $7.500.
   Alias: clinica.delgado
   Titular: Laura Delgado
```

**Diferencia:** No pide nombre ni DNI (ya los tiene). Salta directo de selección a confirm_slot + book_appointment.

---

### Escenario 3: Paciente rechaza opciones

```
👤 Quiero turno para el viernes
🤖 1️⃣ Viernes 09/05 — 10:00 hs
   2️⃣ Viernes 09/05 — 15:00 hs
   Cuál te queda mejor?

👤 No puedo a esas horas, tenés algo a las 12?
🤖 Dejame buscar...
   Lamentablemente a las 12:00 del viernes no hay disponibilidad.
   Te puedo ofrecer:
   1️⃣ Viernes 09/05 — 11:30 hs
   2️⃣ Lunes 12/05 — 12:00 hs
   ¿Alguna de estas te sirve?

👤 El lunes a las 12
🤖 Para reservarte necesito tu nombre completo...
```

**STATE_GUARD:** Detecta `_detect_research_intent` → inyecta hint de re-búsqueda → LLM llama `check_availability` con la nueva preferencia.

---

### Escenario 4: Pregunta lateral durante selección

```
🤖 1️⃣ Lunes 04/05 — 13:00 hs
   2️⃣ Miércoles 06/05 — 12:00 hs
   Cuál te queda mejor?

👤 Cuánto sale la consulta?
🤖 La consulta tiene un valor de $15.000.
   Y respecto al turno, ¿te queda mejor el 1️⃣ o el 2️⃣?

👤 El 1
🤖 Para reservarte necesito tu nombre...
```

**STATE_GUARD:** No detecta selección ni rechazo → inyecta hint de clarificación con recordatorio de slots pendientes.

---

### Escenario 5: Urgencia / dolor (triage)

```
👤 Me duele mucho la muela, necesito turno urgente
🤖 Hola 😊 Soy Paula, la asistente virtual de Clínica Dra. Laura Delgado.
   Entiendo, vamos a ayudarte a resolverlo lo antes posible.
   Hace cuánto tiempo estás con dolor y si notás inflamación?

👤 Desde ayer y sí, está hinchado
🤖 Por los síntomas que describís (dolor + inflamación), es recomendable
   que te vea un profesional lo antes posible.

   Te puedo ofrecer:
   1️⃣ Hoy Jueves 01/05 — 16:00 hs
   2️⃣ Mañana Viernes 02/05 — 09:00 hs
   ¿Cuál preferís?
```

**Tools:** `triage_urgency` + `check_availability("Consulta", search_mode="open")` → ofrece lo más pronto posible.

---

### Escenario 6: Turno para menor (hijo/a)

```
👤 Necesito turno para mi hijo
🤖 ¿Cuántos años tiene?

👤 8 años, le duele una muela
🤖 Entendido. ¿Te atendés de forma particular o con obra social?

👤 Particular
🤖 1️⃣ Lunes 04/05 — 10:00 hs
   2️⃣ Martes 05/05 — 14:00 hs

👤 El martes
🤖 ¿Cómo se llama tu hijo/a?

👤 Tomás González
🤖 Y su DNI?

👤 55123456
🤖 ✅ Turno confirmado para Tomás González:
   🦷 Consulta
   📅 Martes 05/05 a las 14:00
   👩‍⚕️ Con Laura

   Ficha médica de Tomás:
   https://app.dralauradelgado.com/anamnesis/1/minor-uuid
```

**Diferencia:** `book_appointment(is_minor=true)` → phone auto-generado como `+5492994529972-M1`, `guardian_phone` apunta al padre/madre.

---

### Escenario 7: Turno para adulto tercero

```
👤 Necesito turno para mi esposa
🤖 ¿Tu esposa tiene WhatsApp propio?

👤 Sí, su número es 11 5566 7788
🤖 1️⃣ Lunes 04/05 — 13:00 hs
   2️⃣ Miércoles 06/05 — 12:00 hs

👤 El lunes
🤖 ¿Cómo se llama tu esposa?

👤 Ana García
🤖 Y su DNI?

👤 30456789
🤖 ✅ Turno confirmado para Ana García (solicitado por Rodolfo):
   🦷 Consulta
   📅 Lunes 04/05 a las 13:00
   👩‍⚕️ Con Laura
```

**Diferencia:** `book_appointment(patient_phone="+5491155667788")` → crea paciente separado con el phone del tercero.

---

### Escenario 8: Obra social (regla temporal)

```
👤 Hola quiero turno
🤖 Hola 😊 Soy Paula.
   ¿Te vas a atender de forma particular o con obra social?

👤 Con obra social
🤖 Por un tema técnico en el consultorio, los turnos con obra social
   se están agendando a partir del 15 de mayo.
   ¿Te parece bien esa fecha o preferís una fecha posterior?

👤 Sí, dale el 15
🤖 1️⃣ Jueves 15/05 — 10:00 hs
   2️⃣ Jueves 15/05 — 14:00 hs
   Cuál te queda mejor?
```

---

### Escenario 9: Pago con seña (post-booking)

```
(... después del booking con seña ...)
🤖 Para confirmar, necesitamos una seña de $7.500.
   Alias: clinica.delgado
   Titular: Laura Delgado
   Enviame el comprobante por acá 😊

👤 [envía foto del comprobante de transferencia]
🤖 ✅ Comprobante verificado correctamente.
   Tu turno del Lunes 04/05 a las 13:00 quedó confirmado.
   ¡Te esperamos!
```

**Tool:** `verify_payment_receipt` → verificación por visión (holder name fuzzy match + monto ≥ seña).

---

## BUGS CONOCIDOS (al 2026-05-01)

### BUG CRÍTICO: Loop infinito de slots

**Síntoma:** El agente repite las opciones de turno indefinidamente aunque el paciente elija una.

**Causa raíz:** El `STATE_GUARD` en `buffer_task.py` solo tiene handler para el estado `OFFERED_SLOTS`. Cuando `confirm_slot` cambia el estado a `SLOT_LOCKED` y el paciente envía otro mensaje (ej: su DNI), el guard no tiene handler para `SLOT_LOCKED` → no inyecta contexto → el LLM no sabe que hay un slot reservado → llama `check_availability` de nuevo → loop.

**Estados sin guard:** `SLOT_LOCKED`, `BOOKED`, `PAYMENT_PENDING`, `PAYMENT_VERIFIED`.

**Ubicación del bug:** `buffer_task.py:1514` — solo chequea `if prev_state_str == "OFFERED_SLOTS"`.

### BUG SECUNDARIO: Timing del confirm_slot

**Síntoma:** El prompt dice "SOLO después de tener los datos del paciente, llamá confirm_slot", pero si el paciente es NUEVO, la secuencia sería: elige slot → pide datos → confirm_slot → book_appointment. Entre la elección y el confirm_slot pueden pasar varios mensajes (pidiendo nombre, DNI), y durante ese tiempo NO hay lock → otro paciente puede tomar el slot.

**Pero con paciente existente** (que ya tiene datos): elige slot → confirm_slot → book_appointment de inmediato. Funciona bien.

---

## ARCHIVOS CLAVE

| Archivo | Líneas | Qué hace |
|---------|--------|----------|
| `services/buffer_task.py` | 103-180 | `_detect_selection_intent()` — 60+ patrones de selección |
| `services/buffer_task.py` | 183-238 | `_detect_research_intent()` — 33+ patrones de rechazo |
| `services/buffer_task.py` | 1499-1596 | Input-side STATE_GUARD |
| `services/buffer_task.py` | 2299-2380 | Output-side STATE_GUARD |
| `services/conversation_state.py` | completo | Máquina de estados (get/set/transition/reset) |
| `main.py` | 1586-2710 | `check_availability` |
| `main.py` | 2790-4300 | `book_appointment` |
| `main.py` | 6070-6268 | `confirm_slot` |
| `main.py` | 9143-9184 | Greetings por tipo de paciente |
| `main.py` | 9479-9485 | Flujo de urgencia (F2) |
| `main.py` | 9650-9820 | PASOS del flujo de agendamiento |
