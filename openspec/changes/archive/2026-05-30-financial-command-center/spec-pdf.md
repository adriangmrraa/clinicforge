# Spec: Financial Command Center — PDF de Liquidaciones

---

## 1. Template HTML

### PDF-01: Ubicación y estructura

**Archivo:** `orchestrator_service/templates/liquidation/liquidation_statement.html`

El template usa Jinja2 para renderizar el documento de liquidación profesional.

### PDF-02: Datos de entrada

```python
template.render(
    clinic=clinic_data,        # name, address, phone, logo_url, ui_language
    professional=prof_data,    # full_name, specialty, license_number
    period=period_data,        # start (date), end (date), label (e.g. "Marzo 2026")
    summary=summary_data,      # total_sessions, total_billed, total_paid, total_pending, commission_pct, commission_amount, payout_amount
    treatment_groups=groups,   # [{patient_name, treatment_name, sessions: [{date, description, amount, payment_status}], total}]
    payouts=payouts_list,      # [{date, amount, payment_method, reference_number, notes}]
    generated_at=datetime,     # Fecha de generación del PDF
    status=status_string,      # "Borrador" | "Generada" | "Aprobada" | "Pagada"
    notes=notes_text,          # Notas adicionales (opcional)
)
```

### PDF-03: Diseño del PDF

```
┌──────────────────────────────────────────────────────────────┐
│  [LOGO]  Clínica Dra. Laura Delgado                          │
│          Av. Corrientes 1234, CABA | Tel: (011) 4567-8900   │
│                                                              │
│  ═══════════════════════════════════════════════════════════ │
│  LIQUIDACIÓN DE HONORARIOS PROFESIONALES                     │
│  ═══════════════════════════════════════════════════════════ │
│                                                              │
│  Profesional: Dra. María Pérez                               │
│  Especialidad: Odontología General                           │
│  Período: 1 de marzo — 31 de marzo de 2026                   │
│  Estado: APROBADA                                            │
│  Generado: 3 de abril de 2026 a las 10:00                    │
│                                                              │
│  ─────────────────────────────────────────────────────────── │
│  RESUMEN                                                     │
│  ─────────────────────────────────────────────────────────── │
│                                                              │
│  Total de sesiones:                    45                    │
│  Total facturado:                      $500.000,00           │
│  Total cobrado:                        $450.000,00           │
│  Total pendiente:                      $ 50.000,00           │
│                                                              │
│  Comisión aplicada:                    30%                   │
│  Monto de comisión:                    $150.000,00           │
│  ─────────────────────────────────────────────────────────── │
│  NETO A LIQUIDAR:                      $150.000,00           │
│  ─────────────────────────────────────────────────────────── │
│                                                              │
│  ─────────────────────────────────────────────────────────── │
│  DETALLE DE SESIONES                                         │
│  ─────────────────────────────────────────────────────────── │
│                                                              │
│  Paciente: Lucas Puig                                        │
│  ┌────────────┬──────────────────┬──────────┬──────────────┐│
│  │ Fecha      │ Tratamiento      │ Monto    │ Estado       ││
│  ├────────────┼──────────────────┼──────────┼──────────────┤│
│  │ 15/03/2026 │ Consulta inicial │ $50.000  │ ✅ Pagado    ││
│  │ 22/03/2026 │ Colocación       │ $150.000 │ ✅ Pagado    ││
│  ├────────────┼──────────────────┼──────────┼──────────────┤│
│  │ Subtotal   │                  │ $200.000 │              ││
│  └────────────┴──────────────────┴──────────┴──────────────┘│
│                                                              │
│  Paciente: María López                                       │
│  ┌────────────┬──────────────────┬──────────┬──────────────┐│
│  │ Fecha      │ Tratamiento      │ Monto    │ Estado       ││
│  ├────────────┼──────────────────┼──────────┼──────────────┤│
│  │ 10/03/2026 │ Preparación      │ $50.000  │ ✅ Pagado    ││
│  │ 17/03/2026 │ Colocación       │ $90.000  │ ⏳ Pendiente ││
│  ├────────────┼──────────────────┼──────────┼──────────────┤│
│  │ Subtotal   │                  │ $140.000 │              ││
│  └────────────┴──────────────────┴──────────┴──────────────┘│
│                                                              │
│  ─────────────────────────────────────────────────────────── │
│  HISTORIAL DE PAGOS                                          │
│  ─────────────────────────────────────────────────────────── │
│                                                              │
│  03/04/2026  Transferencia  $150.000  Ref: TXN-12345       │
│                                                              │
│  ─────────────────────────────────────────────────────────── │
│                                                              │
│  Firma clínica                        Firma profesional      │
│  ___________________________          _____________________  │
│                                                              │
│  Documento generado automáticamente por {clinic_name}        │
│  3/4/2026 a las 10:00                                      │
└──────────────────────────────────────────────────────────────┘
```

### PDF-04: Estilos CSS (inline para WeasyPrint)

