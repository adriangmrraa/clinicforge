# SPEC: Nova Dental Assistant — Daily Analysis + Insights (Fase 4)

**Fecha**: 2026-03-26
**Proyecto**: ClinicForge
**Dependencia**: Fase 1 (backend), Fase 2 (frontend widget)
**Costo**: ~$0.003/clinica/ejecucion (~$0.006/clinica/dia con 2 ejecuciones)

---

## 1. CONCEPTO

Cron job que corre cada 12 horas, analiza las interacciones de pacientes (conversaciones WhatsApp/IG/FB) y la actividad de la clinica (turnos, cancelaciones, pagos) para generar insights accionables.

Diferencia con Platform AI:
- Platform AI analiza solo conversaciones de ventas
- ClinicForge analiza conversaciones + actividad operativa (turnos, cancelaciones, no-shows)

---

## 2. CRON JOB

### Crear: `orchestrator_service/services/nova_daily_analysis.py`

```python
async def nova_daily_analysis_loop(pool, redis):
    """Background loop — runs every 12 hours."""
    while True:
        try:
            await _run_analysis(pool, redis)
        except Exception as e:
            logger.error(f"nova_daily_analysis_error: {e}")
        await asyncio.sleep(12 * 60 * 60)  # 12 hours
```

### Iterate all tenants

The cron iterates over ALL active tenants and then generates a consolidated cross-sede analysis:

```python
async def _run_analysis(pool, redis):
    tenant_rows = await pool.fetch("SELECT id, clinic_name FROM tenants ORDER BY id ASC")
    for tenant in tenant_rows:
        try:
            await _analyze_tenant(pool, redis, tenant['id'], tenant['clinic_name'])
        except Exception as e:
            logger.error(f"nova_analysis_tenant_{tenant['id']}_error: {e}")

    # CEO consolidated analysis (cross-sede)
    await _analyze_consolidated(pool, redis, tenant_rows)
```

### Registrar en `main.py` (lifespan)

```python
# Dentro de lifespan(), despues de scheduler_start:
try:
    from services.nova_daily_analysis import nova_daily_analysis_loop
    asyncio.create_task(nova_daily_analysis_loop(db.pool, redis_client))
    logger.info("nova_daily_analysis_started")
except Exception as e:
    logger.error(f"nova_daily_analysis_start_failed: {e}")
```

---

## 3. DATOS DE ENTRADA

### 3.1 Conversaciones (ultimas 24h)

```sql
SELECT cm.content, cm.role, cc.channel, cc.customer_phone
FROM chat_messages cm
JOIN chat_conversations cc ON cc.id = cm.conversation_id
WHERE cm.tenant_id = $1
AND cm.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY cm.created_at DESC
LIMIT 100
```

**Compactar**: Truncar cada mensaje a 80 chars, prefijo `USER:` / `AGENT:` / `TOOL:`.

### 3.2 Actividad operativa (ultimas 24h)

```sql
-- Turnos creados
SELECT COUNT(*) as created FROM appointments
WHERE tenant_id = $1 AND created_at >= NOW() - INTERVAL '24 hours'

-- Turnos completados
SELECT COUNT(*) as completed FROM appointments
WHERE tenant_id = $1 AND status = 'completed'
AND completed_at >= NOW() - INTERVAL '24 hours'

-- Cancelaciones
SELECT COUNT(*) as cancelled,
       array_agg(cancellation_reason) as reasons
FROM appointments
WHERE tenant_id = $1 AND status = 'cancelled'
AND updated_at >= NOW() - INTERVAL '24 hours'

-- No-shows
SELECT COUNT(*) as no_shows FROM appointments
WHERE tenant_id = $1 AND status = 'no-show'
AND appointment_datetime >= NOW() - INTERVAL '24 hours'

-- Derivaciones a humano
SELECT COUNT(*) as derivations FROM chat_messages
WHERE tenant_id = $1 AND role = 'tool'
AND content ILIKE '%derivhumano%'
AND created_at >= NOW() - INTERVAL '24 hours'

-- Nuevos pacientes
SELECT COUNT(*) as new_patients FROM patients
WHERE tenant_id = $1 AND created_at >= NOW() - INTERVAL '24 hours'

-- Facturacion
SELECT SUM(billing_amount) as revenue FROM appointments
WHERE tenant_id = $1 AND status = 'completed'
AND payment_status = 'completed'
AND completed_at >= NOW() - INTERVAL '24 hours'
```

