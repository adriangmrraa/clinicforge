# Specs: WhatsApp Multi-Attachment Analysis

## 1. Overview

Extender el sistema de clasificación de adjuntos de WhatsApp para manejar múltiples imágenes (hasta 10) y PDFs (hasta 5) que llegan sin texto, analizar cada uno con Vision API, clasificar como pago/documento clínico, guardar en patient_documents, y generar un resumen LLM para mostrar en la pestaña "Resumen" de la ficha del paciente.

## 2. Functional Requirements

### FR-01: Procesamiento por lotes de imágenes
El sistema DEBE procesar hasta 10 imágenes recibidas en un único mensaje de WhatsApp sin texto.
- Cada imagen DEBE ser analizada con Vision API (GPT-4o)
- El análisis DEBE ejecutarse en paralelo para optimizar tiempo
- Si más de 10 imágenes → procesar las primeras 10, loggear warning

### FR-02: Análisis de PDFs
El sistema DEBE analizar hasta 5 PDFs recibidos usando Vision API.
- PDFs MAYOR a 5MB deben ser rechazados (log warning)
- PDFs DEBEN ser procesados como imágenes (GPT-4o soporta PDF en vision)
- Cada PDF produce una descripción de texto

### FR-03: Clasificación de adjuntos
Cada attachment individual DEBE ser clasificado como:
- **payment_receipt**: Si keywords de pago detectados en el análisis de Vision
- **clinical**: Si keywords médicos detectados, o no se detecta pago

### FR-04: Guardado en patient_documents
Todos los adjuntos DEBEN guardarse en la tabla `patient_documents`:
- Campo `document_type` = 'payment_receipt' | 'clinical'
- Campo `source_details` = JSONB con:
  - `vision_description`: resultado del análisis de Vision
  - `llm_summary`: resumen generado por LLM
  - `attachment_index`: orden del附件 en el mensaje
  - `mime_type`: tipo de archivo

### FR-05: Generación de resumen LLM
El sistema DEBE generar un resumen combinando todos los análisis de Vision:
- Resumen debe incluir: cantidad de archivos, tipos detectados, descripción breve
- Longitud máxima: 500 caracteres
- Debe almacenarse en `patient_documents.source_details.llm_summary` del primer archivo
- También debe crearse entrada en `clinical_record_summaries` (nueva tabla)

### FR-06: Mostrar resumen en UI (Pestaña Resumen)
La pestaña "Resumen" de la ficha del paciente DEBE mostrar:
- Sección rectangular bajo el Odontograma
- Encabezado: "Análisis de Adjuntos Recibidos"
- Contenido: resumen LLM + fecha + cantidad de archivos
- Formato visual: formal, similar a documentos de ficha clínica

### FR-07: Integración con documentos IA
Los documentos generados con IA (digital_records_service) DEBEN incluir:
- Sección "Documentación Adicional" con el `llm_summary` si existe
- Solo incluir si `patient_documents` tiene `llm_summary` no nulo

## 3. Scenarios

### Scenario 1: Paciente envía 5 imágenes sin texto (todas recetas médicas)
**Given** el paciente tiene un turno agendado
**When** envía 5 imágenes de recetas médicas sin texto
**Then** el sistema procesa las 5 imágenes con Vision
**And** clasifica cada una como 'clinical'
**And** guarda las 5 en patient_documents con document_type='clinical'
**And** genera un resumen LLM: "Se recibieron 5 documentos clínicos: recetas médicas..."
**And** el resumen aparece en Pestaña Resumen bajo Odontograma

### Scenario 2: Paciente envía 3 imágenes de transferencia + 2 PDFs de estudios
**Given** el paciente tiene pago pendiente
**When** envía 3 imágenes de comprobante de transferencia + 2 PDFs de estudios
**Then** el sistema procesa las 3 imágenes y 2 PDFs
**And** clasifica las 3 imágenes como 'payment_receipt'
**And** clasifica los 2 PDFs como 'clinical'
**And** genera resumen: "Se recibieron 5 archivos: 3 comprobantes de pago, 2 documentos clínicos..."
**And** el resumen aparece en Pestaña Resumen

