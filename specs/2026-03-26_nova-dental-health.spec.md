# SPEC: Nova Dental Assistant — Health Check Clinico (Fase 3)

**Fecha**: 2026-03-26
**Proyecto**: ClinicForge
**Dependencia**: Fase 1 (backend endpoints)
**Costo**: $0 (solo SQL)

---

## 1. CONCEPTO

El health-check clinico es un sistema de monitoreo proactivo que evalua el estado operativo de la clinica dental. A diferencia de Platform AI Solutions (que mide "completitud de negocio"), aca medimos **salud operativa diaria + configuracion**.

Dos dimensiones:
1. **Operativo** (cambia cada dia): turnos, pagos, recordatorios
2. **Configuracion** (cambia rara vez): profesionales, horarios, integraciones, FAQ

---

## 2. CHECKS OPERATIVOS (diarios)

Ejecutados en cada llamada a `GET /admin/nova/context` y `GET /admin/nova/health-check`.

### Check 1: Turnos sin confirmar hoy
```sql
SELECT COUNT(*) FROM appointments
WHERE tenant_id = $1
AND DATE(appointment_datetime) = CURRENT_DATE
AND status = 'scheduled'
-- scheduled = no confirmado, confirmed = confirmado
```
- **Severidad**: `alert` si count > 0
- **Mensaje**: "{N} turnos sin confirmar para hoy"
- **Accion**: `confirmar_turnos`
- **Peso**: 10

### Check 2: Huecos grandes en agenda (manana)
```sql
-- 1. Obtener horarios de trabajo del profesional
SELECT working_hours FROM professionals
WHERE tenant_id = $1 AND is_active = true

-- 2. Obtener turnos de manana
SELECT appointment_datetime, duration_minutes FROM appointments
WHERE tenant_id = $1
AND DATE(appointment_datetime) = CURRENT_DATE + INTERVAL '1 day'
AND status IN ('scheduled', 'confirmed')
ORDER BY appointment_datetime

-- 3. En Python: comparar slots ocupados vs horarios → detectar gaps > 2h
```
- **Severidad**: `suggestion`
- **Mensaje**: "Hay un hueco de {N}h manana entre las {HH:MM} y {HH:MM}"
- **Accion**: `ver_agenda`
- **Peso**: 5

### Check 3: Recordatorios no enviados
```sql
SELECT COUNT(*) FROM appointments
WHERE tenant_id = $1
AND DATE(appointment_datetime) = CURRENT_DATE + INTERVAL '1 day'
AND reminder_sent = false
AND status IN ('scheduled', 'confirmed')
```
- **Severidad**: `alert` si count > 0
- **Mensaje**: "{N} recordatorios pendientes para turnos de manana"
- **Accion**: `enviar_recordatorios`
- **Peso**: 8

### Check 4: Facturacion pendiente
```sql
SELECT COUNT(*) FROM appointments
WHERE tenant_id = $1
AND status = 'completed'
AND (payment_status IS NULL OR payment_status = 'pending')
AND completed_at >= NOW() - INTERVAL '30 days'
```
- **Severidad**: `warning` si count > 0
- **Mensaje**: "{N} turnos completados sin cobrar"
- **Accion**: `facturacion_pendiente`
- **Peso**: 7

### Check 5: Cancelaciones del dia
```sql
SELECT COUNT(*) FROM appointments
WHERE tenant_id = $1
AND DATE(appointment_datetime) = CURRENT_DATE
AND status = 'cancelled'
```
- **Severidad**: `info` si count > 0
- **Mensaje**: "{N} turnos cancelados hoy"
- **Accion**: `ver_agenda`
- **Peso**: 3

### Check 6: Pacientes nuevos sin anamnesis
```sql
SELECT COUNT(*) FROM patients
WHERE tenant_id = $1
AND (medical_history IS NULL OR medical_history = '{}')
AND created_at >= NOW() - INTERVAL '7 days'
```
- **Severidad**: `suggestion`
- **Mensaje**: "{N} pacientes nuevos sin ficha medica completa"
- **Accion**: `ver_pacientes`
- **Peso**: 4

