# Tasks: Bug B2 — OSDE + implantes genera expectativa falsa de cobertura

## Phase 1: Aplicar cambios de prompt (4 ediciones en main.py)

- [ ] 1.1 Modificar CAMINO 1 (línea 10005): agregar verificación de tratamiento específico contra bloque OBRAS SOCIALES
- [ ] 1.2 Modificar respuesta para status="accepted" (línea 10015): respuesta diferenciada si el paciente preguntó por un tratamiento específico
- [ ] 1.3 Reemplazar prohibición contradictoria (línea 10025): "PROHIBIDO confirmar" → "PERMITIDO informar si hay datos"
- [ ] 1.4 Reemplazar anti-ejemplo (línea 10029): sacar "Sí, trabajamos con OSDE para consultas y tratamientos quirúrgicos" del prompt

## Phase 2: Verificación manual

- [ ] 2.1 Verificar escenario A: "me cubre el implante con OSDE?" → NO responde "Sí" genérico, distingue consulta vs tratamiento
- [ ] 2.2 Verificar escenario B: "la consulta me cubre con OSDE?" → responde "Sí, la consulta puede ser por OSDE"
- [ ] 2.3 Verificar escenario C: "tengo OSDE" sin tratamiento → confirma OSDE, ofrece turno
- [ ] 2.4 Verificar escenario D: la frase "Sí, trabajamos con OSDE para consultas y tratamientos quirúrgicos" NO aparece en ninguna respuesta
