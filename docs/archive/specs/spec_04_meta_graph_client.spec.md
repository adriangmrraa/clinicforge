# Spec 04: Cliente Meta Graph API

## 1. Contexto y Objetivos
**Objetivo:** Consultar la Graph API de Meta para enriquecer los IDs opacos (`ad_id`, `campaign_id`) con nombres legibles por humanos.
**Problema:** El webhook solo envía IDs numéricos. Para el dashboard y la IA, necesitamos nombres reales.

## 2. Requerimientos Técnicos

### Backend (Servicio API)
- **Archivo:** `orchestrator_service/services/meta_ads_service.py` (Nuevo)
- **Clase:** `class MetaAdsClient`
- **Métodos:**
  - `get_ad_details(ad_id: str) -> dict`
- **Lógica:**
  - GET `https://graph.facebook.com/{version}/{ad_id}?fields=name,campaign{name},adset{name}`
  - Auth: Bearer Token desde `META_ADS_TOKEN`.
  - Manejo de Errores: 401 (Token vencido), 429 (Rate Limit), 404 (No encontrado).

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Obtener detalles de anuncio válido
  Given un ad_id válido y un token activo
  When se llama a MetaAdsClient.get_ad_details
  Then retorna un dict con 'campaign_name' y 'ad_name'

Scenario: Token inválido
  Given un token expirado
  When se llama a MetaAdsClient
  Then lanza excepción controlada
```

## 4. Esquema de Datos (Respuesta API)

```json
{
  "name": "Anuncio Implantes V1",
  "campaign": {
    "name": "Campaña R.I.S.A. Q1"
  },
  "id": "123456"
}
```

## 5. Riesgos y Mitigación
- **Riesgo:** Latencia alta en Graph API.
- **Mitigación:** Llamada asíncrona (ver Spec 05) y timeouts estrictos.

## 6. Compliance SDD v2.0
- **Seguridad:** El token de Meta no debe loguearse.
