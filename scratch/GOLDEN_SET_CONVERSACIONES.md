# Golden Set — conversaciones canónicas de regresión (agente Paula)

> La "red de pruebas" que pidió Carlos. Cada fila = una conversación tipo con la conducta ESPERADA.
> Se corre ANTES de cada cambio del prompt (manual por ahora; la meta es automatizarlo con el colector de casos).
> Si una conversación no da el resultado esperado → es un bug, no una opinión del modelo.
> Origen: el manual de conducta (artefacto blueprint) + los casos reales de Lucas (pruebas, 2026-07-03/04).

## Cómo se corre (por ahora)
Mandar cada mensaje del "paciente" al número de pruebas (idealmente RESETEADO: `3434732389`) y verificar que la respuesta cumpla el "esperado". Marcar ✅/❌.

---

## G1 — Saludo simple (rama A)
- P: "hola buenas noches"
- ✅ Esperado: saludo (3 burbujas) + **frase de orientación configurada** ("¿tratamiento específico o turno de evaluación?"). NO improvisar "¿qué necesitás ver?".

## G2 — Turno genérico sin tratamiento (rama B)
- P: "hola, necesito sacar un turno"
- ✅ Esperado: se presenta + usa la **frase de orientación configurada** tal cual. NO "¿qué necesitás ver?" ni "¿qué tratamiento necesitás?".

## G3 — Cobertura como compuerta (el bug histórico)
- P: "quiero una consulta con la dra, ¿turnos para fin de julio?"
- ✅ Esperado: pregunta **particular/OS ANTES** de mostrar turnos. NO saltar a turnos.

## G4 — Particular + encuadre alto ticket
- P (tras G3): "particular"
- ✅ Esperado: encuadra la evaluación (valor + qué incluye si es alto ticket, ej. ortodoncia/cirugía) y ofrece **2 opciones**. NO turno "seco". NO "decime qué día".

## G5 — Fin de mes / rango
- P: "jueves o viernes a fines de julio" (o "para fin de mes")
- ✅ Esperado: busca la última semana del mes y ofrece opciones de esos días; si un día no se atiende, lo explica. NO "no veo opciones" sin buscar.

## G6 — Elegir opción → agendar con datos
- P: "la 1" / "el martes" → luego "Juan Pérez 30111222"
- ✅ Esperado: confirma el turno elegido, pide **nombre completo + DNI** (no solo DNI), agenda. Confirmación **con dirección directa** (calle + Maps), sin "si querés te paso".

## G7 — Reprogramación (la regresión P0)
- P (con turno ya sacado): "che, necesito moverlo, viajo ese día" → "por la tarde jueves o martes"
- ✅ Esperado: apenas da preferencia, **muestra opciones nuevas** y reprograma. NO pedir permiso en loop ("¿querés que busque?").

## G8 — Dale ambiguo tras oferta de dirección (anti-loop)
- P: tras confirmar, si el bot ofreciera algo, "dale"
- ✅ Esperado: cumple lo ofrecido / responde útil. NO "ya tenés el turno confirmado" en loop.

## G9 — Urgencia (F2 intacto)
- P: "me duele muchísimo una muela, ¿tenés algo urgente?"
- ✅ Esperado: contiene primero (empatía), NO precio/dirección antes, ofrece turno próximo con cobertura integrada. La urgencia manda.

## G10 — Cobertura ya dada (no repreguntar)
- P: "tengo OSDE, quiero turno para limpieza el viernes"
- ✅ Esperado: NO re-pregunta cobertura; verifica OSDE (check_insurance_coverage) y ofrece. Sin fricción.

## G11 — Documentos / autorizaciones / fuera de parámetros → elevar
- P: manda una foto de una autorización / pregunta algo sin parámetros
- ✅ Esperado: NO improvisa; avisa que lo revisa el equipo y **eleva el caso** (derivhumano).

## G12 — Ya tiene turno + pregunta lateral
- P (con turno): "¿dónde queda?" / "¿cuánto es la seña?"
- ✅ Esperado: responde con los datos del turno existente. NO re-ofrece turnos.

## G13 — Particular "particular" (regresión histórica)
- P: "¿cuánto sale una extracción?" (sin OS)
- ✅ Esperado: pregunta cobertura o da el valor particular. NUNCA "no trabajamos con particular" (sinsentido).

---

## Regla de uso
Antes de promover CUALQUIER cambio de prompt a producción: correr G1–G13 en pruebas. Todos ✅ = safe.
Cualquier ❌ = no promover hasta arreglarlo. Esto es lo que hubiera evitado la regresión de reprogramación.
