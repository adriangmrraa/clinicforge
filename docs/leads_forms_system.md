# Sistema de Leads Forms para ClinicForge

## 📋 Resumen

Sistema completo para recibir, gestionar y atribuir leads de formularios Meta Ads en ClinicForge. Inspirado en el CRM Ventas pero adaptado específicamente para clínicas dentales.

## 🎯 Objetivos

1. **Reemplazar la tarjeta Webhook Configuration** del Marketing Hub con una pestaña dedicada "Leads Forms" en Settings
2. **Mostrar URL completa del webhook** para copiar/pegar en Meta Ads
3. **Atribución automática completa** de leads a campañas/anuncios específicos
4. **Página de gestión de leads** inspirada en CRM Ventas, adaptada para clínica
5. **Conversión automática** de leads a pacientes con atribución preservada

## ⚠️ **IMPORTANTE: CÓMO FUNCIONA LA ATRIBUCIÓN**

### **¿Qué información llega en el webhook de Meta?**
El webhook estándar de Meta **SOLO envía IDs**, no nombres:
- `ad_id` - ID del anuncio/creativo
- `adset_id` - ID del conjunto de anuncios
- `campaign_id` - ID de la campaña
- `form_id` - ID del formulario
- `page_id` - ID de la página

### **¿Cómo se obtienen los nombres descriptivos?**

#### **Para ClinicForge (nuestra prioridad):**
1. **`ad_name` (ANUNCIO/CREATIVO)** - **ES LO MÁS IMPORTANTE**
   - Se extrae de: `ad_name`, `creative_name`, `creative`, `anuncio`
   - Si no viene, se deriva de `adset_name` o `campaign_name`
   - **SIEMPRE se garantiza que haya un valor en `ad_name`**

2. **`campaign_name` (CAMPAÑA)** - **También importante**
   - Se extrae de: `campaign_name`, `campaña`, `campaign`
   - Se muestra en el dashboard junto con `ad_name`

3. **`adset_name` (CONJUNTO DE ANUNCIOS)** - **Menos importante**
   - Se usa solo si no hay `ad_name`
   - No se muestra prominentemente en el dashboard

#### **Fuentes de datos:**
1. **Payloads custom (n8n/LeadsBridge, Zapier, etc.)**:
   - ✅ **Nombres vienen directamente** en el payload
   - ✅ El sistema detecta automáticamente campos como `ad_name`, `campaign_name`
   - ✅ **INTELIGENCIA AVANZADA**: Detecta campos aunque tengan nombres diferentes
   - ✅ **Procesa formatos combinados** (ej: "Adset - Ad")

2. **Con token de Meta válido**:
   - ✅ Se obtienen nombres via Meta API
   - ⚠️ Requiere token con permisos `ads_management`

3. **Sin token de Meta y sin payload custom**:
   - ⚠️ Solo IDs (sin nombres descriptivos)
   - ✅ Atribución funcional igual funciona
   - ⚠️ UX menos amigable ("Ad {ID}" en lugar de nombre descriptivo)

### **Requisitos para atribución completa:**
- **Token de Meta** con permisos: `ads_management`, `leads_retrieval`
- **Configurado en**: Configuración → Pestaña "Chatwoot (Meta)"
- **Sin token**: Atribución funcional pero sin nombres descriptivos

## 🏗️ Arquitectura

### Backend
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Meta Ads      │───▶│   Webhook API   │───▶│   Leads Service │
│   Lead Forms    │    │   /webhooks/meta│    │                 │
└─────────────────┘    └─────────────────┘    └─────────┬───────┘
                                                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────▼───────┐
│   Frontend      │◀───│   Leads API     │◀───│   PostgreSQL   │
│   React App     │    │   /admin/leads  │    │   Database     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Base de Datos
```sql
-- Tablas principales
meta_form_leads           # Leads recibidos de formularios
lead_status_history       # Historial de cambios de estado
lead_notes                # Notas de seguimiento

-- Relaciones
meta_form_leads → patients    # Conversión a paciente
meta_form_leads → users       # Asignación a usuario
meta_form_leads → tenants     # Multi-tenant isolation
```

## 🔧 Componentes Implementados

### 1. Migración de Base de Datos (`patch_019_meta_form_leads.sql`)
- **Tabla `meta_form_leads`**: Almacena todos los datos del lead
  - Atribución Meta Ads (campaign_id, ad_id, adset_id)
  - Información del paciente (nombre, teléfono, email)
  - Contexto médico (interés, especialidad, obra social)
  - Estado y gestión (status, assigned_to, notes)
  - Conversión a paciente (converted_to_patient_id)

