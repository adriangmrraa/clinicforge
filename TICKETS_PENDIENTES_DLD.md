# ClinicForge — Tickets Pendientes DLD (Dra. Laura Delgado)

> Fecha de generacion: 22 de abril 2026
> Proyecto Jira: DLD — https://codexyoficial.atlassian.net/browse/DLD
> Total pendientes: 10 | Finalizados: 21 | Total historico: 31

---

## Resumen Ejecutivo

El proyecto tiene 10 tickets abiertos organizados en 3 bloques funcionales:

1. **Bugs criticos de plataforma** (DLD-26, DLD-29, DLD-31) — La agenda crashea, el encabezado no es sticky, y la historia de evolucion tira error. Afectan la operatoria diaria.
2. **Modulo de Presupuestos** (DLD-20, DLD-27) — El modulo financiero esta incompleto: no registra metodo de pago, no soporta cuotas, y la navegacion se traba.
3. **Agente IA + Lanzamiento** (DLD-22, DLD-23, DLD-25) — Pulir el agente, agregar flujo ART, y lanzar a produccion.
4. **Mejoras UX** (DLD-30) — Impresion de agenda.
5. **Documentacion** (DLD-28) — Funcionalidades fuera de alcance documentadas.

### Orden de ejecucion recomendado

```
FASE 1 — Bugs bloqueantes (paralelo)
  [Agente A] DLD-26  Crash agenda entre meses        (frontend)
  [Agente B] DLD-31  Historia evolucion + signos      (frontend + backend)
  [Agente C] DLD-29  Encabezado sticky agenda         (frontend CSS)

FASE 2 — Presupuestos (secuencial, dependen entre si)
  [Agente D] DLD-27  Rediseño modulo presupuestos     (full-stack)
  [Agente D] DLD-20  Metodo de pago en presupuestos   (se absorbe en DLD-27)

FASE 3 — Agente IA (secuencial)
  [Agente E] DLD-25  Flujo ART en agente IA           (backend AI + frontend)
  [Agente E] DLD-22  Pulir agente IA completo         (backend AI + testing)

FASE 4 — Mejoras UX
  [Agente F] DLD-30  Impresion de agenda              (frontend)

FASE 5 — Cierre
  [Manual]   DLD-23  Reunion de cierre + deploy       (coordinacion humana)
  [Cerrar]   DLD-28  Ya esta documentado, solo cerrar (sin codigo)
```

### Dependencias

```
DLD-20 ──► se absorbe en DLD-27 (mismo modulo)
DLD-22 ──► depende de que DLD-6/17/18/19/20 esten cerrados (la mayoria ya lo esta)
DLD-23 ──► depende de DLD-22 (agente aprobado por la doctora)
DLD-25 ──► independiente, pero se valida dentro de DLD-22
```

---

## Tickets Detallados

---

### DLD-26 — Bug: Agenda crashea al navegar entre meses

| Campo | Valor |
|-------|-------|
| **Jira** | https://codexyoficial.atlassian.net/browse/DLD-26 |
| **Tipo** | Bug |
| **Prioridad** | HIGH |
| **Creado** | 21 abril 2026 |
| **Asignado** | Sin asignar |
| **Bloque** | Frontend (React + FullCalendar) |

#### Que esta pasando

Al navegar de un mes a otro en la agenda (ej: abril a mayo) y luego entrar a vista semanal o diaria del mes destino, ocurren dos cosas:

1. **Carga indefinida**: los turnos no renderizan, la agenda queda en loading eterno
2. **Crash completo**: la aplicacion se rompe, hay que recargar

#### Causa probable

El componente FullCalendar probablemente no esta manejando bien el cambio de rango de fechas cuando se pasa de un mes a otro y se cambia de vista simultaneamente. Puede ser:
- El fetch de appointments usa el rango viejo mientras la vista ya cambio
- Race condition entre `datesSet` callback y el cambio de vista
- El state del calendario se desincroniza con los datos del backend

#### Archivos clave a investigar

- `frontend_react/src/views/AgendaView.tsx` — Vista principal de agenda
- `frontend_react/src/components/` — Componentes de calendario
- `orchestrator_service/admin_routes.py` — Endpoint de appointments por rango

#### Criterio de exito

- Navegar libremente entre meses sin crash
- Cambiar de vista mensual a semanal/diaria en cualquier mes sin error
- Los turnos se renderizan correctamente en el mes destino

#### Instrucciones para el agente

