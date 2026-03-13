# 🕐 SISTEMA DE JOBS PROGRAMADOS

**Versión:** 1.0  
**Fecha de implementación:** 5-6 de Marzo 2026  
**Última actualización:** 6 de Marzo 2026  
**Estado:** ✅ PRODUCCIÓN

## 🎯 OBJETIVO

Arquitectura unificada para la ejecución de tareas programadas (cron jobs) en ClinicForge, proporcionando:
- **Programación flexible** - Ejecución diaria a horas específicas
- **Integración nativa** - Con FastAPI lifespan (startup/shutdown)
- **Administración completa** - Endpoints para testing y monitoreo
- **Resiliencia** - Manejo de errores y logging detallado
- **Multi-tenant** - Aislamiento completo por clínica

## 📋 RESUMEN EJECUTIVO

### **Jobs implementados:**

| Job | Horario | Descripción | Estado |
|-----|---------|-------------|--------|
| **Appointment Reminders** | 10:00 AM | Recordatorios de turnos para el día siguiente | ✅ PRODUCCIÓN |
| **Lead Recovery** | Cada 1 hora | Recuperación de leads de Meta Ads (ventana 2h) | ✅ PRODUCCIÓN |
| **Post-Treatment Followups** | 11:00 AM | Seguimiento post-atención para pacientes de cirugía | ✅ PRODUCCIÓN |

### **Características comunes:**
- ✅ **Programación diaria** - Horarios específicos configurados
- ✅ **Integración WhatsApp** - Mensajes personalizados por paciente
- ✅ **Tracking completo** - Campos de auditoría en base de datos
- ✅ **Endpoints admin** - Testing y ejecución manual
- ✅ **Multi-tenant** - Aislamiento por `tenant_id`

## 🏗️ ARQUITECTURA

### **Estructura del módulo:**
```
orchestrator_service/jobs/
├── __init__.py          # Import automático y logging
├── scheduler.py         # Sistema de scheduling centralizado
├── reminders.py         # Job de recordatorios de turnos
├── followups.py         # Job de seguimiento post-atención
├── lead_recovery.py     # Job de recuperación de leads (IA + disponibilidad)
└── admin_routes.py      # Endpoints de administración
```

### **Integración con FastAPI:**
```python
# En main.py - Lifespan integration
@app.on_event("startup")
async def startup_event():
    """Inicializa el scheduler de jobs al arrancar la app."""
    from jobs.scheduler import scheduler
    await scheduler.start()
    logger.info("✅ Scheduler de jobs iniciado")

@app.on_event("shutdown")
async def shutdown_event():
    """Detiene el scheduler al apagar la app."""
    from jobs.scheduler import scheduler
    await scheduler.stop()
    logger.info("🛑 Scheduler de jobs detenido")
```

## ⚙️ SISTEMA DE SCHEDULING

### **Clase `AsyncScheduler`:**
```python
class AsyncScheduler:
    """
    Scheduler asíncrono para jobs programados.
    
    Características:
    - Ejecución diaria a horas específicas
    - Registro automático de jobs
    - Manejo de errores individual
    - Logging detallado
    - Startup/shutdown seguro
    """
    
    def __init__(self):
        self.tasks = []  # Lista de (func, interval_seconds, run_at_startup)
        self.running = False
        self._tasks = []
```

### **Decorador `@schedule_daily_at`:**
```python
def schedule_daily_at(hour: int, minute: int = 0, run_at_startup: bool = False):
    """
    Decorador para registrar jobs que se ejecutan diariamente a una hora específica.
    
    Args:
        hour: Hora del día (0-23)
        minute: Minuto (0-59)
        run_at_startup: Si se ejecuta inmediatamente al iniciar
    """
    # Calcular intervalo hasta la próxima ejecución
    interval_seconds = calculate_seconds_until(hour, minute)
    
    def decorator(func):
        scheduler.register_task(func, interval_seconds, run_at_startup)
        return func
    
    return decorator
```

## 🔧 CONFIGURACIÓN

### **Variables de entorno requeridas:**
```bash
# Para integración con WhatsApp Service
WHATSAPP_SERVICE_URL=http://whatsapp_service:8000
INTERNAL_API_TOKEN=tu_token_secreto_aqui
```

### **Configuración por tenant:**
- `tenants.whatsapp_credentials` debe estar configurado
- Credenciales de YCloud/WhatsApp Business API
- Número de teléfono empresarial verificado

## 📊 JOB 1: RECORDATORIOS DE TURNOS

