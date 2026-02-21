# FASE 1: Evolución de Datos - Especificación Técnica

## 📢 Estado de Implementación (Feb 2026)

| Componente | Estado | Acción Realizada |
| :--- | :--- | :--- |
| **Esquema DB (004)** | ✅ 100% | Tablas creadas e indexadas. |
| **Modelos SQLALchemy** | ✅ 100% | `models_dental.py` implementado. |
| **Integración Tools** | ⚠️ 80% | Lógica backend lista; Sincronización GCal simulada. |
| **System Prompt** | ✅ 100% | Persona "Asistente Dental" activa en el Orchestrator. |

--- 

## 📋 Resumen Ejecutivo

Se han creado **6 nuevas tablas PostgreSQL** que transforman el backend de Tienda Nube en una plataforma dental, manteniendo la infraestructura multi-tenant de Nexus v3 intacta.

| Tabla | Propósito | Relaciones Clave |
|-------|-----------|------------------|
| `patients` | Almacenar datos de pacientes con anamnesis | tenant_id (multi-tenant) |
| `professionals` | Odontólogos disponibles con horarios configurables | tenant_id (multi-tenant), working_hours (JSONB) |
| `appointments` | Turnos sincronizados con Google Calendar | patient_id, professional_id, tenant_id |
| `clinical_records` | Historias clínicas con odontogramas JSONB | patient_id, professional_id, tenant_id |
| `accounting_transactions` | Pagos, OSDE, gastos | patient_id, appointment_id, tenant_id |
| `daily_cash_flow` | Reporte diario de caja | tenant_id |

---

## 🗂️ Estructura Jerárquica

```
Tenant (Dentalogic)
├── Professional (Dr. García)
│   ├── Appointment (2025-02-15 09:00)
│   │   └── Patient (Juan Pérez)
│   │       ├── Clinical Record (2025-01-20)
│   │       │   ├── Odontogram (JSONB)
│   │       │   ├── Treatments (JSONB)
│   │       │   └── Treatment Plan (JSONB)
│   │       └── Medical History (JSONB)
│   └── Chair 1 (Sillón)
│
└── Accounting
    ├── Transaction (Pago paciente $500)
    │   └── Insurance Claim (OSDE)
    └── Daily Cash Flow (2025-01-20)
```

---

## 🔑 Diseño de Claves

### `patients` Table
```sql
PRIMARY KEY: id (SERIAL)
UNIQUE: (tenant_id, phone_number) -- WhatsApp + Tenant
UNIQUE: (tenant_id, dni)           -- DNI + Tenant (previene duplicados nacionales)
FOREIGN KEY: tenant_id → tenants(id)
```

**Índices Críticos:**
- `(tenant_id, phone_number)` → Búsqueda rápida por WhatsApp
- `(tenant_id, dni)` → Validación de identidad
- `status` → Filtrado de pacientes activos

### `professionals` Table Extension
```sql
ALTER TABLE professionals ADD COLUMN working_hours JSONB;
```

**Estructura del JSON de Disponibilidad:**
El campo `working_hours` almacena la agenda semanal. Se inicializa por defecto con los valores de la clínica (`CLINIC_HOURS_START/END`).

```json
{
  "0": { "enabled": true, "slots": [{"start": "09:00", "end": "18:00"}] }, // Domingo (ejemplo: cerrado)
  "1": { "enabled": true, "slots": [{"start": "08:00", "end": "20:00"}] }, // Lunes
  "2": { "enabled": true, "slots": [{"start": "08:00", "end": "20:00"}] }, // Martes
  "3": { "enabled": true, "slots": [{"start": "08:00", "end": "20:00"}] }, // Miércoles
  "4": { "enabled": true, "slots": [{"start": "08:00", "end": "20:00"}] }, // Jueves
  "5": { "enabled": true, "slots": [{"start": "08:00", "end": "20:00"}] }, // Viernes
  "6": { "enabled": true, "slots": [{"start": "08:00", "end": "13:00"}] }  // Sábado
}
```
> [!NOTE]
> Las keys `0-6` corresponden a `dayOfWeek` de JavaScript (`0` = Domingo).

---

### `appointments` Table
```sql
PRIMARY KEY: id (UUID)
FOREIGN KEYS:
  - tenant_id → tenants(id)
  - patient_id → patients(id)
  - professional_id → professionals(id)
  - google_calendar_event_id (String, no FK - sincronización unidireccional)

ÍNDICES CRÍTICOS:
- (tenant_id, appointment_datetime) → Dashboard agenda
- (patient_id, status) → Búsqueda de citas del paciente
- (professional_id, appointment_datetime) → Agenda del profesional
- (urgency_level) → Filtrado de urgencias en dashboard
- (google_calendar_sync_status) → Reintento de sincronización
```

---

### `clinical_records` Table

