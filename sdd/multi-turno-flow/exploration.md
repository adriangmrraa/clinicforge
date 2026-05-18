# Exploration: Multi-turno flow in system prompt

## Current State

### El problema (evidenciado en CASO 3)
Paciente agenda evaluación, después pide implante + arreglo. El agente ofrece el mismo horario que ya está ocupado, se enreda, y termina derivando.

### Lo que YA existe
- **Patient conflict guard** (fix de esta sesión): evita ofrecer slots donde el paciente ya tiene turno en check_availability
- **DLD-59** en book_appointment: bloquea turnos en la misma fecha (demasiado restrictivo)
- **PASO 2b**: "El turno es para vos o para otra persona?" (para terceros)
- **CONTEXTO DEL PACIENTE**: muestra PRÓXIMO TURNO si existe
- **REGLA POST-DATOS** (~L9829): si ya dio datos + intención → ejecutar sin preguntar

### Lo que FALTA
- **No hay ningún PASO** que diga "si el paciente YA tiene un turno y pide otro, qué hacer"
- El prompt asume que cada conversación es para UN turno
- Cuando el paciente dice "ahora quiero otro turno", el agente improvisa

### Escenarios no cubiertos
1. Paciente con turno existente pide SEGUNDO turno para otro tratamiento
2. Paciente con turno existente pide turno para OTRA PERSONA (hijo)
3. Paciente pregunta "puedo sacar dos turnos el mismo día?"

## Affected Areas
- `orchestrator_service/main.py` ~9870 — entre PASO 3 y PASO 4 (o nuevo PASO 3b)

## Approaches

### Approach A: Nuevo PASO 3b - Multi-turno
Agregar entre PASO 3 y PASO 4:
```
PASO 3b: PACIENTE CON TURNO EXISTENTE — Si el paciente YA tiene un turno agendado y pide OTRO:
  • Reconocelo: "Ya tenés turno el [día] a las [hora]. Querés otro turno para [tratamiento]?"
  • El nuevo turno: debe ser en distinto horario. NO ofrecer el mismo slot.
  • Si pide mismo día pero distinta hora: OK, siempre que el profesional esté libre.
  • Si pide mismo día misma hora: NO, ya está ocupado.
```
- **Effort**: Bajo
- **Riesgo**: Mínimo

### Approach B: Modificar Regla de Continuidad (~L9953)
Agregar que la Regla de Continuidad también aplica cuando el paciente pide un SEGUNDO turno
- **Effort**: Bajo
- **Riesgo**: Bajo

## Recommendation
**Approach A** — Es más explícito y fácil de entender para el LLM.

## Ready for Proposal
Sí.
