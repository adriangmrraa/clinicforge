# Índice de documentación – Dentalogic

Este documento lista **todos** los archivos de la carpeta `docs/` con una breve descripción. Sirve como mapa para encontrar rápidamente qué documento consultar.  
**Protocolo:** Non-Destructive Fusion. Última revisión: 2026-02.

---

## Documentos numerados (por orden)

| # | Archivo | Contenido |
|---|---------|-----------|
| 01 | [01_architecture.md](01_architecture.md) | Arquitectura del sistema: diagrama, microservicios (Orchestrator, WhatsApp), tools clínicas, cerebro híbrido, Socket.IO, multi-tenant, analytics. |
| 02 | [02_environment_variables.md](02_environment_variables.md) | Variables de entorno por servicio: Orchestrator, WhatsApp, PostgreSQL, Redis, OpenAI, YCloud, Google, JWT, ADMIN_TOKEN, CREDENTIALS_FERNET_KEY. |
| 03 | [03_deployment_guide.md](03_deployment_guide.md) | Guía de despliegue: EasyPanel, configuración de producción, service accounts. |
| 04 | [04_agent_logic_and_persona.md](04_agent_logic_and_persona.md) | Lógica del agente dental: persona, reglas de conversación, tools (check_availability, book_appointment, triage, etc.), flujo de datos. |
| 05 | [05_developer_notes.md](05_developer_notes.md) | Notas para desarrolladores: añadir tools, paginación, debugging, Maintenance Robot, i18n, agenda móvil, analytics, landing. |
| 06 | [06_ai_prompt_template.md](06_ai_prompt_template.md) | Plantilla de prompt para el agente IA. |
| 07 | [07_workflow_guide.md](07_workflow_guide.md) | Guía de flujo de trabajo: ciclo de tareas, Git, documentación, troubleshooting, comunicación entre servicios. |
| 08 | [08_troubleshooting_history.md](08_troubleshooting_history.md) | Histórico de problemas y soluciones; sección "Calendario e IA: La IA no puede ver disponibilidad". |
| 09 | [09_fase1_dental_datos_especificacion.md](09_fase1_dental_datos_especificacion.md) | Fase 1 evolución de datos: especificación técnica, tablas (patients, professionals, appointments, clinical_records, etc.), estado de implementación. |
| 11 | [11_gap_analysis_nexus_to_dental.md](11_gap_analysis_nexus_to_dental.md) | Análisis de gaps: estado de implementación vs requerimientos finales. |
| 12 | [12_resumen_funcional_no_tecnico.md](12_resumen_funcional_no_tecnico.md) | Resumen funcional en lenguaje no técnico: qué hace la plataforma, cerebro, dashboard, trabajo en equipo, registro y aprobación, control humano. |
| 13 | [13_lead_patient_workflow.md](13_lead_patient_workflow.md) | Flujo lead → paciente: protocolo de conversión de contactos a pacientes activos. |
| 29 | [29_seguridad_owasp_auditoria.md](29_seguridad_owasp_auditoria.md) | Auditoría de seguridad OWASP Top 10:2025; cómo gestiona el backend la seguridad; JWT + X-Admin-Token; redacción de credenciales en demo. |
| 30 | [30_audit_api_contrato_2026-02-09.md](30_audit_api_contrato_2026-02-09.md) | Auditoría del contrato API: verificación de que OpenAPI y documentación coinciden con los endpoints reales. |
| 31 | [31_audit_documentacion_2026-02-09.md](31_audit_documentacion_2026-02-09.md) | Auditoría de documentación: alineación con la plataforma SaaS; corrección de referencias a specs consolidados. |

---

## Documentos por nombre (alfabético)

