---
description: Workflow para solucionar bugs en Dentalogic
---

# 🐛 Bug Fix Workflow - Dentalogic

Proceso estandarizado para diagnosticar y solucionar errores en el sistema de gestión dental.

## 🛠 Skills Recomendadas
- **Backend/Seguridad**: [Backend_Sovereign](../skills/Backend_Sovereign/SKILL.md)
- **Frontend/UI**: [Frontend_Nexus](../skills/Frontend_Nexus/SKILL.md)
- **WhatsApp**: [Omnichannel_Chat_Operator](../skills/Omnichannel_Chat_Operator/SKILL.md)

## Fase 1: Diagnóstico (Evidence)

### 1.1. Revisar Logs
```bash
# Logs del orquestador (Principal)
docker logs orchestrator_service --tail 100

# Logs del servicio de WhatsApp (Webhooks YCloud)
docker logs whatsapp_service --tail 100
```

### 1.2. Verificar Integraciones
- [ ] **Google Calendar**: ¿El Service Account tiene acceso al calendario?
- [ ] **YCloud**: ¿El `YCLOUD_WEBHOOK_SECRET` es correcto?
- [ ] **Base de Datos**: `db.py` conectado al pool de PostgreSQL.

## Fase 2: Reproducción (Isolation)

### 2.1. Test de Integración
Si el error es en una tool (ej: `check_availability`), crear un test en `tests/` que llame a la función directamente usando el pool de test.

## Fase 3: Solución (Fix)

### 3.1. Patrones de Arreglo
- **Errores de Cita**: Verificar formato ISO en `gcal_service.py`.
- **Errores de IA**: Ajustar el prompt en `main.py` (Protocolo Gala).
- **Errores de Webhook**: Verificar validación HMAC en `whatsapp_service/main.py`.

## Fase 4: Verificación (Verify)
- [ ] Ejecutar `pytest` si hay tests disponibles.
- [ ] Verificar sincronización con Google Calendar tras el fix.
- [ ] Realizar smoke test desde un dispositivo móvil (Responsive check).
