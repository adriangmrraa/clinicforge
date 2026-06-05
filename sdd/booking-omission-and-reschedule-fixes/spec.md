# Booking Omission and Reschedule Fallback Fixes

## 1. Contexto y Objetivos
- **Problema:** 
  1. **Omisión de `book_appointment` tras la entrega del DNI:** Al finalizar el agendamiento (cuando el slot ya fue pre-reservado mediante `confirm_slot` o está en proceso), si el paciente introduce su DNI acompañado de texto clínico (ej. dolor, descripción visual de dientes) o por coincidencia con la regla de migración de paciente existente sin datos, el LLM se distrae. Esto provoca que el LLM responda con un mensaje conversacional o active la derivación humana en lugar de llamar a `book_appointment`, resultando en la expiración del slot tras 5 minutos y amnesia del turno.
  2. **Reserva unilateral durante reprogramación:** Cuando un paciente solicita reprogramar, el agente llama a `list_my_appointments`. Si esta herramienta devuelve vacío (no hay turnos futuros), el agente no tiene un flujo de fallback claro, lo que causa que alucine un turno anterior o intente reprogramar llamando unilateralmente a `book_appointment` o `reschedule_appointment` sin consentimiento o con datos ficticios.
- **Solución:**
  1. En las system prompts de `main.py` y `specialists.py` (`BookingAgent`), implementar una **REGLA DE CONFIRMACIÓN CON DNI (CRÍTICA E INQUEBRANTABLE)** para priorizar la ejecución inmediata de la tool `book_appointment` cuando se provean los datos de confirmación, ignorando descripciones clínicas y prohibiendo el disparo de la regla de migración en esta interacción específica.
  2. Implementar una regla de fallback explícita para la reprogramación en ambos archivos. Si `list_my_appointments` devuelve que no existen turnos futuros activos, el bot debe reportar esto de forma clara y amable al paciente, y preguntar si desea agendar una nueva cita desde cero, deteniendo cualquier intento unilateral de agendamiento.
- **KPIs:** 
  - 100% de llamadas exitosas a `book_appointment` inmediatamente después de ingresar el DNI con slots pre-reservados.
  - 0% de reprogramaciones unilaterales o alucinadas cuando no existen citas registradas.

## 2. Esquemas de Datos
- **Entradas:** 
  N/A (Lógica de prompts y flujos internos del LLM sobre herramientas existentes: `book_appointment`, `list_my_appointments`, `check_availability`, `reschedule_appointment`).
- **Salidas:** 
  N/A (Mensajes estructurados del bot al paciente y llamadas de herramientas).
- **Persistencia:** 
  No requiere cambios en base de datos. Se operará sobre los modelos existentes.

## 3. Lógica de Negocio (Invariantes)
- **SI** el paciente proporciona su DNI en el contexto de un slot seleccionado/pre-reservado **ENTONCES** el agente DEBE llamar a `book_appointment` de inmediato en ese mismo turno.
- **RESTRICCIÓN:** Queda prohibido responder de forma puramente conversacional o con contención clínica, o activar la regla de migración/derivación humana antes de realizar la llamada a la tool `book_appointment` cuando el DNI fue provisto para confirmar.
- **SI** `list_my_appointments` no devuelve turnos futuros activos en un flujo de reprogramación **ENTONCES** el agente DEBE notificar al paciente y preguntar si desea iniciar el agendamiento de un nuevo turno.
- **RESTRICCIÓN:** Queda prohibido inventar o alucinar datos de turnos previos, llamar a `reschedule_appointment` con datos ficticios, o agendar de forma unilateral un slot si no se encuentran turnos futuros.

## 4. Stack y Restricciones
- **Tecnología:** FastAPI, LangChain AgentExecutor, OpenAI GPT-4o / DeepSeek (modelos inyectados por configuración).
- **Soberanía:** El aislamiento de datos se mantiene mediante los filtros `tenant_id` integrados en todas las llamadas a base de datos de las tools (ej. `list_my_appointments` filtra por el tenant de la conversación).

## 5. Criterios de Aceptación (Gherkin)
- **Escenario 1: Confirmación de turno inmediata al proveer DNI con texto clínico**
  - DADO que un paciente eligió una opción de turno y el slot fue lockeado por `confirm_slot`
  - CUANDO el paciente envía un mensaje con su DNI y una descripción clínica (ej: "Mi DNI es 12345678, y además me duele muchísimo la muela de abajo")
  - ENTONCES el agente debe ejecutar inmediatamente la herramienta `book_appointment` con el DNI provisto
  - Y no debe emitir contención clínica ni disparar derivaciones por migración en ese turno hasta haber confirmado el turno.

- **Escenario 2: Intento de reprogramación sin turnos activos futuros**
  - DADO que un paciente no tiene turnos futuros registrados en el sistema
  - CUANDO el paciente solicita reprogramar su turno (ej: "Hola, quiero cambiar la fecha de mi turno")
  - ENTONCES el agente ejecuta la tool `list_my_appointments`
  - Y al recibir una respuesta vacía o sin citas futuras, el agente informa: "No encuentro ningún turno agendado a tu nombre en el sistema."
  - Y pregunta amablemente al paciente si desea coordinar un nuevo turno desde cero
  - Y no ejecuta ninguna llamada unilateral de agendamiento (`book_appointment` o `reschedule_appointment` con datos inventados).