```
Sos un agente Claude trabajando en el proyecto ClinicForge.
Lee CLAUDE.md para contexto completo del proyecto.

TICKET: DLD-26 — Bug: Agenda crashea al navegar entre meses
JIRA: https://codexyoficial.atlassian.net/browse/DLD-26

PROBLEMA: Al navegar de abril a mayo (o cualquier mes) en la vista mensual y luego
entrar a vista semanal/diaria, la agenda crashea o queda en loading infinito.

PASOS:
1. Lee AgendaView.tsx y los componentes de calendario para entender el flujo actual
2. Busca el handler de datesSet/dateChange y como se fetchean los appointments
3. Identifica la race condition o el state desincronizado
4. Corregilo asegurando que el fetch de datos se sincronice con el cambio de vista
5. Verifica que la solucion funcione en las 3 vistas: mes, semana, dia

REGLAS:
- No rompas otros flujos de la agenda (drag-drop, edicion de turnos, etc.)
- Respeta el dark mode (ver CLAUDE.md)
- Usa el patron de scroll isolation del proyecto
```

---

### DLD-31 — Historia de evolucion con error + eliminar Signos Vitales

| Campo | Valor |
|-------|-------|
| **Jira** | https://codexyoficial.atlassian.net/browse/DLD-31 |
| **Tipo** | Bug + Mejora |
| **Prioridad** | HIGH |
| **Creado** | 21 abril 2026 |
| **Asignado** | Sin asignar |
| **Bloque** | Frontend + Backend |

#### Que esta pasando

Dos problemas en la ficha de paciente:

1. **Historia de evolucion tira error** al intentar cargar datos del paciente. El equipo no puede registrar ni consultar la evolucion clinica.
2. **Signos Vitales aparece en la UI** pero la doctora no lo usa ni lo necesita. Genera confusion y ruido visual.

#### Causa probable

- El endpoint o query que trae la historia de evolucion puede tener un error de schema (campo faltante, tipo incorrecto, null no manejado)
- Signos Vitales es una seccion del frontend que simplemente hay que remover del render

#### Archivos clave a investigar

- `frontend_react/src/views/` — Vista de ficha de paciente (buscar "evolucion" o "evolution")
- `frontend_react/src/components/` — Componente de historia clinica
- `orchestrator_service/admin_routes.py` — Endpoints de clinical records
- `orchestrator_service/models.py` — Modelos de ClinicalRecord / evolution

#### Criterio de exito

- La historia de evolucion carga sin errores
- La seccion de Signos Vitales desaparece de la UI
- El resto de la ficha del paciente sigue funcionando normal

#### Instrucciones para el agente

```
Sos un agente Claude trabajando en el proyecto ClinicForge.
Lee CLAUDE.md para contexto completo del proyecto.

TICKET: DLD-31 — Historia de evolucion con error + eliminar Signos Vitales
JIRA: https://codexyoficial.atlassian.net/browse/DLD-31

DOS TAREAS:
1. BUGFIX: La historia de evolucion dentro de la ficha de paciente tira error al cargar.
   - Investiga el endpoint que trae los datos de evolucion
   - Revisa el componente frontend que los renderiza
   - Encontra el error (null handling, schema mismatch, etc.) y corregi

2. REMOVER: La seccion "Signos Vitales" no es requerida por la doctora.
   - Encontra donde se renderiza en la ficha del paciente
   - Eliminala de la UI (no borres datos del backend, solo ocultala)

REGLAS:
- No toques el backend schema — solo fix de queries/endpoints si es necesario
- Dark mode obligatorio
- No rompas el resto de la ficha del paciente
```

---

### DLD-29 — Encabezado sticky en agenda al scrollear

| Campo | Valor |
|-------|-------|
| **Jira** | https://codexyoficial.atlassian.net/browse/DLD-29 |
| **Tipo** | Bug UX |
| **Prioridad** | HIGH |
| **Creado** | 21 abril 2026 |
| **Asignado** | Sin asignar |
| **Bloque** | Frontend (CSS) |

#### Que esta pasando

En las vistas Semana y Dia de la agenda, cuando el usuario scrollea hacia abajo para ver horarios de tarde/noche, el encabezado con los nombres de los dias (lun 20/4, mar 21/4, etc.) y el rango de fechas desaparecen. La secretaria y la doctora pierden la referencia de que columna es que dia, causando errores al asignar turnos.

#### Solucion

Es un fix de CSS puro en principio:
- `position: sticky; top: 0` en el header de columnas de dias
- `z-index` adecuado para que quede por encima del contenido
- Aplicar en vistas: Semana, Dia y Lista
- El toolbar de navegacion (flechas, "Hoy", rango de fechas) tambien debe ser sticky

