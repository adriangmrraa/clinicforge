# Spec 14: Estabilización Interfaz de Chat (Socket & Multi-canal)

## 1. Contexto y Objetivos
**Objetivo:** Asegurar una experiencia de chat en tiempo real fiable para todos los canales (WhatsApp, Instagram, Facebook) y corregir errores de renderizado y deduplicación.
**Problemas:** 
- Los mensajes de IG/FB no aparecen en tiempo real (falta SocketIO).
- La deduplicación por nombre oculta conversaciones legítimas.
- Las imágenes de perfil de Meta fallan al cargarse directamente.

## 2. Requerimientos Técnicos

### Backend (Orchestrator)
- **Socket.IO:** Exponer instancia `sio` en `app.state` para acceso global.
- **Webhooks:** Emitir evento `NEW_MESSAGE` en `_process_canonical_messages` para todos los canales.
- **Media Proxy:** Firmar y proxear `avatar_url` de Meta para evitar bloqueos del CDN/expiración.

### Frontend (React)
- **Deduplicación:** Basar la unicidad estrictamente en `external_user_id` (y `channel`), eliminando el filtro por nombre.
- **Avatar Handling:** Implementar proxy en el backend y fallback en el frontend (iniciales si la imagen falla).
- **Paridad YCloud:** Asegurar que los mensajes de YCloud sigan usando el flujo de SocketIO existente.

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Recepción de mensaje IG/FB en tiempo real
  Given la vista de chats abierta 
  When llega un webhook de Instagram
  Then el mensaje aparece instantáneamente en el sidebar y ventana de chat sin refrescar

Scenario: Múltiples contactos con mismo nombre (IG)
  Given dos contactos de IG llamados "Juan Pérez" con distintos IDs
  When se carga el summary de chats
  Then ambos aparecen como ítems separados en la lista

Scenario: Avatar de Meta expirado
  Given un avatar_url de Meta que devuelve 403 o expira
  When se renderiza el ítem del chat
  Then se muestra el avatar proxidado o las iniciales del usuario como fallback
```

## 4. Riesgos y Mitigación
- **Riesgo:** Sobrecarga de SocketIO con muchos eventos.
- **Mitigación:** Emitir solo datos esenciales de resumen y mensaje.
- **Riesgo:** Alta latencia en el proxy de imágenes.
- **Mitigación:** El proxy usa streaming y redirecciones eficientes.

- [x] **Estrategia de Deduplicación**: Se mantienen separadas por canal. La unicidad se basa en el ID/Username de cada plataforma. La asociación multi-canal es una función secundaria en la ficha del paciente.
- [x] **Manejo de Avatares**: Si el proxy falla o no hay foto, se muestran iniciales con el color de fondo del canal (WhatsApp: Verde, Facebook: Azul, Instagram: Rosa/Morado).
- [x] **Notificaciones Sonoras**: Habilitar sonidos para todos los canales para unificar la experiencia.
- [x] **Volumen de Historial**: 20 mensajes iniciales en la interfaz de usuario.
- [x] **Estado de Lectura**: CRÍTICO. Se implementará `last_read_at` en `chat_conversations` para persistir el estado de lectura y evitar que las notificaciones reaparezcan tras refrescar la lista.
- [x] **Aislamiento por Canal**: Todas las consultas de mensajes y conteos DEBEN filtrar por `channel` para evitar colisiones entre IDs de redes sociales y números de teléfono.
- [x] **Ventana de 24h**: Estrictamente 24 horas desde el último mensaje del usuario, independientemente del cambio de día. Se debe refrescar el estado visual al recibir mensajes que abran o cierren esta ventana.
- [x] **Paridad de Funcionalidades**: Las conversaciones de Chatwoot deben heredar TODAS las funciones de YCloud: contexto clínico (desktop/mobile), scroll automático al final, integración con base de datos de pacientes y agendamiento.
- [x] **Notificaciones**: Sin distinción entre modo manual e IA; todas deben sonar y mostrar badge de la misma forma.

## 5. Clarificaciones (Workflow /clarify)
- **C1**: El estado "leído" se persiste en DB mediante `last_read_at`.
- **C2**: El `unread_count` solo cuenta mensajes del usuario posteriores a `last_read_at` y al último mensaje del asistente.
- **C3**: La ventana de 24h se calcula matemáticamente por segundos, no por fecha calendario.
