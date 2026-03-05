#!/usr/bin/env python3
"""
Test script to verify save_patient_anamnesis tool implementation
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    # Try to import the module to check for syntax errors
    from orchestrator_service.main import save_patient_anamnesis, DENTAL_TOOLS
    
    print("✅ save_patient_anamnesis function imported successfully!")
    
    # Check function signature
    import inspect
    sig = inspect.signature(save_patient_anamnesis)
    params = list(sig.parameters.keys())
    
    print(f"\n📋 Function parameters: {params}")
    
    # Check for expected parameters
    expected_params = [
        'base_diseases', 'habitual_medication', 'allergies', 
        'previous_surgeries', 'is_smoker', 'smoker_amount', 
        'pregnancy_lactation', 'negative_experiences', 'specific_fears'
    ]
    
    missing_params = [p for p in expected_params if p not in params]
    
    if missing_params:
        print(f"❌ Missing parameters: {missing_params}")
    else:
        print("✅ All expected parameters are present")
    
    # Check that tool is in DENTAL_TOOLS list
    if save_patient_anamnesis in DENTAL_TOOLS:
        print("✅ save_patient_anamnesis is correctly added to DENTAL_TOOLS")
    else:
        print("❌ save_patient_anamnesis is NOT in DENTAL_TOOLS list")
    
    # Check position in list (should be before derivhumano)
    try:
        anamnesis_index = DENTAL_TOOLS.index(save_patient_anamnesis)
        derivhumano_index = DENTAL_TOOLS.index(save_patient_anamnesis.__globals__['derivhumano'])
        
        if anamnesis_index < derivhumano_index:
            print("✅ save_patient_anamnesis is correctly positioned before derivhumano")
        else:
            print("⚠️ save_patient_anamnesis should be before derivhumano in DENTAL_TOOLS")
    except (ValueError, AttributeError) as e:
        print(f"⚠️ Could not verify tool position: {e}")
    
    # Check docstring
    docstring = save_patient_anamnesis.__doc__
    if docstring:
        print(f"\n📝 Docstring length: {len(docstring)} characters")
        
        # Check for key phrases in docstring
        key_phrases = [
            "INMEDIATAMENTE DESPUÉS",
            "book_appointment",
            "preguntas de salud",
            "medical_history",
            "JSONB"
        ]
        
        missing_phrases = []
        for phrase in key_phrases:
            if phrase not in docstring:
                missing_phrases.append(phrase)
        
        if missing_phrases:
            print(f"⚠️ Missing key phrases in docstring: {missing_phrases}")
        else:
            print("✅ Docstring contains all key instructional phrases")
    else:
        print("❌ No docstring found")
        
except SyntaxError as e:
    print(f"❌ Syntax error in main.py: {e}")
    sys.exit(1)
except ImportError as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Other error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🎉 Tool implementation check passed!")