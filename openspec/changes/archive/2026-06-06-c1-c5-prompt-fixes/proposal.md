# SDD Proposal: Corrección de 5 hallazgos críticos en system prompt (C1-C5)

**Change**: `c1-c5-prompt-fixes`
**Status**: PROPOSED
**Date**: 2026-06-06

---

## 1. Intent

5 hallazgos críticos detectados por exploración en el system prompt del agente IA de WhatsApp (`build_system_prompt()` en main.py, y nova_prompt.py). Incluye regla temporal expirada 22 días atrás, instrucciones faltantes post-booking, gap en manejo de quejas sobre la clínica, y tools que el agente no sabe usar.

## 2. Scope

### In Scope
- **C1**: Eliminar bloque `⚠️ REGLA TEMPORAL DE OPERACIÓN (VIGENTE HASTA 2026-05-15)` vencido. Convertir en regla permanente de preguntar particular/obra social.
- **C2**: Agregar instrucción POST-BOOKING EMAIL — ofrecer email post-confirmación y usar `save_patient_email`.
- **C3**: Agregar excepción a REGLA DE NO-ELECCIÓN: dudas sobre el profesional (no horario) no activan No-Elección.
- **C4**: Expandir F1 en F1a (existente, mala experiencia en otro lugar) + F1b (nuevo, queja sobre esta clínica). F1b deriva a PROTOCOLO DE SOPORTE Y QUEJAS.
- **C5**: Documentar tools existentes no referenciadas (`confirm_appointment`, `link_payment_to_patient`). Corregir `list_patient_documents` (crear tool real o marcar como admin route).

### Out of Scope
- NO cambiar lógica de backend, tools, tests ni frontend.
- NO crear nuevas tools (salvo `list_patient_documents` si se decide).
- NO eliminar ejemplos date_query con "15 de mayo".
- NO agregar tools inexistentes (`delete_session_data`, `end_conversation`).

## 3. Capabilities

### New Capabilities
None — cambios sobre texto del prompt solamente. No hay cambios de comportamiento a nivel spec.

### Modified Capabilities
None — ningún requirement existente cambia. Solo se aclaran instrucciones al LLM.

## 4. Approach

| # | Acción | Archivos |
|---|--------|----------|
| C1 | Eliminar bloque temp. PASO 2c: "SIEMPRE preguntar particular/obra social" como regla fija. | `main.py:10489-10497` (bloque), `:10574` (ref), `nova_prompt.py:121-125` (bloque), `:129` (ref) |
| C2 | Nueva sección post-PASO 6: ofrecer email tras confirmación + `save_patient_email`. | `main.py` (~l.10850, post PASO 6) |
| C3 | Excepción en REGLA NO-ELECCIÓN (l.10547): duda sobre profesional → validar + proceder. Referencia cruzada en PRIORITY GATE (l.10699). | `main.py:10547-10556` y `:10699-10747` |
| C4 | F1→F1a (existente). F1b nuevo: trigger queja sobre clínica, M1 empático, derivar a PROTOCOLO DE SOPORTE Y QUEJAS + derivhumano si persiste. Actualizar REGLA PRIORIDAD l.10178. | `main.py:10270-10278`, `:10178-10195` |
| C5 | Agregar secciones en prompt tools para `confirm_appointment` y `link_payment_to_patient`. Decidir sobre `list_patient_documents`. | `main.py` (sección documentación de tools en prompt) |

## 5. Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| C1: Agente deje de preguntar particular/obra social al eliminar regla | Med | Convertir en regla permanente con mismo texto, sin fecha |
| C4-F1b: Exceso de derivaciones a humano | Med | Protocolo graduado: empatizar → ofrecer revisión → derivhumano solo si persiste |
| C5: Documentar tool que no existe en todas las versiones del agente | Bajo | Verificar existencia en código antes de documentar |

## 6. Rollback

Todos los cambios son sobre texto del prompt. `git diff` identifica cada línea modificada. Rollback individual por hallazgo: C1 revertir eliminación del bloque temporal + restaurar referencia en PASO 2c. C2-C4 revertir ediciones de texto. C5 revertir adiciones de secciones.

## 7. Success Criteria

- [ ] C1: Sin referencias a "VIGENTE HASTA 2026-05-15" en main.py ni nova_prompt.py. PASO 2c tiene instrucción permanente.
- [ ] C2: Sección POST-BOOKING EMAIL presente tras PASO 6, instruye ofrecer email + usar `save_patient_email`.
- [ ] C3: REGLA DE NO-ELECCIÓN exceptúa dudas sobre profesional. PRIORITY GATE referencia la excepción.
- [ ] C4: F1a (otro lugar) y F1b (esta clínica) existen como sub-flujos. F1b referencia PROTOCOLO DE SOPORTE Y QUEJAS.
- [ ] C5: `confirm_appointment` y `link_payment_to_patient` documentados. `list_patient_documents` resuelto.
