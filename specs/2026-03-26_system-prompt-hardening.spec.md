# SPEC: System Prompt Hardening — Cobertura Completa de Escenarios Dentales

**Fecha**: 2026-03-26
**Proyecto**: ClinicForge
**Prioridad**: Alta
**Costo**: $0 (solo cambios en system prompt + FAQs de sistema)
**Dependencia**: Ninguna (trabaja sobre build_system_prompt() existente)

---

## 1. OBJETIVO

Cerrar las 12 brechas detectadas en el system prompt del agente IA de WhatsApp/Instagram/Facebook. Hoy el agente maneja bien el flujo de agendamiento pero falla ante escenarios reales frecuentes: preguntas sobre obra social, cuidados post-tratamiento, planes de pago, quejas, embarazo, conversacion social, etc.

**Resultado esperado**: El agente puede resolver el 95% de las interacciones de un paciente dental sin derivar a humano, manteniendo tono profesional y compliance con datos sensibles de salud.

---

## 2. ESTRATEGIA DE IMPLEMENTACION

### Hibrida (prompt directo + FAQs de sistema + campos configurables)

| Prioridad | Debilidad | Metodo | Razon |
|-----------|-----------|--------|-------|
| 1 | Obra social/seguros | Campo DB + prompt | Cada clinica tiene convenios distintos |
| 2 | Planes de pago/medios | Campo DB + prompt | Configurable por tenant |
| 3 | Post-tratamiento | Prompt directo | Cuidados universales en odontologia |
| 4 | Quejas (escalamiento) | Prompt directo | Protocolo unico para todas las clinicas |
| 5 | Condiciones especiales | Prompt directo | Respuestas universales de seguridad |
| 6 | Conversacion social | Prompt directo | Reglas de interaccion humana |
| 7 | Logistica del dia | FAQs de sistema | Varia por clinica |
| 8 | Multi-tratamiento | Prompt directo | Regla simple y universal |
| 9 | Feriados | Prompt directo + working_hours | Cruza con datos existentes |
| 10 | Idioma extranjero | Prompt directo | Regla simple |
| 11 | Datos sensibles | Prompt directo | Compliance obligatorio |
| 12 | Referencias/segunda opinion | Prompt directo | Regla simple |

---

## 3. CAMBIOS EN BASE DE DATOS

### 3.1 Nuevos campos en tabla `tenants`

```sql
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS insurance_providers TEXT DEFAULT '';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS payment_methods TEXT DEFAULT '';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS financing_options TEXT DEFAULT '';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS parking_info TEXT DEFAULT '';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS min_patient_age TEXT DEFAULT '';
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS pre_visit_instructions TEXT DEFAULT '';
```

**Descripcion de campos:**

| Campo | Tipo | Ejemplo | Uso |
|-------|------|---------|-----|
| `insurance_providers` | TEXT | "OSDE, Swiss Medical, Galeno, Medife" | Lista de obras sociales aceptadas |
| `payment_methods` | TEXT | "Efectivo, transferencia, tarjeta de debito, tarjeta de credito" | Medios de pago |
| `financing_options` | TEXT | "Hasta 6 cuotas sin interes con tarjeta Visa/Mastercard" | Opciones de financiacion |
| `parking_info` | TEXT | "Estacionamiento publico a 50m en calle Salta 200" | Info de estacionamiento |
| `min_patient_age` | TEXT | "Atendemos desde los 3 anos" | Edad minima de atencion |
| `pre_visit_instructions` | TEXT | "Traer DNI, carnet de obra social y estudios previos" | Instrucciones pre-consulta |

### 3.2 Migracion Alembic

**Archivo**: `orchestrator_service/alembic/versions/007_tenant_prompt_hardening.py`

```python
"""tenant prompt hardening fields

Revision ID: 007
Revises: 006
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = '007'
down_revision = '006'

def upgrade():
    op.add_column('tenants', sa.Column('insurance_providers', sa.Text(), server_default=''))
    op.add_column('tenants', sa.Column('payment_methods', sa.Text(), server_default=''))
    op.add_column('tenants', sa.Column('financing_options', sa.Text(), server_default=''))
    op.add_column('tenants', sa.Column('parking_info', sa.Text(), server_default=''))
    op.add_column('tenants', sa.Column('min_patient_age', sa.Text(), server_default=''))
    op.add_column('tenants', sa.Column('pre_visit_instructions', sa.Text(), server_default=''))

def downgrade():
    op.drop_column('tenants', 'pre_visit_instructions')
    op.drop_column('tenants', 'min_patient_age')
    op.drop_column('tenants', 'parking_info')
    op.drop_column('tenants', 'financing_options')
    op.drop_column('tenants', 'payment_methods')
    op.drop_column('tenants', 'insurance_providers')
```

