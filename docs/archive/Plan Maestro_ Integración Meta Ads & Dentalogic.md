# **Plan Maestro: Implementación de Atribución de Meta Ads en Dentalogic**

Este documento constituye la hoja de ruta técnica para conectar el ecosistema publicitario de la Dra. Laura Delgado con la plataforma Dentalogic. El objetivo es lograr una **Trazabilidad 360°**: desde el clic en el anuncio hasta la conversión clínica.

## ---

**🛠️ PARTE 1: Tareas de Infraestructura (Manuales)**

*Deben completarse antes de iniciar con Cursor para evitar errores de autenticación.*

1. **App de Negocios en Meta**: Crear una app en developers.facebook.com de tipo **Negocios**. Habilitar el producto **Marketing API**.  
2. **Token de Sistema Permanente**: En el Business Manager (Configuración del Negocio), crear un **Usuario del Sistema** (Admin). Generar un token permanente con los scopes: ads\_read, read\_insights y business\_management.  
3. **Configuración de YCloud**: Asegurar que la cuenta de WhatsApp Business vinculada a YCloud tenga activado el envío del **Referral Object** en los mensajes de entrada.1  
4. **Verificación del Negocio**: Iniciar el proceso de "Business Verification" en el Security Center de Meta para obtener **Acceso Avanzado** (necesario para leer datos de campañas en producción).3  
5. **Variables de Entorno**: Configurar en tu .env o EasyPanel:  
   * META\_ADS\_TOKEN: El token del usuario del sistema.  
   * META\_AD\_ACCOUNT\_ID: El ID de la cuenta (formato act\_XXXXXXXXX).  
   * META\_API\_VERSION: v21.0 (o la versión vigente).

## ---

**💻 PARTE 2: 15 Prompts de Ingeniería para Cursor**

### **FASE A: Evolución de Datos y Modelos**

**Rol Sugerido:** Senior Backend Architect.

#### **Prompt 1: Evolución del Esquema de Base de Datos**

**Rol:** Senior Database Engineer.

**Contexto:** Archivo orchestrator\_service/db.py.

**Tarea:** Crear una migración idempotente para la tabla patients.

**Objetivo:** Agregar columnas para capturar el origen de marketing sin romper la base de datos existente.

**Instrucciones:** Genera un bloque SQL DO $$ que verifique la existencia y agregue: acquisition\_source (VARCHAR, default 'ORGANIC'), meta\_campaign\_id (VARCHAR), meta\_ad\_id (VARCHAR), meta\_ad\_headline (TEXT), y meta\_ad\_body (TEXT). Asegúrate de seguir el patrón de "Evolution Pipeline" del proyecto.

#### **Prompt 2: Actualización de Modelos ORM (SQLAlchemy)**

**Rol:** Backend Developer.

**Contexto:** Archivo orchestrator\_service/db/models\_dental.py.

**Tarea:** Sincronizar el modelo Patient con los nuevos campos de base de datos.

**Objetivo:** Reflejar los campos acquisition\_source, meta\_ad\_id, meta\_ad\_headline y meta\_ad\_body en el modelo SQLAlchemy.

**Criterio de Aceptación:** El modelo debe permitir valores nulos para estos campos y mantener la consistencia con los tipos de datos definidos en el Prompt 1\.

### ---

**FASE B: Captura de Webhooks (Atribución)**

**Rol Sugerido:** Integration Specialist.

#### **Prompt 3: Parsing del Objeto Referral en el Webhook**

**Rol:** Integration Specialist (WhatsApp API). **Contexto:** Archivo whatsapp\_service/main.py. **Tarea:** Modificar el procesador del webhook de YCloud para extraer metadatos de anuncios. **Instrucciones:** Localiza el punto donde se parsea el JSON de mensajes entrantes. Según la documentación de Meta, si un mensaje viene de un anuncio "Click-to-WhatsApp", el payload incluye un objeto referral.5 Extrae source\_id, source\_type, headline, body y source\_url. Modifica el envío al Orchestrator para incluir estos campos dentro de un diccionario opcional referral\_data.

#### **Prompt 4: Lógica de Recepción y Atribución Inicial**

**Rol:** Backend Logic Engineer.

**Contexto:** Archivo orchestrator\_service/main.py, endpoint POST /chat.

**Tarea:** Actualizar el endpoint de chat para procesar la atribución antes de la respuesta de la IA.

**Instrucciones:**

1. Actualiza el modelo Pydantic de entrada para aceptar referral\_data.  
2. Si el paciente es nuevo o no tiene fuente, actualiza su acquisition\_source a 'META\_ADS' y guarda el source\_id como meta\_ad\_id.  
3. Guarda el headline y body iniciales directamente para tener contexto inmediato de la intención (ej: "Anuncio de Implantes R.I.S.A.").

### ---