```css
/* Formato A4 */
@page {
    size: A4;
    margin: 2cm 1.5cm;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 11px;
    color: #1a1a1a;
    line-height: 1.5;
}

/* Header */
.header {
    display: flex;
    align-items: center;
    margin-bottom: 20px;
    padding-bottom: 15px;
    border-bottom: 2px solid #1a1a1a;
}

.logo {
    max-height: 60px;
    margin-right: 15px;
}

.clinic-info h1 {
    font-size: 18px;
    font-weight: 700;
    margin: 0;
}

.clinic-info p {
    font-size: 10px;
    color: #666;
    margin: 2px 0;
}

/* Título del documento */
.doc-title {
    text-align: center;
    font-size: 16px;
    font-weight: 700;
    margin: 20px 0;
    padding: 10px;
    background: #f5f5f5;
    border-radius: 4px;
}

/* Tablas */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0;
}

th, td {
    padding: 6px 10px;
    border: 1px solid #ddd;
    text-align: left;
    font-size: 10px;
}

th {
    background: #f9f9f9;
    font-weight: 600;
}

/* Fila de totales */
.total-row {
    font-weight: 700;
    background: #f5f5f5;
}

/* Resumen */
.summary-table td {
    padding: 4px 10px;
    border: none;
}

.summary-table .label {
    text-align: right;
    color: #555;
}

.summary-table .value {
    text-align: right;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
}

/* Neto a liquidar */
.net-row {
    font-size: 14px;
    font-weight: 700;
    background: #1a1a1a;
    color: white;
}

.net-row td {
    border: none;
    padding: 10px;
}

/* Secciones */
.section-title {
    font-size: 13px;
    font-weight: 700;
    margin: 20px 0 10px;
    padding-bottom: 5px;
    border-bottom: 1px solid #ccc;
}

/* Paciente group */
.patient-group {
    margin: 15px 0;
    page-break-inside: avoid;
}

.patient-name {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 5px;
}

/* Pagos */
.payout-item {
    display: flex;
    gap: 15px;
    padding: 5px 0;
    border-bottom: 1px solid #eee;
    font-size: 10px;
}

/* Footer */
.footer {
    margin-top: 40px;
    padding-top: 15px;
    border-top: 1px solid #ccc;
    font-size: 9px;
    color: #888;
    text-align: center;
}

.signatures {
    display: flex;
    justify-content: space-between;
    margin-top: 50px;
    page-break-inside: avoid;
}

.signature-line {
    width: 40%;
    border-top: 1px solid #333;
    padding-top: 5px;
    text-align: center;
    font-size: 10px;
}

/* Status badge */
.status-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 10px;
    font-weight: 600;
}

.status-draft { background: #e0e0e0; color: #555; }
.status-generated { background: #e3f2fd; color: #1565c0; }
.status-approved { background: #e8f5e9; color: #2e7d32; }
.status-paid { background: #1b5e20; color: white; }
```

---

## 2. Endpoint de Generación

### PDF-05: GET /admin/liquidations/{id}/pdf

Genera y sirve el PDF de una liquidación.

**Lógica:**

1. **Verificar ownership:** `liquidation_record.tenant_id == current_tenant_id`
2. **Check caché:** Si el PDF ya existe en disco y el status no cambió desde la última generación, servir el archivo cacheado
   - Path de caché: `/app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf`
   - Invalidación: al cambiar status de la liquidación, eliminar el archivo cacheado
3. **Recopilar datos:**
   ```python
   async def gather_liquidation_data(pool, liquidation_id: int, tenant_id: int) -> dict:
       # 1. Liquidation record
       record = await pool.fetchrow(
           "SELECT * FROM liquidation_records WHERE id = $1 AND tenant_id = $2",
           liquidation_id, tenant_id
       )

       # 2. Professional
       prof = await pool.fetchrow(
           "SELECT id, first_name, last_name, specialty, license_number FROM professionals WHERE id = $1",
           record["professional_id"]
       )

       # 3. Clinic
       clinic = await pool.fetchrow(
           "SELECT id, clinic_name, address, phone, logo_url, config->>'ui_language' as ui_language FROM tenants WHERE id = $1",
           tenant_id
       )

       # 4. Treatment groups (reusar query de analytics_service.get_professionals_liquidation)
       groups = await pool.fetch("""
           SELECT ... -- misma query que get_professionals_liquidation para el período
       """, tenant_id, record["period_start"], record["period_end"], record["professional_id"])

       # 5. Payouts
       payouts = await pool.fetch("""
           SELECT * FROM professional_payouts
           WHERE liquidation_id = $1 AND tenant_id = $2
           ORDER BY payment_date DESC
       """, liquidation_id, tenant_id)

       return { "record": record, "professional": prof, "clinic": clinic, "groups": groups, "payouts": payouts }
   ```

4. **Render template:**
   ```python
   env = Jinja2Environment(loader=FileSystemLoader("templates/liquidation"))
   template = env.get_template("liquidation_statement.html")
   html = template.render(**data)
   ```

