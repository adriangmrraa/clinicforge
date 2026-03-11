# Estado Actual del Agente de IA - Dentalogic (Marzo 2026)

Este documento contiene la "foto actual" del comportamiento del Agente de IA, su **System Prompt**, las **Tools** de las que dispone, y la explicación detallada de cómo gestiona flujos complejos como la **Admisión de Pacientes Nuevos** y la **Muestra de Servicios/Imágenes**.

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
Si el paciente pregunta *"qué hacen"* o *"qué servicios tienen"*, la IA ejecuta la tool **`list_services`**.
- Devuelve la lista de tipos de tratamiento activos en la clínica junto con su duración media (Ej. *Limpieza Profunda (45 min): Tratamiento preventivo...*).
- **El System Prompt le PROHÍBE ofrecer servicios que no devuelve esta tool.**

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

*Fin del Snapshot del Agente.*
