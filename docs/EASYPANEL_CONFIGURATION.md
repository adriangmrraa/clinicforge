# Configuración para Easypanel - ClinicForge

## 📋 VARIABLES DE ENTORNO POR SERVICIO

### **1. FRONTEND REACT (frontend_react)**
```
VITE_API_BASE_URL=https://tu-dominio-orchestrator.com
NODE_ENV=production
```

### **2. ORCHESTRATOR SERVICE (orchestrator_service)**
```
# URLs (¡IMPORTANTE!)
FRONTEND_URL=https://tu-dominio-frontend.com
PLATFORM_URL=https://tu-dominio-frontend.com
CORS_ALLOWED_ORIGINS=https://tu-dominio-frontend.com,http://localhost:3000

# Seguridad
ADMIN_TOKEN=admin-secret-token-prod-$(openssl rand -hex 16)
JWT_SECRET_KEY=jwt-secret-key-prod-$(openssl rand -hex 32)
CREDENTIALS_FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Meta Ads
META_APP_ID=tu-meta-app-id-real
META_APP_SECRET=tu-meta-app-secret-real
META_REDIRECT_URI=https://tu-dominio-orchestrator.com/auth/meta/callback

# WhatsApp
YCLOUD_API_KEY=tu-ycloud-api-key-real
YCLOUD_WEBHOOK_SECRET=tu-ycloud-webhook-secret-real

# OpenAI
OPENAI_API_KEY=sk-proj-...  # Tu clave real
```

### **3. BFF SERVICE (bff_service)**
```
ORCHESTRATOR_SERVICE_URL=http://orchestrator_service:8000
ADMIN_TOKEN=admin-secret-token-prod-$(openssl rand -hex 16)  # Mismo que orchestrator
JWT_SECRET=jwt-secret-key-prod-$(openssl rand -hex 32)  # Mismo que orchestrator
```

### **4. WHATSAPP SERVICE (whatsapp_service)**
```
YCLOUD_API_KEY=tu-ycloud-api-key-real
YCLOUD_WEBHOOK_SECRET=tu-ycloud-webhook-secret-real
ORCHESTRATOR_SERVICE_URL=http://orchestrator_service:8000
INTERNAL_API_TOKEN=clinicforge-internal-token-prod-$(openssl rand -hex 16)
```

## 🔧 PASOS PARA CONFIGURAR DESPUÉS DEL CAMBIO DE DOMINIO

### **Paso 1: Actualizar variables de entorno en Easypanel**
1. Ir a cada servicio en Easypanel
2. Actualizar las variables que contienen el dominio antiguo
3. **Variables críticas a actualizar:**
   - `FRONTEND_URL` (orchestrator)
   - `PLATFORM_URL` (orchestrator) 
   - `CORS_ALLOWED_ORIGINS` (orchestrator)
   - `META_REDIRECT_URI` (orchestrator)
   - `VITE_API_BASE_URL` (frontend)

### **Paso 2: Reiniciar servicios**
1. Reiniciar **orchestrator_service** primero
2. Luego reiniciar **bff_service**
3. Finalmente reiniciar **frontend_react**

### **Paso 3: Verificar configuración**
1. Acceder a `https://tu-dominio-frontend.com`
2. Verificar que las APIs funcionen correctamente
3. Probar autenticación y flujos principales

## 🚨 PROBLEMAS COMUNES Y SOLUCIONES

### **Problema 1: CORS errors en el frontend**
```
Solución: Verificar que CORS_ALLOWED_ORIGINS incluya el nuevo dominio
```

### **Problema 2: Meta OAuth no funciona**
```
Solución: 
1. Verificar META_REDIRECT_URI apunta al nuevo dominio
2. Actualizar la configuración en Meta Developer Dashboard
3. Reiniciar orchestrator_service
```

### **Problema 3: Webhooks no llegan**
```
Solución:
1. Verificar que YCloud tenga la URL correcta del webhook
2. Verificar que el dominio esté accesible públicamente
3. Revisar logs del whatsapp_service
```

## 📊 VERIFICACIÓN DE CONFIGURACIÓN CORRECTA

### **Endpoints para probar:**
```
1. Health check: https://tu-dominio-orchestrator.com/health
2. Meta auth URL: https://tu-dominio-orchestrator.com/admin/marketing/meta-auth/url
3. API de leads: https://tu-dominio-orchestrator.com/admin/leads
```

### **Logs a revisar:**
```
1. orchestrator_service logs - Buscar errores de CORS o URLs
2. frontend_react logs - Buscar errores de conexión API
3. bff_service logs - Buscar errores de proxy
```

## 🔄 MIGRACIÓN DE DATOS (si aplica)

Si cambiaste de dominio completamente:

### **1. Actualizar webhooks externos:**
- Meta Ads Manager (webhook de leads)
- YCloud (webhook de WhatsApp)
- Google Calendar (si está integrado)

### **2. Actualizar configuraciones:**
- Meta Developer Dashboard (OAuth redirect URIs)
- Google Cloud Console (OAuth credentials)
- Cualquier otra integración externa

## 📞 SOPORTE

### **Para debugging:**
1. Revisar logs completos en Easypanel
2. Verificar que todas las variables estén configuradas
3. Probar endpoints individualmente con curl/postman

### **Comandos útiles para debugging:**
```bash
# Verificar que el dominio responde
curl -I https://tu-dominio-orchestrator.com/health

# Verificar CORS headers
curl -I -H "Origin: https://tu-dominio-frontend.com" https://tu-dominio-orchestrator.com/

# Probar API básica
curl -H "x-admin-token: TU_TOKEN" https://tu-dominio-orchestrator.com/admin/leads
```

---

**Última actualización:** 1 de Marzo 2026  
**Estado:** ✅ URLs hardcodeadas eliminadas  
**Nota:** Todas las URLs ahora usan variables de entorno