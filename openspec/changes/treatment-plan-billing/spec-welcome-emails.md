# Spec: Welcome Emails — Sistema de Emails de Bienvenida

**Change**: treatment-plan-billing
**Module**: User Onboarding Emails
**Status**: Draft
**Date**: 2026-04-03

---

## 1. Overview

Este spec cubre el sistema de emails automáticos de bienvenida que se envían cuando se crea un nuevo usuario (profesional, secretaria o CEO) en la plataforma.

**Flujo básico:**
1. Se crea un nuevo usuario vía `/register` (auth_routes.py) o `create_professional` (admin_routes.py)
2. El sistema detecta el tipo de usuario creado
3. Se envía un email de bienvenida personalizado según el rol
4. El email incluye credenciales de acceso y información de la clínica

---

## 2. Triggers

### Trigger 1: Nuevo profesional creado

- **Origen**: Endpoint `/register` con `role=professional` o `create_professional` (admin_routes.py)
- **Condición**: Se crea una fila en `professionals` con `is_active=TRUE`
- **Email**: Bienvenida específica para profesionales de salud

### Trigger 2: Nueva secretaria creada

- **Origen**: Endpoint `/register` con `role=secretary`
- **Condición**: Se crea una fila en `professionals` con `role=secretary` y `is_active=TRUE`
- **Email**: Bienvenida específica para secretarias

### Trigger 3: Nuevo CEO/Admin creado

- **Origen**: Endpoint `/register` con `role=ceo` o creación por otro CEO
- **Condición**: Se crea un usuario con `role=ceo` y `status=active`
- **Email**: Bienvenida con privilegios de administrador

---

## 3. Contenido del Email por Tipo de Usuario

### 3.1 Email para Profesional

| Campo | Valor |
|-------|-------|
| **Subject** | Bienvenido a {clinic_name} - Tu acceso al sistema |
| **From** | {clinic_name} <no-reply@{tenant_domain}> |
| **To** | {user_email} |

**Cuerpo del email:**

```
Hola {user_first_name},

¡Bienvenido a {clinic_name}! 🎉

Te registramos en nuestro sistema de gestión. Estos son tus datos de acceso:

📋 Credenciales:
   - Usuario: {user_email}
   - Link de acceso: {login_url}

🏥 Clínica:
   - Nombre: {clinic_name}
   - Dirección: {clinic_address}
   - Teléfono: {clinic_phone}

📅 Sistema de Agenda:
   Podés ver tu agenda, gestionar tus turnos y consultar tus pacientes desde el panel.

💬 Soporte:
   Si tenés dudas, escribinos a {support_email}

¡ esperamos que tu experiencia sea excelente!

Saludos,
{clinic_name}
```

### 3.2 Email para Secretaria

| Campo | Valor |
|-------|-------|
| **Subject** | Bienvenida a {clinic_name} - Tu acceso como Secretaría |
| **From** | {clinic_name} <no-reply@{tenant_domain}> |
| **To** | {user_email} |

**Cuerpo del email:**

```
Hola {user_first_name},

¡Bienvenida a {clinic_name}! 🎉

Te registramos en nuestro sistema de gestión como secretária. Estos son tus datos de acceso:

📋 Credenciales:
   - Usuario: {user_email}
   - Link de acceso: {login_url}

🏥 Clínica:
   - Nombre: {clinic_name}
   - Dirección: {clinic_address}
   - Teléfono: {clinic_phone}

📋 Funcionalidades disponibles:
   - Gestión de turnos y agenda
   - Registro de pacientes
   - Confirmación de turnos
   - Historial de conversaciones

💬 Soporte:
   Si tenés dudas, escribinos a {support_email}

¡Estamos felices de tenerte en el equipo!

Saludos,
{clinic_name}
```

### 3.3 Email para CEO/Admin

| Campo | Valor |
|-------|-------|
| **Subject** | Bienvenido a {clinic_name} - Acceso como Administrador |
| **From** | {clinic_name} <no-reply@{tenant_domain}> |
| **To** | {user_email} |

**Cuerpo del email:**

