# 🧠 Dentalogic Brain: Knowledge & Skills Map

Este archivo actúa como el índice maestro de capacidades para los Agentes Autónomos. Define qué Skill utilizar para cada tipo de tarea.

> **Comandos de workflows y skills:** Ver [COMMANDS.md](COMMANDS.md) para la lista completa de comandos (`/specify`, `/plan`, etc.) y triggers de skills. La IA debe usar ese documento en coordinación contigo cuando invoques un comando.

## 🌟 Core Skills (Infraestructura)
| Skill | Trigger Keywords | Uso Principal |
|-------|------------------|---------------|
| **[Backend_Sovereign](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/Backend_Sovereign/SKILL.md)** | `backend`, `fastapi`, `db`, `auth` | Arquitectura, endpoints, seguridad y base de datos. |
| **[Frontend_Nexus](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/Frontend_Nexus/SKILL.md)** | `frontend`, `react`, `ui`, `hooks` | Componentes React, llamadas API, estado y estilos. |
| **[DB_Evolution](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/DB_Evolution/SKILL.md)** | `schema`, `migration`, `sql`, `rag` | Cambios en DB, gestión de vectores y migraciones. |

## 💬 Communication & Integrations
| Skill | Trigger Keywords | Uso Principal |
|-------|------------------|---------------|
| **[Omnichannel_Chat_Operator](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/Omnichannel_Chat_Operator/SKILL.md)** | `chats`, `whatsapp`, `meta`, `msg` | Lógica de mensajería, polling y human handoff. |
| **[Meta_Integration_Diplomat](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/Meta_Integration_Diplomat/SKILL.md)** | `oauth`, `facebook`, `instagram` | Vinculación de cuentas Meta y gestión de tokens. |
| **[TiendaNube_Commerce_Bridge](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/TiendaNube_Commerce_Bridge/SKILL.md)** | `tiendanube`, `products`, `orders` | Sincronización de catálogo y OAuth de e-commerce. |

## 🤖 AI & Onboarding
| Skill | Trigger Keywords | Uso Principal |
|-------|------------------|---------------|
| **[Agent_Configuration_Architect](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/Agent_Configuration_Architect/SKILL.md)** | `agents`, `prompts`, `tools` | Creación y configuración de agentes IA. |
| **[Magic_Onboarding_Orchestrator](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/Magic_Onboarding_Orchestrator/SKILL.md)** | `magic`, `wizard`, `onboarding` | Proceso de "Hacer Magia" y generación de assets. |
| **[Business_Forge_Engineer](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/Business_Forge_Engineer/SKILL.md)** | `forge`, `canvas`, `visuals` | Gestión de assets generados y Fusion Engine. |
| **[Skill_Forge_Master](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/Skill_Forge_Master/SKILL.md)** | `crear skill`, `skill architect` | Generador y arquitecto de nuevas capacidades. |


## 🔒 Security
| Skill | Trigger Keywords | Uso Principal |
|-------|------------------|---------------|
| **[Credential_Vault_Specialist](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/skills/Credential_Vault_Specialist/SKILL.md)** | `credentials`, `vault`, `keys` | Gestión segura de secretos y encriptación. |

---

# 🏗 Sovereign Architecture Context

## 1. Project Identity
**Dentalogic** es un sistema SaaS de Orquestación de IA para Clínicas Odontológicas (Citas, Triaje y Gestión de Pacientes).

Cada clínica posee sus propias credenciales de IA encriptadas en la base de datos y su propia integración con Google Calendar.

**Regla de Oro (Datos):** NUNCA usar `os.getenv("OPENAI_API_KEY")` para lógica de agentes en producción. Siempre usar la credencial correspondiente de la base de datos.

> [!IMPORTANT]
> **REGLA DE SOBERANÍA (BACKEND)**: Es obligatorio incluir el filtro `tenant_id` en todas las consultas (SELECT/INSERT/UPDATE/DELETE). El aislamiento de datos es la barrera legal y técnica inviolable del sistema.

> [!IMPORTANT]
> **REGLA DE SOBERANÍA (FRONTEND)**: Implementar siempre "Aislamiento de Scroll" (`h-screen`, `overflow-hidden` global y `overflow-y-auto` interno) para garantizar que los datos densos no rompan la experiencia de usuario ni se fuguen visualmente fuera de sus contenedores.

## 2. Tech Stack & Standards

