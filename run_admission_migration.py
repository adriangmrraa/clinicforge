#!/usr/bin/env python3
"""
Script to run migration patch 022: Add Patient Admission Fields
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from orchestrator_service.db import db

async def run_migration():
    """Run the migration patch 022"""
    print("🚀 Running Migration Patch 022: Add Patient Admission Fields")
    
    try:
        # Read migration file
        migration_path = project_root / "orchestrator_service" / "migrations" / "patch_022_patient_admission_fields.sql"
        
        if not migration_path.exists():
            print(f"❌ Migration file not found: {migration_path}")
            return False
        
        with open(migration_path, 'r') as f:
            migration_sql = f.read()
        
        print("📋 Executing migration SQL...")
        
        # Execute migration
        async with db.pool.acquire() as conn:
            await conn.execute(migration_sql)
        
        print("✅ Migration Patch 022 executed successfully!")
        print("\n📊 Changes applied:")
        print("   - Added 'city' field to patients table")
        print("   - Ensured 'first_touch_source' field exists")
        print("   - Ensured 'birth_date' field exists") 
        print("   - Ensured 'email' field exists")
        print("   - Created index on city field")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Initialize database connection
    import asyncio
    
    async def main():
        # Ensure database is connected
        await db.ensure_connected()
        
        # Run migration
        success = await run_migration()
        
        if success:
            print("\n🎉 Migration completed successfully!")
            print("📝 Next steps:")
            print("   1. Update book_appointment tool in main.py")
            print("   2. Test the updated admission process")
            print("   3. Verify data is being saved correctly")
        else:
            print("\n❌ Migration failed. Please check the error above.")
            sys.exit(1)
    
    asyncio.run(main())