**FASE C: Integración con Graph API (Enriquecimiento)**

**Rol Sugerido:** API Integration Expert.

#### **Prompt 5: Cliente de Meta Marketing API**

**Rol:** API Integration Expert. **Tarea:** Crear orchestrator\_service/services/meta\_ads\_service.py. **Objetivo:** Implementar una clase MetaAdsClient para consultar información detallada de campañas. **Instrucciones:** Usa httpx para llamar al endpoint graph.facebook.com/{version}/{ad\_id} solicitando los campos name y campaign{name}.1 Implementa manejo de errores para tokens expirados y límites de tasa (rate limits). Usa variables de entorno para el token y la versión.

#### **Prompt 6: Caché de Metadatos con Redis**

**Rol:** DevOps & Performance Engineer.

**Contexto:** El nuevo meta\_ads\_service.py.

**Tarea:** Implementar una capa de caché para las consultas de Meta.

**Objetivo:** Evitar llamadas repetitivas a la API de Meta por el mismo ad\_id.

**Instrucciones:** Integra Redis para almacenar el nombre de la campaña y del anuncio con un TTL (Time To Live) de 48 horas. Si el dato existe en Redis, no llames a la API de Meta.

#### **Prompt 7: Tarea Asíncrona de Enriquecimiento**

**Rol:** Backend Developer.

**Tarea:** Implementar la actualización de datos en segundo plano.

**Instrucciones:** Crea una función en orchestrator\_service/services/tasks.py que reciba el patient\_id y ad\_id. Debe ejecutarse como una BackgroundTask de FastAPI. La tarea llamará al MetaAdsClient, obtendrá el nombre real de la campaña y actualizará el registro del paciente en la base de datos de forma asíncrona para no retrasar la respuesta del chatbot.

### ---

**FASE D: IA y Triaje Contextual**

**Rol Sugerido:** AI Engineer (LangChain specialist).

#### **Prompt 8: Inyección de Intención Publicitaria en el System Prompt**

**Rol:** AI Prompt Engineer. **Contexto:** Archivo orchestrator\_service/main.py, función build\_system\_prompt. **Tarea:** Personalizar la personalidad de la IA según el anuncio de origen. **Instrucciones:** Si los datos del paciente indican que viene de un anuncio cuyo headline contiene "Urgencia", "Dolor" o "Emergencia", inyecta una instrucción prioritaria: "EL PACIENTE TIENE UNA URGENCIA ACTIVA. Salta protocolos de marketing. Activa la tool triage\_urgency inmediatamente y prioriza la seguridad clínica".7

#### **Prompt 9: Herramientas de Triaje (Match-Quality)**

**Rol:** Backend Developer.

**Tarea:** Refinar la tool triage\_urgency.

**Objetivo:** Registrar si la intención del anuncio coincide con la patología detectada.

**Instrucciones:** Modifica la tool para que, si el nivel de urgencia es alto, verifique si el anuncio de origen era de "Urgencia". Guarda este "match" en un log o columna de metadatos para medir la efectividad de la segmentación de los anuncios de la doctora.

### ---

**FASE E: Frontend y Dashboard de ROI**

**Rol Sugerido:** Fullstack Developer (React/FastAPI).

#### **Prompt 10: Endpoint de Estadísticas de Marketing**

**Rol:** Data Engineer.

**Tarea:** Crear el endpoint GET /admin/marketing/stats.

**Objetivo:** Proveer datos para el dashboard de la Dra. Delgado.

**Instrucciones:** Genera una consulta SQL que agrupe pacientes por campaign\_name. Debe devolver: Total Leads, Chats Iniciados, y Citas Agendadas (cruce con la tabla appointments). Calcula la tasa de conversión por campaña.

#### **Prompt 11: Vista de Detalle de Paciente (UI)**

**Rol:** Frontend Developer.

**Contexto:** frontend\_react/src/views/PatientDetail.tsx.

**Tarea:** Mostrar el origen del lead en la ficha del paciente.

**Instrucciones:** Agrega un componente visual (Badge) que muestre "Origen: Meta Ads" si aplica. Al hacer hover, muestra el nombre de la campaña y el headline del anuncio que captó al paciente. Usa iconos de Lucide-React.

#### **Prompt 12: Widget de ROI en Dashboard Principal**

**Rol:** Frontend Developer. **Contexto:** frontend\_react/src/views/DashboardView.tsx. **Tarea:** Crear el componente MarketingPerformanceCard. **Instrucciones:** Diseña una tarjeta que consuma el nuevo endpoint de estadísticas. Debe mostrar de forma clara el gasto estimado (manual o vía API) frente a las señas cobradas (ROI inicial) y tratamientos confirmados.7

#### **Prompt 13: Previsualización del Anuncio en el Chat**

