# Proposal: Análisis de múltiples adjuntos (imágenes + PDF) con resumen LLM

## Intent

Extender el sistema actual de clasificación de imágenes para manejar múltiples adjuntos (hasta 10 imágenes + 5 PDFs) que llegan sin texto. El sistema debe:
1. Analizar cada附件 (imagen o PDF) usando Vision API
2. Clasificar como pago vs documento clínico
3. Guardar todos los adjuntos en "Archivos" del paciente (`patient_documents`)
4. Generar un resumen LLM del contenido para mostrar en la sección "Resumen" de la ficha
5. Usar el resumen en documentos generados con IA posteriormente

## Scope

### In Scope
- Procesamiento por lotes de imágenes (hasta 10 por mensaje)
- Análisis de PDFs usando Vision API
- Clasificación de cada附件 individual (payment_receipt o clinical)
- Guardado en `patient_documents` → Pestaña "Archivos" del paciente
- Generación de resumen LLM desde análisis de Vision/PDF
- Almacenamiento del resumen en `patient_documents.source_details.llm_summary`
- Mostrar resumen en sección "Resumen" (bajo odontograma, formato rectangular formal)
- Integración con documentos generados por IA (usar resumen en templates)

### Out of Scope
- OCR de PDFs (solo análisis visual con Vision)
- Extracción de datos estructurados
- Comparación de imágenes (antes/después)
- Nueva pestaña en UI (agregar a resumen existente)

## Approach

1. **Extender `vision_service.py`**: Agregar `analyze_pdf_url()` y `analyze_attachments_batch()`
2. **Enriquecer `image_classifier.py`**: Usar resultado de Vision para clasificar
3. **Modificar `buffer_task.py`**: Procesar todos los medios, no solo el último
4. **Agregar campo de resumen**: Extender `patient_documents.source_details` con `llm_summary`

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `services/vision_service.py` | Modificado | Agregar analyze_pdf, batch processing (10 img + 5 pdf) |
| `services/image_classifier.py` | Modificado | Usar vision_result para clasificación, incluir PDF |
| `services/buffer_task.py` | Modificado | Loop sobre todos los media (no solo 1) |
| `patient_documents` table | Modificado | Ya tiene source_details, agregar campo `llm_summary` en JSONB |
| Frontend: PatientDetailView | Modificado | Mostrar resumen en sección "Resumen" (bajo odontograma) |
| Doc generation (IA) | Modificado | Usar `llm_summary` en templates de documentos |

## UI/UX Specification

### Resumen Section (Frontend)
- **Ubicación**: Pestaña "Resumen" del paciente, debajo del odontograma
- **Formato**: Tarjeta rectangular, formato formal similar a documentos de ficha
- **Visual**: 
  - Borde sutil, fondo blanco/gris claro
  - Encabezado: "Análisis de Adjuntos" o similar
  - Contenido: resumen texto legible, estructurado
  - Fecha del análisis
  - Cantidad de archivos analizados

### Archivos Section
- Todos los adjuntos van a "Archivos" del paciente (ya existente)
- Clasificación visible: icono de pago vs clínico

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Costo API (múltiples llamadas Vision) | Medium | Limitar a 10 imágenes, cachear resultados |
| PDFs muy grandes | Low | Límite de tamaño (5MB), fallback a texto |
| Timeout en procesamiento | Medium | Async queue, no bloquear respuesta |

## Rollback Plan

- Revertir cambios en `buffer_task.py` (solo último media)
- Eliminar columna `llm_summary` de `patient_documents`
- Mantener `vision_service.py` compatibilidad hacia atrás

## Dependencies

- `whatsapp-image-loop-fix` (ya mergeado) - usa los mismos módulos
- `digital_records_service.py` - integrar `llm_summary` en templates de documentos IA

## Data Flow

```
Chat Webhook → buffer_task (loop todos los media)
                    ↓
              vision_service (analyze_image + analyze_pdf)
                    ↓
              image_classifier (clasifica con vision_result)
                    ↓
              patient_documents (guarda cada archivo + llm_summary)
                    ↓
              Frontend: Pestaña "Resumen" muestra llm_summary
                    ↓
              IA Documents: usa llm_summary en templates
```

## Success Criteria

- [ ] 10 imágenes sin texto → se analizan y clasifican correctamente
- [ ] 5 PDFs se analizan y clasifican
- [ ] Resumen LLM se guarda en patient_documents.source_details.llm_summary
- [ ] Resumen se muestra en Pestaña "Resumen" (bajo odontograma, formato rectangular)
- [ ] Documentos IA usan llm_summary en sus templates