### Backend
- **Python 3.10+**: Lenguaje principal
- **FastAPI**: Framework web asíncrono
- **PostgreSQL 14**: Base de datos relacional
- **SQLAlchemy 2.0 / asyncpg**: Acceso asíncrono a datos
- **Google Calendar API**: Sincronización de turnos
- **Redis**: Cache y buffers de mensajes

### Frontend
- **React 18**: Framework UI
- **TypeScript**: Tipado estricto obligatorio
- **Tailwind CSS**: Sistema de estilos
- **Lucide Icons**: Iconografía

### Infrastructure
- **Docker Compose**: Orquestación local
- **EasyPanel**: Deployment cloud
- **WhatsApp Business API (via YCloud)**: Canal de comunicación oficial

## 3. Architecture Map

### Core Services

#### `/orchestrator_service` - API Principal
- **Responsabilidad**: Gestión de turnos, triaje IA, integración con Google Calendar.
- **Archivos Críticos**:
  - `main.py`: FastAPI app y herramientas de la IA (Dental Tools).
  - `admin_routes.py`: Gestión de pacientes, profesionales y configuración de despliegue.
  - `gcal_service.py`: Integración real con Google Calendar (Service Account).
  - `db.py`: Conector de base de datos asíncrono.

#### `/whatsapp_service` - Canal WhatsApp
- **Responsabilidad**: Recepción de webhooks de YCloud, validación de firmas y forwarding al orquestador.
- **Características**: Buffer/Debounce de mensajes en Redis.

#### `/frontend_react` - Dashboard SPA
- **Responsabilidad**: Interfaz para administración de la clínica (Agenda, Pacientes, Credenciales).
- **Vistas Críticas**:
  - `AgendaView.tsx`: Calendario dinámico con soporte de bloques de Google.
  - `DashboardView.tsx`: Estadísticas en tiempo real y alertas de triaje crítico.

## 4. Workflows Disponibles

