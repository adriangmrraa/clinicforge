# Delta Spec: OSDE + implantes — No generar expectativa falsa de cobertura

**Change**: `bug-b2-osde-implantes-cobertura`
**Domain**: `prompt/insurance-coverage`
**Type**: Delta

---

## ADDED Requirements

### Requirement: RESPUESTA DIFERENCIADA POR TRATAMIENTO

Cuando `check_insurance_coverage` devuelve `status="accepted"` para una obra social, el bot MUST NO responder con un "Sí" genérico que el paciente pueda interpretar como cobertura total. El bot SHALL verificar si el tratamiento específico que consulta el paciente aparece en el bloque OBRAS SOCIALES del prompt como "NO cubiertos" y, de ser así, informarlo claramente.

#### Scenario: Happy path — OSDE accepted pero implante no cubierto

- GIVEN el bloque OBRAS SOCIALES en el prompt lista IMPLANTE como "NO cubiertos" para OSDE
- AND `check_insurance_coverage("OSDE")` devuelve `status: "accepted"`
- WHEN un paciente pregunta "me cubre el implante con OSDE?"
- THEN el bot MUST NO responder "Sí, trabajamos con OSDE" sin matiz
- AND el bot SHALL decir que la consulta de evaluación puede ser por OSDE
- AND el bot SHALL aclarar que el implante no tiene cobertura automática y se define después de la evaluación
- AND el bot MAY mencionar la opción de particular o reintegro

#### Scenario: Edge case — OSDE accepted y tratamiento SÍ cubierto

- GIVEN el bloque OBRAS SOCIALES lista CONSULTA como "Cubiertos" para OSDE
- AND `check_insurance_coverage("OSDE")` devuelve `status: "accepted"`
- WHEN un paciente pregunta "la consulta me cubre con OSDE?"
- THEN el bot MAY responder "Sí, trabajamos con OSDE para la consulta 😊"
- AND el bot SHALL mencionar posible coseguro si corresponde

#### Scenario: Edge case — Paciente pregunta por OSDE sin especificar tratamiento

- GIVEN un paciente dice "tengo OSDE" sin especificar tratamiento
- WHEN el bot responde
- THEN el bot SHALL confirmar que se acepta OSDE para consulta
- AND el bot SHALL NO asumir cobertura de ningún tratamiento específico
- AND el bot SHALL ofrecer coordinar turno de evaluación

### Requirement: ELIMINAR PROHIBICIÓN CONTRADICTORIA

La regla "PROHIBIDO confirmar qué cubre o no cubre cada obra social. PROHIBIDO listar tratamientos incluidos/excluidos." SHALL ser reemplazada por una regla que PERMITA informar cobertura cuando hay datos en el prompt.

#### Scenario: Bot puede informar que un tratamiento no está cubierto

- GIVEN la nueva regla permisiva en el prompt
- WHEN un paciente pregunta específicamente por cobertura de un tratamiento
- AND ese tratamiento está listado como "NO cubiertos" en el bloque OBRAS SOCIALES
- THEN el bot SHALL poder informar que el tratamiento no está cubierto
- AND el bot SHALL ofrecer la opción particular o reintegro

### Requirement: ELIMINAR PATRÓN "trabajamos con OSDE para tratamientos quirúrgicos"

El anti-ejemplo de la línea 10029 SHALL ser reemplazado por un ejemplo correcto que no contenga la frase "trabajamos con OSDE para consultas y tratamientos quirúrgicos", para evitar que el LLM lo aprenda como patrón de respuesta.

#### Scenario: Bot no repite la frase genérica

- GIVEN el prompt sin el anti-ejemplo problemático
- WHEN un paciente pregunta por cobertura de implantes con OSDE
- THEN el bot MUST NO decir "trabajamos con OSDE para consultas y tratamientos quirúrgicos"
- AND el bot SHALL responder diferenciando consulta vs tratamiento

### Requirement: CAMINO 1 AJUSTADO

El flujo CAMINO 1 (OS aceptada) SHALL incluir la verificación de cobertura por tratamiento antes de confirmar genéricamente.

#### Scenario: CAMINO 1 verifica tratamiento específico

- GIVEN el flujo de modalidad de atención CAMINO 1
- WHEN el paciente menciona OSDE y un tratamiento específico
- THEN el bot SHALL verificar en el bloque OBRAS SOCIALES si ese tratamiento está cubierto
- AND el bot SHALL NO confirmar cobertura total si el tratamiento no está cubierto

---

## MODIFIED Requirements

### Requirement: Respuesta para status="accepted" (línea 10015)

La respuesta para `status="accepted"` SHALL ser modificada de un "Sí" genérico a una respuesta que cruce el status con el bloque OBRAS SOCIALES del prompt.

(Previously: `Si status="accepted": "Sí, trabajamos con [provider_name] 😊" + si has_copay: "Según tu plan puede haber coseguro, se abona el día de la consulta."`)

#### Scenario: Respuesta nueva para accepted con tratamiento no cubierto

- GIVEN el prompt con la nueva regla de respuesta diferenciada
- WHEN `check_insurance_coverage` devuelve `status: "accepted"`
- AND el paciente preguntó por un tratamiento que está en "NO cubiertos"
- THEN el bot SHALL responder con matiz: consulta cubierta, tratamiento a definir

---

## REMOVED Requirements

Ninguno.
