# Tasks: Telegram UX Improvements

## Phase 1: Quick Fix — Buttons (Batch 1)

- [ ] **T1.1** Remove `reply_markup=QUICK_ACTIONS` from `_process_and_respond()` in telegram_bot.py — set to `reply_markup=None`
- [ ] **T1.2** Remove `reply_markup=QUICK_ACTIONS` from `_handle_callback()` in telegram_bot.py — set to `reply_markup=None`
- [ ] **T1.3** Verify `_handle_start()` still has `reply_markup=QUICK_ACTIONS` (keep as-is)

## Phase 2: PDF Infrastructure (Batch 2)

- [ ] **T2.1** Add `PDF_MARKER_RE = re.compile(r'\[PDF_ATTACHMENT:([^|]+)\|([^\]]+)\]')` constant in telegram_bot.py
- [ ] **T2.2** Add PDF detection + `send_document()` logic in `_process_and_respond()` — extract matches, send files, strip markers from text before display and history saving
- [ ] **T2.3** Create `custom_report.html` template in `orchestrator_service/templates/digital_records/` — extends base.html, accepts titulo/subtitulo/contenido/fecha, includes table/list CSS for report-content area
- [ ] **T2.4** Import `os` in telegram_bot.py if not already imported (needed for `os.path.exists` in PDF detection)

## Phase 3: Nova Tools — PDF Sending (Batch 3)

- [ ] **T3.1** Add `enviar_pdf_telegram` schema to NOVA_TOOLS_SCHEMA (flat format) — params: patient_id, record_id, tipo_documento
- [ ] **T3.2** Implement `_enviar_pdf_telegram(args, tenant_id)` — query patient_digital_records, generate PDF if missing via `generate_pdf()`, return `[PDF_ATTACHMENT:path|filename]` marker
- [ ] **T3.3** Add `generar_reporte_personalizado` schema to NOVA_TOOLS_SCHEMA (flat format) — params: titulo (required), contenido (required), subtitulo (optional)
- [ ] **T3.4** Implement `_generar_reporte_personalizado(args, tenant_id)` — load tenant data + logo, render custom_report.html with Jinja2, generate PDF with WeasyPrint in /tmp/nova_reports/, return marker
- [ ] **T3.5** Wire both tools in `execute_nova_tool` dispatcher — add elif branches

## Phase 4: System Prompt — Reportes Proactivos (Batch 4)

- [ ] **T4.1** Add REPORTES PDF PERSONALIZADOS block to nova_prompt.py — flujo de generación (5 pasos), formato HTML, tipos de reportes (7 ejemplos), reglas de proactividad
- [ ] **T4.2** Add refuerzo REPORTES PDF al bloque page=telegram en nova_prompt.py
- [ ] **T4.3** Add instrucciones de enviar_pdf_telegram al bloque FICHAS DIGITALES existente — "mandame la ficha" → enviar_pdf_telegram, encadenamiento generar+enviar