| Workflow | Descripción |
|----------|-------------|
| **[bug_fix](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/workflows/bug_fix.md)** | Proceso para solucionar errores con aislamiento dental. |
| **[implement](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/workflows/implement.md)** | Ejecución autónoma del plan de implementación. |
| **[verify](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/workflows/verify.md)** | Ciclo de auto-verificación y corrección. |
| **[plan](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/workflows/plan.md)** | Transforma especificaciones en un plan técnico. |
| **[specify](file:///c:/Users/Asus/Downloads/Clinica%20Dental/.agent/workflows/specify.md)** | Genera especificaciones técnicas .spec.md. |

## 5. Available Skills Index

| Skill Name | Trigger | Descripción |
| :--- | :--- | :--- |
| **[AI Behavior Architect](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Prompt_Architect/SKILL.md)** | `Cuando edite system prompts, plantillas de agentes o lógica de RAG.` | Ingeniería de prompts para los Agentes de Ventas, Soporte y Business Forge. |
| **[Agent Configuration Architect](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Agent_Configuration_Architect/SKILL.md)** | `agents, agentes, AI, tools, templates, models, prompts, system prompt, wizard` | Especialista en configuración de agentes de IA: templates, tools, models, prompts y seed data. |
| **[Business Forge Engineer](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Business_Forge_Engineer/SKILL.md)** | `forge, business forge, assets, fusion, canvas, catalog, visuals, images` | Especialista en Business Forge: gestión de assets post-magia, Fusion Engine y generación de visuales. |
| **[Credential Vault Specialist](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Credential_Vault_Specialist/SKILL.md)** | `credentials, credenciales, vault, api keys, tokens, encriptación, settings, sovereign` | Especialista en gestión segura de credenciales multi-tenant: encriptación, scope, categorías y The Vault. |
| **[DB Schema Surgeon](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/DB_Evolution/SKILL.md)** | `v8.0, sql, idempotent, schema, migration, database` | v8.0: Database & Persistence Master. Gestión de evolución segura, parches idempotentes y JSONB clínico. |
| **[Deep Researcher](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Deep_Research/SKILL.md)** | `Antes de usar una librería nueva, al enfrentar un error desconocido, o cuando el usuario diga 'investiga esto'.` | Investiga documentación oficial y valida soluciones en internet antes de implementar. |
| **[EasyPanel DevOps](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/DevOps_EasyPanel/SKILL.md)** | `Cuando toque Dockerfile, docker-compose.yml o variables de entorno.` | Experto en Dockerización, Docker Compose y despliegue en EasyPanel. |
| **[Magic Onboarding Orchestrator](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Magic_Onboarding_Orchestrator/SKILL.md)** | `magia, magic, onboarding, hacer magia, wizard, sse, stream, assets, branding` | Especialista en el proceso 'Hacer Magia': orquestación de agentes IA, SSE streaming y generación de assets de negocio. |
| **[Maintenance Robot Architect](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Maintenance_Robot_Architect/SKILL.md)** | `N/A` | Especialista en la actualización del sistema de auto-migración "Maintenance Robot" en orchestrator_service/db.py. |
| **[Meta Integration Diplomat](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Meta_Integration_Diplomat/SKILL.md)** | `meta, facebook, instagram, whatsapp, oauth, integration, waba, pages` | Especialista en OAuth Meta (Facebook, Instagram, WhatsApp Business) y gestión de activos de negocio. |
| **[Mobile_Adaptation_Architect](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Mobile_Adaptation_Architect/SKILL.md)** | `v8.0, mobile, responsive, isolation, DKG, adaptive` | v8.0: Senior UI/UX Architect. Especialista en Blueprint Universal, DKG y Scroll Isolation. |
| **[Nexus QA Engineer](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Testing_Quality/SKILL.md)** | `Cuando pida crear tests, probar una feature o corregir bugs.` | Especialista en Pytest Asyncio y Vitest para arquitecturas aisladas. |
| **[Nexus UI Architect](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Nexus_UI_Architect/SKILL.md)** | `N/A` | Especialista en Diseño Responsivo (Mobile First / Desktop Adaptive) y UX para Dentalogic. Define el estándar visual y estructural. |
| **[Nexus UI Developer](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Frontend_Nexus/SKILL.md)** | `frontend, react, tsx, componentes, UI, vistas, hooks` | Especialista en React 18, TypeScript, Tailwind CSS y conexión con API multi-tenant. |
| **[Omnichannel Chat Operator](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Omnichannel_Chat_Operator/SKILL.md)** | `chats, conversaciones, mensajes, whatsapp, human override, handoff` | Especialista en gestión de conversaciones vía WhatsApp (YCloud) para Dentalogic. |
| **[Skill Synchronizer](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Skill_Sync/SKILL.md)** | `Después de crear o modificar una skill, o cuando el usuario diga 'sincronizar skills'.` | Lee los metadatos de todas las skills y actualiza el índice en AGENTS.md. |
| **[Skill_Forge_Master](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Skill_Forge_Master/SKILL.md)** | `crear skill, nueva habilidad, skill architect, forge skill, capability, nueva skill` | Arquitecto y generador de Skills. Define, estructura y registra nuevas capacidades para el agente Antigravity. |
| **[Smart Doc Keeper](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Doc_Keeper/SKILL.md)** | `Cuando el usuario diga 'actualiza la doc', 'documenta este cambio' o tras editar código importante.` | Actualiza documentación y skills usando el protocolo 'Non-Destructive Fusion'. Garantiza que el contenido previo se preserve. |
| **[Sovereign Backend Engineer](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Backend_Sovereign/SKILL.md)** | `v8.0, backend, JIT, tenancy, idempotencia, tools` | v8.0: Senior Backend Architect & Python Expert. Lógica JIT v2, multi-tenancy y evolución idempotente. |
| **[Sovereign Code Auditor](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Sovereign_Auditor/SKILL.md)** | `Antes de hacer commit, o cuando pida revisar seguridad o aislamiento.` | Experto en ciberseguridad y cumplimiento del Protocolo de Soberanía Nexus. |
| **[Spec Architect](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Spec_Architect/SKILL.md)** | `Cuando el usuario diga 'crea una especificación', 'planifica esta feature' o use el comando '/specify'.` | Genera y valida archivos de especificación (.spec.md) siguiendo el estándar SDD v2.0. |
| **[Template Transplant Specialist](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/Template_Transplant_Specialist/SKILL.md)** | `N/A` | Extrae y distribuye instrucciones de un system prompt legacy en las capas correctas (Wizard, Tool Config, Sistema Interno). |
| **[TiendaNube Commerce Bridge](file:///C:/Users/Asus/Downloads/Clinica Dental/.agent/skills/TiendaNube_Commerce_Bridge/SKILL.md)** | `tiendanube, tienda nube, e-commerce, products, orders, oauth, catalog, store` | Especialista en integración con Tienda Nube: OAuth, sincronización de catálogo, órdenes y gestión de productos. |

---
