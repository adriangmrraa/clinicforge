**DOCUMENTACIÓN TÉCNICA DE PROYECTO**

Sistema de Automatización IA — WhatsApp & Instagram \+ Plataforma de Gestión

Cliente:

**Dra. María Laura Delgado**

Cirujana Maxilofacial — Implantología & Rehabilitación Oral

Neuquén Capital, Argentina

Desarrollado por: Codexy — Agencia de Automatización & IA  |  2025

| N° | SECCIÓN |
| :---- | :---- |
| 01 | Datos Generales del Consultorio |
| 02 | Visión General del Sistema |
| 03 | Arquitectura Técnica — Componentes y Stack |
| 04 | Módulo 1 — Bot WhatsApp: Atención & Primer Contacto |
| 05 | Módulo 2 — Detección de Origen del Paciente |
| 06 | Módulo 3 — Admisión y Registro de Paciente Nuevo |
| 07 | Módulo 4 — Cuestionario de Salud (Anamnesis) |
| 08 | Módulo 5 — Agenda y Gestión de Turnos |
| 09 | Módulo 6 — Recordatorios y Confirmaciones |
| 10 | Módulo 7 — Protocolo de Urgencias |
| 11 | Módulo 8 — Seguimiento Post-Consulta |
| 12 | Módulo 9 — Reactivación de Pacientes Inactivos |
| 13 | Módulo 10 — Canal Instagram |
| 14 | Plataforma de Gestión — Estructura de Datos |
| 15 | Flujos de Automatización — Diagrama de Procesos |
| 16 | FAQs Configuradas en el Bot |
| 17 | Plan de Implementación por Fases |
| 18 | Criterios de Aceptación y Entrega |

# **01 — DATOS GENERALES DEL CONSULTORIO**

| DRA. MARÍA LAURA DELGADO — FICHA DEL PROYECTO |
| :---- |
| Nombre comercial:  Dra. María Laura Delgado – Cirujana Maxilofacial |
| Especialidad:       Implantología y Rehabilitación Oral |
| Ciudad:             Neuquén Capital, Argentina |
| Dirección 1:        Calle Córdoba 431, Neuquén Capital |
| Dirección 2:        Calle Salta 147, Neuquén Capital |
| Fecha de relevamiento: 14/02/2026 |

## **Horarios de Atención**

| DÍA | HORARIO |
| :---- | :---- |
| Lunes | 13:00 a 19:00 hs |
| Martes | 10:00 a 17:00 hs |
| Miércoles | 12:00 a 18:00 hs |
| Jueves | 10:00 a 17:00 hs |
| Viernes | 14:00 a 19:00 hs |
| Sábado | No atiende |
| Domingo | No atiende |

## **Equipo de Trabajo**

| ROL | DESCRIPCIÓN |
| :---- | :---- |
| Dra. María Laura Delgado | Cirugía maxilofacial, implantología, rehabilitación oral y estética orofacial — profesional principal |
| Colegas odontólogos | Ortodoncia, endodoncia y odontología general — según necesidades de cada caso |
| Secretaria virtual (bot) | Gestión de turnos, recordatorios y primera orientación al paciente — el sistema a desarrollar |
| Laboratorios odontológicos | Área protésica — trabajo externo según requerimiento del tratamiento |

## **Servicios del Consultorio**

| SERVICIO | DETALLE | TIEMPO ESTIMADO |
| :---- | :---- | :---- |
| Implantes guiados tomográficamente | Planificación digital 3D, cirugía guiada | Según caso clínico |
| Implantes convencionales (R.I.S.A.) | Escaneo y tomografía previa, pacientes con hueso suficiente | Según profesional |
| Protocolo C.I.M.A. | Atrofia severa, implantes cigomáticos o supraperiósticos | Según estudios 3D |
| Cirugía maxilofacial | Cirugías programadas, seguimiento postoperatorio | Según complejidad |
| Prótesis de alta complejidad | Boca completa, prótesis fija y/o removible | A determinar |
| Blanqueamiento BEYOND® | 20 min \+ kit de mantenimiento incluido | 20 min / sesión |
| Armonización orofacial | Rinolips, bioestimulación, bótox, endolifting | A determinar |
| Diseño de sonrisa | Carillas, armonía forma/tamaño, estética | Por evaluación |
| Rehabilitación integral | Implantes \+ prótesis \+ estética \+ armonización | Multi-etapa |

## **Medios de Pago**

* Efectivo

* Transferencia bancaria

* Pago por etapas — se organiza conversando con el paciente para hacerlo más accesible

* No trabaja con obras sociales — atiende de forma particular

# **02 — VISIÓN GENERAL DEL SISTEMA**

El sistema a desarrollar para la Dra. Laura Delgado es una plataforma de gestión centralizada, conectada a un bot conversacional de WhatsApp e Instagram, que automatiza el recorrido completo del paciente desde el primer contacto hasta la fidelización y reactivación.

| OBJETIVO CENTRAL DEL SISTEMA |
| :---- |
| Que la Dra. Laura Delgado y su equipo dejen de gestionar manualmente: |
| → Respuestas a consultas frecuentes fuera del horario de atención |
| → Toma de turnos y coordinación de agenda |
| → Recordatorios previos a la consulta |
| → Seguimiento de pacientes post-tratamiento |
| → Reactivación de pacientes inactivos |
|  |
| El sistema trabaja 24/7 con el tono y los protocolos definidos por la doctora. |
| Todo queda registrado en la plataforma. Nada se pierde. |

