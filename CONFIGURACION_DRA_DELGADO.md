# Configuración Inicial — Clínica Dra. María Laura Delgado

Guía completa para cargar la configuración del asistente de IA desde el panel de administración.

---

## 1. Obras Sociales (Tab "Obras Sociales" en Configuración de Clínica)

| Obra Social | Estado | Restricciones | Requiere Coseguro | Notas del Coseguro | Respuesta personalizada del asistente |
|---|---|---|---|---|---|
| América Servicios (MCA) | Aceptada | — | Sí | — | — |
| APSOT | Aceptada | — | Sí | — | — |
| Bancarios (SIACO) | Aceptada | — | Sí | — | — |
| CEA San Pedro | Aceptada | — | Sí | — | — |
| Credi-Guía | Aceptada | — | Sí | — | — |
| Federada Salud | Con restricciones | Solo cirugías específicas | Sí | — | — |
| Galeno | Aceptada | — | Sí | — | — |
| Jerárquicos Salud | Aceptada | — | Sí | — | — |
| Medicus Especialistas | Aceptada | — | Sí | — | — |
| Medicus | Aceptada | — | Sí | — | — |
| Medifé | Aceptada | — | Sí | — | — |
| OSSEG | Aceptada | — | Sí | — | — |
| Poder Judicial | Aceptada | — | Sí | — | — |
| Sancor Salud | Aceptada | — | Sí | — | — |
| SOSUNC | Aceptada | — | Sí | — | — |
| OSDE | Con restricciones | Solo cirugías | Sí | — | — |
| ISSN | Derivación externa | Solo cirugía maxilofacial en CIMO | No | — | Para ese tratamiento trabajamos a través de CIMO 😊 Te paso el contacto para que coordines directamente. |

**Notas:**
- TODAS las obras sociales requieren coseguro (es condición general de la clínica)
- El asistente responderá por defecto: "Sí 😊 trabajamos con tu obra social. La consulta tiene un coseguro. ¿Querés que te pase turnos disponibles?"
- El asistente NUNCA informará sobre autorizaciones, estudios o coberturas específicas en esta etapa
- Para Federada Salud: pendiente confirmar con la Dra. cuáles son las "cirugías específicas" que cubre
- Para ISSN: cargar el contacto de CIMO en el campo "Derivar a"

---

## 2. Reglas de Derivación (Tab "Derivación" en Configuración de Clínica)

Cargar en este ORDEN (la prioridad determina qué regla se aplica primero):

### Regla 1 — Cirugía e Implantes → Dra. Delgado

| Campo | Valor |
|---|---|
| **Nombre de la regla** | Cirugía e implantes → Dra. Delgado |
| **Condición del paciente** | Cualquier paciente |
| **Tratamientos** | Seleccionar: Cirugía, Implantes, Rehabilitación oral, Estética avanzada, Endolifting |
| **Derivar a** | Profesional específico |
| **Profesional** | Dra. María Laura Delgado |
| **Descripción** | Tratamientos de alto valor y complejidad. Solo la Dra. Delgado los realiza. |

### Regla 2 — Tratamientos generales → Equipo

| Campo | Valor |
|---|---|
| **Nombre de la regla** | Tratamientos generales → Equipo |
| **Condición del paciente** | Paciente nuevo |
| **Tratamientos** | Seleccionar: Limpieza, Arreglos, Conductos, Ortodoncia, Blanqueamiento, Exodoncia |
| **Derivar a** | Equipo (sin filtro) |
| **Profesional** | — |
| **Descripción** | Pacientes nuevos con tratamientos básicos se derivan al equipo. |

### Regla 3 — Paciente existente de la Dra. → Prioridad

| Campo | Valor |
|---|---|
| **Nombre de la regla** | Paciente existente → Dra. Delgado |
| **Condición del paciente** | Paciente existente |
| **Tratamientos** | Todos los tratamientos (*) |
| **Derivar a** | Profesional específico |
| **Profesional** | Dra. María Laura Delgado |
| **Descripción** | Pacientes que ya se atienden con la Dra. siempre van con ella, sin importar el tratamiento. |

**Notas:**
- Las reglas se evalúan en orden. La primera que coincida se aplica.
- La Regla 3 está tercera porque la Regla 1 ya captura cirugías/implantes para CUALQUIER paciente.
- Si ninguna regla coincide, el asistente asigna turnos sin filtro de profesional (equipo disponible).
- Pendiente: confirmar con la Dra. los nombres exactos de los profesionales del equipo y sus especialidades.