---

## 4. PROMPT GPT-4o-mini

```python
ANALYSIS_SYSTEM_PROMPT = """Analiza la actividad de una clinica dental en las ultimas 24 horas.

DATOS DE CONVERSACIONES (WhatsApp/Instagram/Facebook):
{conversation_summary}

DATOS OPERATIVOS:
- Turnos creados: {created}
- Turnos completados: {completed}
- Cancelaciones: {cancelled} (razones: {cancel_reasons})
- No-shows: {no_shows}
- Derivaciones a humano: {derivations}
- Pacientes nuevos: {new_patients}
- Facturacion: ${revenue}

Retorna un JSON con:
- temas_frecuentes: [3-5 temas mas consultados por pacientes, cada uno con "tema" y "cantidad_aprox"]
- problemas: [situaciones donde el agente respondio mal, derivo innecesariamente, o no supo responder]
- temas_sin_cobertura: [preguntas frecuentes que el agente no pudo responder]
- sugerencias: [2-3 mejoras concretas, cada una con "titulo" y "detalle". Pueden ser: agregar FAQ, ajustar horarios, configurar precios, etc.]
- cancelacion_insights: [analisis de por que se cancelaron turnos, si hay patron]
- satisfaccion_estimada: numero 1-10 basado en tono de conversaciones
- resumen: 2-3 oraciones resumen del dia (incluir datos operativos clave)

Solo JSON valido, sin explicaciones ni markdown.
"""
```

### Llamada API

```python
async def _analyze_with_gpt(prompt: str) -> dict | None:
    response = await httpx.AsyncClient(timeout=30).post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": prompt}
            ],
            "temperature": 0,
            "max_tokens": 700,
            "response_format": {"type": "json_object"}
        }
    )
    return json.loads(response.json()["choices"][0]["message"]["content"])
```

### Tokens estimados

| Componente | Tokens |
|-----------|--------|
| System prompt | ~200 |
| Conversation summary (50 msgs x 80 chars) | ~1500 |
| Operational data | ~100 |
| **Input total** | **~1800** |
| Output (JSON response) | ~500 |
| **Total** | **~2300** |
| **Costo GPT-4o-mini** | **~$0.003** |

---

## 5. CACHE EN REDIS

```python
await redis.setex(
    f"nova_daily:{tenant_id}",
    172800,  # 48 horas TTL
    json.dumps({
        **analysis,
        "operational_stats": {
            "turnos_creados": created,
            "turnos_completados": completed,
            "cancelaciones": cancelled,
            "no_shows": no_shows,
            "derivaciones": derivations,
            "nuevos_pacientes": new_patients,
            "facturacion": revenue
        },
        "analyzed_at": datetime.utcnow().isoformat()
    }, ensure_ascii=False)
)
```

---

## 6. CROSS-SEDE CONSOLIDATED ANALYSIS (CEO)

