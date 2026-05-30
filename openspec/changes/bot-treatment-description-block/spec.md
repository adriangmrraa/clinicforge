# Spec — DLD-9: Bot describes/recommends treatments

**Change ID:** `bot-treatment-description-block`
**Ticket:** `DLD-9`
**Status:** Draft
**Fecha:** 2026-04-17

---

## 1. Contexto y problema

El bot TORA actualmente puede describir, explicar o recomendar tratamientos clínicos a los pacientes a través de dos vectores:

1. **`get_service_details` retorna `description` cruda cuando `ai_response_template` es NULL** (línea 5059 de `main.py`). Si el administrador no cargó una plantilla, el bot devuelve la descripción técnica de la BD incluyendo duración, complejidad y precio provisional.

2. **El system prompt instruye llamar `get_service_details` en la primera mención de un tratamiento** (línea 9071 de `main.py`). La regla dice: *"si el paciente menciona un tratamiento por PRIMERA VEZ con interés amplio [...] → DEBÉS llamar get_service_details PRIMERO"*, forzando la presentación de contenido clínico incluso cuando la plantilla está vacía.

3. **El docstring de `get_service_details` es ambiguo** (línea 4982-4985). Incluye *"El paciente menciona una necesidad que mapea con un servicio conocido"* como trigger, lo cual es suficientemente amplio para que el LLM llame la tool ante cualquier mención, no solo ante pedidos explícitos de información.

4. **Las FAQs pueden contener detalle clínico** cargado por el administrador. Cuando el bot parafrasea o mezcla FAQs con `description`, produce recomendaciones clínicas con voz de autoridad médica.

Este comportamiento viola el principio de que un chatbot de agenda NO es un consejero médico. La doctora es la única fuente de recomendación clínica. El rol del bot se limita a agenda, precios, disponibilidad e información logística.

---

## 2. Requisitos

### R1 — `get_service_details` NO devuelve la columna `description`

La columna `description` de `treatment_types` es un campo interno del sistema (usado en formularios del staff, historiales, etc.). Su contenido NO fue redactado para ser leído por pacientes ni para ser procesado por un LLM como información clínica autorizable.

**La tool `get_service_details` DEBE excluir `description` de toda respuesta que retorne al agente**, independientemente del valor de `ai_response_template`.

Datos que la tool SÍ puede retornar:
- `ai_response_template` (texto redactado explícitamente para el paciente por la doctora)
- `patient_display_name` o `name` (nombre del tratamiento)
- Lista de profesionales asignados
- URLs de imágenes del tratamiento

Datos que la tool NO puede retornar:
- `description`
- `default_duration_minutes`
- `complexity_level`
- Cualquier campo no listado en el bloque anterior

### R2 — Cuando `ai_response_template` es NULL, retornar mensaje genérico de agenda

Si el registro no tiene `ai_response_template` configurado, la tool devuelve exactamente:

```
Para conocer todos los detalles sobre este tratamiento, te recomendamos agendar una consulta de evaluación con la doctora.
```

Este mensaje es fijo. No incluye nombre de tratamiento, duración, precio ni ningún dato del registro.

Si hay imágenes disponibles, se incluyen los marcadores `[LOCAL_IMAGE:...]` igualmente (las imágenes son contenido visual, no clínico).

Si hay profesionales asignados, se incluye la lista de profesionales después del mensaje genérico.

### R3 — El system prompt NO instruye llamar `get_service_details` en la primera mención de un tratamiento

La sección "PRIORIDAD DE RESPUESTA — REGLA DE PRIMERA MENCIÓN" (líneas 9067-9088 de `main.py`) y cualquier otra instrucción que fuerce o recomiende llamar `get_service_details` ante menciones de tratamientos, deben ser eliminadas o reemplazadas.

La nueva instrucción debe establecer:

- El bot responde sobre tratamientos **únicamente con FAQs** cargadas por la clínica.
- Si no hay FAQ que cubra el tema, el bot deriva hacia la agenda: *"Para más información sobre ese tratamiento, podés agendar una consulta de evaluación."*
- `get_service_details` se llama **solo** cuando el paciente pide explícitamente las imágenes del tratamiento o cuando el bot necesita verificar qué profesional realiza ese tratamiento para continuar el flujo de agenda.

### R4 — El docstring de `get_service_details` restringe el uso a pedidos explícitos de imágenes o verificación de profesional

El docstring actual permite que el LLM infiera el uso ante cualquier mención de un tratamiento. Debe reemplazarse por uno que establezca con precisión cuándo llamar y cuándo no llamar la tool:

