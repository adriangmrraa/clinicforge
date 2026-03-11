# Nexus Dental - Backend Documentation

## 📋 Descripción General

Backend del sistema de gestión para clínica dental, built with FastAPI + PostgreSQL + LangChain AI agent.

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                      WhatsApp (YCloud)                      │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 WhatsApp Service (Port 5005)                │
│  - Transcripción de audio (Whisper)                         │
│  - Forwarding de mensajes al Orchestrator                   │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│              Orchestrator Service (Port 8000)               │
│  - AI Agent (GPT-4o-mini)                                   │
│  - Tools: check_availability, book_appointment,            │
│            triage_urgency, derivhumano                      │
│  - Persistencia de chat en BD                              │
└─────────────────────────┬───────────────────────────────────┘
                          │
          ┌───────────────┼───────────────┐
          ▼               ▼               ▼
┌─────────────┐  ┌─────────────────┐  ┌─────────────┐
│ PostgreSQL  │  │  TiendaNube     │  │  Platform   │
│ (Puerto     │  │  Service        │  │  UI (Puerto │
│ 5432)       │  │  (Opcional)     │  │  3000)      │
└─────────────┘  └─────────────────┘  └─────────────┘
```

## 📁 Estructura del Proyecto

```
orchestrator_service/
├── main.py              # AI Agent + API endpoints
├── admin_routes.py      # CRUD endpoints (patients, appointments)
├── db.py                # Database connection + helpers
├── utils.py             # Utility functions
├── debug_creds.py       # Debug credentials
└── requirements.txt     # Python dependencies

db/
├── init/
│   └── dentalogic_schema.sql   # Unified schema (all tables)
└── models_dental.py    # SQLAlchemy models (shared)

shared/
├── models_dental.py     # Shared Pydantic models
└── models.py            # Base models
```

## 🚀 Inicio Rápido

### 1. Configuración

```bash
# Copiar variables de entorno
cp .env.example .env
# Editar .env con tus valores
```

### 2. Ejecutar Schema SQL

```bash
# En PostgreSQL
psql -d dental_clinic -f db/init/dentalogic_schema.sql
```

### 3. Iniciar Servidor

```bash
cd orchestrator_service
python main.py
# Servidor corriendo en http://localhost:8000
```

### 4. Verificar

```bash
# Health check
curl http://localhost:8000/health

# Verificación completa
python verify_backend_final.py
```

## 🔧 API Endpoints

### Chat Endpoint

```bash
POST /chat
Content-Type: application/json

{
  "message": "Hola, quiero agendar un turno",
  "phone": "+5491112345678",
  "name": "Juan Pérez"
}
```

### Admin Endpoints

| Method | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/admin/patients` | Listar pacientes |
| POST | `/admin/patients` | Crear paciente |
| GET | `/admin/appointments` | Listar turnos |
| POST | `/admin/appointments` | Crear turno manual |
| GET | `/admin/professionals` | Listar profesionales |
| PUT | `/admin/appointments/{id}/status` | Actualizar estado |
| GET | `/health` | Health check |

## 🤖 AI Agent Tools

| Tool | Descripción |
|------|-------------|
| `check_availability(date_query)` | Consulta disponibilidad de turnos |
| `book_appointment(date_time, treatment_reason)` | Registra un turno |
| `triage_urgency(symptoms)` | Clasifica urgencia de síntomas |
| `derivhumano(reason)` | Deriva a humano (bloquea bot 24h) |

## 🗄️ Base de Datos

### Tablas Principales

| Tabla | Descripción |
|-------|-------------|
| `patients` | Pacientes de la clínica |
| `professionals` | Profesionales/odontólogos |
| `appointments` | Turnos agendados |
| `appointment_statuses` | Estados de turnos |
| `chat_messages` | Historial de chat |
| `clinical_records` | Historia clínica |
| `inbound_messages` | Mensajes entrantes |

### Estados de Turno

| ID | Nombre | Descripción |
|----|--------|-------------|
| 1 | scheduled | Turno programado |
| 2 | confirmed | Turno confirmado |
| 3 | completed | Turno realizado |
| 4 | cancelled | Turno cancelado |
| 5 | no_show | Paciente no asistió |

## 🔒 Variables de Entorno

```env
# Base de datos
POSTGRES_DSN=postgresql://user:pass@localhost:5432/dental_clinic

# OpenAI
OPENAI_API_KEY=sk-...

# Clínica
CLINIC_NAME=Nexus Dental
CLINIC_LOCATION=Buenos Aires, Argentina

# WhatsApp (YCloud V2 API)
YCLOUD_API_KEY=...
YCLOUD_WEBHOOK_VERIFY_TOKEN=...
# (Opcional - Fallback Legacy) YCLOUD_WHATSAPP_NUMBER=... 
# Nota: El servidor usa el valor 'bot_phone_number' de la tabla 'tenants' preferentemente.

# Logging
LOG_LEVEL=INFO
```

## 🧪 Tests

```bash
# Ejecutar tests
pytest tests/

# Test rápido
pytest tests/test_quick.py -v
```

## 📦 Deployment

### Docker

```bash
# Build de todos los servicios
docker-compose build

# Iniciar servicios
docker-compose up -d

# Ver logs
docker-compose logs -f orchestrator
```

### EasyPanel

1. Crear servicio desde `orchestrator_service/`
2. Configurar variables de entorno
3. Deploy

## 📄 Documentación Adicional

- [Arquitectura](docs/01_architecture.md)
- [Variables de Entorno](docs/02_environment_variables.md)
- [Guía de Deployment](docs/03_deployment_guide.md)
- [Lógica del Agente](docs/04_agent_logic_and_persona.md)
- [Notas del Desarrollador](docs/05_developer_notes.md)
- [Template del Agente](docs/06_ai_prompt_template.md)
- [Workflow](docs/07_workflow_guide.md)
- [Historia de Troubleshooting](docs/08_troubleshooting_history.md)
- [Datos Específicos Dental](docs/09_fase1_dental_datos_especificacion.md)

## 🆘 Troubleshooting

### Error de conexión a BD
```
Verificar POSTGRES_DSN en .env
Ejecutar migraciones SQL
```

### El agente no responde
```
Revisar logs: docker-compose logs orchestrator
Verificar OPENAI_API_KEY
```

### Turnos no se crean
```
Verificar que existen profesionales activos
Revisar que las tablas existen
```

## 📝 Changelog

### v1.0.0 (2025-01)
- ✅ AI Agent con LangChain
- ✅ Tools dental (check_availability, book_appointment)
- ✅ CRUD endpoints
- ✅ Persistencia de chat en BD
- ✅ Sistema de derivación a humano (24h block)
- ✅ Integración WhatsApp via YCloud
