# Turno para Terceros (Adultos y Menores)
> Origen: Requerimiento de la Dra. Delgado — sucede frecuentemente que una persona pide turno para otra.

## 1. Contexto y Objetivos

- **Problema:** Actualmente `book_appointment` usa siempre `current_customer_phone.get()` (el teléfono de quien chatea) como identificador del paciente. Si Ramiro pide turno para José, el sistema sobreescribe los datos de Ramiro con los de José, o crea a José con el teléfono de Ramiro. No hay forma de distinguir "para quién es el turno".

- **Solución:** El agente de IA detecta si el turno es para el interlocutor o para un tercero. Tres escenarios diferenciados con manejo específico de phone, datos, archivos y anamnesis.

- **KPIs:**
  - Turnos para terceros se registran con el paciente correcto
  - La identidad del interlocutor nunca se modifica al agendar para otro
  - Menores quedan vinculados al padre/madre via `guardian_phone`
  - Archivos e imágenes enviados por chat se guardan en la ficha del paciente correcto

## 2. Esquemas de Datos

### Entradas (parámetros nuevos de `book_appointment`)
```
patient_phone: Optional[str]  — Teléfono del paciente real (obligatorio para terceros adultos)
is_minor: Optional[bool]      — True si el paciente es menor de edad (hijo/hija)
```

### Persistencia — Migración Alembic REQUERIDA
```sql
ALTER TABLE patients ADD COLUMN guardian_phone VARCHAR(20) DEFAULT NULL;
CREATE INDEX idx_patients_guardian ON patients(guardian_phone) WHERE guardian_phone IS NOT NULL;
```

Actualizar `models.py`: agregar `guardian_phone = Column(String(20), nullable=True)` a la clase `Patient`.

### Phone del paciente menor
Para evitar conflicto UNIQUE(tenant_id, phone_number), los menores usan el phone del progenitor con sufijo:
- Primer menor: `+5491111111-M1`
- Segundo menor: `+5491111111-M2`
- N-ésimo menor: `+5491111111-MN`

El campo `guardian_phone` almacena el phone real del padre/madre (sin sufijo) para vincular y enviar comunicaciones.

## 3. Lógica de Negocio (Invariantes)

### Flujo de detección — Nuevo PASO 2b en el system prompt

Después de definir el servicio (PASO 2) y antes del profesional (PASO 3), el agente SIEMPRE pregunta:

**"El turno es para vos o para otra persona?"**

Tres escenarios:

| Escenario | Detección | Teléfono paciente | guardian_phone | Datos del paciente |
|-----------|-----------|-------------------|----------------|-------------------|
| **A) Para sí mismo** | "para mí" / "sí, para mí" | `current_customer_phone` (chat) | NULL | Los del interlocutor |
| **B) Para otro adulto** | "para mi amigo/esposa/conocido" | **Se pide al interlocutor** (obligatorio) | NULL | Los del tercero |
| **C) Para un menor** | "para mi hijo/hija" | `chat_phone-M{N}` (generado) | `chat_phone` (padre/madre) | Los del menor |

### Reglas del tool `book_appointment`

**Resolución del phone del paciente:**
```python
if is_minor:
    # Menor → generar phone con sufijo -M{N}
    chat_phone = current_customer_phone.get()
    # Contar menores existentes con este guardian_phone
    count = await db.pool.fetchval(
        "SELECT COUNT(*) FROM patients WHERE tenant_id = $1 AND guardian_phone = $2",
        tenant_id, chat_phone
    )
    patient_phone_resolved = f"{chat_phone}-M{count + 1}"
    guardian_phone_value = chat_phone
elif patient_phone:
    # Adulto tercero → usar el teléfono provisto
    patient_phone_resolved = normalize_phone(patient_phone)
    guardian_phone_value = None
else:
    # Para sí mismo → flujo actual
    patient_phone_resolved = current_customer_phone.get()
    guardian_phone_value = None
```

**Búsqueda de paciente existente (menores):**
Para menores, buscar primero por `guardian_phone` + `dni` o `guardian_phone` + nombre exacto, para reutilizar el registro si el menor ya existe (turno repetido).

```python
if is_minor:
    # Buscar menor existente por guardian + DNI
    existing_patient = await db.pool.fetchrow(
        "SELECT id, phone_number FROM patients WHERE tenant_id = $1 AND guardian_phone = $2 AND dni = $3",
        tenant_id, chat_phone, dni
    )
    # Fallback: buscar por guardian + nombre exacto
    if not existing_patient and first_name:
        existing_patient = await db.pool.fetchrow(
            "SELECT id, phone_number FROM patients WHERE tenant_id = $1 AND guardian_phone = $2 AND first_name = $3",
            tenant_id, chat_phone, first_name
        )
    if existing_patient:
        patient_phone_resolved = existing_patient['phone_number']  # Reusar el -M{N} existente
```

