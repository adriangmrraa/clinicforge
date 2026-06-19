import asyncio
import os
from db import db
# Importamos la función que acabamos de agregar
from main import resolve_canonical_treatment

async def test_synonyms():
    await db.connect()
    if not db.pool:
        print("No se pudo conectar a la base de datos.")
        return

    # Usaremos el tenant 1 de prueba
    tenant_id = 1
    
    test_terms = [
        "extracción de muelas",
        "extraccion de muelas",
        "sacar muela",
        "limpieza de sarro",
        "limpieza dental",
        "consulta urgente",
        "Consulta General",
        "ortodoncia brackets",
        "tratamiento inexistente"
    ]
    
    print("=== PROBANDO RESOLUCIÓN DE SINÓNIMOS ===")
    for term in test_terms:
        result = await resolve_canonical_treatment(tenant_id, term)
        if result:
            print(f"✔️ Término: '{term}' -> Resuelto a: '{result['name']}' (Código: {result['code']})")
        else:
            print(f"❌ Término: '{term}' -> No se pudo resolver.")
            
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_synonyms())