## **Los 10 Módulos del Sistema**

| MÓDULO | FUNCIÓN |
| :---- | :---- |
| M01 — Atención & Primer Contacto | Bot WhatsApp responde consultas frecuentes 24/7 con el tono de la clínica |
| M02 — Detección de Origen | Identifica si el paciente viene de Meta Ads, Google Ads, Instagram orgánico o referido |
| M03 — Admisión Paciente Nuevo | Recopila datos de admisión completos y los registra en la plataforma |
| M04 — Anamnesis | Cuestionario de salud antes de la primera consulta — registrado en la ficha del paciente |
| M05 — Agenda y Turnos | Muestra disponibilidad real por profesional y permite tomar/modificar turnos |
| M06 — Recordatorios | Recordatorio automático 24 hs antes \+ confirmación del paciente |
| M07 — Protocolo de Urgencias | Detecta urgencias reales y deriva al protocolo definido por la Dra. |
| M08 — Seguimiento Post-Consulta | Mensajes automáticos según el tratamiento y el calendario definido por la doctora |
| M09 — Reactivación Inactivos | Detecta pacientes sin actividad y lanza campaña de reactivación personalizada |
| M10 — Canal Instagram | DMs de Instagram conectados al mismo sistema, derivando a WhatsApp cuando corresponde |

# **03 — ARQUITECTURA TÉCNICA — COMPONENTES Y STACK**

## **Stack Tecnológico**

| COMPONENTE | TECNOLOGÍA / HERRAMIENTA | FUNCIÓN |
| :---- | :---- | :---- |
| Automatización y flujos | n8n (self-hosted en VPS) | Orquesta todos los flujos: recibe mensajes, decide caminos, ejecuta acciones |
| Canal WhatsApp | WhatsApp Business API | Recepción y envío de mensajes, audios y documentos |
| Canal Instagram | Instagram Graph API | Recepción de DMs, derivación a WhatsApp |
| IA conversacional | OpenAI / Claude API | Respuestas naturales, detección de intenciones, manejo de consultas complejas |
| Plataforma de gestión | Desarrollo a medida (web app) | Base de datos pacientes, agenda, historias clínicas, seguimientos |
| Base de datos | PostgreSQL / MySQL | Almacenamiento estructurado de pacientes, turnos, sesiones |
| Detección de origen | UTM params \+ webhook | Identifica de dónde viene cada lead (Meta Ads, Google, orgánico, referido) |
| VPS de alojamiento | VPS Linux (Ubuntu) | Hosting de n8n, plataforma y base de datos |

## **Flujo General de Datos**

| CÓMO FLUYE LA INFORMACIÓN EN EL SISTEMA |
| :---- |
| 1\. ENTRADA: Paciente escribe al WhatsApp o DM de Instagram |
| 2\. DETECCIÓN: n8n recibe el mensaje e identifica origen (Meta Ads / Google / orgánico / referido) |
| 3\. CLASIFICACIÓN: ¿Es paciente existente? → busca en BD → respuesta personalizada |
|                    ¿Es paciente nuevo? → inicia flujo de admisión |
| 4\. PROCESO: El bot maneja la conversación según el módulo correspondiente |
| 5\. REGISTRO: Todo queda guardado en la plataforma (paciente, turno, sesión, seguimiento) |
| 6\. NOTIFICACIÓN: La Dra. / secretaria recibe alertas de lo relevante (nuevos pacientes, urgencias) |
| 7\. SEGUIMIENTO: n8n programa automáticamente los recordatorios y seguimientos futuros |

# **04 — MÓDULO 1 — BOT WHATSAPP: ATENCIÓN & PRIMER CONTACTO**

El bot es la secretaria virtual del consultorio. Responde 24/7 con el tono de la Dra. Laura Delgado: profesional, cercano y contenedor. Los pacientes no deben notar que no es una persona.

## **Mensaje de Bienvenida — Paciente Nuevo**

| MENSAJE DE BIENVENIDA — TEXTO BASE (personalizable) |
| :---- |
| ¡Hola\! Bienvenido/a al consultorio de la Dra. María Laura Delgado. |
| Cirujana Maxilofacial e Implantóloga en Neuquén. |
|  |
| Estoy para ayudarte. ¿Qué necesitás? |
|  |
| 1\. Pedir un turno |
| 2\. Consultar sobre tratamientos |
| 3\. Información de horarios y ubicación |
| 4\. Tengo una urgencia |
| 5\. Otro motivo |
|  |
| Escribí el número de tu opción o contame directamente qué necesitás 😊 |

## **Respuestas a Preguntas Frecuentes Configuradas**

