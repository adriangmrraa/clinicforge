# Tasks: CASO 1 — Booking after coverage query

## Phase 1: Cambios en system prompt

- [ ] 1.1 En `_format_insurance_providers()` (~L8400): cambiar `"Derivación externa:"` → `"Cobertura con centro externo:"`
- [ ] 1.2 En `_format_insurance_providers()` (~L8408): cambiar `"→ Derivar a {target}"` → `"→ Centro externo: {target}"`
- [ ] 1.3 En sección respuestas `check_insurance_coverage` (~L10026): agregar instrucción post-respuesta para external_derivation

## Phase 2: Verificación

- [ ] 2.1 Verificar que en `_format_insurance_providers()` no queda ninguna ocurrencia de "Derivar" para external_derivation
- [ ] 2.2 Verificar que la instrucción post-respuesta para external_derivation diga "Si paciente ya eligió día → continuar booking. No derivar a humano."
