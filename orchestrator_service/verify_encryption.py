
import asyncio
import os
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from db import db
from core.credentials import get_tenant_credential

# Mock key for testing if not present
if not os.getenv("CREDENTIALS_FERNET_KEY"):
    key = Fernet.generate_key().decode()
    os.environ["CREDENTIALS_FERNET_KEY"] = key
    print(f"Generated Mock Key: {key}")

async def test_encryption_flow():
    await db.connect()
    
    # 1. Setup Test Data
    tenant_id = 9999 # Fake tenant
    cred_name = "TEST_CRED_V2"
    cred_value = "SUPER_SECRET_VALUE_123"
    
    print(f"Testing with Tenant: {tenant_id}, Cred: {cred_name}")
    
    # 2. Simulate Encryption (Logic from admin_routes)
    from admin_routes import _encrypt_credential
    encrypted = _encrypt_credential(cred_value)
    print(f"Encrypted Value: {encrypted}")
    
    # 3. Direct Insert (Simulating POST /admin/credentials)
    await db.pool.execute("""
        INSERT INTO credentials (tenant_id, name, value, category, scope)
        VALUES ($1, $2, $3, 'test', 'tenant')
        ON CONFLICT (id) DO UPDATE SET value = $3
    """, tenant_id, cred_name, encrypted)
    
    # 4. Verify Decryption via Core (Simulating usage)
    decrypted = await get_tenant_credential(tenant_id, cred_name)
    print(f"Decrypted via Core: {decrypted}")
    
    assert decrypted == cred_value, "Decryption failed! Value mismatch."
    print("SUCCESS: Encryption/Decryption cycle validated.")
    
    # Cleanup
    await db.pool.execute("DELETE FROM credentials WHERE tenant_id = $1 AND name = $2", tenant_id, cred_name)
    await db.disconnect()

if __name__ == "__main__":
    asyncio.run(test_encryption_flow())
