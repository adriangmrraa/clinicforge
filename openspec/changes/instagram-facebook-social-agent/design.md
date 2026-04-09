# Design — Instagram/Facebook Social Agent

## 1. Architecture Overview

Goal: make the existing conversational agent (both Solo and Multi engines) behave correctly when the incoming channel is Instagram DM or Facebook Messenger via Chatwoot, WITHOUT duplicating the engine, WITHOUT adding a new specialist, and WITHOUT regressing WhatsApp behavior.

Core idea: the channel is already known at webhook time (Chatwoot adapter normalizes it). We propagate `channel` down to the prompt builder and inject a **social preamble** (rules + CTA routes + identity) at the top of the system prompt ONLY when `is_social_channel=True`. WhatsApp path stays byte-identical.

```
Chatwoot webhook
      │
      ▼
routes/chat_webhooks.py ── ChatwootAdapter.normalize_payload()
      │                     (channel ∈ {instagram, facebook, whatsapp})
      ▼
chat_conversations.channel (persisted)
      │
      ▼
services/buffer_task.py::_run_ai_for_phone
      │  ├── loads tenant.social_ig_active, social_landings, instagram_handle, facebook_page_id
      │  ├── computes is_social_channel = (channel in {ig,fb}) AND social_ig_active
      │  ├── current_source_channel.set(channel)
      │  └── builds TurnContext(extra={channel, is_social_channel, social_landings, ig_handle, fb_page_id})
      ▼
engine_router.dispatch(ctx)
      │
      ├──► SoloEngine → main.get_agent_executable_for_tenant()
      │         └── build_system_prompt(..., channel, is_social_channel, social_landings, ig_handle, fb_page_id)
      │                  └── if is_social_channel: prepend build_social_preamble(...)
      │                       drop ANTI-MARKDOWN block (Chatwoot renders markdown on IG/FB)
      │
      └──► MultiAgentEngine → agents/graph.run_turn(ctx)
                └── AgentState seeded with channel keys from ctx.extra
                     └── supervisor routes as usual
                          └── specialist._with_tenant_blocks(state)
                               └── if state.is_social_channel: prepend build_social_preamble(...)
```

DENTAL_TOOLS remain unchanged. `book_appointment` and `derivhumano` already honor `current_source_channel`.

---

## 2. Turn Lifecycle (with file:line refs)

1. **Chatwoot POST** → `routes/chat_webhooks.py:23` receives payload.
2. **Normalize** → `services/channels/chatwoot.py:35-40` maps `Channel::Instagram`→`"instagram"`, `Channel::FacebookPage`→`"facebook"`.
3. **Persist** → `routes/chat_webhooks.py:197` writes `chat_conversations.channel`.
4. **Buffer consume** → `services/buffer_task.py` loads the conversation row including the channel (JOIN already exists at line 1296).
5. **Context set** → `services/buffer_task.py:270` calls `current_source_channel.set(channel or "whatsapp")`.
6. **Tenant social fields load** → NEW: in `_run_ai_for_phone` near line 1005 (before `build_system_prompt`) fetch `tenants.social_ig_active, social_landings, instagram_handle, facebook_page_id` (single row already loaded for tenant config — add columns to existing SELECT).
7. **Compute flag** → `is_social_channel = channel in ("instagram","facebook") and bool(tenant.social_ig_active)`.
8. **TurnContext.extra** → inject `{channel, is_social_channel, social_landings, instagram_handle, facebook_page_id}`.
9. **Engine dispatch** via `engine_router.get_engine_for_tenant()`.
10. **Solo path**: `main.get_agent_executable_for_tenant()` passes the 5 new kwargs into `build_system_prompt`. If `is_social_channel`, a `build_social_preamble(...)` string is prepended to the assembled prompt and the WhatsApp ANTI-MARKDOWN block at `main.py:7414` is skipped (wrapped in `if channel == "whatsapp":`).
11. **Multi path**: `agents/graph.py::run_turn` reads `ctx.extra` and seeds new keys in `AgentState`. Each specialist, inside `_with_tenant_blocks(state)` in `agents/specialists.py`, prepends `build_social_preamble(...)` when `state["is_social_channel"]`.
12. **Tool calls** → `book_appointment` reads `current_source_channel` (already supports IG/FB placeholder phone at `buffer_task.py:1796-1823`). `derivhumano` honors channel. No changes.
13. **Response back** → Chatwoot adapter sends reply on the originating channel.

---

## 3. File-Level Changes

