# Mejoras Agente IA v2.0 — ClinicForge (Dra. Laura Delgado)

> **Origen:** Audit cruzado entre `Informacion_Automatizacion_Dra_LauraDelgado.docx.md` y el código actual (`orchestrator_service/main.py`, `frontend_react/src/`).
> **Sprint:** Mejora 1 — System Prompt, Servicios e Imágenes + Visualización Anamnesis.

---

## 1. Contexto y Objetivos

- **Problema:** Tras el audit se detectaron 5 desvíos respecto a la especificación ideal del agente:
  1. **FAQs incompletas:** solo 4 de 13 preguntas frecuentes del spec están en el prompt.
  2. **Listado de servicios verboso:** `list_services` devuelve descripción completa → respuesta larga en WhatsApp.
  3. **Imágenes no activadas por el agente:** `get_service_details` existe y envía imágenes, pero el agente no lo llama cuando el paciente pregunta por un servicio concreto.
  4. **Anamnesis invisible en UI:** `patients.medical_history` se guarda correctamente pero no hay ningún componente frontend que lo muestre (ni en ChatsView ni en PatientDetail).
  5. **Signo ortográfico incorrecto en prompt:** el ejemplo de tono usa `¿` violando la POLÍTICA DE PUNTUACIÓN del propio prompt.

- **Solución:**
  1. Ampliar FAQs en `build_system_prompt`, corregir el ejemplo de tono y añadir ejemplos de conversación ideal.
  2. `list_services` → respuesta solo con nombres (sin descripción).
  3. Añadir instrucción en el prompt para llamar `get_service_details` cuando el paciente pide info de un servicio concreto.
  4. Crear `AnamnesisPanel.tsx` y añadirlo al panel derecho de `ChatsView`, y a `PatientDetailView`.
  5. Corregir `¿` en L1595 del prompt.

- **KPIs:**
  - Tasa de FAQs respondidas sin derivación humana: +40% esperado.
  - Imágenes enviadas por el bot cuando paciente consulta un servicio: de 0% → >80%.
  - Anamnesis visible por la Dra./equipo sin entrar a la BD.

---

## 2. Esquemas de Datos

### M04 — Anamnesis en Frontend

**Entrada (API — ya existe):**
```typescript
// GET /admin/patients/{id}  (responde con medical_history JSONB)
interface Patient {
  id: number;
  first_name: string;
  last_name?: string;
  phone_number: string;
  medical_history?: {
    base_diseases?: string;
    habitual_medication?: string;
    allergies?: string;
    previous_surgeries?: string;
    is_smoker?: string;
    smoker_amount?: string;
    pregnancy_lactation?: string;
    negative_experiences?: string;
    specific_fears?: string;
    anamnesis_completed_at?: string;   // ISO 8601
    anamnesis_completed_via?: string;  // "ai_assistant"
  } | null;
}
```

**Nuevo endpoint requerido (si no existe):**
```
GET /admin/patients/by-phone/{phone_number}
→ Devuelve Patient completo incluyendo medical_history
→ Requiere JWT + X-Admin-Token
→ Filtrado por tenant_id del usuario autenticado
```

**Salida (UI):**
```typescript
// Componente AnamnesisPanel — props
interface AnanamnesisField {
  key: keyof Patient['medical_history'];
  label: string;
  alert: boolean;  // true = tag rojo si hay dato
}
```

**Persistencia:** Sin cambios en BD. `patients.medical_history` (JSONB) ya existe y es donde `save_patient_anamnesis` escribe.

---

### M01/M03 — System Prompt (no hay esquema de datos, solo texto)

El system prompt es una `str` generada por `build_system_prompt()` en `orchestrator_service/main.py`. No hay cambios en BD.

---

## 3. Lógica de Negocio (Invariantes)

### Prompt / Servicios
- SI el paciente pregunta **en general** por servicios ("qué hacen", "qué tratamientos tienen") → `list_services` → responder **solo con nombres**, sin descripción, e invitar a preguntar por uno.
- SI el paciente menciona **un servicio concreto** o pide más info de uno → `get_service_details(code)` → el sistema envía imágenes automáticamente vía `[LOCAL_IMAGE:]` → buffer_task.py las intercepta.
- NUNCA usar `list_services` cuando ya se sabe cuál es el servicio concreto.
- NUNCA usar `get_service_details` para listar opciones generales.

### FAQs
- SI el paciente pregunta alguna de las 13 FAQs definidas → responder con la respuesta canónica (hardcodeada en el prompt). NO alucinar políticas adicionales.
- RESTRICCIÓN: Las FAQs son fijas y no se inventan. Si la pregunta no está cubierta, derivar con `derivhumano`.

### Anamnesis UI — 3 puntos de visualización

**Punto 1 — ChatsView (panel derecho "Clinical context"):**
- El panel derecho YA EXISTE y muestra bot status + info del lead.
- Se añade una sección "Anamnesis" debajo de la info del lead, colapsable si no hay datos.
- De solo lectura en este contexto.

