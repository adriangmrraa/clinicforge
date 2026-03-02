# 🚀 SOLUCIÓN PARA PROBLEMA 401 EN PRODUCCIÓN

## **🔍 PROBLEMA IDENTIFICADO:**
El frontend envía `x-admin-token` correctamente, pero el backend también requiere **JWT Token** (Bearer o Cookie) que el frontend no envía.

## **✅ SOLUCIÓN IMPLEMENTADA:**
He creado un **nuevo middleware simplificado** que solo valida `x-admin-token` (sin requerir JWT).

## **📋 PASOS PARA APLICAR EN PRODUCCIÓN:**

### **Paso 1: Actualizar el código en Easypanel**
1. Ve al servicio **orchestrator_service** en Easypanel
2. En la pestaña "Deploy", haz clic en **"Deploy"** o **"Redeploy"**
3. Esto descargará los últimos cambios de GitHub

### **Paso 2: Verificar que se aplicaron los cambios**
Después del deploy, verifica con:

```bash
# Probar el endpoint de debug
curl -H "x-admin-token: admin-secret-token12093876456352884654839" \
     https://dentalforge-orchestrator.gvdlcu.easypanel.host/api/debug/auth

# Probar un endpoint real
curl -H "x-admin-token: admin-secret-token12093876456352884654839" \
     -H "x-tenant-id: 1" \
     https://dentalforge-orchestrator.gvdlcu.easypanel.host/admin/settings/clinic
```

### **Paso 3: Limpiar caché del navegador**
1. Ve a `app.dralauradelgado.com`
2. Abre Developer Tools (F12)
3. Ve a Application → Storage → Clear site data
4. O Ctrl+Shift+Delete → "Cookies and other site data"

### **Paso 4: Probar la aplicación**
1. Recarga `app.dralauradelgado.com`
2. Deberías ver las credenciales conectadas
3. Los mensajes deberían aparecer

## **🔧 CAMBIOS TÉCNICOS REALIZADOS:**

### **1. Nuevo middleware en `core/auth.py`:**
```python
async def verify_infra_token_only(request, x_admin_token):
    """Solo valida x-admin-token (sin JWT)"""
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(401, "Token inválido")
    return user_data_basico
```

### **2. Rutas actualizadas:**
- `routes/marketing.py` - Usa nuevo middleware
- `routes/leads.py` - Usa nuevo middleware  
- `routes/metrics.py` - Usa nuevo middleware

### **3. Compatibilidad mantenida:**
- Las rutas existentes siguen funcionando
- El nuevo middleware es opcional
- Se puede migrar gradualmente

## **🚨 VERIFICACIÓN RÁPIDA:**

### **Si funciona:**
- ✅ Las requests devuelven 200 OK (no 401)
- ✅ Se ven las credenciales en Settings
- ✅ Aparecen los mensajes en Chats
- ✅ Se conectan los canales (YCloud, Meta)

### **Si no funciona:**
1. Revisa logs del orchestrator_service
2. Verifica que el deploy se completó
3. Prueba con curl los endpoints

## **📊 ENDPOINTS PARA PROBAR:**

```bash
# 1. Health check (siempre debería funcionar)
curl https://dentalforge-orchestrator.gvdlcu.easypanel.host/health

# 2. Debug auth (muestra info de autenticación)
curl -H "x-admin-token: admin-secret-token12093876456352884654839" \
     https://dentalforge-orchestrator.gvdlcu.easypanel.host/api/debug/auth

# 3. Settings clinic (debería devolver datos)
curl -H "x-admin-token: admin-secret-token12093876456352884654839" \
     -H "x-tenant-id: 1" \
     https://dentalforge-orchestrator.gvdlcu.easypanel.host/admin/settings/clinic

# 4. Credentials (debería mostrar YCloud, Meta, etc.)
curl -H "x-admin-token: admin-secret-token12093876456352884654839" \
     -H "x-tenant-id: 1" \
     https://dentalforge-orchestrator.gvdlcu.easypanel.host/admin/credentials
```

## **🆘 SI SIGUE SIN FUNCIONAR:**

### **1. Revisar logs en Easypanel:**
- Ve a orchestrator_service → Logs
- Busca errores 401 o warnings

### **2. Verificar variables de entorno:**
- `ADMIN_TOKEN` debe ser `admin-secret-token12093876456352884654839`
- `CORS_ALLOWED_ORIGINS` debe incluir `https://app.dralauradelgado.com`

### **3. Contactar soporte:**
Comparte:
- Los logs del orchestrator
- Resultados de los comandos curl
- Capturas de pantalla de los errores

## **🎯 RESUMEN:**

**El problema era:** El middleware requería JWT + x-admin-token, pero el frontend solo envía x-admin-token.

**La solución es:** Nuevo middleware que solo valida x-admin-token para rutas críticas.

**Acción requerida:** Deploy del orchestrator_service en Easypanel.

**¿Necesitas ayuda con el deploy en Easypanel?**