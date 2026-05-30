# Spec: Financial Command Center — Backend

---

## 1. Migración de Base de Datos (020)

### 1.1 Nueva tabla: `professional_commissions`

Almacena la configuración de comisiones por profesional, con un porcentaje default y overrides opcionales por tratamiento.

```sql
CREATE TABLE professional_commissions (
    id              SERIAL PRIMARY KEY,
    tenant_id       INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    professional_id INTEGER NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    commission_pct  NUMERIC(5,2) NOT NULL DEFAULT 0,
    treatment_code  VARCHAR(100),  -- NULL = default para todos los tratamientos
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_prof_comm UNIQUE (tenant_id, professional_id, COALESCE(treatment_code, '__default__'))
);

CREATE INDEX idx_prof_comm_tenant ON professional_commissions(tenant_id);
CREATE INDEX idx_prof_comm_professional ON professional_commissions(professional_id);
```

**Reglas de negocio:**
- `treatment_code = NULL` → comisión default del profesional (aplica a todos los tratamientos sin override)
- `treatment_code = 'cleaning'` → override específico para ese tratamiento
- Si no hay configuración para un profesional, se usa 0% (el profesional recibe el 100% del cobro) con warning en logs
- `commission_pct` = porcentaje que el profesional recibe (0-100). Si es 30, el profesional recibe 30% del total facturado

### 1.2 Nueva tabla: `liquidation_records`

Snapshots persistentes de liquidaciones por profesional y período.

```sql
CREATE TABLE liquidation_records (
    id                SERIAL PRIMARY KEY,
    tenant_id         INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    professional_id   INTEGER NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    period_start      DATE NOT NULL,
    period_end        DATE NOT NULL,
    total_billed      NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_paid        NUMERIC(12,2) NOT NULL DEFAULT 0,
    total_pending     NUMERIC(12,2) NOT NULL DEFAULT 0,
    commission_pct    NUMERIC(5,2) NOT NULL DEFAULT 0,
    commission_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
    payout_amount     NUMERIC(12,2) NOT NULL DEFAULT 0,
    status            VARCHAR(20) NOT NULL DEFAULT 'draft',
    generated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at       TIMESTAMPTZ,
    paid_at           TIMESTAMPTZ,
    generated_by      VARCHAR(255),
    notes             JSONB DEFAULT '{}',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_liquidation_status CHECK (status IN ('draft', 'generated', 'approved', 'paid')),
    CONSTRAINT uq_liquidation_period UNIQUE (tenant_id, professional_id, period_start, period_end)
);

CREATE INDEX idx_liquidation_tenant ON liquidation_records(tenant_id);
CREATE INDEX idx_liquidation_professional ON liquidation_records(professional_id);
CREATE INDEX idx_liquidation_period ON liquidation_records(period_start, period_end);
CREATE INDEX idx_liquidation_status ON liquidation_records(status);
```

**Estados:**
- `draft` → liquidación creada pero no confirmada
- `generated` → generada con datos del período, lista para revisión
- `approved` → aprobada por el CEO/secretaria, pendiente de pago
- `paid` → pagada al profesional

### 1.3 Nueva tabla: `professional_payouts`

Tracking de pagos realizados a profesionales contra liquidaciones.

```sql
CREATE TABLE professional_payouts (
    id                SERIAL PRIMARY KEY,
    tenant_id         INTEGER NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    liquidation_id    INTEGER NOT NULL REFERENCES liquidation_records(id) ON DELETE CASCADE,
    professional_id   INTEGER NOT NULL REFERENCES professionals(id) ON DELETE CASCADE,
    amount            NUMERIC(12,2) NOT NULL,
    payment_method    VARCHAR(20) NOT NULL DEFAULT 'transfer',
    payment_date      DATE NOT NULL DEFAULT CURRENT_DATE,
    reference_number  VARCHAR(100),
    notes             TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_payout_method CHECK (payment_method IN ('transfer', 'cash', 'check'))
);

CREATE INDEX idx_payout_tenant ON professional_payouts(tenant_id);
CREATE INDEX idx_payout_liquidation ON professional_payouts(liquidation_id);
CREATE INDEX idx_payout_professional ON professional_payouts(professional_id);
```

