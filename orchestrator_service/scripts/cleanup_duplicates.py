
import asyncio
import os
import sys
from typing import List

# Añadir el path actual para poder importar db
sys.path.append(os.getcwd())

async def cleanup_duplicates():
    print("🚀 Iniciando limpieza de duplicados (Spec 31)...")
    from db import db
    
    # 1. Encontrar grupos duplicados por (tenant_id, channel, display_name)
    # Solo para instagram y facebook donde los IDs técnicos variaron
    duplicates = await db.pool.fetch("""
        SELECT tenant_id, channel, LOWER(TRIM(display_name)) as name, COUNT(*), ARRAY_AGG(id ORDER BY last_message_at DESC) as id_list
        FROM chat_conversations
        WHERE channel IN ('instagram', 'facebook') AND display_name IS NOT NULL AND display_name != ''
        GROUP BY tenant_id, channel, name
        HAVING COUNT(*) > 1
    """)
    
    if not duplicates:
        print("✅ No se encontraron duplicados evidentes por nombre en la base de datos.")
        return

    print(f"🔍 Encontrados {len(duplicates)} grupos de duplicados.")
    
    for group in duplicates:
        ids = group['id_list']
        canonical_id = ids[0]
        duplicates_to_merge = ids[1:]
        
        print(f"📦 Procesando: {group['name']} ({group['channel']})")
        print(f"   - Principal: {canonical_id}")
        print(f"   - A fusionar: {duplicates_to_merge}")
        
        for dup_id in duplicates_to_merge:
            # Transferir mensajes
            try:
                res = await db.pool.execute(
                    "UPDATE chat_messages SET conversation_id = $1 WHERE conversation_id = $2",
                    canonical_id, dup_id
                )
                print(f"   ✅ Mensajes movidos de {dup_id}: {res}")
                
                # Eliminar conversación duplicada huérfana
                await db.pool.execute("DELETE FROM chat_conversations WHERE id = $1", dup_id)
                print(f"   🗑️ Conversación eliminada: {dup_id}")
            except Exception as e:
                print(f"   ❌ Error moviendo {dup_id}: {e}")

    print("\n✨ Limpieza completada.")

if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())
