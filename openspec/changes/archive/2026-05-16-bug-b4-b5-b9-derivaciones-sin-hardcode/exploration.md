# Exploration: B4/B5/B9 — Derivaciones sin hardcode

**Change**: `bug-b4-b5-b9-derivaciones-sin-hardcode`
**Date**: 2026-05-16
**Source**: Pruebas Bot Paula 14-15 Mayo 2026

---

## 1. Síntomas

### B4 — Endodoncia agenda directo con Dra. Delgado
Paciente dice "me dijeron que tengo que hacerme un tratamiento de conducto" → bot responde "Sí, eso entra en Endodoncia. Te ayudo a coordinar un turno con la Dra. Laura Delgado." **Debería escalar al equipo.**

### B5 — Urgencias agenda directo
Paciente dice "hola estoy con dolor... mucho dolor" → bot responde "La consulta de urgencia la puede hacer la Dra. X, Y o Z. Te ayudo a coordinar un turno." **Debería contener + escalar al equipo.**

### B9 — Ortodoncia nombra a Dra. Delgado
Paciente pregunta por ortodoncia → bot menciona a la Dra. Delgado cuando ortodoncia la realiza SOLO Elizabeth Ester (equipo). **Debería ir al equipo.**

---

## 2. Causa raíz: CTAs hardcodeados con `{prof_display_full}`

### 2.1 Profesional hardcodeado en el prompt

La variable `prof_display_full` se define al inicio de `build_system_prompt()` (línea 9012):

```python
prof_display_full = (
    f"el/la Dr/a. {professional_name}" if professional_name else "nuestro equipo"
)
```

Para el tenant de Laura, `professional_name` es "Laura Delgado", entonces `prof_display_full` SIEMPRE es "la Dra. Laura Delgado".

### 2.2 Flujos emocionales que usan `{prof_display_full}` en su CTA

| Flujo | Línea | CTA actual | Impacto |
|-------|-------|-----------|---------|
| **F1** (Mala experiencia) | 9538 | `"Te ayudo a coordinar una evaluación con {prof_display_full}."` | Siempre dice "con la Dra. Laura Delgado" aunque sea un caso de equipo |
| **F8b** (Opiniones diferentes) | 9607 | `"Te ayudo a coordinar una evaluación con {prof_display_full}."` | Igual |

### 2.3 Flujo F2 (Urgencia/Dolor) no deriva al equipo

F2 (línea 9543-9551) actualmente hace:
```
M1 — Contener
M2 — Orientar (una pregunta)
M3 — Resolver: triage_urgency + check_availability + mostrar 2 opciones
```

No hay ningún paso que diga "si es endodoncia/caries/arreglo/odontología general → escalar al equipo ANTES de agendar". El bot agenda directo.

### 2.4 Las reglas de derivación YA existen y funcionan

En DB están cargadas vía UI:

| Regla | Condición | Acción |
|-------|-----------|--------|
| Cirugía e implantes → Dra. Delgado | Cualquier paciente | Dra. Delgado |
| Tratamientos generales → Equipo | Paciente nuevo | Equipo |
| Paciente existente → Dra. Delgado | Paciente existente | Dra. Delgado |

Y el prompt ya las recibe via `_format_derivation_rules()` (línea 8455). El bloque generado es:

```
DERIVACIÓN DE PACIENTES — REGLAS (evaluar EN ORDEN, primera que coincida gana):
REGLA 1 — Cirugía e implantes → Dra. Delgado: ...
REGLA 2 — Tratamientos generales → Equipo: ...
REGLA 3 — Paciente existente → Dra. Delgado: ...
Si ninguna regla coincide → sin filtro de profesional (equipo disponible).
```

Y el PASO 3 del flujo de agendamiento (línea 9807) YA respeta las derivaciones:

```
PASO 3: PROFESIONAL ASIGNADO — Según lo que devolvió 'list_services':
  • Si el tratamiento tiene UN SOLO profesional → informá al paciente
  • Si tiene VARIOS → preguntá preferencia
  • Si NO tiene → asigná el primero
```

**El problema:** Los flujos emocionales (F1, F8b) bypassan el PASO 3 porque tienen su propio CTA hardcodeado con `{prof_display_full}`. Y F2 bypassa la escalación al equipo.

### 2.5 Hallazgos adicionales (verificación post-explore)

Al hacer la verificación adversarial del código, se encontraron **3 problemas adicionales** no identificados inicialmente:

#### 🔴 Hallazgo #1: F2 lista profesionales por nombre

En la Prueba 4, el bot responde textualmente:
```
"La consulta de urgencia la puede hacer la Dra. Laura Delgado, la Dra. Elizabeth Ester o la Dra. Eli Perez."
```

