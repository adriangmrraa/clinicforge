# Design: B4/B5/B9 — Derivaciones sin hardcode

## Technical Approach

5 cambios de texto en `build_system_prompt()` de `main.py`. Sin cambios en DB, tools, frontend ni lógica. Las reglas de derivación en DB ya están correctas. El PASO 3 del booking flow ya funciona. Solo se corrigen los flujos emocionales que bypassaban el sistema de derivación.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `orchestrator_service/main.py` | Modify | 5 cambios de texto en el prompt |

### Cambio 1 — F1: CTA genérico (línea 9538)

**Antes:**
```
  M3 — CTA: "Te ayudo a coordinar una evaluación con {prof_display_full}."
```

**Después:**
```
  M3 — CTA: "Te ayudo a coordinar una evaluación. El equipo te va a indicar el profesional más adecuado para tu caso."
```

### Cambio 2 — F8b: CTA genérico (línea 9607)

**Antes:**
```
  M3 — CTA: "Te ayudo a coordinar una evaluación con {prof_display_full}."
```

**Después:**
```
  M3 — CTA: "Te ayudo a coordinar una evaluación. El equipo te va a indicar el profesional más adecuado para tu caso."
```

### Cambio 3 — F2: Prohibir listar profesionales + escalar (después de línea 9548)

**Después de línea 9548 (M2), antes de M3:**
```
PROHIBIDO en F2:
  • NO listar profesionales por nombre. NO decir "la consulta de urgencia la puede hacer X, Y o Z".
  • NO decir "Sí, hacemos [tratamiento]" ni confirmar el tratamiento sin escalar.
  • Si el paciente menciona endodoncia, conducto, caries, arreglo, limpieza o
    cualquier odontología general junto con el dolor → NO agendar directo.
    ESCALAR al equipo: "Entiendo, si estás con dolor lo ideal es que el equipo
    evalúe tu caso y te asigne el profesional más adecuado. Te paso con ellos
    para que te contacten." Y llamá derivhumano con motivo "Urgencia odontología
    general — escalar al equipo".
```

### Cambio 4 — Nueva prohibición 15 (después de línea 9514)

```
15. PROHIBIDO decir "Sí, hacemos [tratamiento]", "Eso entra en [tratamiento]" o
    confirmar que se realiza un tratamiento sin haberlo verificado con list_services
    Y sin seguir el flujo de derivación correspondiente. Si el paciente menciona un
    tratamiento, usá list_services para confirmar si existe y luego aplicá la regla
    de derivación que corresponda según el bloque DERIVACIÓN DE PACIENTES.
```

### Cambio 5 — Sin cambios (verificación)

F3, F5, F6, F7, F8, F9 ya son genéricos. ✅ Verificado.

## Data Flow (corregido)

### B4 — Endodoncia
```
Paciente: "me dijeron que tengo que hacerme un tratamiento de conducto"
                    │
                    ▼
    1. Prohibición 15: NO decir "Sí, hacemos endodoncia"
    2. list_services("conducto") → confirma que existe
    3. Regla de derivación: "Tratamientos generales → Equipo"
    4. RESPUESTA: "Entiendo. Te paso con el equipo para que
       evalúen tu caso y te asignen el profesional más adecuado."
```

### B5 — Urgencia
```
Paciente: "hola estoy con dolor... mucho dolor"
                    │
                    ▼
    1. F2 M1 contener
    2. F2 M2 orientar
    3. Prohibición F2: NO listar profesionales
    4. triage_urgency + check_availability
    5. Si odontología general → escalar al equipo
```

### B9 — Ortodoncia
```
Paciente: "quiero información sobre ortodoncia"
                    │
                    ▼
    1. list_services("ortodoncia") → devuelve: "con: Elizabeth"
    2. PASO 3: tratamiento con UN SOLO profesional
    3. "Este tratamiento lo realiza Elizabeth."
    4. NO menciona a la Dra. Delgado.
```

## Testing Strategy

| Escenario | Input | Expected |
|-----------|-------|----------|
| B4 | "necesito un conducto" | NO dice "Sí, hacemos endodoncia". Escala al equipo. |
| B5 | "estoy con dolor" | NO lista profesionales. Contiene + resuelve. |
| B5+endo | "me duele y necesito conducto" | Escala al equipo. |
| B9 | "ortodoncia" | Menciona al equipo/Eli, NO a la Dra. |
| F1 | "fui a otro y me fue mal" | CTA no menciona a la Dra. |
| F8b | "cada uno me dice algo distinto" | CTA no menciona a la Dra. |

## Migration / Rollout

No requiere migración. Rollback: revertir los 5 cambios.
