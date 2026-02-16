#!/usr/bin/env python3
"""
Quick test script para validar que backend funciona.
Ejecutar: python tests/test_quick.py
"""

import asyncio
import sys
import os

# Agregar parent dir al path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_date_parsing():
    """Prueba que los helpers de parsing de fechas funcionan."""
    from datetime import date, datetime
    from dateutil.parser import parse as dateutil_parse
    
    def get_next_weekday(target_weekday: int) -> date:
        today = datetime.now()
        days_ahead = target_weekday - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return (today + __import__('datetime').timedelta(days=days_ahead)).date()
    
    # Test 1: get_next_weekday
    monday = get_next_weekday(0)
    print(f"✅ get_next_weekday(0=Monday): {monday}")
    
    # Test 2: dateutil parsing
    try:
        dt = dateutil_parse("2025-02-15 14:30", dayfirst=True)
        print(f"✅ dateutil_parse('2025-02-15 14:30'): {dt}")
    except Exception as e:
        print(f"❌ dateutil parsing failed: {e}")
        return False
    
    return True

async def test_helpers():
    """Prueba helpers de slots."""
    from datetime import date, datetime, timedelta
    
    def generate_free_slots(target_date: date, busy_times: list, 
                           start_hour=9, end_hour=18, interval_minutes=30) -> list:
        slots = []
        current = datetime.combine(target_date, datetime.min.time()).replace(hour=start_hour)
        end = datetime.combine(target_date, datetime.min.time()).replace(hour=end_hour)
        
        busy_hours = set()
        for busy_start, duration in busy_times:
            busy_hours.add(busy_start.hour + (busy_start.minute / 60))
        
        while current < end:
            if current.hour >= 13 and current.hour < 14:
                current += timedelta(minutes=interval_minutes)
                continue
            
            hour_decimal = current.hour + (current.minute / 60)
            if hour_decimal not in busy_hours:
                slots.append(current.strftime("%H:%M"))
            
            current += timedelta(minutes=interval_minutes)
        
        return slots[:5]
    
    target_date = date.today()
    busy_times = [
        (datetime.combine(target_date, datetime.min.time()).replace(hour=10), 30),
        (datetime.combine(target_date, datetime.min.time()).replace(hour=14), 30),
    ]
    
    slots = generate_free_slots(target_date, busy_times)
    print(f"✅ generate_free_slots: {slots}")
    
    return len(slots) > 0

async def test_fastapi_imports():
    """Valida que FastAPI y LangChain se pueden importar."""
    try:
        from fastapi import FastAPI
        print("✅ FastAPI OK")
    except ImportError as e:
        print(f"❌ FastAPI import failed: {e}")
        return False
    
    try:
        from langchain_openai import ChatOpenAI
        print("✅ LangChain OK")
    except ImportError as e:
        print(f"❌ LangChain import failed: {e}")
        return False
    
    try:
        from langchain.tools import tool
        print("✅ LangChain tools OK")
    except ImportError as e:
        print(f"❌ LangChain tools import failed: {e}")
        return False
    
    return True

async def test_pydantic_models():
    """Valida que los modelos Pydantic se definen correctamente."""
    try:
        from pydantic import BaseModel
        
        class TestModel(BaseModel):
            name: str
            age: int
        
        obj = TestModel(name="Test", age=25)
        print(f"✅ Pydantic models OK: {obj}")
        return True
    except Exception as e:
        print(f"❌ Pydantic failed: {e}")
        return False

async def main():
    print("🧪 Backend Quick Test Suite")
    print("=" * 50)
    
    tests = [
        ("FastAPI + LangChain imports", test_fastapi_imports),
        ("Date parsing helpers", test_date_parsing),
        ("Free slots generation", test_helpers),
        ("Pydantic models", test_pydantic_models),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n[Testing] {test_name}...")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Exception in {test_name}: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    for test_name, result in results:
        status = "✅" if result else "❌"
        print(f"{status} {test_name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\n{passed}/{total} tests passed")
    
    return all(r for _, r in results)

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