| PREGUNTA DEL PACIENTE | RESPUESTA DEL BOT / ACCIÓN |
| :---- | :---- |
| ¿Atienden por obra social? | No, el consultorio atiende de forma particular. Pero organizamos el pago en etapas para que sea accesible. ¿Querés que te cuente más? |
| ¿Cuánto cuesta un implante? | Cada caso es único. El valor se determina después de la evaluación clínica y los estudios. ¿Querés coordinar una consulta para que la Dra. te oriente? |
| ¿El tratamiento duele? | La doctora trabaja con anestesia y técnicas de mínima invasión. Muchos pacientes se sorprenden de lo cómodo que es el proceso. ¿Querés que te cuente más? |
| ¿Cuánto tarda el tratamiento? | Depende de cada caso. En la primera consulta la Dra. te explica el plan paso a paso. ¿Te agendo una consulta de evaluación? |
| ¿Si tengo poco hueso puedo colocarme implantes? | Sí, en muchos casos es posible. La Dra. trabaja con protocolos avanzados para pacientes con poco hueso. La evaluación con estudios 3D lo determina. |
| ¿Me dijeron que no soy candidata para implantes? | Eso no siempre es definitivo. La Dra. trabaja con casos que otros rechazan. Vale la pena una segunda opinión. ¿Agendamos una consulta? |
| ¿Qué es el blanqueamiento BEYOND? | Es un blanqueamiento profesional de alta tecnología, 20 minutos en sillón e incluye kit de mantenimiento. Los resultados son inmediatos y duraderos. |
| ¿Trabajan con Google / Instagram? | Sí, llegaste bien. ¿Qué necesitás? |

## **Respuesta a Audios**

* El bot puede recibir y procesar audios del paciente usando IA de transcripción (Whisper API)

* Una vez transcripto el audio, el bot responde en texto o en audio según la configuración

* Esto hace que la experiencia sea completamente natural para el paciente

# **06 — MÓDULO 3 — ADMISIÓN Y REGISTRO DE PACIENTE NUEVO**

Cuando el sistema detecta que es un paciente nuevo (no existe en la base de datos), inicia el flujo de admisión. Los datos se solicitan de a uno para que la conversación sea natural.

## **Datos de Admisión Obligatorios**

| CAMPO | DETALLE / VALIDACIÓN |
| :---- | :---- |
| Nombre y apellido | Texto libre — se guarda como nombre principal en la ficha |
| DNI | Número — se valida que sean 7 u 8 dígitos |
| Fecha de nacimiento | Formato DD/MM/AAAA — se calcula automáticamente la edad |
| Teléfono celular (WhatsApp) | Se completa automáticamente con el número desde el que escribe |
| Correo electrónico | Formato email — validación básica de formato |
| Ciudad / barrio | Texto libre |
| ¿Cómo nos conociste? | Opciones: Instagram, Google, Referido, Otro — conectado con Módulo 2 |
| Motivo principal de consulta | Texto libre — el paciente lo describe con sus palabras |

| FLUJO DE ADMISIÓN — CONVERSACIÓN NATURAL |
| :---- |
| Bot: Perfecto, para coordinar mejor tu atención necesito algunos datos. |
|      ¿Me decís tu nombre y apellido completo? |
|  |
| Paciente: \[responde\] |
|  |
| Bot: Gracias \[Nombre\]\! ¿Tu DNI? |
|  |
| Paciente: \[responde\] |
|  |
| Bot: Perfecto. ¿Fecha de nacimiento? (DD/MM/AAAA) |
|  |
| \[...continúa hasta completar todos los campos...\] |
|  |
| Bot: ¡Listo\! Ya tenemos tu ficha creada. |
|      Ahora te hago algunas preguntas de salud para que la Dra. llegue |
|      a tu consulta ya preparada. ¿Empezamos? |

# **07 — MÓDULO 4 — CUESTIONARIO DE SALUD (ANAMNESIS)**

Antes de la primera consulta, el bot realiza el cuestionario de salud definido por la Dra. Laura Delgado. Las respuestas quedan almacenadas en la ficha clínica del paciente y la doctora las revisa antes de la consulta.

## **Preguntas de la Anamnesis**

| PREGUNTA | TIPO DE RESPUESTA |
| :---- | :---- |
| ¿Tenés alguna enfermedad de base? (diabetes, hipertensión, problemas cardíacos, trastornos de coagulación, etc.) | Sí / No \+ texto libre si dice Sí |
| ¿Tomás alguna medicación de forma habitual? ¿Cuál y en qué dosis? | Sí / No \+ texto libre si dice Sí |
| ¿Tenés alergia conocida a medicamentos, anestesia o materiales dentales? | Sí / No \+ texto libre si dice Sí |
| ¿Has tenido cirugías o tratamientos médicos importantes recientemente? | Sí / No \+ texto libre si dice Sí |
| ¿Sos fumador/a? ¿Cantidad aproximada por día? | Sí / No \+ cantidad si dice Sí |
| En mujeres: ¿Estás embarazada o en período de lactancia? | Sí / No / No aplica |
| ¿Has tenido experiencias previas negativas en tratamientos dentales? | Sí / No \+ descripción breve si dice Sí |
| ¿Tenés algún temor o preocupación específica que quieras que la doctora tenga en cuenta? | Texto libre opcional |

