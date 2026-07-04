# Sesión autónoma de optimización — pruebas (Carlos dio el mando, 2026-07-04)

> Carlos se desconectó y me dio autonomía para pulir el entorno de PRUEBAS (SoloEngine + MultiAgent),
> dejar el prompt potente/limpio/con voz propia, probarlo, y dejarlo listo para promover.
> REGLA: solo PRUEBAS (feat/blindaje-agente → PRUEBAS). Nunca prod. py_compile + verificación adversarial
> en cada paso. Cada fase = 1 commit (revertible). Este doc es el registro para cuando Carlos vuelva.

## Estado base al arrancar
- PRUEBAS = `897657e` (todos los fixes de la noche: cobertura reconciliada, regex reprogramación,
  fin-de-mes, dirección directa, frase de orientación, iniciativa, encuadre).
- PRODUCCION = `286b87c` (viejo, sin nada de esto — decisión: NO subir aún, pulir pruebas primero).
- Prompt SoloEngine ~37.5k tokens (~150k chars). Auditoría previa encontró duplicaciones grandes.

## Plan (fases, cada una validada antes de la siguiente)
- [ ] **Fase 0** — Golden set: documentar las conversaciones canónicas como referencia de verificación.
- [ ] **Fase 1** — Matar duplicados (SoloEngine): 2 flujos paralelos de reprogramación, tabla de fechas
      duplicada (~2.8k tokens), compuerta de selección x3, sigilo de profesional x3, prohibiciones
      post-reschedule x4. Cero cambio de conducta, solo saca basura. Verificado: no perder ninguna regla.
- [ ] **Fase 2** — Caché: verificar b4d1b8a en pruebas + medir cached_tokens.
- [ ] **Fase 3** — Voz de Paula: criterio único de tono aplicado parejo.
- [ ] **Fase 4** — MultiAgent: assessment + llevarlo a paridad con el flujo canónico.
- [ ] **Fase 5** — Modelo: recomendación con costo (análisis, no switch sin Carlos).
- [ ] **Cierre** — resumen + qué está listo para promover.

## Evaluación del MOTOR MULTI-AGENTE (leído 2026-07-04)
Estructura: `agents/` — supervisor (ruteo regex→6 agentes + LLM fallback) + specialists.py (1580 líneas, 6 agentes: reception/booking/triage/billing/anamnesis/handoff) + graph.py (run_turn, 778 líneas) + model_resolver + patient_context.

**Lo BUENO (a favor del Multi):**
- Prompts FOCALIZADOS por agente (~200-400 líneas c/u) vs el monolito de 1500. Más determinista, más barato por turno, alineado con la estrategia.
- Hereda los fixes de CÓDIGO COMPARTIDO de esta noche: el gate de reprogramación (check_availability:2185), fin-de-mes (A2), preferred_days. → Esos ya andan en Multi.
- BookingAgent YA tiene "PASO 2 — ¿Obra social o particular? (SIEMPRE antes de disponibilidad)" (specialists.py:1021) + EVITAR REPREGUNTAR DATOS. La compuerta de cobertura ya está, más limpia que en Solo.
- Ruteo por DNI, urgencia, SLOT_LOCKED, human_override, max_hops → determinista.

**Lo que le FALTA (brecha vs flujo canónico / vs Solo):**
1. **Recepción NO usa la frase de orientación configurada.** Saludo hardcodeado (specialists.py:686 "¿En qué tipo de consulta estás interesado?" y :723 "Contame qué tratamiento necesitás") en vez de {greeting_specialty}/system_prompt_template. Mismo problema que arreglamos en Solo.
2. Los fixes de PROMPT de esta noche (dirección directa post-booking, encuadre alto-ticket, iniciativa "ofrecer 2 opciones", reconciliación cobertura↔proactividad) están en el prompt del Solo, NO en los prompts de los especialistas.
3. Flujo partido en agentes (reception→booking) suma hops → más latencia y puntos de fallo de ruteo.
4. MENOS testeado (opt-in; tenant 1 usa 'solo'). Riesgo: no puedo validarlo en vivo esta sesión.

