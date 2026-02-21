# spec_security_proactive_hardening.spec.md - Nexus Hardening v2.0

## 1. Objetivos
Elevar la postura de seguridad de ClinicForge implementando defensas proactivas contra ataques de cabeceras, inyección en agentes de IA y asegurando la integridad del DOM en el frontend.

## 2. Componentes Técnicos

### 2.1 Cabeceras de Seguridad Proactivas (Backend)
Implementar un middleware de seguridad en `orchestrator_service/main.py` que inyecte:
- **Content-Security-Policy (CSP)**: Restringir a `'self'` y dominios de confianza (OpenAI, Meta).
- **X-Frame-Options**: `DENY` para evitar clickjacking.
- **X-Content-Type-Options**: `nosniff`.
- **Strict-Transport-Security (HSTS)**: Forzar HTTPS (6 meses duration).

### 2.2 AI Guardrails (Orchestration Layer)
Reforzar `orchestrator_service/main.py` (o un módulo de validación) para:
- **Validación de Salida**: Antes de ejecutar cualquier `tool` (ej: `book_appointment`), validar que los parámetros cumplan con el esquema esperado (ej: DNI solo números, fecha futura).
- **Prompt Injection Basic**: Implementar un filtro de keywords/instrucciones prohibidas en el input del usuario (ej: "ignore previous instructions").

### 2.3 Sanitización Frontend
Integrar **DOMPurify** en `frontend_react` para procesar cualquier contenido dinámico renderizado fuera de las protecciones estándar de React.

### 2.4 Hito Futuro: SaaS Readiness (Diferido)
> [!NOTE]
> La migración a **SQLAlchemy 2.0** y **Alembic** se reserva para la fase de transición a **SaaS (Multi-tenant escalable)**. 
> Actualmente, el sistema utiliza un pool de conexiones directo (`asyncpg`) que es eficiente para el volumen actual.

## 3. Clarificaciones (Security Deep Dive v2.0)
- **CSP Dinámico**: Los dominios permitidos se cargarán desde `CORS_ALLOWED_ORIGINS` y variables específicas de CSP en `.env`.
- **Defensa Híbrida de IA**: Se implementará un `PromptSecurityMiddleware` que filtre patrones de ataque (Blacklist) antes de invocar al LLM. Se reforzará el `System Message` como segunda capa.
- **Sanitización Obligatoria**: `DOMPurify` será parte del bundle de frontend para cualquier renderizado dinámico.
- **Redundancia HSTS**: Se inyectará en FastAPI independientemente del Proxy de EasyPanel.
- **Validación Estricta**: Las tools devolverán excepciones estructuradas ante datos inválidos para que la IA pida correcciones explícitas al paciente.

## 4. Criterios de Aceptación
1. `curl -I` muestra cabeceras configuradas dinámicamente.
2. Patrones de "Ignore instructions" son detectados y bloqueados por el middleware.
3. El frontend rechaza scripts inyectados en áreas de contenido dinámico.
4. El agente pide corrección de DNI si la validación técnica falla.
