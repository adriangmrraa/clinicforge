# Informe de auditoría: integración Chatwoot (Spec Drift)

**Workflow:** `.agent/workflows/audit.md`  
**SSOT:** `Version Estable/docs/specs/version_estable_clinicas.spec.md`  
**Plan:** `Version Estable/docs/plans/2025-02-13-evolucion-clinicasv1-chatwoot.md`  
**Fecha:** 2025-02-13  
**Alcance:** Código implementado en **CLINICASV1.0** (backend + frontend) frente a la spec y al plan.

**Actualización:** Corrección de los tres drifts aplicada (Vault agente, filtro canal Instagram/Facebook, polling 10s/3s).

---

## 1. Comparativa realizada

- Lectura de la spec (§1–§11), plan (tareas 1–11) y código en:
  - `CLINICASV1.0/orchestrator_service/`: db.py, core/credentials.py, chatwoot_client.py, routes/chat_webhooks.py, routes/chat_api.py, services/relay.py, services/buffer_task.py, main.py
  - `CLINICASV1.0/frontend_react/src/`: views/ChatsView.tsx, views/ConfigView.tsx, api/chats.ts, types/chat.ts

---

## 2. Criterios de aceptación (spec §10) – estado

| # | Criterio | Estado | Notas |
|---|----------|--------|--------|
| 1 | YCloud intacto | ✅ Match | Flujo YCloud sin cambios; lista unificada añadida de forma aditiva. |
| 2 | Chatwoot: recibir, almacenar, mostrar, enviar | ✅ Match | Webhook, upsert conversación, INSERT mensaje, buffer/relay; API summary/messages/send; UI lista + mensajes + envío. |
| 3 | Una sola página Chats, filtro por canal | ✅ Corregido | Filtro: Todos, WhatsApp, Instagram, Facebook; channel pasado a summary. |
| 4 | Human override 24h (Chatwoot) | ✅ Match | POST /admin/conversations/{id}/human-override; toggle en UI; eco (outgoing) activa override en webhook. |
| 5 | Multi-tenant, credenciales por tenant | ✅ Match | tenant_id en queries; webhook por token; get_tenant_credential; get_resolved_tenant_id en API. |
| 6 | Vault: agente con get_tenant_credential(OPENAI_API_KEY) | ✅ Corregido | get_agent_executable_for_tenant(tenant_id); ruta chat y buffer_task usan clave por tenant. |
| 7 | Base intacta (agenda, pacientes, chats YCloud, config) | ✅ Match | Cambios aditivos; flujos existentes conservados. |
| 8 | Nicho único (no CRM ventas) | ✅ Match | No se añadió módulo CRM ni selector de nicho. |

---

## 3. Detección de brechas (Drift)

### 3.1 Filtro por canal (spec §5.1, §10.3)

- **Spec:** “**Canal** (WhatsApp, Instagram, Facebook, Todos)” y “filtro por canal (WhatsApp, Instagram, Facebook, etc.)”.
- **Implementado:** Selector con: **Todos**, **WhatsApp (YCloud)**, **Chatwoot** (sin Instagram ni Facebook como opciones).
- **Brecha:** No existen opciones de filtro **Instagram** y **Facebook**. El backend ya soporta `channel` en GET /admin/chats/summary; el frontend no las usa ni muestra.
- **Acción sugerida:** Añadir en ChatsView opciones “Instagram” y “Facebook” en el selector de canal; al elegir una, llamar a `fetchChatsSummary({ channel: 'instagram' })` o `channel: 'facebook'` y filtrar/mezclar la lista unificada por `item.channel` (para Chatwoot) y por fuente para YCloud (solo WhatsApp cuando canal = whatsapp).

### 3.2 Vault para el agente IA (spec §5.2, §10.6 y plan tarea 7)

- **Spec:** “El agente IA use get_tenant_credential(tenant_id, "OPENAI_API_KEY")” y “no depender de env para producción”.
- **Implementado:** En `main.py`, `get_agent_executable()` sigue usando `OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")` y no recibe `tenant_id` ni llama a `get_tenant_credential`.
- **Brecha:** El agente no usa credenciales por tenant; criterio 6 no cumplido.
- **Acción sugerida:** (1) Hacer que la creación del agente tenga acceso a `tenant_id` (p. ej. factory `get_agent_executable(tenant_id)` o agente creado en el contexto de la petición/buffer con tenant). (2) Sustituir uso de env por `await get_tenant_credential(tenant_id, "OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")` al construir el LLM. (3) buffer_task ya recibe `tenant_id`; pasar ese valor al invocar el agente.