### NEW — `orchestrator_service/alembic/versions/040_add_social_ig_fields.py` (~50 LOC)
Adds 4 columns to `tenants`. Revision `040_add_social_ig_fields`, down_revision `039_add_tenant_support_complaints`.

### NEW — `orchestrator_service/services/social_routes.py` (~180 LOC)
CTA routes parser and in-memory registry. Loads from `instagram rutas DraLauraDelgado.md` at startup (best-effort). Exposes `CTARoute` dataclass, `CTA_ROUTES: list[CTARoute]`, `get_route_for_text(text)->Optional[CTARoute]`. Pitches are **hardcoded constants** inside the module (the .md file is used only as documentation source; parser is future-proofing). Drop-in swap to DB source later.

### NEW — `orchestrator_service/services/social_prompt.py` (~120 LOC)
Exposes `build_social_preamble(tenant_id, channel, social_landings, instagram_handle, facebook_page_id, cta_routes)->str`. Pure string builder, no DB calls. Returns the full social preamble text (identity, channel rules, friend-vs-lead heuristics, CTA routes with pitches, forbidden tools list, medical ethics rule).

### MOD — `orchestrator_service/models.py`
`Tenant` class: add 4 column attributes (see §4). ~6 LOC.

### MOD — `orchestrator_service/services/buffer_task.py` (~25 LOC)
- Extend tenant SELECT to include the 4 new columns (near existing tenant load).
- Compute `is_social_channel`.
- Build `TurnContext.extra` dict with the 5 keys.
- When calling the Solo engine directly (legacy path), pass same kwargs into `build_system_prompt`.

### MOD — `orchestrator_service/main.py` (~60 LOC)
- `build_system_prompt(...)` signature adds 5 kwargs with safe defaults (see §4).
- Wrap the ANTI-MARKDOWN block at `main.py:7414` in `if channel == "whatsapp":`.
- At the top of prompt assembly, if `is_social_channel`: `prompt = build_social_preamble(...) + "\n\n" + prompt`.
- `get_agent_executable_for_tenant()` reads the 4 tenant fields (or accepts them as args from buffer_task) and forwards.

### MOD — `orchestrator_service/agents/state.py` (~10 LOC)
`AgentState` TypedDict adds 5 keys: `channel: str`, `is_social_channel: bool`, `social_landings: Optional[dict]`, `instagram_handle: Optional[str]`, `facebook_page_id: Optional[str]`.

### MOD — `orchestrator_service/agents/graph.py` (~15 LOC)
`run_turn(ctx)` reads `ctx.extra.get("channel","whatsapp")` and friends, seeds them into the initial `AgentState`.

### MOD — `orchestrator_service/agents/specialists.py` (~20 LOC)
`_with_tenant_blocks(state)`: after composing the base block, if `state.get("is_social_channel")`, prepend `build_social_preamble(...)`.

### MOD — `orchestrator_service/admin_routes.py` (~40 LOC)
- `PATCH /admin/settings/clinic`: accept optional `social_ig_active`, `social_landings`, `instagram_handle`, `facebook_page_id`.
- `GET /admin/settings/clinic` (or the tenants getter used by ConfigView): return those fields.
- Validate: `social_ig_active` bool, `social_landings` dict or null, handles max 100 chars.

### MOD — `frontend_react/src/views/ConfigView.tsx` (~150 LOC)
New section "Agente de Redes Sociales" in general tab:
- Toggle `social_ig_active`
- Text inputs `instagram_handle`, `facebook_page_id`
- 4 URL inputs mapped to `social_landings` keys: `blanqueamiento`, `implantes`, `lift`, `evaluacion`
- Saves via existing PATCH endpoint.

### MOD — `frontend_react/src/locales/{es,en,fr}.json` (~30 LOC each)
New keys under `config.socialAgent.*`: `title`, `description`, `enabled`, `instagramHandle`, `facebookPageId`, `landings.blanqueamiento`, `landings.implantes`, `landings.lift`, `landings.evaluacion`.

---

## 4. Key Interfaces

### `build_social_preamble`
```python
def build_social_preamble(
    tenant_id: int,
    channel: str,                      # "instagram" | "facebook"
    social_landings: Optional[dict],   # {"blanqueamiento": "https://...", ...}
    instagram_handle: Optional[str],   # "@draLauraDelgado"
    facebook_page_id: Optional[str],   # "DraLauraDelgado"
    cta_routes: list["CTARoute"],      # from social_routes.CTA_ROUTES
) -> str:
    """
    Returns a Spanish (rioplatense) system-prompt preamble that instructs the
    agent on IG/FB-specific behavior: identity, channel rules, friend vs lead
    heuristics, CTA routes with their pitch templates, tool allow-list, and
    medical ethics rule (no diagnosis over DM).
    Pure function, no I/O.
    """
```

