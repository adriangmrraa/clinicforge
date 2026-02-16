# Spec 10: UI Chat Preview (Anuncio)

## 1. Contexto y Objetivos
**Objetivo:** Dar contexto inmediato a la operadora humana cuando revisa un chat iniciado por publicidad.
**Problema:** El primer mensaje suele ser "Hola", sin indicar que el paciente vio una promo de "Implantes 50% OFF".

## 2. Requerimientos Técnicos

### Frontend (React)
- **Componente:** `MessageList.tsx`
- **Lógica:**
  - Verificar si la sesión tiene metadatos de `referral`.
  - Renderizar `AdContextCard` antes del primer mensaje.
- **Datos:** Imagen (si `source_url`), Headline, Body.

## 3. Criterios de Aceptación (Gherkin)

```gherkin
Scenario: Chat iniciado por anuncio
  Given conversación nueva con referral_data
  When se renderiza lista de mensajes
  Then aparece tarjeta de "Contexto de Anuncio" al inicio
```

## 4. UI/UX
- **Estilo:** Visualmente distinto a burbujas de chat.

## 5. Riesgos y Mitigación
- **Riesgo:** URLs de imagen rotas.
- **Mitigación:** Placeholder.

## 6. Compliance SDD v2.0
- **Diseño:** Componente reutilizable.