**Creación del paciente:**
```python
INSERT INTO patients (tenant_id, phone_number, first_name, last_name, dni, guardian_phone, status, ...)
VALUES ($1, patient_phone_resolved, first_name, last_name, dni, guardian_phone_value, 'active', ...)
```

**Protección contra sobreescritura:**
- Si `is_minor=True` o `patient_phone` provisto: NO ejecutar UPDATE sobre el paciente del interlocutor. Solo buscar/crear el paciente del tercero.

### Datos obligatorios por escenario

| Escenario | Nombre | Apellido | DNI | Teléfono paciente |
|-----------|--------|----------|-----|-------------------|
| Para sí mismo | SÍ | SÍ | SÍ | Ya lo tenemos (chat) |
| Para adulto tercero | SÍ | SÍ | SÍ | SÍ (se pide al interlocutor) |
| Para menor | SÍ | SÍ | SÍ | No (se genera -M{N}) |

Si falta el DNI del tercero adulto, el agente sugiere: "Podrías preguntarle a [nombre] su DNI? Lo necesitamos para completar el registro."

### Archivos e imágenes por chat

Cuando se envían archivos/imágenes durante una conversación donde se agendó para un tercero:
- El agente debe preguntar: "Esta imagen/archivo es para tu ficha o para la de [nombre del paciente]?"
- Según la respuesta, se guarda en el `patient_id` correcto.
- Para menores: los archivos se guardan en la ficha del menor (no del padre).

### Anamnesis (ficha médica)

- **Para sí mismo:** Flujo actual — se envía el link público de anamnesis al interlocutor.
- **Para menor:** Se envía el link de anamnesis del MENOR al interlocutor (padre/madre), para que lo complete con los datos de su hijo. El link apunta al `patient_id` del menor.
- **Para adulto tercero:** El agente dice: "Te paso el link de ficha médica para que se lo reenvíes a [nombre]: [link]". El link apunta al `patient_id` del tercero. NO se guarda la anamnesis en el interlocutor.

### Confirmación del turno (PASO 7)

La confirmación menciona AMBOS — interlocutor y paciente:
- Para sí mismo: "Turno confirmado para [nombre], [tratamiento], [día], [hora], con [profesional], en [sede]."
- Para tercero: "Turno confirmado para [nombre paciente] (solicitado por [nombre interlocutor]): [tratamiento], [día], [hora], con [profesional], en [sede]."

### RESTRICCIONES
- SIEMPRE preguntar "El turno es para vos o para otra persona?" — sin excepciones.
- NUNCA modificar el `first_name` o `last_name` del interlocutor al agendar para otro.
- NUNCA usar el phone del chat como phone del tercero adulto — obligar a pedirlo.
- SOBERANÍA: Todas las queries filtran por `tenant_id`.
- Un interlocutor puede sacar múltiples turnos para diferentes personas en la misma conversación.

## 4. Stack y Restricciones

### Backend
| Archivo | Cambio |
|---------|--------|
| `orchestrator_service/main.py` — `book_appointment` (~línea 708) | +2 params (`patient_phone`, `is_minor`), nueva lógica de resolución de phone, búsqueda de menores existentes, protección contra sobreescritura, guardado de `guardian_phone` |
| `orchestrator_service/main.py` — `build_system_prompt` (~línea 1891) | Nuevo PASO 2b "para quién es el turno", reglas de terceros, confirmación con ambos nombres, instrucciones de anamnesis para terceros |
| `orchestrator_service/models.py` — clase `Patient` | Agregar `guardian_phone = Column(String(20), nullable=True)` |
| `orchestrator_service/alembic/versions/003_add_guardian_phone.py` | Migración: `ADD COLUMN guardian_phone` + índice |

### Frontend
Sin cambios.

### API
Sin endpoints nuevos. Solo se modifican los parámetros del tool `book_appointment`.

### DB
Migración Alembic: `ALTER TABLE patients ADD COLUMN guardian_phone VARCHAR(20)`.

## 5. Criterios de Aceptación (Gherkin)

### Escenario 1: Turno para sí mismo (sin regresión)
- DADO que Ramiro chatea desde +5491111111
- CUANDO el agente pregunta "El turno es para vos o para otra persona?"
- Y Ramiro dice "para mí"
- ENTONCES flujo normal: datos de Ramiro, phone=+5491111111, guardian_phone=NULL

### Escenario 2: Turno para otro adulto
- DADO que Ramiro chatea desde +5491111111
- CUANDO dice "para mi amigo José"
- ENTONCES el agente pide teléfono de José → +5492222222
- Y pide nombre, apellido y DNI de José
- ENTONCES se crea paciente José con phone=+5492222222, guardian_phone=NULL
- Y el registro de Ramiro NO se modifica
- Y la confirmación dice "Turno confirmado para José Mayans (solicitado por Ramiro Alfonso): ..."