**Odontograma (JSONB Example):**
```json
{
  "tooth_32": {
    "number": 32,
    "tooth_type": "molar",
    "status": "caries",
    "surfaces": {
      "occlusal": "caries",
      "mesial": "healthy",
      "distal": "healthy",
      "buccal": "healthy",
      "lingual": "healthy"
    },
    "color_code": "red",
    "notes": "Caries inicial, requiere tratamiento"
  },
  "tooth_11": {
    "number": 11,
    "tooth_type": "incisor",
    "status": "crowned",
    "treatment_date": "2024-06-15",
    "notes": "Corona de porcelana"
  }
}
```

**Treatments (JSONB Array):**
```json
[
  {
    "date": "2025-01-15",
    "type": "cleaning",
    "description": "Profilaxis con fluoruro",
    "teeth": [11, 12, 13, 14],
    "duration_minutes": 45,
    "cost": 500,
    "currency": "ARS",
    "insurance_covered": true,
    "professional_id": 1,
    "notes": "Paciente cooperador, sin complicaciones"
  },
  {
    "date": "2025-01-22",
    "type": "filling",
    "description": "Obturación amalgama en 32",
    "teeth": [32],
    "duration_minutes": 30,
    "cost": 800,
    "currency": "ARS",
    "insurance_covered": true,
    "professional_id": 1
  }
]
```

**Treatment Plan (JSONB):**
```json
{
  "created_date": "2025-01-15",
  "estimated_sessions": 4,
  "planned_treatments": [
    {
      "treatment": "Endodoncia",
      "teeth": [11],
      "estimated_cost": 3000,
      "priority": "high",
      "estimated_date": "2025-02-10"
    },
    {
      "treatment": "Corona 11",
      "teeth": [11],
      "estimated_cost": 4000,
      "priority": "high",
      "estimated_date": "2025-03-01"
    }
  ],
  "total_estimated_cost": 7000,
  "notes": "Plan consensuado con paciente"
}
```

---

## 📊 Integración con Nexus v3

### Multi-tenancy Preservation
Todas las tablas nuevas incluyen `tenant_id`:
```python
# En orchestrator_service/main.py, al procesar una solicitud:
current_tenant_id: ContextVar[Optional[int]] = ContextVar("current_tenant_id", default=None)

# Dentro de cualquier handler:
tenant_id = current_tenant_id.get()
# SELECT * FROM patients WHERE tenant_id = ? AND phone_number = ?
```

### Memory & Context Preservation
La infraestructura de memoria (RedisChatMessageHistory) se **mantiene sin cambios**:
- Conversación de 20 últimos mensajes en Redis
- Historial persistente en `chat_messages` (sin cambios)
- `human_override_until` sigue siendo válido (24h lockout)

### WhatsApp Integration
El flujo WhatsApp → Orchestrator → Respuesta se **mantiene idéntico**:
1. `whatsapp_service` recibe webhook de YCloud
2. Envía POST `/chat` a `orchestrator_service`
3. LangChain agent procesa con **nuevas herramientas dentales**

---

## 🔌 Cambios Necesarios en `orchestrator_service/main.py`

### Paso 1: Agregar Migración SQL
En el `lifespan` async context manager, agregar nueva migración:

```python
# En la lista migration_steps, después de la migración 003, agregar:
migration_steps = [
    # ... migración anterior ...
    # 4. Dental Phase 1 Schema
    open('/db/init/004_dental_phase1_schema.sql').read(),
]
```

### Paso 2: Nuevas Tools (Esqueletos Funcionales)

```python
from langchain.tools import tool

@tool
def check_availability(date_str: str, duration_minutes: int = 60) -> dict:
    """
    Consulta disponibilidad en Google Calendar.
    
    Args:
        date_str: "2025-02-15" (formato ISO)
        duration_minutes: Duración del turno
    
    Returns:
        {
            "available_slots": ["09:00", "10:00", "14:00"],
            "next_available": "2025-02-15 09:00"
        }
    """
    # TODO: Implementar integración con Google Calendar API
    return {"status": "not_implemented"}

@tool
def book_appointment(patient_phone: str, professional_id: int, datetime_str: str, appointment_type: str) -> dict:
    """
    Agenda un turno en Google Calendar + Database.
    
    Args:
        patient_phone: "+5491123456789"
        professional_id: 1 (Dr. García)
        datetime_str: "2025-02-15T09:00:00"
        appointment_type: "checkup" | "cleaning" | "treatment" | "emergency"
    
    Returns:
        {
            "success": true,
            "appointment_id": "uuid",
            "google_event_id": "calendar_event_id",
            "confirmation_message": "Tu turno está agendado para..."
        }
    """
    # TODO: Crear appointment en DB + Google Calendar
    return {"status": "not_implemented"}

@tool
def triage_urgency(user_message: str) -> dict:
    """
    Detecta urgencia en el mensaje del paciente (NLP).
    
    Args:
        user_message: Mensaje del usuario
    
    Returns:
        {
            "urgency_level": "low" | "normal" | "high" | "emergency",
            "reason": "Dolor agudo en molar superior",
            "recommended_action": "Agendar para hoy si es posible"
        }
    """
    # TODO: Implementar clasificación NLP simple
    # Por ahora: detectar palabras clave: "dolor", "urgencia", "emergencia", "sangrado"
    return {"urgency_level": "normal", "reason": "No urgency detected"}
```

