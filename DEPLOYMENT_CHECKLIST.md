# ✅ DEPLOYMENT CHECKLIST - Backend Final

## Estado Actual 

✅ **main.py:** Actualizado con:
- Lifespan context manager (db.connect/disconnect)
- Chat history persistence (get_chat_history + append_chat_message)
- 4 helper functions (parse_date, parse_datetime, generate_free_slots, get_next_weekday)
- 4 dental tools con BD queries (check_availability, book_appointment, triage_urgency, derivhumano)
- System prompt v8 con reglas argentinas

✅ **admin_routes.py:** Actualizado con:
- FK validation (professional_id, patient_id)
- Specific error handling (asyncpg.UniqueViolationError, ForeignKeyViolationError)
- CRUD endpoints para pacientes, turnos, registros clínicos

✅ **requirements.txt:** Agregado `python-dateutil`

⏳ **Pasos restantes:** 3 (15 min total)

---

## 📋 PASO 1: INSTALAR DEPENDENCIAS

### Opción A: Windows PowerShell
```powershell
cd "c:\Users\Asus\Downloads\Clinica Dental"
python -m pip install --upgrade pip
python -m pip install -r orchestrator_service/requirements.txt
```

### Opción B: Windows CMD
```cmd
cd c:\Users\Asus\Downloads\Clinica Dental
python -m pip install -r orchestrator_service/requirements.txt
```

**Tiempo esperado:** 3-5 min

**Verificación:**
```powershell
python -c "from dateutil.parser import parse; print('✅ python-dateutil OK')"
```

---

## 📋 PASO 2: EJECUTAR SCHEMA SQL

### Opción A: Command Line (RECOMENDADO)

Ejecuta el schema unificado:
```powershell
cd "c:\Users\Asus\Downloads\Clinica Dental"
psql -U postgres -d postgres -c "CREATE DATABASE clinica_dental;"
psql -U postgres -d clinica_dental -f db/init/dentalogic_schema.sql
```

**Qué hace:**
1. ✅ Crea BD `clinica_dental` si no existe
2. ✅ Ejecuta dentalogic_schema.sql (schema unificado completo)
3. ✅ Verifica automáticamente la creación de tablas

**Tiempo esperado:** 2-3 min

### Opción B: Manual con psql

```powershell
# 1. Conectar
psql -U postgres -h localhost

# 2. En el prompt de psql:
CREATE DATABASE clinica_dental;
\c clinica_dental

# 3. Ejecutar schema unificado
\i 'db/init/dentalogic_schema.sql'

# 4. Verificar
\dt  # Debe mostrar 14+ tablas
```

**Tiempo esperado:** 5 min

---

## 📋 PASO 3: VALIDAR SINTAXIS Y CORRER SERVIDOR LOCAL

### 3.1 Validar Python Syntax

```powershell
cd "c:\Users\Asus\Downloads\Clinica Dental"

# Validar main.py
python -m py_compile orchestrator_service/main.py
if ($?) { Write-Host "✅ main.py OK" } else { Write-Host "❌ Error en main.py" }

# Validar admin_routes.py
python -m py_compile orchestrator_service/admin_routes.py
if ($?) { Write-Host "✅ admin_routes.py OK" } else { Write-Host "❌ Error en admin_routes.py" }
```

**Resultado esperado:** Ambos archivos OK (sin output = sin errores)

### 3.2 Configurar Variables de Entorno

Crea archivo `.env` en la raíz:

```bash
# DB
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password_here
POSTGRES_DB=clinica_dental

# OpenAI
OPENAI_API_KEY=sk-...your-key...

# Clinic Config
CLINIC_NAME=Mi Clínica Dental
CLINIC_LOCATION=Buenos Aires
CLINIC_PHONE=+5491111111
CLINIC_EMAIL=contact@clinica.ar

# WhatsApp (YCloud - deshabilitado por ahora)
YCLOUD_API_KEY=test_key
YCLOUD_WEBHOOK_URL=http://localhost:3000/webhook

# Log Level
LOG_LEVEL=INFO

# API Port
API_PORT=8000
```

### 3.3 Iniciar Servidor Local