### Escenario 3: Turno para primer hijo menor
- DADO que Laura chatea desde +5491111111 y no tiene hijos registrados
- CUANDO dice "para mi hijo Tomás"
- ENTONCES el agente NO pide teléfono
- Y pide nombre, apellido y DNI de Tomás
- ENTONCES se crea paciente Tomás con phone=+5491111111-M1, guardian_phone=+5491111111
- Y el registro de Laura NO se modifica
- Y el link de anamnesis se envía a Laura para que complete los datos de Tomás

### Escenario 4: Turno para segundo hijo menor
- DADO que Laura ya tiene un menor registrado con phone=+5491111111-M1
- CUANDO dice "también para mi hija Sofía"
- ENTONCES se crea paciente Sofía con phone=+5491111111-M2, guardian_phone=+5491111111

### Escenario 5: Turno repetido para el mismo menor
- DADO que Tomás ya existe con phone=+5491111111-M1 y DNI 55123456
- CUANDO Laura pide otro turno para Tomás
- ENTONCES se reutiliza el paciente existente (se encuentra por guardian_phone + DNI)
- Y NO se crea duplicado

### Escenario 6: Tercero adulto sin teléfono
- DADO que el interlocutor pide turno para un amigo pero no sabe su teléfono
- ENTONCES el agente dice "Necesito el teléfono de [nombre] para registrarlo. Podrías preguntárselo?"
- Y NO usa el teléfono del chat como fallback
- Y NO agenda hasta tener el teléfono

### Escenario 7: Archivos para menor
- DADO que Laura agendó turno para Tomás
- CUANDO Laura envía una radiografía por chat
- ENTONCES el agente pregunta "Esta imagen es para tu ficha o para la de Tomás?"
- Y según la respuesta, se guarda en el patient_id correcto

## 6. Archivos Afectados

| Archivo | Tipo | Cambio |
|---------|------|--------|
| `orchestrator_service/alembic/versions/003_add_guardian_phone.py` | NEW | Migración: ADD COLUMN guardian_phone + índice |
| `orchestrator_service/models.py` | MODIFY | Agregar guardian_phone a clase Patient |
| `orchestrator_service/main.py` — `book_appointment` | MODIFY | +2 params, resolución de phone, búsqueda de menores, guardian_phone |
| `orchestrator_service/main.py` — `build_system_prompt` | MODIFY | Nuevo paso 2b, reglas terceros, confirmación dual, anamnesis terceros |

## 7. Casos Borde y Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Menor con mismo phone-MN que ya existe | Buscar por guardian_phone + DNI/nombre antes de generar -M{N}. Reutilizar si coincide |
| El agente no detecta que "para mi hijo" implica menor | Lista de sinónimos en el prompt: hijo/a, nene/a, menor, bebé, niño/a, chico/a |
| Tercero adulto sin DNI → el interlocutor no puede conseguirlo | El agente sugiere que se comunique directamente con el tercero. No agenda sin DNI |
| Archivos enviados sin contexto → no se sabe a qué paciente pertenecen | Si hubo turno para tercero en la conversación, el agente siempre pregunta antes de guardar |
| Regresión en flujo normal | Sin `patient_phone` ni `is_minor`, todo es idéntico al flujo actual (backward compatible) |
| Phone con sufijo -M1 se muestra feo en la UI | Es un identificador interno. La UI de pacientes podría mostrar "Menor de [guardian_phone]" en el futuro, pero no es bloqueante |
| `save_patient_anamnesis` usa `current_customer_phone` | Para menores: el link de anamnesis apunta al patient_id del menor, no se usa phone lookup. Para terceros adultos: el link apunta a su patient_id directamente |

## Clarificaciones (Resueltas)

1. **Phone de menores:** Se usa phone del progenitor + sufijo `-M{N}` (`-M1`, `-M2`, etc.) para evitar conflicto UNIQUE. El campo `guardian_phone` almacena el phone real del padre/madre para vincular y enviar comunicaciones. Los archivos/imágenes se guardan en la ficha del menor.

2. **Pregunta obligatoria:** El agente SIEMPRE pregunta "El turno es para vos o para otra persona?" — sin excepciones.

3. **DNI obligatorio para terceros:** Se mantiene. Si falta, el agente sugiere contactar al tercero para pedirlo. No se agenda sin DNI.

4. **Anamnesis:** Para menores, el link se envía al padre/madre (guardian_phone) para que complete datos del hijo. Para terceros adultos, el agente pide al interlocutor que reenvíe el link al tercero. La anamnesis nunca se guarda en el interlocutor.

5. **Confirmación del turno:** Menciona al interlocutor y al paciente: "Turno confirmado para [paciente] (solicitado por [interlocutor]): ..."

6. **Nombre de la conversación:** El nombre del paciente asociado al phone del chat (`ensure_patient_exists`) SOLO se actualiza cuando el turno es para sí mismo. Si el turno es para un tercero o menor, el nombre de la conversación NO se toca — debe mantenerse el que viene de WhatsApp/Instagram/Facebook. El UPDATE que hace `book_appointment` sobre `first_name`/`last_name` del paciente interlocutor NO debe ejecutarse cuando el turno es para otro.
