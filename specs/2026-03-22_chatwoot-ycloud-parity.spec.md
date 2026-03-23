# Paridad Chatwoot ↔ YCloud — Estabilizacion de Canales IG/FB

> Origen: Los canales de Instagram y Facebook via Chatwoot ya funcionan (mensajes llegan, agente responde, respuesta llega al usuario). Pero hay funciones que YCloud (WhatsApp) tiene y Chatwoot no — esta spec cierra esas brechas sin romper nada existente.

## 1. Contexto y Objetivos

- **Problema:** El adapter de Chatwoot normaliza mensajes de texto correctamente pero tiene gaps en media (audios, imagenes, documentos), typing indicators, y visualizacion en la UI de Chats. YCloud tiene un flujo maduro que gestiona todo esto.

- **Solucion:** Cerrar las brechas puntuales entre los dos adapters, aprovechando que ambos ya pasan por el mismo pipeline (`_process_canonical_messages`). Los cambios son quirurgicos — no se reestructura nada.

- **Restriccion CRITICA:** NO romper nada de lo que ya funciona:
  - YCloud WhatsApp: texto, audio, imagenes, transcripcion, ficha clinica ✓
  - Chatwoot IG/FB: texto, agente responde, respuesta llega via Chatwoot API ✓
  - Meta Direct FB: texto, agente responde, respuesta via Graph API ✓
  - Token tracking ✓
  - Bubbles con delay ✓
  - Deduplicacion ✓

## 2. Brechas Identificadas

### B1. Typing Indicator en Chatwoot (`send_action` faltante)

**Estado actual:** `ResponseSender` llama `client.send_action(account_id, cw_conv_id, "typing_on")` pero `ChatwootClient` no tiene ese metodo → warning en logs.

**Fix:** Agregar metodo `send_action` a `ChatwootClient`.

**Archivo:** `orchestrator_service/chatwoot_client.py`

```python
async def send_action(self, account_id, conversation_id, action: str):
    """Send typing indicator (typing_on, typing_off) to Chatwoot."""
    url = f"{self.base_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/toggle_typing_status"
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(url, json={"typing_status": action}, headers=self.headers)
        return resp.json() if resp.status_code == 200 else {}
```

**Riesgo:** Ninguno. Si el endpoint de Chatwoot no existe o falla, el warning ya esta manejado con try/except.

---

### B2. Adjuntos de Chatwoot: URLs externas que expiran

**Estado actual:** El adapter de Chatwoot extrae URLs de adjuntos (`data_url` o `source_url`). Estas URLs de Chatwoot pueden expirar. El pipeline (`_process_canonical_messages`) ya tiene logica para descargar media y persistirla localmente (lineas 326-351 de `chat_webhooks.py`), pero depende de que la URL no haya expirado al momento de la descarga.

**Fix:** No se necesita cambio de codigo. El pipeline ya descarga media inmediatamente al recibirla. Si la URL expira despues, la copia local persiste. El `_extract_media` del ChatwootAdapter ya extrae correctamente imagenes, audios, videos y documentos.

**Verificacion necesaria:** Enviar una imagen por Instagram via Chatwoot y verificar que:
1. El `content_attributes` del mensaje tiene el adjunto con URL local
2. El archivo existe en `/media/{tenant_id}/`

---

### B3. Transcripcion de Audio (Whisper) para Chatwoot

**Estado actual:** El pipeline ya dispara `transcribe_audio_url` para `MediaType.AUDIO` (linea 313 de `chat_webhooks.py`). El `ChatwootAdapter._extract_media` ya detecta audios correctamente (incluso fake videos que son audio). La transcripcion deberia funcionar si la URL del audio es accesible.

**Posible gap:** Las URLs de audio de Chatwoot (Instagram/Facebook) pueden requerir headers de autorizacion para descargar. El `whisper_service` descarga la URL directamente — si Chatwoot requiere auth, fallaria silenciosamente.

