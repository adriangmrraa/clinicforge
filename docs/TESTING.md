# Testing Guide — ClinicForge

## Running unit tests locally

```bash
# From the repo root
pytest

# Run a specific test file
pytest tests/test_chatwoot_whatsapp_no_regression.py -v

# Run with output printed (useful for debugging)
pytest tests/ -s -v

# Run only tests matching a keyword
pytest -k "whatsapp" -v
```

The `pytest.ini` configuration sets `asyncio_mode = auto` and adds `orchestrator_service/` to `sys.path`. Tests import from `orchestrator_service` directly (no Docker required for unit tests).

---

## Seeding the sandbox tenant

The sandbox tenant (`id = 99999`) is a safe, isolated tenant used for manual QA and automated smoke tests. It never sends real messages to WhatsApp/YCloud thanks to the sandbox suppression guard in `response_sender.py` (see below).

```bash
# Requires POSTGRES_DSN pointing to a running database
export POSTGRES_DSN="postgresql://user:pass@localhost:5432/clinicforge"
python scripts/seed_sandbox_tenant.py
```

This script is **idempotent** — safe to run multiple times. It skips creation if tenant `99999` already exists.

What it creates:
- Tenant record with `config = {"sandbox": true}` (triggers message suppression)
- One test professional: `Dr. Test Sandbox`
- One test treatment type: `Consulta General Test` (code: `consulta_test`, 30 min)

---

## Running the smoke test

The smoke test verifies the four most critical production endpoints immediately after a deploy.

```bash
export SMOKE_TEST_URL="https://your-production-url.com"
export ADMIN_TOKEN="your-admin-token"
python scripts/smoke_test.py
```

Exits `0` on full pass, `1` on any failure. Suitable for CI/CD pipelines.

**Checks performed:**
1. `GET /health/live` — process is up
2. `GET /health/ready` — database and Redis are connected
3. `GET /admin/ai-engine/health` — both AI engines (solo + multi) are responsive
4. `POST /auth/login` with empty body — endpoint exists (expects `422 Unprocessable Entity`)

---

## Golden files — how they work and when to update them

Golden files are text snapshots of deterministic function outputs stored in `tests/fixtures/`. They allow byte-identical regression testing: if the output of `build_system_prompt` changes unexpectedly, the test fails immediately.

### Current golden files

| File | Channel | Generator |
|------|---------|-----------|
| `golden_prompt_whatsapp.txt` | WhatsApp | `tests/generate_golden_prompt.py` |
| `golden_prompt_instagram.txt` | Instagram DM | `tests/generate_golden_prompts_social.py` |
| `golden_prompt_facebook.txt` | Facebook DM | `tests/generate_golden_prompts_social.py` |
| `golden_prompt_telegram.txt` | Telegram | `tests/generate_golden_prompts_social.py` |

### When to update golden files

Update golden files when you **intentionally** change `build_system_prompt` output (new feature, prompt wording update, new section). Do NOT update them to "fix a failing test" without first understanding WHY the output changed.

```bash
# Regenerate WhatsApp baseline
pytest tests/generate_golden_prompt.py -s

# Regenerate IG + FB + Telegram baselines
pytest tests/generate_golden_prompts_social.py -s
```

After regenerating, commit the updated golden files alongside the code change that caused the diff. This makes the change intentional and reviewable in the PR.

### Stub files

The IG/FB/Telegram golden files are currently stubs (`STUB:NEEDS_GENERATION`). Run the generator scripts above to replace them with real baselines before writing regression tests against those channels.

---

## Sandbox phone suppression

When the sandbox tenant (`config.sandbox = true`) is active, `response_sender.py` logs messages at `INFO` level but does **not** send them to WhatsApp, YCloud, Chatwoot, or Meta. This prevents sandbox test scenarios from reaching real patients.

This guard applies to ALL providers: `chatwoot`, `ycloud`, `meta_direct`.

---

## Testing checklist before deploying to production

Run through this checklist before every production deploy:

### Code quality
- [ ] All tests pass locally: `pytest`
- [ ] No new `# type: ignore` or `# noqa` added without justification
- [ ] New endpoints include `Depends(verify_admin_token)` or `Depends(get_current_user)`
- [ ] Every SQL query includes `WHERE tenant_id = $x` (Sovereignty Protocol)

### Migrations
- [ ] Confirm actual Alembic head: `ls orchestrator_service/alembic/versions/` (don't trust docs)
- [ ] New migration has both `upgrade()` and `downgrade()`
- [ ] `models.py` updated alongside the migration
- [ ] Migration tested locally: `alembic upgrade head` runs without errors

### AI prompt changes
- [ ] If `build_system_prompt` changed, regenerate golden files and verify diff is intentional
- [ ] WhatsApp non-regression test passes: `pytest tests/test_chatwoot_whatsapp_no_regression.py`
- [ ] Social prompt tests pass: `pytest tests/test_build_system_prompt_social.py`

### Smoke test (post-deploy)
- [ ] Set `SMOKE_TEST_URL` to production URL
- [ ] Run `python scripts/smoke_test.py` — all 4 checks must pass
- [ ] Check Sentry/logs for new errors in first 5 minutes after deploy

### Multi-tenant safety
- [ ] Sandbox tenant seeded if doing QA on prod DB: `python scripts/seed_sandbox_tenant.py`
- [ ] No hardcoded tenant IDs in new code (except `SANDBOX_TENANT_ID = 99999` in scripts)
- [ ] No model names hardcoded (use `model_resolver.resolve_tenant_model(tenant_id)`)
