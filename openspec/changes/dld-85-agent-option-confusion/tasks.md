# Tasks: DLD-85 — Agent Option Confusion

## Fase 1: Código — Función `_match_option_number()`

- [x] 1.1 Insertar `_match_option_number(patient_text, offered_slots)` en `orchestrator_service/main.py` antes de `book_appointment` (~línea 2950) con toda la jerarquía: R1 día semana, R2 día+número, R3 ordinal, R4 hora
- [x] 1.2 Reemplazar el bloque de fallback inline (líneas 3196-3266) en `book_appointment` con llamado a `_match_option_number()` + logging estructurado

## Fase 2: Prompt — Agregar casos a las 3 secciones existentes (sin pisar nada)

- [x] 2.1 En `=== REGLA DE RESOLUCIÓN DE SLOT ===` (línea 9923): agregar bloque ADEMÁS para día+número y ordinal/hora
- [x] 2.2 En `REGLA INQUEBRANTABLE DE SELECCIÓN` (línea 10073): agregar ADEMÁS para día de semana y día+número
- [x] 2.3 En `REGLA DE SELECCIÓN DE TURNO` (línea 10097): agregar 3 guiones para día semana, día+número, y match por hora

## Fase 3: Verificación

- [x] 3.1 Probar casos del design con _match_option_number() — día inequívoco, día+número, ordinal, hora, número solo
- [x] 3.2 Verificar sin regresión: "1", "2", "dale", "sí", "agendame ahí" siguen funcionando
- [x] 3.3 Verificar que las 3 secciones del prompt conservan su texto original y solo tienen texto NUEVO agregado