---

## 2. ORM Models (models.py)

Agregar las siguientes clases SQLAlchemy a `orchestrator_service/models.py`:

### 2.1 ProfessionalCommission

```python
class ProfessionalCommission(Base):
    __tablename__ = "professional_commissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    professional_id = Column(Integer, ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False)
    commission_pct = Column(Numeric(5, 2), nullable=False, server_default="0")
    treatment_code = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "professional_id", "treatment_code", name="uq_prof_comm"),
    )

    professional = relationship("Professional", backref="commission_configs")
    tenant = relationship("Tenant")
```

### 2.2 LiquidationRecord

```python
class LiquidationRecord(Base):
    __tablename__ = "liquidation_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    professional_id = Column(Integer, ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    total_billed = Column(Numeric(12, 2), nullable=False, server_default="0")
    total_paid = Column(Numeric(12, 2), nullable=False, server_default="0")
    total_pending = Column(Numeric(12, 2), nullable=False, server_default="0")
    commission_pct = Column(Numeric(5, 2), nullable=False, server_default="0")
    commission_amount = Column(Numeric(12, 2), nullable=False, server_default="0")
    payout_amount = Column(Numeric(12, 2), nullable=False, server_default="0")
    status = Column(String(20), nullable=False, server_default="draft")
    generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    generated_by = Column(String(255), nullable=True)
    notes = Column(JSONB, server_default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    professional = relationship("Professional", backref="liquidation_records")
    tenant = relationship("Tenant")
    payouts = relationship("ProfessionalPayout", back_populates="liquidation_record")
```

### 2.3 ProfessionalPayout

```python
class ProfessionalPayout(Base):
    __tablename__ = "professional_payouts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    liquidation_id = Column(Integer, ForeignKey("liquidation_records.id", ondelete="CASCADE"), nullable=False)
    professional_id = Column(Integer, ForeignKey("professionals.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(20), nullable=False, server_default="transfer")
    payment_date = Column(Date, nullable=False, server_default=func.current_date())
    reference_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    liquidation_record = relationship("LiquidationRecord", back_populates="payouts")
    professional = relationship("Professional", backref="payouts")
    tenant = relationship("Tenant")
```

### 2.4 Modelos faltantes: TreatmentPlan, TreatmentPlanItem, TreatmentPlanPayment

Agregar los 3 modelos que actualmente no existen en `models.py` pero cuyas tablas sí existen en la BD (creadas por migraciones 018 y 019):

```python
class TreatmentPlan(Base):
    __tablename__ = "treatment_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    patient_id = Column(Integer, ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    professional_id = Column(Integer, ForeignKey("professionals.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False, server_default="draft")
    estimated_total = Column(Numeric(12, 2), server_default="0")
    approved_total = Column(Numeric(12, 2), server_default="0")
    paid_total = Column(Numeric(12, 2), server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    approved_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)

    patient = relationship("Patient", backref="treatment_plans")
    professional = relationship("Professional")
    tenant = relationship("Tenant")
    items = relationship("TreatmentPlanItem", back_populates="plan", cascade="all, delete-orphan")
    payments = relationship("TreatmentPlanPayment", back_populates="plan", cascade="all, delete-orphan")


class TreatmentPlanItem(Base):
    __tablename__ = "treatment_plan_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(String(36), ForeignKey("treatment_plans.id", ondelete="CASCADE"), nullable=False)
    treatment_type_code = Column(String(100), nullable=True)
    custom_description = Column(String(500), nullable=True)
    estimated_price = Column(Numeric(12, 2), server_default="0")
    approved_price = Column(Numeric(12, 2), server_default="0")
    quantity = Column(Integer, server_default="1")
    sort_order = Column(Integer, server_default="0")
    status = Column(String(30), server_default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = relationship("TreatmentPlan", back_populates="items")
    tenant = relationship("Tenant")


class TreatmentPlanPayment(Base):
    __tablename__ = "treatment_plan_payments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False)
    plan_id = Column(String(36), ForeignKey("treatment_plans.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(50), nullable=True)
    payment_date = Column(DateTime(timezone=True), server_default=func.now())
    reference_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = relationship("TreatmentPlan", back_populates="payments")
    tenant = relationship("Tenant")
```