### Check 7: Derivaciones a humano (ultimas 24h)
```sql
SELECT COUNT(*) FROM chat_messages
WHERE tenant_id = $1
AND role = 'tool'
AND content ILIKE '%derivhumano%'
AND created_at >= NOW() - INTERVAL '24 hours'
```
- **Severidad**: `alert` si count > 3
- **Mensaje**: "El agente derivo {N} veces en 24h. Puede faltar informacion en las FAQ"
- **Accion**: `agregar_faqs`
- **Peso**: 6

### Check 8: Pacientes sin control hace 6+ meses
```sql
SELECT COUNT(*) FROM patients p
WHERE p.tenant_id = $1
AND p.status = 'active'
AND (p.last_visit IS NULL OR p.last_visit < NOW() - INTERVAL '6 months')
AND EXISTS (SELECT 1 FROM appointments WHERE patient_id = p.id)
```
- **Severidad**: `suggestion` (solo si count > 5)
- **Mensaje**: "{N} pacientes activos sin control hace mas de 6 meses"
- **Accion**: `ver_pacientes`
- **Peso**: 4

---

## 3. CHECKS DE CONFIGURACION

### Check 9: Profesionales sin horarios
```sql
SELECT COUNT(*) FROM professionals
WHERE tenant_id = $1 AND is_active = true
AND (working_hours IS NULL OR working_hours = '{}')
```
- **Severidad**: `warning`
- **Peso**: 8

### Check 10: Google Calendar no conectado
```sql
SELECT COUNT(*) FROM google_oauth_tokens
WHERE tenant_id = $1
```
- **Severidad**: `warning` (si count = 0)
- **Peso**: 6

### Check 11: WhatsApp no conectado
```sql
SELECT COUNT(*) FROM credentials
WHERE tenant_id = $1 AND category = 'ycloud'
```
- **Severidad**: `warning` (si count = 0)
- **Peso**: 8

### Check 12: FAQ insuficientes
```sql
SELECT COUNT(*) FROM clinic_faqs
WHERE tenant_id = $1 AND answer IS NOT NULL AND answer != ''
```
- **Severidad**: `suggestion` (si count < 3)
- **Mensaje**: "Solo tenes {N} FAQ. Agrega mas para que el agente responda mejor"
- **Peso**: 5

### Check 13: Sin tipos de tratamiento
```sql
SELECT COUNT(*) FROM treatment_types
WHERE tenant_id = $1 AND is_active = true
```
- **Severidad**: `warning` (si count = 0)
- **Peso**: 7

---

## 3.1. CHECKS DE ONBOARDING

### Check 14: Onboarding incompleto
```python
# Count completed onboarding steps
steps = [
    has_professionals, has_working_hours, has_treatment_types,
    has_whatsapp, has_google_calendar, has_faqs_min3,
    has_bank_details, has_consultation_price
]
completed = sum(1 for s in steps if s)
```
- **Severidad**: `warning` si completed < 8
- **Mensaje**: "Configuracion {completed}/8 completa. Faltan: {missing_steps}"
- **Accion**: `onboarding`
- **Peso**: 9 (high — incomplete setup affects everything)

---

## 4. SCORE (0-100)

```python
score = 0

# Configuracion (50 puntos max)
if has_active_professionals:          score += 10
if professionals_have_schedules:      score += 10
if has_treatment_types:               score += 10
if has_whatsapp_connected:            score += 10
if has_google_calendar:               score += 5
if faq_count >= 3:                    score += 5

# Operativo (50 puntos max)
if appointments_this_week > 0:        score += 10
if unconfirmed_today == 0:            score += 10
if pending_payments == 0:             score += 10
if reminders_sent_pct >= 80:          score += 10
if derivations_24h <= 3:              score += 10
```

---

## 4.1. Score Consolidado (solo CEO)

When a CEO views health across all sedes:

