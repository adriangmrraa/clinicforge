# Spec: DLD-33 — Número de afiliado

## Requirements

- **REQ-1**: El campo `insurance_id` de la tabla `patients` debe ser listo/escribible desde todos los endpoints administrativos de pacientes.
- **REQ-2**: `PatientCreate` y `PatientUpdate` deben aceptar `insurance_id` como campo opcional (`Optional[str]`, max 50 caracteres, `None` por defecto).
- **REQ-3**: El endpoint `GET /admin/patients` (lista) debe incluir `insurance_id` en cada objeto devuelto.
- **REQ-4**: El endpoint `GET /admin/patients/{id}` (detalle) debe incluir `insurance_id` en el objeto devuelto.
- **REQ-5**: El formulario de alta/edición de paciente en `PatientsView.tsx` debe exponer un input de texto opcional mapeado a `obra_social_number`.
- **REQ-6**: La ficha de paciente en `PatientDetail.tsx` debe mostrar `obra_social_number` junto a los datos de obra social.
- **REQ-7**: El campo es completamente opcional — su ausencia no debe bloquear alta ni edición.
- **REQ-8**: Todo texto visible debe usar claves i18n en los tres idiomas (`es`, `en`, `fr`).

## Scenarios

### SC-1: Alta de paciente con número de afiliado
- **Dado** que el usuario completa el formulario de nuevo paciente
- **Cuando** ingresa un valor en el campo "Número de afiliado" (ej: "A4872634")
- **Entonces** el POST incluye `insurance_id: "A4872634"` en el body
- **Y** la respuesta del servidor devuelve el paciente con `obra_social_number: "A4872634"`
- **Y** el paciente aparece en lista con ese valor disponible en su objeto

### SC-2: Edición de paciente agregando número de afiliado
- **Dado** un paciente existente sin número de afiliado (`insurance_id: null`)
- **Cuando** el usuario abre el modal de edición e ingresa el número
- **Entonces** el PUT envía `insurance_id` con el nuevo valor
- **Y** la respuesta refleja el dato actualizado
- **Y** la ficha del paciente muestra el nuevo número

### SC-3: Visualización en lista de pacientes
- **Dado** que existen pacientes con y sin número de afiliado
- **Cuando** se carga la vista de pacientes
- **Entonces** el objeto de cada paciente incluye `obra_social_number` (string o null)
- **Nota**: no se requiere que sea una columna visible en la tabla de lista, pero el dato debe estar en el payload para que el modal de edición pueda pre-popularlo

### SC-4: Visualización en ficha del paciente
- **Dado** un paciente con `obra_social_number` no nulo
- **Cuando** se navega a su ficha (`PatientDetail`)
- **Entonces** el número de afiliado se muestra en la sección de cobertura/obra social
- **Y** si el valor es null o vacío, el campo no muestra texto (no muestra "null" ni "—" forzado)

### SC-5: Campo vacío — no bloquea
- **Dado** que el usuario completa el formulario de nuevo paciente SIN ingresar número de afiliado
- **Cuando** guarda el registro
- **Entonces** el alta se completa normalmente
- **Y** `insurance_id` queda como `NULL` en base de datos
- **Y** no hay error de validación ni mensaje de advertencia

## Technical Changes

### Backend (`orchestrator_service/admin_routes.py`)

**Pydantic schemas**
- `PatientCreate`: agregar `insurance_id: Optional[str] = None`
- `PatientUpdate`: agregar `insurance_id: Optional[str] = None`

**POST /admin/patients**
- Incluir `insurance_id` en la lista de columnas y valores del INSERT SQL
- Incluir `insurance_id` en el SELECT de retorno

**PUT /admin/patients/{id}**
- Incluir `insurance_id` en los campos actualizables del UPDATE SQL
- Respetar el patrón existente (SET directo o COALESCE según convenga — preferir SET directo con el valor del payload, que ya viene `None` si no se envía)

**GET /admin/patients (lista)**
- Agregar `insurance_id` al SELECT
- Incluir en el dict de retorno con la misma clave `insurance_id`

**GET /admin/patients/{id} (detalle)**
- Agregar `insurance_id` al SELECT
- Incluir en el dict de retorno

### Frontend

**`PatientsView.tsx`**
- Estado local del modal: campo `obra_social_number: string` (inicializado desde el paciente existente o `""`)
- Input de texto `<input type="text">` opcional, label i18n `patients.insurance_number`, placeholder i18n `patients.insurance_number_placeholder`
- Posición: inmediatamente debajo del campo `obra_social` en el formulario
- Body del POST/PUT: incluir `obra_social_number` mapeado como `insurance_id`

**`PatientDetail.tsx`**
- Leer `obra_social_number` del objeto paciente
- Renderizar en la sección de cobertura/obra social únicamente si el valor no es nulo ni vacío
- Usar la misma clase visual de los campos de solo lectura de la ficha (sin estilo especial nuevo)

**`src/locales/es.json`**
```
"patients.insurance_number": "Número de afiliado",
"patients.insurance_number_placeholder": "Ej: A4872634"
```

**`src/locales/en.json`**
```
"patients.insurance_number": "Insurance number",
"patients.insurance_number_placeholder": "e.g. A4872634"
```

**`src/locales/fr.json`**
```
"patients.insurance_number": "Numéro d'assuré",
"patients.insurance_number_placeholder": "Ex: A4872634"
```

## Out of Scope

- **Importación bulk CSV/XLSX**: el campo `insurance_id` no se mapea en el import por ahora. Futura mejora independiente.
- **Validación de formato**: el campo es libre. No se aplica regex, longitud mínima, ni prefijos por obra social.
- **Búsqueda por número de afiliado**: no se agrega filtro en la lista de pacientes.
- **Migración Alembic**: la columna existe desde el baseline (migración 001). Alembic head actual: 058. Cero cambios DDL.
- **IA bot / herramientas LangChain**: el número de afiliado no se expone al agente conversacional.
- **Nova tools**: no se modifica `nova_tools.py`.
