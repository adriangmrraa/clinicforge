---
name: "Omnichannel Chat Operator"
description: "Especialista en gestión de conversaciones vía WhatsApp (YCloud) para Dentalogic."
trigger: "chats, conversaciones, mensajes, whatsapp, human override, handoff"
scope: "CHATS"
auto-invoke: true
---

# Omnichannel Chat Operator - Dentalogic

## 1. Arquitectura de Comunicación (WhatsApp via YCloud)
Dentalogic centraliza toda la comunicación en WhatsApp utilizando el proveedor **YCloud**.

### Flujo de Recepción:
1. **YCloud**: Envía Webhook a `whatsapp_service/webhook/ycloud`.
2. **Validación**: HMAC-SHA256 usando `YCLOUD_WEBHOOK_SECRET`.
3. **Forwarding**: El `whatsapp_service` limpia el payload y lo envía al orquestador.

## 2. Gestión de Human Handoff (Intervención Humana)
La IA detecta automáticamente cuándo un paciente pide hablar con una persona o si la situación es crítica.

### Token de Activación:
`HUMAN_HANDOFF_REQUESTED`

Cuando el orquestador detecta este token en la respuesta de la IA:
1. Activa el "Chat Lock" (bloqueo de IA) por 24 horas.
2. Envía una notificación vía email/notificación administrativa.
3. El dashboard resalta la conversación en rojo.

## 3. Seguridad de Webhooks
**REGLA DE ORO**: Nunca procesar un mensaje de WhatsApp sin validar su firma.

### Protocolo de Verificación:
```python
# whatsapp_service/main.py
signed_payload = f"{timestamp}.{raw_body}"
expected = hmac.new(secret, signed_payload, hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, signature):
    raise HTTPException(401, "Invalid signature")
```

## 4. Envío de Mensajes
Todas las respuestas de gestión manual desde el Dashboard deben enviarse vía:
`POST /admin/whatsapp/send`

El orquestador se encarga de llamar al `ycloud_client.py` en el `whatsapp_service` para el envío final.

## 5. Estándares de Interfaz para el Operador (UX)
Para garantizar la eficiencia del operador humano en Dentalogic:
- **Vista Rígida**: La cabecera del chat y el área de composición de mensajes deben permanecer fijos.
- **Scroll de Mensajes**: El historial debe tener scroll propio e independiente (Caja de mensajes).
- **Carga de Historial**: Usar el botón de "Cargar más" para acceder a mensajes antiguos sin perder el contexto de la conversación actual.

## 5. Checklist de Operación
- [ ] ¿El `YCLOUD_WEBHOOK_SECRET` está configurado correctamente en el entorno?
- [ ] ¿El triaje IA de "Gala" está activado en el orquestador?
- [ ] ¿Las notificaciones de handoff están configuradas para alertar al personal?
- [ ] ¿El Dashboard muestra los estados de entrega (sent, delivered, read) devueltos por YCloud?