5. **Generar PDF con WeasyPrint (en thread executor):**
   ```python
   import asyncio
   from weasyprint import HTML

   async def generate_pdf(html: str, output_path: str):
       loop = asyncio.get_event_loop()
       await loop.run_in_executor(None, lambda: HTML(string=html).write_pdf(output_path))
   ```

6. **Guardar en caché:** Escribir en `/app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf`

7. **Retornar FileResponse:**
   ```python
   from fastapi.responses import FileResponse

   filename = f"Liquidacion_{prof_name}_{period_label}.pdf".replace(" ", "_")
   return FileResponse(
       path=output_path,
       media_type="application/pdf",
       filename=filename
   )
   ```

**Fallback:** Si WeasyPrint no está disponible o falla:
- Retornar HTML response con `Content-Type: text/html`
- Log de error: `logger.warning("PDF generation failed, returning HTML fallback")`

---

## 3. Endpoint de Envío por Email

### PDF-06: POST /admin/liquidations/{id}/send-email

Envía el PDF de liquidación por email al profesional.

**Request:**
```json
{
  "to_email": "profesional@email.com"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Liquidación enviada a profesional@email.com"
}
```

**Lógica:**

1. **Validar email:** Si no se proporciona `to_email`, usar el email del profesional desde la tabla `professionals` o `users`
2. **Generar PDF:** Llamar la lógica de generación (reusar, no duplicar código)
3. **Enviar email:**
   ```python
   def send_liquidation_email(
       self,
       to_email: str,
       pdf_path: str,
       professional_name: str,
       clinic_name: str,
       period_label: str,
       payout_amount: float,
       language: str = "es"
   ):
       """Envía liquidación por email con PDF adjunto."""
       subject = f"Liquidación {period_label} — {clinic_name}"

       # Body HTML según idioma del template
       body = render_email_template(
           "liquidation_email.html",
           professional_name=professional_name,
           clinic_name=clinic_name,
           period_label=period_label,
           payout_amount=payout_amount,
           language=language
       )

       # Send via existing email_service
       self.send_email(
           to=to_email,
           subject=subject,
           html_body=body,
           attachments=[pdf_path]
       )
   ```

4. **Template de email (`templates/liquidation/liquidation_email.html`):**
   ```html
   <p>Hola {professional_name},</p>
   <p>Te adjuntamos tu liquidación correspondiente al período {period_label}.</p>
   <p><strong>Monto a liquidar: ${payout_amount:,.2f}</strong></p>
   <p>Si tenés alguna consulta, no dudes en comunicarte con la administración de {clinic_name}.</p>
   <p>Saludos,<br>Equipo de {clinic_name}</p>
   ```

5. **Log de envío:** Registrar en `notes` de la liquidación:
   ```json
   {
     "action": "email_sent",
     "to": "profesional@email.com",
     "by": "ceo@clinic.com",
     "at": "2026-04-03T10:00:00Z"
   }
   ```

---

## 4. Caché de PDFs

### PDF-07: Estrategia de caché

| Evento | Acción |
|--------|--------|
| Generar PDF por primera vez | Crear archivo en `/app/uploads/liquidations/{tenant_id}/{id}.pdf` |
| Generar PDF nuevamente (sin cambios) | Servir archivo existente |
| Cambiar status de liquidación | Eliminar archivo cacheado |
| Actualizar notas de liquidación | Eliminar archivo cacheado |
| Registrar payout | Eliminar archivo cacheado |

**Función de invalidación:**
```python
async def invalidate_liquidation_pdf(tenant_id: int, liquidation_id: int):
    pdf_path = f"/app/uploads/liquidations/{tenant_id}/{liquidation_id}.pdf"
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
```

**Llamar en:**
- `update_liquidation_status()` (EP-FC-05)
- `create_payout()` (EP-FC-06)
- Cualquier PATCH a la liquidación

---

## 5. Criterios de Aceptación

| # | Criterio | Verificación |
|---|----------|-------------|
| AC-PDF-01 | PDF se genera con datos correctos | Generar PDF → verificar montos, profesional, período |
| AC-PDF-02 | PDF usa idioma de la clínica (ui_language) | Clínica con ui_language='en' → PDF en inglés |
| AC-PDF-03 | PDF se cachea en disco | Generar 2 veces → segunda vez es instantánea |
| AC-PDF-04 | Caché se invalida al cambiar status | Cambiar status → generar PDF → nuevo archivo |
| AC-PDF-05 | Email se envía con PDF adjunto | Enviar email → verificar recepción con attachment |
| AC-PDF-06 | Email usa idioma de la clínica | Clínica con ui_language='fr' → email en francés |
| AC-PDF-07 | Fallback a HTML si PDF falla | Simular fallo de WeasyPrint → recibir HTML |
| AC-PDF-08 | Formato A4 profesional | Abrir PDF → verificar dimensiones y márgenes |
| AC-PDF-09 | Logo de clínica incluido | PDF generado → logo visible en header |
| AC-PDF-10 | Líneas de firma incluidas | PDF generado → espacio para firma clínica y profesional |
