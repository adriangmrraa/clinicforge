# Exploration: CASO 2 — Agent ignores derivation rules when asked "who does X?"

## Current State

### El problema
Cuando un paciente pregunta "Con qué profesional me atiendo una endodoncia?" el agente responde incorrectamente listando TODOS los profesionales:
> "La endodoncia la realizan la Dra. Laura Delgado, la Dra. Elizabeth Ester y Eli Perez."

Esto está mal porque:
1. **Endodoncia → NO la hace Laura Delgado** (ella es cirujana maxilofacial)
2. **Las reglas de derivación** (configuradas en UI) dicen: endodoncia → equipo (no nombres individuales)
3. **Para reglas tipo "equipo"** no se deben nombrar los profesionales

### Causa raíz: El prompt tiene 3 problemas

#### Problema 1 — PASO 3 no referencia las reglas de derivación (~línea 9812-9815)
```
PASO 3: PROFESIONAL ASIGNADO — Según lo que devolvió 'list_services' o 'get_service_details':
  • Si tiene UN SOLO profesional asignado → informá al paciente
  • Si tiene VARIOS profesionales asignados → decí: "Este tratamiento lo realizan [nombres]"
  • Si NO tiene profesionales asignados → preguntá preferencia
```
**No hay NINGUNA mención a `derivation_section`**. El agente sigue esta instrucción al pie de la letra y usa `list_services`/`get_service_details`, ignorando completamente las reglas de derivación que están en otra sección del prompt.

#### Problema 2 — `get_service_details` appendea profesionales incluso con template (~línea 5392-5395)
```python
if row.get("ai_response_template"):
    res = f"{row['ai_response_template']}\n"
    if assigned_profs:
        res += f"\nProfesionales: {', '.join(assigned_profs)}\n"  # <-- ESTO CONTAMINA
```
El template de endodoncia dice "lo realiza el equipo odontológico", pero la tool APPENDEA los nombres después. El agente recibe información contradictoria.

#### Problema 3 — `list_professionals` no acepta filtro de tratamiento (~línea 5122)
La tool no tiene parámetro de tratamiento. Cuando preguntan "quién hace X?", el agente llama `list_professionals()` y obtiene TODOS los profesionales sin filtrar.

### Lo que YA funciona
- `check_availability` usa correctamente las reglas de derivación para filtrar profesional al agendar (~línea 1744-1794)
- Las reglas de derivación se inyectan correctamente en el prompt (~línea 9717)
- `list_services` tiene filtro de categoría y `patient_term`

## Affected Areas
- `orchestrator_service/main.py` ~9812-9815 — PASO 3 del system prompt
- `orchestrator_service/main.py` ~5392-5395 — `get_service_details` appendea profesionales
- `orchestrator_service/main.py` ~5122 — `list_professionals` sin filtro

## Approaches

### Approach A (RECOMENDADA): Modificar PASO 3 + get_service_details
**Qué**: Agregar en PASO 3 instrucción de consultar derivación PRIMERO. Y en `get_service_details`, no appender profesionales cuando existe `ai_response_template`.
- **Pros**: Ataca la raíz del problema, mínimo riesgo
- **Cons**: No resuelve el filtro en list_professionals
- **Effort**: Bajo

### Approach B: Modificar PASO 3 + agregar filtro a list_professionals
**Qué**: Además de PASO 3, agregar parámetro `treatment_name` a `list_professionals` para filtrar.
- **Pros**: Más preciso, list_professionals más útil
- **Cons**: Más cambios, mayor complejidad
- **Effort**: Medio

### Approach C: Reemplazar PASO 3 por consulta directa a derivation_section
**Qué**: Eliminar la referencia a list_services/get_service_details en PASO 3 y que use SOLO derivation_section.
- **Pros**: Elimina ambigüedad
- **Cons**: Podría perder flexibilidad si no hay regla de derivación configurada
- **Effort**: Medio

## Recommendation
**Approach A** — Menor riesgo, ataca la causa raíz. PASO 3 debe decir: "Primero consultá DERIVACIÓN DE PACIENTES. Si la regla dice equipo → decí 'equipo médico'. Si dice profesional específico → nombrá solo ese profesional. Si no hay regla → usá list_services/get_service_details."

## Ready for Proposal
Sí.
