# REVIEW DEL PROMPT — plan de correcciones (2026-07-12)
Fuente: 4 revisores en paralelo sobre `build_system_prompt` (main.py ~11009-13327).
Todo verificado con línea exacta. Se aplica en PRUEBAS, se valida con banco, luego a PROD.

## 🔴 CRÍTICOS — fallas en conversaciones (lo que Carlos pidió arreglar)

| # | Falla | Dónde | Fix |
|---|---|---|---|
| C1 | **Fuga de precio por FAQ**: lead con OS pregunta precio → FAQ "$60.000" se responde textual, salteando el gate | formatter FAQ 10869-72 + 12491 | El GATE DE PRECIO le gana también a las FAQs de precio: si es FAQ de precio/consulta y no está resuelta la cobertura → aplicar gate primero |
| C2 | **Coseguro**: el prompt inyecta "coseguro por defecto: X%" y autoriza a decirlo (pedido Carlos: NO dar monto) | 10930 + 13040 | Sacar la inyección del % + regla dura: "nunca des un monto/porcentaje de coseguro; decí que se confirma en la clínica". Casos de banco YA generados |
| C3 | **Derivación fantasma en medios de pago**: "lo consulto con el equipo y te aviso" sin derivhumano | 13008 | derivhumano en el MISMO turno (coherencia palabra-acción) |
| C4 | **find_patient es tool inexistente** (no está en DENTAL_TOOLS) → loop/error al agendar para terceros | 11688 | Borrar el paso 4 (book_appointment ya resuelve por teléfono) |
| C5 | **Excepción (b) del gate**: si el paciente cita un monto, se confirma $60k aunque tenga OS | 12146(b) | Que surja la alternativa de OS igual que la excepción (e) |
| C6 | **Mirta con hueco**: mi fix exige que el paciente diga "mañana"; una emergencia que describe el cuadro sin pedir apuro podría recibir fecha lejana | 12292 | En EMERGENCY: derivar por fecha lejana aunque no lo pida explícito |

## 🟡 ROBUSTEZ — huecos de bajo riesgo

| # | Hueco | Dónde | Fix |
|---|---|---|---|
| R1 | REGLA GESTIÓN PREVIA vive DENTRO de bank_section → si el tenant no tiene banco, la regla desaparece (5 lugares la referencian) | 11583-601 / 12021 | Mover fuera de bank_section (bloque propio) |
| R2 | `{nombre}`/`{tratamiento}` con llaves literales en un string no-f → el modelo mini puede copiar "{nombre}" | 11664, 11667 | Cambiar a `[nombre]`/`[tratamiento]` (convención del resto) |
| R3 | Referencia obsoleta "BLOQUE 4" (la secuencia ahora es MENSAJE 1/2/3) | 12971 | "al final del BLOQUE 4" → "en la SECUENCIA POST-BOOKING (MENSAJE 2)" |
| R4 | Plantilla de precio con `{price_text}` vacío se inyecta aunque no haya precio → "…valor de . Ahí…" | 11824-32 | Envolver en `if price_text` |

## 💰 TOKENS — Lote 2 (recorte seguro ~3.500, alta confianza ~1.750)
- Flujos de reprogramación duplicados (12621-643 vs 13142-241) — ~600 tokens.
- Ejemplos de fecha duplicados (12659-712 vs 13149-186) — ~800 tokens.
- Restatement de seña opcional ×5-6 — ~350 tokens.
- Formato WhatsApp / CTA prohibidas / datos mínimos repetidos — ~900 tokens.
- ⚠️ NO tocar el prefijo cacheable (13305-08) ni el ancla de foco final (13319-25) — rompen el caché que descuenta 50%.

## ⚠️ APARTE — delicado, NO tocar sin Carlos
- "Síntoma normal → NO derivhumano" (12982): un post-op con sangrado 2 días podría descartarse como normal. Es seguridad médica — analizar con Carlos antes de tocar.
- Medicación con dosis (9970): canal controlado por config de la clínica; exposición de diseño, no bug.

## ORDEN DE EJECUCIÓN
1. **Lote A (comportamiento)**: C1-C6 + R1-R4 → verificar (compile + AST 28 tools) → 1 corrida de banco.
2. **Lote B (tokens)**: recortes alta confianza → 1 corrida de banco (mide ahorro).
3. Promoción curada a PROD (con OK de Carlos).
4. Comparar prompt PRUEBAS vs PROD (diff documentado).