**Fix:** Verificar si `whisper_service.transcribe_audio_url` puede descargar URLs de Chatwoot. Si no, agregar header `api_access_token` al download.

**Archivo a verificar:** `orchestrator_service/services/whisper_service.py`

---

### B4. Guardado en Ficha Clinica (`patient_documents`) para IG/FB

**Estado actual:** El pipeline guarda imagenes/documentos en `patient_documents` (lineas 354-413 de `chat_webhooks.py`) pero busca al paciente por `phone_number`:

```python
patient_row = await pool.fetchrow("""
    SELECT id FROM patients
    WHERE tenant_id = $1 AND (
        phone_number = $2 OR phone_number = $3 OR
        external_ids @> $4::jsonb OR external_ids @> $5::jsonb
    )
""", tenant_id, msg.external_user_id, clean_ext_id, ...)
```

Para Chatwoot IG/FB, `external_user_id` es un username (ej: `dra.lauradelgado`) o un ID numerico de Chatwoot (ej: `1`), no un telefono. La query no encontrara al paciente.

**Fix:** Agregar busqueda por `instagram_psid` y `facebook_psid` como fallback, y tambien por `name` como ultimo recurso.

**Archivo:** `orchestrator_service/routes/chat_webhooks.py` (lineas 357-370)

**Cambio:**
```python
patient_row = await pool.fetchrow("""
    SELECT id FROM patients
    WHERE tenant_id = $1 AND (
        phone_number = $2 OR
        phone_number = $3 OR
        instagram_psid = $2 OR
        facebook_psid = $2 OR
        external_ids @> $4::jsonb OR
        external_ids @> $5::jsonb
    )
    LIMIT 1
""", tenant_id, msg.external_user_id, clean_ext_id,
    json.dumps({"whatsapp_id": msg.external_user_id}),
    json.dumps({"whatsapp_id": clean_ext_id}))
```

**Riesgo:** Bajo. Solo agrega condiciones OR al WHERE. No afecta resultados existentes.

---

### B5. Visualizacion de Adjuntos en UI de Chats

**Estado actual:** La UI (`ChatsView.tsx`) renderiza mensajes pero necesita verificar que los adjuntos de Chatwoot se muestren correctamente (imagenes inline, reproductor de audio, links de documentos).

**Posible gap:** Los `content_attributes` se guardan como JSON string con el formato:
```json
[{"type": "image", "url": "/media/1/abc.jpg", "file_name": "image.jpg"}]
```

La UI debe parsear esto y renderizar segun tipo. Verificar que el componente de mensajes ya maneja esto.

**Archivo a verificar:** `frontend_react/src/views/ChatsView.tsx` — seccion de renderizado de mensajes.

---

### B6. Avatar del Contacto en Lista de Chats

**Estado actual:** Para YCloud/WhatsApp, el avatar se obtiene del perfil de WhatsApp. Para Chatwoot IG/FB, el avatar viene en `sender.avatar_url` o `sender.thumbnail` del webhook.

**Posible gap:** El avatar puede no persistirse correctamente en `chat_conversations.meta` porque el `get_or_create_conversation` usa `avatar_url` como parametro pero la UI puede leerlo de otro campo.

**Verificacion:** Revisar si la UI muestra avatares para conversaciones de Chatwoot. Si no, verificar que `meta.customer_avatar` o el campo directo `avatar_url` se estan seteando.

---

### B7. Nombre del Contacto (external_user_id numerico vs nombre real)

**Estado actual:** Para Chatwoot IG/FB, `external_user_id` puede ser un ID numerico (`1`, `2`) del contacto de Chatwoot en vez del username o telefono. Esto aparece debajo del nombre en la UI.

**Fix:** El `display_name` del `CanonicalMessage` se extrae correctamente del webhook (linea 56 de `chatwoot.py`: `sender.name`). El problema es que `external_user_id` (que se muestra como subtitulo) es un ID numerico.