---

## 3. Servicio de Liquidaciones (liquidation_service.py)

Nuevo archivo: `orchestrator_service/services/liquidation_service.py`

### 3.1 `generate_liquidation(tenant_id, professional_id, period_start, period_end, generated_by)`

Genera un snapshot de liquidación para un profesional en un período dado.

**Lógica:**
1. Verificar unicidad: si ya existe `liquidation_record` para `(tenant_id, professional_id, period_start, period_end)`, retornarlo (idempotente)
2. Obtener comisiones del profesional desde `professional_commissions`
3. Ejecutar query de liquidación (reusar lógica de `analytics_service.get_professionals_liquidation`):
   - SELECT appointments en el período para ese profesional
   - Incluir `billing_amount`, `payment_status`, tratamiento, paciente
   - Incluir `treatment_plan_payments` asociados
4. Calcular totales:
   - `total_billed` = SUM(billing_amount) de todos los appointments
   - `total_paid` = SUM(billing_amount) donde payment_status = 'paid' + SUM(treatment_plan_payments.amount)
   - `total_pending` = total_billed - total_paid
5. Aplicar comisión:
   - Para cada appointment: buscar override por `treatment_code`, sino usar `commission_pct` default
   - `commission_amount` = SUM(billing_amount * commission_pct / 100) para cada línea
   - `payout_amount` = commission_amount (el payout es lo que el profesional recibe)
6. Crear `liquidation_record` con status='generated'
7. Retornar el record completo con detalle de treatment groups

**Criterio de aceptación:**
- Generación idempotente: llamar 2 veces con mismos parámetros retorna el mismo record
- Cálculos coinciden con `analytics_service.get_professionals_liquidation` para el mismo período
- Si no hay appointments, retorna liquidación con $0 en todos los totales
- Si no hay comisión configurada, usa 0% con warning en logs

### 3.2 `generate_bulk_liquidations(tenant_id, period_start, period_end, generated_by)`

Genera liquidaciones para TODOS los profesionales activos del tenant en el período.

**Lógica:**
1. Obtener lista de profesionales activos: `SELECT id FROM professionals WHERE tenant_id=$1 AND is_active=true`
2. Para cada profesional, llamar `generate_liquidation()`
3. Retornar array de liquidation_records creados

### 3.3 `get_liquidation_detail(tenant_id, liquidation_id)`

Retorna el detalle completo de una liquidación incluyendo treatment groups.

**Lógica:**
1. Fetch `liquidation_record` verificando `tenant_id`
2. Re-ejecutar query de appointments del período para obtener detalle actualizado (mismo query que `get_professionals_liquidation`)
3. Retornar: liquidation_record + treatment_groups (profesional → paciente → tratamiento → sesiones)

### 3.4 `update_liquidation_status(tenant_id, liquidation_id, new_status, updated_by, notes)`

Actualiza el status de una liquidación con audit trail.

**Lógica:**
1. Validar transición de estado: draft→generated→approved→paid
2. Actualizar status + timestamp correspondiente (approved_at, paid_at)
3. Agregar entrada al JSONB `notes`: `{ action: 'status_change', from: 'X', to: 'Y', by: 'email', at: 'ISO8601', notes: '...' }`
4. Si status='paid' y no hay payout, crear payout automático por `payout_amount`

### 3.5 `create_payout(tenant_id, liquidation_id, amount, payment_method, reference_number, notes, created_by)`

Crea un registro de pago a profesional.

**Lógica:**
1. Verificar que `liquidation_record` existe y pertenece al tenant
2. Crear `professional_payout` record
3. Calcular total payouts de la liquidación: `SELECT SUM(amount) FROM professional_payouts WHERE liquidation_id=$1`
4. Si `total_payouts >= liquidation.payout_amount`, actualizar status a 'paid' y set `paid_at`
5. Agregar entrada audit al `notes` de la liquidación

### 3.6 `get_payouts_for_liquidation(tenant_id, liquidation_id)`

Retorna todos los payouts asociados a una liquidación.

---