```python
async def _analyze_consolidated(pool, redis, tenants):
    """Generates cross-sede comparison for CEO view."""
    per_sede_stats = []
    for t in tenants:
        tid = t['id']
        stats = await _get_operational_stats(pool, tid)
        per_sede_stats.append({
            "sede": t['clinic_name'],
            "tenant_id": tid,
            **stats
        })

    # Build comparison prompt
    comparison_prompt = f"""Compara el rendimiento de {len(tenants)} sedes de una clinica dental en las ultimas 24 horas.

DATOS POR SEDE:
{json.dumps(per_sede_stats, indent=2, ensure_ascii=False)}

Retorna JSON con:
- ranking: lista de sedes ordenadas por rendimiento (mejor a peor), cada una con "sede", "score_estimado" (1-10), "razon"
- mejor_sede: {{sede, motivo}} (la que mejor rindio)
- peor_sede: {{sede, motivo, sugerencia}} (la que peor rindio, con sugerencia de mejora)
- comparativas: [3-5 insights comparando sedes. Ej: "Sede X tuvo 60% mas cancelaciones que Sede Y"]
- tendencia_global: 1 oracion sobre la tendencia general del grupo de sedes
- resumen_ceo: 2-3 oraciones resumen ejecutivo para el CEO

Solo JSON valido.
"""

    analysis = await _analyze_with_gpt(comparison_prompt)
    if analysis:
        await redis.setex(
            "nova_daily:consolidated",
            172800,
            json.dumps({**analysis, "analyzed_at": datetime.utcnow().isoformat(), "per_sede_stats": per_sede_stats}, ensure_ascii=False)
        )
```

---

## 7. RESPONSE SHAPE (daily-analysis endpoint)

### GET `/admin/nova/daily-analysis`

**Per-tenant** (default, without query params):

```json
{
    "available": true,
    "analysis": {
        "temas_frecuentes": [
            {"tema": "Consultas de precio (blanqueamiento, ortodoncia)", "cantidad_aprox": 8},
            {"tema": "Disponibilidad de turnos urgentes", "cantidad_aprox": 5},
            {"tema": "Cambios y cancelaciones de turno", "cantidad_aprox": 4},
            {"tema": "Cobertura de obra social", "cantidad_aprox": 3}
        ],
        "problemas": [
            "3 pacientes preguntaron por blanqueamiento y el agente no tenia el precio configurado",
            "2 derivaciones innecesarias por consultas de horarios (la info estaba en las FAQ pero el agente no la encontro)"
        ],
        "temas_sin_cobertura": [
            "Precio de blanqueamiento laser",
            "Si aceptan obra social OSECAC",
            "Estacionamiento cerca de la clinica"
        ],
        "sugerencias": [
            {
                "titulo": "Agregar precios de blanqueamiento",
                "detalle": "Crear FAQ: 'Cuanto sale el blanqueamiento?' → 'El blanqueamiento dental tiene un costo de $X a $Y dependiendo del tipo. Consulta disponibilidad.'"
            },
            {
                "titulo": "Agregar obras sociales aceptadas",
                "detalle": "Crear FAQ: 'Que obras sociales aceptan?' → 'Trabajamos con OSDE, Swiss Medical, Galeno, Medife. Consulta por tu obra social.'"
            },
            {
                "titulo": "Informacion de ubicacion",
                "detalle": "Agregar al prompt del agente: indicaciones de como llegar, estacionamiento cercano, transporte publico."
            }
        ],
        "cancelacion_insights": [
            "2 de 3 cancelaciones fueron por 'problemas de horario'. Considerar agregar turnos en horario extendido (sabado tarde)."
        ],
        "satisfaccion_estimada": 7,
        "resumen": "Dia activo con 12 turnos completados y 3 cancelaciones. 5 pacientes nuevos consultaron por WhatsApp. El agente derivo 2 veces por falta de info en FAQ de precios.",
        "operational_stats": {
            "turnos_creados": 8,
            "turnos_completados": 12,
            "cancelaciones": 3,
            "no_shows": 1,
            "derivaciones": 2,
            "nuevos_pacientes": 5,
            "facturacion": 45000
        },
        "analyzed_at": "2026-03-26T06:00:00Z"
    }
}
```

### GET `/admin/nova/daily-analysis?consolidated=true` (CEO view)

Returns cross-sede analysis from `nova_daily:consolidated` Redis key:

