#!/usr/bin/env python3
"""
Test database connection
"""

import os
import asyncio
import asyncpg

async def test_connection():
    """Test database connection"""
    # Try to get DSN from environment or use default
    POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://postgres:postgres@localhost:5432/dentalogic")
    
    print(f"🔗 Testing connection to: {POSTGRES_DSN}")
    
    try:
        conn = await asyncpg.connect(POSTGRES_DSN)
        print("✅ Database connection successful!")
        
        # Check patients table structure
        print("\n📊 Checking patients table structure...")
        result = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'patients'
            ORDER BY ordinal_position
        """)
        
        print(f"Found {len(result)} columns in patients table:")
        for row in result:
            print(f"  - {row['column_name']}: {row['data_type']} ({'NULL' if row['is_nullable'] == 'YES' else 'NOT NULL'})")
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_connection())