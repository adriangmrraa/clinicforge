# Análisis: Spec del Agente IA vs Implementación Actual en ClinicForge

**Última actualización:** 2026-03-11 | **Spec activa:** `specs/2026-03-11_mejoras-agente-ia-v2.spec.md`

El documento de spec de Codexy define **10 módulos** del sistema ideal para la Dra. Delgado. ClinicForge es la implementación de esa visión.

---

## Estado por Módulo

| Módulo Spec | Función | Estado en ClinicForge |
|:---|:---|:---|
| **M01** — Bot WhatsApp Atención 24/7 | Responde consultas frecuentes, tono clínica | ✅ **Implementado** — FAQs ampliadas de 4 → 13 en el prompt (sprint v2) |
| **M02** — Detección de Origen | UTM params, Instagram/Google/Referido/Otro | ✅ **Implementado** (campo `acquisition_source` en admisión) |
| **M03** — Admisión Paciente Nuevo | Fichas de paciente: nombre, DNI, email, ciudad, etc. | ✅ **Implementado** (flujo de a UN dato por mensaje) |
| **M04** — Anamnesis | Cuestionario de salud post-agendamiento | ✅ **Implementado** — guardado por IA + **visualización UI completa** (sprint v2) |
| **M05** — Agenda y Turnos | Disponibilidad real, turno, reprogramar, cancelar | ✅ **Implementado** (sistema híbrido GCal/local) |
| **M06** — Recordatorios y Confirmaciones | 24h antes automático, confirmación del paciente | ✅ **Implementado** (`jobs/reminders.py`, enviado por YCloud) |
| **M07** — Protocolo de Urgencias | Detección de urgencias, derivación, alertas | ✅ **Implementado** (`triage_urgency` + `derivhumano`) |
| **M08** — Seguimiento Post-Consulta | Mensajes automáticos según tratamiento | ✅ **Implementado** (`jobs/followups.py`) |
| **M09** — Reactivación de Inactivos | Campaña para pacientes sin actividad | ⚠️ **PARCIAL** — la lista de inactivos existe en dashboard; el envío automático de campaña NO está implementado |
| **M10** — Canal Instagram | DMs de Instagram conectados, derivación a WhatsApp | ⚠️ **PARCIAL** — Chatwoot integra Instagram en la bandeja unificada, pero sin flujo automático de derivación a WhatsApp |

---

## Sprint v2 — Mejoras implementadas el 2026-03-11

### ✅ System Prompt — FAQs ampliadas (M01)

| Antes | Después |
|:---|:---|
| 4 FAQs en el prompt | 13 FAQs específicas del consultorio |
| Ejemplo de tono con `¿` (bug) | Voseo correcto, sin `¿` ni `¡` |
| Sin ejemplos de conversación ideal | 2 ejemplos ideales de conversación incluidos |

Las 13 FAQs cubren: obra social, costos, financiación, dolor, implantes, ortodoncia adultos, ortopedia en niños, tiempo de tratamiento, blanqueamiento lactancia, extracción más implante, urgencias, documentación para primera consulta, lista de espera.

### ✅ Lógica de Servicios (M01 / M03)
- `list_services` ahora devuelve **solo nombres** (sin descripción) cuando el paciente pregunta qué tratamientos hay
- Se añadió regla explícita en el prompt: si el paciente pide info de un **servicio concreto** → llamar `get_service_details(code)` → el sistema envía imágenes automáticamente
- `get_service_details` docstring clarificado para cuándo usarlo y cuándo no

### ✅ Anamnesis — Visualización UI completa (M04)

**Nuevo componente compartido `AnamnesisPanel.tsx`:**
- Muestra los 8 campos del cuestionario de anamnesis
- Badges de alerta en condiciones críticas: `allergies`, `habitual_medication`, `pregnancy_lactation`
- Modo compact (panel lateral) y expanded (tab completo)
- Edición con RBAC: CEO edita siempre, profesional solo sus pacientes

**3 puntos de integración en el frontend:**

| Punto | Archivo | Modo | Editable |
|:---|:---|:---|:---|
| Panel derecho en Chats | `ChatsView.tsx` | compact | Solo lectura |
| 4ª tab en Detalle Paciente | `PatientDetail.tsx` | expanded | CEO/Profesional asignado |
| Tab Anamnesis en turno | `AppointmentForm.tsx` | expanded | Solo lectura |

**2 nuevos endpoints en `admin_routes.py`:**
- `GET /admin/patients/by-phone/{phone}` — Obtiene paciente por teléfono (usado en ChatsView)
- `PATCH /admin/patients/{patient_id}/anamnesis` — Actualiza anamnesis con validación de rol

---

## Capacidades del Agente Actual — Resumen Técnico

