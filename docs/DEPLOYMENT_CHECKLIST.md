# ClinicForge — Deployment Checklist

This checklist is for production deployments on EasyPanel (or any container-based host).
Focus: minimizing impact on active patient conversations during restarts.

---

## Before deploying

1. [ ] Run tests locally: `pytest`
2. [ ] Check active conversations: look at Redis for `convstate:*` keys
   ```bash
   redis-cli keys "convstate:*" | wc -l
   ```
3. [ ] If changing prompts/FAQs: note that ALL active conversations will see new behavior immediately (there is no per-conversation rollout guard)
4. [ ] If changing tools or endpoints: verify backward compatibility with existing conversations in-flight
5. [ ] If adding an Alembic migration: confirm head revision matches expectations
   ```bash
   ls orchestrator_service/alembic/versions/ | tail -5
   ```
6. [ ] Verify no orphaned active locks in Redis before deploy (optional, sanity check)
   ```bash
   redis-cli keys "active_task:*"
   ```

---

## During deployment

7. [ ] EasyPanel will restart the container — expect 30–60 s downtime
8. [ ] On startup, `recover_orphaned_buffers()` will automatically re-process any buffered
       messages that were interrupted mid-flight by the previous restart
9. [ ] Slot locks (`confirm_slot`, 120 s TTL) may expire during restart — patients who were
       mid-booking may need to re-confirm their slot
10. [ ] The `active_task` lock TTL is now 60 s (down from `60 + buffer_ttl`). Any conversation
        that was processing at restart will be unlocked within 60 s and will resume normally

---

## After deployment

11. [ ] Check logs for errors:
    ```bash
    docker logs clinicforge-orchestrator --tail 100
    ```
    Look for `recover_orphaned_buffers` output — it will report how many buffers were
    re-queued vs deleted
12. [ ] Verify a test message works end-to-end (use sandbox tenant if available)
13. [ ] If the app started a drain on shutdown, confirm logs show:
    ```
    Shutting down — waiting up to 15s for active tasks...
    ```
    If you need more drain time, set `SHUTDOWN_DRAIN_TIMEOUT=30` in the environment

---

## Environment variables related to deployment behaviour

| Variable | Default | Purpose |
|----------|---------|---------|
| `SHUTDOWN_DRAIN_TIMEOUT` | `15` | Seconds to wait for active buffer tasks on graceful shutdown |

---

## Rollback procedure

If the deployment breaks conversations:

1. Revert the image tag in EasyPanel to the previous version
2. Redis state is shared — buffers and locks persist across rollbacks
3. After rollback, `recover_orphaned_buffers()` will run again on startup and handle any
   messages that arrived during the broken window
