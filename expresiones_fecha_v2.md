**Expresiones de fecha — Contexto clínica Argentina**

Guía de interpretación para el agente IA de turnos

**1 — RELATIVAS AL TIEMPO**

| \# | EXPRESIÓN DEL PACIENTE | CÓMO DEBE INTERPRETARLO EL AGENTE |
| :---- | :---- | :---- |
| 01 | El mes que viene   **relativa**   | Cualquier fecha dentro del mes calendario siguiente al actual |
| 02 | A principios de mes   **relativa**   | Del 1 al 7 del mes más cercano disponible |
| 03 | A mediados de mes   **relativa**   | Del 12 al 18 del mes mencionado o siguiente |
| 04 | A fin / finales de mes   **relativa**   | Del 22 al último día del mes correspondiente |
| 05 | La semana que viene   **relativa**   | Lunes a domingo de la semana inmediata siguiente |
| 06 | Esta misma semana   **relativa**   | Lunes a viernes del ciclo en curso; incluir hoy si hay disponibilidad |
| 07 | Dentro de un par de días   **relativa**   | Hoy \+ 2 a hoy \+ 4 días; priorizar el extremo más próximo disponible |
| 08 | Pasado mañana   **relativa**   | Fecha exacta: hoy \+ 2 días; sin restricción de franja |
| 09 | Antes de que termine el mes   **relativa**   | Fecha máxima \= último día del mes en curso; fecha mínima \= mañana |
| 10 | El mes que viene, la segunda quincena   **relativa**   | Del 15 al último día del mes siguiente; ignorar la primera quincena |

**2 — DÍAS Y HORARIOS ESPECÍFICOS**

| \# | EXPRESIÓN DEL PACIENTE | CÓMO DEBE INTERPRETARLO EL AGENTE |
| :---- | :---- | :---- |
| 11 | El 12 o el 15, lo que haya   **específica**   | Prioridad en esas dos fechas exactas; si no hay disponibilidad, preguntar alternativa |
| 12 | Antes de mi viaje / de la operación   **específica**   | Fecha límite declarada por el paciente; priorizar el hueco más próximo antes de esa fecha |
| 13 | La próxima semana pero no el lunes   **específica**   | Martes a viernes de la semana siguiente; excluir explícitamente el día mencionado |
| 14 | Un día de semana, no importa cuál   **específica**   | Lunes a viernes; preguntar franja horaria para acotar; ofrecer el hueco más próximo |

**3 — PREFERENCIAS SIN FECHA FIJA (FLEXIBLES)**

| \# | EXPRESIÓN DEL PACIENTE | CÓMO DEBE INTERPRETARLO EL AGENTE |
| :---- | :---- | :---- |
| 15 | Cualquier martes o jueves por la tarde   **flexible**   | Día de la semana \+ franja tarde; sin fecha fija; repetible cualquier semana |
| 16 | Un día que no sea viernes   **flexible**   | Disponibilidad abierta excluyendo el día indicado; ofrecer cualquier otro día hábil |
| 17 | Tengo libre recién después del 20   **flexible**   | Fecha mínima: día 21 del mes en curso o siguiente; sin límite superior declarado |
| 18 | Después de que salga del trabajo   **flexible**   | Franja tarde-noche; sin restricción de fecha; confirmar días en que trabaja |
| 19 | Cuando no tenga que llevar a los chicos al colegio   **flexible**   | Excluir horario de entrada escolar en días hábiles; franja libre posterior o fin de semana |
| 20 | Después de las vacaciones   **flexible**   | Preguntar fecha de regreso; agendar desde ese día \+ 2 días de margen mínimo |
| 21 | Cuando haya lugar, no me apuro   **flexible**   | Sin urgencia; ofrecer el primer hueco disponible sin forzar fecha; prioridad baja |
| 22 | Me da igual cuándo, que sea de mañana   **flexible**   | Sin restricción de fecha; franja fija: turno de mañana |

**4 — URGENTES O INMEDIATAS**

| \# | EXPRESIÓN DEL PACIENTE | CÓMO DEBE INTERPRETARLO EL AGENTE |
| :---- | :---- | :---- |
| 23 | Lo antes posible / cuando puedan   **urgente**   | Ofrecer el primer turno disponible; confirmar si acepta las próximas 48–72 hs |
| 24 | Hoy mismo si se puede   **urgente**   | Prioridad máxima ese día; si no hay lugar, ofrecer el turno más próximo disponible |
| 25 | Necesito algo esta semana sí o sí   **urgente**   | Fecha límite \= viernes de la semana en curso; ofrecer cualquier hueco disponible sin filtrar día |

**5 — AMBIGUAS — REQUIEREN REPREGUNTA OBLIGATORIA**

| \# | EXPRESIÓN DEL PACIENTE | CÓMO DEBE INTERPRETARLO EL AGENTE |
| :---- | :---- | :---- |
| 26 | Cualquier día está bien | No asumir libertad total; preguntar franja preferida y ofrecer 2 opciones concretas |
| 27 | Pronto, pero tampoco tan pronto | Rango orientativo: hoy \+ 4 a hoy \+ 14 días; preguntar si hay alguna semana que prefiera evitar |
| 28 | Cuando ustedes puedan | El paciente delega completamente; asignar el primer hueco disponible y confirmar antes de cerrar |
| 29 | Lo que haya / no sé | Sin preferencia declarada; ofrecer máximo 2 opciones concretas; esperar confirmación del paciente |

**LEYENDA      relativa**    fecha calculada desde hoy          **específica**    día o límite exacto          **flexible**    preferencia sin fecha fija          **urgente**    prioridad máxima, ASAP