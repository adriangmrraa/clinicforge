# Estado Actual del Agente de IA - ClinicForge / Dra. Laura Delgado (Marzo 2026 — Sprint v2)

Este documento contiene la "foto actual" del comportamiento del Agente de IA, su **System Prompt**, las **Tools** de las que dispone, y la explicación detallada de cómo gestiona flujos complejos como la **Admisión de Pacientes Nuevos**, la **Muestra de Servicios/Imágenes** y la **Visualización de Anamnesis en la UI**.

---

## 1. System Prompt Principal (Resumen de Lógica)

El Agente opera impulsado por un *System Prompt* dinámico e inyectado en cada invocación a través de LangChain (`get_agent_executable` en `main.py`).

**Identidad y Tono:**
- Se presenta SÓLO como: "Secretaria virtual de la Dra. María Laura Delgado" (Cirujana Maxilofacial e Implantóloga en Neuquén).
- Usa voseo rioplatense (ej. "Tenés", "Podés", "Mirá") y actitud cálida, empática pero profesional.
- **Idioma Dinámico**: El prompt inyecta reglas estrictas para responder únicamente en el idioma detectado del paciente (Español, Inglés o Francés).
- **Puntuación**: Tiene prohibido usar signos de apertura (`¿`, `¡`) para simular un comportamiento humano más natural de chat.

**Reglas de Oro del Prompt:**
1. **NUNCA INVENTAR**: No inventa horarios, no inventa profesionales, ni inventa servicios. Todo debe provenir de las herramientas (Tools).
2. **REGLA ANTI-PASADO**: Bloquea cognitivamente al modelo para no intentar agendar turnos en horarios pasados.
3. **NO DIAGNOSTICAR**: Se limita a realizar un *Triage* derivando diagnósticos definitivos a la doctora.
4. **DERIVACIÓN**: Deriva a humano mediante la tool `derivhumano` ante enojos, solicitud explícita, o urgencias críticas confirmadas.

---

## 2. Flujo Completo: Admisión de Paciente Nuevo y Anamnesis

El proceso de admisión es estricto y el System Prompt fuerza al LLM a pedir datos **"De a UNO por mensaje"** para mantener la naturalidad tipo WhatsApp.

### **Paso A: Recolección de Datos Duros (Antes de agendar)**
Cuando un paciente elige un horario para un tratamiento, la IA le va consultando iterativamente:
1. Nombre
2. Apellido
3. DNI (solo números)
4. Fecha de Nacimiento (DD/MM/AAAA)
5. Email
6. Ciudad/Barrio
7. Cómo nos conoció (Instagram, Google, Referido, Otro)

*Una vez recolectados esos 7 datos, el agente dispara la tool `book_appointment`, la cual registra el turno y crea la ficha del paciente en PostgreSQL.*

### **Paso B: Anamnesis Médica (Inmediatamente después de agendar)**
Cuando `book_appointment` retorna éxito, el prompt obliga a la IA a decir: *"¡Listo! Ya tenemos tu ficha. Ahora te hago unas preguntas de salud..."*

Luego, iterativamente, recaba:
1. Enfermedades de base
2. Medicación habitual
3. Alergias
4. Cirugías previas
5. Hábito de fumar (y cantidad)
6. Embarazo/Lactancia
7. Experiencias odontológicas negativas previas
8. Miedos específicos

*Al finalizar esta ronda, el agente dispara u llama a la tool `save_patient_anamnesis` guardando este historial directamente en la base de datos (campo JSONB `medical_history`).*

---

## 3. Catálogo de Servicios e Imágenes (Visualización)

La gestión de los tratamientos ofertados no está "hardcodeada" en la memoria del agente, sino que consulta la base de datos en tiempo real.

### **A. Cómo muestra los servicios**
El comportamiento depónde del tipo de consulta:
- Si el paciente pregunta **en general** ("qué hacen", "qué servicios tienen") → la IA ejecuta **`list_services`** → devuelve **solo los nombres** de tratamientos activos, sin descripción ni duración → termina invitando a preguntar por uno concreto.
- Si el paciente pregunta **por un servicio específico** → la IA ejecuta **`get_service_details(code)`** → el sistema envía texto extenso + imágenes automáticamente.
- **El System Prompt le PROÍBE ofrecer servicios que no devuelve esta tool.**

### **B. Cómo se gestionan y envían las fotos de los servicios**
Si el paciente pregunta detalles específicos de un servicio (Ej. *"Quiero saber más sobre ortodoncia"* o *"Tenés fotos de los implantes?"*), la IA ejecuta la tool **`get_service_details(code)`**.