### `build_system_prompt` (delta)
```python
def build_system_prompt(
    # ...existing ~47 params...
    channel: str = "whatsapp",
    is_social_channel: bool = False,
    social_landings: Optional[dict] = None,
    instagram_handle: Optional[str] = None,
    facebook_page_id: Optional[str] = None,
) -> str: ...
```
Invariant: `build_system_prompt(channel="whatsapp")` with all new defaults MUST produce a string byte-identical to the pre-change implementation.

### `AgentState` delta
```python
class AgentState(TypedDict, total=False):
    # ...existing...
    channel: str
    is_social_channel: bool
    social_landings: Optional[dict]
    instagram_handle: Optional[str]
    facebook_page_id: Optional[str]
```

### Migration 040 (sketch)
```python
"""add social ig fields to tenants

Revision ID: 040_add_social_ig_fields
Revises: 039_add_tenant_support_complaints
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "040_add_social_ig_fields"
down_revision = "039_add_tenant_support_complaints"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("tenants",
        sa.Column("social_ig_active", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tenants",
        sa.Column("social_landings", postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column("tenants",
        sa.Column("instagram_handle", sa.String(length=100), nullable=True))
    op.add_column("tenants",
        sa.Column("facebook_page_id", sa.String(length=100), nullable=True))

def downgrade():
    op.drop_column("tenants", "facebook_page_id")
    op.drop_column("tenants", "instagram_handle")
    op.drop_column("tenants", "social_landings")
    op.drop_column("tenants", "social_ig_active")
```

---

## 5. CTA Routes Parser

```python
# orchestrator_service/services/social_routes.py
from dataclasses import dataclass
from typing import Optional
import unicodedata, re, logging

log = logging.getLogger(__name__)

@dataclass(frozen=True)
class CTARoute:
    group: str                  # "blanqueamiento" | "implantes" | "lift" | "evaluacion"
    keywords: tuple[str, ...]   # accent-insensitive, lowercase
    pitch_template: str         # agent says this, ends with direct booking trigger
    landing_url_key: str        # key into tenant.social_landings

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii","ignore").decode().lower()
    return re.sub(r"\s+"," ", s).strip()

CTA_ROUTES: list[CTARoute] = [
    CTARoute(
        group="blanqueamiento",
        keywords=("blanqueamiento","blanquear","dientes blancos","whitening"),
        pitch_template=(
            "El blanqueamiento profesional que hace la Dra. Laura es con protocolo clínico "
            "controlado — resultados reales sin sensibilidad. Si querés, agendamos tu turno "
            "ahora mismo: decime qué día te queda cómodo y lo coordino."
        ),
        landing_url_key="blanqueamiento",
    ),
    CTARoute(
        group="implantes",
        keywords=("implante","implantes","perdí un diente","perdi un diente","me falta un diente"),
        pitch_template=(
            "Los implantes son una de las especialidades de la Dra. Laura. Por ética no puedo "
            "darte un diagnóstico por acá, pero sí puedo agendarte una evaluación presencial "
            "para que veas opciones reales. ¿Qué día de esta semana te sirve?"
        ),
        landing_url_key="implantes",
    ),
    CTARoute(
        group="lift",
        keywords=("lift","sonrisa gingival","encia","encía","diseño de sonrisa","diseno de sonrisa"),
        pitch_template=(
            "El LIFT es un procedimiento estético específico de la Dra. Laura para rediseñar "
            "la sonrisa. Lo ideal es una evaluación presencial para ver si sos candidato. "
            "¿Te agendo un turno?"
        ),
        landing_url_key="lift",
    ),
    CTARoute(
        group="evaluacion",
        keywords=("evaluacion","evaluación","cirugia","cirugía","consulta","turno","precio","cuanto sale","cuánto sale"),
        pitch_template=(
            "Te puedo agendar una evaluación con la Dra. Laura — ahí resolvés todo presencial. "
            "¿Qué día te queda cómodo?"
        ),
        landing_url_key="evaluacion",
    ),
]

def get_route_for_text(text: str) -> Optional[CTARoute]:
    if not text:
        return None
    t = _norm(text)
    for route in CTA_ROUTES:
        for kw in route.keywords:
            if kw in t:
                return route
    return None

def load_routes_from_file(path: str) -> list[CTARoute]:
    """Future hook: parse the .md file for route overrides. Graceful failure."""
    try:
        # MVP: return hardcoded CTA_ROUTES. Future: parse path.
        return CTA_ROUTES
    except Exception as e:
        log.warning("social_routes: failed to parse %s: %s — using defaults", path, e)
        return CTA_ROUTES
```