### Scenario 3: Exceso de archivos (15 imágenes)
**Given** el paciente envía 15 imágenes
**When** el sistema recibe el mensaje
**Then** procesa las primeras 10 imágenes
**And** loggea warning: "超越了MAX_ATTACHMENTS (10), truncando"
**And** no procesa las 5 restantes

### Scenario 4: PDF muy grande (10MB)
**Given** el paciente envía un PDF de 10MB
**When** el sistema intenta analizar el PDF
**Then** rechaza el archivo por tamaño
**And** loggea warning: "PDF demasiado grande (10MB), máximo 5MB"
**And** guarda el archivo sin análisis de Vision (solo metadata)

### Scenario 5: Generación de documento IA con adjuntos
**Given** el paciente tiene documentos con llm_summary en su ficha
**When** se genera un documento clínico (ej: informe)
**Then** el documento incluye sección "Documentación Adicional"
**And** muestra el llm_summary del paciente

## 4. Architecture Decisions

### AD-01: Paralelización de Vision API
- Usar `asyncio.gather()` para procesar múltiples imágenes en paralelo
- Limitar concurrencia a 5 tareas simultáneas para evitar rate limits
- Timeout por attachment: 30 segundos

### AD-02: Almacenamiento de llm_summary
- Guardar en `patient_documents.source_details` (ya existe JSONB)
- Solo guardar el resumen en el primer attachment del batch
- Crear tabla `clinical_record_summaries` para persistencia por conversación

### AD-03: UI - Sección Resumen
- Nuevo componente React `<AttachmentSummaryCard />`
- Ubicación: después del componente Odontograma en Pestaña Resumen
- Estilo: tarjeta con borde sutil, fondo claro, formato profesional

### AD-04: Documentos IA
- Modificar `digital_records_service.py` para incluir `llm_summary`
- Agregar sección en el template cuando existe el dato
- Fallback: si no hay llm_summary, no mostrar sección

### AD-05: Manejo de errores
- Si Vision API falla para un attachment → guardar sin descripción, continuar
- Si LLM summary falla → guardar con "Resumen no disponible"
- Nunca bloquear el flujo por errores parciales

## 5. Database Schema

### Nueva tabla: clinical_record_summaries
```sql
CREATE TABLE clinical_record_summaries (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenants(id),
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    conversation_id VARCHAR(100),
    summary_text TEXT NOT NULL,
    attachments_count INTEGER,
    attachments_types JSONB, -- ['payment', 'clinical', 'clinical']
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, patient_id, conversation_id)
);
```

### Extensión: patient_documents.source_details
```json
{
  "vision_description": "Descripción de Vision API...",
  "llm_summary": "Resumen generado por LLM...",
  "attachment_index": 0,
  "mime_type": "image/jpeg",
  "is_first_in_batch": true
}
```

## 6. API Endpoints

### GET /patients/{id}/attachments-summary
Devuelve el resumen de adjuntos más reciente del paciente.

```json
{
  "summary_text": "Se recibieron 3 archivos...",
  "attachments_count": 3,
  "attachments_types": ["payment", "clinical", "payment"],
  "created_at": "2026-04-02T12:00:00Z"
}
```

## 7. Frontend Components

### AttachmentSummaryCard
```tsx
<Card className="border border-gray-200 bg-gray-50 p-4">
  <h4 className="font-semibold text-gray-700 mb-2">
    Análisis de Adjuntos Recibidos
  </h4>
  <p className="text-sm text-gray-600">{llm_summary}</p>
  <div className="mt-2 text-xs text-gray-400">
    {attachmentsCount} archivos • {formattedDate}
  </div>
</Card>
```

## 8. Security & Performance

- **Rate limiting**: Max 5 llamadas concurrentes a Vision API
- **Timeout**: 30s por attachment, 300s total por batch
- **Costo**: ~$0.007 por 5 imágenes (estimado)
- **Logs**: Cada análisis de attachment con nivel INFO
- **Errors**: No exponer detalles de Vision API al usuario