### 3.3 Actualizar modelo ORM

**Archivo**: `orchestrator_service/models.py` — clase `Tenant`

Agregar:
```python
insurance_providers = Column(Text, server_default='')
payment_methods = Column(Text, server_default='')
financing_options = Column(Text, server_default='')
parking_info = Column(Text, server_default='')
min_patient_age = Column(Text, server_default='')
pre_visit_instructions = Column(Text, server_default='')
```

---

## 4. CAMBIOS EN build_system_prompt()

**Archivo**: `orchestrator_service/main.py`, funcion `build_system_prompt()`

### 4.1 Nuevos parametros de la funcion

Agregar a la firma:
```python
def build_system_prompt(
    ...,  # parametros existentes
    insurance_providers: str = "",
    payment_methods: str = "",
    financing_options: str = "",
    parking_info: str = "",
    min_patient_age: str = "",
    pre_visit_instructions: str = "",
):
```

### 4.2 Leer campos en buffer_task.py

**Archivo**: `orchestrator_service/services/buffer_task.py`

En la query que lee el tenant, agregar los nuevos campos:
```sql
SELECT ..., insurance_providers, payment_methods, financing_options,
       parking_info, min_patient_age, pre_visit_instructions
FROM tenants WHERE id = $1
```

Pasar los valores a `build_system_prompt()`.

### 4.3 Nuevas secciones del prompt

Agregar ANTES de la seccion `{anamnesis_section}` (justo antes de linea ~3088):

---

#### SECCION: OBRA SOCIAL Y SEGUROS

```python
insurance_section = ""
if insurance_providers:
    insurance_section = f"""
## OBRAS SOCIALES Y SEGUROS
Obras sociales aceptadas: {insurance_providers}
REGLAS:
• Si el paciente pregunta por una obra social de la lista → "Si, trabajamos con {{nombre}}. Queres que agendemos una consulta?"
• Si pregunta por una que NO esta en la lista → "Actualmente no tenemos convenio con esa obra social, pero podemos atenderte de forma particular. Queres que te cuente las opciones?"
• Si pregunta por cobertura de un tratamiento → "La cobertura depende de tu plan. Te sugerimos consultar con tu obra social antes de la visita. Mientras tanto, queres agendar una consulta de evaluacion?"
• NUNCA inventes convenios ni cobertura. Solo menciona las obras sociales configuradas.
"""
else:
    insurance_section = """
## OBRAS SOCIALES Y SEGUROS
Si preguntan por obras sociales o cobertura:
"Para consultas sobre obras sociales y cobertura, te recomiendo comunicarte directamente con la clinica."
"""
```

#### SECCION: MEDIOS DE PAGO Y FINANCIACION

```python
payment_section = ""
payment_lines = []
if payment_methods:
    payment_lines.append(f"Medios de pago aceptados: {payment_methods}")
if financing_options:
    payment_lines.append(f"Financiacion: {financing_options}")
if payment_lines:
    payment_section = f"""
## MEDIOS DE PAGO Y FINANCIACION
{chr(10).join(payment_lines)}
REGLAS:
• Si preguntan como pagar → compartir los medios de pago configurados.
• Si preguntan por cuotas o financiacion → compartir las opciones de financiacion.
• Si preguntan cuanto sale un tratamiento especifico (NO la consulta) → "El costo depende de cada caso. En la consulta de evaluacion el profesional te da un presupuesto detallado."
• Si preguntan por presupuesto previo → "En la primera consulta el profesional evalua tu caso y te entrega un presupuesto detallado con todas las opciones."
• NUNCA inventes precios de tratamientos. Solo compartir el precio de consulta si esta configurado.
"""
else:
    payment_section = """
## MEDIOS DE PAGO
Si preguntan por formas de pago o financiacion:
"Para consultas sobre medios de pago y financiacion, te recomiendo comunicarte directamente con la clinica."
"""
```

#### SECCION: CUIDADOS POST-TRATAMIENTO

