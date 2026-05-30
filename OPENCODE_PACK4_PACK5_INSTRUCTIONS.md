# Opencode — Cerrar el batch SDD: pack derivation + pack support-complaints

**Modo de trabajo**: Mode B (shared worktree). Vamos a usar UN solo worktree principal `clinicforge` para evitar el desastre de cuatro terminales en paralelo que ya pasó. Solo un agente escribe a la vez. La coordinación entre agentes va por Engram.

**Skill obligatoria**: leé y aplicá la skill `agent-coordination` (en `~/.claude/skills/agent-coordination/SKILL.md`). Esa skill define las reglas de Mode B con el lock vía Engram. Este documento es task-specific; la skill es la fuente de verdad para el protocolo.

**Idioma**: español rioplatense para todo lo que ve el usuario y comentarios en código. Inglés para mensajes de commit.

---

## Estado real actual (verificado 2026-04-08)

**Main HEAD**: `7ad9eb6 merge: clinic-holidays-integration (pack 4/7) — UI surfacing complete`

**Migration chain en código**: `034 → 035 → 036 → 037`

**Packs ya merged a main**:

| # | Pack | Migration | Merge SHA |
|---|------|-----------|-----------|
| 0 | clinic-bot-name-editable | 033 | (cherry-picks pre-sesión) |
| 1 | insurance-coverage-by-treatment | 034 | `fdda0cf` |
| 2 | clinic-payment-financing-config | 035 | `9bac1b9` |
| 3 | clinic-special-conditions | 036 | `05b8919` |
| 4 | treatment-pre-post-instructions-enhancement | 037 | `0c821ca` |
| 5 | clinic-holidays-integration | (frontend only) | `7ad9eb6` |

**Packs PENDIENTES** (los dos que tenés que cerrar):

| # | Pack | Migration esperada | Status |
|---|------|--------------------|--------|
| 6 | **derivation-escalation-fallback** | 038 | NOT STARTED (había trabajo abandonado en worktrees borrados — backup en `.abandoned_clinicforge-sdd*.patch`) |
| 7 | **clinic-support-complaints-config** | 039 | NOT STARTED |

---

## Worktrees actuales (limpio post-cleanup)

```
clinicforge/   → main, worktree único
```

Los worktrees `clinicforge-sdd` y `clinicforge-sdd-2` fueron eliminados (causaban conflictos cuando varios agentes los usaban en paralelo). **No los recrees**. Trabajamos todo desde `clinicforge/` con feature branches.

Hay dos archivos `.abandoned_clinicforge-sdd*.patch` en la raíz con el WIP rescatado de los worktrees borrados. Inspeccionalos antes de empezar pack derivation — pueden tener trabajo útil.

---

## Paso 0 — Cargar contexto desde Engram (OBLIGATORIO antes de tocar código)

```
1. mem_search "agent-coordination" → leer la skill (o leer ~/.claude/skills/agent-coordination/SKILL.md directamente)
2. mem_search "sdd/batch-2026-04-08/resume-point" project=clinicforge
   → mem_get_observation(id) para el contenido completo (no la preview)
3. mem_search "sdd/derivation-escalation-fallback" project=clinicforge
   → leer cada resultado con mem_get_observation
4. mem_search "sdd/clinic-support-complaints-config" project=clinicforge
   → leer cada resultado
5. mem_search "worktree/clinicforge/lock" project=clinicforge
   → si hay un ACQUIRED activo de otro agente, STOP y avisar al usuario
```

---

## Paso 1 — Inspeccionar los patches abandonados (pack derivation)

```bash
cd "C:/Users/Asus/Documents/estabilizacion/Laura Delgado/clinicforge"
cat .abandoned_clinicforge-sdd.patch | head -50
cat .abandoned_clinicforge-sdd-2.patch | head -50
```

Si el contenido es relevante para el pack derivation, podés aplicarlo como punto de partida con `git apply --3way .abandoned_clinicforge-sdd.patch` (después de crear la rama). Si parece basura o trabajo a medio terminar que es más fácil rehacer, descartá los patches y empezá de cero.

---

## Paso 2 — Verificar git y main

```bash
cd "C:/Users/Asus/Documents/estabilizacion/Laura Delgado/clinicforge"
git fetch origin
git log --oneline -10                    # main HEAD esperado: 7ad9eb6 o posterior
git status --short                         # debe estar limpio (excepto archivos untracked normales)
git worktree list                          # solo debe haber UN worktree: clinicforge en main
git branch -a | grep -v remotes            # ver ramas locales
```

