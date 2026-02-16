# Spec 08: UI Patient Detail (Origen de Lead)

## 1. Contexto y Objetivos
**Objetivo:** Mostrar origen del paciente en su ficha.
**Problema:** Operadores desconocen si el paciente viene de promo.

## 2. Requerimientos Técnicos

### Frontend (React)
- **Componente:** `PatientDetail.tsx` (Info Section).
- **UI:** Badge "Meta Ads" con Tooltip mostrando Campaña/Anuncio.
- **Lógica:** Render condicional si `acquisition_source == 'META_ADS'`.

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Visualización origen Meta
  Given paciente con source META_ADS
  When se ve el detalle
  Then badge visible con info de campaña
```

## 4. UI/UX
- **Estilo:** Consistente con Nexus UI (Tailwind).

## 5. Riesgos y Mitigación
- **Riesgo:** Nombres de campaña largos.
- **Mitigación:** Truncate visual.

## 6. Compliance SDD v2.0
- **Scroll Isolation:** Contenido interno, safe.