### 3.3 Polling (plan tarea 8)

- **Plan:** “Polling lista 10s, mensajes 3s para Chatwoot.”
- **Implementado:** Polling del summary cada **15 s**; no hay polling de mensajes al tener abierta una conversación Chatwoot.
- **Brecha:** Menor: intervalo de lista 15s en lugar de 10s; ausencia de refresco periódico de mensajes (3s).
- **Acción sugerida:** Cambiar intervalo de `fetchChatsSummary` a 10 s; opcionalmente añadir `setInterval` de 3 s para `fetchChatMessages(selectedChatwoot.id)` mientras `selectedChatwoot` no sea null.

---

## 4. Esquemas de datos (spec §6)

- **chat_conversations:** id (UUID), tenant_id, channel, channel_source, provider, external_user_id, external_chatwoot_id, external_account_id, display_name, status, human_override_until, meta, last_message_at, last_message_preview, created_at, updated_at. Índice único (tenant_id, channel, external_user_id).  
  → **Match** con parches 16/16b en db.py.

- **chat_messages (extensión):** conversation_id (nullable), role, content, content_attributes, platform_metadata, platform_message_id; from_number se mantiene.  
  → **Match** con parche 17.

- **credentials:** tenant_id, name, value; índices.  
  → **Match** con parche 18.

---

## 5. Entradas/salidas principales (spec §7)

- POST /admin/chatwoot/webhook → 200, tenant por token, upsert, mensaje, buffer si incoming, eco → override. ✅  
- GET /admin/chats/summary → lista con channel, provider, last_message, is_locked. ✅  
- GET /admin/chats/{id}/messages → mensajes DESC. ✅  
- POST /admin/whatsapp/send → conversation_id, message; enrutado por provider. ✅  
- POST /admin/conversations/{id}/human-override → enabled, 24h/NULL. ✅  
- GET /admin/integrations/chatwoot/config → webhook_path, access_token, api_base. ✅  

---

## 6. Configuración Chatwoot en Settings (spec §5.4)

- URL completa del webhook con token, botón “Copiar”, texto de ayuda.  
- **Match:** ConfigView incluye sección Chatwoot, `fetchChatwootConfig`, URL construida, Copiar e instrucciones.

---

## 7. Lógica no pedida / ruido

- No se detecta lógica extra que contradiga la spec ni módulos ajenos al alcance (p. ej. CRM).  
- Uso de `channel_source` en webhook y en tabla está alineado con el esquema y el flujo Chatwoot.

---

## 8. Resumen del informe

| Resultado | Descripción |
|-----------|-------------|
| ✅ **Match** | Criterios 1, 2, 4, 5, 7, 8; esquemas de datos; entradas/salidas; Config Chatwoot. |
| ⚠️ **Drift menor** | Filtro por canal sin Instagram/Facebook (§3.1); polling 15s y sin polling de mensajes (§3.3). |
| ❌ **Drift** | Vault para el agente: agente no usa get_tenant_credential(OPENAI_API_KEY) (§3.2). |

---

## 9. Acción correctiva (aplicada)

1. **Vault agente:** Implementado en `main.py`: `get_agent_executable(openai_api_key=None)`, `async get_agent_executable_for_tenant(tenant_id)` usando `get_tenant_credential(tenant_id, "OPENAI_API_KEY")`. La ruta de chat YCloud y `buffer_task.process_buffer_task` usan el executor por tenant.
2. **Filtro por canal:** ChatsView con opciones Todos, WhatsApp, Instagram, Facebook; `fetchChatsSummary({ channel })` según filtro; lista unificada y badge por canal (WhatsApp/Instagram/Facebook).
3. **Polling:** Lista summary cada 10 s; mensajes Chatwoot cada 3 s mientras hay conversación abierta (solo loading en carga inicial).

---

*Audit siguiendo `.agent/workflows/audit.md`. SSOT: version_estable_clinicas.spec.md.*