Si `git worktree list` muestra más de uno, **STOP** y avisá al usuario — no hay que crear worktrees adicionales en este flujo.

---

## Paso 3 — Adquirir el lock del worktree (Mode B)

Antes de crear cualquier rama o tocar archivos:

```
mem_save:
  topic_key: "worktree/clinicforge/lock"
  type: "pattern"
  project: "clinicforge"
  content: |
    Action: ACQUIRED
    Agent: opencode-main
    Branch: main → about to create feat/clinic-derivation-escalation-fallback
    Timestamp: <ISO actual>
    Expected duration: ~1-2 horas (pack derivation completo)
    Reason: Iniciando pack 6/7 derivation-escalation-fallback en Mode B
```

Una vez liberado el lock al final del pack, hacés otro `mem_save` con `Action: RELEASED` (mismo topic_key, sobrescribe).

---

## Paso 4 — Cerrar pack derivation-escalation-fallback (migración 038)

### 4.1 Crear rama feature DESDE main
```bash
cd "C:/Users/Asus/Documents/estabilizacion/Laura Delgado/clinicforge"
git checkout main
git pull origin main
git checkout -b feat/clinic-derivation-escalation-fallback
```

### 4.2 Leer las specs del pack
```bash
ls openspec/changes/derivation-escalation-fallback/
# proposal.md, spec.md, design.md, tasks.md
```

Leelos COMPLETOS antes de tocar código. Son tu fuente de verdad.

### 4.3 Implementar las 5 phases con commits separados

Pattern obligatorio (idéntico a packs 1-3, ya validado):

| Phase | Commit message |
|-------|---------------|
| 1 | `feat(derivation-fallback): migration 038 + ORM (phase 1)` |
| 2 | `feat(derivation-fallback): Pydantic + update_tenant + GET SELECT (phase 2)` |
| 3 | `feat(derivation-fallback): _format_<area> + buffer_task wiring (phase 3)` |
| 4 | `feat(derivation-fallback): ClinicsView section + i18n (phase 4)` |
| 5 | `test(derivation-fallback): E2E scenarios + backward-compat (phase 5)` |

**Detalles de cada phase**: ver la sección "Pattern obligatorio por pack" en este mismo archivo (más abajo).

### 4.4 Después de cada phase
- `git push origin feat/clinic-derivation-escalation-fallback`
- `mem_save` a `sdd/derivation-escalation-fallback/apply-progress` con la nueva SHA y el status del phase

### 4.5 Merge a main
```bash
git checkout main
git pull origin main
git merge --no-ff feat/clinic-derivation-escalation-fallback -m "merge: derivation-escalation-fallback (pack 6/7) — 5 phases complete"
git push origin main
```

Si hay conflicts, resolverlos con "keep both" en zonas aditivas (kwargs de `build_system_prompt`, field blocks de `update_tenant`, etc).

### 4.6 Cleanup post-merge
```bash
git branch -d feat/clinic-derivation-escalation-fallback   # solo si merged
```

### 4.7 Actualizar engram
- `sdd/derivation-escalation-fallback/apply-progress` → status COMPLETE + merged
- `sdd/batch-2026-04-08/resume-point` → mover el pack a la tabla de "merged"

---

## Paso 5 — Cerrar pack clinic-support-complaints-config (migración 039)

**Esperar a que pack 6 esté mergeado en main antes de empezar este**. La migración 039 depende de 038. Si arrancás en paralelo, vas a tener que rebasar al final.

Repetir EXACTAMENTE el mismo flujo del Paso 4 con:
- Branch: `feat/clinic-support-complaints-config`
- Migration: 039 (`down_revision = "038"`)
- Specs: `openspec/changes/clinic-support-complaints-config/`
- Merge message: `merge: clinic-support-complaints-config (pack 7/7) — batch SDD complete`

---

## Paso 6 — Liberar el lock al terminar TODO

```
mem_save:
  topic_key: "worktree/clinicforge/lock"
  content: |
    Action: RELEASED
    Agent: opencode-main
    Timestamp: <ISO>
    Reason: Pack 6 y pack 7 completos. Batch SDD cerrado.
```

Y un `mem_save` final del resume point con los 7 packs (0-6) marcados como ✅ merged.

---

## Pattern obligatorio por pack (referencia detallada)

### Phase 1 — Infraestructura (migration + ORM)
- `orchestrator_service/alembic/versions/0XX_<nombre>.py`
  - `revision = "0XX"`, `down_revision = "<previous>"`
  - `upgrade()` con idempotency guard (`inspector.get_columns("tenants")` antes de cada `add_column`)
  - `downgrade()` con drop en orden inverso, try/except defensivo
