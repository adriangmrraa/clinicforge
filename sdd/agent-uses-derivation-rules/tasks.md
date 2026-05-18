# Tasks: CASO 2 — Agent uses derivation rules for professional assignment

## Phase 1: Modificar get_service_details

- [ ] 1.1 En `get_service_details()` (~L5392-5395): cuando existe `ai_response_template`, NO appender la línea `"Profesionales:"` con nombres individuales

## Phase 2: Modificar PASO 3 en system prompt

- [ ] 2.1 En PASO 3 (~L9812-9815): reemplazar instrucción actual por nueva estructura con 3 niveles:
  - Primero: consultar DERIVACIÓN DE PACIENTES
  - Si regla dice "equipo" → "nuestro equipo odontológico" sin nombres
  - Si regla dice profesional específico → nombrar solo ese profesional
  - Fallback: si no hay regla → usar list_services/get_service_details

## Phase 3: Verificación

- [ ] 3.1 Verificar que `get_service_details` con `ai_response_template` ya no appendea profesionales
- [ ] 3.2 Verificar que PASO 3 nuevo contiene: (a) referencia a derivation_section, (b) instrucción "equipo" sin nombres, (c) instrucción profesional específico, (d) fallback
