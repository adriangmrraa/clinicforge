# PROMPT_CHANGELOG — Agente de WhatsApp (Paula / SoloEngine / TORA)

Registro de cambios del **system prompt** del agente y del **contexto que se le inyecta**.
Sirve para responder *"desde qué cambio empezó a fallar"* y poder **volver a una versión conocida-buena**.

> El prompt se arma en `orchestrator_service/main.py` → `build_system_prompt()` (empieza en **main.py:10991**),
> es un f-string grande. El contexto del turno (próximo turno, visual, audio, media) se arma en
> `orchestrator_service/services/buffer_task.py`.

---

## Cómo volver atrás (rollback)

1. **Un cambio de prompt = un commit.** Cada fila de la tabla de abajo apunta a su commit.
2. Para revertir un cambio puntual: `git revert <commit>` y redeploy del orchestrator.
3. Para volver a un estado entero: `git checkout <commit> -- orchestrator_service/main.py` (o el archivo afectado), revisar y commitear.
4. En EasyPanel también se puede re-deployar una versión anterior desde la pestaña *Deployments*.
5. Si el problema es de comportamiento del agente y no se sabe qué commit lo causó: buscar en esta tabla la fecha en que empezó la queja y revertir desde ahí hacia atrás.

**Regla:** antes de tocar el prompt, agregá una fila acá. Nunca metas varios cambios de prompt en un mismo commit sin anotarlos.

---

## Índice de secciones del prompt (ancla por TEXTO; la línea es aproximada y se corre al editar)

> Para ubicar una sección, **buscá el texto del encabezado** (es estable) en `main.py`. La línea es solo orientativa.

| Sección | Encabezado (buscar este texto) | Línea aprox. |
|---|---|---|
| Inicio del prompt | `def build_system_prompt(` | 10991 |
| Saludo lead nuevo | `GREETING (PRIMERA INTERACCIÓN CON LEAD NUEVO)` | 11278 |
| Saludo paciente sin turno | `GREETING (PACIENTE EXISTENTE SIN TURNO FUTURO)` | 11296 |
| Saludo paciente con turno | `GREETING (PACIENTE CON TURNO FUTURO)` | 11312 |
| Flujo implantes/prótesis | `## FLUJO DE IMPLANTES Y PRÓTESIS` | 11449 |
| Cobertura antes de disponibilidad | `### REGLA DE COBERTURA ANTES DE DISPONIBILIDAD` | 11542 |
| Leads alto valor (sin hueso) | `=== F8: SIN HUESO / RECHAZADO PARA IMPLANTES ===` | 11741 |
| Flujo de agendamiento | `FLUJO DE AGENDAMIENTO (ORDEN ESTRICTO)` | 11924 |
| · Paso 1 saludo/identidad | `PASO 1: SALUDO E IDENTIDAD` | 11989 |
| · Paso 2 / 2b / 2c | `PASO 2: DEFINIR SERVICIO` … `PASO 2c: MODALIDAD` | 11990 |
| · Paso 3 / 3b profesional | `PASO 3: PROFESIONAL ASIGNADO` / `PASO 3b: PACIENTE CON TURNO EXISTENTE` | 12021 |
| · Paso 4 disponibilidad | `PASO 4: CONSULTAR DISPONIBILIDAD` | 12056 |
| · Presentación de opciones | `REGLA DE PRESENTACIÓN DE OPCIONES` | ~12125 |
| · Pide otro día/horario | `SI EL PACIENTE RECHAZA LAS OPCIONES O PIDE OTRO DÍA/HORARIO` | ~12219 |
| · Paso 4b / 4c datos+reserva | `PASO 4b: DATOS DE ADMISIÓN` / `PASO 4c: RESERVA TEMPORAL` | 12248 |
| · Paso 5/6/7 booking+confirmación | `PASO 5` / `PASO 6: AGENDAR` / `PASO 7: CONFIRMACIÓN` | 12270 |
| · Secuencia post-booking (sede+maps) | `SECUENCIA POST-BOOKING` | ~12322 |
| Reglas de lenguaje (anti-interno) | `REGLAS DE LENGUAJE CON EL PACIENTE` | 12475 |
| No repetir datos | `REGLA DE NO-REPETICIÓN DE DATOS` | 12493 |
| Pacientes existentes (regla suprema) | `PACIENTES EXISTENTES (REGLA SUPREMA` | 12498 |
| Obras sociales / coseguro | `OBRAS SOCIALES, COSEGURO Y COBERTURA — REGLAS` | 12426 |
| Reprogramación | `LLAMADO OBLIGATORIO DE TOOLS EN REPROGRAMACIÓN` | 12585 |
| Triaje y urgencias | `TRIAJE Y URGENCIAS` | 12675 |