- **Tabla `lead_status_history`**: Audit trail de cambios de estado
- **Tabla `lead_notes`**: Notas de seguimiento y comunicación
- **Estados predefinidos**: new, contacted, consultation_scheduled, treatment_planned, converted, not_interested, spam

### 2. Servicio Backend (`meta_leads_service.py`)
- **Procesamiento de webhooks**: Soporta formatos estándar Meta y custom (n8n/LeadsBridge)
- **Enriquecimiento con Meta API**: Obtiene nombres de campañas/ads automáticamente
- **Deduplicación**: Evita leads duplicados (mismo teléfono + campaña en 24h)
- **Gestión completa**: CRUD, cambio de estado, notas, conversión a paciente
- **Estadísticas**: Métricas de conversión, distribución por campaña, tendencias

### 3. API Endpoints (`routes/leads.py`)
```
GET    /admin/leads                    # Lista de leads con filtros
GET    /admin/leads/{id}              # Detalle completo de lead
PUT    /admin/leads/{id}/status       # Cambiar estado
PUT    /admin/leads/{id}/assign       # Asignar a usuario
POST   /admin/leads/{id}/notes        # Agregar nota
POST   /admin/leads/{id}/convert      # Convertir a paciente
GET    /admin/leads/stats/summary     # Estadísticas
GET    /admin/leads/webhook/url       # URL del webhook
```

### 4. Frontend React

#### **Pestaña Leads Forms (`LeadsFormsTab.tsx`)**
- Reemplaza la tarjeta Webhook Configuration del Marketing Hub
- Muestra URL completa del webhook para copiar/pegar
- Token de verificación para Meta Ads
- Instrucciones paso a paso
- Estadísticas en tiempo real
- Enlaces rápidos a gestión de leads

#### **Página de Gestión (`LeadsManagementView.tsx`)**
- Lista tabular de leads con filtros avanzados
- Vista móvil responsive con cards
- Paginación y ordenamiento
- Cambio de estado en línea
- Exportación de datos
- Dashboard de métricas

#### **Detalle de Lead (`LeadDetailView.tsx`)**
- Información completa del contacto
- Atribución Meta Ads detallada
- Historial de estados
- Notas de seguimiento
- Línea de tiempo de eventos
- Acciones rápidas (llamar, cambiar estado, convertir)

#### **Integración en Configuración**
- Nueva pestaña "Leads Forms" en ConfigView
- Accesible solo para usuarios CEO
- Reemplaza completamente la funcionalidad anterior

## 🚀 Flujo de Trabajo

### 1. Configuración Inicial
```
Usuario → Configuración → Pestaña "Leads Forms"
         ↓
Copia URL del webhook y token
         ↓
Configura en Meta Ads Manager
         ↓
Verifica conexión
```

### 2. Recepción de Leads
```
Meta Ad → Lead Form → Meta Webhook → ClinicForge
         ↓
Procesamiento automático
         ↓
Atribución a campaña/anuncio
         ↓
Almacenamiento en base de datos
         ↓
Notificación (opcional)
```

### 3. Gestión de Leads
```
Recepción → Estado "new"
         ↓
Contacto → Estado "contacted"
         ↓
Agendamiento → Estado "consultation_scheduled"
         ↓
Planificación → Estado "treatment_planned"
         ↓
Conversión → Estado "converted" + paciente vinculado
```

### 4. Conversión a Paciente
```
Lead → Convertir a paciente
     ↓
Seleccionar paciente existente
     ↓
Transferir atribución Meta Ads
     ↓
Actualizar paciente con source=META_ADS
     ↓
Lead marcado como convertido
```

## 🔐 Seguridad y Multi-Tenant

### Aislamiento de Datos
- Todos los queries incluyen `tenant_id` filtering
- Webhooks validan tenant_id en parámetros o headers
- Usuarios solo ven leads de su clínica asignada

### Validación de Webhooks
- Token de verificación configurable por entorno
- Rate limiting (20 requests/minuto)
- Procesamiento en background para escalabilidad
- Logging completo para debugging

### Control de Acceso
- Endpoints solo accesibles para usuarios CEO
- Validación de UUIDs en todas las operaciones
- Transacciones atómicas para operaciones críticas

## 📊 Métricas y Analytics

### Estadísticas en Tiempo Real
- **Totales**: Leads totales, convertidos, tasa de conversión
- **Por Estado**: Distribución por estado del workflow
- **Por Campaña**: Performance por campaña Meta Ads
- **Tendencia Diaria**: Leads recibidos por día

### Atribución de ROI
- Cada lead mantiene referencia exacta a campaign_id, ad_id, adset_id
- Conversión a paciente preserva atribución completa
- Integración con Marketing Hub para métricas unificadas
- Cálculo automático de ROI por campaña

