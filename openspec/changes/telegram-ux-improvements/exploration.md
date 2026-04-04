# Exploration: Telegram UX Improvements

## Feature 1: QUICK_ACTIONS Buttons Only on First Message

### Current State
- `QUICK_ACTIONS` (Agenda/Pendientes/Resumen/Ayuda) is an `InlineKeyboardMarkup` sent as `reply_markup` on EVERY Nova response (last chunk) — both in `_process_and_respond` (line 619) and `_handle_callback` (line 1099).
- Also sent on `/start` (line 1019) — this is the only correct place.
- The buttons clutter every response and make the chat look like a menu-driven bot instead of an intelligent assistant.

### Approach
**Simple removal** — Remove `reply_markup=QUICK_ACTIONS` from `_process_and_respond` and `_handle_callback`. Keep it ONLY in `_handle_start`. The CEO already knows what Nova can do — she doesn't need buttons on every message.

- Files: `telegram_bot.py` — lines 619, 1099
- Effort: **Low** (2 line changes)

---

## Feature 2: Nova Sends PDFs via Telegram

### Current State

**Existing PDF infrastructure:**
- `generar_ficha_digital` tool: Generates 4 types of clinical documents (clinical_report, post_surgery, odontogram_art, authorization_request)
- Uses Jinja2 templates from `orchestrator_service/templates/digital_records/` (base.html + 4 type templates)
- Templates include clinic branding: logo via `resolve_logo_data_uri(tenant_id)`, clinic name in header
- PDF generation via WeasyPrint: `generate_pdf(html_content, output_path)` — async wrapper over `generate_pdf_sync`
- Records saved to `patient_digital_records` table with `html_content` and `pdf_path`
- `enviar_ficha_digital` tool: Sends existing PDFs via email — generates PDF if `pdf_path` is empty

**What's missing:**
- No way to send a PDF file directly to a Telegram chat (only email sending exists)
- No "custom report" tool — only the 4 predefined clinical document types exist
- python-telegram-bot supports `send_document(document=bytes_or_InputFile, filename="report.pdf")` natively

### Affected Areas
- `orchestrator_service/services/telegram_bot.py` — needs `send_document` capability
- `orchestrator_service/services/nova_tools.py` — needs 2 new tools
- `orchestrator_service/services/digital_records_service.py` — needs a generic report generator
- `orchestrator_service/templates/digital_records/` — needs a `custom_report.html` template

### Sub-Features

#### 2A: Send Existing PDFs via Telegram
A new tool `enviar_pdf_telegram` that:
1. Finds the patient's digital record (by record_id or most recent)
2. Generates the PDF if `pdf_path` is empty (using existing `generate_pdf`)
3. Reads the PDF bytes
4. Calls `update.effective_chat.send_document(document=pdf_bytes, filename="Informe - Paciente.pdf")`

**Challenge**: The tool needs access to the Telegram `update` object to call `send_document`. Currently tools only get `(args, tenant_id, user_role, user_id)`. Two approaches:

| Approach | Pros | Cons |
|----------|------|------|
| A. Return PDF path in tool result, telegram_bot.py detects and sends | No tool signature changes, clean separation | Needs special handling in _process_with_nova |
| B. Pass a callback/send function via args | Direct control | Couples tools to Telegram transport |

**Recommendation**: Approach A — the tool returns a special marker like `[PDF_ATTACHMENT:/path/to/file.pdf|Filename.pdf]` and `_process_and_respond` in telegram_bot.py detects this pattern and calls `send_document` before sending the text response.

#### 2B: On-Demand Custom Reports
A new tool `generar_reporte_personalizado` that:
1. Receives a `titulo` and `instrucciones` (e.g., "cruzá datos de abril vs diciembre")
2. Uses Nova's own intelligence to query data (via CRUD tools) and generate analysis
3. Assembles HTML with clinic branding using a new `custom_report.html` template
4. Generates PDF via WeasyPrint
5. Returns the PDF path marker for Telegram sending

**The content flow**:
```
CEO asks for report → Nova chains tools to gather data → Nova calls generar_reporte_personalizado
with the gathered data as content → Tool renders HTML template → WeasyPrint → PDF → send to Telegram
```

The custom_report.html template extends base.html (gets logo, clinic name, styling) but has a free-form content area where Nova can write markdown/HTML analysis.

### Risks
- WeasyPrint may not be installed in production (it's optional). Need to handle gracefully.
- PDF files need cleanup (disk space) — should use temp files or existing upload directory.
- Large PDFs from complex reports could be slow to generate.
- The `[PDF_ATTACHMENT:...]` marker approach needs to not leak into conversation history.

### Ready for Proposal
Yes — both features are well-defined. Feature 1 is trivial. Feature 2 has clear architecture with the marker approach + new template.
