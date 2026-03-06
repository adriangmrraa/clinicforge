# Índice de documentación – ClinicForge

Este documento lista **todos** los archivos de la carpeta `docs/` con una breve descripción. Sirve como mapa para encontrar rápidamente qué documento consultar.  
**Protocolo:** Non-Destructive Fusion. Última revisión: 2026-03.

---

## 📘 Manuales y Guías Principales (Core)

Estos documentos explican el funcionamiento actual, la arquitectura y los procesos operativos del sistema.

| # | Archivo | Contenido |
|---|---------|-----------|
| 01 | [01_architecture.md](01_architecture.md) | Arquitectura del sistema: diagrama, microservicios, tools clínicas, cerebro híbrido, Socket.IO, multi-tenant. |
| 02 | [02_environment_variables.md](02_environment_variables.md) | Variables de entorno necesarias por cada servicio. |
| 03 | [03_deployment_guide.md](03_deployment_guide.md) | Guía de despliegue en producción (EasyPanel). |
| 04 | [04_agent_logic_and_persona.md](04_agent_logic_and_persona.md) | Lógica, persona y reglas de conversación del agente IA. |
| 05 | [05_developer_notes.md](05_developer_notes.md) | Notas técnicas para desarrolladores. |
| 06 | [06_ai_prompt_template.md](06_ai_prompt_template.md) | Plantilla de prompt base para el agente. |
| 07 | [07_workflow_guide.md](07_workflow_guide.md) | **Ciclo de tareas, Git y flujo de trabajo SDD v3.0 (Actualizado Feb 2026).** |
| 12 | [12_resumen_funcional_no_tecnico.md](12_resumen_funcional_no_tecnico.md) | **ACTUALIZADO** - Resumen funcional en lenguaje para humanos (incluye sistema de seguimiento post-atención). |
| 13 | [13_lead_patient_workflow.md](13_lead_patient_workflow.md) | Protocolo de conversión de contactos a pacientes. |
| 14 | [NUEVO_PROCESO_ADMISION_ANAMNESIS.md](NUEVO_PROCESO_ADMISION_ANAMNESIS.md) | **ACTUALIZADO** - Documentación completa del proceso de admisión y sistema de anamnesis automatizada (Marzo 2026). Incluye nota sobre campo `city` y migración requerida. |
| 15 | [SISTEMA_SEGUIMIENTO_POST_ATENCION.md](SISTEMA_SEGUIMIENTO_POST_ATENCION.md) | **NUEVO** - Sistema automatizado de seguimiento post-atención para pacientes de cirugía (Marzo 2026). |
| 16 | [SISTEMA_JOBS_PROGRAMADOS.md](SISTEMA_JOBS_PROGRAMADOS.md) | **NUEVO** - Arquitectura de jobs programados: recordatorios y seguimientos (Marzo 2026). |
| 17 | [ESTADO_ACTUAL_SISTEMA.md](ESTADO_ACTUAL_SISTEMA.md) | **NUEVO** - Estado actual del sistema, documentación vs código real, desfases corregidos (Marzo 2026). |
| 32 | [32_SECURITY_AUDIT_REPORT.md](32_SECURITY_AUDIT_REPORT.md) | **Reporte de Seguridad Actualizado (Misión 8 + Feb 2026).** |
| -- | [API_REFERENCE.md](API_REFERENCE.md) | Referencia completa de endpoints de la API. |
| -- | [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Guía activa de problemas comunes y soluciones. |

---

## 🔒 Auditoría y Seguridad (Compliance v8.0)

Documentos sobre el endurecimiento del sistema y reportes de seguridad.

| # | Archivo | Contenido |
|---|---------|-----------|
| 32 | [32_SECURITY_AUDIT_REPORT.md](32_SECURITY_AUDIT_REPORT.md) | Reporte de Seguridad Actualizado (Misión 8). |
| -- | [Auditoría de Seguridad Deep dive.md](Auditoría%20de%20Seguridad%20Deep%20dive.md) | Análisis profundo de vectores de ataque y mitigaciones. |
| -- | [spec_security_proactive_hardening.spec.md](spec_security_proactive_hardening.spec.md) | Especificación técnica del blindaje de prompts e infraestructura. |

---

## 🛠️ Lógica Interna y Deep Dives (Arquitectura Detallada)

Documentación técnica profunda sobre módulos específicos.

| Archivo | Contenido |
|---------|-----------|
| [INTEGRATIONS_LOGIC_DEEP_DIVE.md](INTEGRATIONS_LOGIC_DEEP_DIVE.md) | Lógica de integración de chats, webhooks y servicios cognitivos. |
| [meta_ads_backend.md](meta_ads_backend.md) | Backend de Meta Ads: Atribución, enriquecimiento y API. |
| [meta_ads_database.md](meta_ads_database.md) | Estructura de base de datos para Marketing ROI. |
| [meta_ads_frontend.md](meta_ads_frontend.md) | Componentes y estado de la UI de Marketing Hub. |
| [google_ads_integration.md](google_ads_integration.md) | **NUEVO:** Integración completa de Google Ads: OAuth, API, dashboard combinado. |
| [leads_forms_system.md](leads_forms_system.md) | Sistema de Leads Forms Meta con atribución automática. |
| [metrics_and_roi_calculation.md](metrics_and_roi_calculation.md) | Cálculo de ROI y métricas combinadas Meta + Google. |
| [CONTEXTO_AGENTE_IA.md](CONTEXTO_AGENTE_IA.md) | Guía de navegación para el Agente Antigravity. |
| [riesgos_entendimiento_agente_agendar.md](riesgos_entendimiento_agente_agendar.md) | Análisis de fallos lógicos en el flujo de agenda. |
| [TRANSFORMACION_AGNOSTICA_NICHO.md](TRANSFORMACION_AGNOSTICA_NICHO.md) | Estrategia de generalización de la plataforma. |

---

## 📜 Archivo Histórico y Desarrollo (Archive)

Documentos usados durante el desarrollo, auditorías cerradas y especificaciones implementadas.

| Archivo | Contenido |
|---------|-----------|
| [09_fase1_dental_datos.md](archive/09_fase1_dental_datos_especificacion.md) | Especificación original de la Fase 1 de datos. |
| [08_troubleshooting_history.md](archive/08_troubleshooting_history.md) | Histórico de incidentes previos. |
| [SPECS_IMPLEMENTADOS_INDICE.md](SPECS_IMPLEMENTADOS_INDICE.md) | Índice de especificaciones técnicas (ahora en `archive/specs/`). |
| [Auditoría OWASP 2025](archive/29_seguridad_owasp_auditoria.md) | Línea base inicial de seguridad OWASP. |
| [AUDIT_ESTADO_PROYECTO.md](archive/AUDIT_ESTADO_PROYECTO.md) | Reporte de estado consolidado (2026-02). |
| -- | [Ver carpeta /archive para auditorías y planes previos...](archive/) |

---

## Documentos en la raíz (Referencia Crítica)

- **[AGENTS.md](../AGENTS.md)**: Reglas de oro del proyecto y arquitectura de Soberanía.
- **[README.md](../README.md)**: Visión global y guía de inicio rápido.

---

**Total:** 37+ documentos organizados. Para auditoría de contrato API, ver Swagger en `/docs`.