## 4. Servicio de Dashboard Financiero (financial_dashboard_service.py)

Nuevo archivo: `orchestrator_service/services/financial_dashboard_service.py`

### 4.1 `get_financial_summary(tenant_id, period_start, period_end)`

Retorna resumen financiero global del período.

**Query:**
```sql
-- Total revenue: SUM de billing_amount de appointments completed + treatment_plan_payments
-- Total payouts: SUM de professional_payouts.amount
-- Net profit: revenue - payouts
-- Pending collections: appointments con payment_status != 'paid' y billing_amount > 0
```

**Response:**
```json
{
  "total_revenue": 1500000.00,
  "total_payouts": 450000.00,
  "net_profit": 1050000.00,
  "pending_collections": 230000.00,
  "period_start": "2026-03-01",
  "period_end": "2026-03-31"
}
```

### 4.2 `get_revenue_by_professional(tenant_id, period_start, period_end)`

Retorna revenue agrupado por profesional para gráfico de barras.

**Response:**
```json
[
  { "professional_id": 5, "professional_name": "Dra. Pérez", "total_revenue": 500000.00, "appointment_count": 45 },
  { "professional_id": 8, "professional_name": "Dr. García", "total_revenue": 350000.00, "appointment_count": 32 }
]
```

### 4.3 `get_revenue_by_treatment(tenant_id, period_start, period_end)`

Retorna revenue agrupado por tipo de tratamiento para gráfico de torta.

**Response:**
```json
[
  { "treatment_code": "cleaning", "treatment_name": "Limpieza dental", "total_revenue": 200000.00, "percentage": 25.0 },
  { "treatment_code": "implant", "treatment_name": "Implante", "total_revenue": 400000.00, "percentage": 50.0 }
]
```

### 4.4 `get_daily_cash_flow(tenant_id, period_start, period_end)`

Retorna entradas diarias para gráfico de línea.

**Response:**
```json
[
  { "date": "2026-03-01", "revenue": 45000.00, "payouts": 0 },
  { "date": "2026-03-02", "revenue": 32000.00, "payouts": 15000.00 }
]
```

### 4.5 `get_mom_growth(tenant_id, current_period_start, current_period_end)`

Calcula crecimiento mes a mes comparando con el período anterior de igual duración.

**Response:**
```json
{
  "current_revenue": 1500000.00,
  "previous_revenue": 1200000.00,
  "growth_pct": 25.0,
  "current_payouts": 450000.00,
  "previous_payouts": 400000.00,
  "payout_growth_pct": 12.5
}
```

### 4.6 `get_top_treatments(tenant_id, period_start, period_end, limit=5)`

Retorna los N tratamientos más rentables del período.

**Response:**
```json
[
  { "treatment_code": "implant", "treatment_name": "Implante dental", "revenue": 400000.00, "count": 8 },
  { "treatment_code": "crown", "treatment_name": "Corona", "revenue": 300000.00, "count": 12 }
]
```

### 4.7 `get_pending_collections(tenant_id, period_start, period_end)`

Retorna lista de cobros pendientes con alertas.

**Response:**
```json
[
  {
    "patient_id": 123,
    "patient_name": "Lucas Puig",
    "appointment_id": "uuid",
    "treatment_name": "Implante",
    "amount_pending": 180000.00,
    "days_overdue": 15,
    "professional_name": "Dra. Pérez"
  }
]
```

---

## 5. Endpoints (admin_routes.py)

Todos los endpoints bajo `/admin/`, protegidos con `verify_admin_token` y `get_resolved_tenant_id`.

---

### EP-FC-01: POST /admin/liquidations/generate

Genera una liquidación para un profesional en un período específico.

**Request:**
```json
{
  "professional_id": 5,
  "period_start": "2026-03-01",
  "period_end": "2026-03-31"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "professional_id": 5,
  "professional_name": "Dra. Pérez",
  "period_start": "2026-03-01",
  "period_end": "2026-03-31",
  "total_billed": 500000.00,
  "total_paid": 450000.00,
  "total_pending": 50000.00,
  "commission_pct": 30.00,
  "commission_amount": 150000.00,
  "payout_amount": 150000.00,
  "status": "generated",
  "generated_at": "2026-04-03T10:00:00Z",
  "generated_by": "ceo@clinic.com",
  "treatment_groups": [ ... ]
}
```