F2 (línea 9543) NO tiene ninguna instrucción que diga que liste profesionales. El LLM lo hace por iniciativa propia al ver los datos de `list_professionals`. **Hay que agregar una prohibición explícita** en F2: NO listar profesionales por nombre.

#### 🔴 Hallazgo #2: No hay regla que prohíba "Sí, hacemos [tratamiento]"

En la Prueba 4, el bot responde:
```
"Sí, eso entra en Endodoncia 😊"
```

El bot CONFIRMA el tratamiento sin escalar al equipo. No existe una regla que diga: "PROHIBIDO decir 'Sí, hacemos [tratamiento]' o 'Eso entra en [tratamiento]' como respuesta cerrada sin verificar derivación."

#### 🔴 Hallazgo #3: `{prof_display_full}` usado en 10 lugares — 8 son correctos, 2 hay que cambiar

Se verificaron TODOS los usos de `{prof_display_full}` en el prompt:

| Línea | Uso | ¿Correcto? |
|-------|-----|-----------|
| 9197 | Bio del profesional (specialty_pitch) | ✅ Siempre la Dra. |
| 9385 | "es quien define la indicación" | ✅ Siempre la Dra. |
| 9493 | "evaluará tu caso" (Prohibición 1) | ✅ Siempre la Dra. |
| **9538** | **F1 CTA** | **❌ Debe ser genérico** |
| **9607** | **F8b CTA** | **❌ Debe ser genérico** |
| 9728 | "Siempre posicionar a {prof_display_full}" | ✅ Es sobre SERVICIOS DE LA DRA. |
| 9996 | Precio altos/implantes | ✅ Son de la Dra. |
| 10040 | Leads alto valor | ✅ Son de la Dra. |

**Conclusión:** Solo F1 y F8b necesitan cambio. Los otros 6 usos están correctos porque se refieren a contextos donde SÍ debe ser la Dra. Delgado.

---

## 3. Análisis del flujo completo de cada bug

### B4 (Endodoncia)
```
Paciente: "hola estoy con dolor... mucho dolor"
→ F2 se activa
→ Bot responde: "La consulta de urgencia la puede hacer la Dra. X, Y o Z"
   ↑ PROBLEMA: F2 no prohíbe listar profesionales. El LLM lo hace.

Paciente: "me dijeron q tengo q hacerme un tratamiento de conducto"
→ Bot: "Sí, eso entra en Endodoncia 😊"
   ↑ PROBLEMA: No hay regla que prohíba confirmar tratamientos sin escalar.
→ Bot: "Te ayudo a coordinar un turno con la Dra. Laura Delgado"
   ↑ PROBLEMA: F2 no escala al equipo. Booking flow usa default prof_display_full.
```

### B5 (Urgencias)
```
Paciente: "hola estoy con dolor... mucho dolor"
→ F2 se activa
→ Bot lista profesionales (mismo problema que B4)
→ No escala al equipo, ofrece turno directo
```

### B9 (Ortodoncia)
```
Paciente: consulta por ortodoncia
→ Regla de derivación 2 dice: Tratamientos generales → Equipo
→ Pero bot menciona a la Dra. porque no hay regla explícita que diga
  "ortodoncia → equipo, NO nombrar a la Dra."
```

---

## 4. Asignaciones reales por tratamiento (desde DB)

| Tratamiento | Profesionales asignados | Debería derivar a |
|------------|------------------------|-------------------|
| `endodoncia` | Laura + Elizabeth | **Equipo** (puede cualquiera) |
| `consulta_urgencia` | Laura + Elizabeth + Eli | **Equipo** (puede cualquiera) |
| `consulta_ortodoncia` | **Solo Elizabeth** | **Equipo** |
| `limpieza_dental` | Eli + Elizabeth + Laura | **Equipo** |
| `implante_*` | **Solo Laura** | **Dra. Delgado** |
| `cirugia_*` | **Solo Laura** | **Dra. Delgado** |
| `estetica_facial_*` | **Solo Laura** | **Dra. Delgado** |

---

## 4. Cambios necesarios

| # | Cambio | Dónde | Tipo |
|---|--------|-------|------|
| 1 | F1: reemplazar `{prof_display_full}` por "el equipo" o mención genérica | `main.py` ~9538 | Texto prompt |
| 2 | F8b: reemplazar `{prof_display_full}` por "el equipo" o mención genérica | `main.py` ~9607 | Texto prompt |
| 3 | F2: agregar paso de escalación: si es endodoncia/caries/arreglo/odontología general → escalar al equipo ANTES de agendar | `main.py` ~9549 | Texto prompt |
| 4 | F5, F6, F7, F8, F9, F3: verificar que ningún otro CTA mencione profesional específico | `main.py` 9553-9619 | Verificación |

**Riesgo:** Bajo. Solo cambios de texto. Las reglas de derivación reales ya funcionan via tools + PASO 3.
