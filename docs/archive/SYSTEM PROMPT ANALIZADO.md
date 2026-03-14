Perfecto Adrián. He analizado exhaustivamente el System Prompt del Agente de IA de ClinicForge. Aquí tienes el análisis detallado y propuestas de mejora:

📊 ANÁLISIS DEL SYSTEM PROMPT ACTUAL

1. ESTRUCTURA Y FUNCIONAMIENTO

Ubicación: orchestrator_service/main.py → función build_system_prompt()
Inyección: Dinámica por cada invocación del agente LangChain

Componentes clave:

1. Regla de idioma (es/en/fr) - Obligatoria
2. Contextos adicionales (Meta Ads + Paciente)
3. Identidad - Dra. María Laura Delgado
4. Diccionario de sinónimos médicos (10 categorías)
5. Reglas de uso del diccionario (5 reglas)
6. Política de puntuación (sin ¿¡)
7. Optimización para WhatsApp (8 reglas)
8. Seguridad y restricciones
9. FAQs hardcodeadas (13 preguntas)
10. Ejemplos de conversación (2 diálogos)
11. Reglas de herramientas (check_availability, etc.)

2. TOOLS DISPONIBLES (11 HERRAMIENTAS)

DENTAL_TOOLS = [
    list_professionals,     # Lista profesionales activos
    list_services,          # Catálogo general (solo nombres)
    get_service_details,    # Detalle + imágenes automáticas
    check_availability,     # Disponibilidad real (local/Google)
    book_appointment,       # Reserva con validación datos
    list_my_appointments,   # Turnos del paciente
    cancel_appointment,     # Cancelación
    reschedule_appointment, # Reprogramación
    triage_urgency,         # Clasificación urgencia
    save_patient_anamnesis, # Guardado historial médico
    derivhumano             # Handoff a operador humano
]

3. MECANISMO DE ACTIVACIÓN DE TOOLS

Requisitos para activar cada tool:

| Tool                | Requisitos previos                                                                                | Edge Cases                                                           |
| ------------------- | ------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| check_availability  | 1. Servicio definido<br>2. Fecha consultada<br>3. (Opcional) Profesional                          | • Fecha pasada → error<br>• Profesional no existe → fallback general |
| book_appointment    | 1. Servicio + Fecha/Hora<br>2. Paciente nuevo: Nombre, Apellido, DNI<br>3. Paciente existente: ID | • DNI inválido → rechazo<br>• Colisión calendario → error            |
| get_service_details | 1. Código de servicio válido                                                                      | • Código no existe → lista alternativas                              |
| triage_urgency      | 1. Síntomas descritos                                                                             | • Síntomas ambiguos → clasificación conservadora                     |
| derivhumano         | 1. Razón justificada                                                                              | • Abuso → registro en logs                                           |

4. FORMATO DE RESPUESTAS Y DATOS

Estructura de respuesta del agente:

1. Saludo identitario (si primera interacción)
2. Confirmación de entendimiento
3. Ejecución de tool (si aplica)
4. Presentación de resultados
5. Pregunta/paso siguiente

Datos inyectados dinámicamente:

• ad_context: Contexto de Meta Ads (si aplica)
• patient_context: Datos paciente + turnos
• response_language: Idioma detectado (es/en/fr)
• clinic_name: Nombre clínica desde BD

5. EDGE CASES Y COMPORTAMIENTO ESPECIAL

Casos críticos manejados:

1. Intento de jailbreaking → Filtrado por detect_prompt_injection()
2. Paciente enojado → deri