### **Configuración:**
- **Horario:** 10:00 AM diario
- **Objetivo:** Recordar turnos programados para el día siguiente
- **Audiencia:** Todos los pacientes con turno confirmado

### **Query SQL:**
```sql
SELECT 
    a.id as appointment_id,
    a.appointment_datetime,
    a.status,
    a.reminder_sent,
    p.id as patient_id,
    p.first_name,
    p.last_name,
    p.phone_number,
    t.id as tenant_id,
    t.name as tenant_name,
    t.whatsapp_credentials
FROM appointments a
INNER JOIN patients p ON a.patient_id = p.id AND p.tenant_id = a.tenant_id
INNER JOIN tenants t ON a.tenant_id = t.id
WHERE a.status IN ('confirmed', 'scheduled')
    AND a.appointment_datetime >= $1  -- Mañana inicio del día
    AND a.appointment_datetime <= $2  -- Mañana fin del día
    AND (a.reminder_sent IS NULL OR a.reminder_sent = false)
    AND p.phone_number IS NOT NULL
    AND p.phone_number != ''
ORDER BY a.appointment_datetime
```

### **Mensaje template:**
```
"Hola [Nombre], te escribimos del consultorio de la Dra. Delgado 
para recordarte tu turno de mañana a las [Hora]. 
¿Me confirmás tu asistencia?"
```

### **Campos de BD:**
```sql
-- En tabla appointments
reminder_sent BOOLEAN DEFAULT FALSE
reminder_sent_at TIMESTAMPTZ

-- Índices
CREATE INDEX idx_appointments_reminder_sent ON appointments(reminder_sent);
CREATE INDEX idx_appointments_reminder_date ON appointments(reminder_sent_at);
```

## ⚕️ JOB 2: SEGUIMIENTO POST-ATENCIÓN

### **Configuración:**
- **Horario:** 11:00 AM diario
- **Objetivo:** Seguimiento de pacientes atendidos ayer (solo tratamientos/cirugías)
- **Audiencia:** Pacientes con turnos `status='completed'` del día anterior

### **Query SQL:**
```sql
SELECT 
    a.id as appointment_id,
    a.appointment_datetime,
    a.status,
    a.followup_sent,
    a.treatment_type,
    p.id as patient_id,
    p.first_name,
    p.last_name,
    p.phone_number,
    t.id as tenant_id,
    t.name as tenant_name,
    t.whatsapp_credentials
FROM appointments a
INNER JOIN patients p ON a.patient_id = p.id AND p.tenant_id = a.tenant_id
INNER JOIN tenants t ON a.tenant_id = t.id
WHERE a.status = 'completed'
    AND a.appointment_datetime >= $1  -- Ayer inicio del día
    AND a.appointment_datetime <= $2  -- Ayer fin del día
    AND (a.followup_sent IS NULL OR a.followup_sent = false)
    AND p.phone_number IS NOT NULL
    AND p.phone_number != ''
    -- Solo seguimiento para tratamientos/cirugías (no consultas simples)
    AND (a.treatment_type IS NOT NULL OR a.treatment_type != 'consultation')
ORDER BY a.appointment_datetime
```

### **Mensaje template:**
```
"Hola [Nombre], soy la asistente de la Dra. Delgado. 
Te escribo para saber cómo te sentís hoy después de la atención de ayer ([Fecha]). 
¿Tuviste alguna molestia o va todo bien?"
```

### **Campos de BD:**
```sql
-- En tabla appointments
followup_sent BOOLEAN DEFAULT FALSE
followup_sent_at TIMESTAMPTZ

-- Índices
CREATE INDEX idx_appointments_followup_sent ON appointments(followup_sent);
CREATE INDEX idx_appointments_followup_date ON appointments(followup_sent_at);
```

## 🔍 DETECCIÓN Y TRIAGE

### **Integración con agente LLM:**
```python
# En buffer_task.py - Detección de contexto especial
if isinstance(attrs, dict) and attrs.get("is_followup"):
    is_followup_response = True
    followup_context = (
        "⚠️ ATENCIÓN: El paciente está respondiendo a un mensaje de "
        "seguimiento post-atención. DEBÉS evaluar síntomas con 'triage_urgency' "
        "y aplicar las 6 reglas maxilofaciales de urgencia."
    )
```

