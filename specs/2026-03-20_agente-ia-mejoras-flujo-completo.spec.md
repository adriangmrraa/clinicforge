# Mejoras Integrales del Agente de IA — Flujo Completo
> Origen: Conversación con CEO (2026-03-20) — Requerimientos de flujo comercial para Dra. Laura Delgado

## 1. Contexto y Objetivos

- **Problema:** El agente de IA tiene un saludo genérico que no diferencia entre leads nuevos y pacientes existentes. No tiene flujo de triage comercial para implantes/prótesis. No maneja objeciones (precio, miedo). La Dra. trabaja en 2 sedes según el día (Salta L-M-J-V, Córdoba Miércoles) pero solo hay una sede en la plataforma. La anamnesis por chat es larga y fricciona la conversación.

- **Solución:** 10 mejoras integradas:
  1. Greeting diferenciado (lead/paciente sin turno/paciente con turno futuro)
  2. Triage comercial de implantes/prótesis con opciones visibles + emojis
  3. Manejo de objeciones (precio y miedo)
  4. Flujo de conversión a consulta
  5. Multi-sede por día en working_hours (tenant + profesional)
  6. Confirmación con sede correcta según día
  7. Página pública de anamnesis (checklist mobile-friendly)
  8. Endpoint público para guardar anamnesis desde formulario
  9. Reemplazar cuestionario de anamnesis por link en flujo del agente
  10. AI lee anamnesis completada y la confirma al paciente

- **KPIs:**
  - Tasa de conversión lead → turno agendado (mejora esperada con triage + objeciones)
  - Reducción de abandono en flujo de anamnesis (link vs interrogatorio)
  - Cero errores de sede en confirmaciones de turno

## 2. Esquemas de Datos

### 2.1 Tenant working_hours (JSONB) — Extensión con ubicación por día

```json
{
  "monday": {
    "enabled": true,
    "slots": [{"start": "09:00", "end": "12:00"}, {"start": "14:00", "end": "18:00"}],
    "location": "Sede Salta",
    "address": "Av. Salta 123, Resistencia, Chaco",
    "maps_url": "https://maps.google.com/..."
  },
  "wednesday": {
    "enabled": true,
    "slots": [{"start": "09:00", "end": "13:00"}],
    "location": "Sede Córdoba",
    "address": "Av. Córdoba 456, Resistencia, Chaco",
    "maps_url": "https://maps.google.com/..."
  }
}
```

**Regla de fallback:** Si un día NO tiene `location`/`address`/`maps_url`, se usa `tenants.address` y `tenants.google_maps_url` como default (comportamiento actual).

### 2.2 Professional working_hours (JSONB) — Extensión opcional con ubicación

Misma estructura que tenant. Si el profesional tiene `location` en un día, se usa esa. Si no, se hereda del tenant para ese día.

**Cadena de resolución de ubicación:**
1. `professional.working_hours[day].location` (si existe)
2. `tenant.working_hours[day].location` (si existe)
3. `tenant.address` + `tenant.google_maps_url` (fallback global)

### 2.3 Página pública de anamnesis

**URL formato:** `/anamnesis/{tenant_id}/{token}`
- `token` = hash seguro derivado del `patient_id` + `tenant_id` + secret (no DNI en URL por seguridad)
- Alternativa simple: UUID generado al momento de agendar, guardado en `patients.anamnesis_token`

**Nuevos campos en DB:**
```sql
-- patients
anamnesis_token UUID DEFAULT NULL

-- tenants
consultation_price DECIMAL(12,2) DEFAULT NULL
```

**Nueva variable de entorno:**
```
FRONTEND_URL=https://app.dralauradelgado.com  (sin trailing slash)
```

**Entradas (formulario):**
```typescript
interface AnamnesisFormData {
  base_diseases: string[];        // checklist: diabetes, hipertension, cardiopatia, etc.
  habitual_medication: string;    // texto libre
  allergies: string[];            // checklist: penicilina, latex, anestesia, etc. + otro
  previous_surgeries: string;     // texto libre
  is_smoker: "si" | "no";
  smoker_amount?: string;
  pregnancy_lactation: "si" | "no" | "no_aplica";
  negative_experiences: string;   // texto libre
  specific_fears: string[];       // checklist: agujas, dolor, ruido del torno, etc. + otro
}
```

**Salidas:** Guarda en `patients.medical_history` JSONB (mismo formato actual).

### 2.4 Patient context para el agente — Extensión

El `patient_context` inyectado en el system prompt se extiende con:
- `is_new_lead: bool` — Si no existe en tabla patients
- `has_past_appointments: bool` — Si tiene turnos en el pasado
- `has_future_appointments: bool` — Si tiene turnos en el futuro
- `anamnesis_completed: bool` — Si `medical_history` tiene datos

## 3. Lógica de Negocio (Invariantes)