```
Hola {user_first_name},

¡Bienvenido a {clinic_name} como Administrador! 🎉

Te registramos con acceso completo al sistema. Estos son tus datos de acceso:

📋 Credenciales:
   - Usuario: {user_email}
   - Link de acceso: {login_url}

🏥 Clínica:
   - Nombre: {clinic_name}
   - Dirección: {clinic_address}
   - Teléfono: {clinic_phone}

📊 Dashboard y Métricas:
   - Ver ingresos y estadísticas
   - Gestión de液态iones
   - Reportes detallados

⚙️ Configuraciones disponibles:
   - Configurar clínica
   - Gestionar usuarios y permisos
   - Ajustar agenda y horarios
   - Integrar calendario Google

💬 Soporte:
   Si tenés dudas, escribinos a {support_email}

Saludos,
{clinic_name}
```

---

## 4. Integración Técnica

### 4.1 Punto de integración: auth_routes.py

**Endpoint `/register` (POST)** — Después del INSERT exitoso:

```python
# En auth_routes.py - función register()
# Después de crear el usuario y profesional/secretary

# ENVIAR EMAIL DE BIENVENIDA (async, no bloqueante)
try:
    await send_welcome_email(
        tenant_id=payload.tenant_id or resolved_tenant_id,
        user_id=user_id,
        role=payload.role,
    )
except Exception as e:
    logger.warning(f"Welcome email failed: {e}")  # No rompe la respuesta
```

### 4.2 Punto de integración: admin_routes.py

**Endpoint `create_professional` (POST)** — Después de crear profesional activo:

```python
# En admin_routes.py - función create_professional()
# Después de crear el profesional con is_active=TRUE

# ENVIAR EMAIL DE BIENVENIDA
if professional.is_active:
    try:
        await send_welcome_email(
            tenant_id=tenant_id,
            user_id=user_id,
            role="professional",
        )
    except Exception as e:
        logger.warning(f"Welcome email failed: {e}")
```

### 4.3 Método en email_service.py

**Nuevo método a agregar:**

```python
async def send_welcome_email(
    self,
    tenant_id: int,
    user_id: str,
    role: str,
    db_pool,
) -> bool:
    """
    Envía email de bienvenida según el rol del usuario.
    Retorna True si envió, False sifalló.
    """
    # 1. Obtener datos del usuario (email, first_name)
    # 2. Obtener datos de la clínica (clinic_name, address, phone)
    # 3. Seleccionar template según rol (professional/secretary/ceo)
    # 4. Renderizar con variables dinámicas
    # 5. Enviar via SMTP
    # 6. Loggear resultado
```

### 4.4 Plantillas en email_templates.py

**Agregar:**

```python
# templates/welcome_professional.html
# templates/welcome_secretary.html
# templates/welcome_ceo.html
```

O agregar al archivo de templates existente.

---

## 5. Variables Dinámicas

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `{user_first_name}` | Nombre del usuario | María |
| `{clinic_name}` | Nombre de la clínica | Clínica Sonría |
| `{clinic_address}` | Dirección de la clínica | Av. Santa Fe 1234 |
| `{clinic_phone}` | Teléfono de contacto | +54 11 1234 5678 |
| `{user_email}` | Email del usuario (login) | maria@gmail.com |
| `{login_url}` | URL de acceso | https://app.clinicforge.com/login |
| `{support_email}` | Email de soporte | soporte@clinica.com |

---

## 6. Criterios de Aceptación

- [ ] Cuando se crea un nuevo profesional → se envía email de bienvenida profesional
- [ ] Cuando se crea una nueva secretaria → se envía email de bienvenida secretary
- [ ] Cuando se crea un nuevo CEO/Admin → se envía email de bienvenida admin
- [ ] El email incluye credenciales de acceso (usuario, link)
- [ ] El email incluye datos de la clínica
- [ ] El contenido varía según el rol del usuario
- [ ] El sistema usa el email_service existente
- [ ] El email se envía de forma asíncrona (no bloquea la respuesta)

---

## 7. Archivos Afectados

| Archivo | Acción |
|---------|--------|
| `email_service.py` | Agregar método `send_welcome_email` |
| `auth_routes.py` | Integrar trigger en `/register` |
| `admin_routes.py` | Integrar trigger en `create_professional` |
| `email_templates.py` | Agregar plantillas HTML |

---

## 8. Considerations

- **Estado pending vs active**: Los usuarios pending (esperando aprobación) no reciben email. Solo activos.
- **Email duplicado**: Verificar que no se envió antes (evitar reenvíos)
- **Fallback**: Si el email falla, loguear pero no bloquear la creación del usuario
- **Link de login**: Usar variable de entorno `FRONTEND_URL` para construir la URL

---

*Fin del spec de Welcome Emails.*