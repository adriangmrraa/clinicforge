import asyncio
import os
import json
import asyncpg
from datetime import datetime

POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://postgres:Wstg1793.@localhost:5432/clinicforge_test")

async def run_diag():
    dsn = POSTGRES_DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(dsn)
    
    phones = ['5493464553032', '5491137973901', '5492994068005', '5492996724351']
    
    print("==================================================")
    print("CONVERSATION STATE AND CHAT LOGS DIAGNOSTIC")
    print("==================================================")
    
    for phone in phones:
        print(f"\nChecking phone/user: {phone}")
        
        # 1. State of patient in chat_conversations table
        state_row = await conn.fetchrow("""
            SELECT id, tenant_id, external_user_id, channel, human_override_until FROM chat_conversations 
            WHERE external_user_id ILIKE $1 
            LIMIT 1
        """, f"%{phone}%")
        
        if state_row:
            print(f"Conversation Row: {dict(state_row)}")
        else:
            print("No conversation found in chat_conversations.")
            
        # 2. Patient details
        patient_row = await conn.fetchrow("""
            SELECT id, first_name, last_name, assigned_professional_id, human_handoff_requested, human_override_until, last_derivhumano_at
            FROM patients
            WHERE phone_number ILIKE $1
            LIMIT 1
        """, f"%{phone}%")
        if patient_row:
            print(f"Patient Row: {dict(patient_row)}")
        else:
            print("No patient record found.")
            
        # 3. Recent Chat Messages
        messages = await conn.fetch("""
            SELECT cm.id, cm.role, cm.content, cm.created_at
            FROM chat_messages cm
            JOIN chat_conversations cc ON cc.id = cm.conversation_id
            WHERE cc.external_user_id ILIKE $1 OR cc.external_user_id ILIKE $2
            ORDER BY cm.created_at DESC
            LIMIT 15
        """, f"%{phone}%", f"+{phone}")
        
        print("Recent Messages (most recent first):")
        for m in messages:
            print(f"  [{m['created_at'].strftime('%Y-%m-%d %H:%M:%S')}] {m['role'].upper()}: {m['content']}")
            
        print("-" * 50)
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(run_diag())
