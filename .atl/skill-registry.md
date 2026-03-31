# Skill Registry — ClinicForge

Generated: 2026-03-31 (updated with project skills)

## User Skills

| Skill | Trigger | Source |
|-------|---------|--------|
| judgment-day | "judgment day", "dual review", "doble review", "juzgar" | ~/.claude/skills/judgment-day |
| branch-pr | Creating a PR, preparing changes for review | ~/.claude/skills/branch-pr |
| issue-creation | Creating a GitHub issue, reporting a bug | ~/.claude/skills/issue-creation |
| go-testing | Writing Go tests, using teatest | ~/.claude/skills/go-testing |
| skill-creator | Creating new AI skills | ~/.claude/skills/skill-creator |

## SDD Skills (auto-loaded by orchestrator)

sdd-init, sdd-explore, sdd-propose, sdd-spec, sdd-design, sdd-tasks, sdd-apply, sdd-verify, sdd-archive

## Project Skills (.agent/skills/)

| Skill | Scope | Trigger Context |
|-------|-------|-----------------|
| Agent_Configuration_Architect | AGENTS | agents, AI tools, system prompt, wizard |
| Backend_Sovereign | BACKEND | backend, tenancy, alembic, bff, tools |
| Business_Forge_Engineer | FORGE | forge, assets, canvas, catalog, visuals |
| Credential_Vault_Specialist | SECURITY | credentials, vault, api keys, tokens |
| DB_Evolution | DATABASE | sql, alembic, schema, migration, orm, models |
| Deep_Research | GLOBAL | new library, unknown error, "investiga esto" |
| DevOps_EasyPanel | DEVOPS | Dockerfile, docker-compose, env vars |
| Doc_Keeper | MAINTENANCE | "actualiza la doc", "documenta este cambio" |
| Frontend_Nexus | FRONTEND | frontend, react, tsx, componentes, UI, hooks |
| Magic_Onboarding_Orchestrator | MAGIC | magia, onboarding, wizard, sse, branding |
| Maintenance_Robot_Architect | DB | alembic, migrations, database schema |
| Meta_Integration_Diplomat | INTEGRATIONS | meta, facebook, instagram, whatsapp, oauth |
| Mobile_Adaptation_Architect | FRONTEND | mobile, responsive, isolation, adaptive |
| Nexus_UI_Architect | FRONTEND | responsive design, mobile first |
| Omnichannel_Chat_Operator | CHATS | chats, conversaciones, whatsapp, handoff |
| Prompt_Architect | AI_CORE | system prompts, agent templates, RAG |
| Secure_Credential_Vault | SECURITY | credential management protocol |
| Skill_Forge_Master | META | crear skill, nueva habilidad, skill architect |
| Skill_Sync | SYSTEM | sync skills after creation/modification |
| Sovereign_Auditor | SECURITY | commit review, security audit, isolation |
| Spec_Architect | PLANNING | "crea especificación", "planifica feature" |
| Subsystem_Documentation_Architect | DOCS | documentar funcionalidad, reverse engineering |
| Template_Transplant_Specialist | LEGACY | legacy system prompt extraction |
| Testing_Quality | QA | crear tests, probar feature, corregir bugs |
| TiendaNube_Commerce_Bridge | ECOMMERCE | tiendanube, e-commerce, products, orders |

## Project Conventions

| File | Purpose |
|------|---------|
| CLAUDE.md (project) | ClinicForge architecture, rules, patterns |
| CLAUDE.md (workspace) | Estabilizacion workspace conventions |
| CLAUDE.md (user) | Global user preferences, personality, tools |

## Compact Rules

### branch-pr
- Every PR MUST link an approved issue
- Every PR MUST have exactly one `type:*` label
- Automated checks must pass before merge

### issue-creation
- MUST use a template (bug report or feature request)
- Every issue gets `status:needs-review` on creation
- Maintainer MUST add `status:approved` before any PR

### judgment-day
- Launch two independent blind judge sub-agents in parallel
- Synthesize findings, apply fixes, re-judge until both pass
- Escalate after 2 iterations if still failing

### ClinicForge Project Rules
- Multi-tenant: every SQL query MUST include `WHERE tenant_id = $x` (from JWT, never request params)
- Auth: `Depends(verify_admin_token)` or `Depends(get_current_user)` on all admin routes
- i18n: all text via `t('key')`, add to es.json, en.json, fr.json
- DB changes: always Alembic migrations, never raw SQL
- Frontend: dark mode only, scroll isolation, BFF proxy pattern
- Python: FastAPI async, asyncpg for queries, SQLAlchemy for models
- React: strict TypeScript, Tailwind CSS, Lucide icons, axios via api/axios.ts
