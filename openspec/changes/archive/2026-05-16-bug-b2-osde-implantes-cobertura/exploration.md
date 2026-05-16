# Exploration: Bug B2 — OSDE + implantes genera expectativa falsa de cobertura

**Change**: `bug-b2-osde-implantes-cobertura`
**Date**: 2026-05-16
**Source**: Pruebas Bot Paula 14-15 Mayo 2026 (Prueba 2 y Prueba 7)

---

## 1. Síntoma

**Prueba 2** — Paciente después de mencionar implantes fallidos:
```
Paciente: "Tengo OSDE. ¿me cubre?"
Paula:    "Sí, trabajamos con OSDE 😊 La consulta se realiza por tu cobertura..."
Paciente: "¿me cubre el implante???"
Paula:    "Sí, con OSDE trabajamos para consultas y tratamientos quirúrgicos 😊"  ← ERROR
```

**Prueba 7** — Paciente con OSDE:
```
Paciente: "quiero hacerme un implante. ¿me cubre OSDE?"
Paula:    "Sí, trabajamos con OSDE para consultas y tratamientos quirúrgicos 😊"  ← ERROR
Paciente: "me cubre implantes con OSDE?"
Paula:    "Trabajamos con OSDE para consultas y tratamientos quirúrgicos." ← ERROR (repite)
```

**Problema central**: El paciente escucha "SÍ" cuando la realidad es que **OSDE NO CUBRE implantes automáticamente**. La Dra. Delgado es prestadora de cirugía maxilofacial, no de odontología general. Implantes, rehabilitación, prótesis se manejan como particular o con documentación para reintegro.

---

## 2. Análisis de datos disponibles en DB

### 2.1 Estructura de `tenant_insurance_providers`

La tabla tiene `coverage_by_treatment` (JSONB) que permite definir por tratamiento qué cubre y qué no:

```json
{
  "CONSULTA": {
    "covered": true,
    "copay_percent": 0,
    "requires_pre_authorization": false,
    "pre_auth_leadtime_days": 0,
    "waiting_period_days": 0,
    "max_annual_coverage": null,
    "notes": ""
  },
  "IMPLANTE": {
    "covered": false,
    "copay_percent": 0,
    "requires_pre_authorization": false,
    "pre_auth_leadtime_days": 0,
    "waiting_period_days": 0,
    "max_annual_coverage": null,
    "notes": "Particular o reintegro segun el caso"
  }
}
```

### 2.2 Cruce con profesionales

Laura Delgado está cargada en `professionals` con su especialidad. Los tratamientos tienen profesionales asignados via `treatment_type_professionals`. Esto significa que el bot puede (y debe) saber:

- ¿Qué tratamiento pide el paciente?
- ¿Qué profesional lo realiza?
- ¿Ese profesional recibe esa obra social?
- ¿El tratamiento específico está cubierto por esa OS?

### 2.3 Datos actuales (confirmados por el usuario)

Los datos en DB están correctos: OSDE tiene `coverage_by_treatment` poblado, ISSN está cargado, los profesionales tienen sus asignaciones.

---

## 3. Análisis de código — 3 causas raíz

### 🔴 CAUSA 1: Línea 10015 — Respuesta genérica "Sí" para cualquier OS aceptada

```python
Si status="accepted": "Sí, trabajamos con [provider_name] 😊" + si has_copay:
"Según tu plan puede haber coseguro, se abona el día de la consulta."
```

La tool `check_insurance_coverage()` (línea 7522-7523) para `status="accepted"` devuelve:

```python
return json.dumps({
    "status": "accepted",
    "provider_name": name,
    "has_copay": bool(row.get("requires_copay")),
    "next_action": "offer_slots"
})
```

**NO revisa `coverage_by_treatment`** para ver si el tratamiento específico está cubierto. Solo devuelve un "accepted" genérico. El LLM lee eso y dice "Sí" aunque el tratamiento que preguntó el paciente no esté cubierto.