---

## 3. FAQs (Botón "FAQs" en cada tarjeta de clínica)

### Categoría: General

| Pregunta | Respuesta |
|---|---|
| ¿Dónde queda el consultorio? | Estamos ubicados en [DIRECCIÓN]. Te dejo el link de Google Maps: [LINK] |
| ¿Cuál es el horario de atención? | Atendemos de lunes a viernes de [HORA] a [HORA] y sábados de [HORA] a [HORA]. |
| ¿Tienen estacionamiento? | [Completar según la clínica] |
| ¿Cómo llego en transporte público? | [Completar según la clínica] |
| ¿Atienden sin turno previo? | No, trabajamos únicamente con turno previo. ¿Querés que te pase los turnos disponibles? |

### Categoría: Precios y Costos

| Pregunta | Respuesta |
|---|---|
| ¿Cuánto sale la consulta? | La consulta tiene un valor de $[MONTO]. Si tenés obra social, la consulta tiene un coseguro. ¿Querés agendar un turno? |
| ¿La primera consulta tiene costo? | Sí, la primera consulta tiene un costo de $[MONTO]. En esa consulta se evalúa tu caso y se arma un plan de tratamiento personalizado. |
| ¿Hacen presupuestos? | Sí, en la primera consulta la Dra. evalúa tu caso y te entrega un presupuesto detallado sin compromiso. |

### Categoría: Medios de Pago

| Pregunta | Respuesta |
|---|---|
| ¿Qué medios de pago aceptan? | Aceptamos efectivo, transferencia bancaria, tarjeta de débito y crédito. |
| ¿Aceptan tarjeta? | Sí, aceptamos tarjetas de débito y crédito. |
| ¿Puedo pagar con transferencia? | Sí, te paso los datos bancarios al momento de reservar tu turno. |

### Categoría: Financiación

| Pregunta | Respuesta |
|---|---|
| ¿Tienen planes de financiación? | [Completar: cuotas, condiciones, etc.] |
| ¿Puedo pagar en cuotas? | [Completar según política de la clínica] |

### Categoría: Obras Sociales

| Pregunta | Respuesta |
|---|---|
| ¿Aceptan obra social? | Sí 😊 trabajamos con varias obras sociales. La consulta tiene un coseguro. ¿Cuál es tu obra social para verificar? |
| ¿Trabajan con OSDE? | Sí, trabajamos con OSDE pero solo para cirugías. ¿En qué tratamiento estás interesado/a? |
| ¿Trabajan con ISSN? | Para ISSN trabajamos a través de CIMO para cirugía maxilofacial 😊 Te paso el contacto para que coordines directamente. |
| ¿Qué es el coseguro? | El coseguro es un monto que abonás en el consultorio al momento de la consulta, además de lo que cubre tu obra social. Todas las consultas con obra social tienen coseguro. |
| ¿Necesito autorización previa? | Eso se evalúa después de la consulta según el tratamiento que necesites. Primero agendemos tu turno y la Dra. te asesora en la consulta. |

### Categoría: Coseguros

| Pregunta | Respuesta |
|---|---|
| ¿Cuánto es el coseguro? | [Completar con montos por obra social si varían, o monto general] |
| ¿El coseguro es siempre el mismo? | [Completar: si varía por OS o tratamiento] |

### Categoría: Implantes y Prótesis

| Pregunta | Respuesta |
|---|---|
| ¿Hacen implantes dentales? | Sí, la Dra. Delgado es especialista en implantes dentales. Es uno de nuestros tratamientos principales. ¿Querés agendar una consulta de evaluación? |
| ¿Cuánto dura un implante? | Un implante bien colocado y cuidado puede durar toda la vida. En la consulta la Dra. evalúa tu caso específico y te explica todo el proceso. |
| ¿Duele ponerse un implante? | El procedimiento se realiza con anestesia local, por lo que no sentís dolor durante la intervención. Después te damos todas las indicaciones para una recuperación cómoda. |
| ¿Cuánto tiempo lleva el tratamiento de implantes? | Depende de cada caso. Generalmente entre 3 y 6 meses. En la consulta la Dra. te da un cronograma personalizado. |
| ¿Hacen prótesis? | Sí, realizamos todo tipo de rehabilitación protésica: prótesis fijas, removibles y sobre implantes. |

### Categoría: Estética Dental

