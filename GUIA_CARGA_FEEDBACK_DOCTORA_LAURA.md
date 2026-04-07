# Guía de Carga — Feedback Dra. Laura Delgado

> **Propósito**: Esta guía te indica EXACTAMENTE qué cargar en cada página de la plataforma ClinicForge para implementar el feedback completo de la doctora. El system prompt ya fue actualizado por código — todo lo demás se carga desde la UI.

> **Antes de empezar**: Asegurate de estar logueado como admin del tenant de la Dra. Laura Delgado.

---

## 📋 Índice

1. [Página: Tratamientos](#1-página-tratamientos-treatments)
2. [Página: Personal (Profesionales)](#2-página-personal-personal)
3. [Página: Configuración → Obras Sociales](#3-página-configuración--obras-sociales)
4. [Página: Configuración → Reglas de Derivación](#4-página-configuración--reglas-de-derivación)
5. [Página: FAQs](#5-página-faqs)
6. [Plantillas YCloud HSM (en Meta WhatsApp Manager)](#6-plantillas-ycloud-hsm)
7. [Asignación masiva de pacientes](#7-asignación-masiva-de-pacientes)

---

## 1. Página: Tratamientos (`/treatments`)

> **PRIORIDAD CRÍTICA**: La doctora pidió explícitamente que TODOS los tratamientos estén cargados con su configuración completa antes de iniciar pruebas.

Para CADA tratamiento de la lista, cargá los siguientes campos:

### 🟢 IMPLANTES (Prioridad Alta — Dra. Laura)

| Campo | Valor |
|---|---|
| **Nombre** | Implante dental |
| **Código** | `implante` |
| **Categoría** | surgical |
| **Prioridad** | `high` |
| **Profesional asignado** | Dra. Laura Delgado |
| **Duración** | 60 min |
| **Precio base** | (consultar con doctora) |

**Pre-instructions**:
```
🌿 PRE TRATAMIENTO
Comer normalmente (salvo indicación)
No consumir alcohol 24 hs antes
Informar medicación y antecedentes médicos
Mantener buena higiene bucal

📄 Si tenés estudios previos (radiografías, tomografías, derivaciones), enviálos antes de tu consulta para optimizar la planificación.
```

**Post-instructions** (timing: post inmediato):
```
🤍 POST TRATAMIENTO
Morder la gasa 30-40 minutos
No enjuagarse ni escupir por 24 hs
Aplicar frío (10 min sí / 10 min no)
Evitar actividad física el mismo día

🥣 ALIMENTACIÓN
Dieta blanda y fría
Evitar comidas calientes

🪥 HIGIENE
No enjuagar 24 hs
Luego, enjuagues suaves según indicación
Cepillar con cuidado

🚫 EVITAR
Fumar
Alcohol
Manipular la zona

🤍 ES NORMAL
Dolor leve, inflamación, sangrado leve

⚠️ CONSULTAR SI
Dolor intenso, sangrado persistente, fiebre, inflamación excesiva

💬 Estamos para acompañarte en todo el proceso 😊
```

---

### 🟢 PRÓTESIS / REHABILITACIÓN (Prioridad Alta — Dra. Laura)

| Campo | Valor |
|---|---|
| **Nombre** | Prótesis dental |
| **Código** | `protesis` |
| **Categoría** | restorative |
| **Prioridad** | `high` |
| **Profesional asignado** | Dra. Laura Delgado |
| **Duración** | 60 min |

**Pre/Post**: usar las mismas indicaciones de Cirugía si aplica.

---

### 🟢 BLANQUEAMIENTO BEYOND (Prioridad Alta cuando es Dra. Laura, Baja si es equipo)

| Campo | Valor |
|---|---|
| **Nombre** | Blanqueamiento Beyond |
| **Código** | `blanqueamiento` |
| **Categoría** | aesthetic |
| **Prioridad** | `high` |
| **Profesional asignado** | Dra. Laura Delgado |
| **Duración** | 60 min |

**Pre-instructions**:
```
🌿 PRE TRATAMIENTO
Para lograr mejores resultados:
Realizar una limpieza dental previa
Evitar alimentos con colorantes el día del turno
Informar si presentás sensibilidad dental

💛 Esto nos permite optimizar el resultado del tratamiento
```

**Post-instructions** (timing: post inmediato):
```
🤍 POST TRATAMIENTO
Acabamos de blanquear tu sonrisa ✨
Ahora comienza una etapa clave para mantener el resultado:

🥛 DIETA BLANCA (48 hs)
🚫 Evitar:
Café, mate, té
Vino tinto
Gaseosas oscuras
Salsas (tomate, soja)
Remolacha

✔️ Preferir:
Agua, lácteos, pollo, pescado, arroz

🚫 EVITAR
Fumar
Alimentos y bebidas con colorantes

😬 SENSIBILIDAD
En la mayoría de los casos no genera sensibilidad 😊
Si aparece, suele ser leve y transitoria
👉 Si es intensa o persiste, escribinos

🪥 HIGIENE
Mantener buena higiene bucal
Usar productos recomendados

💬 Estamos para acompañarte 😊
```

---

### 🟢 BOTOX (Prioridad Alta — Dra. Laura)

| Campo | Valor |
|---|---|
| **Nombre** | Botox / Aplicación de toxina botulínica |
| **Código** | `botox` |
| **Categoría** | aesthetic |
| **Prioridad** | `high` |
| **Profesional asignado** | Dra. Laura Delgado |
| **Duración** | 30-45 min |

**Pre-instructions**:
```
🌿 PRE TRATAMIENTO
Evitar alcohol 24 hs antes
No tomar antiinflamatorios si no es necesario
Informar medicación o condiciones médicas
```

**Post-instructions** (timing: post inmediato):
```
🤍 POST TRATAMIENTO
No acostarse por 4 horas
No masajear la zona
Evitar ejercicio físico 24 hs
No consumir alcohol el mismo día

💛 Los resultados comienzan a verse en pocos días
```

---

### 🟢 ARMONIZACIÓN FACIAL (Prioridad Alta — Dra. Laura)

| Campo | Valor |
|---|---|
| **Nombre** | Armonización facial |
| **Código** | `armonizacion_facial` |
| **Categoría** | aesthetic |
| **Prioridad** | `high` |
| **Profesional asignado** | Dra. Laura Delgado |
| **Duración** | 45-60 min |

**Pre-instructions**:
```
🌿 PRE TRATAMIENTO
Evitar alcohol 24 hs antes
Informar medicación
No asistir con maquillaje en la zona
```

**Post-instructions** (timing: post inmediato):
```
🤍 POST TRATAMIENTO
No masajear la zona
Evitar ejercicio físico 24 hs
Puede aparecer leve inflamación o hematomas
Evitar calor intenso

💛 Los resultados se aprecian de forma progresiva
```

---

### 🟢 ENDOLIFTING (Prioridad Alta — Dra. Laura)

| Campo | Valor |
|---|---|
| **Nombre** | Endolifting |
| **Código** | `endolifting` |
| **Categoría** | aesthetic |
| **Prioridad** | `high` |
| **Profesional asignado** | Dra. Laura Delgado |
| **Duración** | 60-90 min |

**Pre-instructions**:
```
🌿 PRE TRATAMIENTO
Informar antecedentes médicos
Evitar alcohol 24 hs antes
Asistir con la piel limpia
```

**Post-instructions** (timing: post inmediato):
```
🤍 POST TRATAMIENTO
Puede haber inflamación leve o hematomas
Aplicar frío si es necesario
Evitar ejercicio físico por 48 hs
No exponerse al sol

💛 Los resultados son progresivos en las semanas siguientes
```

---

### 🟡 CIRUGÍA MAXILOFACIAL (Prioridad Media — Dra. Laura)

| Campo | Valor |
|---|---|
| **Nombre** | Cirugía maxilofacial |
| **Código** | `cirugia_maxilofacial` |
| **Categoría** | surgical |
| **Prioridad** | `medium` |
| **Profesional asignado** | Dra. Laura Delgado |
| **Duración** | 60-90 min |

**Pre/Post**: mismas indicaciones que IMPLANTES (es cirugía bucal).

⚠️ **REGLA IMPORTANTE**: Aunque sea por obra social, NO se deriva al equipo. SIEMPRE Dra. Laura.

---

### 🔴 LIMPIEZA DENTAL (Prioridad Baja — Dra. Ester)

| Campo | Valor |
|---|---|
| **Nombre** | Limpieza dental / Profilaxis |
| **Código** | `limpieza` |
| **Categoría** | prevention |
| **Prioridad** | `low` |
| **Profesional asignado** | Dra. Ester Alberto |
| **Duración** | 45 min |

---

### 🔴 ORTODONCIA (Prioridad Baja — Dra. Ester)

| Campo | Valor |
|---|---|
| **Nombre** | Ortodoncia |
| **Código** | `ortodoncia` |
| **Categoría** | orthodontics |
| **Prioridad** | `low` |
| **Profesional asignado** | Dra. Ester Alberto |
| **Duración** | 45 min (consulta inicial) |

---

### 🔴 ENDODONCIA (Prioridad Baja — Dra. Ester)

| Campo | Valor |
|---|---|
| **Nombre** | Endodoncia / Tratamiento de conducto |
| **Código** | `endodoncia` |
| **Categoría** | restorative |
| **Prioridad** | `low` |
| **Profesional asignado** | Dra. Ester Alberto |
| **Duración** | 60 min |

---

### 🔴 CARIES / EMPASTES (Prioridad Baja — Dra. Ester)

| Campo | Valor |
|---|---|
| **Nombre** | Caries / Empaste |
| **Código** | `caries` |
| **Categoría** | restorative |
| **Prioridad** | `low` |
| **Profesional asignado** | Dra. Ester Alberto |
| **Duración** | 45 min |

---

### 🔴 CONTROL ODONTOLÓGICO (Prioridad Baja — Dra. Ester)

| Campo | Valor |
|---|---|
| **Nombre** | Control odontológico |
| **Código** | `control` |
| **Categoría** | prevention |
| **Prioridad** | `low` |
| **Profesional asignado** | Dra. Ester Alberto |
| **Duración** | 30 min |

---

## 2. Página: Personal (`/personal`)

Cargá los 2 profesionales del equipo:

### 👩‍⚕️ Dra. Laura Delgado

| Campo | Valor |
|---|---|
| **Nombre** | Laura |
| **Apellido** | Delgado |
| **Email** | (consultar) |
| **Especialidad principal** | Cirugía maxilofacial / Implantología |
| **Activo** | ✅ Sí |
| **Precio consulta** | (consultar valor con doctora) |
| **Tratamientos asignados** | Implantes, Prótesis, Cirugía maxilofacial, Botox, Armonización facial, Endolifting, Blanqueamiento Beyond |

**Bio para el agente** (campo `system_prompt_template` del tenant si aplica):
> "La Dra. Laura Delgado es cirujana maxilofacial especializada en implantología, prótesis y rehabilitación oral. Trabaja con técnica de cirugía guiada y atiende casos complejos de rehabilitación completa. También realiza tratamientos de estética facial: armonización, botox y endolifting."

---

### 👩‍⚕️ Dra. Ester Alberto

| Campo | Valor |
|---|---|
| **Nombre** | Ester |
| **Apellido** | Alberto |
| **Email** | (consultar) |
| **Especialidad principal** | Odontología general |
| **Activo** | ✅ Sí |
| **Tratamientos asignados** | Limpieza, Caries, Controles, Ortodoncia, Endodoncia |

> Atiende adultos, niños y adolescentes. Es la profesional de referencia para tratamientos generales y de rutina.

---

### Cómo asignar tratamientos a profesionales

Una vez creados los profesionales y los tratamientos, andá a cada tratamiento en `/treatments` y usá el botón **"Asignar profesionales"**. Marcá los profesionales que pueden realizar ese tratamiento. **Importante**: si un tratamiento NO tiene profesionales asignados, todos los activos pueden hacerlo (regla de fallback).

---

## 3. Página: Configuración → Obras Sociales

Andá a `/config` → tab **Obras Sociales** y cargá las que la clínica acepta.

> ⚠️ **Regla de oro**: Para el campo `copay_notes` (notas de coseguro), **JAMÁS pongas montos específicos**. Dejalo vacío o poné solo "según cobertura". El system prompt ya está configurado para no mostrar montos.

### Ejemplo de cargas

| Provider Name | Status | Restrictions | External Target | Copay Notes | AI Response Template |
|---|---|---|---|---|---|
| **OSDE** | accepted | (vacío) | — | según cobertura | (vacío — usa default) |
| **Federada Salud** | restricted | "Cobertura variable según plan y tratamiento" | — | según cobertura | "La cobertura depende del plan. Se confirma luego de la evaluación clínica 😊" |
| **ISSN** | external_derivation | — | **CIMO Salud** | — | "Para ISSN derivamos a CIMO Salud (cirugía maxilofacial). Web: cimosalud.com — WhatsApp: https://api.whatsapp.com/send/?phone=5492995348849" |
| **IOMA** | accepted | (vacío) | — | según cobertura | (vacío) |
| **PAMI** | restricted | "Requiere autorización previa según el caso" | — | según cobertura | (vacío) |

### Reglas que debés seguir al cargar

- **NO cargues montos** en `copay_notes`. Solo "según cobertura" o vacío.
- **NO cargues** "qué cubre exactamente esta OS" en restrictions. Solo "variable según plan".
- Para ISSN, asegurate de incluir el link de CIMO en el `ai_response_template`.
- Las que no acepten: cargalas con status `rejected` solo si la doctora quiere mencionarlas explícitamente. Si no, mejor NO cargarlas (el sistema responderá la fallback genérica).

---

## 4. Página: Configuración → Reglas de Derivación

Andá a `/config` → tab **Reglas de Derivación** y cargá estas reglas en orden de prioridad:

### Regla 1 — Implantes / Prótesis / Estética → Dra. Laura

| Campo | Valor |
|---|---|
| **Nombre** | Implantes y Estética → Dra. Laura |
| **Condición de paciente** | Cualquier paciente |
| **Categorías de tratamiento** | implante, protesis, cirugia_maxilofacial, botox, armonizacion_facial, endolifting, blanqueamiento |
| **Profesional destino** | Dra. Laura Delgado |
| **Prioridad** | 1 |

### Regla 2 — Odontología General → Dra. Ester

| Campo | Valor |
|---|---|
| **Nombre** | Odontología General → Dra. Ester |
| **Condición de paciente** | Cualquier paciente |
| **Categorías de tratamiento** | limpieza, caries, control, ortodoncia, endodoncia |
| **Profesional destino** | Dra. Ester Alberto |
| **Prioridad** | 2 |

### Regla 3 — Pacientes con dolor → Dra. Laura (urgencia)

| Campo | Valor |
|---|---|
| **Nombre** | Urgencias → Dra. Laura |
| **Condición de paciente** | Pacientes con dolor / urgencia |
| **Categorías de tratamiento** | urgencia, dolor |
| **Profesional destino** | Dra. Laura Delgado |
| **Prioridad** | 0 (más alta) |

### Regla 4 — Casos ambiguos (falta de dientes) → Dra. Laura

| Campo | Valor |
|---|---|
| **Nombre** | Casos ambiguos → Dra. Laura |
| **Condición de paciente** | Pacientes con dientes faltantes o problemas funcionales |
| **Categorías de tratamiento** | (todas las que mencionen dientes faltantes) |
| **Profesional destino** | Dra. Laura Delgado |
| **Prioridad** | 3 |

> **Regla de oro**: si hay duda entre "odontología general" y "rehabilitación", SIEMPRE derivar a la doctora (implantes/prótesis), NUNCA al equipo. Esto ya está reforzado en el system prompt.

---

## 5. Página: FAQs

Andá a `/faqs` y cargá las preguntas frecuentes con las respuestas oficiales que la doctora redactó. El sistema RAG va a recuperarlas semánticamente cuando el paciente pregunte algo similar.

> **Importante**: las FAQs se vectorizan automáticamente al guardar. El agente las usa con prioridad absoluta sobre cualquier tool.

### FAQ 1 — Coseguro

| Campo | Valor |
|---|---|
| **Categoría** | Obras Sociales |
| **Pregunta** | ¿Trabajan con obra social? ¿Cuánto sale el coseguro? |
| **Respuesta** | Si contás con obra social, la consulta se realiza por tu cobertura y puede tener un coseguro según el plan 😊 El valor exacto depende de la obra social y se confirma en la clínica. |

### FAQ 2 — Cobertura

| Campo | Valor |
|---|---|
| **Categoría** | Obras Sociales |
| **Pregunta** | ¿Qué cubre mi obra social? ¿Cubre implantes? ¿Cubre cirugía? |
| **Respuesta** | La cobertura depende de la obra social, el plan y el tipo de tratamiento. Para indicarte con precisión qué incluye en tu caso, es necesario realizar una evaluación clínica y revisar tu cobertura específica. Si querés, podemos coordinarte una consulta y orientarte correctamente 😊 |

### FAQ 3 — Reintegros

| Campo | Valor |
|---|---|
| **Categoría** | Obras Sociales |
| **Pregunta** | ¿Hay reintegro? ¿Cómo es el tema de los reintegros? |
| **Respuesta** | En algunos casos, las obras sociales pueden ofrecer reintegros presentando la factura. El detalle del proceso depende de cada obra social y se confirma en la clínica 😊 |

### FAQ 4 — Autorizaciones previas

| Campo | Valor |
|---|---|
| **Categoría** | Obras Sociales |
| **Pregunta** | ¿Necesito autorización previa? ¿Mi obra social pide autorización? |
| **Respuesta** | En algunos tratamientos, especialmente quirúrgicos, la obra social puede requerir una autorización previa. Esto se gestiona luego de la evaluación, ya que depende del diagnóstico 😊 |

### FAQ 5 — Sin obra social

| Campo | Valor |
|---|---|
| **Categoría** | Pagos |
| **Pregunta** | No tengo obra social, ¿pueden atenderme? |
| **Respuesta** | Por supuesto 😊 Trabajamos con algunas obras sociales específicas, pero también podemos evaluarte de forma particular y ofrecerte la mejor opción de tratamiento según tu caso. Contanos qué necesitás y te orientamos. |

### FAQ 6 — Precio de implantes

| Campo | Valor |
|---|---|
| **Categoría** | Implantes |
| **Pregunta** | ¿Cuánto sale un implante? ¿Qué precio tienen los implantes? |
| **Respuesta** | Cada caso de implantes se evalúa de forma personalizada, ya que depende del hueso disponible, la zona a tratar y el tipo de rehabilitación necesaria. La doctora se especializa en este tipo de tratamientos. Lo ideal es realizar una evaluación para indicarte la mejor opción según tu caso. Si querés, te ayudo a coordinar un turno 😊 |

### FAQ 7 — Estudios previos

| Campo | Valor |
|---|---|
| **Categoría** | Implantes |
| **Pregunta** | ¿Necesito traer radiografías? ¿Qué estudios necesito? |
| **Respuesta** | Si contás con estudios previos (radiografías, tomografías, etc.), podés enviarlos antes de tu consulta para optimizar la evaluación y planificación de tu caso 😊 Si no tenés, no hay problema, eso se evalúa en la consulta. |

### FAQ 8 — Lista de espera para implantes

| Campo | Valor |
|---|---|
| **Categoría** | Turnos |
| **Pregunta** | ¿Hay lista de espera? ¿Y si no hay turno cerca? |
| **Respuesta** | Si no hay disponibilidad cercana, podemos agendarte el primer turno disponible y también dejarte en lista de espera por si se libera uno antes. Te avisaríamos por WhatsApp 😊 |

### FAQ 9 — Cirugía maxilofacial

| Campo | Valor |
|---|---|
| **Categoría** | Cirugía |
| **Pregunta** | ¿Hacen cirugía de muelas de juicio? ¿Hacen extracciones? |
| **Respuesta** | Sí 😊 La doctora es cirujana maxilofacial y realiza extracciones, cirugía de muelas de juicio, implantes y otras cirugías bucales. Si querés, te ayudo a coordinar una evaluación. |

---

## 6. Plantillas YCloud HSM

Las plantillas que faltan crear en Meta WhatsApp Manager (la doctora ya creó 6, faltan estas):

### Plantillas adicionales necesarias

| Nombre | Categoría | Idioma | Texto del cuerpo |
|---|---|---|---|
| `seguimiento_dia_1` | Marketing | Spanish (ARG) | "Hola {{1}} 😊 Pasaron 24 horas desde tu consulta con la Dra. Laura. ¿Cómo te sentís? Cualquier duda, escribinos 💛" |
| `seguimiento_dia_3` | Marketing | Spanish (ARG) | "Hola {{1}} 😊 ¿Cómo te encontrás después del tratamiento? Si tenés alguna molestia, contanos para acompañarte 💛" |
| `botox_post` | Marketing | Spanish (ARG) | "Hola {{1}} 😊 Después de tu sesión de Botox: no acostarte por 4 hs, no masajear la zona, evitar ejercicio 24 hs. Cualquier duda, escribinos 💛" |
| `endolifting_post` | Marketing | Spanish (ARG) | "Hola {{1}} 😊 Después de tu Endolifting: evitar ejercicio 48 hs, no exponerse al sol, puede haber leve inflamación. Estamos para acompañarte 💛" |
| `pre_cirugia` | Marketing | Spanish (ARG) | "Hola {{1}} 😊 Te compartimos las indicaciones previas a tu cirugía: comer normalmente (salvo indicación), no consumir alcohol 24 hs antes, mantener buena higiene bucal. Si tenés estudios, podés enviarlos antes 📄 Cualquier duda, estamos para ayudarte 💛" |

### Cómo cargarlas

1. Andá a https://business.facebook.com/latest/whatsapp_manager/message_templates
2. Click en **"Crear plantilla"**
3. Categoría: **Marketing** o **Utility** según corresponda
4. Idioma: **Spanish (ARG)**
5. Pegá el nombre y el cuerpo según la tabla
6. Esperá aprobación de Meta (suele ser en minutos)

> **Después de aprobarse**, andá a `/templates` en ClinicForge → tab "Plantillas YCloud" → Refrescar. Si no aparecen, abrí la consola del browser (F12 → Console) — el último deploy agregó logs de diagnóstico que te van a decir exactamente por qué.

### Reglas de envío automático

Andá a `/templates` → tab "Reglas" y configurá:

| Trigger | Cuándo se dispara | Plantilla a enviar |
|---|---|---|
| **24h antes del turno** | 24h antes del `appointment_datetime` | `confirmacion_asistencia` |
| **Post agendamiento (cirugía/implante)** | Inmediatamente después de book_appointment con tratamiento de cirugía | `pre_cirugia` |
| **Post tratamiento** | 4-6h después del turno | Según tratamiento: `blanqueamiento_beyond`, `botox_post`, `armonizacion_facial`, `post_cirugia`, etc. |
| **Día 1 post-tratamiento** | 24h después del turno | `seguimiento_dia_1` |
| **Día 3 post-tratamiento** | 72h después del turno | `seguimiento_dia_3` |

---

## 7. Asignación masiva de pacientes

> Esta funcionalidad fue implementada en commit `44b20d9`.

### Pasos

1. Andá a `/patients`
2. Vas a ver una **columna de checkboxes** a la izquierda y una columna nueva **"Profesional asignado"** a la derecha
3. Marcá los checkboxes de los pacientes que son de la Dra. Laura (los 70 importados por CSV)
4. En la barra que aparece arriba, click en **"Asignar profesional"**
5. Seleccioná **Dra. Laura Delgado** del dropdown
6. Confirmá

A partir de ese momento, cuando esos pacientes escriban por WhatsApp, el agente va a saber automáticamente que son pacientes habituales de la doctora y los va a priorizar/derivar siempre a ella.

---

## ✅ Checklist de carga

Marcá conforme vayas completando:

### Tratamientos (`/treatments`)
- [ ] Implante dental — high — Dra. Laura — pre/post
- [ ] Prótesis — high — Dra. Laura
- [ ] Blanqueamiento Beyond — high — Dra. Laura — pre/post
- [ ] Botox — high — Dra. Laura — pre/post
- [ ] Armonización facial — high — Dra. Laura — pre/post
- [ ] Endolifting — high — Dra. Laura — pre/post
- [ ] Cirugía maxilofacial — medium — Dra. Laura — pre/post
- [ ] Limpieza dental — low — Dra. Ester
- [ ] Ortodoncia — low — Dra. Ester
- [ ] Endodoncia — low — Dra. Ester
- [ ] Caries / Empaste — low — Dra. Ester
- [ ] Control odontológico — low — Dra. Ester

### Personal (`/personal`)
- [ ] Dra. Laura Delgado creada y activa
- [ ] Dra. Ester Alberto creada y activa
- [ ] Tratamientos asignados a cada profesional

### Obras Sociales (`/config`)
- [ ] OSDE configurada (sin montos)
- [ ] Federada Salud configurada (sin montos)
- [ ] ISSN configurada con derivación a CIMO + link WhatsApp
- [ ] IOMA configurada (sin montos)
- [ ] PAMI configurada (sin montos)
- [ ] (Otras según el listado de la clínica)

### Reglas de Derivación (`/config`)
- [ ] Regla 1: Implantes/Estética → Dra. Laura (prioridad 1)
- [ ] Regla 2: Odontología general → Dra. Ester (prioridad 2)
- [ ] Regla 3: Urgencias/dolor → Dra. Laura (prioridad 0)
- [ ] Regla 4: Casos ambiguos (dientes faltantes) → Dra. Laura (prioridad 3)

### FAQs (`/faqs`)
- [ ] FAQ 1: Coseguro
- [ ] FAQ 2: Cobertura
- [ ] FAQ 3: Reintegros
- [ ] FAQ 4: Autorizaciones
- [ ] FAQ 5: Sin obra social
- [ ] FAQ 6: Precio implantes
- [ ] FAQ 7: Estudios previos
- [ ] FAQ 8: Lista de espera
- [ ] FAQ 9: Cirugía maxilofacial

### Plantillas YCloud HSM
- [ ] `seguimiento_dia_1` creada y aprobada
- [ ] `seguimiento_dia_3` creada y aprobada
- [ ] `botox_post` creada y aprobada
- [ ] `endolifting_post` creada y aprobada
- [ ] `pre_cirugia` creada y aprobada
- [ ] Reglas de envío automático configuradas

### Pacientes
- [ ] 70 pacientes importados asignados a Dra. Laura (bulk assign)

---

## 🎯 Lo que YA fue actualizado por código (no requiere acción tuya)

El system prompt del agente fue actualizado para incluir:

1. ✅ Reglas blocantes sobre coseguro: nunca informar montos
2. ✅ Reglas sobre cobertura: nunca confirmar qué cubre cada OS
3. ✅ Reglas sobre autorizaciones (antes vs después del turno)
4. ✅ Reglas sobre reintegros (mención general sin detalles)
5. ✅ Detección de leads de alto valor: "me falta un diente", "se me rompió un diente", etc. → SIEMPRE Dra. Laura
6. ✅ Lista de espera obligatoria para implantes sin disponibilidad
7. ✅ Seguimiento post-atención: positivo (sin acción) vs negativo (derivhumano OBLIGATORIO + ofrecer control)
8. ✅ Estudios previos pedidos automáticamente después de confirmar turno de cirugía/implante
9. ✅ Pacientes propios con dolor → urgencia, sin dolor → prioridad media
10. ✅ Respuesta oficial para obras sociales no listadas
11. ✅ F4 (obra social no reconocida) actualizado con respuesta oficial
12. ✅ F6 (pérdida de dientes) ampliado con más palabras clave del feedback

---

## 📞 Dudas

Si algo no está claro o algún campo no aparece en la UI esperada, avisame y te ayudo a destrabarlo. Lo más probable es que falten datos o que haya un bug del que no me enteré.

> **Próximo paso después de cargar todo**: hacer pruebas con conversaciones reales en WhatsApp y validar que el agente responde como esperamos.