```python
async def get_consolidated_health(allowed_tenant_ids: List[int]):
    per_sede = []
    total_score = 0
    all_checks = []

    for tid in allowed_tenant_ids:
        sede_health = await get_health_check(tid)  # existing function
        clinic_name = await get_clinic_name(tid)
        per_sede.append({
            "tenant_id": tid,
            "clinic_name": clinic_name,
            "score": sede_health["score"],
            "checks": sede_health["checks"],
            "stats": sede_health["stats"]
        })
        total_score += sede_health["score"]
        # Prepend sede name to each check message
        for check in sede_health["checks"]:
            check["sede"] = clinic_name
            all_checks.append(check)

    consolidated_score = total_score // len(allowed_tenant_ids) if allowed_tenant_ids else 0

    # Sort all checks by weight descending
    all_checks.sort(key=lambda c: c["weight"], reverse=True)

    return {
        "consolidated_score": consolidated_score,
        "per_sede": per_sede,
        "global_checks": all_checks[:10],  # Top 10 across all sedes
        "global_stats": {
            "total_sedes": len(allowed_tenant_ids),
            "sedes_ok": len([s for s in per_sede if s["score"] >= 80]),
            "sedes_warning": len([s for s in per_sede if 50 <= s["score"] < 80]),
            "sedes_critical": len([s for s in per_sede if s["score"] < 50]),
            # Aggregated stats
            "appointments_today": sum(s["stats"]["appointments_today"] for s in per_sede),
            "patients_total": sum(s["stats"]["patients_total"] for s in per_sede),
            "pending_payments": sum(s["stats"]["pending_payments"] for s in per_sede),
            "cancellations_today": sum(s["stats"]["cancellations_today"] for s in per_sede),
        }
    }
```

Response shape for CEO:
```json
{
    "consolidated_score": 75,
    "per_sede": [
        {"tenant_id": 1, "clinic_name": "Sede Salta", "score": 78, "checks": [...], "stats": {...}},
        {"tenant_id": 2, "clinic_name": "Sede Córdoba", "score": 65, "checks": [...], "stats": {...}},
        {"tenant_id": 3, "clinic_name": "Sede Neuquén", "score": 82, "checks": [...], "stats": {...}}
    ],
    "global_checks": [
        {"type": "alert", "sede": "Sede Córdoba", "message": "5 turnos sin confirmar para hoy", "weight": 10},
        {"type": "warning", "sede": "Sede Salta", "message": "Google Calendar no conectado", "weight": 6}
    ],
    "global_stats": {
        "total_sedes": 3,
        "sedes_ok": 1,
        "sedes_warning": 2,
        "sedes_critical": 0,
        "appointments_today": 34,
        "patients_total": 580,
        "pending_payments": 8,
        "cancellations_today": 2
    }
}
```

---

## 5. GREETING BASADO EN SCORE

```python
def build_greeting(page, checks, score, stats, onboarding_completed=8):
    # Before page-specific greeting, check onboarding
    if onboarding_completed < 8:
        missing = 8 - onboarding_completed
        return f"Tu sede tiene {missing} pasos de configuracion pendientes. Queres que te ayude a completarlos?"

    # Score-based prefix
    if score < 50:
        alert_checks = [c for c in checks if c["type"] in ("alert", "warning")]
        if alert_checks:
            return f"La clinica necesita atencion. Lo mas urgente: {alert_checks[0]['message']}"

    if score <= 80:
        suggestions = [c for c in checks if c["type"] == "suggestion"]
        if suggestions:
            return f"Va bien! Pero podes mejorar: {suggestions[0]['message']}"

    # Page-specific
    if page == "agenda":
        n = stats.get("appointments_today", 0)
        unconf = stats.get("unconfirmed_today", 0)
        if n > 0:
            msg = f"Hoy tenes {n} turnos."
            if unconf > 0:
                msg += f" {unconf} sin confirmar."
            return msg
        return "No hay turnos para hoy."

    if page == "pacientes":
        return f"Tenes {stats.get('patients_total', 0)} pacientes. Busco alguno?"

    if page == "chats":
        active = stats.get("active_conversations", 0)
        if active > 0:
            return f"{active} conversaciones activas. Alguna para revisar?"
        return "Sin conversaciones activas. Todo tranquilo."

    if page == "analytics":
        return "Queres que te haga un resumen de la semana?"

    if page == "configuracion":
        return "Aca podes ajustar integraciones y configuracion de la clinica."

    return "Hola! Soy Nova. En que te ayudo?"
```

