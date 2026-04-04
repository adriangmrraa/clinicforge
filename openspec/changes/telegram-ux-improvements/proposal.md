# Proposal: Telegram UX Improvements

## Intent

Two improvements to the Telegram bot experience: (1) remove cluttering QUICK_ACTIONS buttons from every response — keep only on `/start`, (2) enable Nova to send PDF documents directly in the Telegram chat — both existing patient records and on-demand custom reports with clinic branding.

## Scope

### In Scope
1. **Buttons cleanup** — Remove `reply_markup=QUICK_ACTIONS` from `_process_and_respond` and `_handle_callback`. Keep only in `_handle_start`.
2. **PDF sending via Telegram** — `enviar_pdf_telegram` tool: fetches/generates existing patient digital records as PDF, sends via `send_document()`.
3. **Custom report generation** — `generar_reporte_personalizado` tool: Nova writes analysis content, renders with clinic-branded template (`custom_report.html` extending `base.html`), generates PDF via WeasyPrint, sends to chat.
4. **PDF attachment detection** — `_process_and_respond` detects `[PDF_ATTACHMENT:path|filename]` markers in tool results, sends the file before the text response, strips marker from history.

### Out of Scope
- Sending images/photos from Nova to Telegram
- PDF viewing/preview in web UI (already exists)
- Scheduled/automated report generation
- Report templates beyond the single custom_report.html

## Approach

**Buttons**: Direct removal from 2 send points. Trivial.

**PDF sending**: Marker-based approach. Tools return `[PDF_ATTACHMENT:/path/file.pdf|Display Name.pdf]` in their result string. `telegram_bot.py` detects this pattern in the response text, extracts path + filename, calls `update.effective_chat.send_document(document=open(path,'rb'), filename=name)`, then strips the marker from the text before sending/saving to history.

**Custom reports**: New Jinja2 template `custom_report.html` extends `base.html` (inherits logo, clinic name, A4 styling). Accepts `titulo` and `contenido_html` (free-form HTML that Nova writes). The tool converts Nova's markdown content to HTML sections, renders template, generates PDF via WeasyPrint.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `services/telegram_bot.py` | Modified | Remove QUICK_ACTIONS from responses + PDF attachment detection in `_process_and_respond` |
| `services/nova_tools.py` | Modified | Add `enviar_pdf_telegram` + `generar_reporte_personalizado` tools + implementations |
| `templates/digital_records/custom_report.html` | New | Branded template for free-form reports |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| WeasyPrint not installed | Low | Already used for existing fichas; graceful error message if missing |
| PDF file disk cleanup | Med | Use `/tmp/` for custom reports, existing upload dir for patient records |
| Marker leaks into history | Low | Strip `[PDF_ATTACHMENT:...]` before saving to Redis history |

## Rollback Plan

Revert the commit. Buttons reappear, PDF tools become unrecognized (Nova ignores them). No DB changes needed.

## Success Criteria

- [ ] QUICK_ACTIONS buttons appear ONLY on `/start`, never on regular responses
- [ ] CEO can say "mandame el informe clínico de García" and receive the PDF in Telegram
- [ ] CEO can say "generame un reporte de turnos de abril vs diciembre" and receive a branded PDF
- [ ] PDF markers never appear in the visible text response to the user