**Solucion en UI:** No mostrar el `external_user_id` si es un numero corto (1-4 digitos). O mostrar el `channel` (Instagram/Facebook) en su lugar.

**Archivo:** `frontend_react/src/views/ChatsView.tsx` — donde se renderiza el subtitulo de cada conversacion.

---

## 3. Logica de Negocio (Invariantes)

### NO se cambia:
- Pipeline de `_process_canonical_messages` (ya maneja todo correctamente)
- `BufferManager` (ya tiene defaults para chatwoot)
- `ResponseSender` (ya envia bubbles con delay para chatwoot)
- Deduplicacion (ya funciona)
- Token tracking (ya funciona)
- `ChatwootAdapter.normalize_payload` (ya retorna CanonicalMessage correctamente)
- `ChatwootAdapter._extract_media` (ya extrae todos los tipos de media)

### SI se cambia:
- `ChatwootClient`: agregar `send_action` para typing (B1)
- `chat_webhooks.py`: ampliar query de paciente para PSIDs (B4)
- `ChatsView.tsx`: mejorar subtitulo de contacto (B7)
- Verificaciones manuales: audio download, image persistence, UI rendering (B2, B3, B5, B6)

---

## 4. Archivos Afectados

| Archivo | Tipo | Cambio | Brecha |
|---------|------|--------|--------|
| `orchestrator_service/chatwoot_client.py` | MODIFY | Agregar `send_action()` | B1 |
| `orchestrator_service/routes/chat_webhooks.py` | MODIFY | Agregar `instagram_psid`/`facebook_psid` a query de paciente | B4 |
| `frontend_react/src/views/ChatsView.tsx` | MODIFY | Mejorar subtitulo: ocultar IDs numericos cortos | B7 |

---

## 5. Criterios de Aceptacion

### Escenario 1: Typing indicator en Chatwoot
```gherkin
Dado que el agente esta procesando un mensaje de Instagram via Chatwoot
Cuando genera la respuesta y la envia
Entonces el usuario ve "escribiendo..." en la conversacion de Instagram
Y no hay warnings de 'send_action' en los logs
```

### Escenario 2: Imagen por Instagram guardada en ficha
```gherkin
Dado que un paciente ya identificado envia una imagen por Instagram
Cuando el webhook llega y se procesa
Entonces la imagen se descarga y guarda en /media/{tenant_id}/
Y si el paciente tiene instagram_psid vinculado, se guarda en patient_documents
```

### Escenario 3: Audio por Facebook con transcripcion
```gherkin
Dado que un paciente envia un audio por Facebook via Chatwoot
Cuando el webhook llega con un adjunto de tipo audio
Entonces se dispara transcripcion via Whisper
Y la transcripcion se inyecta como contenido del mensaje para el agente
```

### Escenario 4: Nombre correcto en lista de chats
```gherkin
Dado que una conversacion de Instagram tiene external_user_id = "1"
Cuando se muestra en la lista de chats
Entonces el subtitulo muestra "Instagram" en vez de "1"
```

---

## 6. Orden de Implementacion

1. **B1** — `send_action` en ChatwootClient (~2 min)
2. **B4** — Query de paciente ampliada con PSIDs (~3 min)
3. **B7** — Subtitulo de contacto en UI (~3 min)
4. **B2/B3/B5/B6** — Verificaciones manuales enviando media por IG/FB (testing)

---

## 7. Riesgos

| Riesgo | Mitigacion |
|--------|------------|
| Query ampliada de paciente (B4) devuelve paciente equivocado | Agregar condiciones con OR sin cambiar el orden de prioridad. phone_number sigue siendo prioritario |
| `send_action` falla con Chatwoot self-hosted | Ya hay try/except en ResponseSender. Warning en log, no crash |
| URLs de Chatwoot expiran antes de descargar | La descarga se hace inmediatamente en `_process_canonical_messages`. Si expira en ese corto lapso, se loguea error pero no crashea |