**Key rewrite note**: every pitch ends with a **direct booking trigger** (e.g. "¿Qué día te queda cómodo?"), NOT "¿te paso el WhatsApp?" — the agent books directly on IG/FB.

---

## 6. Friend Detection (Prompt-Only)

Pure prompt engineering. No runtime classifier. The social preamble contains a block like:

```
DETECCIÓN AMIGO vs LEAD:
Señales de AMIGO (conversación personal, no comercial):
- Te tutea con familiaridad ("che", "boluda", nombres propios)
- Menciona eventos personales compartidos ("el asado del sábado", "tu viaje")
- No menciona ningún tratamiento, precio, turno, síntoma, ni servicio dental
- Saludo informal sin intención comercial ("hola bella", "cómo andás")

Señales de LEAD (potencial paciente):
- Pregunta por tratamientos, precios, turnos, servicios
- Describe un síntoma o problema bucal
- Pide información sobre la clínica o la doctora
- Usa lenguaje formal o neutro

REGLA DE OVERRIDE: Si detectás CUALQUIER keyword de ruta CTA (blanqueamiento,
implantes, LIFT, evaluación, turno, precio, cirugía…) → SIEMPRE tratás como LEAD,
ignorás señales de amigo.

EN DUDA → tratás como LEAD (más seguro comercialmente).

RESPUESTA A AMIGO (flexible, adaptate al mensaje):
- Breve, casual, cálido, en voseo
- Base sugerida: "Hola, ¿cómo vas? Dame un rato y te respondo con más tiempo"
- Podés variarla según el mensaje entrante — no repitas siempre igual
- NO llamás ninguna tool
- NO agendás
- NO activás human_override
- NO derivás
```

---

## 7. Tool Allow-List on Social Mode

MVP is prompt-level only (runtime filtering deferred). Hardcoded in the preamble:

```
HERRAMIENTAS PROHIBIDAS EN ESTE CANAL (IG/FB):
- NUNCA llames a `triage_urgency` — por ética no hacemos triage médico por DM.
  Si detectás urgencia, usá `derivhumano` con el contexto.

HERRAMIENTAS PERMITIDAS:
- list_services, list_professionals, check_availability, confirm_slot,
  book_appointment, reschedule_appointment, cancel_appointment,
  list_my_appointments, save_patient_email, save_patient_anamnesis,
  get_patient_anamnesis, verify_payment_receipt, derivhumano
```

The Solo agent and every Multi specialist still receive the same `DENTAL_TOOLS` list; the ban is enforced via the prompt. Future hardening: filter `DENTAL_TOOLS` at `get_agent_executable_for_tenant` when `is_social_channel=True`.

---

## 8. Testing Strategy

### Unit
- `tests/test_social_routes.py` — keyword matching (accents, case, partial), priority order, `get_route_for_text` returns None when no match, unicode normalization.
- `tests/test_social_prompt.py` — `build_social_preamble` produces expected sections; missing landings handled; None handles handled.
- `tests/test_build_system_prompt_regression.py` — `build_system_prompt(channel="whatsapp")` output hash matches golden file (regression guarantee).
- `tests/test_migration_040.py` — upgrade/downgrade round-trip on a temp DB.
- `tests/test_agent_state_channel.py` — `AgentState` accepts new keys, `run_turn` propagates them from `ctx.extra`.

### Integration
- `tests/test_ig_flow_solo.py` — simulated IG webhook → buffer → Solo engine → asserts preamble present in prompt sent to OpenAI (mock OpenAI client, capture messages).
- `tests/test_ig_flow_multi.py` — same but Multi engine; assert `_with_tenant_blocks` prepended preamble.
- `tests/test_whatsapp_regression.py` — WhatsApp webhook → asserts preamble ABSENT and ANTI-MARKDOWN block PRESENT.
- `tests/test_social_flag_toggle.py` — channel=instagram + `social_ig_active=false` → preamble ABSENT (flag gates).
- `tests/test_friend_vs_lead_override.py` — messages with friend signals + CTA keyword → agent still treats as lead (verified via prompt injection assertion, not LLM output).

