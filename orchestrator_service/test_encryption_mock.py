
import asyncio
import os
from unittest.mock import MagicMock, patch
from cryptography.fernet import Fernet

# Set default key for testing
TEST_KEY = Fernet.generate_key().decode()
os.environ["CREDENTIALS_FERNET_KEY"] = TEST_KEY

# Import functions to test
# We need to mock get_pool inside admin_routes and core.credentials to avoid DB connection attempt
with patch("db.get_pool", return_value=MagicMock()):
    from admin_routes import _encrypt_credential, _decrypt_credential
    from core.credentials import get_tenant_credential

async def test_crypto_logic():
    print(f"Testing Crypto Logic with Key: {TEST_KEY[:5]}...")
    
    original_value = "MY_SECRET_token_123"
    
    # 1. Test Encrypt
    encrypted = _encrypt_credential(original_value)
    print(f"Encrypted ({len(encrypted)} chars): {encrypted}")
    assert encrypted != original_value
    assert len(encrypted) > 20
    
    # 2. Test Decrypt (Direct)
    decrypted_direct = _decrypt_credential(encrypted)
    print(f"Decrypted Direct: {decrypted_direct}")
    assert decrypted_direct == original_value
    
    # 3. Test get_tenant_credential logic (Mocking DB)
    # Simulator of what DB returns (encrypted string)
    mock_row = {"value": encrypted}
    
    # Mock pool and connection
    mock_pool = MagicMock()
    mock_conn = MagicMock()
    mock_pool.fetchrow.return_value = mock_row
    
    # Patch get_pool in core.credentials
    with patch("core.credentials.get_pool", return_value=mock_pool):
        # The function awaits pool.fetchrow, so we need to mock async return
        f = asyncio.Future()
        f.set_result(mock_row)
        mock_pool.fetchrow.return_value = f
        
        result = await get_tenant_credential(1, "TEST_KEY")
        print(f"Decrypted via Core: {result}")
        assert result == original_value
        
    print("SUCCESS: Logic validated without DB connection.")

if __name__ == "__main__":
    asyncio.run(test_crypto_logic())
