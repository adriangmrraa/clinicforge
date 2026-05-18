# Proposal: CASO 2 — Agent must use derivation rules to determine professional

## Intent

El agente ignora las reglas de derivación configuradas en la UI cuando el paciente pregunta "quién hace X tratamiento". En vez de consultar las reglas, usa `list_services`/`get_service_details` que devuelven todos los profesionales. Para endodoncia, la regla dice "equipo" pero el agente lista nombres individuales incluyendo a Laura Delgado que no hace endodoncia.

## Scope

### In Scope
1. Modificar **PASO 3** del system prompt para que consulte `derivation_section` ANTES que `list_services`/`get_service_details`
2. Si la regla de derivación dice "equipo" → responder "nuestro equipo médico" sin nombres individuales
3. Si la regla apunta a un profesional específico → nombrar SOLO ese profesional
4. Si no hay regla que coincida → usar `list_services`/`get_service_details` como fallback

### Out of Scope
- Modificar tool `list_professionals` (se puede hacer después si hace falta)
- Modificar tool `list_services`
- CASO 1 (cobertura ISSN) — se maneja por separado
- Cambiar datos de reglas de derivación en DB

## Approach

### Cambio 1 — Modificar PASO 3 en system prompt (~línea 9812-9815)
Reemplazar el PASO 3 actual con uno que priorice las reglas de derivación:

```
PASO 3: PROFESIONAL ASIGNADO — Consultar en este orden:

  PRIMERO — Verificar DERIVACIÓN DE PACIENTES (bloque arriba):
  • Buscá si el tratamiento o su categoría aparece en alguna regla de derivación.
  • Si la regla dice "sin filtro de profesional (equipo)":
    Respondé: "Ese tratamiento lo realiza nuestro equipo odontológico. ¿Te ayudo a coordinar un turno?"
    NO menciones nombres de profesionales individuales.
  • Si la regla dice "agendar con [Nombre] (ID: X)":
    Respondé: "Ese tratamiento lo realiza el/la Dr/a. [Nombre]."
    Mencioná SOLO ese profesional.
  
  SOLO SI ninguna regla coincide → usá lo que devuelve list_services/get_service_details:
  • Si tiene UN profesional asignado → "Este tratamiento lo realiza el/la Dr/a. X"
  • Si tiene VARIOS → "Este tratamiento lo realizan [nombres]. Preferís alguno/a?"
  • Si NO tiene → preguntá preferencia o asigná primero disponible.
```

### Cambio 2 — Modificar get_service_details (apendice de profesionales)
En `get_service_details`, cuando exista `ai_response_template`, NO appender la línea de "Profesionales:" después del template. Opcional: agregar la info en un formato que el agente use internamente pero no repita al paciente.

```
# Antes (~line 5392-5395):
if row.get("ai_response_template"):
    res = f"{row['ai_response_template']}\n"
    if assigned_profs:
        res += f"\nProfesionales: {', '.join(assigned_profs)}\n"

# Después:
if row.get("ai_response_template"):
    res = row["ai_response_template"]
    # NO appender profesionales — la derivación se maneja via derivation_section
```

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `main.py` ~9812-9815 | Modified | PASO 3: priorizar derivation_section |
| `main.py` ~5392-5395 | Modified | get_service_details: no appender profesionales con template |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Que ningún tratamiento tenga regla de derivación configurada → PASO 3 fallback a list_services funciona | Bajo | El fallback está contemplado |
| get_service_details sin profesionales puede confundir al agente | Medio | La info de profesionales sigue via derivation_section + list_services |

## Rollback Plan
Revertir cambios en `main.py`. Sin migraciones.

## Success Criteria
- [ ] Paciente pregunta "con quién me atiendo una endodoncia?" → agente responde "con nuestro equipo médico" sin nombrar individuos
- [ ] Paciente pregunta "quién hace implantes?" → agente responde "con la Dra. Laura Delgado" (por regla 1)
- [ ] Si no hay regla de derivación configurada → agente usa list_services como fallback
