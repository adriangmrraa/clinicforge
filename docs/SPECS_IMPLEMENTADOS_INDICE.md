# Índice de especificaciones implementadas

Este documento registra las especificaciones (`.spec.md`) que existían en el proyecto y dónde queda documentada cada funcionalidad tras la consolidación. Los archivos `.spec.md` fueron retirados para reducir dispersión; el contenido útil se migró a la documentación permanente siguiendo el protocolo **Non-Destructive Fusion**.

**Fecha de consolidación:** 2026-02-09

---

## Especificaciones consolidadas

| Especificación original | Estado | Dónde está documentado ahora |
|-------------------------|--------|-------------------------------|
| **14_google_calendar_sync_fix.spec.md** | Implementado | `01_architecture.md` (cerebro híbrido, JIT), `08_troubleshooting_history.md` (sección Calendario e IA). |
| **15_agenda_inteligente_2_0.spec.md** | Implementado | `README.md` (Agenda), `12_resumen_funcional_no_tecnico.md`, `01_architecture.md`. |
| **15_ceo_professionals_analytics.spec.md** | Implementado | `README.md` (Analíticas CEO), `API_REFERENCE.md` (GET /admin/analytics/professionals/summary, GET /admin/professionals/{id}/analytics). |
| **16_sovereign_glass_architecture.spec.md** | Implementado | Estilo UI en componentes; `README.md` (Landing / Demo), `AGENTS.md`. |
| **17_mobile_agenda_range_fix.spec.md** | Implementado | `01_architecture.md`, vistas Agenda en frontend. |
| **18_mobile_scroll_fix.spec.md** | Implementado | `AGENTS.md` (aislamiento de scroll), vistas con `min-h-0 overflow-y-auto`. |
| **19_treatments_optimization.spec.md** | Implementado | `README.md` (Tratamientos), `API_REFERENCE.md` (treatment-types). |
| **20_professionals_personal_activo_sync.spec.md** | Implementado | `README.md` (Personal y aprobaciones), `12_resumen_funcional_no_tecnico.md` (Registro y aprobación). |
| **21_lead_vs_paciente_solo_con_turno.spec.md** | Implementado | `13_lead_patient_workflow.md`, flujo del agente en `README.md`. |
| **22_professionals_ceo_control_vision.spec.md** | Implementado | `README.md` (Analíticas, Personal, Sedes), `01_architecture.md`. |
| **23_registro_con_sede_y_datos_profesional.spec.md** | Implementado | `README.md` (Guía rápida), `API_REFERENCE.md` (POST /auth/register con tenant_id, specialty, etc.). |
| **24_modal_datos_profesional_acordeon.spec.md** | Implementado | Vista Aprobaciones / Personal Activo (UserApprovalView, modales). |
| **25_idioma_plataforma_y_agente.spec.md** | Implementado | `README.md` (Idiomas e internacionalización), `01_architecture.md`, Configuración y agente en es/en/fr. |
| **26_calendario_hibrido_clinica_profesional.spec.md** | Implementado | `01_architecture.md` (cerebro híbrido, tools), `08_troubleshooting_history.md` (sección "Calendario e IA: La IA no puede ver disponibilidad"), `API_REFERENCE.md` (Turnos, Calendario). |
| **27_staff_scroll_aislamiento.spec.md** | Implementado | `AGENTS.md` (Aislamiento de Scroll), UserApprovalView con `flex-1 min-h-0 overflow-y-auto`. |
| **28_landing_demo_publica.spec.md** | Implementado | `README.md` (Landing / Demo pública), rutas `/demo`, `/login?demo=1`, LandingView. |
| **29_seguridad_owasp_auditoria.spec.md** | Implementado / migrado | **`29_seguridad_owasp_auditoria.md`** (mismo contenido; documento permanente de seguridad y OWASP). |
| **version_estable_clinicas (Chatwoot omnicanal)** | Implementado | Spec en `Version Estable/docs/specs/version_estable_clinicas.spec.md`. En CLINICASV1.0: `docs/AUDIT_CHATWOOT_2025-02-13.md` (auditoría y correcciones), `API_REFERENCE.md` (sección Chat omnicanal), tablas `chat_conversations` y `credentials`, webhook `/admin/chatwoot/webhook`, API `/admin/chats/summary`, `/admin/chats/{id}/messages`, `/admin/whatsapp/send`, `/admin/conversations/{id}/human-override`, ConfigView (URL webhook), ChatsView (filtro canal Todos/WhatsApp/Instagram/Facebook, Vault agente por tenant). |
| **spec_13_unified_clinical_context.spec.md** | Implementado | `13_lead_patient_workflow.md` (identidad y visibilidad), `API_REFERENCE.md` (soporte platform IDs). |
| **spec_14_multichannel_ui.spec.md** | Implementado | `meta_ads_frontend.md` (sección 6 - Patrones de UI), `ChatsView.tsx` (lógica de estilos dinámicos). |
| **spec_18_outgoing_messages.spec.md** | Implementado | `API_REFERENCE.md` (sección "4. Envío de Mensajes (Omnicanal)" con `POST /admin/chat/send`, validación 24h, enrutamiento a YCloudClient/ChatwootClient). |

Cualquier criterio de aceptación o detalle técnico de los specs anteriores que no figure en los documentos indicados se considera cubierto por la implementación en código y por AGENTS.md (reglas de soberanía, scroll, auth).

**Especificación en subproyecto:** `Dashboard_Analytics_Sovereign/docs/specs/01_dashboard_analytics.spec.md` fue retirada; la funcionalidad y planes siguen en `Dashboard_Analytics_Sovereign/docs/plans/` (feasibility_report, implementation_plan, technical_gate).

---

## Documentos de referencia principales

- **Índice de toda la documentación:** [00_INDICE_DOCUMENTACION.md](00_INDICE_DOCUMENTACION.md) (lista de los docs en `docs/`).
- **Funcionalidad y uso:** `README.md`, `12_resumen_funcional_no_tecnico.md`
- **Arquitectura y flujos:** `01_architecture.md`, `13_lead_patient_workflow.md`
- **API:** `API_REFERENCE.md`, Swagger en `/docs` del Orchestrator
- **Chatwoot / Version Estable:** `AUDIT_CHATWOOT_2025-02-13.md` (auditoría y drifts corregidos), `REFERENCIA_VERSION_ESTABLE_CHATWOOT.md` (enlaces a spec y plan en Version Estable)
- **Seguridad:** `29_seguridad_owasp_auditoria.md`, `AGENTS.md`
- **Problemas conocidos y soluciones:** `08_troubleshooting_history.md`
- **Despliegue y variables:** `02_environment_variables.md`, `03_deployment_guide.md`

---

*Índice generado en el marco del workflow Update Docs (Non-Destructive Fusion).*