#### Archivos clave a investigar

- `frontend_react/src/views/AgendaView.tsx` — Vista de agenda
- CSS/Tailwind del header del calendario (FullCalendar custom styles)

#### Criterio de exito

- Al scrollear en vista Semana, los nombres de dias quedan visibles arriba
- Al scrollear en vista Dia, el nombre del dia queda visible
- El toolbar de navegacion (Hoy, flechas, rango) tambien queda sticky
- No se rompe el layout en ninguna vista

#### Instrucciones para el agente

```
Sos un agente Claude trabajando en el proyecto ClinicForge.
Lee CLAUDE.md para contexto completo del proyecto.

TICKET: DLD-29 — Encabezado sticky en agenda
JIRA: https://codexyoficial.atlassian.net/browse/DLD-29

PROBLEMA: El encabezado de dias (lun/mar/mie...) y el toolbar de navegacion
desaparecen al scrollear la agenda. Necesitan ser sticky.

PASOS:
1. Lee AgendaView.tsx y encontra el componente de FullCalendar
2. Identifica los selectores CSS del header de columnas (FullCalendar genera
   clases como .fc-col-header, .fc-scrollgrid, etc.)
3. Aplica position: sticky con z-index al header de dias
4. Aplica lo mismo al toolbar de navegacion si no es sticky ya
5. Verifica en vistas: Semana, Dia, Lista

REGLAS:
- Usa Tailwind o CSS custom segun el patron existente
- No modifiques la logica JS, esto es solo CSS
- Dark mode obligatorio
- Testa que el scroll isolation (h-screen, overflow-hidden) siga funcionando
```

---

### DLD-27 — Rediseño modulo de Presupuestos (cuotas, pagos, navegacion)

| Campo | Valor |
|-------|-------|
| **Jira** | https://codexyoficial.atlassian.net/browse/DLD-27 |
| **Tipo** | Mejora (rediseño) |
| **Prioridad** | HIGH |
| **Creado** | 21 abril 2026 |
| **Asignado** | Sin asignar |
| **Bloque** | Full-stack |

#### Que esta pasando

El modulo de presupuestos tiene problemas serios de usabilidad:

1. **Se traba**: una vez creado el presupuesto, no se puede volver atras ni editar. La UI queda en un estado sin salida.
2. **Sin metodo de pago**: no se puede registrar si fue efectivo, transferencia o tarjeta.
3. **Sin cuotas**: no se puede dividir un presupuesto en pagos parciales.
4. **Sin marcado manual**: no hay forma de tildar "pagado" manualmente.
5. **Sin resumen de cuentas**: la secretaria no tiene un reporte de cobros por paciente/periodo.

#### NOTA: DLD-20 se absorbe aca

DLD-20 (metodo de pago en presupuestos) es un subset de este ticket. Si se resuelve DLD-27 completo, DLD-20 se puede cerrar automaticamente.

#### Alcance del trabajo

- **Backend**: agregar campos de cuotas, metodo de pago, estado de pago por cuota. Posiblemente una tabla nueva `budget_installments` o campos JSONB.
- **Frontend**: rediseñar el flujo de creacion/edicion de presupuestos. Agregar vista de resumen de cuentas.
- **Requiere exploracion previa**: el ticket pide que el dev detalle como esta armado el modulo actual antes de rediseñar.

#### Archivos clave a investigar

- `frontend_react/src/views/` — Vista de presupuestos (buscar "budget", "presupuesto", "billing")
- `orchestrator_service/admin_routes.py` — Endpoints de presupuestos
- `orchestrator_service/models.py` — Modelos de Treatment Plans / Billing

#### Criterio de exito

- Flujo de presupuesto navegable (crear, editar, volver atras)
- Soporte de cuotas con montos y fechas
- Registro de metodo de pago por cuota
- Marcado manual de "pagado" por cuota
- Resumen de cuentas por paciente y periodo

#### Instrucciones para el agente

