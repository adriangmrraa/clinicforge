# Riesgos de entendimiento del agente al agendar turnos

Lista de situaciones donde lo que dice el usuario puede no alinearse con lo que el agente/envío espera, y qué puede fallar.

---

## Contrato de formato: agente vs backend

**El agente es la fuente principal de formato canónico.** El system prompt incluye la sección "FORMATO CANÓNICO AL LLAMAR TOOLS", que obliga al agente a traducir lo que dice el usuario (en español o inglés) al formato esperado por las tools antes de llamarlas (p. ej. `date_time` como "día 17:00", `dni` solo dígitos, `birth_date` como "DD/MM/AAAA", `email` válido, `city` como texto, `acquisition_source` como Instagram/Google/Referido/Otro). **El backend conserva la normalización actual** (parse_datetime ampliado, DNI solo dígitos, validación de email, validación de fecha, normalización de fuente) como **red de seguridad**: si el agente envía algo que el backend puede interpretar, se acepta; si la tool devuelve error (❌/⚠️), el agente debe reintentar al menos una vez con el formato canónico antes de dar por perdida la reserva. Así se reduce la probabilidad de fallos sin romper el comportamiento actual.

---

## 1. Fecha y hora (`date_time`)

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "el próximo miércoles", "la semana que viene el jueves" | `parse_date` solo mira "miércoles"/"jueves"; "próximo" no se usa → puede interpretar "este" miércoles si ya pasó. | No hay "próximo" explícito; depende de `get_next_weekday` (próximo por defecto). |
| "pasado mañana a las 10" | No está en `day_map` → puede caer en dateutil o default. | No manejado; podría añadirse "pasado mañana" → hoy+2. |
| "el 15 de febrero", "el 20" | Depende de `dateutil_parse`; "el 20" puede ser ambiguo (día 20 del mes actual). | Parcial (dateutil). |
| "5 de la tarde", "a las 5 pm" | Hora en formato 12h; regex busca 1–2 dígitos + hs/horas. "5 pm" no matchea → hora por defecto 14:00. | **Riesgo alto**: "5 pm" / "17" sin "hs" ya cubierto; "5 de la tarde" no. |
| "a la mañana temprano", "primer horario" | Sin hora concreta; el agente podría inventar o pasar algo genérico. | Depende del prompt; la tool necesita una hora. |
| "miércoles a la tarde" (sin hora) | El agente debería elegir un slot de tarde (ej. 14:00 o 17:00); si pasa solo "miércoles" → 14:00 default. | Parcial (default 14:00). |

---

## 2. Nombre y apellido (`first_name` / `last_name`)

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "Me llamo Juan Pérez" | El modelo puede poner todo en `first_name` o repartir bien. | Depende del LLM. |
| "Adrian Rodolfo Argañaraz" | Varias palabras: ¿Adrian / Rodolfo Argañaraz o Adrian Rodolfo / Argañaraz? | Cualquier reparto válido; no hay regla fija. |
| "Soy María de los Ángeles García" | "De los Ángeles" puede ir en first o en last; convenciones por país. | Sin normalización. |
| "Solo Carlos" / "Carlos nada más" | Sin apellido; para **nuevo** paciente la tool exige first_name **y** last_name → rechazo. | Tool devuelve mensaje claro; el agente debe pedir apellido. |
| Nombre con tildes/ñ (Argañaraz, José) | Encoding o copy-paste raro podría alterar caracteres. | Normalmente OK si el modelo y BD usan UTF-8. |

---

## 3. DNI / documento

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "40.989.310", "40 989 310" | Puntos o espacios; la tool hace `.strip()` pero no quita puntos. | Puede guardarse con puntos; no suele romper, pero conviene normalizar a dígitos. |
| "mi documento es 12345678", "DNI 12345678" | El modelo debe extraer solo el número. | Depende del LLM. |
| "no tengo DNI" / menores | Sin DNI; la tool lo exige para nuevos. | Mensaje claro; flujo humano si aplica. |

---

## 4. Sistema de Seguimiento Post-Atención

### 4.1 Detección de respuestas a seguimientos

| Situación | Riesgo | Estado actual |
|-----------|--------|----------------|
| Paciente responde "todo bien" a seguimiento | Agente debe detectar contexto de seguimiento y evaluar síntomas | ✅ Buffer task detecta metadata `is_followup` |
| Paciente reporta dolor/inflamación | Agente debe activar `triage_urgency` inmediatamente | ✅ Contexto especial inyectado en prompt |
| Paciente responde con audio/imagen | Sistema debe procesar multimedia y mantener contexto | ✅ Mismo flujo que mensajes regulares |
| Múltiples mensajes en conversación | Contexto debe persistir durante toda la interacción | ✅ Historial completo en chat_messages |

### 4.2 Evaluación de triage automático

| Síntoma reportado | Regla aplicada | Nivel de urgencia |
|-------------------|----------------|-------------------|
| Dolor intenso que no cede | Regla 1 - Dolor intenso | Emergency/High |
| Inflamación importante en cara | Regla 2 - Inflamación facial | Emergency/High |
| Sangrado abundante | Regla 3 - Sangrado no controlado | Emergency/High |
| Traumatismo reciente | Regla 4 - Traumatismo facial | Emergency/High |
| Fiebre + dolor dental | Regla 5 - Fiebre asociada | Emergency/High |
| Prótesis se cayó | Regla 6 - Pérdida de prótesis | Emergency/High |
| Dolor leve/manejable | No cumple criterios de emergencia | Normal/Low |

