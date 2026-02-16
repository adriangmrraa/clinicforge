# Guía para Desarrolladores - Mantenimiento y Extensión

Este documento contiene tips técnicos para mantener, debugear y extender **Dentalogic**, la plataforma de gestión clínica dental.

## 1. Agregar una Nueva Herramienta (Tool)

### Paso 1: Definir la Función en main.py

Ubicación: `orchestrator_service/main.py`

```python
from langchain.tools import tool

@tool
async def mi_nueva_herramienta(parametro1: str, parametro2: int = 10):
    """
    Descripción clara de qué hace esta herramienta.
    """
    # Tu lógica aquí
    return {"resultado": "ok"}
```

### Paso 2: Agregar a la Lista de Tools

Busca la lista `tools` y agrega la referencia.

## 2. Paginación y Carga Incremental de Mensajes

Para optimizar el rendimiento en conversaciones extensas, Dentalogic utiliza un sistema de carga bajo demanda en `ChatsView.tsx`:
- **Backend (Admin API)**: Soporta parámetros `limit` (default 50) y `offset` para consultas SQL (`LIMIT $2 OFFSET $3`).
- **Frontend**: Utiliza el estado `messageOffset` para gestionar qué bloque de mensajes solicitar. Los nuevos mensajes se concatenan al principio del array `messages` preservando la cronología.

## 3. Deduplicación de Mensajes
 
Redis almacena los `message_id` por 2 minutos para evitar procesar dobles webhooks de WhatsApp.

## 4. Debugging 

- **Logs Locales**: `docker-compose logs -f`
- **Logs Producción**: Panel de EasyPanel → Logs.
- **Protocolo Omega**: Los links de activación se imprimen en los logs del orquestador si falla el SMTP.

## 10. Versioning y Migración (Maintenance Robot)

Si necesitas cambiar la base de datos:
1.  Agrega el cambio en `db/init/dentalogic_schema.sql` (Foundation).
2.  Agrega un parche en `orchestrator_service/db.py` (Evolution). Usa bloques `DO $$` para que sea idempotente.

**Ejemplo: Patch working_hours (Feb 2026)**
```python
# En orchestrator_service/db.py
patch_sql = """
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='professionals' AND column_name='working_hours') THEN
            ALTER TABLE professionals ADD COLUMN working_hours JSONB;
            -- Inicializar con default si es necesario
            UPDATE professionals SET working_hours = '{"1":{"enabled":true,"slots":[{"start":"08:00","end":"20:00"}]}}'::jsonb;
        END IF;
    END $$;
"""
```

## 12. Gestión de Usuarios y Seguridad (Auth Layer)

### 12.1 Ciclo de Vida del Usuario
1.  **Registro**: Crea un usuario `pending`.
2.  **Aprobación**: Un CEO activa la cuenta en `/aprobaciones`.
    -   Se vincula/crea un perfil en `professionals`.
3.  **Activación**: El usuario ya puede loguearse.

### 12.2 Omega Protocol Prime
En despliegues iniciales, el sistema auto-activa al primer `ceo` registrado para evitar bloqueos.

### 12.3 Headers de Seguridad
-   `Authorization: Bearer <JWT_TOKEN>` (Identidad)
-   `X-Admin-Token: <INTERNAL_ADMIN_TOKEN>` (Infraestructura)

---

*Guía de Desarrolladores Dentalogic © 2026*

---

## 20. Agenda Móvil: Rangos y Scroll (2026-02-08)

### 20.1 Cálculo de Rango sin FullCalendar
En móvil, el componente `FullCalendar` no se renderiza. Esto rompe la lógica de `fetchData` que intenta acceder a `activeStart/End` vía `calendarRef`.
- **Solución**: Se implementó un fallback que calcula un rango de `+/- 7 días` basado en el estado `selectedDate`.

### 20.2 Scroll Isolation en Flexbox
Para que un componente hijo (`MobileAgenda`) tenga un scroll independiente dentro de un padre con `overflow-hidden`:
1. El contenedor padre debe ser `flex flex-col h-screen overflow-hidden`.
2. El contenedor intermedio debe ser `flex-1 min-h-0`.
3. El componente hijo debe ser `flex-1 min-h-0` con un área interna de `overflow-y-auto`.
- **Nota**: El `min-h-0` es mandatorio en Chrome y Safari para permitir que el hijo se contraiga y active su propio scrollbar.

### 20.3 Normalización de Fechas
Se recomienda el uso de `format(parseISO(...), 'yyyy-MM-dd')` de `date-fns` para todas las comparaciones de UI, evitando inconsistencias de huso horario entre el backend (UTC) y los dispositivos móviles.

## 21. Sovereign Analytics Engine (2026-02-08)

### 21.1 Lógica de Ingresos por Asistencia
Para garantizar el alineamiento con el flujo de caja real, los ingresos en el Dashboard **solo** se cuentan si:
1. La transacción en `accounting_transactions` tiene `status = 'completed'`.
2. El turno (`appointment_id`) asociado tiene `status` en `('completed', 'attended')`.
*No se deben sumar ingresos de turnos `scheduled` o `confirmed` hasta que se valide la presencia del paciente.*

### 21.2 Filtrado de Rangos (Query Params)
El endpoint `/admin/stats/summary` requiere el parámetro `range` (`weekly` | `monthly`) para calcular los intervalos SQL dinámicamente. 

### 21.3 Conteo de Conversaciones (Threads vs Messages)
Para evitar inflación de métricas, el conteo de conversaciones **debe** usar `DISTINCT from_number`. Un paciente puede intercambiar 200 mensajes, pero el Dashboard lo reportará como **1 conversación** para medir alcance real, no volumen de tokens.

