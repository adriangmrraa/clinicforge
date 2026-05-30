# **Blueprint de Sincronización Total: YCloud a Plataforma Dental**

Este documento sirve como guía técnica definitiva para la implementación de un sistema de persistencia de datos desde la API de YCloud hacia la base de datos local de la plataforma.

## **1\. Arquitectura del Sistema de Sincronización**

### **A. Flujo de Control (Backend)**

La sincronización debe ser **asíncrona** y **recursiva**. Dado que el historial puede contener miles de registros, no se debe realizar en una única petición HTTP bloqueante.

1. **Activación:** El usuario presiona "Sync" en la UI.  
2. **Auth:** El sistema recupera la API Key de YCloud (desencriptándola si es necesario).  
3. **Bucle de Paginación (The "Crawler"):**  
   * Petición inicial a GET /v2/whatsapp/messages?limit=100.  
   * Procesamiento del array items.  
   * Identificación del nextCursor.  
   * Si hasMore es true, realizar una nueva petición pasando el cursor.  
4. **Finalización:** Actualización del timestamp last\_sync\_at en la configuración de la clínica.

### **B. Lógica de Persistencia (Estrategia Upsert)**

Para evitar la duplicidad de datos en ejecuciones repetidas, se debe usar una lógica de **Upsert** (Update or Insert) basada en el ID de YCloud.

* **Unique Constraint:** El campo external\_id (o ycloud\_id) en la base de datos debe ser único.  
* **Mapeo de Pacientes:** Cada mensaje debe intentar vincularse a un patient\_id buscando el número de teléfono (from o to) en la tabla de pacientes.

## **2\. Gestión de Contenidos Multimedia (Crítico)**

Los archivos de WhatsApp (imágenes, PDFs, audios) alojados en servidores de Meta/YCloud **expiran a los 30 días**. Para una plataforma dental, perder una radiografía es inaceptable.

**Protocolo de Media:**

1. Si el mensaje tiene type diferente a text:  
   * Extraer el mediaId.  
   * Llamar a GET /v2/whatsapp/media/{mediaId}.  
   * La API devolverá una URL temporal o el binario.  
2. **Descarga y Almacenamiento:**  
   * Descargar el archivo.  
   * Subirlo al storage de la plataforma (S3, Cloudinary, Local Storage, etc.).  
   * Guardar la URL del *nuevo* storage en la base de datos de mensajes.

## **3\. Especificaciones de la API de YCloud (V2)**

### **Endpoint de Mensajes: GET /v2/whatsapp/messages**

**Estructura de Respuesta esperada:**

{  
  "items": \[  
    {  
      "id": "whatsapp\_msg\_123",  
      "wamid": "ABGGR0987654321",  
      "from": "5493704XXXXXX",  
      "type": "image",  
      "image": { "id": "media\_id\_456", "caption": "Radiografía" },  
      "createTime": "2024-05-10T15:30:00Z",  
      "status": "read"  
    }  
  \],  
  "nextCursor": "abc\_cursor\_123",  
  "hasMore": true  
}

### **Endpoint de Media: GET /v2/whatsapp/media/{id}**

Este endpoint provee el acceso al archivo físico que debe ser clonado.

## **4\. Requerimientos de Interfaz (Frontend)**

Ubicación: Página de Configuración / Settings.

* **Componente:** Card de "Integración WhatsApp".  
* **Elementos:**  
  * Indicador de "Última sincronización": dd/mm/yyyy hh:mm.  
  * Botón de acción: Sincronizar ahora.  
  * **Visualizador de Progreso:** Un componente que muestre el conteo de mensajes procesados en tiempo real (ej: "Mensajes recuperados: 1,250...").  
* **Seguridad:** El botón debe estar deshabilitado si ya hay una sincronización en curso.

## **5\. Instrucciones Directas para el Agente de IA**

"Actúa como un desarrollador experto. Implementa la sincronización siguiendo estos pasos obligatorios:

1. **Service Layer:** Crea una clase o módulo YCloudService que maneje todas las llamadas a la API v2. Incluye manejo de errores con 'exponential backoff' para los límites de velocidad (Rate Limits).  
2. **Database:** Crea o ajusta la migración de la tabla whatsapp\_messages. Asegúrate de incluir campos para external\_id, wamid, patient\_id, content, media\_url, direction (inbound/outbound) y timestamp.  
3. **Paginación:** El método de sincronización debe ser capaz de recorrer el historial completo de forma recursiva o iterativa usando el puntero cursor.  
4. **Archivos:** Implementa una función downloadAndStoreMedia(mediaId) que se dispare cada vez que un mensaje de imagen o documento sea procesado. No asumas el storage, utiliza la interfaz de almacenamiento ya configurada en el proyecto.  
5. **UI:** Genera el componente de React/Vue/HTML necesario en la sección de Settings para disparar este proceso, mostrando estados de carga y éxito.  
6. **Vínculo Clínico:** Al guardar un mensaje, busca el teléfono en la tabla de pacientes. Si existe, vincula el mensaje. Si no, déjalo como 'huérfano' para ser vinculado manualmente después."