| Archivo | Contenido |
|---------|-----------|
| [API_REFERENCE.md](API_REFERENCE.md) | Referencia completa de la API: autenticación, auth, configuración, usuarios, sedes, pacientes, turnos, chat (YCloud + Chatwoot omnicanal), profesionales, calendario, tratamientos, estadísticas, analítica, health, chat IA. Incluye Swagger en `/docs`, ReDoc en `/redoc`. |
| [AUDIT_CHATWOOT_2025-02-13.md](AUDIT_CHATWOOT_2025-02-13.md) | Auditoría de la integración Chatwoot: comparativa código vs spec version_estable_clinicas; drifts detectados y correcciones aplicadas (Vault agente, filtro canal, polling). |
| [audit_26_calendario_hibrido_2026-02-10.md](audit_26_calendario_hibrido_2026-02-10.md) | Auditoría del calendario híbrido: verificación código vs especificación (contenido migrado a 01_architecture, 08_troubleshooting, SPECS_IMPLEMENTADOS_INDICE). |
| [AUDIT_ESTADO_COMPLETO_POR_PAGINA.md](AUDIT_ESTADO_COMPLETO_POR_PAGINA.md) | Auditoría estado completo por página del frontend. |
| [AUDIT_ESTADO_PROYECTO.md](AUDIT_ESTADO_PROYECTO.md) | Estado del proyecto: backend, frontend, BD, specs vs código; endpoints por módulo; acciones correctivas; trazabilidad en SPECS_IMPLEMENTADOS_INDICE. |
| [cambios_recientes_2026-02-10.md](cambios_recientes_2026-02-10.md) | Resumen de cambios recientes (spec 26, disponibilidad, paciente+turno, scroll Staff, landing, docs). |
| [CONTEXTO_AGENTE_IA.md](CONTEXTO_AGENTE_IA.md) | Punto de entrada para agentes IA: qué es el proyecto, stack, carpetas, reglas, API, rutas frontend, BD, i18n, índice de documentación, tareas frecuentes. |
| [Instrucciones para IA.md](Instrucciones%20para%20IA.md) | Instrucciones dirigidas a una IA que trabaje en el proyecto. |
| [MATRIZ_DECISION_SKILLS.md](MATRIZ_DECISION_SKILLS.md) | Matriz de decisión para elegir skills según tipo de tarea. |
| [mision_maestra_agenda.md](mision_maestra_agenda.md) | Misión maestra de la agenda: objetivos y criterios. |
| [PROMPT_CONTEXTO_IA_COMPLETO.md](PROMPT_CONTEXTO_IA_COMPLETO.md) | Bloque de texto listo para copiar/pegar al inicio de una conversación con una IA: contexto global, reglas, workflows, skills, checklist. |
| [PROTOCOLO_AUTONOMIA_SDD.md](PROTOCOLO_AUTONOMIA_SDD.md) | Protocolo de autonomía SDD v2.0: ciclo de retroalimentación, criterios de detención, soberanía de datos. |
| [REFERENCIA_VERSION_ESTABLE_CHATWOOT.md](REFERENCIA_VERSION_ESTABLE_CHATWOOT.md) | Enlaces a spec y plan de Chatwoot en Version Estable; estado de implementación en CLINICASV1.0 y comprobación de alineación. |
| [riesgos_entendimiento_agente_agendar.md](riesgos_entendimiento_agente_agendar.md) | Riesgos de entendimiento del agente al agendar: análisis y mitigaciones. |
| [SPECS_IMPLEMENTADOS_INDICE.md](SPECS_IMPLEMENTADOS_INDICE.md) | Índice de especificaciones implementadas: consolidación de .spec.md retirados; dónde está documentada cada funcionalidad. |
| [TRANSFORMACION_AGNOSTICA_NICHO.md](TRANSFORMACION_AGNOSTICA_NICHO.md) | Transformación a plataforma agnóstica de nicho: base reutilizable, qué cambia por nicho, ejemplo CRM vendedores/setters, 10 prompts clave para empezar; para arrancar conversación con agente de código (leer con CONTEXTO_AGENTE_IA y PROMPT_CONTEXTO_IA_COMPLETO). |

---

## Documentos en la raíz del proyecto (referencia)

| Archivo | Contenido |
|---------|-----------|
| **AGENTS.md** (raíz) | Guía suprema del proyecto: arquitectura, soberanía de datos, aislamiento de scroll, tools, Maintenance Robot, i18n, connect-sovereign. **Leer antes de modificar.** |
| **README.md** (raíz) | Visión, tecnología, características, estructura del proyecto, despliegue, documentación hub. |

---

## Total

- **En `docs/`:** 30+ archivos Markdown (numerados 01–31 y por nombre; incluye AUDIT_CHATWOOT_2025-02-13).
- **En raíz:** AGENTS.md, README.md.

Para una lista detallada de endpoints y contratos API, usar [API_REFERENCE.md](API_REFERENCE.md) y Swagger en `http://localhost:8000/docs`.
