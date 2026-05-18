# Tasks: Professional assignment precedence and anti-cession

## Phase 1: Agregar regla en CONTEXTO DEL PACIENTE

- [ ] 1.1 En REGLAS DE USO DEL CONTEXTO DEL PACIENTE (~L9043): agregar regla para "PROFESIONAL ASIGNADO" que diga que es el profesional de cabecera con prioridad absoluta

## Phase 2: Reestructurar PASO 3

- [ ] 2.1 Reemplazar PASO 3 actual (~L9812-9826) por nuevo orden de precedencia: 1. assigned_professional_id → 2. treatment_type_professionals → 3. derivation_rules → 4. fallback
- [ ] 2.2 Agregar REGLA ANTI-CESIÓN al final de PASO 3: si paciente insiste con profesional no designado, mantenerse firme

## Phase 3: Verificación

- [ ] 3.1 Verificar que PASO 3 nuevo contiene assigned_professional_id como paso 1
- [ ] 3.2 Verificar que existe la REGLA ANTI-CESIÓN en el prompt
- [ ] 3.3 Verificar que la regla de CONTEXTO DEL PACIENTE menciona "PROFESIONAL ASIGNADO"