**Rol:** Frontend Developer. **Contexto:** frontend\_react/src/components/Chat/MessageList.tsx. **Tarea:** Mostrar el creativo del anuncio si el chat inicia desde uno. **Instrucciones:** Si el primer mensaje de la conversación tiene metadatos de referral, muestra una miniatura del anuncio o el texto del headline sobre el primer mensaje del paciente. Esto ayuda a la secretaria a entender el contexto visual que vio el paciente.5

### ---

**FASE F: Seguridad y Monitoreo**

**Rol Sugerido:** Security & QA Engineer.

#### **Prompt 14: Sanitización de Logs y Seguridad de Tokens**

**Rol:** Security Engineer.

**Tarea:** Implementar un filtro de logs para datos sensibles.

**Instrucciones:** Revisa el sistema de logging. Asegúrate de que los payloads de Meta y los tokens de acceso nunca se impriman en texto plano en los logs de producción. Implementa una máscara para el META\_ADS\_TOKEN.

#### **Prompt 15: Health Check de Integración Meta**

**Rol:** QA Engineer.

**Tarea:** Crear un script de validación scripts/check\_meta\_health.py.

**Objetivo:** Verificar que el token y la conexión con Meta Ads y WhatsApp referral sigan activos.

**Instrucciones:** El script debe intentar una llamada simple a /me/adaccounts y verificar que el token del sistema no haya sido revocado. Debe integrarse opcionalmente en el flujo de inicio del Orchestrator.

### ---

**📝 Guía de Pasos para el Humano (Tú)**

1. **Validación de Credenciales**: No intentes programar sin haber generado el Token de Usuario del Sistema. Es el error \#1.  
2. **Modo Desarrollo**: Trabaja inicialmente con tu propio usuario como "Tester" en la App de Meta. Los datos de la Dra. solo fluirán correctamente una vez que la App pase a modo "Live".  
3. **Prueba de Fuego**: Crea un anuncio de prueba o usa el "Ad Preview" de Meta para enviarte un mensaje a ti mismo. Verifica en la consola del backend que el objeto referral llegue con datos antes de avanzar a la fase de IA.  
4. **Revisión de App (App Review)**: Meta es estricto. Cuando solicites ads\_read de forma avanzada, graba un video de Dentalogic mostrando cómo los datos de Meta ayudan a la Dra. a gestionar mejor a sus pacientes.8

#### **Obras citadas**

1. Track WhatsApp Leads from Meta Ads | Help Desk \- Whapi.Cloud, fecha de acceso: febrero 15, 2026, [https://support.whapi.cloud/help-desk/faq/track-whatsapp-leads-from-meta-ads](https://support.whapi.cloud/help-desk/faq/track-whatsapp-leads-from-meta-ads)  
2. Tracking referrals from Meta ads \- Cue \- User Guides, fecha de acceso: febrero 15, 2026, [https://help.cuedesk.com/tracking-referrals-from-meta-ads/](https://help.cuedesk.com/tracking-referrals-from-meta-ads/)  
3. Meta Ads API: Complete Guide for Advertisers and Developers (2025) | AdManage.ai Blog, fecha de acceso: febrero 15, 2026, [https://admanage.ai/blog/meta-ads-api](https://admanage.ai/blog/meta-ads-api)  
4. Meta Business Verification \- BizMagnets Docs, fecha de acceso: febrero 15, 2026, [https://docs.bizmagnets.ai/whatsapp-channel/meta-business-verification](https://docs.bizmagnets.ai/whatsapp-channel/meta-business-verification)  
5. referral | WhatsApp Business Platform | Postman API Network, fecha de acceso: febrero 15, 2026, [https://www.postman.com/meta/a31742be-ce5c-4b9d-a828-e10ee7f7a5a3/folder/0dvb95u/referral](https://www.postman.com/meta/a31742be-ce5c-4b9d-a828-e10ee7f7a5a3/folder/0dvb95u/referral)  
6. Meta Ads | Extract by Singular, fecha de acceso: febrero 15, 2026, [https://docs.extract.to/sources/meta-ads](https://docs.extract.to/sources/meta-ads)  
7. Estrategia de Transformación Digital: Dra. Laura Delgado  
8. Meta App Review Process | PDF | Internet | Information Technology \- Scribd, fecha de acceso: febrero 15, 2026, [https://www.scribd.com/document/942933129/Meta-App-Review-Process](https://www.scribd.com/document/942933129/Meta-App-Review-Process)  
9. Meta App Review isn't random. I've seen apps approved after 42 tries because no one fixed this one thing : r/facebook \- Reddit, fecha de acceso: febrero 15, 2026, [https://www.reddit.com/r/facebook/comments/1qdzez0/meta\_app\_review\_isnt\_random\_ive\_seen\_apps/](https://www.reddit.com/r/facebook/comments/1qdzez0/meta_app_review_isnt_random_ive_seen_apps/)