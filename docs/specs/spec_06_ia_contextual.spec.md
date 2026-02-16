# Spec 06: IA Contextual y Triaje

## 1. Contexto y Objetivos
**Objetivo:** Que el asistente IA reconozca el contexto del anuncio y adapte su comportamiento.
**Problema:** Si el paciente viene de un anuncio de "Urgencia Dolor", el bot no debe tratarlo como lead genérico.

## 2. Requerimientos Técnicos

### Backend (System Prompt)
- **Archivo:** `orchestrator_service/main.py` -> `build_system_prompt`
- **Lógica:**
  - Leer `meta_ad_headline` del paciente/sesión.
  - Si contiene keywords ["Urgencia", "Dolor", "Emergencia", "Trauma"]:
    - Inyectar instrucción prioritaria de triaje clínico.

### Backend (Tool Triage)
- **Tool:** `triage_urgency`
- **Modificación:**
  - Registrar coincidencia entre urgencia detectada y origen del anuncio (`ad_intent_match`).

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Prompt dinámico por urgencia
  Given paciente de anuncio "Urgencia 24hs"
  When se construye el system prompt
  Then incluye directiva de prioridad clínica

Scenario: Registro de Match Quality
  Given paciente de anuncio de urgencia
  When tool 'triage_urgency' confirma dolor
  Then registra 'ad_intent_match = True'
```

## 4. Esquema de Datos

Métrica en logs o metadatos de sesión.

## 5. Riesgos y Mitigación
- **Riesgo:** Alucinación de IA.
- **Mitigación:** Reglas estrictas en prompt base.

## 6. Compliance SDD v2.0
- **Seguridad:** Prompt injection protection estándar.
