# Gestión de Leads vs Pacientes (Workflow)

Este documento detalla el flujo de conversión de **Leads** (contactos iniciales) a **Pacientes** (con historia clínica activa), implementado en la Fase 14.

## 1. Definiciones

- **Lead (Guest):** Todo usuario nuevo que contacta por WhatsApp.
  - **Estado en BD:** `status='guest'`
  - **Datos mínimos:** Teléfono (automático por WhatsApp) y Nombre de Perfil WhatsApp.
  - **Limitaciones:** No se le genera ficha clínica ni puede agendar sin completar sus datos.

- **Paciente (Active):** Usuario con datos validados y al menos un turno agendado (o ficha creada manualmente).
  - **Estado en BD:** `status='active'`
  - **Datos requeridos:** Nombre, Apellido, DNI, Obra Social.

## 2. Flujo de Conversión por IA (WhatsApp)

El agente de IA sigue un protocolo estricto para evitar "basura" en la base de datos de pacientes activos.

### Protocolo de Agendamiento

1.  **Lead solicita turno:** El usuario dice "quiero un turno" o saluda.
2.  **Indagación de Servicio (Etapa Crítica - JIT):** 
    - El agente **DEBE** preguntar el tratamiento o consulta deseada antes de solicitar datos personales.
    - Esto permite calcular la **duración exacta del turno** (ej. 30 min para Limpieza vs 60 min para Endodoncia) y consultar disponibilidad real.
3.  **Verificación de Estado:** El sistema detecta si el usuario es `guest`.
4.  **Solicitud de Datos (Solo tras confirmación de interés):**
    - La IA solicita: Nombre, Apellido, DNI, Obra Social.
    - *Regla de Oro:* No se ejecuta `book_appointment` hasta tener los 4 datos y el horario elegido.
4.  **Verificación de Disponibilidad (JIT):**
    - Antes de confirmar, el sistema ejecuta una **Sincronización Just-In-Time**:
        - Limpia el nombre del profesional (ignora 'Dra.', 'Dr.').
        - Consulta Google Calendar en tiempo real.
        - Filtra bloqueos que ya son citas del sistema para evitar falsos negativos.
5.  **Reserva y Activación:**
    - Al llamar a `book_appointment(..., first_name, last_name, dni, insurance_provider)`, el sistema:
        1.  Valida que los campos no estén vacíos.
        2.  Actualiza el registro del paciente con los nuevos datos.
        3.  Cambia el status de `guest` a `active`.
        4.  Confirma el turno y lo guarda en BD + Google Calendar.

## 3. Flujo de Creación Manual (Admin Panel)

Para agilizar la recepción, el panel administrativo permite un "Alta Express":

1.  **Nuevo Paciente:** Se ingresan los datos personales (Nombre, Apellido, Tel, DNI, Obra Social).
2.  **Agendamiento Inmediato (Opcional):**
    - En el mismo modal de creación, se puede asignar un **Turno Inicial**.
    - Se selecciona: Tratamiento, Profesional, Fecha y Hora.
3.  **Ejecución:**
    - El backend crea el paciente (`active`) y, acto seguido, genera el turno asociado.

## 4. Filtrado en Dashboard

- Los Leads (`guest`) no ensucian la lista principal de pacientes hasta que concretan su primer turno.

## 5. Visibilidad en Chats (Contexto Clínico)

Para facilitar la atención humana, la vista de **Chats** integra un panel de **Contexto Clínico** que se sincroniza en tiempo real:

- **Detección Automática**: Al seleccionar una conversación, el sistema busca el perfil del paciente por número de teléfono.
- **Diferenciación Visual**:
    - **Leads**: Muestran "Sin citas programadas" y "Sin plan de tratamiento".
    - **Pacientes**: Muestran detalles de la última visita (incluyendo duración y profesional) y próximas citas agendadas.
- **Soberanía**: La información mostrada está estrictamente aislada por el `tenant_id` de la clínica actual.