```
Sos un agente Claude trabajando en el proyecto ClinicForge.
Lee CLAUDE.md para contexto completo del proyecto.

TICKET: DLD-27 — Rediseño modulo de Presupuestos
JIRA: https://codexyoficial.atlassian.net/browse/DLD-27
ABSORBE: DLD-20 (metodo de pago)

ESTE TICKET REQUIERE EXPLORACION PRIMERO. Antes de escribir codigo:

1. EXPLORA el estado actual del modulo de presupuestos:
   - Busca en models.py las tablas de treatment_plans, billing, budgets
   - Busca en admin_routes.py los endpoints de presupuestos
   - Busca en el frontend la vista de presupuestos
   - Documenta: estructura de datos actual, estados posibles, flujo de navegacion

2. PROPONE un diseño que resuelva:
   - Navegacion fluida (crear → editar → volver sin trabarse)
   - Cuotas: tabla o JSONB para installments (monto, fecha_vencimiento, estado, metodo_pago)
   - Metodo de pago: efectivo, transferencia, tarjeta (por cuota)
   - Marcado manual de pagado
   - Resumen de cuentas exportable

3. IMPLEMENTA con migracion Alembic si necesitas cambios de schema.
   IMPORTANTE: antes de crear la migracion, correr
   ls orchestrator_service/alembic/versions/ para confirmar el head actual.

REGLAS:
- Multi-tenant: SIEMPRE tenant_id en queries
- Dark mode obligatorio
- i18n: textos con useTranslation()
- Convenciones de CLAUDE.md
```

---

### DLD-25 — Flujo ART en el Agente IA

| Campo | Valor |
|-------|-------|
| **Jira** | https://codexyoficial.atlassian.net/browse/DLD-25 |
| **Tipo** | Feature |
| **Prioridad** | MEDIUM |
| **Creado** | 21 abril 2026 |
| **Asignado** | Sin asignar |
| **Bloque** | Backend AI + Frontend |

#### Que esta pasando

El sistema no contempla pacientes derivados por ART (Aseguradora de Riesgos del Trabajo). En estos casos:
- Una empresa contacta la clinica para agendar a un empleado/accidentado
- El que llama NO es el paciente
- El agente IA no detecta ni diferencia este caso
- No hay flujo para registrar un paciente ART con datos provisorios

#### Decision pendiente

Hay dos opciones planteadas. **Recomendacion del ticket: Opcion A**.

- **Opcion A** (preferida): El agente IA detecta ART, pide DNI, crea paciente ficticio automatico ("Paciente ART") y agenda.
- **Opcion B**: El agente detecta ART y deriva a la secretaria para gestion manual.

#### Alcance completo

1. **Backend AI**: Deteccion de caso ART en el agente, creacion de paciente ficticio con DNI
2. **Frontend**: Diferenciacion visual en TODAS las vistas:
   - Lista de pacientes: badge/etiqueta "ART" en color
   - Agenda: turno ART con borde o icono diferente
   - Ficha: indicador de paciente ART + alerta de datos incompletos
3. **Post-agendamiento**: El profesional debe completar datos reales antes de atender

#### Archivos clave a investigar

- `orchestrator_service/main.py` — System prompt + tools del agente (DENTAL_TOOLS)
- `orchestrator_service/main.py` — Tool `book_appointment`
- `orchestrator_service/models.py` — Modelo Patient (agregar campo `is_art` o similar)
- `frontend_react/src/views/PatientsView.tsx` — Lista de pacientes
- `frontend_react/src/views/AgendaView.tsx` — Turnos en agenda

#### Criterio de exito

- El agente IA detecta casos ART correctamente
- Crea paciente ficticio con DNI provisto
- El turno queda agendado
- Diferenciacion visual ART en todas las vistas
- Alerta de datos incompletos al abrir ficha/turno ART
- El profesional puede completar datos reales

#### Instrucciones para el agente

```
Sos un agente Claude trabajando en el proyecto ClinicForge.
Lee CLAUDE.md para contexto completo del proyecto.

TICKET: DLD-25 — Flujo ART en el Agente IA
JIRA: https://codexyoficial.atlassian.net/browse/DLD-25

DECISION TOMADA: Implementar Opcion A (agente IA crea paciente ficticio automatico).

PASOS:
1. BACKEND AI:
   - Modifica el system prompt en main.py para detectar casos ART
   - Agrega logica en book_appointment o un nuevo tool para crear paciente ART
   - El paciente se crea con: nombre "Paciente ART", DNI provisto, obra_social "ART"

2. MODELO:
   - Agrega campo al modelo Patient para marcar ART (ej: patient_source = 'art')
   - Migracion Alembic (confirmar head con ls antes de crear)

3. FRONTEND:
   - Badge "ART" en PatientsView (lista)
   - Borde/icono diferenciador en AgendaView (turnos)
   - Alerta en ficha del paciente si datos incompletos + es ART

REGLAS:
- Multi-tenant SIEMPRE
- Dark mode
- i18n
- No rompas el flujo de booking normal
- El flujo de terceros/menores ya existe (ver CLAUDE.md seccion Third-Party)
  El flujo ART es similar pero con paciente ficticio
```