**Nuevo docstring (exacto):**
```
Obtiene imágenes y profesionales asignados a un tratamiento específico.
USAR ÚNICAMENTE cuando:
- El paciente pide explícitamente imágenes o fotos del tratamiento ("tenés fotos de X", "me mostrás cómo queda X").
- El bot necesita resolver qué profesional realiza el tratamiento para continuar el flujo de agenda.
NO USAR para responder preguntas sobre qué es, cómo funciona, cuánto dura, si duele, o cuándo conviene un tratamiento.
Para esas preguntas: usá las FAQs. Si no hay FAQ, derivá a consulta de evaluación.
code: Código único del tratamiento devuelto por list_services (ej: 'implant', 'cleaning').
```

### R5 — El bot NUNCA describe, explica, ni recomienda tratamientos específicos

El bot no puede:
- Explicar en qué consiste un tratamiento.
- Describir el procedimiento, sus etapas o su resultado esperado.
- Comparar tratamientos entre sí.
- Recomendar un tratamiento como adecuado para la situación del paciente.
- Parafrasear, sintetizar o reformular contenido clínico de `description`, FAQs, o cualquier otra fuente.

El bot puede:
- Informar que ese tratamiento existe y que se puede agendar.
- Indicar el nombre del profesional que lo realiza.
- Mostrar imágenes si el paciente las pide.
- Indicar precio cuando la clínica tiene el precio configurado y hay FAQ que lo menciona.
- Derivar a consulta de evaluación como única respuesta ante preguntas sobre indicaciones, técnica o conveniencia.

---

## 3. Escenarios

### Escenario 1 — Mención general de un tratamiento, sin `ai_response_template`

```
Given   un paciente escribe "me interesa hacerme un implante"
And     el tratamiento 'implant' no tiene ai_response_template configurado
When    el bot procesa el mensaje
Then    el bot NO llama get_service_details
And     el bot responde con la FAQ de implantes si existe
And     si no hay FAQ, responde: "Para conocer todos los detalles, te recomendamos agendar una consulta de evaluación."
And     el bot NO describe en qué consiste el implante, ni sus etapas, ni su resultado
```

### Escenario 2 — Mención general de un tratamiento, con `ai_response_template`

```
Given   un paciente escribe "quiero saber sobre el blanqueamiento"
And     el tratamiento 'blanqueamiento' tiene ai_response_template = "Realizamos blanqueamiento profesional con tecnología LED..."
When    el bot procesa el mensaje
Then    el bot SÍ puede mostrar el ai_response_template (fue redactado por la doctora para este fin)
And     el bot lo muestra vía FAQ, NO vía get_service_details a menos que el paciente pida imágenes
```

### Escenario 3 — Paciente pide fotos de un tratamiento

```
Given   un paciente escribe "tenés fotos de cómo quedan las carillas?"
When    el bot procesa el mensaje
Then    el bot llama get_service_details('estetica') o el código correspondiente
And     la tool retorna SOLO los marcadores [LOCAL_IMAGE:...] y el ai_response_template (si existe)
And     la tool NO incluye description, duración ni complejidad en la respuesta
And     si no hay ai_response_template, la tool retorna el mensaje genérico de agenda + imágenes
```

### Escenario 4 — Llamado a `get_service_details` para tratamiento sin `ai_response_template`

```
Given   el agente llama get_service_details('endodoncia')
And     el registro de endodoncia tiene description = "Tratamiento de conducto radicular en 2-3 sesiones..."
And     el registro NO tiene ai_response_template
When    la tool ejecuta
Then    la tool retorna: "Para conocer todos los detalles sobre este tratamiento, te recomendamos agendar una consulta de evaluación con la doctora."
And     la tool NO incluye description, duración ni complejidad en el string de retorno
And     si hay imágenes, las agrega igualmente
And     si hay profesionales asignados, los lista igualmente
```

### Escenario 5 — Paciente pregunta si un tratamiento le conviene

```
Given   un paciente escribe "tengo dientes muy separados, ¿los brackets o las carillas serían mejor opción para mí?"
When    el bot procesa el mensaje
Then    el bot NO compara los tratamientos
And     el bot NO emite una recomendación
And     el bot responde derivando a consulta: "Esa decisión la toma la doctora en la evaluación inicial. ¿Querés que agendemos una consulta?"
```

### Escenario 6 — El paciente ya tiene una FAQ que cubre el tratamiento

