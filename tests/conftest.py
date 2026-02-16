import pytest
import os
from unittest.mock import MagicMock

# Set env vars before importing apps
os.environ["YCLOUD_API_KEY"] = "test_ycloud_key"
os.environ["YCLOUD_WEBHOOK_SECRET"] = "test_webhook_secret"
os.environ["INTERNAL_API_TOKEN"] = "test_internal_token"
os.environ["TIENDANUBE_API_KEY"] = "test_tn_key"
os.environ["OPENAI_API_KEY"] = "test_openai_key"
os.environ["POSTGRES_DSN"] = "postgresql://test:test@localhost:5432/test"
os.environ["REDIS_URL"] = "redis://localhost:6379"

@pytest.fixture
def mock_redis():
    mock = MagicMock()
    # Mock redis lock context manager
    mock.lock.return_value.acquire.return_value = True
    return mock

@pytest.fixture
def mock_db_pool():
    mock = MagicMock()
    return mock
    
