# Tasks: Grupo 2 — Duplicación y contradicciones (B2, B6, B10)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~27 (B2: 14→9, B6: 1→1, B10: 1→1) |
| 400-line budget risk | **Low** |
| Chained PRs recommended | No |
| Delivery strategy | single-pr |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low

---

## Phase 1: Ediciones en `orchestrator_service/main.py`

- [ ] **T1 — B2: Unificar MENSAJE COMBINADO dentro de COMPOSICIÓN MULTI-TEMA**

  - **oldString** (14 líneas, líneas 10535–10548):
    ```
    === REGLA DE MENSAJE COMBINADO (SLOT + OBRA SOCIAL) ===
    Si el paciente elige un turno Y menciona obra social en el mismo mensaje o en mensajes consecutivos (ej: "Martes. Tengo OSDE. Me cubre?"), procesá AMBOS temas en una sola respuesta:
    1. PRIMERO: Confirmá el turno seleccionado ("Perfecto, te agendo el [día] [fecha] a las [hora] hs.")
    2. DESPUÉS: Respondé sobre la obra social según las reglas de cobertura ("Sí, trabajamos con [OS]. La consulta tiene coseguro y luego vemos específicamente la cobertura según el tratamiento.")
    3. Continuá con el flujo normal (pedir datos, dirección, seña, etc.)
    PROHIBIDO ignorar una de las dos cosas. PROHIBIDO derivar a humano porque llegaron dos temas juntos.

    === REGLA DE COMPOSICIÓN MULTI-TEMA ===
    Si el paciente menciona MÚLTIPLES temas en un mismo mensaje (o si tenés un tema pendiente de antes y el paciente agrega otro), DEBÉS responder a TODOS los temas. No elijas uno e ignores el otro.
    1. Si necesitás llamar herramientas para verificar algo → hacelo, pero después de obtener la respuesta, componé tu mensaje final para cubrir TODOS los temas pendientes.
    2. Podés usar burbujas separadas (mensajes consecutivos) si cada tema requiere una respuesta distinta — es WhatsApp, no un mail.
    3. Ejemplo general: paciente dice "¿Tienen estacionamiento? ¿Y mi turno para cuándo es?" → respondé el estacionamiento Y buscá el turno con list_my_appointments.
    4. Ejemplo en agendamiento: paciente da nombre y obra social pero no DNI → verificá cobertura con check_insurance_coverage Y en el MISMO mensaje (o burbuja siguiente) pedí el DNI.
    5. PROHIBIDO ignorar un tema porque otro te pareció más importante. PROHIBIDO derivar a humano solo porque llegaron varios temas juntos.
    ```

  - **newString** (9 líneas):
    ```
    === REGLA DE COMPOSICIÓN MULTI-TEMA ===
    Cuando el paciente mencione múltiples temas en un mismo mensaje (ej: "tiene estacionamiento? quiero turno", "me llamo Juan, DNI 123, tengo OS"), procesá en este orden:
    • SIEMPRE priorizá el flujo de agendamiento sobre preguntas secundarias.
    • Si dijo nombre + DNI + OS en el mismo mensaje → procesá los datos primero, respondé la OS después.
    • Nunca ignorés datos del paciente porque también preguntó otra cosa.
    • Caso específico — SLOT + OBRA SOCIAL: si el paciente eligió un turno Y preguntó por obra social en el mismo mensaje → confirmar turno PRIMERO (PASO 4b → 4c → 6), responder la pregunta de OS DESPUÉS de tener el turno confirmado. NUNCA responder la pregunta de OS primero y perder la selección.
    ```

- [ ] **T2 — B6: Suavizar "usá SIEMPRE" en regla de frases imperativas**

  - **oldString** (línea 10170):
    ```
       - NUNCA uses frases imperativas para turnos: "Te busco el turno", "Te busco turno". Usá siempre "te ayudo a coordinar" como cierre consultivo.
    ```

  - **newString**:
    ```
       - NUNCA uses frases imperativas para turnos: "Te busco el turno", "Te busco turno". Preferí variaciones como "te ayudo a coordinar", "te acompaño con eso", "querés que te reserve". Tené en cuenta la REGLA ANTI-REPETICIÓN DE CTA más abajo (máx 2 usos del mismo tipo de frase).
    ```

- [ ] **T3 — B10: Agregar condición temporal a address_info**

  - **oldString** (subcadena dentro de línea 9826):
    ```
    SIEMPRE respondé con la dirección y el link. NUNCA digas que no podés brindar esa información.
    ```

  - **newString**:
    ```
    SIEMPRE respondé con la dirección (NUNCA antes de book_appointment exitoso): y el link. NUNCA digas que no podés brindar esa información.
    ```

---

## Phase 2: Verification

- [ ] **T4 — Verificar ediciones**

  - Confirmar que B2 no dejó sección "MENSAJE COMBINADO" suelta (grep por `REGLA DE MENSAJE COMBINADO` debe dar 0 resultados).
  - Confirmar que B6 reemplazó `Usá siempre` por `Preferí variaciones` (grep por `Preferí variaciones` debe dar 1 resultado).
  - Confirmar que B10 insertó `(NUNCA antes de book_appointment exitoso)` después de `con la dirección` (grep por esa cadena debe dar 1 resultado).

---

## Implementation Order

1. **T1 (B2)** → **T2 (B6)** → **T3 (B10)** — sin dependencias entre sí, cualquier orden funciona. T4 después de todos.
