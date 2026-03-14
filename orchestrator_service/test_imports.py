#!/usr/bin/env python3
"""
Script para verificar que todas las importaciones del sistema mejorado funcionan
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== TEST DE IMPORTACIONES DEL SISTEMA MEJORADO ===\n")

# Test 1: Módulos del agente
print("1. Probando módulos del agente...")
try:
    from agent.prompt_builder import SYSTEM_PROMPT_MODULES
    print("   ✅ agent.prompt_builder - OK")
except ImportError as e:
    print(f"   ❌ agent.prompt_builder - ERROR: {e}")

try:
    from agent.validators import validate_before_tool
    print("   ✅ agent.validators - OK")
except ImportError as e:
    print(f"   ❌ agent.validators - ERROR: {e}")

try:
    from agent.context_memory import memory_manager
    print("   ✅ agent.context_memory - OK")
except ImportError as e:
    print(f"   ❌ agent.context_memory - ERROR: {e}")

try:
    from agent.fallback_handler import fallback_handler
    print("   ✅ agent.fallback_handler - OK")
except ImportError as e:
    print(f"   ❌ agent.fallback_handler - ERROR: {e}")

try:
    from agent.metrics_tracker import metrics_tracker
    print("   ✅ agent.metrics_tracker - OK")
except ImportError as e:
    print(f"   ❌ agent.metrics_tracker - ERROR: {e}")

try:
    from agent.integration import enhanced_system
    print("   ✅ agent.integration - OK")
except ImportError as e:
    print(f"   ❌ agent.integration - ERROR: {e}")

# Test 2: Módulos de guardrails
print("\n2. Probando módulos de guardrails...")
try:
    from guardrails.injection_detector import enhanced_guardrails
    print("   ✅ guardrails.injection_detector - OK")
except ImportError as e:
    print(f"   ❌ guardrails.injection_detector - ERROR: {e}")

# Test 3: Módulos de experiments
print("\n3. Probando módulos de experiments...")
try:
    from experiments.ab_testing import PromptExperiment
    print("   ✅ experiments.ab_testing - OK")
except ImportError as e:
    print(f"   ❌ experiments.ab_testing - ERROR: {e}")

# Test 4: Funciones principales del sistema
print("\n4. Probando funciones principales...")
try:
    # Simular contexto para build_system_prompt
    context = {
        "clinic_name": "Clínica Test",
        "response_language": "es",
        "ad_context": "",
        "patient_context": "",
        "current_time": "2026-03-14 20:00:00",
        "hours_start": "08:00",
        "hours_end": "19:00",
        "is_first_interaction": True,
        "channel": "whatsapp",
        "conversation_active": False,
        "faq_triggered": False,
        "asks_location": False
    }
    
    from agent.integration import enhanced_system
    import asyncio
    
    async def test_prompt():
        prompt = await enhanced_system.build_optimized_prompt(context)
        return len(prompt)
    
    prompt_length = asyncio.run(test_prompt())
    print(f"   ✅ Sistema completo - OK (prompt length: {prompt_length} chars)")
    
except Exception as e:
    print(f"   ❌ Sistema completo - ERROR: {e}")

print("\n=== TEST COMPLETADO ===")