# Referencia Version Estable – Chatwoot y clínicas

**Propósito:** Este documento enlaza la implementación de Chatwoot en **CLINICASV1.0** con la especificación y el plan que viven en **Version Estable**. El código evoluciona en CLINICASV1.0; Version Estable es referencia de specs, planes y código a copiar/adaptar.

---

## Documentos de referencia (Version Estable)

| Documento | Ubicación (relativa al workspace) | Contenido |
|-----------|-----------------------------------|-----------|
| **Spec clínicas + Chatwoot** | `Version Estable/docs/specs/version_estable_clinicas.spec.md` | SSOT: objetivos, principio YCloud intacto, tablas chat_conversations/credentials, webhook, API UI, relay/buffer, frontend (filtro canal, Config Chatwoot), Vault, criterios de aceptación. |
| **Plan evolución Chatwoot** | `Version Estable/docs/plans/2025-02-13-evolucion-clinicasv1-chatwoot.md` | Tareas 1–11: BD, credentials, ChatwootClient, webhook, relay/buffer, chat_api, main.py, ChatsView, ConfigView, dependencias, verify. |
| **Comparativa CLINICASV1 vs Version Estable** | `Version Estable/docs/CLINICASV1_VS_VERSION_ESTABLE.md` | Diferencias entre ambos proyectos y criterios de paridad. |
| **Integración clínicas V1** | `Version Estable/docs/INTEGRACION_CLINICAS_V1.md` | Contexto de integración. |
| **Implement chat omnicanal** | `Version Estable/docs/IMPLEMENT_CHAT_OMNICHANNEL.md` | Guía de implementación del chat omnicanal. |
| **Specs técnicos Chatwoot** | `Version Estable/docs/specs/chatwoot_integration.spec.md`, `chats_omnichannel_final.spec.md` | Detalle técnico webhook, canales, buffer. |

---

## Estado en CLINICASV1.0

- **Implementado:** Tablas (parches en `db.py`), `core/credentials.py`, `chatwoot_client.py`, `routes/chat_webhooks.py`, `routes/chat_api.py`, `services/relay.py`, `services/buffer_task.py`, routers montados en `main.py`, Vault agente (`get_agent_executable_for_tenant`), ChatsView (lista unificada, filtro Todos/WhatsApp/Instagram/Facebook, polling 10s/3s), ConfigView (sección Chatwoot). Drifts corregidos (audit 2025-02-13).
- **Auditoría:** `docs/AUDIT_CHATWOOT_2025-02-13.md` (comparativa código vs spec, drifts y correcciones aplicadas).
- **API:** `docs/API_REFERENCE.md` (sección *Chat omnicanal (Chatwoot)*).

---

## Comprobar alineación

Para revisar que CLINICASV1.0 sigue alineado con Version Estable en Chatwoot:

1. Comparar criterios de aceptación de `version_estable_clinicas.spec.md` §10 con el estado en `AUDIT_CHATWOOT_2025-02-13.md`.
2. Verificar endpoints en `API_REFERENCE.md` y en Swagger (`/docs`) del orchestrator de CLINICASV1.0.
3. Ejecutar el workflow **Audit** (`.agent/workflows/audit.md`) cuando se cambie código relacionado con chat o credenciales.

---

*Documento de referencia. Protocolo: Non-Destructive Fusion. Actualizado 2026-02.*
