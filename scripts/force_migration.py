import asyncio
import os
import asyncpg
from datetime import datetime

# Adjust as needed or load from .env
# Default to localhost for local run, or service name for docker run
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://user:pass@postgres:5432/dental_db") 

async def force_apply_patch():
    print(f"🔌 Connecting to DB...")
    try:
        if "postgresql+asyncpg://" in POSTGRES_DSN:
            dsn = POSTGRES_DSN.replace("postgresql+asyncpg://", "postgresql://")
        else:
            dsn = POSTGRES_DSN
            
        pool = await asyncpg.create_pool(dsn)
        
        async with pool.acquire() as conn:
            print("🛠 Checking for 'last_derivhumano_at' column...")
            
            # Check if column exists
            exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.columns 
                    WHERE table_name='chat_conversations' 
                    AND column_name='last_derivhumano_at'
                );
            """)
            
            if exists:
                print("✅ Column 'last_derivhumano_at' ALREADY EXISTS. No action needed.")
            else:
                print("⚠️ Column missing. Attempting to ADD column...")
                await conn.execute("""
                    ALTER TABLE chat_conversations 
                    ADD COLUMN last_derivhumano_at TIMESTAMP WITH TIME ZONE;
                """)
                print("✅ Column 'last_derivhumano_at' CREATED successfully.")
                
                # Create index
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_chat_conv_last_derivhumano 
                    ON chat_conversations(last_derivhumano_at);
                """)
                print("✅ Index created.")

    except Exception as e:
        print(f"❌ Error: {e}")
        
if __name__ == "__main__":
    asyncio.run(force_apply_patch())
