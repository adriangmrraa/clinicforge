# 📊 Análisis de Gaps: Nexus v3 → Dentalogic

Este documento detalla el estado actual de la plataforma frente a los requerimientos de la **Plataforma Dentalogic**.

## 1. Backend (Lógica y Orquestación)

| Requerimiento | Estado | Notas |
| :--- | :--- | :--- |
| **Adaptación de Tools** | ✅ Implementado | `check_availability()` y `book_appointment()` existen en `orchestrator_service/main.py`. |
| **Sincronización Google Calendar** | ⚠️ Parcial | La lógica en `admin_routes.py` es simulada. Requiere implementación real de OAuth2. |
| **Triaje Automatizado** | ✅ Implementado | Tool `triage_urgency()` funcional con lógica NLP básica. |
| **Procesamiento de Audio** | ✅ Implementado | Integración con OpenAI Whisper en `whatsapp_service/main.py`. |
| **Mecanismo de Silencio (Lockout)** | ✅ Implementado | Funcionalidad `human_override_until` de 24h activa. |
| **Gestión de Profesionales** | ✅ Completado | Columna `working_hours` (JSONB) integrada y lógica de IA sincronizada. |
| **Relay de Mensajería** | ⚠️ Pendiente | El `Universal Delivery Relay` para envíos masivos no se detectó en la búsqueda. |

---

## 2. Frontend (Centro de Operaciones Dental)

| Requerimiento | Estado | Notas |
| :--- | :--- | :--- |
| **Monitor de Actividad** | ✅ Implementado | `DashboardView.tsx` muestra estadísticas de turnos y urgencias. |
| **Agenda Inteligente** | ⚠️ Parcial | `AgendaView.tsx` usa FullCalendar, pero el **Drag & Drop** no está habilitado comercialmente. |
| **Odontograma Interactivo** | ❌ Faltante | No se encontró la interfaz gráfica de odontograma en `frontend_react`. |
| **Perfil 360° del Paciente** | ✅ Implementado | `PatientDetail.tsx` incluye historial clínico, anamnesis y alertas médicas. |
| **Gestión de Profesionales (UI)** | ✅ Completado | Vista `ProfessionalsView.tsx` 100% responsiva con configuración de horarios IA-Aware. |
| **Módulo Contable** | ⚠️ Parcial | Existe `accounting_transactions` en DB, pero no la interfaz de usuario completa. |

---

## 3. Database (Persistencia y Estructura)

| Requerimiento | Estado | Notas |
| :--- | :--- | :--- |
| **Evolución del Esquema** | ✅ Implementado | Tablas `patients`, `appointments`, `clinical_records` y `accounting` creadas (Migración 004). |
| **Gestión de Alertas Médicas** | ✅ Implementado | Campo `medical_history` JSONB en `patients` con detección de alertas en el frontend. |
| **Memoria Persistente** | ✅ Implementado | Vinculación de `chat_messages` con `patient_id` funcional. |
| **Redis para Efimeridad** | ✅ Implementado | Deduplicación y locks en Redis activos en `whatsapp_service`. |
| **Bóveda de Credenciales** | ✅ Implementado | Sistema de almacenamiento en `credentials_vault` (vía `admin/internal/credentials`). |

---

## 🚀 Resumen de Próximos Pasos

1. **Implementar OAuth2 real** para Google Calendar.
2. **Desarrollar el componente de Odontograma** (SVG Interactivo).
3. **Activar Drag & Drop** en la Agenda.
4. **Construir el Dashboard Contable** para liquidaciones de Obras Sociales.