```json
{
    "available": true,
    "consolidated": true,
    "analysis": {
        "ranking": [
            {"sede": "Sede Neuquen", "score_estimado": 8, "razon": "100% turnos completados, 0 cancelaciones"},
            {"sede": "Sede Salta", "score_estimado": 7, "razon": "Buena actividad, 1 cancelacion"},
            {"sede": "Sede Cordoba", "score_estimado": 5, "razon": "3 cancelaciones, 2 no-shows"}
        ],
        "mejor_sede": {"sede": "Sede Neuquen", "motivo": "Tasa de completitud perfecta"},
        "peor_sede": {"sede": "Sede Cordoba", "motivo": "Alta tasa de cancelaciones", "sugerencia": "Revisar confirmaciones automaticas 24h antes"},
        "comparativas": [
            "Sede Cordoba tuvo 3x mas cancelaciones que Salta y Neuquen combinadas",
            "Neuquen lidera en pacientes nuevos (8) vs Salta (3) y Cordoba (2)",
            "La facturacion de Salta ($85.000) supera a las otras dos sedes juntas"
        ],
        "tendencia_global": "Las 3 sedes muestran actividad saludable pero Cordoba necesita atencion en retencion",
        "resumen_ceo": "Dia productivo con 34 turnos totales. Neuquen lidera en completitud, Salta en facturacion. Cordoba preocupa con 3 cancelaciones y 2 no-shows — considerar llamadas de confirmacion."
    },
    "per_sede_stats": [
        {"sede": "Sede Salta", "turnos_creados": 5, "completados": 12, "cancelaciones": 1, "no_shows": 0, "facturacion": 85000},
        {"sede": "Sede Cordoba", "turnos_creados": 3, "completados": 8, "cancelaciones": 3, "no_shows": 2, "facturacion": 32000},
        {"sede": "Sede Neuquen", "turnos_creados": 8, "completados": 14, "cancelaciones": 0, "no_shows": 0, "facturacion": 45000}
    ]
}
```

---

## 8. FRONTEND: TAB INSIGHTS

### Layout del tab (per-tenant)

```
┌──────────────────────────────────────┐
│ 📊 Resumen                           │
│ "Dia activo con 12 turnos            │
│  completados y 3 cancelaciones..."   │
│                                      │
│ 12 completados · 3 cancel · 7/10    │
├──────────────────────────────────────┤
│ STATS OPERATIVOS                     │
│ ┌────┬────┬────┬────┐               │
│ │ 12 │  3 │  1 │ 5  │               │
│ │comp│canc│n/s │new │               │
│ └────┴────┴────┴────┘               │
│ Facturacion: $45.000                 │
├──────────────────────────────────────┤
│ TEMAS FRECUENTES                     │
│ Precios blanqueamiento         8x   │
│ Turnos urgentes                5x   │
│ Cambios de turno               4x   │
├──────────────────────────────────────┤
│ ⚠️ PROBLEMAS                        │
│ "3 pacientes preguntaron por         │
│  blanqueamiento y no habia precio"   │
├──────────────────────────────────────┤
│ 📉 CANCELACIONES                     │
│ "2/3 por problemas de horario.       │
│  Considerar horario extendido."      │
├──────────────────────────────────────┤
│ 💡 SUGERENCIAS                       │
│ ┌ Agregar precios blanqueamiento   ┐│
│ │ "Crear FAQ: Cuanto sale el..."   ││
│ │        [Aplicar sugerencia]      ││
│ └──────────────────────────────────┘│
│ ┌ Agregar obras sociales           ┐│
│ │ "Crear FAQ: Que obras..."        ││
│ │        [Aplicar sugerencia]  ✅  ││
│ └──────────────────────────────────┘│
└──────────────────────────────────────┘
```

### Layout del tab (consolidated=true, CEO view)

```
┌──────────────────────────────────────┐
│ 📊 Resumen ejecutivo                 │
│ "Dia productivo con 34 turnos.       │
│  Neuquen lidera, Cordoba necesita    │
│  atencion en retencion."             │
├──────────────────────────────────────┤
│ RANKING DE SEDES                     │
│ 🥇 Neuquen       ████████████ 8/10  │
│ 🥈 Salta         █████████── 7/10   │
│ 🥉 Cordoba       ██████───── 5/10   │
├──────────────────────────────────────┤
│ 📈 COMPARATIVAS                      │
│ • Cordoba: 3x mas cancelaciones      │
│ • Neuquen lidera en pacientes nuevos │
│ • Salta lidera en facturacion        │
├──────────────────────────────────────┤
│ ⚠️ ATENCION                         │
│ Sede Cordoba: alta tasa cancelacion  │
│ Sugerencia: llamadas confirmacion    │
│ 24h antes            [Aplicar →]     │
└──────────────────────────────────────┘
```

