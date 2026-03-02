# ✅ CHECKLIST DE VERIFICACIÓN POST-DEPLOY

## **📋 DESPUÉS DEL DEPLOY DEL FRONTEND:**

### **1. LIMPIAR CACHÉ DEL NAVEGADOR:**
```javascript
// En Console (F12 → Console)
localStorage.clear();
sessionStorage.clear();
location.reload();
```

O usa: `Ctrl+Shift+Delete` → "Cookies and other site data" + "Cached images and files"

### **2. VERIFICAR QUE FUNCIONE:**

#### **✅ SETTINGS → PESTAÑA "LEADS FORMS":**
1. Ve a `https://app.dralauradelgado.com/configuracion`
2. Haz clic en la pestaña **"Leads Forms"**
3. **DEBERÍAS VER:**
   - Webhook URL para copiar/pegar en Meta Ads
   - Estadísticas de leads (si hay)
   - Instrucciones de configuración
   - Botón "Ver Leads"

#### **✅ SIDEBAR → OPCIÓN "LEADS":**
1. En el sidebar izquierdo
2. **DEBERÍA APARECER:** "Leads" después de "Marketing Hub"
3. Al hacer clic → va a `/leads`

#### **✅ PÁGINA `/leads`:**
1. Ve a `https://app.dralauradelgado.com/leads`
2. **DEBERÍAS VER:**
   - Título: "Gestión de Leads"
   - Filtros por estado, campaña, fecha
   - Tabla de leads (vacía si no hay)
   - Botones de acción

### **3. VERIFICAR CONSOLA SIN ERRORES:**
1. Abre Console (F12)
2. **NO DEBERÍA HABER:**
   - `ReferenceError: require is not defined`
   - `ReferenceError: AlertCircle is not defined`
   - `ReferenceError: MessageSquare is not defined`

### **4. PROBAR BACKEND CON CURL:**
```bash
# Probar endpoint de webhook
curl -H "x-admin-token: admin-secret-token12093876456352884654839" \
     -H "x-tenant-id: 1" \
     https://dentalforge-orchestrator.gvdlcu.easypanel.host/admin/leads/webhook/url

# Probar estadísticas
curl -H "x-admin-token: admin-secret-token12093876456352884654839" \
     -H "x-tenant-id: 1" \
     https://dentalforge-orchestrator.gvdlcu.easypanel.host/admin/leads/stats/summary
```

## **🔧 SI HAY PROBLEMAS:**

### **PROBLEMA 1: Settings se pone en blanco**
**Solución:** Revisar Console → Compartir errores

### **PROBLEMA 2: No aparece opción "Leads" en sidebar**
**Solución:** Verificar que el usuario tiene rol "ceo"

### **PROBLEMA 3: Página `/leads` no carga**
**Solución:** Verificar rutas en `App.tsx` y permisos

### **PROBLEMA 4: WebSocket errors**
**Solución:** Agregar ambas URLs a CORS:
```
CORS_ALLOWED_ORIGINS=https://app.dralauradelgado.com,https://dentalforge-frontend.gvdlcu.easypanel.host
```

## **📞 SOPORTE:**

**Compartir para diagnóstico:**
1. Screenshot de la consola con errores
2. Resultado de comandos curl
3. Screenshot de lo que ves/No ves

**Commit actual:** `3054495` - "fix: arreglar carga de LeadsFormsTab y agregar al sidebar"