### 3.1 Greeting diferenciado
- SI el usuario NO es paciente registrado → "¿En qué tipo de consulta estás interesado?"
- SI es paciente SIN turno futuro (pero con historial) → "¿En qué podemos ayudarte hoy?"
- SI es paciente CON turno futuro → Comentario sobre su turno próximo (fecha, hora, sede, tratamiento) + "te esperamos en [sede] a las [hora] para [tratamiento]"

### 3.2 Triage de implantes
- SI el lead/paciente menciona implantes, prótesis, o tratamientos relacionados → Activar flujo de triage
- ENVIAR opciones con emojis (OBLIGATORIO mostrar opciones):
  - 🦷 Perdí un diente
  - 🦷🦷 Perdí varios dientes
  - 🔄 Uso prótesis removible
  - 🔧 Necesito cambiar una prótesis
  - 😣 Tengo una prótesis que se mueve
  - 🤔 No estoy seguro
- PROFUNDIZACIÓN: "¿Hace cuánto tiempo tenés este problema?"
- POSICIONAMIENTO: Mensaje sobre la Dra. Laura Delgado y sus especialidades

### 3.3 Manejo de objeciones
- SI pregunta precio → Respuesta empática + explicar evaluación personalizada + valor consulta desde `tenants.consultation_price` (dinámico, configurable desde UI)
- SI `consultation_price` es NULL o 0 → omitir precio, decir "consultá directamente con la clínica"
- SI expresa miedo → Respuesta empática + tecnología moderna + anestesia sin agujas + testimonios

### 3.4 Conversión a consulta
- Preguntar: "¿Querés que coordinemos una consulta de evaluación con la Dra. Laura Delgado?"
- Las opciones (Sí quiero agendar / Ver horarios) NO se envían visiblemente, son internas del agente

### 3.5 Multi-sede
- RESTRICCIÓN: La sede se determina por el DÍA del turno, NO por elección del paciente
- SI turno es Miércoles → Sede Córdoba (según tenant.working_hours.wednesday)
- SI turno es L/M/J/V → Sede Salta (según tenant.working_hours del día correspondiente)
- SOBERANÍA: `tenant_id` siempre desde JWT/context, nunca del request

### 3.6 Confirmación con sede
- El mensaje de confirmación DEBE incluir: fecha, hora, sede (nombre + dirección + maps)
- Después de confirmar → enviar link de anamnesis

### 3.7 Anamnesis por link
- ELIMINAR PASO 8 y PASO 9 del flujo de agendamiento
- REEMPLAZAR con: enviar link público de formulario de anamnesis
- El link es único por paciente (token UUID)
- El formulario es mobile-friendly, tipo checklist
- SI el paciente confirma que completó el formulario → el agente lee los datos y confirma

## 4. Stack y Restricciones

### Backend
| Archivo | Cambio |
|---------|--------|
| `orchestrator_service/main.py` | Modificar `build_system_prompt`: greeting, triage implantes, objeciones, conversión, multi-sede, eliminar PASO 8-9, agregar paso de link anamnesis |
| `orchestrator_service/main.py` | Modificar `book_appointment`: incluir sede en confirmación, generar anamnesis_token |
| `orchestrator_service/main.py` | Modificar `check_availability`: devolver sede del día consultado |
| `orchestrator_service/services/buffer_task.py` | Extender patient_context con is_new_lead, has_past_appointments, anamnesis_completed, sede del día |
| `orchestrator_service/admin_routes.py` | Nuevo endpoint público `GET /public/anamnesis/{tenant_id}/{token}` (sin auth) |
| `orchestrator_service/admin_routes.py` | Nuevo endpoint público `POST /public/anamnesis/{tenant_id}/{token}` (sin auth) |
| `orchestrator_service/models.py` | Agregar `anamnesis_token` a Patient |
| `orchestrator_service/alembic/versions/` | Nueva migración para `anamnesis_token` |

### Frontend
| Archivo | Cambio |
|---------|--------|
| `frontend_react/src/views/AnamnesisPublicView.tsx` | NUEVO — Página pública de formulario checklist |
| `frontend_react/src/App.tsx` | Agregar ruta pública `/anamnesis/:tenantId/:token` |

