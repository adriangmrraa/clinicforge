import asyncio
import argparse
from db import db
from services.conversation_state import _normalize_phone_for_key, _get_redis_key
from services.relay import get_redis

async def clear_chat(phone: str):
    print(f"Buscando historial para el teléfono: {phone}")
    
    # 1. Connect to DB
    await db.connect()
    
    try:
        # Normalizar el teléfono
        phone_normalized = _normalize_phone_for_key(phone)
        
        # Obtener todos los tenants donde el paciente existe con este teléfono
        # para borrar el Redis state de todos ellos
        rows = await db.fetch("SELECT tenant_id FROM patients WHERE phone_number = $1", phone_normalized)
        tenant_ids = [r['tenant_id'] for r in rows]
        
        # 2. Borrar de Redis (conversation_state)
        r = get_redis()
        if r is not None:
            for tid in tenant_ids:
                key = _get_redis_key(tid, phone_normalized)
                await r.delete(key)
                print(f"✔️  Estado de conversación (Redis) borrado para tenant {tid}")
        else:
            print("⚠️  No se pudo conectar a Redis, omitiendo borrado de caché.")
            
        # 3. Borrar historial de mensajes
        # Las conversaciones tienen un ID que enlaza a los mensajes
        conversations = await db.fetch("SELECT id FROM chat_conversations WHERE patient_phone = $1", phone_normalized)
        conv_ids = [c['id'] for c in conversations]
        
        if conv_ids:
            # Borrar los mensajes dentro de la conversación
            await db.execute("DELETE FROM chat_messages WHERE conversation_id = ANY($1::int[])", conv_ids)
            # Borrar las conversaciones
            await db.execute("DELETE FROM chat_conversations WHERE id = ANY($1::int[])", conv_ids)
            print(f"✔️  Borrados los mensajes y conversaciones ({len(conv_ids)} conversaciones)")
        else:
            print("✔️  No se encontraron conversaciones de chat.")
            
        # 4. Borrar inbound_messages (YCloud webhooks logs)
        await db.execute("DELETE FROM inbound_messages WHERE from_number = $1 OR from_number = $2", phone_normalized, phone)
        print("✔️  Borrados los logs de webhooks entrantes.")
        
        # 5. Borrar whatsapp_messages (Outbound logs)
        await db.execute("DELETE FROM whatsapp_messages WHERE to_number = $1 OR to_number = $2", phone_normalized, phone)
        print("✔️  Borrados los logs de mensajes salientes.")

        # 6. Borrar patient_conversation_state (Estado persistente del agente, si existe)
        await db.execute("DELETE FROM patient_conversation_state WHERE phone_number = $1", phone_normalized)
        print("✔️  Borrado el contexto persistente del Agente.")
        
        # 7. Borrar Lead context y notas
        # A veces el summary de LLM se guarda en pacientes, lo limpiamos:
        for tid in tenant_ids:
            await db.execute("""
                UPDATE patients 
                SET context = NULL, 
                    frustration_level = 0,
                    system_tags = '[]'::jsonb
                WHERE phone_number = $1 AND tenant_id = $2
            """, phone_normalized, tid)
        print("✔️  Limpiado el contexto de IA en la tabla de pacientes.")
        
        print("\n✅ ¡Historial y estados vaciados con éxito! Tus turnos y tu registro de paciente están intactos.")

    finally:
        await db.disconnect()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Vaciar chat y estado de IA para un paciente (sin borrar el paciente ni turnos)")
    parser.add_argument("--phone", required=True, help="Número de teléfono del paciente (ej: 5492991234567)")
    args = parser.parse_args()
    
    asyncio.run(clear_chat(args.phone))