```python
post_treatment_section = """
## CUIDADOS POST-TRATAMIENTO (GUIA BASICA)
Si el paciente dice que tuvo un tratamiento reciente y tiene dudas de cuidados:

POST-EXTRACCION:
"Es normal tener algo de sangrado leve las primeras horas. Morde suavemente una gasa durante 30 minutos. Dieta blanda y fria las primeras 24 horas. Evita bebidas calientes y pajitas. No hagas buches ni escupas con fuerza durante 24 horas."
Si el sangrado es abundante o no para → ejecutar triage_urgency.

POST-IMPLANTE:
"Algo de hinchazon y molestia es normal los primeros 3-5 dias. Aplica hielo en la zona (20 min si, 20 min no) las primeras 48 horas."
Si dolor intenso despues del dia 3 → ejecutar triage_urgency.

POST-ENDODONCIA:
"Es normal sentir sensibilidad los primeros dias. Evita masticar del lado tratado hasta que se coloque la restauracion definitiva."

REGLA GENERAL POST-TRATAMIENTO:
• Dar info basica de cuidados → cerrar con: "Si tenes alguna molestia que te preocupe, no dudes en consultarnos."
• Si los sintomas suenan anormales → ejecutar triage_urgency.
• NUNCA recetes medicacion especifica. Deci: "Lo mejor es seguir las indicaciones que te dio el profesional."
"""
```

#### SECCION: PROTOCOLO DE QUEJAS

```python
complaints_section = """
## PROTOCOLO DE QUEJAS (ESCALAMIENTO GRADUAL)
NUNCA derivar inmediatamente ante una queja. Seguir este orden:

NIVEL 1 — QUEJA LEVE (esperas, incomodidad menor):
"Lamento mucho que hayas tenido esa experiencia. Tu feedback es muy importante para nosotros."
→ Si se conforma: "Gracias por avisarnos. Hay algo mas en lo que te pueda ayudar?"
→ Si insiste → NIVEL 2.

NIVEL 2 — QUEJA MODERADA (atencion, cobro, resultado):
"Entiendo tu frustracion y quiero que se resuelva. Voy a derivar tu caso para que alguien del equipo te contacte personalmente."
→ Ejecutar derivhumano("Queja de paciente: {resumen}").

NIVEL 3 — QUEJA GRAVE (mala praxis, dolor severo post-tratamiento):
→ Ejecutar derivhumano INMEDIATAMENTE. Si hay sintomas → ejecutar TAMBIEN triage_urgency.

REGLAS:
• SIEMPRE empatizar ANTES de derivar.
• NUNCA pedir disculpas en nombre del profesional por un tratamiento (implicaria culpa).
• Usar "entiendo tu preocupacion" en vez de "perdon por el error".
• Si piden dejar resena → "Podes dejarnos tu opinion en Google Maps. Tu feedback nos ayuda a mejorar!"
"""
```

#### SECCION: CONDICIONES ESPECIALES

```python
special_conditions_section = """
## CONDICIONES ESPECIALES DEL PACIENTE

EMBARAZO/LACTANCIA:
Si mencionan embarazo o lactancia:
"Es muy importante que nos lo informes. Muchos tratamientos dentales son seguros durante el embarazo, especialmente limpiezas y urgencias. El profesional va a evaluar tu caso."
→ Agendar normalmente.

MEDICACION (anticoagulantes, bifosfonatos, inmunosupresores):
"Gracias por avisarnos, es clave que el profesional lo sepa. Asegurate de mencionarlo en la consulta y completarlo en tu ficha medica."
→ NUNCA aconsejar suspender o modificar medicacion.

ENFERMEDADES CRONICAS (diabetes, cardiopatias):
"Es importante que el profesional lo tenga en cuenta para adaptar el tratamiento. Podemos agendar tu consulta?"
→ Tono normalizado. NUNCA mostrar alarma.

ALERGIAS:
"Anotado! Es fundamental que el profesional lo sepa. Si no lo completaste, te paso el link de tu ficha medica."

REGLA: Ante CUALQUIER condicion especial → tranquilizar + derivar a evaluacion profesional + sugerir completar ficha medica. NUNCA dar consejo medico especifico. NUNCA alarmar. NUNCA decir que no se puede atender.
"""
```

#### SECCION: CONVERSACION SOCIAL Y LIMITES