### API — Endpoints nuevos
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/public/anamnesis/{tenant_id}/{token}` | NONE | Obtener datos del paciente + preguntas |
| POST | `/public/anamnesis/{tenant_id}/{token}` | NONE | Guardar respuestas de anamnesis |

## 5. Criterios de Aceptación (Gherkin)

### Escenario 1: Lead nuevo escribe "Hola"
- DADO que el número de teléfono NO está registrado en patients
- CUANDO envía "Hola"
- ENTONCES el agente responde con el mensaje estándar + "¿En qué tipo de consulta estás interesado?"

### Escenario 2: Paciente con turno futuro escribe "Hola"
- DADO que el paciente tiene un turno el 26/03 a las 16:00 en Sede Salta
- CUANDO envía "Hola"
- ENTONCES el agente responde con el mensaje estándar + comentario sobre su turno + "te esperamos en Sede Salta a las 16:00"

### Escenario 3: Lead pregunta por implantes
- DADO que el usuario mencionó "implantes" o "prótesis"
- CUANDO el agente detecta el tema
- ENTONCES envía las 6 opciones con emojis (VISIBLES, no ocultas)

### Escenario 4: Turno agendado un Miércoles
- DADO que el paciente agenda un turno para Miércoles
- CUANDO book_appointment confirma
- ENTONCES la confirmación incluye "Sede Córdoba" con la dirección y maps correctos

### Escenario 5: Turno agendado un Martes
- DADO que el paciente agenda un turno para Martes
- CUANDO book_appointment confirma
- ENTONCES la confirmación incluye "Sede Salta" con la dirección y maps correctos

### Escenario 6: Link de anamnesis
- DADO que el paciente acaba de agendar un turno
- CUANDO recibe la confirmación
- ENTONCES recibe también un link a un formulario de anamnesis público y único
- Y cuando completa el formulario y avisa al agente
- ENTONCES el agente lee los datos guardados y confirma

### Escenario 7: Paciente pregunta por precio de implantes
- DADO que el paciente pregunta "cuánto sale un implante"
- CUANDO el agente detecta la objeción de precio
- ENTONCES responde con el guión de manejo de objeciones (evaluación personalizada + valor consulta)

## 6. Archivos Afectados

| Archivo | Tipo | Cambio |
|---|---|---|
| `orchestrator_service/main.py` | MODIFY | System prompt (greeting, triage, objeciones, sede, anamnesis link), book_appointment (sede + token), check_availability (sede) |
| `orchestrator_service/services/buffer_task.py` | MODIFY | Patient context extendido (lead/paciente/turno/anamnesis + sede del día) |
| `orchestrator_service/admin_routes.py` | MODIFY | Endpoints públicos de anamnesis |
| `orchestrator_service/models.py` | MODIFY | Patient.anamnesis_token |
| `orchestrator_service/alembic/versions/` | NEW | Migración anamnesis_token |
| `frontend_react/src/views/AnamnesisPublicView.tsx` | NEW | Formulario público |
| `frontend_react/src/App.tsx` | MODIFY | Ruta pública |
| `bff_service/index.js` | MODIFY | Proxy para ruta pública (si aplica) |

## 7. Casos Borde y Riesgos

| Riesgo | Mitigación |
|---|---|
| Tenant sin working_hours extendido (no tiene location por día) | Fallback a `tenants.address` y `tenants.google_maps_url` |
| Profesional sin location en working_hours | Hereda del tenant para ese día |
| Paciente accede a link de anamnesis de otro paciente | Token UUID único por paciente, no predecible |
| Link de anamnesis expira o paciente perdió el link | El agente puede regenerar/reenviar el link |
| Formulario completado parcialmente | Guardar lo que se envió, marcar como parcial |
| Tenant sin configuración de multi-sede (otros tenants) | Todo funciona igual que antes — fallback global |
| Agente alucina sede incorrecta | La sede viene del dato, no de la IA: check_availability y book_appointment la resuelven del working_hours |

## Clarificaciones Resueltas (2026-03-20)

### C1. Valor de consulta ($X)
**Respuesta:** NO hardcodear. Nuevo campo `consultation_price` en tabla `tenants` (DECIMAL). Configurable desde la UI en la sección de datos de la clínica/sede. El agente obtiene este valor dinámicamente al construir el system prompt (se lee junto con address, working_hours, etc.). Si el valor es NULL o 0, el agente omite el precio y dice "consultá directamente con la clínica".

### C2. Direcciones y configuración de sedes
**Respuesta:** Todo configurable desde la UI. Tanto el `working_hours` del tenant (con location/address/maps_url por día) como el del profesional se editan desde el panel de administración. Los valores se persisten en la base de datos (JSONB). NO se hardcodea ninguna dirección en el código.

### C3. Checklist de anamnesis
**Respuesta:** Usar las preguntas actuales como base + ampliar con estándar odontológico completo. El formulario se irá mejorando iterativamente. Campos actuales: base_diseases, habitual_medication, allergies, previous_surgeries, is_smoker, smoker_amount, pregnancy_lactation, negative_experiences, specific_fears. Ampliar con opciones de checklist predefinidas estándar dental.

### C4. Horarios por sede
**Respuesta:** Configurables desde la UI. Los horarios exactos de cada día (slots + sede) se gestionan desde el panel. NO se hardcodean horarios. La UI debe permitir configurar por día: habilitado/deshabilitado, slots de horario, nombre de sede, dirección y link de maps.

### C5. Dominio del link de anamnesis
**Respuesta:** Usar variable de entorno `VITE_API_URL` o `FRONTEND_URL` (no hardcodear dominio). En producción: `https://app.dralauradelgado.com/`. La ruta pública `/anamnesis/:tenantId/:token` NO aparece en el sidebar/navegación. Solo es accesible cuando el agente de IA envía el link al paciente. Optimizado para mobile.