---

## 5. Nuevos campos obligatorios para pacientes nuevos

### 4.1 Fecha de nacimiento (`birth_date` - formato DD/MM/AAAA)

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "15/05/1990" | Formato correcto | ✅ Validación estricta en backend |
| "15-05-1990", "15.05.1990" | Formatos alternativos | ❌ Rechazado - debe usar DD/MM/AAAA |
| "15 de mayo de 1990" | Formato textual | ❌ Rechazado - debe usar DD/MM/AAAA |
| "05/15/1990" | Formato MM/DD/AAAA (confuso) | ❌ Rechazado - debe usar DD/MM/AAAA |

### 4.2 Email (`email`)

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "usuario@dominio.com" | Formato válido | ✅ Validación con regex |
| "usuario @ dominio . com" | Espacios incorrectos | ❌ Rechazado - email inválido |
| "sin email", "no tengo" | Campo requerido | ❌ Rechazado - campo obligatorio |

### 4.3 Ciudad/Barrio (`city`)

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "Neuquén Capital", "Centro" | Texto libre | ✅ Aceptado |
| "NQN", "Nqn" | Abreviaciones | ✅ Aceptado (se guarda tal cual) |

### 4.4 Cómo nos conoció (`acquisition_source`)

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "Instagram", "IG" | Normalizado a INSTAGRAM | ✅ Cubierto |
| "Google", "buscador" | Normalizado a GOOGLE | ✅ Cubierto |
| "Referido", "recomendación" | Normalizado a REFERRED | ✅ Cubierto |
| "Otro", "otros" | Normalizado a OTHER | ✅ Cubierto |
| "Facebook", "Twitter" | No en lista | Normalizado a OTHER |

**NOTA:** `insurance_provider` ha sido eliminado. La clínica atiende de forma particular.

---

## 5. Tratamiento (`treatment_reason`)

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "una limpieza" vs "limpieza profunda" | En BD solo puede existir "Limpieza Profunda"; "limpieza" hace ILIKE `%limpieza%` → puede matchear. | Normalmente OK. |
| "limpieza de dientes", "limpieza dental" | Si en BD está "Limpieza Profunda", el ILIKE sigue matcheando. | OK. |
| "el que me dijiste" / "ese" | Referencia anafórica; el modelo debe sustituir por el tratamiento ya hablado. | Depende del contexto del chat. |
| Typo: "limpeza", "consulta general" | ILIKE puede no matchear → `t_data` null → duration 30 y code = treatment_reason (string) que puede no ser un code válido. | INSERT usa `treatment_code`; si no hay match, se usa el texto; puede haber inconsistencia. |

---

## 6. Profesional (`professional_name`)

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "con el doctor Facundo", "Facundo" | Se limpia "Dr./Dra." en la query; "Facundo" matchea por first_name. | OK. |
| "con la doctora Laura" y hay dos Lauras | ILIKE puede devolver el primero; no hay desambiguación. | Posible match incorrecto si hay varios con mismo nombre. |
| "el primero disponible" | professional_name no se pasa; la lógica elige el primero sin conflicto. | OK. |

---

## 7. Un solo mensaje largo con todo

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "Quiero el miércoles a las 17, soy Adrian Argañaraz DNI 40989310 15/05/1990 adrian@email.com Neuquén Instagram, limpieza con Facundo" | El modelo debe extraer: date_time, first_name, last_name, dni, birth_date, email, city, acquisition_source, treatment_reason, professional_name. Cualquier campo mal asignado (ej. fecha mal formateada, email inválido) rompe o da datos incorrectos. | Depende del LLM; mensajes de error de la tool ayudan a reintentar. |

---

## 8. Idioma (es/en/fr)

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "Wednesday 5pm", "tomorrow at 10" | parse_date tiene "wednesday", "tomorrow"; parse_datetime tiene "10" pero "5pm" no matchea el regex (solo dígitos + hs). | "5pm" / "5 am" no se interpretan → hora por defecto. |
| "mercredi 17h", "je suis Pierre Dupont" | "mercredi" no está en day_map; "17h" sí (regex). | Fecha en francés puede fallar; nombre depende del modelo. |

---

## 9. Horarios en el pasado

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "quiero para ayer a las 10" | parse_datetime puede devolver ayer 10:00; el INSERT no valida "no pasado". | Podría agendar en el pasado; check_availability evita ofrecer slots pasados, pero book_appointment no rechaza explícitamente. |

---

## 10. Varios turnos o tratamientos

| Cómo lo dice el usuario | Riesgo | Estado actual |
|-------------------------|--------|----------------|
| "quiero dos turnos", "limpieza y después revisión" | La tool solo agenda uno por llamada. | El agente tendría que llamar book_appointment dos veces; no siempre lo hace. |

---

## Resumen de prioridad

- **Alto:** "5 de la tarde" / "5 pm" (hora 12h); "pasado mañana"; normalizar DNI (solo dígitos); normalizar "particular" en obra social; rechazar fecha/hora en el pasado en `book_appointment`.
- **Medio:** Añadir "pasado mañana" y "próximo [día]" si hace falta; mejorar mensajes cuando falta nombre/apellido o cuando el tratamiento no matchea.
- **Bajo:** Varios profesionales con el mismo nombre; referencias "el que me dijiste"; múltiples turnos en un mensaje.

Este documento se puede usar para ir priorizando mejoras en el prompt del agente y en las tools (parse_datetime, normalización de DNI/obra social, validación de “no pasado”).