1. La tool busca en la base de datos el nivel de complejidad y detalles profundos.
2. Consulta la tabla `treatment_images` para ver si hay fotos asociadas.
3. Si hay fotos, la tool devuelve al LLM el siguiente tag "invisible" en formato Markdown:
   `[LOCAL_IMAGE:http://url-publica-de-la-api/media/uuid]`
4. **Intercepción del Parser**: El LLM, siguiendo sus instrucciones, responde al usuario y regurgita este string `[LOCAL_IMAGE:...]` en su respuesta final. Estando en `buffer_task.py`, el *Orchestrator* intercepta este patrón mediante expresiones regulares (Regex). 
5. Si lo detecta, elimina el texto de la respuesta escrita del LLM (para que el humano no vea el string raro) y genera las llamadas correspondientes a la API de **YCloud** (WhatsApp) para enviar dichas URLs de imagen como mensajes fotográficos ("Media").

---

## 4. Repositorio de Tools disponibles para el Agente

La lista completa de `DENTAL_TOOLS` en `main.py` es la siguiente:

1. **`check_availability`**: Busca huecos combinando agenda local (PostgreSQL) y reservas de Google Calendar (Sistema híbrido JIT).
2. **`book_appointment`**: Ejecuta la reserva final de un turno + inserción de pacientes. Controla que el DNI o el Email sean válidos y emite los eventos visuales para el Dashboard (WebSockets).
3. **`list_services`**: Catálogo general de los procedimientos habilitados para agendar.
4. **`get_service_details`**: Inmersión en un servicio, retornando imágenes adjuntas vía `LOCAL_IMAGE`.
5. **`list_professionals`**: Retorna el personal activo; útil para pacientes que buscan un doctor/doctora en particular.
6. **`list_my_appointments`**: Permite a un paciente consultar su estado actual de turnos futuros.
7. **`reschedule_appointment`**: Mueve un turno a otra fecha validando colisiones en el proceso.
8. **`cancel_appointment`**: Libera el slot de la agenda para que otro paciente pueda utilizarlo.
9. **`triage_urgency`**: Tool analítica. Transforma un relato de dolor del paciente en nivel de urgencia (`high`, `emergency`, `normal`, `low`). Modifica el UI marcando alertas rojas a la secretaria física si es riesgo vital o urgencia severa.
10. **`save_patient_anamnesis`**: Anexa la entrevista médica recopilada por la IA al legajo clínico del paciente.
11. **`derivhumano`**: Handoff manual a la secretaria física o a recepción. Envía correos de notificación e instruye a la IA a dejar de responder provisoriamente.

---

## 5. Visualización de Anamnesis en la UI (Sprint v2 — 2026-03-11)

La anamnesis fue únicamente gestionada por la IA (guardado en `medical_history` JSONB) hasta el Sprint v2. Ahora **es visible en 3 puntos del frontend** mediante el componente reutilizable `AnamnesisPanel.tsx`:

| Punto | Archivo | Modo | Edición |
|:---|:---|:---|:---|
| Panel derecho en `/chats` | `ChatsView.tsx` | Compact (sólo lectura) | ❌ |
| 4ª tab en Detalle Paciente | `PatientDetail.tsx` | Expanded | CEO / Profesional asignado ✅ |
| Tab Anamnesis en turno | `AppointmentForm.tsx` | Expanded (sólo lectura) | ❌ |

**Nuevos endpoints backend (`admin_routes.py`):**
- `GET /admin/patients/by-phone/{phone}` — Busca paciente por teléfono e incluye `medical_history`
- `PATCH /admin/patients/{patient_id}/anamnesis` — Actualiza anamnesis con RBAC (CEO = cualquiera; profesional = solo sus pacientes)

**Reglas de alerta visual:**
- `allergies` ≠ null / "No" → badge rojo 🔴
- `habitual_medication` ≠ null / "No" → badge naranja 🟠
- `pregnancy_lactation` ≠ null / "No" → badge rojo 🔴
- `medical_history == null` → mensaje "Sin anamnesis" + botón recordatorio

---

## 6. Cambios en System Prompt (Sprint v2 — 2026-03-11)

| Aspecto | Antes | Después |
|:---|:---|:---|
| FAQs en prompt | 4 preguntas frecuentes | 13 FAQs specs del consultorio |
| Ejemplo de tono | Contenía `¿` (bug) | Corregido: voseo sin `¿` ni `¡` |
| Ejemplos conversación | Ninguno | 2 conversaciones ideales incluidas |
| Lista de servicios | Devuelve descripción completa | Solo nombres; detalle via `get_service_details` |
| Imagen por servicio | No activada por el agente | Regla explícita: llamar `get_service_details` para servicios concretos |

*Fin del Snapshot del Agente.*