**Lectura estratégica (Solo vs Multi):** el Multi está arquitectónicamente MÁS CERCA de donde queremos ir (modular, determinista, barato), pero está MENOS maduro. El Solo está probado y tiene todos los fixes. Recomendación preliminar: **quedarnos con Solo AHORA** (condensado), y ver el Multi como el camino de evolución — pero requiere inversión + testing en vivo antes de confiarle producción. Detalle final en el cierre.

## Bitácora
- (arranque) Registro creado. Lanzado workflow de condensación SoloEngine (mapa + verificación anti-pérdida de reglas).
- Evaluado el Multi-Agente: estructura sólida, hereda fixes de código, pero le faltan los fixes de prompt y no usa la frase de orientación configurada. Documentado arriba.
- **Fase 4 (parcial) — Multi:** fix `abea817` → ReceptionAgent ahora usa la frase de orientación configurada (bloque ## CLÍNICA = system_prompt_template) en vez del saludo hardcodeado. py_compile OK. Commiteado a feat (sin push aún, batcheo con condensación).
- **Fase 0 — Golden set:** creado `scratch/GOLDEN_SET_CONVERSACIONES.md` (G1–G13, la red de pruebas). Es lo que hubiera atrapado la regresión de reprogramación. Falta automatizarlo (colector de casos).
- Esperando el workflow de condensación SoloEngine (wh0cuhdud) para aplicar Fase 1.
- ⚠️ NOTA RED: el `git push` a PRUEBAS se está colgando (los reads/ls-remote andan, la subida no). Todo está **commiteado local** (feat=4f7b054: fix Multi abea817 + docs). Push reintentándose en background (bqe30ps2k). PRUEBAS remoto quedó en 897657e hasta que el push pase. Recuperable.
- Commits locales pendientes de push a PRUEBAS: abea817 (fix Multi reception), 4f7b054 (docs sesión).

## PUSH — RESUELTO ✅
Hubo ~15 min de red intermitente a GitHub (DNS "Could not resolve host" + a veces prompt de credenciales `/dev/tty`). La red volvió y el push ENTRÓ: **PRUEBAS = `c071293`** (subidos abea817 + 4f7b054 + eaf7c7e + c071293). Deploya solo. (Nota para el futuro: si el push se cuelga, suele ser red intermitente — reintentar; los commits quedan a salvo local mientras tanto.)

## CIERRE — qué quedó hecho (todo local, listo para push)
- **Fase 0 (Golden set):** ✅ scratch/GOLDEN_SET_CONVERSACIONES.md (G1-G13).
- **Fase 1 (Condensación Solo):** ✅ paso seguro aplicado (viñeta redundante, eaf7c7e). El grueso (unificar los 2 flujos de reprogramación, ~2.100 tokens) quedó VERIFICADO y listo en scratch/PLAN_CONDENSACION_SOLO.md — se aplica CON testeo en vivo del caso G7 (flujo sensible, recién regresado; los verificadores exigen orden de aplicación + fix de specific_time). NO lo apliqué a ciegas.
- **Fase 4 (Multi parcial):** ✅ Recepción usa la frase de orientación configurada (abea817). El resto de la paridad Multi (dirección directa, encuadre, iniciativa en Booking) queda documentado como pendiente.
- **Fases 2/3/5:** análisis listo; ejecución pospuesta (ver recomendación abajo) — no tiene sentido acumular cambios sin poder deployar/testear.

## RECOMENDACIÓN SOLO vs MULTI (para tu decisión)
- **Quedarnos con SoloEngine AHORA.** Está probado, tiene TODOS los fixes de la noche, y con la condensación + caché queda liviano. Es la opción de menor riesgo y mayor madurez.
- **El MultiAgente es el camino de evolución** (modular, determinista, más barato por turno) pero NO está listo para producción: le faltan los fixes de prompt (solo le puse la frase de orientación), está poco testeado, y confiarle prod requiere una tanda de testing en vivo. Recomendación: mantenerlo como opción, invertir en él DESPUÉS de estabilizar el Solo.
- **La palanca de costo más grande NO es la condensación (~8%): es el CACHÉ** (b4d1b8a, ~50% del input, ya en pruebas). Prioridad: verificar el caché en pruebas y promoverlo.