| CÓMO SE PRESENTA LA ANAMNESIS EN LA PLATAFORMA |
| :---- |
| Cuando la Dra. abre la ficha del paciente antes de su consulta, ve: |
|  |
| ANAMNESIS — \[Nombre Paciente\] — \[Fecha de carga\] |
| → Enfermedades de base: \[respuesta\] |
| → Medicación habitual: \[respuesta\] |
| → Alergias: \[respuesta\] |
| → Cirugías previas: \[respuesta\] |
| → Fumador/a: \[respuesta\] |
| → Embarazo/lactancia: \[respuesta\] |
| → Experiencias negativas previas: \[respuesta\] |
| → Temores / observaciones: \[respuesta\] |
|  |
| Si algún campo tiene alertas (alergias, medicación anticoagulante, embarazo) |
| se destacan visualmente en rojo para que la Dra. los vea de inmediato. |

# **08 — MÓDULO 5 — AGENDA Y GESTIÓN DE TURNOS**

El bot puede mostrar turnos disponibles en tiempo real y permitir al paciente seleccionar el que más le conviene, según el profesional y el tipo de consulta.

## **Configuración de la Agenda**

| PARÁMETRO | CONFIGURACIÓN INICIAL |
| :---- | :---- |
| Profesionales | 2 actualmente: Dra. María Laura Delgado \+ colegas según especialidad |
| Días disponibles | Lunes a Viernes (sábado y domingo cerrado) |
| Horarios Dra. Delgado | Lun 13-19 / Mar 10-17 / Mié 12-18 / Jue 10-17 / Vie 14-19 |
| Duración de turnos | Variable según tratamiento — se configura por tipo de servicio |
| Bloqueo de agenda | La Dra. puede bloquear días/horarios desde la plataforma sin intervención técnica |
| Dirección según día | A confirmar con la Dra. qué dirección corresponde a cada día |

## **Flujo de Toma de Turno por WhatsApp**

| CONVERSACIÓN — TOMA DE TURNO |
| :---- |
| Paciente: Quiero pedir un turno |
|  |
| Bot: ¡Genial\! ¿Con qué motivo querés venir? |
|      1\. Primera consulta / evaluación |
|      2\. Implantes o cirugía |
|      3\. Blanqueamiento BEYOND |
|      4\. Armonización orofacial |
|      5\. Otro motivo |
|  |
| Paciente: \[elige opción\] |
|  |
| Bot: Perfecto. Estos son los próximos turnos disponibles: |
|      📅 Martes 14/01 — 10:00 hs |
|      📅 Martes 14/01 — 11:30 hs |
|      📅 Miércoles 15/01 — 12:00 hs |
|      📅 Jueves 16/01 — 10:00 hs |
|  |
|      ¿Cuál te queda mejor? |
|  |
| Paciente: El martes a las 10 |
|  |
| Bot: ¡Perfecto\! Tu turno queda agendado: |
|      📅 Martes 14 de enero — 10:00 hs |
|      📍 \[Dirección según el día\] |
|      👩‍⚕️ Dra. María Laura Delgado |
|  |
|      Te enviaré un recordatorio 24 hs antes. ¿Algo más en lo que pueda ayudarte? |

## **Modificación y Cancelación de Turnos**

* El paciente puede escribir 'cancelar turno' o 'cambiar turno' en cualquier momento

* El bot verifica el turno activo del paciente y ofrece opciones de reprogramación

* Al cancelar, el horario se libera automáticamente en la agenda de la plataforma

* Se notifica automáticamente a la Dra. cuando se cancela un turno

# **09 — MÓDULO 6 — RECORDATORIOS Y CONFIRMACIONES**

Los recordatorios son automáticos y no requieren intervención manual. El sistema los envía según los turnos registrados en la plataforma.

## **Flujo de Recordatorios**

| MOMENTO | MENSAJE AUTOMÁTICO |
| :---- | :---- |
| 24 hs antes del turno | Recordatorio completo: nombre, fecha, hora, dirección. Solicita confirmación. |
| Confirmación del paciente | Si dice 'Sí / Confirmo' → marca como confirmado en la plataforma |
| Si no confirma en 4 hs | Reenvío de recordatorio con mensaje más directo. Segunda oportunidad de confirmar. |
| Día del turno (2 hs antes) | Mensaje breve: 'Hola \[Nombre\], hoy a las \[hora\] te esperamos. ¡Nos vemos pronto\!' |
| Reprogramación por demora | Si la Dra. necesita avisar demora, puede enviar el mensaje desde la plataforma con 1 click |

| TEXTO DEL RECORDATORIO — BASE (basado en conversaciones reales del consultorio) |
| :---- |
| 👋 ¡Hola \[Nombre\]\! |
|  |
| 💬 Te recordamos tu turno con la Dra. María Laura Delgado |
| 📅 \[Día\] \[Fecha completa\] |
| 🕐 \[Hora\] |
| 📍 \[Dirección según el día\] |
|  |
| ¿Podés confirmar tu asistencia? Respondé: |
| ✅ SI — para confirmar |
| ❌ NO — para cancelar o reprogramar |
|  |
| Para cualquier cambio, no dudes en avisarnos. |

## **Registro en la Plataforma**

* Cada recordatorio enviado queda registrado con fecha y hora

* El estado de confirmación del paciente se actualiza automáticamente

* La Dra. puede ver en su dashboard: turnos confirmados / sin confirmar / cancelados del día