| Capability | Tool | Estado |
|:---|:---|:---|
| Listar tratamientos (solo nombres) | `list_services` | ✅ (mejorado v2) |
| Detalle de tratamiento + imagen | `get_service_details` | ✅ (regla activada en prompt v2) |
| Listar profesionales de BD | `list_professionals` | ✅ |
| Consultar disponibilidad real | `check_availability` | ✅ (híbrido GCal/local) |
| Registrar turno + paciente | `book_appointment` | ✅ |
| Guardar anamnesis | `save_patient_anamnesis` | ✅ |
| **Ver anamnesis en ChatsView** | `AnamnesisPanel` (compact) | ✅ **(nuevo v2)** |
| **Ver/editar anamnesis en Paciente** | `AnamnesisPanel` (4ª tab) | ✅ **(nuevo v2)** |
| **Ver anamnesis en turno** | `AnamnesisPanel` (modal) | ✅ **(nuevo v2)** |
| Ver turnos del paciente | `list_my_appointments` | ✅ |
| Cancelar turno | `cancel_appointment` | ✅ |
| Reprogramar turno | `reschedule_appointment` | ✅ |
| Triaje de urgencias | `triage_urgency` | ✅ |
| Derivar a humano (24h silencio) | `derivhumano` | ✅ |
| Procesar audios de voz | Whisper | ✅ (whatsapp_service) |
| Responder en español/inglés/francés | Detección idioma | ✅ |
| Recordatorios automáticos | job `reminders.py` | ✅ |
| Seguimiento post-atención | job `followups.py` | ✅ |
| Reactivación de inactivos | — | ❌ **FALTA** |
| Segundo recordatorio (4hs post-envío) | — | ❌ **FALTA** |
| Mensaje día del turno (2hs antes) | — | ❌ **FALTA** |

---

## Gaps Pendientes

### ⚠️ M09 — Reactivación de Pacientes Inactivos (prioritario)

| Tipo de Paciente | Criterio |
|:---|:---|
| En tratamiento sin turno | +X días → recordatorio de continuar |
| Rutina (control/blanqueamiento) | 60-90 días sin visita |
| Tratamiento completado | A los 6 y 12 meses |
| Lead que nunca sacó turno | 7 días sin turno → oferta evaluación gratuita |
| Inactivo general | +1 año → campaña personalizada |

**Trabajo necesario:** Crear `orchestrator_service/jobs/reactivation.py` con un job diario que evalúe los criterios de inactividad y envíe mensajes vía YCloud por tenant.

---

### ⚠️ M06 — Gaps menores de recordatorios

1. Recordatorio 24hs antes ✅ implementado
2. Si no confirma en 4hs → reenvío ❌ no implementado
3. Mensaje día del turno 2hs antes ❌ no implementado

---

### ⚠️ M10 — Canal Instagram (Parcial)

**Estado actual:** Chatwoot integra Instagram como canal. El agente responde mensajes de Instagram via Chatwoot. Sin embargo, **no existe un flujo automático** que proactivamente derive a WhatsApp cuando el paciente consulta un turno desde IG (hay que hacerlo manual).

---

### ⚠️ M02 — Gap técnico: rastreo UTM

La spec menciona UTM params para rastreo automático. **Estado actual:** El campo `acquisition_source` pregunta al paciente directamente via bot ("¿Cómo nos conociste?"). Gap menor dado el modelo de operación del consultorio.

---

## Prioridad de Trabajo sugerida

| Prioridad | Tarea | Complejidad |
|:---|:---|:---|
| 🔴 Alta | Job de reactivación de pacientes inactivos (`reactivation.py`) | Media |
| 🟡 Media | Segundo recordatorio (4hs post-primer-envío) y mensaje del día del turno | Baja |
| 🟡 Media | Verificar/completar campos de historia clínica (números de serie de implantes, seguimiento desde sesión) | Media |
| 🟢 Baja | Flujo automático de derivación Instagram → WhatsApp | Alta |
| 🟢 Baja | Tracking UTM automático | Alta |

---

## Conclusión

**ClinicForge implementa ~88% del sistema especificado.** Tras el sprint v2 (2026-03-11):

- ✅ Todos los módulos de atención, agendamiento, admisión, anamnesis (guardar + **visualizar**), urgencias, recordatorios básicos y seguimiento están alineados con la spec
- ✅ La anamnesis es ahora visible en los 3 puntos definidos en la spec (Chats, Detalle Paciente, Edit Turno)
- ✅ Las 13 FAQs del spec están hardcodeadas en el prompt
- ✅ La lógica de servicios (breve vs. detallado) está implementada en el prompt y en las tools

El módulo más significativo aún pendiente es la **reactivación automática de pacientes inactivos (M09)**, con alto valor clínico y comercial para la Dra. Delgado.
