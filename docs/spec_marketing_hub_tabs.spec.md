# Especificación: Marketing Hub Tabs (Campañas y Creativos)

Esta especificación detalla la incorporación de una interfaz de pestañas en el Marketing Hub para permitir a los usuarios desglosar el rendimiento tanto por Campaña como por Anuncio (Creativo) individual.

## 1. Objetivos
- **UX**: Permitir la navegación entre "Campañas" y "Creativos" en el bloque inferior del Hub.
- **Data**: Recuperar y mostrar métricas a nivel de anuncio (spend, leads, status).
- **Consistencia**: Mantener la lógica "Campaign-First" para asegurar que el gasto histórico siga cuadrando.

## 2. Definición de Interfaz (UI)

### Pestaña "Campañas" (Existente)
- **Columnas**: Campaña, Inversión, Leads, Citas, ROI Real, Estado.
- **Acción**: Versión actual agregada por campaña.

### Pestaña "Creativos" (Nueva)
- **Columnas**: Anuncio (Nombre + Miniatura si es posible), Campaña (Padre), Inversión, Leads, Citas (Opcional por ahora), ROI Real (Opcional por ahora), Estado.
- **Acción**: Lista detallada de todos los anuncios dentro del rango de tiempo seleccionado.

## 3. Lógica de Datos

### Backend (Marketing Service)
- Modificar el endpoint `/admin/marketing/stats` para incluir un nuevo array `ads`.
- **Retrieval**: 
    - Opción A: Consulta dedicada a `/ads?fields=insights{...}`.
    - Opción B: Expandir campañas para traer sus anuncios hijos.
- **Soberanía**: Asegurar que solo se muestran anuncios vinculados a leads del tenant actual.

### Frontend (React)
- Implementar componente `Tabs` (Versión simplificada con botones de estilo cápsula).
- Estado local `activeTab` para controlar el renderizado condicional de la tabla.

## 4. Criterios de Aceptación
1. El usuario puede ver 4 campañas en la pestaña "Campañas".
2. El usuario puede ver todos los anuncios individuales en la pestaña "Creativos".
3. El gasto total de la pestaña "Creativos" + Fallback histórico debe coincidir con el gasto total de la cuenta.
4. El cambio no rompe la visualización de datos de la Dra. Laura Delgado (gasto de $881k).