# **10 — MÓDULO 7 — PROTOCOLO DE URGENCIAS**

El bot detecta automáticamente cuando el paciente describe una urgencia real y activa el protocolo definido por la Dra. Laura Delgado. Este módulo es crítico para la seguridad del paciente.

| URGENCIAS REALES — CRITERIOS DEFINIDOS POR LA DRA. DELGADO |
| :---- |
| El sistema marca como URGENCIA REAL y deriva a consulta prioritaria cuando el paciente refiere: |
|  |
| → Dolor intenso que no cede con analgésicos habituales |
| → Inflamación importante en cara o cuello, con dificultad para abrir la boca, hablar o tragar |
| → Sangrado abundante que no se controla con presión local |
| → Traumatismo en cara o boca (golpe, caída, accidente) |
| → Fiebre asociada a dolor dental o inflamación |
| → Pérdida brusca de una prótesis fija o fractura que impida comer o hablar |

## **Notificación a la Dra.**

* Cuando el bot detecta una urgencia, envía una notificación inmediata a la Dra. (WhatsApp o plataforma)

* La notificación incluye el nombre del paciente, su número y el resumen de lo que describió

* La Dra. puede responder al paciente directamente desde la notificación

* La urgencia queda registrada en la plataforma con timestamp

# **11 — MÓDULO 8 — SEGUIMIENTO POST-CONSULTA**

Después de cada consulta, el sistema envía mensajes automáticos según el tratamiento realizado y el calendario que la Dra. configure para cada paciente. Ninguna secretaria puede hacer esto de forma consistente — el sistema sí.

## **Cómo se Activa el Seguimiento**

1. La Dra. carga la sesión en la plataforma al terminar la consulta

2. Indica el tipo de tratamiento realizado y si el paciente debe volver

3. Configura el plazo de seguimiento (30, 60, 90 días o fecha específica)

4. El sistema programa automáticamente el mensaje de seguimiento

5. En la fecha indicada, el mensaje se envía solo al paciente

## **Tipos de Seguimiento según Tratamiento**

| TRATAMIENTO | SEGUIMIENTO CONFIGURADO |
| :---- | :---- |
| Implante reciente (post-cirugía) | 24 hs: ¿Cómo te sentís? ¿Tuviste sangrado o dolor intenso? / 72 hs: control de cicatrización / 7 días: ¿Cómo vas con la recuperación? |
| Blanqueamiento BEYOND | 7 días: ¿Cómo quedó tu sonrisa? Recordatorio de usar el kit de mantenimiento |
| Armonización orofacial | 3 días: ¿Cómo evolucionó? ¿Alguna consulta? / 30 días: Imagen de resultado |
| Tratamiento multi-etapa (implantes) | Recordatorio de próxima etapa según fecha acordada en la sesión |
| Control de rutina | 30-60-90 días: Recordatorio de próximo control según indicación de la Dra. |

| TEXTO BASE — SEGUIMIENTO POST-CONSULTA (editable por la Dra.) |
| :---- |
| Hola \[Nombre\]\! Te saluda el consultorio de la Dra. Delgado. |
|  |
| Han pasado \[X días/semanas\] desde tu consulta. |
| ¿Cómo te sentís? ¿Todo bien con \[el tratamiento\]? |
|  |
| Cualquier duda o molestia, escribinos acá. |
| Estamos para acompañarte en todo el proceso 😊 |

## **Registro de Sesión — Lo que Carga la Dra. en la Plataforma**

| CAMPO | DESCRIPCIÓN |
| :---- | :---- |
| Motivo de consulta del día | Lo que trajo al paciente ese día |
| Evaluación y diagnóstico | Hallazgos clínicos |
| Tratamientos realizados | Detalle del procedimiento |
| Materiales e insumos | Incluyendo números de serie de implantes, injertos, hialurónico, bótox |
| Medicación indicada | Receta y recomendaciones postoperatorias |
| Próxima cita | Fecha y objetivo de la próxima sesión |
| Observaciones relevantes | Acuerdos especiales, notas del caso |
| Seguimiento programado | Plazo y tipo de mensaje post-consulta a enviar |

# **12 — MÓDULO 9 — REACTIVACIÓN DE PACIENTES INACTIVOS**

El sistema monitorea automáticamente la base de pacientes. Si un paciente no tiene actividad (turno, respuesta o consulta) en un período definido, lanza una campaña de reactivación personalizada.

## **Criterios de Inactividad**

| TIPO DE PACIENTE | CRITERIO DE REACTIVACIÓN |
| :---- | :---- |
| Paciente con tratamiento en curso sin turno programado | Si pasaron más de X días sin nuevo turno → recordatorio de continuar el tratamiento |
| Paciente de rutina (control, blanqueamiento) | Si pasaron más de 60/90 días sin visita → invitación a control |
| Paciente con tratamiento completado | A los 6 meses y al año → recordatorio de control o mantenimiento |
| Lead que consultó pero nunca sacó turno | Si pasaron más de 7 días sin turno → seguimiento con oferta de evaluación gratuita |
| Paciente inactivo general (más de 1 año) | Campaña de reactivación con mensaje personalizado |

