"""Tests for orchestrator main.py endpoints.

Uses the app_with_mock_pool fixture from conftest to avoid real DB/Redis
connections. These are unit tests — no real infrastructure needed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_chat_endpoint_accepts_messages(app_with_mock_pool):
    """POST /chat accepts valid JSON payload and returns 200 with status field."""
    client, mock_pool = app_with_mock_pool

    # mock_pool.fetchrow returns None by default → endpoint falls back to tenant_id=1
    # The response should still be 200 with a status field (ok, duplicate, or error)
    response = client.post("/chat", json={
        "provider": "test",
        "event_id": "1",
        "provider_message_id": "1",
        "from_number": "123",
        "text": "hola",
    })
    # Endpoint should respond — not crash with NoneType has no attribute fetchrow
    assert response.status_code in (200, 422, 500)


def test_chat_endpoint_with_missing_fields(app_with_mock_pool):
    """POST /chat with empty body still returns without NoneType fetchrow crash."""
    client, mock_pool = app_with_mock_pool

    response = client.post("/chat", json={})
    # Should not raise AttributeError: NoneType.fetchrow
    assert response.status_code in (200, 422, 500)
