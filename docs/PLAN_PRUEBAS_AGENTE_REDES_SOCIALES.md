# Plan de Pruebas Proactivo — Agente de Redes Sociales (Instagram + Facebook)

**Ticket**: DLD-63
**Fecha**: 2026-05-08
**Estado**: En curso
**Responsable**: Adrián Gamarra

---

## Arquitectura: Lo que comparten y lo que difiere

### Pipeline unificado
WhatsApp, Instagram y Facebook comparten el **mismo pipeline**:
- Mismo `buffer_task.py` (procesamiento de mensajes)
- Mismos `DENTAL_TOOLS` (check_availability, book_appointment, confirm_slot, etc.)
- Mismo system prompt base (`build_system_prompt()`)
- Mismo motor de IA (SoloEngine o MultiAgentEngine según tenant)

### Diferencia: Social Preamble
Instagram y Facebook reciben un **preamble adicional** prepended al prompt (`build_social_preamble()` en `services/social_prompt.py`) con 8 reglas específicas:

| Regla | Descripción |
|-------|-------------|
| R1 | Booking directo — PROHIBIDO redirigir a WhatsApp |
| R2 | CTA routes — keywords → pitch + landing URL |
| R3 | Otros tratamientos → `list_services` |
| R4 | Detección amigo vs lead |
| R5 | Ética médica — no diagnóstico por DM |
| R6 | Tools prohibidos: `triage_urgency` |
| R7 | Markdown habilitado (a diferencia de WhatsApp) |
| R8 | Español rioplatense con voseo |

---

## Fixes recientes ya aplicados (automáticos en todos los canales)

Estos fixes viven en el system prompt de `main.py` y se aplican a los 3 canales:

| Fix | Commit | Verificar en redes |
|-----|--------|--------------------|
| Anti-repetición de OS/coseguro | `a2b8adc` | Preguntar 2 veces por la misma OS → no debe repetir info idéntica |
| Greeting como 3 burbujas separadas | `f81dcbe` | Primer mensaje → 3 burbujas: "Hola 😊" / "Soy Paula..." / especialidad |
| Regla de No-Elección | `94f4821` | Decir "no sé" o "lo tengo que pensar" → NO re-ofrecer turnos |
| 12 correcciones de Dra. Laura | `5b23c0f` | Mensajes cortos, max 1-2 emojis, voseo, no repetir frase |
| No same-day booking | `2dc0c49` | Pedir turno "hoy" → debe ofrecer desde mañana |
| Soft-lock double-booking | `640cd1a` | 2 pacientes al mismo tiempo → cada uno con profesional diferente |

---

## Checklist de pruebas — Instagram

### A. Flujo de saludo y presentación
- [ ] **A1**: Enviar "Hola" → debe responder con 3 burbujas separadas (saludo + nombre + especialidad)
- [ ] **A2**: NO debe decir "¿En qué te puedo ayudar?" al final del saludo
- [ ] **A3**: NO debe mencionar "asistente virtual" — debe decir "del equipo de [clínica]"
- [ ] **A4**: Debe usar voseo ("podés", "querés", "tenés")

### B. Flujo de booking desde Instagram
- [ ] **B1**: Preguntar por blanqueamiento → debe dar pitch + landing URL (CTA route)
- [ ] **B2**: Pedir turno → debe ofrecer 2 opciones (no 1, no 3)
- [ ] **B3**: Elegir turno → debe pedir datos (nombre, DNI) ANTES de confirmar
- [ ] **B4**: Confirmar turno → NO debe redirigir a WhatsApp para agendar
- [ ] **B5**: Post-booking → debe ofrecer link de WhatsApp "Para futuras consultas..."
- [ ] **B6**: Pedir turno "hoy" → debe ofrecer desde mañana (DLD-67)

### C. Reglas de tono y formato
- [ ] **C1**: Mensajes cortos (max 2-3 líneas por burbuja)
- [ ] **C2**: Max 1-2 emojis por mensaje
- [ ] **C3**: NO párrafos largos
- [ ] **C4**: Markdown habilitado (negritas, cursivas) — verificar que se renderice bien en IG
- [ ] **C5**: Tono natural argentino, no genérico

### D. Reglas de no-repetición
- [ ] **D1**: Preguntar por OS → responde info
- [ ] **D2**: Preguntar de nuevo por la misma OS → NO repite idénticamente, reformula brevemente
- [ ] **D3**: Decir "no sé" o "lo tengo que pensar" → deja de ofrecer turnos

### E. Detección amigo vs lead
- [ ] **E1**: Enviar "Hola amiga!" → debe detectar como amiga, no ofrecer turno directo
- [ ] **E2**: Enviar "Hola, quiero blanqueamiento" → detectar como lead, activar CTA
- [ ] **E3**: Enviar keyword de CTA incluso en tono informal → SIEMPRE tratar como lead (override)

### F. Tools prohibidos
- [ ] **F1**: Describir síntomas graves → NO debe hacer triage de urgencia
- [ ] **F2**: Ante síntomas → debe recomendar consulta presencial o derivar a humano
- [ ] **F3**: NO debe dar diagnósticos por DM

### G. Datos del paciente en redes
- [ ] **G1**: Después de booking → pedir teléfono ("¿Me pasás tu número?")
- [ ] **G2**: Guardar email si el paciente lo proporciona
- [ ] **G3**: Enviar link de anamnesis post-booking

---

## Checklist de pruebas — Facebook

### Mismos tests que Instagram (A-G) más:
- [ ] **FB1**: Verificar que el preamble dice "Facebook" y no "Instagram"
- [ ] **FB2**: Verificar que landing URLs funcionan desde Facebook Messenger
- [ ] **FB3**: Verificar que los mensajes se entregan correctamente via Chatwoot

---

## Pruebas de concurrencia (Instagram + WhatsApp simultáneo)

- [ ] **CC1**: Mismo paciente escribe por IG y WhatsApp → debe mantener contexto separado por canal
- [ ] **CC2**: Paciente agenda por IG → el turno aparece en la agenda del CRM
- [ ] **CC3**: 2 pacientes piden turno al mismo horario desde IG → soft-lock funciona (cada uno con profesional diferente)

---

## Configuración previa necesaria

1. **Verificar en Settings**: `social_ig_active = true` para el tenant
2. **Verificar CTA routes**: Que estén configurados los keywords y landing URLs en la config del tenant
3. **Verificar Chatwoot**: Que el canal de Instagram esté conectado y activo
4. **Verificar bot_name**: Que coincida con el nombre del agente en el preamble

---

## Criterios de aprobación

- Todos los items A-G pasan para Instagram
- Todos los items A-G + FB1-FB3 pasan para Facebook
- Todos los items CC1-CC3 de concurrencia pasan
- Cero fugas de prompt (no se muestra texto interno al paciente)
- Cero redirecciones a WhatsApp durante el flujo de booking
- Tono consistente con el agente de WhatsApp (pero con markdown habilitado)

---

## Hallazgos

*Sección para documentar bugs encontrados durante las pruebas*

| # | Canal | Test | Bug encontrado | Severidad | Ticket |
|---|-------|------|---------------|-----------|--------|
| | | | | | |