| TEXTO BASE — REACTIVACIÓN PACIENTE INACTIVO |
| :---- |
| Hola \[Nombre\]\! Te saluda el consultorio de la Dra. María Laura Delgado. |
|  |
| Hace un tiempo que no te vemos por acá y queríamos saber cómo estás. |
|  |
| \[Si tiene tratamiento en curso:\] |
| Sabemos que el proceso de \[tratamiento\] puede llevar su tiempo. |
| Si tenés alguna duda o querés retomar, estamos acá. |
|  |
| \[Si es control de rutina:\] |
| Tu próximo control de \[motivo\] estaría venciendo. |
| ¿Querés que te ayudemos a coordinar un turno? |
|  |
| Escribinos cuando quieras 😊 |

## **Configuración del Período de Inactividad**

* Los plazos de reactivación los define la Dra. desde la plataforma para cada tipo de tratamiento

* Se puede activar o desactivar la campaña de reactivación por segmento de paciente

* Máximo 1 mensaje de reactivación cada 30 días por paciente (evitar spam)

* Si el paciente responde, entra automáticamente al flujo activo del bot

# **13 — MÓDULO 10 — CANAL INSTAGRAM**

## **Respuestas Automáticas en Instagram**

| TIPO DE MENSAJE EN IG | ACCIÓN DEL BOT |
| :---- | :---- |
| '¿Cuánto cuesta un implante?' | Responde en IG con info general \+ invita a WhatsApp para consulta personalizada |
| '¿Atienden por obra social?' | Responde directamente en IG (No, particular) |
| '¿Cómo saco turno?' | Da el link de WhatsApp para agendar |
| 'Me gustaría información de blanqueamiento' | Responde info básica \+ enlaza a WhatsApp |
| Comentario en publicación con consulta | DM automático invitando a continuar por WhatsApp |

# **14 — PLATAFORMA DE GESTIÓN — ESTRUCTURA DE DATOS**

La plataforma es el corazón del sistema. La Dra. y su equipo la usan para ver la agenda, gestionar pacientes, cargar sesiones y controlar los seguimientos activos.

## **Módulos de la Plataforma**

| MÓDULO | QUÉ INCLUYE |
| :---- | :---- |
| Dashboard principal | Turnos del día / mañana, confirmados vs. sin confirmar, alertas de urgencias, pacientes nuevos |
| Gestión de pacientes | Ficha completa: datos personales, admisión, anamnesis, historial de turnos, sesiones, seguimientos |
| Agenda | Vista semanal/mensual por profesional, bloqueo de horarios, alta de turnos manual |
| Historia clínica | Registro de sesiones con todos los campos definidos por la Dra. (incluyendo números de serie) |
| Seguimientos activos | Lista de todos los seguimientos programados: quién, cuándo, qué mensaje |
| Pacientes inactivos | Listado con filtros por días de inactividad y tipo de paciente |
| Reportes | Nuevos pacientes por mes, origen del paciente, tasas de confirmación, tratamientos más frecuentes |
| Configuración del bot | Editar respuestas, horarios, mensajes de seguimiento — sin intervención técnica |

## **Ficha del Paciente — Estructura**

| CAMPOS DE LA FICHA COMPLETA DE PACIENTE |
| :---- |
| DATOS PERSONALES: Nombre, DNI, fecha nac, teléfono WSP, emai |
| ORIGEN: Canal de captación, campaña, fecha primer contacto |
| ANAMNESIS: Respuestas al cuestionario de salud (con alertas visuales en campos críticos) |
| TURNOS: Historial completo de turnos (fecha, hora, estado, dirección) |
| HISTORIA CLÍNICA: Registro de sesiones (motivo, diagnóstico, tratamiento, materiales, próx. cita) |
| SEGUIMIENTOS: Seguimientos programados y registros de los enviados |
| ESTADO DEL PACIENTE: Activo / En tratamiento / Control / Inactivo |
| NOTAS: Campo libre para observaciones de la Dra. o el equipo |

## **Accesos a la Plataforma**

| ROL | ACCESO | PERMISOS |
| :---- | :---- | :---- |
| Dra. María Laura Delgado | Total | Ver y editar todo: pacientes, agenda, historia clínica, configuración del bot |
| Colegas odontólogos | Parcial | Ver su agenda, cargar sesiones de sus pacientes, ver fichas asignadas |
| Soporte Codexy | Técnico | Acceso de mantenimiento — solo configuración técnica, no a datos de pacientes |

# **15 — FLUJOS DE AUTOMATIZACIÓN — DIAGRAMA DE PROCESOS**

## **Flujo 1 — Paciente Nuevo por WhatsApp**

| FLUJO PACIENTE NUEVO |
| :---- |
| \[ENTRADA\] Paciente escribe al WhatsApp del consultorio |
|   ↓ |
| \[DETECCIÓN\] ¿Existe en la base de datos? → NO |
|   ↓ |
| \[ORIGEN\] Detectar UTM / origen del mensaje → registrar |
|   ↓ |
| \[BIENVENIDA\] Mensaje de bienvenida  |
|   ↓ |
| \[ADMISIÓN\] Recolectar datos de admisión uno a uno → crear ficha en plataforma |
|   ↓ |
| \[ANAMNESIS\] ¿Quiere turno? → Si SÍ → hacer cuestionario de salud |
|   ↓ |
| \[AGENDA\] Mostrar turnos disponibles → paciente elige |
|   ↓ |
| \[CONFIRMACIÓN\] Confirmar turno por escrito al paciente → registrar en agenda |
|   ↓ |
| \[RECORDATORIO\] Programar recordatorio automático 24 hs antes |
|   ↓ |
| \[NOTIFICACIÓN\] Alertar a la Dra. de nuevo paciente agendado |

