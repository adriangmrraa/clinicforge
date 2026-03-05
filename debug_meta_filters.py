#!/usr/bin/env python3
"""
Script para diagnosticar por qué los filtros de tiempo no funcionan en Meta Ads.
"""

import asyncio
import sys
import os

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_meta_presets():
    """Testear diferentes date_preset values para ver cuáles funcionan."""
    
    # Simular los valores que estamos usando
    test_cases = [
        ("last_30d", "last_30d"),
        ("last_90d", "last_90d"), 
        ("this_year", "this_year"),
        ("lifetime", "maximum"),
        ("all", "maximum")
    ]
    
    print("🔍 Test de date_preset values para Meta API")
    print("=" * 60)
    
    for frontend_value, meta_preset in test_cases:
        print(f"\n📊 Frontend: '{frontend_value}' → Meta: '{meta_preset}'")
        
        # Verificar si el valor es válido según documentación de Meta
        valid_presets = [
            "today", "yesterday", "this_month", "last_month", 
            "this_quarter", "last_quarter", "this_year", "last_year",
            "maximum", "last_3d", "last_7d", "last_14d", "last_28d",
            "last_30d", "last_90d", "last_week_mon_sun", "last_week_sun_sat"
        ]
        
        if meta_preset in valid_presets:
            print(f"   ✅ Preset válido según documentación Meta")
        else:
            print(f"   ⚠️  Preset NO está en lista de valores válidos conocidos")
    
    print("\n" + "=" * 60)
    print("🎯 Recomendaciones:")
    print("1. Verificar logs del backend después del deploy")
    print("2. Probar cada filtro individualmente")
    print("3. Si sigue sin funcionar, considerar usar time_range con fechas específicas")
    print("4. Verificar que haya datos en los períodos seleccionados")

async def check_data_availability():
    """Verificar si hay datos en diferentes períodos de tiempo."""
    print("\n📅 Análisis de disponibilidad de datos por período:")
    print("=" * 60)
    
    # Preguntas clave para diagnóstico
    questions = [
        "1. ¿Las campañas de Meta están activas actualmente o son antiguas?",
        "2. ¿Hay gasto registrado en los últimos 30 días en Meta Ads Manager?",
        "3. ¿Los pacientes en ClinicForge tienen fechas de creación recientes?",
        "4. ¿Las columnas meta_campaign_id y meta_ad_id están pobladas en pacientes?",
        "5. ¿Hay citas/transacciones en los últimos 30/90 días?"
    ]
    
    for q in questions:
        print(f"   {q}")
    
    print("\n🔧 Comandos SQL para diagnóstico:")
    print("""
    -- Ver pacientes con atribución Meta en últimos 30 días
    SELECT COUNT(*) as total, 
           COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '30 days') as last_30d,
           COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '90 days') as last_90d,
           COUNT(*) FILTER (WHERE EXTRACT(YEAR FROM created_at) = EXTRACT(YEAR FROM NOW())) as this_year
    FROM patients 
    WHERE acquisition_source = 'META_ADS' AND meta_campaign_id IS NOT NULL;
    
    -- Ver campañas con gasto reciente
    SELECT meta_campaign_id, COUNT(*) as leads, 
           MIN(created_at) as first_lead, MAX(created_at) as last_lead
    FROM patients 
    WHERE acquisition_source = 'META_ADS' AND meta_campaign_id IS NOT NULL
    GROUP BY meta_campaign_id
    ORDER BY last_lead DESC;
    """)

if __name__ == "__main__":
    print("🚀 DIAGNÓSTICO DE FILTROS META ADS")
    print("=" * 60)
    
    asyncio.run(test_meta_presets())
    asyncio.run(check_data_availability())
    
    print("\n" + "=" * 60)
    print("📋 PASOS RECOMENDADOS:")
    print("1. Esperar a que el deploy termine (revertimos cambios problemáticos)")
    print("2. Verificar que 'All' vuelva a funcionar")
    print("3. Revisar logs del backend para ver qué datos se obtienen")
    print("4. Ejecutar queries SQL de diagnóstico si es necesario")
    print("5. Contactarme para implementar solución incremental")