**Punto 2 — Edit Appointment modal (tab "Anamnesis"):**
- El tab YA EXISTE con placeholder "Medical history available soon".
- Se debe implementar el contenido: mostrar `medical_history` del paciente del turno.
- De solo lectura para cualquier rol que pueda ver el turno.

**Punto 3 — PatientDetail (nueva 4ª pestaña "Anamnesis"):**
- Se agrega como 4ª tab junto a Clinical Summary, History and Evolution, Files and Studies.
- **EDITABLE** según rol:
  - **CEO**: puede editar todos los campos.
  - **Profesional a cargo del paciente**: puede editar sus campos.
  - **Otro profesional**: solo lectura.
  - **Secretaria**: solo lectura.

**Lógica de alertas (los 3 puntos):**
- SI `medical_history == null` → mostrar badge "Sin anamnesis".
- SI `allergies` ≠ "No"/null → badge rojo 🔴 Alergia.
- SI `habitual_medication` ≠ "No"/null → badge naranja 🟠 Medicación.
- SI `pregnancy_lactation` ≠ "No"/null → badge rojo 🔴 Embarazo/Lactancia.

**SOBERANÍA:** Todo endpoint filtra por `tenant_id` del JWT autenticado.

### Puntuación
- RESTRICCIÓN: El ejemplo de tono en el prompt **nunca** debe contener `¿` ni `¡`. Si se detecta en una revisión futura, es un bug del prompt.

---

## 4. Stack y Restricciones

- **Backend:**
  - Python 3.x, FastAPI, asyncpg.
  - `build_system_prompt()` en `orchestrator_service/main.py` (L1551–L1696).
  - Tools: `list_services` (L1305), `get_service_details` (L1334), `save_patient_anamnesis` (L1426).
  - Modelo: `gpt-4o-mini` (sin cambio).

- **Frontend:**
  - React 18, TypeScript, Tailwind CSS.
  - Nuevo componente: `frontend_react/src/components/AnamnesisPanel.tsx` (compartido entre los 3 puntos).
  - Modificar: `frontend_react/src/views/ChatsView.tsx` → añadir sección anamnesis en panel derecho (ya existe).
  - Modificar: `frontend_react/src/views/PatientDetail.tsx` → añadir 4ª tab `'anamnesis'` e interface `medical_history`.
  - Modificar: modal de turno (Edit Appointment) → implementar tab Anamnesis que ya existe como placeholder.
  - Iconos: `lucide-react` (ya instalado — usar `HeartPulse`, `AlertTriangle`, `Pill`, `Baby`, `Shield`).

- **API:**
  - `GET /admin/patients/{id}` ya existe. Verificar si serializa `medical_history`. Si no, añadirlo a la query SQL del endpoint.
  - `GET /admin/patients/by-phone/{phone}` — verificar si existe; si no, crearlo en `admin_routes.py`.
  - Filtrado obligatorio por `tenant_id` (REGLA DE SOBERANÍA).
  - Para edición de anamnesis: `PATCH /admin/patients/{id}/anamnesis` — nuevo endpoint, valida que el caller sea CEO o el profesional asignado al paciente.

- **Soberanía Multi-tenant:**
  - Toda consulta de `patients` incluye `WHERE tenant_id = $1` donde `$1` viene del JWT del usuario autenticado.
  - El agente ya usa `current_tenant_id.get()` en todas las tools → sin cambio.

---

## 5. Criterios de Aceptación (Gherkin)

### Escenario 1: FAQ — Obra social
- DADO que un paciente escribe "tienen obra social?" por WhatsApp
- CUANDO el agente procesa el mensaje
- ENTONCES responde exactamente: *"No, atendemos de forma particular, pero organizamos el pago en etapas para que sea accesible. Querés que te cuente más opciones?"*
- Y NO llama ninguna tool.

### Escenario 2: Listado general de servicios
- DADO que un paciente escribe "qué tratamientos tienen?"
- CUANDO el agente llama `list_services`
- ENTONCES la respuesta contiene **solo los nombres** de los tratamientos (ej: "• Consulta inicial\n• Implante convencional\n...") **sin descripción ni duración**.
- Y la respuesta termina con una frase como *"Sobre cuál querés más info?"*.

### Escenario 3: Detalle de servicio con imagen
- DADO que un paciente escribe "contame sobre el blanqueamiento"
- CUANDO el agente llama `get_service_details(code='blanqueamiento')`
- Y ese tratamiento tiene imágenes cargadas en `treatment_images`
- ENTONCES `buffer_task.py` intercepta los tags `[LOCAL_IMAGE:...]` y envía las imágenes por WhatsApp/Chatwoot.
- Y el agente no agrega texto adicional a las imágenes.

### Escenario 4: Signos de puntuación
- DADO que el agente genera cualquier respuesta en español
- CUANDO la respuesta contiene una pregunta
- ENTONCES el signo de interrogación aparece **solo al final** (ej: `"Cómo estás?"`)
- Y **nunca** al principio (`¿`).