```powershell
cd "c:\Users\Asus\Downloads\Clinica Dental"

# Opción A: Con uvicorn directo
python -m uvicorn orchestrator_service.main:app --host 0.0.0.0 --port 8000 --reload

# Opción B: En background (PowerShell)
Start-Process -NoNewWindow -FilePath "python" -ArgumentList `
  "-m uvicorn orchestrator_service.main:app --host 0.0.0.0 --port 8000 --reload"
```

**Resultado esperado:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

---

## 📋 PASO 4: PRUEBAS RÁPIDAS

### 4.1 Test Chat Endpoint

```powershell
# Prueba simple (PowerShell)
$body = @{
    message = "Hola, quiero agendar un turno"
    phone = "5491111111"
} | ConvertTo-Json

Invoke-WebRequest -Uri "http://localhost:8000/chat" `
  -Method POST `
  -Headers @{"Content-Type"="application/json"} `
  -Body $body | Select-Object -ExpandProperty Content
```

**Resultado esperado:**
```json
{
  "output": "¡Hola! 👋 Te ayudaré a agendar un turno...",
  "status": "ok"
}
```

### 4.2 Test Admin CRUD

```powershell
# Listar pacientes (requiere token)
Invoke-WebRequest -Uri "http://localhost:8000/admin/patients?search=Juan" `
  -Headers @{"X-Admin-Token"="admin-secret-token"} | Select-Object -ExpandProperty Content

# Listar turnos
Invoke-WebRequest -Uri "http://localhost:8000/admin/appointments" `
  -Headers @{"X-Admin-Token"="admin-secret-token"} | Select-Object -ExpandProperty Content

# Listar profesionales
Invoke-WebRequest -Uri "http://localhost:8000/admin/professionals" `
  -Headers @{"X-Admin-Token"="admin-secret-token"} | Select-Object -ExpandProperty Content
```

### 4.3 OpenAPI Documentation

Abre en navegador:
```
http://localhost:8000/docs
```

Deberías ver Swagger UI con todos los endpoints documentados.

---

## 📋 PASO 5: VERIFICACIÓN FINAL

### Checklist de Confirmación

- [ ] `python -m pip install -r orchestrator_service/requirements.txt` ejecutado sin errores
- [ ] `dentalogic_schema.sql` ejecutado → Todas las tablas creadas
- [ ] `python -m py_compile orchestrator_service/main.py` sin errores
- [ ] `python -m py_compile orchestrator_service/admin_routes.py` sin errores
- [ ] Servidor uvicorn inicia sin errores (startup complete)
- [ ] POST /chat responde con JSON válido
- [ ] GET /admin/patients responde (con token válido)
- [ ] http://localhost:8000/docs muestra swagger

### Si falla algo:

**Error: `ModuleNotFoundError: No module named 'dateutil'`**
```powershell
python -m pip install python-dateutil
```

**Error: `Connection refused` en PostgreSQL**
```powershell
# Verificar que PostgreSQL está corriendo
net start postgresql-x64-XX  # Ajusta el número de versión

# O desde PowerShell
Start-Service -Name postgresql-x64-*
```

**Error: `foreign key violation` al crear turnos**
→ Significa que falta un profesional. Inserta uno:
```sql
INSERT INTO professionals (id, name, specialty, is_active)
VALUES (1, 'Dr. Merlo', 'General', true);
```

---

## 🎯 PRÓXIMO PASO: FRONTEND

Una vez que **todos** los pasos anteriores pasen:

```powershell
# El backend está listo para recibir requests del frontend
# La documentación OpenAPI está en: http://localhost:8000/docs
```

Frontend puede conectar a:
- **Chat:** POST http://localhost:8000/chat
- **Admin Panel:** GET/POST http://localhost:8000/admin/*

Continuar con: `FRONTEND_SETUP.md` (será creado)

---

## 📊 Timeline

| Paso | Acción | Tiempo | Estado |
|------|--------|--------|--------|
| 1 | Instalar deps | 5 min | ⏳ |
| 2 | SQL migrations | 3 min | ⏳ |
| 3 | Validar sintaxis | 2 min | ⏳ |
| 4 | Correr servidor | 1 min | ⏳ |
| 5 | Tests rápidos | 3 min | ⏳ |
| **TOTAL** | | **14 min** | ⏳ |

**Objetivo:** Backend 100% funcional en ~15 minutos ✅