### Manual E2E
1. Toggle flag from ConfigView, reload.
2. Send IG DM "hola bella cómo andás" → expect friendly casual reply, no tools.
3. Send IG DM "quiero blanqueamiento" → expect pitch + booking trigger.
4. Send IG DM "me caí y se me rompió un diente" → expect `derivhumano` (no `triage_urgency`).
5. Send WhatsApp "hola" → expect unchanged greeting (regression check).

---

## 9. Rollout Plan

1. **Merge + deploy with flag OFF** — migration 040 runs, all tenants default `social_ig_active=false`. Zero behavior change.
2. **UI available** — CEO can see the new ConfigView section.
3. **Pilot tenant** (Dra. Laura) — CEO fills identity + landings + toggles ON.
4. **48h monitoring** — watch `agent_turn_log` for IG/FB turns, check Chatwoot conversations manually for quality, monitor error rate.
5. **Rollback path** — toggle flag OFF from UI; no redeploy needed. Preamble immediately stops being injected on next turn (tenant row is read per turn in buffer_task).
6. **Emergency rollback** — revert commits + `alembic downgrade -1` (columns are nullable/defaulted, safe to drop).

---

## 10. Forward Compatibility

- **CTA routes as drop-in swap**: `load_routes_from_file(path)` wraps the source. Replacing with `load_routes_from_db(tenant_id)` later is a single-line change at the import site in `social_prompt.build_social_preamble`.
- **`social_landings` JSONB**: free-form dict, extensible to N landing types without migration.
- **Preamble builder takes dict inputs**: no DB calls inside, pure function — trivial to unit test and to move into a tenant-level override system later.
- **Future specialist**: if we decide to add a dedicated `SocialAgent` specialist later, the state keys are already propagated; only supervisor routing needs a rule.
- **Runtime tool filtering**: when we move from prompt-level to runtime allow-list, the hook is `get_agent_executable_for_tenant(is_social_channel=...)` — signature already carries the flag.

---

## 11. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| WhatsApp regression from shared prompt path | Medium | High | Golden-file prompt hash test; default kwargs guarantee byte-identical output |
| Agent ignores `triage_urgency` ban (prompt-only) | Low | Medium | Strong "NUNCA" wording + explicit fallback to `derivhumano`; runtime filter planned |
| Chatwoot renders markdown unexpectedly on some IG clients | Low | Low | ANTI-MARKDOWN dropped only on social; fallback: re-enable via flag |
| Friend detection misclassifies lead as friend → lost sale | Medium | Medium | "Uncertain → lead" default + CTA keyword override rule |
| CTA pitch file not found at startup | Low | Low | `load_routes_from_file` returns hardcoded defaults on failure |
| Migration 040 conflict with parallel SDD pack | Low | High | `ls alembic/versions/` before writing; confirmed head is 039 |
| Tenant forgets to fill `social_landings` | Medium | Low | Preamble handles None gracefully; pitch still works without URL |
| Multi engine state missing channel keys (old state snapshots) | Low | Medium | `total=False` on TypedDict; `.get()` with defaults everywhere |

---

## 12. Definition of Done

- [ ] Migration 040 applied on dev + staging; `alembic current` shows `040_add_social_ig_fields`.
- [ ] `tenants` table has 4 new columns, defaults correct.
- [ ] `social_routes.py` module exists with `CTA_ROUTES` and `get_route_for_text`.
- [ ] `social_prompt.build_social_preamble` implemented and unit-tested.
- [ ] `build_system_prompt` accepts 5 new kwargs; golden-file regression test passes on WhatsApp path.
- [ ] ANTI-MARKDOWN block gated by `channel == "whatsapp"`.
- [ ] `AgentState` TypedDict extended; `graph.run_turn` propagates from `ctx.extra`.
- [ ] `specialists._with_tenant_blocks` prepends preamble when `is_social_channel`.
- [ ] `buffer_task` computes `is_social_channel`, loads new tenant fields, injects into `TurnContext.extra`.
- [ ] `admin_routes` PATCH/GET expose the 4 fields; validation in place.
- [ ] `ConfigView` shows "Agente de Redes Sociales" section; CEO can toggle + save.
- [ ] i18n keys added to `es.json`, `en.json`, `fr.json`.
- [ ] Unit tests green: parser, prompt builder, state propagation, migration.
- [ ] Integration tests green: IG Solo flow, IG Multi flow, WhatsApp regression, flag toggle, friend vs lead override.
- [ ] Manual E2E checklist (§8) executed on pilot tenant with flag ON.
- [ ] 48h monitoring window clean (no new errors in `agent_turn_log`).
- [ ] Rollback procedure validated (toggle OFF → preamble stops injecting within 1 turn).