### Escenario 5: Panel Anamnesis en ChatsView — con datos
- DADO que soy secretaria/CEO logueada en `/chats`
- Y tengo seleccionada la conversación de un paciente que completó la anamnesis
- CUANDO hago click en la pestaña "Anamnesis" del panel derecho
- ENTONCES veo cada campo de la anamnesis con su valor
- Y los campos `allergies`, `habitual_medication`, `pregnancy_lactation` con valor ≠ "No" muestran un badge rojo de alerta.

### Escenario 6: Panel Anamnesis en ChatsView — sin datos
- DADO que el paciente nunca completó la anamnesis (`medical_history == null`)
- CUANDO el agente/secretaria ve el panel Anamnesis
- ENTONCES ve el mensaje *"Este paciente aún no completó la anamnesis"* con botón para recordar.

### Escenario 7: Soberanía — Anamnesis
- DADO que la secretaria de Clínica A está logueada
- CUANDO consulta el panel de anamnesis de un paciente
- ENTONCES el endpoint filtra por `tenant_id` de su JWT
- Y **nunca** puede ver anamnesis de pacientes de Clínica B.

---

## 6. Archivos Afectados

| Archivo | Tipo | Cambio |
|---|---|---|
| `orchestrator_service/main.py` | MODIFY | `build_system_prompt`: 9 FAQs nuevas, ejemplos conversación, regla servicios breve, fix `¿` |
| `orchestrator_service/main.py` | MODIFY | `list_services`: formato solo nombres, docstring actualizado |
| `orchestrator_service/main.py` | MODIFY | `get_service_details`: docstring aclarado sobre cuándo usarla |
| `orchestrator_service/admin_routes.py` | MODIFY | Verificar/añadir `medical_history` en `GET /patients/{id}` |
| `orchestrator_service/admin_routes.py` | NEW | `GET /admin/patients/by-phone/{phone}` |
| `orchestrator_service/admin_routes.py` | NEW | `PATCH /admin/patients/{id}/anamnesis` (edición con control de rol) |
| `frontend_react/src/components/AnamnesisPanel.tsx` | NEW | Componente compartido: display + edición opcional, badges de alerta |
| `frontend_react/src/views/ChatsView.tsx` | MODIFY | Añadir sección anamnesis en panel derecho "Clinical context" |
| `frontend_react/src/views/PatientDetail.tsx` | MODIFY | 4ª tab "Anamnesis" + interface actualizada con `medical_history` |
| Componente modal `EditAppointment` | MODIFY | Implementar tab "Anamnesis" (actualmente dice "Medical history available soon") |

---

## 7. Casos Borde y Riesgos

| Riesgo | Mitigación |
|---|---|
| `medical_history` es `null` (paciente sin anamnesis) | UI muestra estado vacío con mensaje claro, sin errores de runtime |
| `get_service_details` llamado con `code` inválido | La tool ya maneja el caso y devuelve mensaje de error; el agente lo comunica al paciente |
| Paciente pregunta por un servicio que no existe en la plataforma | `list_services` devuelve la lista real; agente responde que no está disponible |
| El endpoint `by-phone` no existe | Verificar en `admin_routes.py`; si no existe, crearlo con el parche correspondiente |
| El agente llama `list_services` cuando debería llamar `get_service_details` | Regla explícita en el prompt con ejemplos concretos reduce la tasa de error |

---

## 8. Clarificaciones Incorporadas (/clarify — 2026-03-11)

| # | Pregunta | Respuesta | Impacto en spec |
|---|---|---|---|
| 1 | ¿Existe panel derecho en ChatsView? | ✅ Sí, "Clinical context" con bot status y lead info | Sección anamnesis se añade dentro del panel existente, no se crea un tab nuevo |
| 2 | ¿`GET /admin/patients/{id}` serializa `medical_history`? | ❓ Desconocido → se verifica al implementar | Puede requerir modificación de la query SQL en `admin_routes.py` |
| 3 | ¿FAQs configurables por tenant? | ❌ No, son fijas. Solo se usa la clínica de la Dra. Delgado por ahora | FAQs hardcodeadas en el prompt. Sin tabla en BD. |
| 4 | `list_services` ¿con descripción corta o solo nombres? | Solo nombres si la pregunta es general | `list_services` devuelve solo nombres. Para detalle, `get_service_details`. |
| 5 | ¿Anamnesis editable? | Sí: CEO puede editar siempre. Profesional puede editar solo pacientes a su cargo. Resto: solo lectura. | Nuevo endpoint `PATCH /admin/patients/{id}/anamnesis` con validación de rol |

**Hallazgos adicionales de capturas:**
- El modal "Edit Appointment" ya tiene tab "Anamnesis" con placeholder "Medical history available soon" → solo hay que implementar el contenido, no crear el tab.
- `PatientDetail` tiene 3 tabs (Clinical Summary / History and Evolution / Files and Studies) → la anamnesis va como **4ª tab nueva**.
- ChatsView tiene panel derecho "Clinical context" con `Lead (No appointments)` y `No clinical history` → la anamnesis se añade como sección expandible dentro de ese panel.

---

*Spec generada: 2026-03-11 | SDD v2.0 | Refinada con /clarify 2026-03-11*