**Lógica:**
1. Validar fechas (mismas validaciones que endpoint de liquidación existente)
2. Llamar `liquidation_service.generate_liquidation()`
3. Si ya existe (idempotente), retornar 200 con el record existente
4. Si es nuevo, retornar 201

**Criterios de aceptación:**
- Idempotente: misma request 2 veces → mismo record
- Si profesional no existe → HTTP 404
- Si período inválido → HTTP 400
- Si no hay appointments → liquidación con $0 totales

---

### EP-FC-02: POST /admin/liquidations/generate-bulk

Genera liquidaciones para TODOS los profesionales activos del tenant.

**Request:**
```json
{
  "period_start": "2026-03-01",
  "period_end": "2026-03-31"
}
```

**Response (201 Created):**
```json
{
  "generated_count": 5,
  "skipped_count": 2,
  "liquidations": [
    { "id": 1, "professional_id": 5, "professional_name": "Dra. Pérez", "total_billed": 500000.00, "status": "generated" },
    { "id": 2, "professional_id": 8, "professional_name": "Dr. García", "total_billed": 350000.00, "status": "generated" }
  ]
}
```

**Lógica:**
1. Llamar `liquidation_service.generate_bulk_liquidations()`
2. Retornar conteo de generadas vs salteadas (ya existentes)

---

### EP-FC-03: GET /admin/liquidations

Lista de liquidaciones con filtros y paginación.

**Query params:**
- `professional_id` (opcional): filtrar por profesional
- `status` (opcional): draft|generated|approved|paid
- `period_start` (opcional): filtrar desde
- `period_end` (opcional): filtrar hasta
- `page` (default: 1)
- `page_size` (default: 20, max: 100)

**Response (200 OK):**
```json
{
  "liquidations": [
    {
      "id": 1,
      "professional_id": 5,
      "professional_name": "Dra. Pérez",
      "period_start": "2026-03-01",
      "period_end": "2026-03-31",
      "total_billed": 500000.00,
      "commission_amount": 150000.00,
      "payout_amount": 150000.00,
      "status": "approved",
      "generated_at": "2026-04-01T10:00:00Z",
      "approved_at": "2026-04-02T14:00:00Z"
    }
  ],
  "total": 45,
  "page": 1,
  "page_size": 20,
  "total_pages": 3
}
```

---

### EP-FC-04: GET /admin/liquidations/{id}

Detalle completo de una liquidación con treatment groups.

**Response (200 OK):**
```json
{
  "id": 1,
  "professional_id": 5,
  "professional_name": "Dra. Pérez",
  "period_start": "2026-03-01",
  "period_end": "2026-03-31",
  "total_billed": 500000.00,
  "total_paid": 450000.00,
  "total_pending": 50000.00,
  "commission_pct": 30.00,
  "commission_amount": 150000.00,
  "payout_amount": 150000.00,
  "status": "approved",
  "generated_at": "2026-04-01T10:00:00Z",
  "approved_at": "2026-04-02T14:00:00Z",
  "generated_by": "ceo@clinic.com",
  "notes": {},
  "treatment_groups": [
    {
      "patient_id": 123,
      "patient_name": "Lucas Puig",
      "treatment_code": "implant",
      "treatment_name": "Implante dental",
      "sessions": [
        { "appointment_id": "uuid", "date": "2026-03-15", "amount": 200000.00, "payment_status": "paid" }
      ],
      "total": 200000.00
    }
  ],
  "payouts": [
    { "id": 1, "amount": 150000.00, "payment_method": "transfer", "payment_date": "2026-04-02", "reference_number": "TXN-12345" }
  ]
}
```

---

### EP-FC-05: PATCH /admin/liquidations/{id}

Actualiza el status de una liquidación.

**Request:**
```json
{
  "status": "approved",
  "notes": "Revisado y conforme"
}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "status": "approved",
  "approved_at": "2026-04-03T10:00:00Z",
  "notes": {
    "audit_trail": [
      { "action": "status_change", "from": "generated", "to": "approved", "by": "ceo@clinic.com", "at": "2026-04-03T10:00:00Z", "notes": "Revisado y conforme" }
    ]
  }
}
```