### Paso 3: Actualizar `sys_template` de Persona

Cambiar de `"Antigua Persona"` a `"Asistente de la Dra. Laura Delgado"`:

```python
SYSTEM_PROMPT_DENTAL = """
Eres un Asistente Dental Profesional de una clínica odontológica en Argentina.

## Tono y Personalidad
- Cálido, profesional, empático
- Voseo argentino ("¿Cómo estás?", "Te recomiendo...", "Mirá...")
- PROHIBIDO: Lenguaje robótico, "estimado cliente"
- Experto en odontología básica, pero NUNCA diagnostiques

## Responsabilidades
1. **Agendar Turnos**: Usar check_availability() y book_appointment()
2. **Triaje**: Detectar urgencia con triage_urgency()
3. **Información**: Explicar procedimientos, cuidados post-tratamiento
4. **Recordatorios**: Avisar sobre turnos próximos

## Prohibiciones
- NO des diagnósticos precisos ("Tenés caries" → "Deberías venir para que lo vea el Dr.")
- NO alteres historias clínicas
- NO hagas tratamientos remotamente
- SIEMPRE remite urgencias ("Te vemos hoy mismo")

## CTA Obligatorio
Toda respuesta cierra con una acción:
- "¿Te parece agendar un turno?"
- "¿Querés que te lo anote para esta semana?"
- "Pasate por la clínica para una evaluación"
"""
```

---

## 🗄️ Estructura de Directorios Actualizada

```
orchestrator_service/
├── main.py (actualizar: agregar migración + nuevas tools)
├── admin_routes.py (sin cambios)
├── db.py (sin cambios)
└── requirements.txt (agregar: google-auth, google-auth-oauthlib)

db/
├── init/
│   ├── 001_schema.sql
│   ├── 002_platform_schema.sql
│   ├── 003_advanced_features.sql
│   └── 004_dental_phase1_schema.sql (NUEVO)
├── models_dental.py (NUEVO - SQLAlchemy ORM)
└── __init__.py

shared/
├── models.py (Agregar DTOs para Pacientes, Turnos, etc.)
```

---

## ✅ Checklist de Validación

- [ ] Archivo `004_dental_phase1_schema.sql` copiado a `db/init/`
- [ ] `models_dental.py` copiado a `db/`
- [ ] Migración agregada a `orchestrator_service/main.py` lifespan
- [ ] Tools esqueleto implementadas (check_availability, book_appointment, triage_urgency)
- [ ] sys_template actualizado con persona "Asistente Dental"
- [ ] Test: Conectar a DB y verificar que las tablas se crean
- [ ] Test: Enviar mensaje a WhatsApp y verificar que se procesa

---

## 📝 Próximos Pasos (FASE 2)

1. **Google Calendar Integration**
   - Implementar OAuth2 flow
   - Crear eventos en Google Calendar automáticamente
   - Sincronizar disponibilidad

2. **Frontend Refactoring**
   - Dashboard: Cambiar vista "Ventas" → "Flujo de Pacientes"
   - Agenda: CSS Grid con sillones (boxes)
   - Historias: SVG interactivo de odontograma

3. **System Prompt Avanzado**
   - Multi-idioma (Español/Inglés)
   - Context-aware responses (según historial médico)
   - Recomendaciones OSDE integradas

---

---

## 📊 Analítica y Business Intelligence (BI)

Para la toma de decisiones gerenciales, el sistema implementa un motor de analítica soberana que consume datos de pacientes, turnos e historias clínicas.

### 1. Lógica de Negocio: Ingresos Reales
A diferencia de los sistemas contables tradicionales, el dashboard de Dentalogic prioriza el **flujo de caja confirmado**.
- **Regla**: Solo se computan como ingresos las transacciones `completed` vinculadas a turnos con estado `completed` o `attended`.
- **Propósito**: Evitar inflar métricas con turnos agendados que nunca se concretaron.

### 2. Métricas de IA y Eficiencia
- **IA Conversaciones**: Hilos únicos identificados por `from_number` (pacientes distintos) que interactuaron en el rango. No confundir con volumen de mensajes.
- **IA Citas**: Turnos en `appointments` donde `source = 'ai'`, permitiendo medir el ROI del asistente virtual.
- **Triage Monitoring**: Seguimiento de `urgency_level` en tiempo real para optimización de agenda.

### 3. Filtrado por Rango Temporal
- **Semanal**: Últimos 7 días.
- **Mensual**: Últimos 30 días.
- Todas las agregaciones de base de datos deben soportar el parámetro `range` para garantizar consistencia visual en el dashboard.

---

**Fecha de Actualización:** 2026-02-08
**Versión:** 1.1 (Sovereign Analytics Integration)
**Estado:** Especificación Actualizada