```python
social_section = """
## CONVERSACION SOCIAL Y LIMITES

AGRADECIMIENTO/DESPEDIDA:
• "Gracias" → "De nada! Cualquier otra consulta, escribime."
• "Chau"/"Nos vemos" → "Hasta luego! Cualquier cosa, escribime."
• NO preguntar "hay algo mas?" si el paciente se esta despidiendo.

IDENTIDAD:
• "Como te llamas?" → "Soy la asistente virtual del consultorio. En que te puedo ayudar?"
• "Sos una IA?" → "Soy una asistente virtual. Estoy aca para ayudarte con turnos e informacion."

OFF-TOPIC (chistes, clima, deportes, politica):
→ "Me encantaria ayudarte con eso pero mi especialidad es la odontologia! Necesitas algo de la clinica?"

EMOJIS/STICKERS SIN TEXTO:
→ "Hola! En que te puedo ayudar?"

MENSAJES INCOMPRENSIBLES:
→ "No entendi bien tu mensaje. Podrias repetirlo?"
"""
```

#### SECCION: DATOS SENSIBLES

```python
sensitive_data_section = """
## DATOS SENSIBLES DE SALUD (COMPLIANCE)
Si el paciente comparte info medica sensible (VIH, adicciones, psiquiatria):
"Gracias por compartirlo, es importante que el profesional lo sepa. Esta informacion se mantiene de forma confidencial."
REGLAS:
• NUNCA repetir diagnosticos o condiciones del paciente en mensajes posteriores.
• NUNCA preguntar detalles sobre condiciones sensibles.
• Si envian fotos/radiografias → "Gracias! Para un diagnostico preciso es necesaria la evaluacion presencial. Queres agendar una consulta?"
• NUNCA diagnosticar a partir de una foto.
"""
```

#### SECCION: MULTI-TRATAMIENTO

```python
multi_treatment_section = """
## MULTI-TRATAMIENTO
Si el paciente pide 2+ tratamientos en la misma visita:
"Algunos tratamientos se pueden combinar en la misma visita, pero depende de cada caso. Queres que agendemos una consulta de evaluacion?"
→ NO intentar agendar 2 tratamientos en el mismo slot. Agendar consulta de evaluacion.
"""
```

#### SECCION: HORARIO ACTUAL Y FERIADOS

```python
schedule_awareness_section = """
## HORARIO Y FERIADOS
• Si preguntan "estan abiertos?" o "atienden ahora?" → cruzar TIEMPO ACTUAL con los horarios de atencion. Si esta dentro → "Si, estamos atendiendo hoy hasta las {hora}." Si esta fuera → "Estamos fuera del horario de atencion. Nuestro horario es {horario}."
• Si preguntan por feriados → "Para feriados los horarios pueden variar. Te recomiendo consultar con la clinica."
• Si un dia no tiene horario configurado → "Los {dia} la clinica no atiende. Busco disponibilidad para otro dia?"
"""
```

#### SECCION: IDIOMA

```python
language_section = """
## IDIOMA DEL PACIENTE
Si el paciente escribe en otro idioma (portugues, ingles, etc.):
→ Responder en el idioma del paciente en la primera respuesta.
→ Preguntar: "Preferis que sigamos en {idioma} o en espanol?"
→ Adaptarse a la preferencia del paciente.
• NUNCA corregir ortografia del paciente.
"""
```

#### SECCION: LOGISTICA

```python
logistics_section = ""
logistics_lines = []
if parking_info:
    logistics_lines.append(f"Estacionamiento: {parking_info}")
if min_patient_age:
    logistics_lines.append(f"Edad minima: {min_patient_age}")
if pre_visit_instructions:
    logistics_lines.append(f"Instrucciones pre-consulta: {pre_visit_instructions}")
if logistics_lines:
    logistics_section = f"""
## LOGISTICA PRE-CONSULTA
{chr(10).join(logistics_lines)}
"""

logistics_section += """
LLEGADA TARDE:
Si el paciente avisa que llega tarde → "Te recomendamos llegar 10 minutos antes. Si vas a llegar tarde, avisanos lo antes posible."
ACOMPANANTE:
"Podes venir acompanado/a, no hay problema."
DURACION PRIMERA CONSULTA:
"La primera consulta suele durar entre 20 y 40 minutos."
"""
```

#### SECCION: REFERENCIAS

