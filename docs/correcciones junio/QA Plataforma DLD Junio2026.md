**QA — PLATAFORMA · CLINICFORGE**

**Registro de problemas**

**ClinicForge · Clínica Dra. Laura Delgado**

**Fecha:** 11/06/2026

**Entorno:** Producción

**Reportado por:** Lucas — Codexy

**Estado:** Documento vivo — se agregan ítems a medida que se detectan

**Contexto:** Las funciones de historia de evolución y evaluación agregadas recientemente introdujeron regresiones. Este documento las consolida junto con problemas de seguimientos, recordatorios, plantillas y la preparación de tracking para Meta Ads.

**ÍNDICE**

| ID | Problema / Tarea | Prioridad |
| :---- | :---- | ----- |
| **P-01** | Odontograma: duplica las marcas de hallazgos | **URGENTE** |
| **P-02** | Historia de evolución: no guarda las entradas | **URGENTE** |
| **P-03** | Recordatorio de turnos: no automático \+ cobertura incompleta | **ALTA** |
| **P-04** | Envío de seguimientos no funciona | **ALTA** |
| **P-05** | Plantillas: revisión integral de envíos | **ALTA** |
| **P-06** | Agente IA: verificación de funcionamiento | **MEDIA** |
| **P-07** | Meta Ads: tracking del contenido/leads en la plataforma | **PLANIF.** |

# **P-01 — Odontograma: duplica las marcas de hallazgos  \[URGENTE\]**

**PROBLEMA**

Al cargar un hallazgo en el odontograma, el sistema lo registra también en una cara que no fue indicada: **marca dos caras en lugar de una**.

**EJEMPLO**

**PEDIDO**  Caries en la cara oclusal.

**RESULTADO ACTUAL**  Agrega caries en la cara oclusal **y también en la vestibular**.

**ESPERADO**  Registra caries únicamente en la cara oclusal.

**COMPORTAMIENTO ESPERADO**

* El hallazgo se registra solo en la cara/superficie indicada, sin duplicar en otras caras.

**IMPACTO**

El odontograma es parte de la ficha clínica del paciente. Un registro duplicado es información clínica incorrecta. Prioridad urgente.

# **P-02 — Historia de evolución: no guarda las entradas  \[URGENTE\]**

**PROBLEMA**

Es parte de las funciones de historia/evaluación agregadas recientemente. Al pedir cargar una historia o evolución de un paciente, el sistema falla y **no agrega la entrada**.

**COMPORTAMIENTO ESPERADO**

* La historia/evolución se guarda correctamente y queda asociada al paciente.

* Revisar la regresión introducida por las features nuevas de historia y evaluación.

**IMPACTO**

El paciente queda sin registro de evolución clínica. Prioridad urgente.

# **P-03 — Recordatorio de turnos: no se dispara automáticamente y no cubre a todos  \[ALTA\]**

**PROBLEMA**

El recordatorio de turnos **no funciona de forma automática**. Además, cuando se envía, **no llega a la totalidad de los pacientes agendados** para ese día.

**COMPORTAMIENTO ESPERADO**

* El recordatorio se dispara de forma automática para la fecha correspondiente.

* Cobertura del 100% de los pacientes agendados para ese día — ninguno queda sin recordatorio.

**IMPACTO**

Pacientes sin recordatorio se traduce en ausencias y huecos en la agenda. Afecta directo la facturación del día.

# **P-04 — Envío de seguimientos no funciona  \[ALTA\]**

**PROBLEMA**

Los mensajes de seguimiento a pacientes no se están enviando.

**COMPORTAMIENTO ESPERADO**

* Los seguimientos se envían según el flujo configurado.

* Verificar el trigger/programación que dispara estos envíos.

**IMPACTO**

Se pierde el contacto de seguimiento post-turno, pieza clave del flujo de retención y control. (Relacionado con E-08 del Registro de errores — Agente IA.)

# **P-05 — Plantillas: revisión integral de envíos  \[ALTA\]**

**TAREA**

Verificar que todas las plantillas que deben enviarse se disparen y lleguen correctamente: confirmación, recordatorio, seguimiento, pre-tratamiento y demás.

**COMPORTAMIENTO ESPERADO**

* Cada plantilla se envía cuando corresponde, una sola vez y con el contenido correcto.

**IMPACTO**

Las fallas de plantillas afectan toda la comunicación con el paciente. (Relacionado con E-01 del Registro de errores — Agente IA: envío múltiple de plantillas.)

# **P-06 — Agente IA: verificación de funcionamiento  \[MEDIA\]**

**TAREA**

Chequear el funcionamiento general del agente IA tras los cambios recientes y confirmar que opere correctamente.

**COMPORTAMIENTO ESPERADO**

* El agente responde, agenda y deriva según lo definido, sin regresiones.

**REFERENCIA**

Los casos puntuales detectados están documentados en el Registro de errores — Agente IA (E-01 a E-09).

# **P-07 — Meta Ads: tracking del contenido/leads en la plataforma  \[PLANIF.\]**

**CONTEXTO**

Se planea lanzar una campaña de Meta Ads en los próximos días.

**TAREA**

* Asegurar que la plataforma trackee correctamente el contenido y los leads que ingresan a través de ella.

* Validar la atribución antes del lanzamiento para poder medir el rendimiento de la campaña con datos confiables.

**IMPACTO**

Sin tracking confiable no se puede evaluar el CPL ni optimizar la campaña; se invierte a ciegas.