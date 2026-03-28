# ClinicForge — Guía Completa de Usuario

---

## Contenido

1. [Introducción](#1-introducción)
2. [Panel Principal (Dashboard)](#2-panel-principal-dashboard)
3. [Configuración de la Clínica](#3-configuración-de-la-clínica)
4. [Gestión de Profesionales](#4-gestión-de-profesionales)
5. [Gestión de Tratamientos y Servicios](#5-gestión-de-tratamientos-y-servicios)
6. [Agenda y Turnos](#6-agenda-y-turnos)
7. [Gestión de Pacientes](#7-gestión-de-pacientes)
8. [Chats — Centro de Mensajería](#8-chats--centro-de-mensajería)
9. [El Agente de IA — Cómo Funciona](#9-el-agente-de-ia--cómo-funciona)
10. [Marketing y Leads](#10-marketing-y-leads)
11. [Analytics — Métricas del Equipo](#11-analytics--métricas-del-equipo)
12. [Modelo de IA y Consumo de Tokens](#12-modelo-de-ia-y-consumo-de-tokens)
13. [Nova — Asistente de Voz](#13-nova--asistente-de-voz)

---

## 1. Introducción

ClinicForge es una plataforma de gestión clínica con inteligencia artificial integrada. Combina la administración de turnos, pacientes, facturación y comunicación con pacientes a través de WhatsApp, Instagram y Facebook, todo potenciado por un agente de IA que atiende a los pacientes automáticamente y un asistente de voz (Nova) que permite al equipo operar la clínica mediante comandos de voz.

**Roles disponibles:**

| Rol | Qué puede hacer |
|-----|-----------------|
| **CEO** | Acceso total: todas las clínicas, configuración, analytics, facturación, Nova completo |
| **Profesional** | Su agenda, pacientes, notas clínicas, historial, Nova (limitado a su clínica) |
| **Secretaria** | Agenda, pacientes, chats, mensajes, pagos, Nova (limitado a su clínica) |

---

## 2. Panel Principal (Dashboard)

Al ingresar a la plataforma, el Dashboard muestra un resumen ejecutivo en tiempo real:

**Métricas principales:**
- **Conversaciones IA**: Cantidad total de conversaciones que el agente de IA mantuvo con pacientes
- **Turnos agendados por IA**: Cuántos turnos logró agendar el agente automáticamente
- **Urgencias activas**: Pacientes que el agente clasificó como urgentes (dolor, emergencias)
- **Facturación confirmada**: Monto total de turnos pagados
- **Facturación estimada**: Monto de turnos pendientes de pago
- **Pagos pendientes**: Monto total de turnos con pago pendiente o parcial (ámbar)
- **Facturación hoy**: Monto total cobrado en el día actual (teal)

**Gráficos:**
- Tendencia de conversaciones vs turnos completados (semanal, mensual, anual)

**Actualizaciones en tiempo real:**
El dashboard se actualiza automáticamente cuando:
- Se agenda un nuevo turno (por IA o manualmente)
- Se confirma un pago
- Se actualiza un paciente
- Llega una nueva urgencia

---

## 3. Configuración de la Clínica

Desde la sección **Clínicas** se configura toda la información que el agente de IA y Nova utilizan para operar.

### 3.1 Datos generales

| Campo | Para qué sirve | Cómo lo usa el agente de IA |
|-------|----------------|----------------------------|
| **Nombre de la clínica** | Identifica tu clínica | Lo usa en el saludo: "Soy la asistente virtual de [nombre]" |
| **Teléfono del bot** | Número de WhatsApp conectado | Es el número desde el que el agente responde |
| **Dirección** | Dirección física de la clínica | La incluye cuando confirma un turno al paciente |
| **URL de Google Maps** | Link a la ubicación | Lo envía al paciente junto con la confirmación del turno |
| **Sillas máximas** | Cuántos pacientes pueden atenderse simultáneamente | Limita la cantidad de turnos que se agendan en el mismo horario |
| **Proveedor de calendario** | "Local" (solo base de datos) o "Google Calendar" | Si es Google, sincroniza los turnos con el calendario de Google del profesional |

### 3.2 Horarios de atención (Working Hours)

Se configuran **por día de la semana** (Lunes a Domingo). Para cada día:

- **Activar/Desactivar**: Si la clínica atiende ese día o no
- **Franjas horarias**: Una o más franjas (ej: 09:00-13:00 y 15:00-19:00)
- **Sede del día**: Si la clínica opera en distintas ubicaciones según el día
- **Dirección del día**: Dirección específica para esa sede
- **URL Maps del día**: Link de Google Maps de esa sede

**Cómo lo usa el agente de IA:**
- Cuando un paciente pide turno, el agente consulta los horarios de ese día para saber qué slots ofrecer
- Si el paciente pide un día que la clínica no atiende (ej: sábado desactivado), el agente automáticamente busca el día más cercano disponible y se lo comunica al paciente
- Si la clínica tiene multi-sede (ej: Lunes en "Salta 147", Miércoles en "Córdoba 431"), el agente incluye la dirección correcta en la confirmación del turno

### 3.3 Precio de consulta

| Campo | Para qué sirve |
|-------|----------------|
| **Precio de consulta** | Precio general de una consulta en la clínica |

- Si un paciente pregunta "cuánto sale la consulta?", el agente responde con este valor
- Cada profesional puede tener su propio precio (ver sección 4), que tiene prioridad sobre el precio general

### 3.4 Datos bancarios (para seña/depósito)

| Campo | Para qué sirve |
|-------|----------------|
| **CBU** | Código bancario para transferencias |
| **Alias** | Alias de la cuenta bancaria |
| **Titular** | Nombre del titular de la cuenta |

**Cómo lo usa el agente de IA:**
- Después de agendar un turno, el agente envía los datos bancarios al paciente para que realice la seña (depósito del 50%)
- Cuando el paciente envía una foto del comprobante, el agente verifica automáticamente que el nombre del titular y el monto coincidan

### 3.5 Email de derivación

Cuando el agente deriva una conversación a un humano (por urgencia o pedido del paciente), envía un email a esta dirección con el resumen completo del caso.

### 3.6 Preguntas Frecuentes (FAQs)

Se cargan preguntas y respuestas que el agente de IA usa para responder consultas comunes:

| Campo | Descripción |
|-------|-------------|
| **Categoría** | Tema de la FAQ (ej: Pagos, Horarios, Tratamientos) |
| **Pregunta** | La pregunta que el paciente podría hacer |
| **Respuesta** | La respuesta que el agente debe dar |

**Ejemplo:**
- Pregunta: "Aceptan obra social?"
- Respuesta: "Sí, trabajamos con OSDE, Swiss Medical y Galeno. Traé tu credencial el día del turno."

El agente de IA consulta estas FAQs automáticamente cuando el paciente hace una pregunta que coincide.

---

## 4. Gestión de Profesionales

Desde la sección de **Staff/Equipo** se gestionan los profesionales de la clínica.

### 4.1 Datos del profesional

| Campo | Descripción |
|-------|-------------|
| **Nombre y Apellido** | Nombre del profesional |
| **Email** | Correo de contacto |
| **Especialidad** | Odontología General, Ortodoncia, Endodoncia, Cirugía Oral, Implantología, etc. |
| **Teléfono** | Teléfono de contacto |
| **Matrícula** | Número de matrícula profesional |
| **Precio de consulta** | Precio individual (si es diferente al de la clínica) |
| **Google Calendar ID** | ID del calendario para sincronización |
| **Horarios propios** | Horarios específicos del profesional (pueden diferir de los de la clínica) |

### 4.2 Horarios por profesional

Cada profesional puede tener sus propios horarios de atención, independientes de los de la clínica. Esto permite que:
- Un profesional atienda solo por la mañana, mientras otro solo por la tarde
- Un profesional atienda ciertos días de la semana
- Un profesional tenga una sede diferente a la de la clínica en ciertos días

**Cómo lo usa el agente de IA:**
- Si un paciente pide turno con un profesional específico, el agente verifica los horarios de ESE profesional
- Si el profesional no atiende el día pedido, el agente automáticamente busca el próximo día que sí atiende

### 4.3 Asignación a tratamientos

Los profesionales se asignan a tratamientos específicos (ver sección 5). Esto determina:
- Si un tratamiento tiene profesionales asignados, SOLO ellos pueden atenderlo
- Si un tratamiento no tiene profesionales asignados, TODOS los profesionales activos pueden atenderlo

---

## 5. Gestión de Tratamientos y Servicios

Desde la sección **Tratamientos** se configuran todos los servicios que la clínica ofrece.

### 5.1 Campos de cada tratamiento

| Campo | Descripción | Cómo lo usa el agente de IA |
|-------|-------------|----------------------------|
| **Código** | Identificador único (ej: "blanqueamiento", "consulta") | Lo usa internamente para agendar turnos |
| **Nombre** | Nombre visible (ej: "Blanqueamiento BEYOND") | Lo muestra al paciente en las opciones |
| **Descripción** | Explicación detallada del tratamiento | Lo usa cuando el paciente pregunta "qué incluye?" |
| **Duración** | Minutos que dura (ej: 60 min) | Determina el tamaño del slot al buscar disponibilidad |
| **Duración mínima/máxima** | Rango permitido | Flexibilidad para agendamiento |
| **Complejidad** | Baja, Media, Alta | Información para el equipo |
| **Categoría** | Prevención, Restauración, Cirugía, Ortodoncia, Emergencia | Organización visual |
| **Precio base** | Costo del tratamiento (ej: $9.500.000) | Se usa para calcular el monto a cobrar cuando la secretaria asigna un tratamiento a un turno. El agente de IA lo muestra cuando el paciente pregunta "cuánto sale?" |
| **Activo** | Si el tratamiento está habilitado | Solo tratamientos activos aparecen en búsquedas |
| **Disponible para reserva** | Si los pacientes pueden agendarlo | Si está desactivado, el agente no lo ofrece |
| **Profesionales asignados** | Qué profesionales realizan este tratamiento | El agente solo ofrece disponibilidad con esos profesionales |
| **Notas internas** | Notas para el equipo | No visibles para pacientes |
| **Imágenes** | Fotos del tratamiento | El agente las envía por WhatsApp cuando el paciente pregunta |

### 5.2 Ejemplo práctico

Si se carga un tratamiento "Blanqueamiento BEYOND" con:
- Duración: 90 min
- Precio: $45.000
- Profesional asignado: Dra. Laura Delgado

Cuando un paciente escribe "quiero un blanqueamiento", el agente:
1. Identifica el tratamiento "Blanqueamiento BEYOND"
2. Busca disponibilidad SOLO con la Dra. Laura Delgado
3. Busca slots de 90 minutos
4. Muestra opciones con el precio: "$45.000 (90 min)"

---

## 6. Agenda y Turnos

### 6.1 Vista de calendario

La agenda muestra todos los turnos en formato calendario con código de colores:

| Color | Origen del turno |
|-------|-----------------|
| **Azul** | Agendado por el agente de IA (WhatsApp/Instagram/Facebook) |
| **Verde** | Agendado manualmente desde la plataforma |
| **Violeta** | Agendado por Nova (asistente de voz) |
| **Gris** | Bloqueo de Google Calendar (solo lectura) |

**Vistas disponibles:** Semana, Día, Lista

**Indicadores en cada tarjeta de turno:**

| Indicador | Significado |
|-----------|------------|
| **Punto verde** | Pago completado (seña o tratamiento pagado) |
| **Punto amarillo** | Pago parcial |
| **Punto rojo parpadeante** | Pago pendiente |
| **"ALERTA" rojo** | El paciente tiene condiciones médicas críticas (diabetes, hipertensión, alergias, etc.) |

Estos indicadores aparecen tanto en la vista de escritorio como en la vista móvil.

### 6.2 Crear turno manualmente

Al hacer click en un espacio del calendario se abre el formulario:
- Seleccionar paciente (buscador)
- Asignar profesional
- Elegir tipo de tratamiento
- Fecha y hora
- Duración
- Notas

El sistema detecta automáticamente si hay colisiones con otros turnos.

### 6.3 Estados de un turno

| Estado | Significado |
|--------|------------|
| **Programado** | Turno creado, pendiente de confirmación |
| **Confirmado** | Paciente confirmó asistencia o pagó seña |
| **En progreso** | El paciente está siendo atendido |
| **Completado** | Atención finalizada |
| **No asistió** | El paciente no se presentó |
| **Cancelado** | Turno cancelado |

### 6.4 Facturación por turno

Cada turno tiene campos de facturación:
- **Monto**: Precio cobrado
- **Cuotas**: Plan de pago (ej: "3 cuotas de $5.000")
- **Estado de pago**: Pendiente / Parcial / Pagado
- **Comprobante**: Datos del comprobante de pago verificado

---

## 7. Gestión de Pacientes

### 7.1 Datos del paciente

| Campo | Descripción |
|-------|-------------|
| **Nombre y Apellido** | Datos personales |
| **Teléfono** | Número de WhatsApp (se captura automáticamente del chat) |
| **DNI** | Documento de identidad |
| **Email** | Correo electrónico |
| **Obra Social** | Prepaga/seguro médico |
| **Ciudad** | Ciudad de residencia |
| **Fecha de nacimiento** | Datos demográficos |

**Indicadores en la lista de pacientes:**

| Columna | Qué muestra |
|---------|------------|
| **Próximo turno** | Fecha y hora del siguiente turno agendado, o "Sin turno" |
| **Balance** | Monto pendiente de pago (ámbar si hay deuda) |

**Resumen financiero en la ficha del paciente (pestaña Resumen):**
Al abrir la ficha de un paciente, se muestra una tarjeta con 4 indicadores:
- **Turnos**: Cantidad total de registros clínicos
- **Próximo turno**: Fecha del siguiente turno
- **Última visita**: Fecha de la última consulta
- **Balance pendiente**: Monto adeudado (verde "Al día" o ámbar con el monto)

### 7.2 Ficha clínica del paciente

Cada paciente tiene una ficha con:
- **Resumen**: Datos personales y alertas médicas
- **Historial**: Todos los registros clínicos y turnos pasados
- **Documentos**: Imágenes médicas, radiografías, fotos
- **Anamnesis**: Historia médica completa (enfermedades, alergias, medicamentos)

**Alertas automáticas:** El sistema detecta automáticamente condiciones críticas en las notas médicas: diabetes, hipertensión, problemas cardíacos, hemofilia, alergia a penicilina, embarazo, anticoagulación, HIV, hepatitis, asma severa.

### 7.3 Importación masiva (CSV/XLSX)

Se pueden importar pacientes desde un archivo Excel o CSV:

1. **Subir archivo**: Arrastrá o seleccioná el archivo (máximo 1.000 filas)
2. **Previsualización**: Revisá los datos antes de importar
3. **Duplicados**: Elegí si omitir o actualizar pacientes que ya existen (se detectan por teléfono)
4. **Resultado**: Muestra cuántos se crearon, actualizaron, omitieron o dieron error

**Columnas reconocidas:** nombre, apellido, teléfono, email, DNI, obra_social, ciudad, fecha_nacimiento, notas

### 7.4 Búsqueda inteligente

Además de buscar por nombre/teléfono/DNI, existe una **búsqueda semántica** que permite buscar pacientes por condiciones médicas. Ejemplo: buscar "diabetes" muestra todos los pacientes diabéticos.

---

## 8. Chats — Centro de Mensajería

### 8.1 Canales soportados

| Canal | Integración |
|-------|-------------|
| **WhatsApp** | A través de YCloud |
| **Instagram** | A través de Chatwoot |
| **Facebook Messenger** | A través de Chatwoot |

### 8.2 Vista de chats

La pantalla de chats muestra:
- Lista de conversaciones activas con preview del último mensaje
- Contador de mensajes no leídos
- Estado del chat (activo, pausado, en manos de humano, silenciado)
- Nivel de urgencia del paciente (bajo, medio, alto, crítico)

### 8.3 Panel de contexto del paciente

Al seleccionar un chat, se abre un panel lateral con:
- Próximo turno del paciente
- Último turno realizado
- Plan de tratamiento
- Diagnósticos
- Anamnesis (historia médica)
- Origen de adquisición (si llegó por Meta Ads, muestra la campaña)

### 8.4 Acciones disponibles

| Acción | Descripción |
|--------|-------------|
| **Enviar mensaje** | Escribir como humano en la conversación |
| **Derivar a humano** | Tomar el control del chat (el agente de IA se silencia por 24 horas) |
| **Pausar chat** | Silenciar temporalmente al agente de IA |
| **Enviar archivo** | Adjuntar imágenes o documentos |

### 8.5 Notificaciones

- Sonido configurable para nuevos mensajes
- Notificaciones toast para: derivaciones a humano, nuevos turnos, actualizaciones de pacientes

---

## 9. El Agente de IA — Cómo Funciona

### 9.1 Qué es

El agente de IA es un asistente virtual que atiende a los pacientes por **WhatsApp, Instagram y Facebook** de forma completamente autónoma. Puede:

- Responder preguntas sobre la clínica, tratamientos y precios
- Agendar, cancelar y reprogramar turnos
- Clasificar urgencias médicas
- Cobrar seña y verificar comprobantes de pago
- Recopilar la historia médica (anamnesis)
- Derivar a un humano cuando es necesario

### 9.2 Flujo de agendamiento (cómo agenda un turno)

Cuando un paciente escribe pidiendo un turno, el agente sigue estos pasos en orden:

**Paso 1 — Saludo personalizado**
El agente adapta su saludo según quién sea el paciente:
- **Paciente nuevo**: "Hola! Soy la asistente virtual de [clínica]. En qué tipo de consulta estás interesado?"
- **Paciente sin turno próximo**: "Hola [nombre]! En qué podemos ayudarte?"
- **Paciente con turno próximo**: "Hola [nombre]! Te esperamos el [fecha] a las [hora] en [sede] para tu [tratamiento]"

**Paso 2 — Identificar el tratamiento**
Si el paciente ya dijo qué necesita (ej: "quiero un blanqueamiento"), el agente lo valida contra los tratamientos cargados en la plataforma. Si dice algo coloquial (ej: "limpiar los dientes"), lo mapea al tratamiento correcto ("Limpieza profunda").

**Paso 3 — Profesional**
- Si el tratamiento tiene UN solo profesional asignado: informa al paciente sin preguntar
- Si tiene VARIOS: pregunta preferencia
- Si no tiene asignados: usa el primero disponible

**Paso 4 — Buscar disponibilidad**
El agente busca turnos disponibles considerando:
- Los horarios de la clínica para ese día
- Los horarios del profesional
- Los turnos ya agendados
- La duración del tratamiento
- El límite de sillas simultáneas

Muestra 3 opciones en días diferentes:
```
📅 Opciones disponibles para tu Blanqueamiento BEYOND:

1️⃣  Jueves 30/04 — 10:00 hs
2️⃣  Viernes 01/05 — 14:15 hs
3️⃣  Lunes 04/05 — 13:00 hs

Hay 22 turnos más disponibles si preferís otro horario.
📍 Dirección: Salta 147, Neuquén Capital. Maps: [link]
```

Si el día pedido no está disponible (clínica cerrada, profesional no atiende), **automáticamente busca el día más cercano** y le avisa al paciente.

**Paso 5 — Reserva temporal**
Cuando el paciente elige un horario, el agente lo reserva por 30 segundos mientras recopila datos.

**Paso 6 — Datos de admisión**
Solo si el paciente es nuevo, pide:
- Nombre y apellido
- DNI

No pide email, fecha de nacimiento ni ciudad.

**Paso 7 — Confirmar turno**
El agente confirma el turno y envía al paciente:
- Resumen: tratamiento, profesional, fecha, hora, duración, sede, precio
- Datos bancarios para la seña (50% del valor)
- Link a la ficha médica (anamnesis)
- Instrucciones pre-turno

### 9.3 Tipos de turno que puede agendar

| Tipo | Cómo funciona |
|------|---------------|
| **Para sí mismo** | El paciente agenda para sí mismo (flujo normal) |
| **Para un adulto tercero** | El paciente agenda para un amigo/familiar adulto. El agente pide el teléfono del tercero |
| **Para un menor** | El paciente agenda para su hijo/a. El agente NO pide teléfono (usa el del padre automáticamente) |

### 9.4 Sistema de seña (depósito)

Después de cada turno agendado:
1. El agente envía los datos bancarios (CBU, Alias, Titular)
2. El paciente transfiere el 50% del valor de la consulta
3. El paciente envía foto del comprobante por WhatsApp
4. El agente verifica automáticamente:
   - Que el nombre del titular coincida
   - Que el monto sea correcto
5. Si es correcto: confirma el pago y cambia el estado del turno
6. Si es incorrecto: informa el problema y pide que reenvíe

### 9.5 Clasificación de urgencias

Cuando un paciente menciona dolor o urgencia, el agente activa el protocolo:
1. Analiza los síntomas (dolor intenso, hinchazón, sangrado, trauma, fiebre)
2. Clasifica la urgencia: baja, normal, alta, crítica
3. Si es alta/crítica: busca turno inmediato de consulta
4. Si es crítico: además deriva a un humano

### 9.6 Flujo de implantes y prótesis

Cuando un paciente menciona implantes o prótesis, el agente activa un flujo comercial especial:

1. Muestra 6 opciones con emoji para identificar el caso:
   - 🦷 Perdí un diente
   - 🦷🦷 Perdí varios dientes
   - 🔄 Uso prótesis removible
   - 🔧 Necesito cambiar una prótesis
   - 😣 Tengo una prótesis que se mueve
   - 🤔 No estoy seguro

2. Profundiza: "Hace cuánto tiempo tenés este problema?"
3. Posiciona al profesional como especialista
4. Busca turno de consulta inmediatamente

### 9.7 Qué puede responder el agente

- Preguntas sobre tratamientos (usa la descripción y las imágenes cargadas)
- Precios (usa los precios de los tratamientos y la consulta)
- Horarios de atención (usa los working hours configurados)
- Ubicación y sedes (usa la dirección y Maps de cada día)
- Preguntas frecuentes (usa las FAQs cargadas)
- Turnos existentes del paciente
- Estado de pagos

### 9.8 Cuándo deriva a un humano

El agente deriva automáticamente cuando:
- El paciente pide explícitamente hablar con una persona
- La urgencia es crítica
- El paciente está frustrado o enojado
- El agente no puede resolver la consulta después de varios intentos

Al derivar, envía un email al equipo con todo el contexto de la conversación.

---

## 10. Marketing y Leads

### 10.1 Conexión con Meta Ads

La plataforma se conecta con Meta (Facebook/Instagram) para:
- Rastrear qué campaña/anuncio trajo a cada paciente
- Medir conversión: lead → paciente → turno → pago
- Capturar leads de formularios de Facebook automáticamente

### 10.2 Pipeline de leads

Los leads pasan por estas etapas:
1. **Nuevo**: Acaba de llegar
2. **Contactado**: Se le respondió
3. **Consulta agendada**: Tiene turno
4. **Tratamiento planificado**: Se definió plan de tratamiento
5. **Convertido**: Se convirtió en paciente activo

### 10.3 Métricas de marketing

- Total de leads recibidos
- Tasa de conversión (leads → pacientes)
- Costo por lead
- ROI por campaña
- Rendimiento por anuncio

---

## 11. Analytics — Métricas del Equipo

### 11.1 Métricas por profesional

Para cada profesional se mide:

| Métrica | Qué significa |
|---------|---------------|
| **Total de turnos** | Cantidad de turnos en el período |
| **Tasa de asistencia** | % de turnos completados vs agendados |
| **Tasa de cancelación** | % de turnos cancelados |
| **Tasa de no-show** | % de pacientes que no se presentaron |
| **Facturación** | Ingresos generados |
| **Ticket promedio** | Ingreso promedio por turno |
| **Tasa de retención** | % de pacientes que vuelven |
| **Pacientes únicos** | Cantidad de pacientes diferentes atendidos |

### 11.2 Tags de rendimiento

El sistema asigna automáticamente etiquetas:
- **Alto rendimiento**: Profesional con métricas excepcionales
- **Maestro de retención**: Alta tasa de retención de pacientes
- **Top facturación**: Mayor generación de ingresos
- **Riesgo: cancelaciones**: Alta tasa de cancelación
- **Riesgo: no-shows**: Alta tasa de ausencias

---

## 12. Modelo de IA y Consumo de Tokens

### 12.1 Modelos configurables

La plataforma permite elegir qué modelo de IA usar para cada función:

| Función | Para qué se usa | Modelos disponibles |
|---------|-----------------|-------------------|
| **Chat con pacientes** | Conversaciones por WhatsApp/Instagram/Facebook | GPT-4o-mini, GPT-4o, GPT-5.4-Mini, GPT-5.4, DeepSeek V4 |
| **Análisis diario** | Insights automáticos cada 12 horas | Mismos modelos |
| **Nova (voz)** | Asistente de voz en el dashboard | GPT-4o-mini-realtime, GPT-4o-realtime |
| **Memorias de pacientes** | Extraer y guardar información de conversaciones | Mismos modelos |

### 12.2 Métricas de consumo

En la sección de Tokens y Métricas se puede ver:
- Costo total en USD
- Tokens consumidos por día
- Costo por conversación promedio
- Distribución de uso por modelo
- Proyección de capacidad del sistema

---

## 12b. Sistema de Verificación de Pagos

### Cómo funciona la verificación automática de comprobantes

1. El paciente recibe datos bancarios después de agendar un turno (alias, CBU, titular)
2. El paciente transfiere la seña (50% del precio de consulta del profesional)
3. El paciente envía foto del comprobante por WhatsApp
4. El agente de IA detecta automáticamente que es un comprobante de pago (no un documento médico)
5. Ejecuta verificación automática:
   - Compara el titular del comprobante con los datos bancarios de la clínica
   - Verifica que el monto coincida con la seña esperada
6. Si es correcto: confirma el turno y marca como pagado
7. Si es incorrecto: explica qué falló y pide reenvío

### Casos especiales

| Caso | Qué hace el agente |
|------|-------------------|
| Monto mayor a la seña | Acepta y anota el excedente en notas de facturación |
| Monto menor a la seña | Informa cuánto falta y pide que complete la diferencia |
| Titular no coincide | Pide que verifique la cuenta destino y reenvíe |
| Imagen no legible | Pide que reenvíe una foto más clara |
| Múltiples comprobantes | Suma los pagos parciales automáticamente |

### Dónde ver los comprobantes

- **Ficha del paciente → Archivos**: aparece con etiqueta verde "Comprobante de Pago"
- **Editar turno → Facturación**: muestra el comprobante verificado con badge verde, montos y fecha

---

## 13. Nova — Asistente de Voz

### 13.1 Qué es Nova

Nova es un asistente de voz con inteligencia artificial que funciona dentro de la plataforma. Aparece como un botón flotante en todas las páginas. Permite operar toda la clínica mediante comandos de voz, como un "Jarvis" para la clínica dental.

Nova escucha, entiende y ejecuta. No necesita que le dictes comandos exactos — habla naturalmente como le hablarías a un asistente humano.

### 13.2 Cómo usar Nova

1. Hacé click en el botón de Nova (flotante en cualquier página)
2. Hablá naturalmente (ej: "Agendame un turno para Juan Pérez mañana a las 10")
3. Nova ejecuta la acción y te responde por voz
4. Podés encadenar pedidos: "Buscame a María López y decime sus próximos turnos"

### 13.3 Todo lo que puede hacer Nova

Nova tiene acceso a **47 herramientas** organizadas en 10 categorías. A continuación, cada una explicada en detalle:

---

#### A. Gestión de Pacientes (7 herramientas)

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Buscame al paciente García" | Busca por nombre, apellido, DNI o teléfono. Muestra hasta 5 resultados |
| "Mostrame la ficha de la paciente 45" | Muestra perfil completo: datos personales, obra social, historia médica, último turno |
| "Registrá un nuevo paciente: María López, teléfono 3704567890" | Crea un paciente nuevo con los datos que le dictes |
| "Actualizale el email a la paciente 45" | Modifica un campo específico del paciente (teléfono, email, obra social, notas) |
| "Mostrame el historial clínico del paciente 32" | Muestra diagnósticos, tratamientos realizados y odontograma |
| "Registrá una nota clínica: caries en pieza 36, superficie oclusal" | Agrega un registro clínico con diagnóstico, pieza dental (nomenclatura FDI), tratamiento y superficie |
| "Eliminá al paciente 99" | Desactiva un paciente (solo CEO). No borra datos, lo marca como inactivo |

---

#### B. Agenda y Turnos (9 herramientas)

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Mostrame la agenda de hoy" | Lista todos los turnos del día, por profesional si querés |
| "Quién es el próximo paciente?" | Muestra el próximo turno del profesional actual |
| "Hay disponibilidad el martes para limpieza?" | Verifica slots libres para un tratamiento en una fecha específica |
| "Agendá un turno para Juan Pérez, mañana a las 10, limpieza" | Crea un turno completo: paciente + fecha + hora + tratamiento + profesional |
| "Cancelá el turno ABC123" | Cancela un turno con motivo opcional |
| "Confirmá todos los turnos de hoy" | Confirma en lote los turnos pendientes del día |
| "Reprogramá el turno ABC123 para el jueves a las 15" | Mueve un turno a nueva fecha/hora |
| "Marcá como completado el turno ABC123" | Cambia el estado: completado, no-show, en progreso, confirmado |
| "Bloqueá la agenda de Laura el viernes de 12 a 14" | Crea un bloqueo (almuerzo, reunión, descanso) donde no se pueden agendar turnos |

---

#### C. Tratamientos y Facturación (3 herramientas)

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Qué tratamientos tenemos?" | Lista todos los tratamientos activos con precios y duraciones |
| "Registrá un pago de $15.000 en efectivo para el turno ABC123" | Registra el pago (efectivo, tarjeta, transferencia, obra social) |
| "Qué turnos tienen pago pendiente?" | Lista todos los turnos completados sin cobrar |

---

#### D. Analytics y Reportes (5 herramientas)

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Dame el resumen de la semana" | Turnos creados, completados, cancelaciones, nuevos pacientes, facturación total, no-shows |
| "Cómo le fue a la Dra. López este mes?" | Métricas del profesional: turnos, cancelaciones, retención, facturación, ticket promedio |
| "Mostrame las estadísticas del mes" | Dashboard general: turnos, pacientes, facturación, cancelaciones |
| "Cómo viene el marketing este trimestre?" | Inversión Meta Ads, leads generados, costo por lead, conversiones, ROI |
| "Dame el resumen financiero del mes" | Facturación por tratamiento, pagos pendientes, cobros por profesional (solo CEO) |

---

#### E. Navegación (2 herramientas)

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Llevame a la agenda" | Navega a cualquier sección: agenda, pacientes, chats, tratamientos, analytics, configuración, marketing, leads |
| "Abrí la ficha del paciente 45" | Navega directamente a la ficha de un paciente específico |

---

#### F. Multi-Sede / CEO (4 herramientas)

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Dame un resumen de todas las sedes" | Comparativa de todas las clínicas: turnos, pacientes, facturación, puntaje de rendimiento |
| "Compará las cancelaciones entre sedes este mes" | Comparativa específica: cancelaciones, nuevos pacientes, facturación, ocupación |
| "Cambiate a la sede Córdoba" | Cambia el contexto activo a otra clínica. Los siguientes comandos aplican a esa sede |
| "Cómo está el onboarding de la sede nueva?" | Muestra el estado de configuración: profesionales, horarios, tratamientos, WhatsApp, Google Calendar, FAQs, datos bancarios, precio de consulta |

---

#### G. Operaciones de Staff (10 herramientas)

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Qué profesionales tenemos?" | Lista todos los profesionales activos con especialidad y precio |
| "Mostrame la configuración de la clínica" | Nombre, dirección, teléfono, datos bancarios, precio, web, email |
| "Cambiá el precio de consulta a $15.000" | Actualiza configuración de la clínica (solo CEO) |
| "Creá un tratamiento nuevo: Limpieza Profunda, código limpieza, 45 minutos, $8.000" | Agrega un nuevo tratamiento al catálogo (solo CEO) |
| "Cambiá la duración del blanqueamiento a 90 minutos" | Modifica un tratamiento existente (solo CEO) |
| "Mostrame los últimos 5 chats" | Lista las conversaciones recientes con vista previa |
| "Mandále un WhatsApp a 3704567890: Recordá tu turno mañana a las 10" | Envía un mensaje de WhatsApp desde la clínica |
| "Mostrame las estadísticas de hoy" | Estadísticas generales: turnos, pacientes, facturación |
| "Mostrame las FAQs" | Lista todas las preguntas frecuentes configuradas |
| "Agregá una FAQ: 'Aceptan OSDE?' - 'Sí, trabajamos con OSDE plan 210 y superiores'" | Crea o actualiza una FAQ que el agente de IA usará para responder |

---

#### H. Anamnesis por Voz (2 herramientas)

Cuando Nova está en la página de anamnesis de un paciente, cambia su modo y habla directamente con el paciente para completar su ficha médica:

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Guardá la anamnesis: diabetes tipo 2, toma metformina, alérgico a penicilina" | Guarda las secciones de la historia médica dictadas por voz. Se puede hacer progresivamente (sección por sección) |
| "Mostrame la anamnesis del paciente 45" | Muestra la ficha médica completa: enfermedades, medicamentos, alergias, cirugías, tabaquismo, embarazo, miedos |

**Las secciones de la anamnesis son:**
1. Enfermedades de base (diabetes, hipertensión, cardiopatías)
2. Medicación habitual
3. Alergias (penicilina, anestesia, etc.)
4. Cirugías previas
5. Tabaquismo (sí/no, cantidad)
6. Embarazo/lactancia
7. Experiencias negativas previas con dentistas
8. Miedos específicos (agujas, dolor, etc.)

---

#### H2. Odontograma Dental (2 herramientas)

Nova puede ver y modificar el odontograma completo de cualquier paciente por voz. Los cambios quedan guardados permanentemente en la ficha clínica.

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Mostrame el odontograma de García" | Busca al paciente y muestra el estado de todas las piezas dentales, agrupadas por cuadrante (superior derecho, superior izquierdo, inferior izquierdo, inferior derecho) |
| "El paciente tiene caries en la 1.6 y la 1.8" | Actualiza las piezas 16 y 18 como caries en el odontograma |
| "La 36 tiene conducto" | Marca la pieza 36 como tratamiento de conducto |
| "Le falta la muela de juicio de abajo a la derecha" | Marca la pieza 48 como ausente |
| "La 21 tiene una corona" | Marca la pieza 21 como corona |
| "Marcá la 14 y 15 como restauración, superficie oclusal tratada" | Actualiza dos piezas con detalle de superficies |
| "Tiene dos dientes rotos" (sin número) | Nova PREGUNTA: "En qué piezas? Necesito los números" |

**Estados disponibles para cada pieza:**

| Estado | Significado | Color en el odontograma |
|--------|------------|------------------------|
| Sano (healthy) | Sin patología | Blanco |
| Caries | Lesión cariosa activa | Rojo |
| Restauración | Pieza restaurada/obturada | Azul |
| Extracción | Pieza extraída | Oscuro con X |
| Planificado | Tratamiento planificado | Amarillo |
| Corona | Pieza con corona protésica | Violeta |
| Implante | Pieza con implante | Indigo |
| Ausente | Pieza ausente (nunca existió o perdida) | Mínimo con guion |
| Prótesis | Pieza protésica removible | Teal |
| Conducto | Tratamiento de conducto realizado | Naranja |

**Superficies dentales (opcional, nivel de detalle adicional):**
- Oclusal (cara de masticación)
- Mesial (cara hacia el centro)
- Distal (cara hacia atrás)
- Bucal (cara hacia la mejilla)
- Lingual (cara hacia la lengua)

Cada superficie puede estar: sana, con caries, o tratada.

**Numeración FDI (la que usa Nova):**

```
        Superior Derecho (Q1)  |  Superior Izquierdo (Q2)
        18 17 16 15 14 13 12 11 | 21 22 23 24 25 26 27 28
        ────────────────────────┼────────────────────────
        48 47 46 45 44 43 42 41 | 31 32 33 34 35 36 37 38
        Inferior Derecho (Q4)  |  Inferior Izquierdo (Q3)
```

Si decís "1.6" Nova interpreta como pieza 16 (primer molar superior derecho).

**Reglas de seguridad del odontograma:**
1. Nova SIEMPRE mira el odontograma actual antes de modificarlo
2. Si no decís números de piezas, Nova pregunta cuáles son antes de tocar nada
3. Si hay duda, Nova confirma: "Voy a marcar la 16 y 18 como caries, correcto?"
4. Los cambios se guardan en la ficha clínica del paciente y se ven reflejados en la UI
5. Se pueden modificar varias piezas en un solo comando

**Ejemplo de flujo completo:**

> **Vos:** "El paciente García tiene caries en la 1.6 y fractura en la 2.1"
>
> **Nova:** *(busca a García, ve su odontograma actual)*
> "García tiene el odontograma con 3 piezas registradas. Voy a marcar la 16 como caries y la 21 como extracción. Listo, odontograma actualizado."

---

#### I. Consultas Avanzadas de Datos (3 herramientas)

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Cuántos turnos hay esta semana?" | Consulta en lenguaje natural: convierte tu pregunta en una búsqueda en la base de datos |
| "Cuántos pacientes nuevos tuvimos este mes?" | Funciona con cualquier pregunta sobre datos |
| "Cuántos leads de Meta no fueron contactados?" | Consultas complejas de marketing y conversión |

---

#### J. Acceso Directo a Base de Datos (4 herramientas)

Para consultas más específicas, Nova puede acceder directamente a cualquier tabla:

| Comando de ejemplo | Qué hace Nova |
|-------------------|---------------|
| "Traeme los últimos 10 pacientes creados" | Lee registros de cualquier tabla con filtros |
| "Actualizá el estado del turno XYZ a completado" | Modifica registros directamente |
| "Creá un registro clínico para el paciente 45" | Inserta registros en cualquier tabla |
| "Cuántos turnos cancelados hay este mes?" | Cuenta registros con filtros |

**Tablas accesibles:** pacientes, turnos, profesionales, tratamientos, clínicas, mensajes de chat, conversaciones, documentos, registros clínicos, logs de automatización, memorias de pacientes, FAQs, bloqueos de calendario, insights de Meta Ads.

---

### 13.4 Análisis Diario Automático

Cada 12 horas, Nova genera automáticamente un análisis de la clínica que incluye:

- **Temas frecuentes**: Las 3-5 consultas más comunes de los pacientes
- **Problemas detectados**: Casos donde el agente de IA falló o no pudo responder
- **Temas sin cobertura**: Preguntas frecuentes que el agente no puede responder (sugerencia de agregar FAQs)
- **Sugerencias**: 2-3 mejoras concretas (agregar FAQs, ajustar horarios, configurar precios)
- **Insights de cancelaciones**: Patrones en las cancelaciones
- **Satisfacción estimada**: Puntuación 1-10 basada en el tono de las conversaciones
- **Resumen ejecutivo**: 2-3 oraciones resumiendo el estado de la clínica

Para el CEO con múltiples sedes, además genera:
- **Ranking de sedes**: De mejor a peor rendimiento
- **Mejor sede**: Cuál y por qué
- **Peor sede**: Cuál, por qué y sugerencia de mejora
- **Comparativas**: 3-5 insights comparando sedes
- **Tendencia global**: Resumen de la organización completa

### 13.5 Principios de Nova

- **Ejecutar primero, hablar después**: Nova ejecuta las acciones antes de explicar. No pide confirmación innecesaria.
- **Encadenar acciones**: Puede ejecutar 2-3 herramientas seguidas sin preguntar. Ej: "Buscame a García y agendále un turno mañana" → busca + agenda.
- **Nunca decir "no puedo"**: Si existe una herramienta que resuelve el pedido, la usa.
- **Datos reales**: Nunca inventa información. Todo viene de la base de datos.
- **Respuestas cortas**: 2-3 oraciones máximo por respuesta de voz.

---

## Soporte

Si tenés dudas o necesitás ayuda con la configuración, contactá al equipo de soporte de ClinicForge.