```python
referral_section = """
## REFERENCIAS Y SEGUNDA OPINION
• "Me mando el Dr. X" → "Excelente! Queres que agendemos la consulta?"
• "Otro dentista me dijo que necesito X" → "Nuestro profesional va a evaluar tu caso de forma independiente. Queres agendar una consulta?"
• NUNCA contradecir ni hablar mal de otro profesional.
"""
```

### 4.4 Ensamblar en el prompt final

Agregar todas las secciones justo antes de `{anamnesis_section}`:

```python
return f"""...prompt existente...

{insurance_section}
{payment_section}
{post_treatment_section}
{complaints_section}
{special_conditions_section}
{social_section}
{sensitive_data_section}
{multi_treatment_section}
{schedule_awareness_section}
{language_section}
{logistics_section}
{referral_section}
{anamnesis_section}
{bank_section}
...resto del prompt existente...
"""
```

---

## 5. CAMBIOS EN FRONTEND (ConfigView)

### 5.1 Agregar campos al formulario de configuracion de clinica

**Archivo**: `frontend_react/src/views/ConfigView.tsx` (o ClinicsView.tsx)

En la seccion de configuracion del tenant, agregar:

| Campo UI | Campo DB | Tipo input | Placeholder |
|----------|----------|------------|-------------|
| Obras sociales aceptadas | insurance_providers | textarea | "OSDE, Swiss Medical, Galeno..." |
| Medios de pago | payment_methods | textarea | "Efectivo, transferencia, tarjeta..." |
| Financiacion | financing_options | textarea | "Hasta 6 cuotas sin interes..." |
| Estacionamiento | parking_info | input | "Estacionamiento publico a 50m..." |
| Edad minima | min_patient_age | input | "Atendemos desde los 3 anos" |
| Instrucciones pre-consulta | pre_visit_instructions | textarea | "Traer DNI, carnet obra social..." |

### 5.2 Endpoint PUT /admin/tenants/{id}

Ya existe. Solo agregar los nuevos campos al UPDATE SQL y al schema de validacion.

### 5.3 i18n

Agregar keys a `es.json`, `en.json`, `fr.json`:
```json
{
  "config.insurance_providers": "Obras sociales aceptadas",
  "config.insurance_providers_placeholder": "OSDE, Swiss Medical, Galeno...",
  "config.payment_methods": "Medios de pago",
  "config.payment_methods_placeholder": "Efectivo, transferencia, tarjeta...",
  "config.financing_options": "Opciones de financiacion",
  "config.financing_options_placeholder": "Hasta 6 cuotas sin interes...",
  "config.parking_info": "Estacionamiento",
  "config.parking_info_placeholder": "Estacionamiento publico a 50m...",
  "config.min_patient_age": "Edad minima de atencion",
  "config.min_patient_age_placeholder": "Desde los 3 anos",
  "config.pre_visit_instructions": "Instrucciones pre-consulta",
  "config.pre_visit_instructions_placeholder": "Traer DNI, carnet obra social..."
}
```

---

## 6. CAMBIOS EN admin_routes.py

### GET /admin/tenants

Agregar los nuevos campos a la respuesta (ya se devuelven todos los campos de tenants, solo verificar que no esten excluidos).

### PUT /admin/tenants/{id}

Agregar los nuevos campos al UPDATE:
```sql
UPDATE tenants SET
    ...,
    insurance_providers = $X,
    payment_methods = $X,
    financing_options = $X,
    parking_info = $X,
    min_patient_age = $X,
    pre_visit_instructions = $X
WHERE id = $1
```

---

## 7. ESTIMACION DE TOKENS

### Impacto en el system prompt

| Seccion | Tokens estimados | Metodo |
|---------|-----------------|--------|
| Obra social | ~80 (varia) | Dinamico (DB) |
| Medios de pago | ~80 (varia) | Dinamico (DB) |
| Post-tratamiento | ~180 | Fijo |
| Quejas | ~150 | Fijo |
| Condiciones especiales | ~160 | Fijo |
| Conversacion social | ~120 | Fijo |
| Datos sensibles | ~100 | Fijo |
| Multi-tratamiento | ~50 | Fijo |
| Horarios/feriados | ~80 | Fijo |
| Idioma | ~60 | Fijo |
| Logistica | ~80 (varia) | Dinamico (DB) |
| Referencias | ~60 | Fijo |
| **Total adicional** | **~1200 tokens** | |

**Costo adicional por mensaje**: ~$0.00018 (GPT-4o-mini input) — despreciable.

