#!/usr/bin/env python3
"""
Test script to verify book_appointment function syntax
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

try:
    # Try to import the module to check for syntax errors
    from orchestrator_service.main import book_appointment
    
    print("✅ book_appointment function imported successfully!")
    
    # Check function signature
    import inspect
    sig = inspect.signature(book_appointment)
    params = list(sig.parameters.keys())
    
    print(f"\n📋 Function parameters: {params}")
    
    # Check for required new parameters
    expected_params = ['date_time', 'treatment_reason', 'first_name', 'last_name', 
                      'dni', 'birth_date', 'email', 'city', 'acquisition_source', 'professional_name']
    
    missing_params = [p for p in expected_params if p not in params]
    
    if missing_params:
        print(f"❌ Missing parameters: {missing_params}")
    else:
        print("✅ All expected parameters are present")
        
    # Check that insurance_provider is not present
    if 'insurance_provider' in params:
        print("❌ insurance_provider parameter should have been removed")
    else:
        print("✅ insurance_provider parameter correctly removed")
        
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

print("\n🎉 Syntax check passed!")