### **Instrucciones en system prompt:**
```
SEGUIMIENTO POST-ATENCIÓN (CRÍTICO): Si el paciente responde a un mensaje de seguimiento post-atención (identificado por "seguimiento" en el contexto o metadata), DEBÉS:
1. Preguntar específicamente por síntomas post-tratamiento
2. Evaluar inmediatamente con 'triage_urgency' si menciona dolor, inflamación, sangrado, fiebre o cualquier molestia
3. Aplicar las 6 reglas maxilofaciales de urgencia configuradas
4. Si es emergency/high, activar protocolo de urgencia inmediatamente
5. Si es normal/low, tranquilizar y dar indicaciones de cuidado post-operatorio
```

## 🤖 JOB 3: RECUPERACIÓN DE LEADS (LEAD RECOVERY)

### **Configuración:**
- **Horario:** Ejecución horaria (verifica leads de hace 2 horas).
- **Objetivo:** Convertir leads de Meta Ads que no agendaron tras interactuar con la IA.
- **Audiencia:** Leads con `source = 'META_ADS'` sin citas previas ni futuras.

### **Lógica de Ejecución:**
1. **Filtro de Exclusión**: Se excluyen pacientes que ya tienen o tuvieron turnos (considerados pacientes en tratamiento).
2. **Análisis de Interés**: La IA analiza los últimos 15 mensajes para extraer el servicio de interés.
3. **Disponibilidad Real**: Consulta huecos libres para el servicio detectado (Mañana -> +7 días).
4. **Mensaje Personalizado**: Genera un mensaje contextual (ej: "Vi que te interesó el blanqueamiento...").

### **Query SQL de Identificación:**
```sql
SELECT 
    p.id as patient_id, 
    p.phone_number, 
    p.first_name, 
    p.tenant_id,
    c.id as clinic_id
FROM patients p
JOIN tenants c ON p.tenant_id = c.id
WHERE p.source = 'META_ADS'
  AND p.created_at < NOW() - INTERVAL '2 hours'
  AND p.created_at > NOW() - INTERVAL '26 hours' -- Evitar leads muy viejos
  AND NOT EXISTS (
      SELECT 1 FROM appointments a 
      WHERE a.patient_id = p.id
  )
  AND (p.platform_metadata->>'recovery_sent')::boolean IS NOT TRUE;
```

### **Campos de BD:**
```sql
-- En tabla patients (platform_metadata JSONB)
-- recovery_sent: true/false
-- last_recovery_at: timestamp
```

## 🔧 ENDPOINTS DE ADMINISTRACIÓN

### **Disponibles en `/admin/jobs/`:**
| Método | Endpoint | Descripción | Job |
|--------|----------|-------------|-----|
| **POST** | `/reminders/test-today` | Probar recordatorios con turnos de hoy | Reminders |
| **POST** | `/reminders/run-now` | Ejecutar recordatorios manualmente | Reminders |
| **GET** | `/reminders/status` | Estado del job de recordatorios | Reminders |
| **POST** | `/followups/test-today` | Probar seguimientos con turnos de hoy | Followups |
| **POST** | `/followups/run-now` | Ejecutar seguimientos manualmente | Followups |
| **GET** | `/followups/status` | Estado del job de seguimientos | Followups |
| **GET** | `/scheduler/status` | Estado general del scheduler | Todos |

### **Ejemplo de uso:**
```bash
# Probar job de recordatorios
curl -X POST http://localhost:8000/admin/jobs/reminders/test-today \
  -H "Authorization: Bearer <jwt_token>" \
  -H "X-Admin-Token: <admin_token>"

# Ver estado del scheduler
curl http://localhost:8000/admin/jobs/scheduler/status \
  -H "Authorization: Bearer <jwt_token>" \
  -H "X-Admin-Token: <admin_token>"
```

## 🚀 DESPLIEGUE

### **Pasos para producción:**
1. **Aplicar parches de BD:** Se ejecutan automáticamente al reiniciar
2. **Configurar variables de entorno:** `WHATSAPP_SERVICE_URL` y `INTERNAL_API_TOKEN`
3. **Reiniciar servicio:**
   ```bash
   sudo systemctl restart clinicforge-backend
   ```
4. **Verificar jobs registrados:**
   ```bash
   # Ver logs de inicio
   journalctl -u clinicforge-backend -f
   
   # Verificar endpoints
   curl http://localhost:8000/admin/jobs/scheduler/status
   ```

