# PLAN DE LA SEMANA — dejar todo listo (2026-07-12)

## Modo de trabajo (nuevo, pedido de Carlos)
- **Yo manejo y decido.** No espero indicaciones para avanzar en PRUEBAS.
- **Validación en LOTES**: UNA sola corrida de banco por lote (no run-and-paste por cada cambio → se acaba el bucle y el gasto de tokens en pruebas inútiles).
- **PROD**: solo con OK explícito de Carlos.
- **Anti errores burdos**: verifico esquema/módulo/columna ANTES de escribir queries; commits con `-F archivo` (no here-strings de PowerShell); python/git por PowerShell (Bash perdió coreutils).

---

## LOTE 1 — AGENTE: urgencia + OS + coseguro + tokens (a PROD esta semana)
| Ítem | Estado |
|---|---|
| Fix Mirta (urgencia con turno lejano → DERIVA, no ofrece +9 días) | ✅ en pruebas (`12b112a`) |
| Semáforo OS (ofrece +N días, amable aunque insistan; particular prioridad) | ✅ funciona (confirmado en banco) |
| Coseguro híbrido ("suele ser $30.000, se confirma en la clínica") | 🔧 decidido, implementar en el batch |
| **Token r2 #1**: RAG deja de volcar 20 FAQs cuando no matchea | ✅ en pruebas |
| Recalibración banco os-demora (OSDE=30, no 40) | ✅ en pruebas (`db68178`) |

**Validación**: UNA corrida de banco completa → mide tokens antes/después + confirma 0 regresiones.
**→ PROD** con: la **tabla de 17 OS** de Carlos (para configurar) + su OK.

## LOTE 2 — GLOBOS + más tokens (esta semana)
- Consolidación de globos r2: reglas para juntar burbujas (menos mensajes salientes = menos $ Meta desde 1-oct).
- Auditoría del prompt: cortar grasa (PROHIBIDOs duplicados, secciones verbosas repetidas).
- **Validación**: una corrida de banco (tokens + regresiones).

## LOTE 3 — MÓDULOS a PROD (Carlos valida visual)
- Liquidaciones (motor + PDF administrador + historial + cobro en mostrador).
- Laboratorio (necesito **lista de labs** + **plantilla WhatsApp** aprobada).

---

## Lo que necesito de Carlos (3 datos — destraban todo, sin esto me quedo en pruebas)
1. **Tabla de las 17 OS** con días de demora (OSDE 30 ✓, Galeno 15 ✓, faltan las otras 15).
2. **Lista de laboratorios** (nombre + mail/teléfono).
3. **Plantilla de WhatsApp** aprobada en Meta (para los avisos de laboratorio fuera de ventana 24h).

## Métrica de éxito
- Agente en PROD: urgencia deriva bien + semáforo OS con las 17 cargadas + menos tokens/mensaje medido en el banco.
- Módulos (liquidaciones + laboratorio) en PROD validados por la Dra.
- Base lista para la consolidación de globos antes del 1-oct (Meta).