---

### DLD-22 — Pulir Agente IA y entregar para pruebas

| Campo | Valor |
|-------|-------|
| **Jira** | https://codexyoficial.atlassian.net/browse/DLD-22 |
| **Tipo** | Objetivo / QA |
| **Prioridad** | HIGH |
| **Creado** | 21 abril 2026 |
| **Asignado** | Sin asignar |
| **Bloque** | Backend AI + Testing |

#### Que esta pasando

Este es un ticket paraguas de QA. Antes de entregar el agente a la doctora para pruebas, hay que verificar que TODO funcione:

1. **Flujo de muestra**: el agente se presenta, responde, guia al paciente
2. **Flujo de agendamiento**: ofrece turnos reales, verifica disponibilidad, confirma, registra
3. **Todos los bugs previos resueltos**: DLD-6 (disponibilidad), DLD-17 (edicion), DLD-18 (formulario), DLD-19 (UX agenda)

#### PRIORIDAD CRITICA

> No se aprueba NINGUN cambio en el agente IA si el flujo de muestra o de agendamiento falla.

#### Alcance

- Revision de bugs abiertos del agente (la mayoria ya estan cerrados)
- Test end-to-end del flujo completo de conversacion
- Verificar: no confirma sin disponibilidad, no ofrece horarios pasados, deriva correctamente
- Entregar acceso a la doctora para pruebas con casos reales

#### Archivos clave

- `orchestrator_service/main.py` — Agente completo (system prompt + tools)
- `orchestrator_service/services/buffer_task.py` — Pipeline de mensajes
- `whatsapp_service/` — Integracion WhatsApp

#### Instrucciones para el agente

```
Sos un agente Claude trabajando en el proyecto ClinicForge.
Lee CLAUDE.md para contexto completo del proyecto.

TICKET: DLD-22 — Pulir Agente IA para pruebas
JIRA: https://codexyoficial.atlassian.net/browse/DLD-22

ESTE ES UN TICKET DE QA, NO DE DESARROLLO.

TAREAS:
1. Lee el system prompt completo del agente en main.py
2. Verifica que las tools book_appointment y check_availability:
   - No confirmen sin disponibilidad real
   - No ofrezcan horarios pasados
   - Respeten working_hours del tenant
3. Verifica que el agente derive correctamente (no diagnostique tratamientos)
4. Revisa que DLD-6, DLD-9 esten efectivamente resueltos en el codigo
5. Documenta cualquier issue que encuentres

REGLAS:
- NO hagas cambios especulativos
- Si encontras un bug, documentalo con: archivo, linea, descripcion, impacto
- Si todo esta bien, reporta "LISTO PARA PRUEBAS" con el checklist verificado
```

---

### DLD-30 — Impresion de agenda diaria/semanal

| Campo | Valor |
|-------|-------|
| **Jira** | https://codexyoficial.atlassian.net/browse/DLD-30 |
| **Tipo** | Feature |
| **Prioridad** | MEDIUM |
| **Creado** | 21 abril 2026 |
| **Asignado** | Sin asignar |
| **Bloque** | Frontend |

#### Que esta pasando

No hay forma de imprimir o exportar la agenda. La clinica necesita copia fisica o PDF de los turnos para recepcion, sala de espera y consultorio.

#### Solucion propuesta

1. Boton de impresion en el header de la agenda
2. `@media print` CSS que oculte sidebar, botones, y muestre solo:
   - Nombre de clinica + profesional
   - Rango de fecha
   - Turnos: horario, paciente, tratamiento, profesional
3. Compatible con Ctrl+P y exportacion PDF del navegador

#### Archivos clave

- `frontend_react/src/views/AgendaView.tsx`
- CSS global o un `print.css` nuevo

#### Instrucciones para el agente

```
Sos un agente Claude trabajando en el proyecto ClinicForge.
Lee CLAUDE.md para contexto completo del proyecto.

TICKET: DLD-30 — Impresion de agenda
JIRA: https://codexyoficial.atlassian.net/browse/DLD-30

IMPLEMENTAR:
1. Boton de impresion (icono Printer de lucide-react) en el toolbar de AgendaView
2. Al clickear: window.print()
3. @media print CSS que:
   - Oculte sidebar, NovaWidget, toolbar buttons (excepto titulo)
   - Muestre la agenda con fondo blanco (override dark mode para impresion)
   - Formato limpio: nombre clinica, fecha, tabla de turnos
4. Vista semanal: una columna por dia
5. Vista diaria: lista por hora

REGLAS:
- Solo frontend, no backend
- El boton debe respetar dark mode (la impresion puede ser light)
- i18n para el tooltip del boton
- Usa lucide-react para el icono (Printer)
```