**Validaciones:**
- Transiciones válidas: draft→generated, generated→approved, approved→paid
- Transiciones inválidas → HTTP 400
- Si status='paid', set `paid_at`

---

### EP-FC-06: POST /admin/liquidations/{id}/payout

Registra un pago a profesional.

**Request:**
```json
{
  "amount": 150000.00,
  "payment_method": "transfer",
  "reference_number": "TXN-12345",
  "notes": "Transferencia bancaria"
}
```

**Response (201 Created):**
```json
{
  "id": 1,
  "liquidation_id": 1,
  "amount": 150000.00,
  "payment_method": "transfer",
  "payment_date": "2026-04-03",
  "reference_number": "TXN-12345",
  "created_at": "2026-04-03T10:00:00Z"
}
```

**Lógica:**
1. Crear `professional_payout`
2. Si `SUM(payouts.amount) >= liquidation.payout_amount`, actualizar liquidation status a 'paid'
3. Audit trail en notes de la liquidación

**Validaciones:**
- `amount` > 0 → sino HTTP 400
- `payment_method` en ['transfer', 'cash', 'check'] → sino HTTP 400
- Liquidation no puede estar en 'draft' → HTTP 400

---

### EP-FC-07: GET /admin/liquidations/{id}/payouts

Lista todos los payouts de una liquidación.

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "liquidation_id": 1,
    "amount": 150000.00,
    "payment_method": "transfer",
    "payment_date": "2026-04-03",
    "reference_number": "TXN-12345",
    "notes": "Transferencia bancaria",
    "created_at": "2026-04-03T10:00:00Z"
  }
]
```

---

### EP-FC-08: GET /admin/financial-dashboard

Dashboard financiero global con todas las métricas.

**Query params:**
- `period_start` (requerido): YYYY-MM-DD
- `period_end` (requerido): YYYY-MM-DD

**Response (200 OK):**
```json
{
  "summary": {
    "total_revenue": 1500000.00,
    "total_payouts": 450000.00,
    "net_profit": 1050000.00,
    "pending_collections": 230000.00
  },
  "revenue_by_professional": [
    { "professional_id": 5, "professional_name": "Dra. Pérez", "total_revenue": 500000.00, "appointment_count": 45 }
  ],
  "revenue_by_treatment": [
    { "treatment_code": "implant", "treatment_name": "Implante", "total_revenue": 400000.00, "percentage": 26.7 }
  ],
  "daily_cash_flow": [
    { "date": "2026-03-01", "revenue": 45000.00, "payouts": 0 }
  ],
  "mom_growth": {
    "current_revenue": 1500000.00,
    "previous_revenue": 1200000.00,
    "growth_pct": 25.0
  },
  "top_treatments": [
    { "treatment_code": "implant", "treatment_name": "Implante dental", "revenue": 400000.00, "count": 8 }
  ],
  "pending_collections": [
    { "patient_name": "Lucas Puig", "treatment_name": "Implante", "amount_pending": 180000.00, "days_overdue": 15 }
  ]
}
```

---

### EP-FC-09: GET /admin/professionals/{id}/commissions

Retorna configuración de comisiones de un profesional.

**Response (200 OK):**
```json
{
  "professional_id": 5,
  "professional_name": "Dra. Pérez",
  "default_commission_pct": 30.00,
  "per_treatment": [
    { "treatment_code": "implant", "treatment_name": "Implante", "commission_pct": 35.00 },
    { "treatment_code": "crown", "treatment_name": "Corona", "commission_pct": 25.00 }
  ]
}
```

**Si no hay configuración:**
```json
{
  "professional_id": 5,
  "professional_name": "Dra. Pérez",
  "default_commission_pct": 0,
  "per_treatment": [],
  "warning": "Sin configuración de comisiones. Se aplica 0% (profesional recibe 100%)."
}
```

---

### EP-FC-10: PUT /admin/professionals/{id}/commissions

Crea o actualiza configuración de comisiones.

**Request:**
```json
{
  "default_commission_pct": 30.00,
  "per_treatment": [
    { "treatment_code": "implant", "commission_pct": 35.00 },
    { "treatment_code": "crown", "commission_pct": 25.00 }
  ]
}
```

**Response (200 OK):**
```json
{
  "professional_id": 5,
  "default_commission_pct": 30.00,
  "per_treatment": [
    { "treatment_code": "implant", "commission_pct": 35.00 },
    { "treatment_code": "crown", "commission_pct": 25.00 }
  ],
  "updated_at": "2026-04-03T10:00:00Z"
}
```

**Lógica:**
1. Upsert default: `INSERT ... ON CONFLICT (tenant_id, professional_id, treatment_code) DO UPDATE`
2. Para cada per_treatment: upsert individual
3. Eliminar overrides que ya no están en la lista (comparar con existentes)
4. Log de auditoría

**Validaciones:**
- `default_commission_pct` entre 0 y 100 → sino HTTP 400
- Cada `per_treatment.commission_pct` entre 0 y 100 → sino HTTP 400
- `treatment_code` debe existir en `treatment_types` → sino HTTP 400

---

### EP-FC-11: GET /admin/reconciliation

Reporte de conciliación financiera.

**Query params:**
- `period_start` (requerido): YYYY-MM-DD
- `period_end` (requerido): YYYY-MM-DD

**Response (200 OK):**
```json
{
  "period_start": "2026-03-01",
  "period_end": "2026-03-31",
  "total_patient_payments": 1500000.00,
  "total_professional_payouts": 450000.00,
  "difference": 1050000.00,
  "discrepancies": [
    {
      "type": "payment_without_liquidation",
      "appointment_id": "uuid",
      "patient_name": "María López",
      "treatment_name": "Limpieza",
      "amount": 5000.00,
      "appointment_date": "2026-03-15",
      "professional_name": "Dra. Pérez",
      "description": "Pago registrado sin liquidación asociada"
    }
  ],
  "discrepancy_count": 3
}
```

**Lógica de detección de discrepancias:**
1. Obtener todos los appointments con payment_status='paid' en el período
2. Obtener todos los appointments incluidos en liquidation_records del período
3. Discrepancia = appointments pagados que NO están en ninguna liquidación
4. También verificar: payouts sin liquidación asociada (integridad referencial)

---

### EP-FC-12: GET /admin/liquidations/{id}/pdf

Genera y sirve PDF de liquidación.

**Response:**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="Liquidacion_Dra_Perez_Marzo_2026.pdf"
```