- `orchestrator_service/models.py` — agregar columnas al ORM `Tenant` (o tabla que toque)
- Commit: `feat(<area>): migration 0XX + ORM (phase 1)`

### Phase 2 — Backend (Pydantic + endpoint + GET SELECT)
- Si necesita validación estructurada: agregar Pydantic model con `model_config = {"extra": "forbid"}` cerca de los otros models en `admin_routes.py`
- Field blocks en `update_tenant()`: pattern de presence-check → validation → `params.append` → `updates.append`
- Extender SELECT en `get_tenants()` para incluir las nuevas columnas
- Si hay JSONB nuevos: agregarlos al loop de `json.loads` defensivo
- Commit: `feat(<area>): Pydantic + update_tenant + GET SELECT (phase 2)`

### Phase 3 — Formatter + prompt wiring
- `_format_<area>()` en `orchestrator_service/main.py` cerca de los otros `_format_*`
- Función devuelve `""` cuando no hay config (backward-compat obligatorio)
- JSONB-as-string defensivo: `if isinstance(val, str): val = json.loads(val)`
- En `build_system_prompt`: agregar kwargs con defaults backward-compat (o pasar string pre-formateado, decidir según el pack)
- Inyectar en el f-string del prompt después de los bloques existentes (`{bank_section}`, `{payment_section}`, `{special_conditions_block}`, etc)
- Extender SELECT de `tenant_row` en `orchestrator_service/services/buffer_task.py`
- Pasar los nuevos valores a `build_system_prompt`
- Commit: `feat(<area>): _format_<area> + buffer_task wiring (phase 3)`

### Phase 4 — Frontend
- `frontend_react/src/views/ClinicsView.tsx`:
  - Interface `Clinica` con los nuevos campos
  - `formData` state inicial
  - `handleOpenModal` (edit + reset)
  - `handleSubmit` payload
  - Bloque JSX collapsible con dark mode (`bg-white/[0.04] border-white/[0.08]`)
- i18n keys en LOS TRES locales: `frontend_react/src/locales/{es,en,fr}.json`
- Commit: `feat(<area>): ClinicsView <section> + i18n (phase 4)`

### Phase 5 — Tests E2E
- `tests/test_<area>.py`:
  - Unit tests del formatter (devuelve `""` con defaults, backward-compat)
  - Integration tests con `build_system_prompt` (bloque inyectado/no inyectado)
  - Scenarios de `spec.md` (prompt-contract tests, NO LLM real)
  - Backward-compat regression
- **NO ejecutar pytest** — el usuario los corre manualmente
- Commit: `test(<area>): E2E scenarios + backward-compat (phase 5)`

---

## Reglas no negociables (de la skill agent-coordination)

1. **NO ejecutar `pytest`** sin permiso explícito del usuario
2. **NO ejecutar `npm run build` ni `npm install`** sin permiso
3. **NO usar git destructivo** (`reset --hard`, `push --force`, `branch -D` de no-merged) sin permiso
4. **NO usar `--no-verify`**
5. **NO añadir `Co-Authored-By: Claude`** ni attribution de IA
6. **Conventional commits**: `feat(scope):`, `fix(scope):`, `test(scope):`, `docs(scope):`, `refactor(scope):`
7. **Español rioplatense** para textos visibles y comentarios. **Inglés** para commit messages
8. **UN agente escribe a la vez** (Mode B). Adquirir el lock antes, liberarlo después
9. **Save a engram después de cada phase**, no solo al final

---

## Checklist final antes de cerrar la sesión

- [ ] Pack 6 (derivation) mergeado a main con push exitoso
- [ ] Pack 7 (support-complaints) mergeado a main con push exitoso
- [ ] `sdd/derivation-escalation-fallback/apply-progress` guardado en engram
- [ ] `sdd/clinic-support-complaints-config/apply-progress` guardado en engram
- [ ] `sdd/batch-2026-04-08/resume-point` actualizado: TODOS los packs ✅ merged
- [ ] `worktree/clinicforge/lock` liberado (`Action: RELEASED`)
- [ ] `git log --oneline -15` en main muestra los dos merge commits nuevos
- [ ] Resumen al usuario: SHAs, files touched, próxima acción (alembic upgrade head en prod)
- [ ] Archivos `.abandoned_clinicforge-sdd*.patch` eliminados si su contenido ya está en main
