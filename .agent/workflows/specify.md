---
description: Genera una especificación técnica (.spec.md) rigurosa a partir de requerimientos vagos, usando análisis de 3 pilares.
---

# 📝 Specify Workflow - Dentalogic

Transforma requerimientos vagos en una especificación técnica rigurosa.

1.  **Entrevista Técnica**:
    - Definir Entradas de Datos (ej: Datos del paciente, fechas).
    - Definir Salidas (ej: Cita en GCal, Mensaje de confirmación).
2.  **Generación de `.spec.md`**:
    - Estructura: Objetivos, Esquema de Datos, Lógica "Gala", Criterios de Aceptación.
3.  **Soberanía de Datos**:
    - Validar que se cumplan las reglas de aislamiento multi-tenant.
4.  **REGLA DE ORO DE EJECUCIÓN**:
    - NO ejecutar comandos SQL (`psql`) directamente. Proporcionar el comando al usuario y esperar sus resultados.
