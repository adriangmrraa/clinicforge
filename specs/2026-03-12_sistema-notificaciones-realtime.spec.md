# Sistema de Notificaciones Real-Time — ClinicForge (Nexus v7.6)

> **Origen:** Análisis de `main.py`, `chat_webhooks.py` y `DashboardView.tsx`.
> **Sprint:** Mejora 2 — Notificaciones de Agendamientos, Urgencias y Nuevos Pacientes.

---

## 1. Contexto y Objetivos

- **Problema:** El sistema actual carece de interactividad inmediata para eventos críticos de CRM y atención de pacientes.
  1. **Nuevos Pacientes:** No hay alerta visual cuando entra un lead; solo se ve si se refresca la lista de pacientes/leads.
  2. **Urgencias Desincronizadas:** El Dashboard muestra urgencias, pero la lista es estática desde la carga inicial.
  3. **Toast Limitado:** Solo existe `HUMAN_HANDOFF` en el Layout global.

- **Solución:**
  1. Implementar el evento `NEW_PATIENT` en los webhooks de entrada.
  2. Convertir el Dashboard en una interfaz reactiva que escuche `PATIENT_UPDATED` y `NEW_APPOINTMENT`.
  3. Ampliar el `Layout.tsx` para mostrar Toasts de diversos tipos (Lead, Urgencia, Agendamiento).

- **KPIs:**
  - Tiempo de respuesta a nuevos leads: -30% esperado.
  - Sincronización del Dashboard: 100% real-time sin F5.

---

## 2. Esquemas de Datos (Eventos Socket.IO)

### NEW_PATIENT (Nuevo)
**Emisor:** `chat_webhooks.py` o `ensure_patient_exists`.
**Payload:**
```typescript
{
  tenant_id: number;
  phone_number: string;
  name: string;
  channel: 'whatsapp' | 'instagram' | 'facebook';
}
```

### PATIENT_UPDATED (Existente, ampliar uso)
**Emisor:** `main.py` (triage_urgency).
**Payload:**
```typescript
{
  tenant_id: number;
  phone_number: string;
  urgency_level: 'NORMAL' | 'HIGH' | 'CRITICAL';
  reason: string;
  patient_name: string;
}
```

---

## 3. Lógica de Negocio (Clarificaciones Incorporadas)

### Notificaciones Globales (Layout.tsx)
- **Visibilidad:** Todos los Toasts duran **10 segundos**.
- **Alcance:** Todos los usuarios del `tenant_id` reciben las notificaciones.
- **Interactividad (Click/Touch):**
  - **Urgencia (`PATIENT_UPDATED`):** Redirige a `/chats` seleccionando la conversación del paciente.
  - **Nuevo Paciente (`NEW_PATIENT`):** Redirige a `/leads` o `/chats` (según origen) para ver el nuevo contacto. Se muestra toda la info disponible (nombre, teléfono, canal).
  - **Agendamiento (`NEW_APPOINTMENT`):** Redirige a `/agenda` y **abre automáticamente el modal de edición** del turno correspondiente.
- **Sonidos:**
  - **Urgencia Crítica:** Sonido de alerta distintivo y persistente.
  - **Resto (Agendamientos/Leads):** Sonido de notificación estándar.

### Dashboard & Vistas (Reactividad)
- **Dashboard:** Actualización dinámica de:
  - Lista de Urgencias Recientes (insersión local o refetch silencioso).
  - Contadores de KPIs (IA Appointments, Active Urgencies).
- **Leads Management:** Recarga automática de la lista ante `NEW_PATIENT`.

---

## 4. Clarificaciones Incorporadas (/clarify — 2026-03-12)

| # | Pregunta | Respuesta | Impacto en spec |
|---|---|---|---|
| 1 | Alcance de Notificaciones | Todos los usuarios del tenant. | Sin filtrado por rol en frontend para Toasts básicos. |
| 2 | Sonidos | Distinto para Urgencia Crítica. | Lógica condicional en `Layout.tsx` para `audio.play()`. |
| 3 | Duración e Interacción | 10 segundos + Click-to-Redirect. | `setTimeout` a 10s. Lógica de `navigate` con estado específico. |
| 4 | Dashboard Refresh | Dinámico (Real-time). | Sincronización de estado en `DashboardView.tsx`. |
| 5 | Privacidad/Info | Mostrar toda la relación al paciente en New Patient. | Payload de `NEW_PATIENT` debe ser completo. |

---

## 5. Criterios de Aceptación (Gherkin)

### Escenario: Redirección de Agendamiento
- DADO que recibo una notificación de `NEW_APPOINTMENT`
- CUANDO hago click en el Toast
- ENTONCES la app me redirige a `/agenda`
- Y el modal de edición del turno se abre automáticamente con los datos del paciente.

### Escenario: Notificación de Urgencia Crítica
- DADO que un paciente reporta síntomas graves
- CUANDO el bot emite `PATIENT_UPDATED` con severidad `CRITICAL`
- ENTONCES suena un tono de alerta especial
- Y el Toast es rojo y permanece 10 segundos.

---

*Spec generada: 2026-03-12 | SDD v2.0 | Refinada con clarificaciones finales*