---

## Versión actual

`PROMPT_VERSION = 2026.06.29` — cambios de cobertura OS, dictado clínico (Nova), disponibilidad por rango (Nova).

> (Pendiente, FASE 0 opcional): agregar una constante `PROMPT_VERSION` cerca de `build_system_prompt` y loguearla
> por turno en la línea `BOOKING_FLOW | LLM_RESULT` para correlacionar quejas con versiones. Se hace al primer
> cambio del prompt extenso (FASE 2/3).

---

## Registro de cambios

| Fecha | Commit | Archivo / Sección | Qué cambió | Por qué | Revertir |
|---|---|---|---|---|---|
| 2026-06-28 | `cfebe9c` | nova_prompt.py · DICTADO CLÍNICO | Forzar `crear_nota_clinica` al dictar y confirmar con detalle | El dictado respondía "listo" sin guardar | `git revert cfebe9c` |
| 2026-06-29 | `0c09584` | main.py · COBERTURA + F4 + COSEGURO | Verificar OS antes de afirmar cobertura; decir coseguro real; "no atendida → particular/reintegro" | Afirmaba cobertura falsa (Integral Salud) | `git revert 0c09584` |
| 2026-06-29 | `df0263c` / `8a18657` | nova_prompt.py + nova_tools.py · DISPONIBILIDAD | Disponibilidad por rango (no inventar días/horarios) | Inventaba horarios genéricos en rango | `git revert 8a18657` |
| 2026-06-29 | `edb11d6` | vision_service.py + chat_webhooks.py · IMÁGENES | Preservar `original_url` para que la visión guarde la descripción de la foto | El bot quedaba ciego a las fotos (match fallaba) | `git revert edb11d6` |
| 2026-06-29 | `a576e72` | main.py · GREETING paciente sin turno (regla C) | Ante "ok/dale" tras ofrecer turno → avanzar agendamiento, no repetir | El paciente quedaba en el aire (caso Susana) | `git revert a576e72` |
| 2026-06-29 | `a576e72` | buffer_task.py · `_detect_research_intent` | Detectar "antes / más cercano" para re-buscar | Pedía antes y el bot repetía las mismas opciones (Veronica) | `git revert a576e72` |
| 2026-06-29 | `a576e72` | playbook_executor.py · fallbacks playbook | Persistir el saliente en chat_messages sin conversación previa | Plantillas/AI msgs no aparecían en el chat web | `git revert a576e72` |
| 2026-06-29 | `a576e72` | main.py + buffer_task.py · AG-09 nombre placeholder | "Visitante"/"Paciente" = sin nombre → pedir datos antes de agendar | Agendaba en blanco ("no disponible", caso Romina) | `git revert a576e72` |
| 2026-06-29 | `a576e72` | main.py + nova_tools.py · COBERTURA alias ISSN | ISSN ↔ "Instituto" = misma OS (paso 1b, solo match único) | El agente no reconocía "Instituto" como ISSN | `git revert a576e72` |
| 2026-06-29 | `a576e72` | buffer_task.py · media_context foto clínica | Comentar la foto con prudencia, no derivar solo por imagen | El bot ignoraba la foto y derivaba | `git revert a576e72` |
| 2026-06-29 | `68d8006` | main.py · VERIFICACIÓN DE COMPROBANTE (tono) | No arrancar con "no pude verificarlo"; transmitir tranquilidad sin confirmar de más | El bot parafraseaba el resultado en negativo y generaba rechazo | `git revert 68d8006` |
| 2026-06-29 | `2c03f29` | nova_prompt.py + nova_tools.py · enviar_instrucciones_tratamiento | Nova puede mandar las instrucciones pre/post CARGADAS en el tratamiento (no solo plantillas HSM); completa el nombre | Faltaba poder enviar a pedido las instrucciones del tratamiento desde Telegram | `git revert 2c03f29` |
| 2026-06-29 | `a0745c4` | main.py · COSEGURO/OS (cierre condicional) | "¿Te paso turnos?" solo si el paciente NO tiene turno; si ya reservó, no re-ofrece | Re-ofrecía turnos a quien ya había agendado (efecto colateral de 0c09584) | `git revert a0745c4` |
| 2026-06-29 | `a950358` | main.py · PRESENTACIÓN DE OPCIONES + DÍA DE SEMANA | Copiar opciones verbatim (no recalcular día/fecha); "antes" sin nada más cercano → honesto; día de semana suelto → próximo real | Caso Rafael ("Martes 01/06" mal-transcripto) y Denis ("antes?" repetía las mismas) | `git revert a950358` |
| 2026-07-01 | `6a63e7e` | main.py · COMPUERTA DE SELECCIÓN (antes de PASO 4b) **+** `reschedule_appointment` (main.py:6535) | (1) No pedir datos ni agendar hasta que el paciente elija un turno ofrecido (alineado con la DETECCIÓN DE MATCH; respeta el "dale/sí" de opción única, solo repregunta con 2+ opciones ambiguas, una vez). (2) La confirmación de reprogramar usa la fecha REAL de la DB (`new_dt`), no el texto del LLM | (1) Agendaba la 1ª opción sin que el paciente confirmara (caso Emanuel — CRÍTICO). (2) Se contradecía al reprogramar (caso Martín). Revisado con agentes adversariales. | `git revert 6a63e7e` |
| 2026-07-01 | `291a836` | main.py · REGLAS DE USO DEL CONTEXTO (ÚLTIMO/PRÓXIMO TURNO) + FAST TRACK | (A) ÚLTIMO TURNO solo se comenta con SEGUIMIENTO POST-TRATAMIENTO activo; no menciona turnos viejos ni ofrece agendar a partir de ellos. (B) No re-recordar un turno recién confirmado en la misma conversación. (C) FAST TRACK exige selección antes de pedir datos (cierra el agujero de la compuerta) | (A) "veo que tuviste turno el 20/04". (B) Re-recordaba turno recién confirmado (caso Héctor). (C) FAST TRACK saltaba la compuerta (caso Emanuel). Auditoría + verificación adversarial. | `git revert 291a836` |
| 2026-07-01 | `a5d406f` | main.py · REPROGRAMACIÓN + honestidad de franja + PASO 2c/REGLA SUPREMA cobertura | (D) Reprogramar: acotar la prohibición de reschedule al caso sin-preferencia, sin contradecir el flujo directo cuando el slot pedido está libre. (E) Franja: si al pedir otra franja (mañana/tarde) check devuelve los MISMOS slots, no repetirlos como nuevos → ofrecer otro día. (F) Si el contexto trae "Obra Social registrada", no re-preguntar particular/obra social (alinea PASO 2c y REGLA SUPREMA con la REGLA DE COBERTURA 11588) | (D) Se contradecía al reprogramar (caso Martín). (E) Loop al pedir otra franja horaria (caso Martín). (F) Paciente habitual tratado como lead: re-preguntaban la obra social ya registrada (caso Laura Altamirano). Verificación adversarial (3 agentes): safe. | `git revert a5d406f` |
| 2026-07-01 | `bf35468` | main.py · PASO 2c (pregunta cálida) + [INTERNAL_DEBT] (12449) | (F2) Paciente CONOCIDO/RECURRENTE SIN cobertura cargada (particular habitual): preguntar la modalidad de forma cálida reconociéndolo, no en frío como a un lead. (H) NUNCA mostrar la etiqueta literal `[INTERNAL_DEBT:...]` al paciente; informar el saldo en lenguaje natural | (F2) Un particular habitual igual recibía la re-pregunta (el sistema no guarda "Particular"). (H) Prevención de fuga del tag interno. Verificación adversarial (2 agentes): safe. | `git revert bf35468` |
| 2026-07-01 | `fae9984` | main.py · REGLAS DE USO DEL CONTEXTO (CONFIRMACIÓN DE ASISTENCIA, ~11114) | Regla nueva: cuando el paciente confirma por texto su asistencia a un recordatorio y tiene PRÓXIMO TURNO, agradecer corto y cálido — PROHIBIDO repetir día/hora/sede, re-preguntar el horario o iniciar agendamiento. Distingue confirmar-asistencia de elegir-slot. Portado del motor multi (specialists.py:941) | Caso Susana: respondía por texto (no botón) y el bot repetía el turno + "¿todo bien con ese horario?" (fricción). Verificación adversarial (2 agentes): safe. | `git revert fae9984` |

