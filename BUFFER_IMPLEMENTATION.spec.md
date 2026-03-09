# BUFFER_IMPLEMENTATION.spec.md

## 1. Contexto y Objetivos

**Problema:** ClinicForge maneja múltiples canales (WhatsApp via YCloud, IG/FB via Chatwoot) pero el buffer de debounce actual (`relay.py`) es menos robusto comparado con la versión estabilizada en Dentalogic.
**Objetivo:** Implementar el "Sistema Robusto de Buffer/Debounce Multi-Canal" (tiempo de gracia para mensajes en ráfagas), procesando eventos atómicamente a través de un pipeline de Redis y manejando la concurrencia/redundancia mediante locks.

## 2. Requerimientos Técnicos

**Backend:**
- Reemplazar buffer actual de `whatsapp_service/main.py` y `relay.py` por el nuevo `BufferManager`.
- Implementar `AtomicRedisProcessor`.
- Acomodar el flujo de `chatwoot.py` para encolar mediante `BufferManager`.
- Implementar envío de mensajes en modo "Burbujas" (Bubble-by-bubble):
  - WhatsApp (YCloud): Refinar `send_sequence` para usar el delay configurado (ej. `BUBBLE_DELAY_SECONDS`) dinámicamente y el evento `typing_indicator`.
  - Chatwoot (IG/FB): Implementar llamadas a la API de Chatwoot para `typing_on`, aplicar delay y luego el envío del texto parcial por iteración.
  - Asegurar un límite de caracteres configurable (ej. 400 caracteres máximos por burbuja) para hacer una fragmentación inteligente (por párrafos o signos de puntuación).
- Implementar métricas Prometheus e integraciones de Health Check (`UnifiedHealthChecker`).

**Base de Datos / Multi-Tenancy:**
- Agregado de tabla `channel_configs` para dinámicamente cambiar parámetros por tenant/app.
- **Checkpoint de Soberanía:** "Validar que el `tenant_id` se extraiga de JWT (o BD mediante validación segura) y no de un parámetro de URL fácilmente manipulable. Toda consulta debe tener `WHERE tenant_id = $tenant_id` explícitamente."

**UI/UX (Para cumplimiento estricto aunque es un feature de Backend):**
- **Checkpoint de UI:** "Aplicar patrón de Scroll Isolation: `overflow-hidden` en contenedor padre, `min-h-0` en área de contenido en caso de generar interfaces de monitoreo de canales."

## 3. Criterios de Aceptación (Gherkin)

**Scenario: Recepción de múltiples mensajes rápidos (Ráfaga)**
*Given* que un usuario envía 3 mensajes por WhatsApp en un rango de 5 segundos
*When* los mensajes entran al Webhook de YCloud
*Then* el timer de Redis se debe reiniciar a los 11 segundos con cada nuevo mensaje
*And* el `BufferManager` debe enviar un único payload concatenado al orquestador tras el silencio de 11 segundos.

**Scenario: Resiliencia ante caídas de orquestación**
*Given* un buffer que debe procesar los mensajes encolados
*When* la solicitud al Orquestador falla
*Then* el sistema debe realizar un re-intento con backoff exponencial
*And* el lock del buffer se debe mantener hasta completar la entrega exitosa o fallar exhaustivamente.

**Scenario: Envío de respuestas largas en múltiples burbujas**
*Given* que el sistema tiene una respuesta muy larga (mayor a 400 caracteres) que enviar
*When* procesa el contenido para enviarlo al usuario
*Then* debe dividir el texto lógico en oraciones/párrafos más pequeños de no más de 400 caracteres (haciendo el corte inteligentemente en un espacio o signo de puntuación)
*And* debe enviar estos fragmentos como burbujas consecutivas.
*And* debe haber un delay configurado (`bubble_delay`, ej. 3-4 segundos) entre burbujas, acompañado del envío de eventos "typing_on" (escribiendo) soportados por el proveedor (YCloud para WhatsApp y API nativa de Chatwoot para Instagram/Facebook).
*And* asegurar que no se envíe un `typing_on` si el canal no lo soporta o está explícitamente deshabilitado (`typing_indicator: false` en `channel_configs`).

## 4. Esquema de Datos

**Tabla: `channel_configs`**
- `id`: SERIAL PRIMARY KEY
- `tenant_id`: INTEGER NOT NULL (FK a tenants)
- `provider`: VARCHAR(50) NOT NULL ('whatsapp', 'chatwoot')
- `channel`: VARCHAR(50)
- `config`: JSONB NOT NULL DEFAULT '{}'
- **Constraint:** UNIQUE(tenant_id, provider, channel)

## 5. Riesgos y Mitigación

- **Sobrecarga de Redis:** Implementar TTL exactos y limpieza forzada de locks caídos.
- **Sobrecarga de Redis:** Implementar TTL exactos y limpieza forzada de locks caídos.
- **Falta de Memoria:** Monitorear métricas de Redis.
- **Tokens/Credenciales Expiradas:** Capturar excepciones de llamadas HTTP al YCloud API y reportarlo al log estructurado, forzando fallbacks a configuración estática de ser necesario.

## 6. Clarificaciones y Reglas de Negocio (Confirmadas)

> [!NOTE]
> Reglas de negocio confirmadas para la implementación de las burbujas y casos de borde.

1. **Timeout del Typing Indicator (Pings de Escribiendo):** Implementaremos pings periódicos de `typing_on` mientas el Orquestador o la IA tarden más de 10-15 segundos. Se validará que esto funcione de manera estable tanto en YCloud como en la API de Chatwoot sin romper el flujo.
2. **Interrupción de la IA (Double-typing):** Si la IA está en medio de la secuencia de enviar las burbujas y el usuario manda un mensaje nuevo, la IA **TERMINA** de mandar la respuesta que estaba enviando (la secuencia programada), y luego el nuevo mensaje entrante iniciará su propio ciclo normal de buffer y respuesta. No se aborta la respuesta en curso.
3. **Manejo Mixto (Texto + Imagen):** En el orden de prioridad, si la IA responde con texto y una imagen al mismo tiempo, **primero se enviará la imagen** (si existiese) y luego las burbujas de texto.
4. **Respuesta Siempre Activa (Override):** El sistema debe responder SIEMPRE, a menos que el estado explícito de la conversación indique que el `human override` (bot apagado para ese paciente) está activo. No existen decisiones silenciosas de "no responder" por parte de la IA.
5. **Configuración Unificada (Valores por defecto):** Usaremos una configuración por defecto centralizada y unificada (ej. en las variables de entorno o un único registro DB de fallback). Todos los canales leerán de este único lugar para facilitar el mantenimiento.