---

### DLD-23 — Reunion de cierre y lanzamiento a produccion

| Campo | Valor |
|-------|-------|
| **Jira** | https://codexyoficial.atlassian.net/browse/DLD-23 |
| **Tipo** | Objetivo / Coordinacion |
| **Prioridad** | HIGH |
| **Creado** | 21 abril 2026 |
| **Asignado** | Sin asignar |
| **Bloque** | Manual (no es codigo) |

#### Que esta pasando

Este ticket es el cierre del proyecto. Una vez que el agente IA este aprobado por la doctora (DLD-22), se hace reunion final y se lanza a produccion.

#### Dependencias

- DLD-22 debe estar COMPLETO y aprobado por la doctora
- Todos los bugs bloqueantes deben estar cerrados
- El sistema debe estar estable

#### Tareas (manuales)

1. Coordinar reunion con la Dra. Laura Delgado y secretaria
2. Confirmar aprobacion del agente y plataforma
3. Ejecutar pase a produccion
4. Verificar flujos en produccion: agente, plantillas, agenda, presupuestos
5. Comunicar a la clinica que el sistema esta activo

> Este ticket NO se delega a un agente Claude. Es coordinacion humana.

---

### DLD-28 — Documentacion: funcionalidades fuera de alcance DLD-17

| Campo | Valor |
|-------|-------|
| **Jira** | https://codexyoficial.atlassian.net/browse/DLD-28 |
| **Tipo** | Documentacion |
| **Prioridad** | LOW |
| **Creado** | 21 abril 2026 |
| **Asignado** | Sin asignar |
| **Bloque** | Ninguno (ya documentado) |

#### Que esta pasando

Durante DLD-17 se identificaron 2 funcionalidades que quedaron fuera de alcance:

1. **Reasignar paciente desde modal de turno** — El campo paciente es solo lectura. Reasignar rompe la cadena clinica. Flujo correcto: cancelar y reagendar.
2. **Editar datos del paciente desde modal de turno** — Ya existe en PatientsView (DLD-18, DLD-24). Duplicar agrega complejidad sin valor.

#### Accion

Este ticket ya esta documentado en si mismo. Se puede:
- **Cerrar como "Won't Do"** si no se van a implementar
- **Dejar abierto** como backlog futuro si el PM quiere priorizarlas despues

> No requiere agente Claude. Decision de producto.

---

## Matriz de Asignacion Sugerida

| Agente | Tickets | Perfil requerido | Estimacion |
|--------|---------|-------------------|------------|
| **Agente A** | DLD-26 | Frontend React + FullCalendar | 1-2 horas |
| **Agente B** | DLD-31 | Frontend + Backend (ficha paciente) | 1-2 horas |
| **Agente C** | DLD-29 | Frontend CSS (sticky headers) | 30 min - 1 hora |
| **Agente D** | DLD-27 + DLD-20 | Full-stack (presupuestos completo) | 3-4 horas |
| **Agente E** | DLD-25 + DLD-22 | Backend AI + System prompt + QA | 3-4 horas |
| **Agente F** | DLD-30 | Frontend (print CSS) | 1 hora |
| **Manual** | DLD-23 | Coordinacion humana | — |
| **Cerrar** | DLD-28 | Decision de producto | — |

### Notas para delegacion

1. **Cada agente debe leer CLAUDE.md PRIMERO** — Contiene las reglas criticas del proyecto (multi-tenant, dark mode, i18n, scroll isolation).
2. **Migraciones Alembic**: antes de crear una migracion, SIEMPRE correr `ls orchestrator_service/alembic/versions/` para confirmar el head real. NUNCA confiar en la documentacion.
3. **DLD-27 y DLD-20 van juntos**: DLD-20 es un subset de DLD-27. Implementar DLD-27 primero y cerrar DLD-20 como absorbido.
4. **DLD-22 va DESPUES de DLD-25**: El flujo ART debe estar implementado antes de la revision general del agente.
5. **DLD-23 no es codigo**: Es reunion de cierre. Solo se ejecuta cuando todo lo demas este listo.