## 🛠️ Instalación y Configuración

### 1. Ejecutar Migración
```bash
cd /home/node/.openclaw/workspace/projects/clinicforge
python3 run_leads_migration.py
```

### 2. Configurar Variables de Entorno
```bash
# Token de verificación para webhooks Meta
META_WEBHOOK_VERIFY_TOKEN=clinicforge_meta_secret_token

# URL base para webhooks (se auto-genera desde deployment config)
```

### 3. Configurar Meta Ads
1. Ir a Meta Ads Manager → Configuración → Webhooks
2. Crear nueva suscripción para "Leadgen"
3. Pegar URL de `/admin/leads/webhook/url`
4. Usar token de verificación configurado
5. Guardar y verificar conexión

### 4. Probar el Sistema
1. Crear formulario de leads en Meta Ads
2. Generar lead de prueba
3. Verificar llegada a `/leads`
4. Probar cambio de estado y notas
5. Probar conversión a paciente

## 🔄 Mantenimiento y Monitoreo

### Logs a Monitorear
- **Webhook reception**: `📥 Received Meta webhook`
- **Lead processing**: `✅ Lead saved successfully`
- **Errors**: `❌ Error processing lead form webhook`

### Tareas Programadas
- **Limpieza de datos**: Leads muy antiguos (configurable)
- **Backup automático**: Exportación periódica de leads
- **Reportes**: Envío automático de métricas por email

### Performance
- **Indexes**: Optimizados para queries comunes
- **Caching**: Estadísticas en Redis (opcional)
- **Background processing**: Webhooks no bloqueantes

## 🎨 UX/UI Considerations

### Diseño Responsive
- **Desktop**: Tablas con todas las columnas
- **Tablet**: Tablas simplificadas
- **Mobile**: Cards con información esencial

### Estados Visuales
- **Colores por estado**: Código de colores consistente
- **Iconografía**: Iconos representativos para cada acción
- **Feedback inmediato**: Confirmaciones de acciones

### Navegación
- **Breadcrumbs**: Ruta clara desde Configuración → Leads
- **Enlaces rápidos**: Acceso directo desde dashboard
- **Historial**: Navegación hacia atrás preservada

## 📈 Roadmap y Mejoras Futuras

### Fase 2 (Próxima)
- [ ] Notificaciones push para nuevos leads
- [ ] Asignación automática por reglas
- [ ] Integración con calendario para agendamiento
- [ ] Plantillas de email para seguimiento

### Fase 3
- [ ] Dashboard de analytics avanzado
- [ ] Machine learning para scoring de leads
- [ ] Integración con otros canales (Google Ads, etc.)
- [ ] API pública para integraciones externas

### Fase 4
- [ ] Chatbot integrado para qualificación inicial
- [ ] Sistema de seguimiento automático
- [ ] Reportes personalizados
- [ ] Exportación a CRM externos

## 🐛 Troubleshooting

### Problemas Comunes

#### Webhook no llega
1. Verificar URL en Meta Ads Manager
2. Verificar token de verificación
3. Revisar logs del backend
4. Probar con herramienta de debugging (ngrok, etc.)

#### Leads duplicados
1. Verificar deduplicación (teléfono + campaña en 24h)
2. Revisar formato del payload
3. Verificar procesamiento en background

#### Atribución incorrecta
1. Verificar que Meta token tenga permisos suficientes
2. Revisar enriquecimiento automático
3. Verificar IDs de campaña/anuncio en payload

### Comandos de Debugging
```bash
# Ver logs del backend
tail -f /var/log/clinicforge/backend.log | grep -i "lead\|webhook"

# Ver leads en base de datos
psql -d clinicforge -c "SELECT COUNT(*), status FROM meta_form_leads GROUP BY status;"

# Probar endpoint de webhook
curl -X POST https://tu-dominio.com/api/webhooks/meta \
  -H "Content-Type: application/json" \
  -d '{"test": "payload"}'
```

## 📚 Referencias

### Documentación Relacionada
- [Meta Webhooks Documentation](https://developers.facebook.com/docs/graph-api/webhooks)
- [Lead Ads API Reference](https://developers.facebook.com/docs/marketing-api/lead-ads)
- [ClinicForge Marketing Hub Spec](./spec_marketing_hub_tabs.spec.md)

### Inspiración
- CRM Ventas Implementation (proyecto hermano)
- HubSpot Leads Management
- Salesforce Sales Cloud

---

**Última actualización**: 27 de Febrero 2026  
**Versión**: 1.0.0  
**Estado**: ✅ Implementación Completa