### 🔴 CAUSA 2: Línea 10025 — Prohibición contradictoria

```
PROHIBIDO confirmar qué cubre o no cubre cada obra social. PROHIBIDO listar tratamientos incluidos/excluidos.
```

Esta regla LE IMPIDE al bot usar los datos de `coverage_by_treatment` que `_format_insurance_providers()` (línea 8268) genera en el prompt. El prompt tiene un bloque como:

```
OSDE:
  Cubiertos:
    • Consulta (CONS): cubierto, sin coseguro
  NO cubiertos:
    • Implante (IMPT)
```

Pero el LLM no puede usar esa información porque la prohibición se lo impide.

### 🔴 CAUSA 3: Línea 10029 — Anti-ejemplo que el LLM aprende como patrón

```
NO repetir "Sí, trabajamos con OSDE para consultas y tratamientos quirúrgicos."
```

Aunque la línea DICE "NO repetir", el LLM ve esa frase y la aprende como un patrón de respuesta válido. En la Prueba 7, el bot repite EXACTAMENTE esa frase.

### 🔴 CAUSA 4 (secundaria): `check_insurance_coverage` no recibe el tratamiento

La tool `check_insurance_coverage(insurance_provider: str)` solo recibe el nombre de la OS. No recibe el nombre del tratamiento. No puede devolver "aceptado para consulta pero no para implante".

Sin embargo, el bloque de `_format_insurance_providers` YA lista cubiertos/no cubiertos en el prompt. El LLM tiene esa data. El problema no es la tool, es que las reglas le prohíben usarla.

---

## 4. Flujo actual del error

```
Paciente: "quiero hacerme un implante, me cubre OSDE?"
                    │
                    ▼
    1. check_insurance_coverage("OSDE")
       → DB: OSDE status="accepted"
       → Tool devuelve {"status": "accepted", ...}
                    │
                    ▼
    2. LLM lee línea 10015:
       "Si status='accepted' → 'Sí, trabajamos con [provider]'"
                    │
                    ▼
    3. LLM lee línea 10025:
       "PROHIBIDO confirmar qué cubre o no cubre"
                    │
                    ▼
    4. También ve línea 10029:
       NO repetir "Sí, trabajamos con OSDE para..."
       → Pero aprende el patrón
                    │
                    ▼
    5. RESPUESTA: "Sí, trabajamos con OSDE 😊"
       (El paciente piensa que implantes están cubiertos)
```

---

## 5. Respuesta modelo definida por Laura (de Prueba 7, documento de pruebas)

```
"Sí, la Dra. Delgado atiende consultas por OSDE 😊
En implantes, lo ideal es realizar primero una evaluación para ver qué
opción es la más adecuada para vos.
Luego, según el diagnóstico y el tipo de tratamiento, se define si
corresponde por cobertura, si es particular o si se puede entregar
documentación para reintegro.
¿Querés que te ayude a coordinar un turno?"
```

Características:
- Distingue: "la consulta puede ser por OSDE" (SÍ) vs "el implante" (se define después)
- No genera expectativa falsa
- Lleva a evaluación (donde se define realmente)

---

## 6. Reglas existentes que ya están bien (NO TOCAR)

| Regla | Línea | Estado |
|-------|-------|--------|
| `_format_insurance_providers` genera bloque con cubiertos/no cubiertos | 8268-8435 | ✅ Correcto, usa `coverage_by_treatment` |
| F4: Obra social no reconocida → particular con reintegro | 9541-9547 | ✅ Correcto |
| Modalidad atención 3 caminos | 10003-10008 | ✅ Estructura bien, contenido hay que ajustar |
| Diferenciación Dra. vs Equipo | 9727-9729 | ✅ Correcto |

---

## 7. Archivos afectados

| Archivo | Cambio |
|---------|--------|
| `orchestrator_service/main.py` | Modificaciones de texto en `build_system_prompt()` — solo cambios en string del prompt |

**Riesgo**: Bajo. Cambios de texto. Rollback: revertir líneas.