### 21.4 Mapeo de Contexto Clínico (Frontend Compatibility)
En el endpoint `/admin/patients/phone/{phone}/context`, el backend realiza un alias explícito: `appointment_datetime AS date`. Esto es necesario porque el componente `ChatsView.tsx` consume el campo `date` para uniformidad con otros dashboards de la plataforma. Cualquier cambio en el esquema de Citas debe mantener este alias para evitar errores de "Invalid Date".

### 21.5 Robustez en Sincronización JIT (GCal Blocks)
Para evitar que fallos en un solo calendario bloqueen todo el sistema de disponibilidad, se implementó `ON CONFLICT (google_event_id) DO NOTHING` en las inserciones de `google_calendar_blocks`. Esto permite que agendas sugeridas o compartidas entre profesionales no generen duplicados ni errores 500 durante la consulta JIT.

### 21.6 Validación de Horarios Universales (Locale Isolation)
Se ha migrado la validación de `working_hours` del uso de nombres de días (`strftime("%A")`) a índices numéricos de Python (`target_date.weekday()`). 
*   **Razón**: El locale del servidor (Inglés vs Español) puede alterar los nombres de los días, rompiendo el mapeo con el JSONB de la base de datos. Usar `0-6` garantiza que el sistema funcione en cualquier entorno de despliegue (Local, Render, VPS).

### 21.7 Lógica "Service-First" en Agente IA
El protocolo de agendamiento se ha reestructurado para que el agente indague el servicio clínico **antes** de solicitar datos personales (DNI, Nombre).
*   **Objetivo**: Obtener la duración del tratamiento (`treatment_types`) de forma inmediata para que `check_availability` devuelva slots precisos.
*   **Sugerencia Contextual**: Si el paciente es vago, la IA sugiere tratamientos típicos según la especialidad del tenant.

---

## 22. Internacionalización (i18n) – Cómo añadir y mantener traducciones (2026-02-08)

### 22.1 Alcance
Toda la interfaz de la plataforma respeta el idioma elegido en **Configuración** (Español, English, Français). El idioma se persiste por sede en `tenants.config.ui_language` y se aplica a login, menús, formularios, agenda, analíticas, chats y componentes compartidos.

### 22.2 Añadir un texto traducido
1. **Añadir la clave en los tres archivos de locales:** `frontend_react/src/locales/es.json`, `en.json`, `fr.json`. Usar namespaces existentes (ej. `nav`, `common`, `config`, `login`, `agenda`, `chats`, `analytics`, `patient_detail`, `professionals`, `approvals`) o crear uno nuevo.
2. **En el componente:** Importar `useTranslation` desde `../context/LanguageContext` (o la ruta correcta), llamar `const { t } = useTranslation();` y usar `t('namespace.key')` en lugar del string fijo.

### 22.3 Ejemplo
```tsx
import { useTranslation } from '../context/LanguageContext';

function MyView() {
  const { t } = useTranslation();
  return <h1>{t('my_section.title')}</h1>;
}
```
En `es.json`: `"my_section": { "title": "Mi Título" }`. Repetir en `en.json` y `fr.json`.

### 22.4 Backend – Rutas admin y auth
Las rutas administrativas usan la dependencia **`verify_admin_token`** (valida JWT + header `X-Admin-Token` + rol). Para rutas solo CEO se comprueba `user_data.role == 'ceo'`. No usar únicamente `get_current_user` en endpoints que deban restringirse por rol. Ver lista completa de endpoints en `docs/AUDIT_ESTADO_PROYECTO.md` y `docs/API_REFERENCE.md`.

### 22.5 Documentación de contexto para IA
Para que otra IA tome contexto completo del proyecto en una nueva conversación, usar **`docs/CONTEXTO_AGENTE_IA.md`**: incluye stack, estructura, reglas obligatorias, cómo ejecutar, resumen de API, rutas frontend, base de datos, i18n e índice de documentación.

---

## 23. Landing pública y flujo demo (2026-02)

### 23.1 Rutas públicas
- **`/demo`**: Landing (LandingView). No está envuelta en `ProtectedRoute` ni en `Layout`. Accesible sin login.
- **`/login`**: LoginView. Público. Con query `?demo=1` se activa el modo demo (prellenado de credenciales y botón "Entrar a la demo").

### 23.2 Flujo "Probar app"
1. Usuario entra a `/demo` y hace clic en "Probar app".
2. Navega a `/login?demo=1`.
3. LoginView detecta `demo=1`, prellena email/contraseña con la cuenta demo y muestra solo el botón "Entrar a la demo".
4. Al hacer clic, se envía `POST /auth/login` con esas credenciales; si el login es correcto, se redirige al dashboard (`/`).

### 23.3 Credenciales y WhatsApp
- Las credenciales demo y el número de WhatsApp para "Probar Agente IA" están definidos en el frontend: `LoginView.tsx` (DEMO_EMAIL, DEMO_PASSWORD) y `LandingView.tsx` (WHATSAPP_NUMBER, mensaje predefinido). Para cambiar el número o el mensaje de WhatsApp, editar `LandingView.tsx`.

### 23.4 Especificación
Ver **README** (sección Landing / Demo pública) y **`docs/SPECS_IMPLEMENTADOS_INDICE.md`** para trazabilidad; detalle de la landing (móvil, conversión, estética) en código (LandingView, LoginView demo).

---

*Guía de Desarrolladores Dentalogic © 2026*