---

## 8. ARCHIVOS AFECTADOS

| Archivo | Cambio | Complejidad |
|---------|--------|-------------|
| `orchestrator_service/alembic/versions/007_...py` | NUEVO — migracion 6 campos | Baja |
| `orchestrator_service/models.py` | MODIFICAR — 6 campos en Tenant | Baja |
| `orchestrator_service/main.py` | MODIFICAR — build_system_prompt() + 12 secciones | Media |
| `orchestrator_service/services/buffer_task.py` | MODIFICAR — leer nuevos campos + pasarlos | Baja |
| `orchestrator_service/admin_routes.py` | MODIFICAR — PUT /admin/tenants | Baja |
| `frontend_react/src/views/ConfigView.tsx` | MODIFICAR — 6 inputs nuevos | Baja |
| `frontend_react/src/locales/es.json` | MODIFICAR — 12 keys | Baja |
| `frontend_react/src/locales/en.json` | MODIFICAR — 12 keys | Baja |
| `frontend_react/src/locales/fr.json` | MODIFICAR — 12 keys | Baja |

---

## 9. CRITERIOS DE ACEPTACION

### Obras sociales
- [ ] CEO configura "OSDE, Swiss Medical" en config → paciente pregunta "aceptan OSDE?" → agente responde "Si, trabajamos con OSDE"
- [ ] Paciente pregunta por obra social no configurada → agente ofrece atencion particular
- [ ] Sin obras sociales configuradas → agente deriva a consultar con clinica

### Post-tratamiento
- [ ] Paciente dice "me sangra despues de la extraccion" → agente da cuidados basicos + evalua si es urgencia
- [ ] Paciente pregunta "puedo comer despues del implante?" → agente responde con cuidados post-implante

### Medios de pago
- [ ] Paciente pregunta "tienen cuotas?" → agente comparte opciones configuradas
- [ ] Paciente pregunta "cuanto sale un implante?" → agente dice que depende del caso y ofrece consulta de evaluacion

### Quejas
- [ ] Paciente dice "espere 1 hora" → agente empatiza ANTES de cualquier accion
- [ ] Paciente frustrado y enojado → agente empatiza + derivhumano
- [ ] Paciente pregunta "donde dejo resena?" → agente sugiere Google Maps

### Condiciones especiales
- [ ] Paciente dice "estoy embarazada" → agente tranquiliza + agenda normalmente
- [ ] Paciente menciona medicacion → agente pide completar ficha medica
- [ ] Agente NUNCA da consejo medico especifico

### Conversacion social
- [ ] Paciente dice "sos un robot?" → agente confirma que es asistente virtual sin dar detalles tecnicos
- [ ] Paciente manda emoji solo → agente responde "En que te puedo ayudar?"
- [ ] Paciente dice tema off-topic → agente redirige amablemente a odontologia

### Datos sensibles
- [ ] Paciente comparte condicion sensible → agente NO la repite en mensajes siguientes
- [ ] Paciente envia foto → agente NO intenta diagnosticar, sugiere consulta presencial

### Multi-tratamiento
- [ ] Paciente pide 2 tratamientos → agente sugiere consulta de evaluacion en vez de 2 turnos separados

### Horarios
- [ ] Paciente pregunta "estan abiertos?" → agente cruza hora actual con working_hours y responde correctamente

### Idioma
- [ ] Paciente escribe en portugues → agente responde en portugues y pregunta preferencia

### Logistica
- [ ] Paciente pregunta por estacionamiento → agente comparte info si esta configurada
- [ ] Paciente avisa que llega tarde → agente sugiere avisar lo antes posible

### Referencias
- [ ] Paciente dice "me mando el Dr. Garcia" → agente agradece y ofrece agendar
- [ ] Paciente pide segunda opinion → agente ofrece evaluacion sin hablar mal de otro profesional

---

## 10. VERIFICACION FINAL

1. Testear cada escenario de los 12 puntos en una conversacion real de WhatsApp
2. Verificar que el prompt no exceda limites de tokens (GPT-4o-mini max context: 128k)
3. Verificar que los campos configurables aparecen en el panel de configuracion
4. Verificar que campos vacios no generan secciones rotas en el prompt
5. Verificar que las secciones fijas no afectan el flujo de agendamiento existente
6. Verificar compliance: datos sensibles no se repiten, no se diagnostica por foto, no se receta medicacion
