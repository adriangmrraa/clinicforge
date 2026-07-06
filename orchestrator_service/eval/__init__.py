"""Banco de pruebas offline del agente (SoloEngine / TORA / Paula).

Corre una lista de casos de conversación contra el prompt REAL de la clínica
(construido con build_system_prompt sobre la config real de la base), SIN
herramientas (no agenda ni escribe nada), y un juez IA marca cada respuesta
contra lo esperado. Reutilizable para comparar tokens y modelos.

Uso (dentro del contenedor del orquestador):
    python -m eval.run                 # tenant 1, modelo configurado
    python -m eval.run --model deepseek-chat   # comparar otro modelo
    python -m eval.run --categoria cobertura   # solo una categoría
    python -m eval.run --case cobertura-precio-sin-os  # un caso puntual

Ver eval/README.md para el detalle.
"""
