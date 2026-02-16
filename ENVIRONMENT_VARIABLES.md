# Dentalogic - Environment Variables Reference

Quick reference for EasyPanel deployment.

## Service Ports

| Service       | Internal Port |
|---------------|---------------|
| orchestrator  | 8000          |
| bff_service   | 8001          |
| whatsapp      | 8002          |
| frontend      | 3000          |
| postgres      | 5432          |
| redis         | 6379          |

## Internal Service URLs

```bash
ORCHESTRATOR_SERVICE_URL=http://orchestrator:8000
WHATSAPP_SERVICE_URL=http://whatsapp:8002
BFF_SERVICE_URL=http://bff_service:8001
```

## Core Variables (All Backend Services)

```bash
POSTGRES_DSN=postgresql+asyncpg://postgres:password@postgres:5432/dentalogic
REDIS_URL=redis://redis:6379/0
INTERNAL_API_TOKEN=secret-internal-token-2024
LOG_LEVEL=INFO
```

## orchestrator (8000)

```bash
OPENAI_API_KEY=sk-proj-...
CLINIC_NAME=Clínica Dental
CLINIC_LOCATION=Buenos Aires, Argentina
GOOGLE_CREDENTIALS={"type":"service_account",...}
GOOGLE_CALENDAR_ID=primary
YCLOUD_API_KEY=...
YCLOUD_WEBHOOK_SECRET=...
WHATSAPP_SERVICE_URL=http://whatsapp:8002
ADMIN_TOKEN=admin-secret-token
CORS_ALLOWED_ORIGINS=https://dentalogic-frontend.ugwrjq.easypanel.host,http://localhost:3000

# SMTP Configuration (Human Handoff)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASS=tu-app-password
SMTP_SENDER=tu-email@gmail.com
NOTIFICATIONS_EMAIL=doctor@clinica.com
```

## whatsapp (8002)

```bash
OPENAI_API_KEY=sk-proj-...
YCLOUD_API_KEY=...
YCLOUD_WEBHOOK_SECRET=...
ORCHESTRATOR_SERVICE_URL=http://orchestrator:8000
INTERNAL_API_TOKEN=secret-internal-token-2024
```

## bff_service (8001)

```bash
POSTGRES_DSN=postgresql+asyncpg://...
REDIS_URL=redis://redis:6379/0
ORCHESTRATOR_SERVICE_URL=http://orchestrator:8000
WHATSAPP_SERVICE_URL=http://whatsapp:8002
INTERNAL_API_TOKEN=secret-internal-token-2024
ADMIN_TOKEN=admin-secret-token
JWT_SECRET=your-jwt-secret
```

## frontend (3000)

```bash
VITE_API_URL=https://dentalogic-orchestrator.ugwrjq.easypanel.host
VITE_BFF_URL=https://dentalogic-bff.ugwrjq.easypanel.host
NODE_ENV=production
```
