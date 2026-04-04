# Design: Telegram UX Improvements

## Architecture

```
CEO message → Nova (gpt-5.4-mini) → tool chain → tool result
                                                      ↓
                                            contains [PDF_ATTACHMENT:...]?
                                            ├── YES → send_document() + strip marker + send text
                                            └── NO  → send text only (no buttons)
```

### PDF Generation Flow
```
generar_reporte_personalizado(titulo, contenido_html)
  ├── resolve_logo_data_uri(tenant_id) → logo base64
  ├── db.fetchrow(tenants) → clinic_name, address
  ├── Jinja2: custom_report.html(data={clinic, titulo, contenido, fecha})
  ├── WeasyPrint: html → /tmp/nova_reports/{uuid}.pdf
  └── return "[PDF_ATTACHMENT:/tmp/nova_reports/{uuid}.pdf|{titulo}.pdf]\n..."

enviar_pdf_telegram(patient_id, tipo_documento)
  ├── db.fetchrow(patient_digital_records) → html_content, pdf_path
  ├── if !pdf_path → generate_pdf(html_content, output_path)
  └── return "[PDF_ATTACHMENT:{pdf_path}|{title}.pdf]\n..."
```

### Marker Detection in telegram_bot.py
```python
PDF_MARKER_RE = re.compile(r'\[PDF_ATTACHMENT:([^|]+)\|([^\]]+)\]')

# In _process_and_respond, BEFORE sending text:
matches = PDF_MARKER_RE.findall(response_text)
for pdf_path, filename in matches:
    if os.path.exists(pdf_path):
        with open(pdf_path, 'rb') as f:
            await update.effective_chat.send_document(document=f, filename=filename)

# Strip markers from text
clean_text = PDF_MARKER_RE.sub('', response_text).strip()
```

## Implementation Details

### S1: Buttons cleanup
```python
# _process_and_respond — line ~619
# BEFORE:
reply_markup=QUICK_ACTIONS if is_last else None
# AFTER:
reply_markup=None

# _handle_callback — line ~1099
# BEFORE:
reply_markup=QUICK_ACTIONS if is_last else None
# AFTER:
reply_markup=None
```

### S2: enviar_pdf_telegram tool schema (flat Realtime format)
```python
{
    "type": "function",
    "name": "enviar_pdf_telegram",
    "description": "Envía un PDF de ficha digital existente por el chat. Busca el registro en patient_digital_records, genera el PDF si no existe, y lo envía como archivo adjunto.",
    "parameters": {
        "type": "object",
        "properties": {
            "patient_id": {"type": "integer", "description": "ID del paciente"},
            "record_id": {"type": "string", "description": "UUID del registro específico (opcional)"},
            "tipo_documento": {
                "type": "string",
                "enum": ["clinical_report", "post_surgery", "odontogram_art", "authorization_request"],
                "description": "Tipo de documento a buscar (opcional — si no se especifica, busca el más reciente)"
            }
        }
    }
}
```

### S3: generar_reporte_personalizado tool schema
```python
{
    "type": "function",
    "name": "generar_reporte_personalizado",
    "description": "Genera un PDF personalizado con el análisis/reporte que escribiste. El PDF tiene logo y branding de la clínica. Usá esto después de recopilar datos y escribir tu análisis como HTML.",
    "parameters": {
        "type": "object",
        "properties": {
            "titulo": {"type": "string", "description": "Título del reporte (ej: 'Comparativa Abril vs Diciembre 2025')"},
            "contenido": {"type": "string", "description": "Contenido del reporte en HTML. Usá <h2>, <table>, <ul>, <p>, <b> para formatear."},
            "subtitulo": {"type": "string", "description": "Subtítulo o descripción breve (opcional)"}
        },
        "required": ["titulo", "contenido"]
    }
}
```

### S4: _process_and_respond PDF detection
Insert BEFORE the `safe_text = _safe_html(response_text)` line:

```python
# Detect and send PDF attachments
pdf_matches = PDF_MARKER_RE.findall(response_text)
for pdf_path, pdf_filename in pdf_matches:
    try:
        if os.path.exists(pdf_path):
            with open(pdf_path, 'rb') as pdf_file:
                await update.effective_chat.send_document(
                    document=pdf_file,
                    filename=pdf_filename,
                    caption=f"📄 {pdf_filename}",
                )
        else:
            logger.warning(f"PDF not found: {pdf_path}")
    except Exception as e:
        logger.error(f"Failed to send PDF: {e}")

# Strip markers from text before display and history
response_text = PDF_MARKER_RE.sub('', response_text).strip()
```

### S5: custom_report.html template
```html
{% extends "base.html" %}
{% block content %}
<div class="report-header">
    <h1>{{ data.titulo }}</h1>
    {% if data.subtitulo %}<p class="subtitle">{{ data.subtitulo }}</p>{% endif %}
    <p class="date">{{ data.fecha }}</p>
</div>
<div class="report-content">
    {{ data.contenido | safe }}
</div>
<div class="report-footer">
    <p>Generado por Nova AI — {{ data.clinic.name }}</p>
</div>
{% endblock %}
```

With additional CSS for tables inside report-content:
```css
.report-content table { width: 100%; border-collapse: collapse; margin: 1em 0; }
.report-content th, .report-content td { border: 1px solid #cbd5e0; padding: 8px 12px; text-align: left; }
.report-content th { background: #edf2f7; font-weight: bold; }
.report-content tr:nth-child(even) { background: #f7fafc; }
```

### S6: Prompt additions in nova_prompt.py

Two insertion points:
1. After FICHAS DIGITALES section → full REPORTES PDF block
2. Inside page=telegram section → short reinforcement

## File Changes

| File | Changes |
|------|---------|
| `services/telegram_bot.py` | Remove QUICK_ACTIONS from responses, add PDF_MARKER_RE detection |
| `services/nova_tools.py` | Add 2 tool schemas + 2 implementations |
| `services/nova_prompt.py` | Add S6 prompt blocks (reportes + telegram reinforcement) |
| `templates/digital_records/custom_report.html` | New template extending base.html |

## Dependencies
- WeasyPrint (already installed — used by existing fichas)
- Jinja2 (already installed)
- No new Python packages
- No DB migrations needed