## **Flujo 2 — Paciente Existente**

| FLUJO PACIENTE EXISTENTE |
| :---- |
| \[ENTRADA\] Paciente escribe al WhatsApp |
|   ↓ |
| \[DETECCIÓN\] ¿Existe en la base de datos? → SÍ |
|   ↓ |
| \[SALUDO PERSONALIZADO\] 'Hola \[Nombre\], ¿en qué puedo ayudarte?' |
|   ↓ |
| \[INTENCIÓN\] ¿Qué necesita? → Turno / Consulta / Urgencia / Seguimiento |
|   ↓ |
| Si TURNO → mostrar disponibilidad → agendar |
| Si CONSULTA → responder con IA según FAQs configuradas |
| Si URGENCIA → activar Módulo 7 (protocolo de urgencias) |
| Si SEGUIMIENTO → responder y registrar en historial |

## **Flujo 3 — Seguimiento y Reactivación**

| FLUJO AUTOMÁTICO SIN INTERVENCIÓN HUMANA |
| :---- |
| \[TRIGGER DIARIO\] n8n corre proceso de verificación a las 09:00 hs |
|   ↓ |
| \[RECORDATORIOS\] ¿Hay turnos mañana? → enviar recordatorios a los pacientes |
|   ↓ |
| \[SEGUIMIENTOS\] ¿Hay seguimientos post-consulta programados para hoy? → enviar |
|   ↓ |
| \[INACTIVOS\] ¿Hay pacientes que cumplen criterio de inactividad hoy? → lanzar reactivación |
|   ↓ |
| \[REPORTE\] Generar resumen del día para la Dra. (nuevos pacientes, confirmaciones, seguimientos enviados) |

# **16 — FAQs CONFIGURADAS EN EL BOT**

Estas son las preguntas frecuentes reales que los pacientes hacen al consultorio (extraídas del relevamiento de la Dra. Delgado). El bot las responde automáticamente.

| PREGUNTA REAL DEL PACIENTE | RESPUESTA CONFIGURADA EN EL BOT |
| :---- | :---- |
| ¿Atienden por obra social? | El consultorio atiende de forma particular. Pero organizamos el pago en etapas para hacer el tratamiento más accesible. ¿Querés que te cuente más opciones? |
| ¿Cómo saco un turno? | ¡Con gusto\! Escribime 'turno' y te muestro los horarios disponibles para coordinar el mejor momento para vos. |
| ¿Cuáles son las formas de pago? | Aceptamos efectivo y transferencia bancaria. También podemos organizar el pago en etapas, conversando con la doctora según cada caso. |
| ¿En qué consiste el blanqueamiento BEYOND y por qué es diferente? | El blanqueamiento BEYOND® es una tecnología profesional que actúa en 20 minutos en el sillón. Es diferente a los kits caseros porque tiene una concentración controlada, luz de activación y resultados inmediatos. Incluye kit de mantenimiento para casa. |
| ¿Tienen disponibilidad para esta semana? | Contame qué día y horario te conviene y te busco la disponibilidad. |
| ¿Se puede hacer la consulta en persona sin turno? | Para garantizar que la doctora pueda dedicarte el tiempo que necesitás, trabajamos con turno previo. Puedo coordinarte uno rápido. |
| ¿El tratamiento de implantes es muy doloroso? | La doctora trabaja con anestesia local y técnicas de mínima invasión. La gran mayoría de los pacientes se sorprenden de lo cómodo que resulta el proceso. El postoperatorio suele ser muy llevadero. |
| ¿Cuáles son las formas de pago? | Efectivo y transferencia. Además, si el tratamiento es de mayor costo, se puede organizar en etapas. |
| ¿Se va a ver natural el resultado? | Sí. El enfoque de la Dra. está en lograr resultados en armonía con tu rostro y tu edad. Todo se planifica de forma personalizada para que el resultado se vea natural. |
| ¿Tengo que andar sin dientes hasta tener la prótesis? | En muchos casos se puede hacer una carga inmediata o provisorio. La posibilidad depende del caso clínico. Es algo que se evalúa en la primera consulta. |
| ¿Necesito estudios previos? | Para implantes o cirugías generalmente se requiere tomografía. La doctora te indica exactamente qué estudios necesitás según tu caso en la primera consulta. |
| ¿Si tengo poco hueso puedo colocarme implantes? | Muchas veces sí. La Dra. trabaja con protocolos avanzados para pacientes con poco hueso, incluyendo técnicas de regeneración ósea o implantes especiales. La tomografía 3D determina la opción ideal. |
| Me dijeron que no soy candidata para implantes | Eso no siempre es definitivo. La Dra. trabaja con casos que otros profesionales rechazan y tiene soluciones para situaciones complejas. Vale la pena una segunda evaluación. |