| Pregunta | Respuesta |
|---|---|
| ¿Hacen blanqueamiento? | Sí, realizamos blanqueamiento dental profesional con resultados visibles desde la primera sesión. ¿Querés agendar? |
| ¿Qué tratamientos estéticos ofrecen? | Ofrecemos blanqueamiento dental, carillas, coronas estéticas, y armonización orofacial. ¿En cuál estás interesado/a? |
| ¿Hacen endolifting? | Sí, la Dra. Delgado realiza endolifting. Es un tratamiento mínimamente invasivo para rejuvenecimiento facial. ¿Querés más información? |

### Categoría: Cirugía

| Pregunta | Respuesta |
|---|---|
| ¿Hacen extracción de muelas de juicio? | Sí, realizamos extracciones de terceros molares (muelas de juicio). ¿Tenés una radiografía panorámica? Nos ayuda a evaluar tu caso. |
| ¿Hacen cirugía maxilofacial? | Sí, la Dra. Delgado realiza cirugías maxilofaciales. ¿Querés contarme un poco más sobre lo que necesitás? |

### Categoría: Primera Consulta

| Pregunta | Respuesta |
|---|---|
| ¿Qué hago en la primera consulta? | En la primera consulta la Dra. revisa tu boca, te hace un diagnóstico completo y te arma un plan de tratamiento personalizado con presupuesto. |
| ¿Tengo que llevar algo? | Si tenés radiografías o estudios previos, traelos. Si no tenés, no te preocupes, te indicamos qué necesitás. |
| ¿Cuánto dura la primera consulta? | La primera consulta dura aproximadamente 30-40 minutos para poder evaluar bien tu caso. |

### Categoría: Emergencias

| Pregunta | Respuesta |
|---|---|
| Tengo una emergencia dental | Si tenés una emergencia, contactanos al [TELÉFONO] y te damos un turno lo antes posible. ¿Querés que te derive con una persona del equipo? |
| Me duele mucho un diente | Entiendo tu urgencia. Vamos a buscar el turno más cercano disponible para que la Dra. te atienda lo antes posible. |
| Se me cayó un diente / corona | Es importante actuar rápido. Si se te cayó un diente, conservalo en leche o suero. Contactanos ya al [TELÉFONO]. |

### Categoría: Cuidados Post-tratamiento

| Pregunta | Respuesta |
|---|---|
| ¿Qué cuidados debo tener después de una extracción? | No enjuagues las primeras 24hs, aplicá hielo por fuera si hay hinchazón, dieta blanda, y tomá la medicación indicada. Si hay sangrado que no para, contactanos. |
| ¿Qué cuidados debo tener después del blanqueamiento? | Evitá alimentos y bebidas con color (café, vino, salsa de tomate) por 48-72hs. No fumes. Usá la pasta dental que te indicamos. |

### Categoría: Diferenciadores

| Pregunta | Respuesta |
|---|---|
| ¿Por qué elegir esta clínica? | La Dra. Delgado es especialista en cirugía e implantes con [X] años de experiencia. Trabajamos con tecnología de última generación y un equipo multidisciplinario para darte la mejor atención. |
| ¿Qué experiencia tiene la Dra.? | La Dra. María Laura Delgado es [completar: especialidades, formación, trayectoria]. |

### Categoría: Tecnología

| Pregunta | Respuesta |
|---|---|
| ¿Qué tecnología usan? | [Completar: escáner intraoral, tomografía, láser, etc.] |
| ¿Usan radiografía digital? | [Completar según equipamiento] |

### Categoría: Ventajas Competitivas

| Pregunta | Respuesta |
|---|---|
| ¿Qué los diferencia de otras clínicas? | [Completar: atención personalizada, tecnología, especialización de la Dra., equipo, etc.] |

---

## 4. Datos Pendientes de Confirmar con la Dra.

Antes de cargar la configuración, necesitamos confirmar:

1. **Dirección exacta del consultorio** y link de Google Maps
2. **Horarios de atención** (días y horas)
3. **Precio de la consulta** (monto actual)
4. **Coseguro**: ¿es un monto fijo o varía por obra social/tratamiento?
5. **Federada Salud**: ¿cuáles son las "cirugías específicas" que cubre?
6. **OSDE**: ¿todas las cirugías o un subset?
7. **CIMO**: teléfono/dirección de contacto para derivar pacientes de ISSN
8. **Obra social no listada**: ¿qué responde el asistente? (sugerencia: "No tengo información sobre esa obra social. ¿Querés que consulte con la clínica?")
9. **Profesionales del equipo**: nombres, especialidades y qué tratamientos atienden
10. **Financiación**: ¿ofrecen cuotas? ¿condiciones?
11. **Teléfono de emergencias**: número para emergencias fuera de horario
12. **Experiencia de la Dra.**: años, especialidades, formación para las FAQs de diferenciadores
13. **Tecnología**: equipamiento para destacar en las FAQs