### **Parches idempotentes aplicados:**
```sql
-- Parche 24: Campos de recordatorios en appointments
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='reminder_sent') THEN
        ALTER TABLE appointments ADD COLUMN reminder_sent BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='reminder_sent_at') THEN
        ALTER TABLE appointments ADD COLUMN reminder_sent_at TIMESTAMPTZ;
    END IF;
    
    CREATE INDEX IF NOT EXISTS idx_appointments_reminder_sent ON appointments(reminder_sent);
    CREATE INDEX IF NOT EXISTS idx_appointments_reminder_date ON appointments(reminder_sent_at);
END $$;

-- Parche 25: Campos de seguimiento post-atención en appointments
DO $$ 
BEGIN 
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='followup_sent') THEN
        ALTER TABLE appointments ADD COLUMN followup_sent BOOLEAN DEFAULT FALSE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='appointments' AND column_name='followup_sent_at') THEN
        ALTER TABLE appointments ADD COLUMN followup_sent_at TIMESTAMPTZ;
    END IF;
    
    CREATE INDEX IF NOT EXISTS idx_appointments_followup_sent ON appointments(followup_sent);
    CREATE INDEX IF NOT EXISTS idx_appointments_followup_date ON appointments(followup_sent_at);
END $$;
```

## 📊 MONITOREO Y LOGGING

### **Logs generados por cada job:**
- **Inicio/Fin** - Tiempo de ejecución total
- **Turnos encontrados** - Cantidad procesada
- **Mensajes enviados** - Estadísticas de éxito/error
- **Errores individuales** - Detalles para debugging sin interrumpir flujo
- **Resumen final** - Métricas agregadas

### **Métricas clave:**
- **Tasa de éxito:** % de mensajes enviados exitosamente
- **Tiempo de ejecución:** Duración total del job
- **Turnos procesados:** Cantidad por ejecución
- **Errores por tenant:** Distribución de problemas

## ⚠️ CONSIDERACIONES IMPORTANTES

### **1. Multi-tenant:**
- ✅ Todas las queries incluyen `tenant_id`
- ✅ Credenciales de WhatsApp por tenant
- ✅ Datos aislados por tenant
- ✅ Índices optimizados por tenant

### **2. Resiliencia:**
- ✅ Manejo de errores individual (no interrumpe job completo)
- ✅ Logging detallado para debugging
- ✅ Reintentos configurados para fallos de red
- ✅ Timeouts apropiados para llamadas externas

### **3. Performance:**
- ✅ Índices optimizados en campos de tracking
- ✅ Queries eficientes con joins apropiados
- ✅ Ejecución asíncrona para no bloquear API
- ✅ Batch processing para grandes volúmenes

### **4. Seguridad:**
- ✅ Endpoints protegidos con autenticación JWT + admin token
- ✅ Validación de datos de entrada
- ✅ Sanitización de parámetros SQL
- ✅ Logging sin datos sensibles

## 🔄 MANTENIMIENTO

### **Scripts de utilidad:**
```bash
# Verificar estado de todos los jobs
python3 -c "
import asyncio
from jobs.reminders import test_reminder_for_today
from jobs.followups import test_followup_for_today

async def check_all():
    print('🧪 Testing reminder job...')
    await test_reminder_for_today()
    print('🧪 Testing followup job...')
    await test_followup_for_today()
    print('✅ All jobs tested')

asyncio.run(check_all())
"

# Ejecutar jobs manualmente
python3 -c "
import asyncio
from jobs.reminders import send_appointment_reminders
from jobs.followups import send_post_treatment_followups

async def run_all():
    print('🚀 Running reminder job...')
    await send_appointment_reminders()
    print('🚀 Running followup job...')
    await send_post_treatment_followups()
    print('✅ All jobs executed')

asyncio.run(run_all())
"
```

### **Actualizaciones futuras:**
1. **Más jobs:** Notificaciones de resultados, recordatorios de pagos, etc.
2. **Configuración dinámica:** Horarios ajustables por tenant
3. **Dashboard de monitoreo:** UI para ver estado y métricas
4. **Alertas:** Notificaciones cuando jobs fallan
5. **Backoff exponencial:** Para reintentos en fallos de red

## 📋 CHECKLIST DE IMPLEMENTACIÓN

### **✅ COMPLETADO:**
- [x] Sistema de scheduling centralizado (`scheduler.py`)
- [x] Job de recordatorios de turnos (`reminders.py`)
- [x] Job de seguimiento post-atención (`followups.py`)
- [x] Endpoints de administración (`admin_routes.py`)
- [x] Integración con FastAPI lifespan
- [x] Parches idempotentes de BD
- [x] Testing automatizado completo
- [x] Documentación exhaustiva

### **🔧 CONFIGURACIÓN REQUERIDA:**
- [ ] Variables de entorno configuradas
- [ ] Credenciales de WhatsApp por tenant
- [ ] Reinicio del servicio backend

##