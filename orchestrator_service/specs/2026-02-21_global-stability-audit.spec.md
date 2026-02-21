# Global Continuity & Stability Audit (Nexus v8.0)

## 1. Contexto y Objetivos
- **Problema:** La implementación del protocolo de endurecimiento de seguridad (Nexus v8.0) ha introducido regresiones sutiles pero críticas. Específicamente, el cambio de diccionarios a objetos Pydantic (`TokenData`) y las restricciones de tipado de `asyncpg` para intervalos SQL han roto páginas que funcionaban anteriormente.
- **Solución:** Realizar una auditoría sistemática y corrección ("Stabilization Sweep") en todos los archivos de rutas y servicios para asegurar compatibilidad total con el nuevo modelo de seguridad.
- **KPIs:** 
    - 0 errores `TypeError: 'TokenData' object is not subscriptable` en logs.
    - 0 errores de SQL relacionados con casting de intervalos de tiempo.
    - Todas las páginas críticas (Agendas, Pacientes, Finanzas) cargando datos correctamente.

## 2. Esquemas de Datos
- **Entradas:** Ninguna ( Auditoría de Código).
- **Salidas:** Reporte de archivos corregidos y verificación de estabilidad.
- **Persistencia:** No se requieren cambios en el esquema, solo en la forma en que se consultan los datos existentes (especialmente `created_at` y filtros de tiempo).

## 3. Lógica de Negocio (Invariantes)
- **Acceso a Usuario:** SI `user` es de tipo `TokenData`, ENTONCES usar `user.role` (NO `user["role"]`).
- **Intervalos SQL:** SI se usa un intervalo dinámico en `asyncpg`, ENTONCES debe pasarse como un objeto `timedelta` de Python (NO como string de Postgres).
- **Seguridad:** Mantener la validación de `X-Admin-Token` y `get_ceo_user_and_tenant` en todas las rutas administrativas.

## 4. Stack y Restricciones
- **Tecnología:** Python 3.10+, FastAPI, asyncpg, Pydantic v2.
- **Soberanía:** Se debe garantizar que las correcciones no rompan el aislamiento por `tenant_id`.

## 5. Criterios de Aceptación (Gherkin)
- **Escenario 1: Navegación sin errores**
  - DADO que el sistema tiene el nuevo protocolo de seguridad activo
  - CUANDO el usuario navega por las secciones de Pacientes, Agendas y Finanzas
  - ENTONCES las peticiones al backend deben retornar 200 OK y mostrar los datos correctos.

- **Escenario 2: Robustez de Consultas Temporales**
  - DADO una consulta que filtra por los últimos 30 días
  - CUANDO se ejecuta la ruta correspondiente
  - ENTONCES el backend debe procesar el intervalo correctamente sin errores de tipado en SQL.