# **17 — PLAN DE IMPLEMENTACIÓN POR FASES**

## **Fase 1 — Configuración Base (Semanas 1-2)**

| FASE 1 — ENTREGABLES |
| :---- |
| → Configuración de WhatsApp Business API con el número del consultorio |
| → Desarrollo de flujos básicos en n8n: bienvenida, menú, FAQs |
| → Integración del bot con la plataforma de gestión (base de datos de pacientes) |
| → Módulo de admisión: recolección de datos y creación de ficha |
| → Módulo de agenda: conexión con los horarios de los 2 profesionales |
| → Toma de turnos básica (mostrar disponibilidad \+ confirmar) |
| → Protocolo de urgencias configurado según criterios de la Dra. |
| → Pruebas internas y ajuste de tono / respuestas |

## **Fase 2 — Automatizaciones de Seguimiento (Semanas 3-4)**

| FASE 2 — ENTREGABLES |
| :---- |
| → Módulo de recordatorios: automático 24 hs antes con confirmación |
| → Módulo de anamnesis: cuestionario de salud en el flujo pre-consulta |
| → Módulo de seguimiento post-consulta: integrado con el registro de sesiones |
| → Historia clínica: formulario de carga para la Dra. con todos los campos definidos |
| → Dashboard de la plataforma: turnos del día, confirmaciones, nuevos pacientes |
| → Pruebas con pacientes reales (modo beta con feedback de la Dra.) |

## **Fase 3 — Canal Instagram y Analítica (Semana 5\)**

| FASE 3 — ENTREGABLES |
| :---- |
| → Conexión de DMs de Instagram al sistema |
| → Flujo de derivación Instagram → WhatsApp |
| → Módulo de detección de origen (UTM params / Meta Ads / Google Ads) |
| → Módulo de reactivación de pacientes inactivos |
| → Reportes básicos: nuevos pacientes, origen, tasas de confirmación |
| → Capacitación a la Dra. y equipo en el uso de la plataforma |
| → Entrega del sistema completo en producción |

## **Cronograma Estimado**

| FASE | PERÍODO | HITO DE ENTREGA |
| :---- | :---- | :---- |
| Fase 1 — Base | Semanas 1-2 | Bot activo \+ agenda \+ admisión funcionando |
| Fase 2 — Seguimientos | Semanas 3-4 | Recordatorios \+ anamnesis \+ historia clínica |
| Fase 3 — IG y analítica | Semana 5 | Sistema completo \+ capacitación \+ entrega |

# **18 — CRITERIOS DE ACEPTACIÓN Y ENTREGA**

El sistema se considera entregado cuando cumple todos los criterios de aceptación definidos abajo. Antes de la entrega final se hace una sesión de prueba conjunta con la Dra.

## **Criterios de Aceptación por Módulo**

| MÓDULO | CRITERIO DE ACEPTACIÓN |
| :---- | :---- |
| Bot WhatsApp — Bienvenida | Responde en menos de 3 segundos. El tono es reconocido como del consultorio por la Dra. |
| Admisión paciente nuevo | Todos los campos se guardan correctamente en la plataforma. La ficha queda completa. |
| Anamnesis | Las respuestas aparecen ordenadas en la ficha con alertas en campos críticos. |
| Agenda — Toma de turno | El turno se agenda correctamente y queda bloqueado el horario en la plataforma. |
| Recordatorio 24 hs | Se envía automáticamente sin intervención manual. La confirmación actualiza el estado. |
| Protocolo urgencias | Al describir síntomas de urgencia, el bot activa el protocolo en menos de 1 mensaje. |
| Seguimiento post-consulta | Los mensajes se envían en la fecha programada por la Dra. sin intervención. |
| Reactivación inactivos | Los pacientes inactivos aparecen en el listado según los criterios configurados. |
| Canal Instagram | Los DMs reciben respuesta automática en menos de 1 minuto. |
| Historia clínica | La Dra. puede cargar una sesión completa en menos de 5 minutos desde la plataforma. |
| Reportes | El dashboard muestra datos reales del día sin retrasos. |

| PROCESO DE ENTREGA |
| :---- |
| 1\. Sesión de testing conjunto con la Dra. (1-2 horas) |
| 2\. Ajustes finales de tono, respuestas y configuraciones |
| 3\. Capacitación del equipo en el uso de la plataforma (1 sesión de 1 hora) |
| 4\. Período de soporte intensivo: 2 semanas post-lanzamiento con respuesta en 2 hs |
| 5\. Manual de uso entregado por escrito |
| 6\. Entrega formal con firma de conformidad |

## **Soporte y Mantenimiento Post-Entrega**

* Soporte técnico mensual incluido en el pago de mantenimiento

* Tiempo de respuesta ante incidentes: menos de 2 horas hábiles

* Actualizaciones menores de respuestas y mensajes: incluidas

* Nuevos módulos o integraciones: se presupuestan por separado

* Backup semanal de la base de datos de pacientes

**CODEXY — Agencia de Automatización & IA  |  Documentación Técnica de Proyecto**

Cliente: Dra. María Laura Delgado — Neuquén  |  Versión 1.0  |  2025  |  Confidencial