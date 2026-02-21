# Spec 02: Recepción de Webhooks (YCloud)

## 1. Contexto y Objetivos
**Objetivo:** Interceptar el objeto `referral` que WhatsApp envía cuando un usuario inicia chat desde un anuncio de Click-to-WhatsApp.
**Problema:** El webhook actual de YCloud ignora estos metadatos, perdiendo la trazabilidad.

## 2. Requerimientos Técnicos

### Backend (WhatsApp Service)
- **Archivo:** `whatsapp_service/main.py`
- **Lógica:**
  - Parsear el JSON entrante de YCloud.
  - Identificar si contiene la clave `referral` dentro de `messages`.
  - Extraer: `source_url`, `source_id`, `source_type`, `headline`, `body`, `media_type`, `image_url` (si disponible).
- **Output:** Incluir estos datos en un diccionario `referral_data` al enviar el mensaje al Orchestrator.

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Recepción de mensaje desde anuncio
  Given un payload de webhook de YCloud con objeto 'referral'
  When el servicio procesa el mensaje
  Then se extrae el 'source_id' del anuncio
  And se extrae el 'headline' y 'body'
  And el payload enviado al Orchestrator incluye 'referral_data'

Scenario: Mensaje normal sin anuncio
  Given un payload de webhook estándar sin 'referral'
  When el servicio procesa el mensaje
  Then 'referral_data' es NULL o vacío
  And el flujo continúa normalmente
```

## 4. Esquema de Datos (Payload Interno)

```json
{
  "sender": "123456789",
  "text": "Hola, info",
  "referral_data": {
    "source_id": "1234567890",
    "source_type": "ad",
    "headline": "Promo Implantes",
    "body": "Descuento 50%",
    "source_url": "https://fb.me/..."
  }
}
```

## 5. Riesgos y Mitigación
- **Riesgo:** Cambios en la API de YCloud o formato de Meta.
- **Mitigación:** Logs estructurados de payloads entrantes (sanitizados) para debugging.

## 6. Compliance SDD v2.0
- **Seguridad:** Los datos del referral son seguros, pero URLs largas deben validarse.