### Aplicar Sugerencia

```typescript
const applySuggestion = async (suggestion, idx) => {
    setApplyingIdx(idx);
    try {
        // Extraer pregunta y respuesta del detalle
        await fetchApi('/admin/nova/apply-suggestion', {
            method: 'POST',
            body: {
                type: 'faq',  // o 'prompt_rule'
                question: suggestion.titulo,
                answer: suggestion.detalle
            }
        });
        setAppliedIdxs(prev => [...prev, idx]);
    } catch (e) {}
    setApplyingIdx(null);
};
```

### Endpoint: POST `/admin/nova/apply-suggestion`

```python
@router.post("/apply-suggestion")
async def apply_suggestion(
    type: str = Body(...),
    question: str = Body(...),
    answer: str = Body(...),
    current_user: User = Depends(get_current_user)
):
    tenant_id = current_user.tenant_id

    if type == "faq":
        # Insertar o actualizar FAQ
        existing = await db.pool.fetchrow(
            "SELECT id FROM clinic_faqs WHERE tenant_id = $1 AND question ILIKE $2",
            tenant_id, f"%{question[:50]}%"
        )
        if existing:
            await db.pool.execute(
                "UPDATE clinic_faqs SET answer = $1, updated_at = NOW() WHERE id = $2",
                answer, existing["id"]
            )
        else:
            await db.pool.execute(
                "INSERT INTO clinic_faqs (tenant_id, question, answer) VALUES ($1, $2, $3)",
                tenant_id, question, answer
            )
        return {"status": "ok", "action": "faq_updated"}

    elif type == "prompt_rule":
        # Agregar regla al system prompt del agente (similar a agregar_regla de Platform AI)
        # Dependera de como ClinicForge maneja el prompt (actualmente en prompt_builder.py)
        return {"status": "ok", "action": "rule_added"}

    return {"status": "error", "detail": "Unknown type"}
```

---

## 9. COSTOS

| Concepto | Costo | Frecuencia |
|----------|-------|------------|
| Health check (SQL) | $0 | Cada vez que se abre Nova |
| Score calculation | $0 | Con health check |
| Toast notification | $0 | 1 por sesion |
| Daily analysis (GPT-4o-mini) | ~$0.003/clinica | 2 veces/dia |
| Consolidated (CEO) | ~$0.002 (shorter prompt, just stats) | 2 veces/dia |
| **Per-tenant: 1 clinica/mes** | **~$0.18** | |
| **3 sedes/dia (2 runs)** | **~$0.022/dia** | |
| **3 sedes/mes** | **~$0.66** | |
| **100 clinicas/mes** | **~$18** | |
| **1000 clinicas/mes** | **~$180** | |

---

## 10. VERIFICACION

1. Cron arranca al iniciar el orchestrator (log: `nova_daily_analysis_started`)
2. Cron itera ALL active tenants (log per tenant on error: `nova_analysis_tenant_{id}_error`)
3. Despues de 12h (o manual trigger), Redis tiene `nova_daily:{tenant_id}` per tenant
4. Redis tiene `nova_daily:consolidated` with cross-sede analysis
5. `GET /admin/nova/daily-analysis` retorna el analisis per-tenant
6. `GET /admin/nova/daily-analysis?consolidated=true` retorna cross-sede CEO analysis
7. Tab Insights muestra resumen, temas, problemas, sugerencias (per-tenant view)
8. Tab Insights CEO view muestra ranking de sedes, comparativas, alertas
9. "Aplicar sugerencia" → FAQ creada en DB → badge "Aplicada"
10. Insight de cancelaciones muestra patrones
11. Stats operativos correctos (comparar con queries directas)
12. Sin datos → "Sin datos de hoy" con mensaje informativo
13. Analisis no incluye datos de pacientes individuales (privacy)
