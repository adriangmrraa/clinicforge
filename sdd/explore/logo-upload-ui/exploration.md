## Exploration: Logo Upload UI

### Current State
- **Backend**: Endpoint POST `/admin/tenants/{tenant_id}/logo` ya implementado (solo CEO, valida imagen <2MB, guarda en `/app/uploads/tenants/{tenant_id}/logo.{ext}`, actualiza columna `tenants.logo_url`).
- **Frontend**: ConfigView.tsx tiene pestañas para configuraciones (General, YCloud, Chatwoot, Otras, Mantenimiento, Leads, Meta). Solo CEO ve las pestañas de integración.
- **Sidebar**: Carga el logo desde GET `/admin/public/tenant-logo/{tenant_id}` al montarse, guarda URL blob en estado y localStorage, y establece favicon.
- **Traducciones**: Archivos i18n en `src/locales/{es,en,fr}.json` con claves para config.

### Affected Areas
- `frontend_react/src/views/ConfigView.tsx` — agregar pestaña nueva o expandir General
- `frontend_react/src/locales/es.json`, `en.json`, `fr.json` — nuevas claves de traducción
- `frontend_react/src/components/Sidebar.tsx` — posible mejora para actualización en caliente (evento custom)
- `frontend_react/src/api/axios.ts` — ya maneja autenticación; subida de archivos requiere `Content-Type: multipart/form-data`

### Approaches
1. **Nueva pestaña "Branding" (recomendada)**
   - Pros: Separación clara, espacio para futuras configuraciones de marca (colores, fuentes). Coherente con patrón de pestañas por funcionalidad.
   - Cons: Añade una pestaña más a la lista ya extensa.
   - Effort: Medio

2. **Sección dentro de pestaña "General"**
   - Pros: Menos cambios, el logo está relacionado con configuración general.
   - Cons: Puede saturar la pestaña General y limitar expansión futura.
   - Effort: Bajo

3. **Modal de edición desde Sidebar (icono de lápiz junto al logo)**
   - Pros: Acceso directo y contextual.
   - Cons: Requiere cambios en Sidebar, manejo de permisos más complejo, fuera del flujo de configuración central.
   - Effort: Medio-Alto

### Recommendation
**Opción 1 (Nueva pestaña "Branding")** porque:
- Sigue el patrón existente (cada integración tiene su pestaña).
- El CEO ya está acostumbrado a navegar por pestañas.
- Permite agregar en el futuro más opciones de personalización (colores, fuentes, favicon, etc.).
- El esfuerzo es moderado y el impacto visual es organizado.

**Detalles de implementación**:
- Agregar pestaña "Branding" dentro del bloque `user?.role === 'ceo'`.
- Incluir selector de clínica (dropdown de tenants) igual que en YCloud/Chatwoot.
- Componente de upload con drag‑and‑drop, preview del logo actual, validaciones de formato (PNG, JPG, SVG, WebP, ICO) y tamaño (2 MB).
- Después de subida exitosa, emitir evento custom `tenant-logo-updated` para que Sidebar recargue el logo sin recargar la página.
- Agregar traducciones para todos los textos nuevos.

### Risks
- **Logo no se actualiza en Sidebar inmediatamente**: Mitigar con evento custom `tenant-logo-updated` que Sidebar escuche y vuelva a ejecutar la carga del logo.
- **CEO con múltiples clínicas selecciona la equivocada**: Usar el mismo dropdown de tenants que ya existe en otras pestañas, asegurar que el tenant_id se envía correctamente al endpoint.
- **Caché del navegador**: El endpoint GET devuelve el archivo directamente; el navegador puede cachearlo. Agregar query param `?t=${Date.now()}` al refrescar.
- **Validaciones frontend inconsistentes con backend**: Replicar exactamente las mismas reglas (formatos, tamaño) en el frontend.

### Ready for Proposal
Sí. La exploración identifica la solución técnica, los archivos afectados, y los riesgos mitigables. El siguiente paso es crear una propuesta de cambio (proposal) con especificaciones detalladas.