```
Given   la clínica tiene una FAQ: "¿En qué consiste la limpieza?" → "Es una profilaxis profesional que dura 45 min..."
And     un paciente escribe "contame sobre la limpieza"
When    el bot procesa el mensaje
Then    el bot usa la FAQ TEXTUAL, sin parafrasear
And     el bot NO llama get_service_details
And     el bot NO agrega información adicional de la BD
```

### Escenario 7 — Verificación de profesional en flujo de agenda

```
Given   un paciente escribe "quiero turno con la doctora para implantes"
And     el bot necesita confirmar qué profesional realiza implantes
When    el bot ejecuta get_service_details para resolver el profesional
Then    la tool retorna SOLO la lista de profesionales y el ai_response_template (o mensaje genérico)
And     la tool NO retorna description en ningún caso
```

---

## 4. Criterios de aceptación

| ID | Criterio | Verificación |
|----|----------|--------------|
| AC-1 | La función `get_service_details` no incluye el campo `description` en ninguna rama de retorno | Code review: `grep "description" get_service_details` no aparece en strings de respuesta |
| AC-2 | Cuando `ai_response_template` es NULL, la tool retorna exactamente el mensaje genérico de agenda | Test unitario: `test_get_service_details_no_template_returns_generic` |
| AC-3 | El system prompt no contiene la sección "REGLA DE PRIMERA MENCIÓN" ni instrucción de llamar `get_service_details` en primera mención | Code review: líneas 9067-9088 de `main.py` eliminadas o reemplazadas |
| AC-4 | El docstring de `get_service_details` prohíbe explícitamente su uso para preguntas de qué-es/cómo-funciona/cuándo-conviene | Code review del docstring actualizado |
| AC-5 | El system prompt contiene una regla explícita que prohíbe al bot describir, explicar o recomendar tratamientos | Code review: sección R5 presente en el prompt |
| AC-6 | El system prompt establece que ante preguntas sobre tratamientos sin FAQ: la única respuesta válida es derivar a consulta de evaluación | Code review: instrucción presente en el prompt |
| AC-7 | `get_service_details` retorna imágenes y profesionales igualmente aunque `ai_response_template` sea NULL | Test unitario: `test_get_service_details_no_template_still_sends_images` |
| AC-8 | `list_services` no se modifica en este cambio y sigue devolviendo nombres sin descripción | Sin cambios en `list_services`; code review confirma |

---

## 5. Fuera de alcance

- **Modificación de `list_services`**: esa tool ya retorna solo nombres, sin descripción. No se toca.
- **Validación o moderación de contenido en FAQs**: el administrador puede cargar lo que quiera en las FAQs. Este cambio no valida ni filtra el contenido de las FAQs. La responsabilidad de qué poner en una FAQ es del administrador de la clínica.
- **Campo `ai_response_template` en el frontend**: la UI de edición de tratamientos que permite cargar la plantilla existe y no se modifica.
- **Flujo de implantes/prótesis (F1-F8)**: los flujos comerciales de implantes tienen sus propias instrucciones en el system prompt. Este cambio NO toca esos flujos, dado que están basados en `ai_response_template` ya validados por la doctora.
- **Nova (voice assistant)**: Nova tiene sus propias tools (`listar_tratamientos`, `ver_odontograma`). Este cambio aplica exclusivamente al agente LangChain de TORA (WhatsApp/web chat). Nova queda fuera de alcance.
- **Agentes del MultiAgentEngine**: las tools `DENTAL_TOOLS` son compartidas entre SoloEngine y MultiAgentEngine, por lo que R1 y R2 se aplican automáticamente a ambos motores. Sin embargo, los system prompts de los agentes especializados (`agents/specialists.py`) no se modifican en este cambio.
- **Retroactividad en conversaciones en curso**: el cambio aplica a mensajes nuevos. Las conversaciones existentes en Redis no se limpian.

---

## 6. Archivos afectados (referencia para implementación)

| Archivo | Cambio |
|---------|--------|
| `orchestrator_service/main.py` | R1: remover `description` del SELECT y del bloque `else` en `get_service_details` (líneas 4994, 5006, 5059) |
| `orchestrator_service/main.py` | R2: reemplazar bloque `else` con mensaje genérico fijo (línea 5058-5061) |
| `orchestrator_service/main.py` | R3: eliminar sección "REGLA DE PRIMERA MENCIÓN" del system prompt (líneas 9067-9088) + agregar regla R5 |
| `orchestrator_service/main.py` | R4: reemplazar docstring de `get_service_details` (líneas 4981-4987) |
| `tests/` | AC-2, AC-7: tests unitarios para `get_service_details` con y sin template |