**Lógica:** Ver spec-pdf.md

---

### EP-FC-13: POST /admin/liquidations/{id}/send-email

Envía PDF de liquidación por email al profesional.

**Request:**
```json
{
  "to_email": "profesional@email.com"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Liquidación enviada a profesional@email.com"
}
```

**Lógica:**
1. Generar PDF si no existe en caché
2. Enviar email con PDF adjunto
3. Subject: "Liquidación {mes/año} — {clinic_name}"
4. Body: saludo profesional + PDF attachment

---

## 6. Criterios de Aceptación Generales

| # | Criterio | Verificación |
|---|----------|-------------|
| AC-01 | Todas las queries incluyen `tenant_id` filter | Revisar cada query en liquidation_service y financial_dashboard_service |
| AC-02 | Generación idempotente de liquidaciones | LLAMAR 2 veces EP-FC-01 con mismos params → mismo ID |
| AC-03 | Cálculos coinciden con vista actual de liquidación | Comparar output de EP-FC-01 con `GET /analytics/professionals/liquidation` |
| AC-04 | Transiciones de estado válidas | draft→generated→approved→paid, rechazar saltos |
| AC-05 | Audit trail en notes JSONB | Cada cambio de status agrega entrada al array audit_trail |
| AC-06 | Comisión 0% si no configurada | Profesional sin comisiones → liquidación con commission_pct=0 y warning |
| AC-07 | Liquidación vacía si sin appointments | Período sin turnos → liquidación con $0 totales, status='generated' |
| AC-08 | Payout auto-completa liquidación | Si SUM(payouts) >= payout_amount → status='paid' |