---

## 6. TOAST NOTIFICATION

Logica del toast (1 por sesion):

```typescript
useEffect(() => {
    const shown = sessionStorage.getItem('nova_toast_shown');
    if (shown) return;

    const checkAlerts = async () => {
        const data = await fetchApi('/admin/nova/health-check');
        const alerts = data?.checks?.filter(c => c.type === 'alert') || [];
        if (alerts.length > 0) {
            setToastMessage(`Nova: ${alerts[0].message}`);
            setToastVisible(true);
            sessionStorage.setItem('nova_toast_shown', 'true');
            setTimeout(() => setToastVisible(false), 8000);
        }

        // CEO: find worst sede
        if (user.role === 'ceo' && data.per_sede) {
            const worst = data.per_sede.sort((a, b) => a.score - b.score)[0];
            if (worst.score < 70) {
                setToastMessage(`Nova: ${worst.clinic_name} necesita atencion (score: ${worst.score})`);
                setToastVisible(true);
                sessionStorage.setItem('nova_toast_shown', 'true');
                setTimeout(() => setToastVisible(false), 8000);
            }
        }
    };

    // Delay 2s para no bloquear carga
    setTimeout(checkAlerts, 2000);
}, []);
```

---

## 7. RESPONSE SHAPE (health-check)

```json
{
    "score": 78,
    "checks": [
        {
            "type": "alert",
            "icon": "calendar",
            "message": "3 turnos sin confirmar para hoy",
            "action": "confirmar_turnos",
            "weight": 10
        },
        {
            "type": "warning",
            "icon": "credit-card",
            "message": "5 turnos completados sin cobrar",
            "action": "facturacion_pendiente",
            "weight": 7
        }
    ],
    "completed": [
        "3 profesionales activos",
        "Horarios configurados",
        "8 tipos de tratamiento",
        "WhatsApp conectado",
        "234 pacientes registrados",
        "Turnos esta semana (45)"
    ],
    "top_priority": "3 turnos sin confirmar para hoy",
    "stats": {
        "professionals": 3,
        "treatment_types": 8,
        "patients_total": 234,
        "appointments_today": 12,
        "appointments_week": 45,
        "unconfirmed_today": 3,
        "pending_payments": 5,
        "cancellations_today": 1,
        "derivations_24h": 2,
        "faq_count": 7
    }
}
```

---

## 8. ICON MAP (Frontend)

```typescript
const ICON_MAP: Record<string, ReactNode> = {
    'calendar': <Calendar size={14} />,
    'clock': <Clock size={14} />,
    'bell': <Bell size={14} />,
    'credit-card': <CreditCard size={14} />,
    'alert-triangle': <AlertTriangle size={14} />,
    'user-plus': <UserPlus size={14} />,
    'message-circle': <MessageCircle size={14} />,
    'users': <Users size={14} />,
    'settings': <Settings size={14} />,
    'link': <Link size={14} />,
    'help-circle': <HelpCircle size={14} />,
    'clipboard': <Clipboard size={14} />,
};
```

---

## 9. VERIFICACION

1. `GET /admin/nova/health-check` retorna score + checks correctos
2. Score sube cuando se resuelven checks (confirmar turnos → check desaparece)
3. Greeting contextual correcto por pagina
4. Toast aparece 1 vez por sesion si hay alertas
5. Cards de checks en tab Salud son clicables → navegan a la pagina correcta
6. Stats grid muestra datos reales del tenant
7. Profesional ve solo checks relevantes a su rol
8. CEO ve todos los checks incluyendo facturacion y analytics
9. CEO consolidated score muestra promedio correcto de todas las sedes
10. CEO toast muestra la sede con peor score cuando < 70
11. Onboarding check detecta pasos faltantes y muestra greeting especifico
12. Check 14 (onboarding) aparece con peso 9 cuando configuracion < 8/8
