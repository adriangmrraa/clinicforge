# Spec 06: Marketing Hub - Ad Account Selection & ROI Tracking

## 1. Contexto y Objetivos
**Objetivo:** Implementar un flujo de conexión de Meta Ads tipo "Partner", que permita:
1.  Vincular una conexión de Meta a una clínica específica (tenant).
2.  Listar portafolios de negocio (Business Managers) y sus cuentas de anuncios asociadas.
3.  Seleccionar una cuenta de anuncios por clínica, evitando duplicidades.
4.  Visualizar métricas reales (Spend, ROI) de los últimos 30 días, en la moneda local de la cuenta.

## 2. Requerimientos Técnicos

### Backend (Servicios)
- **Archivo:** `orchestrator_service/routes/marketing.py` y `meta_auth.py`
- **Flujo de Endpoints:**
  - `GET /admin/marketing/clinics`: Listar clínicas disponibles para el usuario CEO.
  - `GET /admin/marketing/meta-portfolios`: Listar Business Managers accesibles por el token.
  - `GET /admin/marketing/meta-accounts?portfolio_id=X`: Listar cuentas de anuncios de ese portafolio.
  - `POST /admin/marketing/connect`: Vincula (Tenant ID, Ad Account ID, User Token) y valida que esa clínica no tenga otra cuenta activa.
- **Sincronización:**
  - `MetaAdsClient.get_ads_insights` debe pedir `date_preset=last_30d` y capturar el campo `currency`.

### Frontend (React)
- **Componente:** `MetaConnectionWizard (Nuevo Modal)`
  - **Paso 1:** Elegir Clínica (si hay varias).
  - **Paso 2:** Elegir Portafolio.
  - **Paso 3:** Elegir Cuenta de Anuncios.
  - **Paso 4:** Confirmar y recargar Dashboard.

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Selección de clínica y cuenta
  Given un CEO con acceso a varias clínicas
  When inicia el flujo de conexión
  Then debe elegir primero la clínica a la que desea aplicar la conexión
  And el sistema debe impedir conectar una cuenta de anuncios si la clínica ya tiene una activa (bloqueo preventivo)

Scenario: Datos históricos y moneda
  Given una cuenta de anuncios en USD vinculada
  When el dashboard carga los insights
  Then debe mostrar los últimos 30 días de datos (incluyendo campañas apagadas)
  And el símbolo de moneda debe ser USD
```

## 4. Clarificaciones (Workflow /clarify)
- [ ] ¿Cómo manejamos si el usuario tiene acceso a +50 cuentas? (Paginación en lista).
- [ ] ¿Qué sucede si la cuenta seleccionada se borra en Meta? (Error gracioso y re-selección).
- [ ] ¿El gasto se muestra en la moneda de la clínica o de la cuenta de anuncios? (Conversión vs Etiqueta).
