# 🧪 Matriz de Decisión de Skills (Laboratorio de Capacidades)

Este documento define el razonamiento algorítmico que el Agente Antigravity utiliza para seleccionar especialistas y descomponer problemas complejos.

---

### 1. Mapeo de Contexto a Combinación de Skills

Para problemas que trascienden un solo archivo, se deben combinar las siguientes capacidades v8.0:

| Problema Complejo | Skill Primaria | Skill de Soporte | Objetivo del Duo |
| :--- | :--- | :--- | :--- |
| **Latencia en Agenda / GCal** | `Backend_Sovereign` | `Skill_Sync` | Optimizar lógica JIT v2 y asegurar que las tools estén sincronizadas. |
| **Refactorización UI Mobile** | `Nexus_UI_Architect` | `Frontend_Nexus` | Aplicar Blueprint Universal + Implementación de hooks. |
| **Inconsistencia de Datos** | `DB_Evolution` | `Sovereign_Auditor` | Ejecutar parche idempotente + Auditoría de `tenant_id`. |
| **Nueva Feature Completa** | `Spec_Architect` | `Skill_Forge_Master` | Generar SSOT (SDD) + Crear nuevas capacidades si es necesario. |
| **Falla en Notificaciones** | `Backend_Sovereign` | `Omnichannel_Operator` | Verificar orquestador + Debugging de ráfagas en WhatsApp. |

---

### 2. Protocolo de Análisis Pre-Vuelo (Atomicidad vs Descomposición)

Antes de ejecutar cualquier cambio, el agente debe completar este checklist mental para decidir el uso de `/tasks`:

- [ ] **Volumen**: ¿El cambio afecta a más de 3 archivos core (`main.py`, `db.py`, `App.tsx`)?
- [ ] **Dependencia**: ¿La lógica de la Parte B requiere que la Parte A esté persistida en DB?
- [ ] **Riesgo**: ¿Es un cambio en `auth_routes.py` o en la validación del `tenant_id`?
- [ ] **Confianza**: ¿La ruta técnica está validada al 100% en la fase `/gate`?

**Regla de Decisión**:
- Si >2 checks son positivos → **OBLIGATORIO** usar `/tasks` y descomponer en tickets atómicos.
- Si <2 checks son positivos → Se permite `/implement` directo con checkpoints de `task.md`.

---

### 3. Gestión de Skills v8.0 (Preferencias de Arquitectura)

Para cualquier refactorización, las habilidades v8.0 tienen prioridad absoluta sobre patrones legacy:

#### 3.1 Preferencia UI (Adaptive & Isolated)
- **Patrón**: Siempre favorecer `Isolation de Scroll` y `DKG` (Dato Clave de Gestión).
- **Acción**: Si una vista es plana, proponer el toggle de "Vista Estratégica" mediante la skill de `Nexus_UI_Architect`.

#### 3.2 Preferencia Backend (JIT & Idempotent)
- **Patrón**: Sincronización Just-In-Time v2 para servicios externos.
- **Acción**: Cualquier inserción en DB debe nacer como un parche en el **Evolution Pipeline**, nunca como un comando SQL aislado.

---

### 4. Evaluación de Confianza Técnica
- **Confianza > 80%**: Se procede al `/gate` de implementación.
- **Confianza 70% - 80%**: Se requiere un `/review` de diseño antes de codear.
- **Confianza < 70%**: Parada técnica. Se dispara el workflow `/clarify`.

---
*Matriz de Decisión Nexus v8.0 - Antigravity Brain Context*