---

## 5. Instrucciones Pre/Post Tratamiento (en cada Tratamiento → "Configurar Instrucciones")

Estas se cargan desde la vista de Tratamientos, botón "Configurar Instrucciones" en cada uno.

### Cirugía (extracción, muelas de juicio, maxilofacial)

**Pre-tratamiento:**
```
Indicaciones antes de tu cirugía:
• No tomar aspirina ni anticoagulantes 7 días antes (consultar con tu médico)
• Comer algo liviano 2 horas antes del turno
• Venir acompañado/a (no podrás manejar después)
• Traer la medicación indicada si te la recetaron
• Evitar alcohol 24hs antes
```

**Post-tratamiento:**

| Momento | Instrucción | Sugerir turno de control |
|---|---|---|
| Inmediato | No escupir ni enjuagar las primeras 24hs. Morder la gasa por 30 minutos. Aplicar hielo por fuera 15 min sí / 15 min no. Dieta blanda y fría. | No |
| 24 horas | ¿Cómo te sentís? Si hay hinchazón es normal. Seguí aplicando hielo. Tomá la medicación indicada. Si hay sangrado que no para, contactanos. | No |
| 72 horas | ¿Cómo seguís? La hinchazón debería ir bajando. Ya podés enjuagar suavemente con agua tibia y sal. Seguí con dieta blanda. | No |
| Retiro de puntos (7 días) | Es momento de retirar los puntos. Agendá tu turno de control. | Sí |

### Blanqueamiento

**Pre-tratamiento:**
```
Indicaciones antes de tu blanqueamiento:
• Realizá una limpieza dental previa (si no la tenés hecha)
• No es necesario venir en ayunas
• El procedimiento dura aproximadamente 1 hora
```

**Post-tratamiento:**

| Momento | Instrucción | Sugerir turno de control |
|---|---|---|
| Inmediato | Evitá alimentos y bebidas con color por 48-72hs: café, té, vino tinto, salsa de tomate, remolacha. No fumes. Usá la pasta dental que te indicamos. | No |
| 48 horas | ¿Cómo te sentís con tu nueva sonrisa? Recordá seguir evitando alimentos con color. Si sentís sensibilidad, es normal y pasará en unos días. | No |

### Implantes

**Pre-tratamiento:**
```
Indicaciones antes de tu cirugía de implante:
• No tomar aspirina ni anticoagulantes 7 días antes
• Comer algo liviano 2 horas antes
• Venir acompañado/a
• Traer la tomografía y estudios solicitados
• Evitar alcohol 48hs antes
```

**Post-tratamiento:**

| Momento | Instrucción | Sugerir turno de control |
|---|---|---|
| Inmediato | No enjuagar ni escupir las primeras 24hs. Hielo por fuera 15/15 min. Dieta blanda y fría. No fumar mínimo 7 días (idealmente 30). Dormir con la cabeza elevada. | No |
| 24 horas | ¿Cómo te sentís? Seguí con hielo, dieta blanda y la medicación indicada. No tocar la zona con la lengua ni los dedos. | No |
| 72 horas | ¿Cómo evoluciona? La hinchazón debería ir bajando. Si notás algo inusual, contactanos. | No |
| 1 semana | Control post-quirúrgico. Retiro de puntos si corresponde. | Sí |

### Consulta General

**Post-tratamiento:**

| Momento | Instrucción | Sugerir turno de control |
|---|---|---|
| 24 horas | ¡Hola! ¿Cómo te sentiste en la consulta? Tu opinión nos ayuda a mejorar 😊 | No |

---

## Notas Importantes

- Los campos marcados con [COMPLETAR] necesitan los datos reales de la clínica
- Las FAQs alimentan al agente de IA — escribir las respuestas en tono amigable y profesional
- Las instrucciones pre/post se envían automáticamente al paciente por WhatsApp
- Todas las obras sociales tienen coseguro como regla general de la clínica
- Las reglas de derivación se evalúan en orden de prioridad (menor número = mayor prioridad)