| 2026-07-01 | `da088ef` | main.py (DETECCIÓN DE MATCH, COMPUERTA, PASO 2c, honestidad, R0, GREETING C, 2+ turnos, typo) + buffer_task.py (STATE_HINT + conteo de turnos futuros) | Pack de afinación post-auditoría: "dale" con 2+ opciones → preguntar UNA vez (antes el hint agendaba la opción 1 por defecto); compuerta sin auto-contradicción; OS registrada → confirmación afirmativa + verificar con check_insurance_coverage; excepción de honestidad; reprogramar espejado; greeting caso C; avisar 2+ turnos futuros y confirmar CUÁL | Auditoría integral (4 agentes + 18 conversaciones simuladas) halló choques entre reglas | `git revert da088ef` |
| 2026-07-02 | `4542761` | main.py (REGLA CERO, FAST TRACK, DETECCIÓN IMPLÍCITA, F5, implantes, F2 M3, coseguro 12472/12482/12486, REGLA COBERTURA 11594, PRESENTACIÓN 11277 + NOTA 11264) + email_service.py (dedup destinatarios) | Pack "particular/OS + coseguro sin montos": (1) EXCEPCIÓN de cobertura en todos los flujos rápidos — a paciente NUEVO se le pregunta particular/obra social UNA vez antes de precio/turnos (combinable en el mismo mensaje; si la cobertura ya se conoce NO se re-pregunta). (2) Eliminados los 3 ejemplos "$30.000" del prompt + regla ORIGEN ÚNICO DE CIFRAS: el coseguro se relata desde el copay_note/bloque OS tal cual, nunca cifras de ejemplos ni memorias. (3) Con OS aceptada no se usa la plantilla de precio particular. (4) Precio por profesional: list_professionals antes de cotizar si nombran a un profesional. (5) Email de derivación sin destinatarios duplicados (case-insensitive) | Caso real Héctor Navarro (07/07 12:30): agendó y cotizó $60.000 sin que NUNCA se le preguntara particular/obra social — auditoría (5 agentes, 590k tokens) confirmó 5 reglas de avance rápido que salteaban la pregunta y riesgo de loro con los "$30.000" de ejemplo tras limpiar el dato en la UI. Verificación adversarial post-fix (4 agentes) | `git revert 4542761` |
| 2026-07-02 | `0f7929b` | main.py (CIERRE DE CORTESÍA junto a "PROHIBIDO repetir" + descripción de end_conversation) + buffer_task.py (red de seguridad [SILENCIO] junto a AG-12) | Anti-loop de gracias: ante mensajes de pura cortesía sin pedido nuevo → cerrar UNA sola vez (corto) + end_conversation; si el cierre ya se hizo y el paciente vuelve a agradecer → responder exactamente `[SILENCIO]` y el sistema NO envía nada (guard de respuesta vacía existente). Si `[SILENCIO]` viene embebido con texto real, se quita el token y se envía el resto. Prohibido re-mencionar datos ya dichos en un cierre de cortesía. NUNCA aplica si hay pregunta pendiente, dato nuevo o flujo activo | Caso real Bárbara Anahí: 6+ intercambios "gracias"→"gracias a vos 😊 quedo atenta..." en loop, repitiendo el comunicado de vialidad y el turno de la hija en cada cierre | `git revert 0f7929b` |
| 2026-07-02 | `9cbbea4` | main.py (prohibición de corchetes, docstring end_conversation, guion migración, CTA directa, REGLA POST-DATOS, FUSIÓN OS+alto valor, REGLA DE COBERTURA, prioridad F2, F5 PRIORIDAD/M0, ORIGEN ÚNICO, CIERRE DE CORTESÍA) + buffer_task.py (handler [SILENCIO] case-insensitive + limpieza de puntuación) | Ola 2 — recomendaciones de la verificación adversarial: excepción [SILENCIO] en la prohibición de corchetes (contradicción real); paciente-que-vuelve pregunta modalidad en el guion; salvedad de cobertura en POST-DATOS y CTA directa; excepción F2 explícita en la regla primordial; F5 reconciliado con M0; ORIGEN ÚNICO ampliado (FAQs, prohibido derivar de %); con OS not_found/rejected el valor particular SÍ se informa; saludos reabren conversación (no silencio); ok/dale tras opciones = elección | Verificación adversarial post-fix (4 agentes, 612k tokens, 27 simulaciones): 4× "apto con observaciones", 0 críticas — esta ola aplica sus recomendaciones textuales | `git revert 9cbbea4` |
| 2026-07-02 | `9f75b40` | main.py · REGLA GESTIÓN PREVIA SIN REGISTRO (bloque tras CONSULTA DE SALDO + whitelist PROHIBICIONES + lista ESCALAR + exclusión en trigger F5) | Nueva regla: si el paciente refiere un presupuesto/plan/estudio/turno/gestión que dice que YA arregló y las tools (get_patient_payment_status Y list_my_appointments) no la encuentran → derivhumano DIRECTO con mensaje cálido, NO evaluación nueva ni "reviso de qué se trata". Refuerzos de la verificación (3 agentes): prioridad sobre F5 (presupuesto en pasado ≠ precio); obliga a llamar ambas tools antes de responder; deriva igual ante error/timeout; salida literal de tools no es CTA de agendar; precedencia explícita con MIGRACIÓN | Caso real Manuel Gerardo Lillo: paciente registrado preguntó por "el presupuesto de la contención que arreglamos", el bot no lo encontró y ofreció "coordinar una evaluación" en vez de derivar al equipo. Confirmación adversarial: APTO (5 hallazgos ALTA/MEDIA cerrados) | `git revert 9f75b40` |
| 2026-07-02 | `f12fef8` + `a4ad8f1` | main.py · REGLA GESTIÓN PREVIA SIN REGISTRO — cobertura de ESTUDIOS/PLACAS/RESULTADOS/AUTORIZACIONES | Amplía el disparador a consultas de ESTADO/LLEGADA ("¿llegaron mis placas?", "¿están mis resultados?", "¿ya llegó mi estudio?", "¿llegó/me dieron la autorización?"). Para estudios/placas/autorizaciones NO hay tool → revisar ficha/contexto y si no figura, DERIVAR. PROHIBIDO pedir "reenviá/remandá" un estudio ya dejado; para autorizaciones NO dar la explicación genérica cuando pregunta por el ESTADO de la suya (distinción ESTADO ≠ CÓMO FUNCIONAN) | Casos reales: Lucas ("¿llegaron mis placas?" → el bot improvisó "reenviámelas") + muchos preguntan "¿llegó la autorización?/¿me la dieron?" | `git revert f12fef8 a4ad8f1` |

> A partir de acá, cada cambio de prompt agrega su fila ANTES de commitear.

---

## Convención a futuro

- **Una mejora de prompt = un commit = una fila acá.**
- En el mensaje del commit, nombrar la **sección** tocada (ej. `prompt(disponibilidad): ...`).
- Si un cambio resulta malo, se revierte por su commit y se anota la reversión como una fila nueva.
- Las 3 ramas (`main` / `PRUEBAS` / `PRODUCCION`) reciben el mismo commit; el rollback aplica a las 3.
