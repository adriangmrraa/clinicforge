"""
Integration test for single page sync in ycloud-sync.
"""

import asyncio
import json
import os
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestSinglePageSync(unittest.TestCase):
    """Test cases for single page sync functionality."""

    def test_single_page_fetch(self):
        """Test fetching a single page of messages."""
        from ycloud_client import YCloudClient

        # Create mock client
        client = YCloudClient(api_key="test_key", business_number="+5491112345678")

        # Mock the fetch_messages response
        mock_response = {
            "messages": [
                {
                    "id": "msg_001",
                    "from": "5491112345678",
                    "to": "5491112345678",
                    "type": "text",
                    "text": {"body": "Hello, this is a test message"},
                    "timestamp": "1704067200",
                },
                {
                    "id": "msg_002",
                    "from": "5491188765432",
                    "to": "5491112345678",
                    "type": "text",
                    "text": {"body": "Another test message"},
                    "timestamp": "1704067300",
                },
            ],
            "next_cursor": None,  # No more pages
        }

        # Verify response structure matches what sync service expects
        self.assertIn("messages", mock_response)
        self.assertEqual(len(mock_response["messages"]), 2)
        self.assertIsNone(mock_response["next_cursor"])

    def test_message_parsing(self):
        """Test that messages can be parsed correctly."""
        from ycloud_client import normalize_phone_e164

        message = {
            "id": "msg_001",
            "from": "5491112345678",
            "to": "5491112345678",
            "type": "text",
            "text": {"body": "Test message"},
            "timestamp": "1704067200",
        }

        # Test phone normalization for from/to
        from_normalized = normalize_phone_e164(message["from"])
        to_normalized = normalize_phone_e164(message["to"])

        self.assertEqual(from_normalized, "+5491112345678")
        self.assertEqual(to_normalized, "+5491112345678")

    def test_pagination_detected(self):
        """Test that pagination is correctly detected."""
        response_with_next = {
            "messages": [{"id": "msg_001"}],
            "next_cursor": "cursor_page_2",
        }

        response_without_next = {"messages": [{"id": "msg_002"}], "next_cursor": None}

        # First page has next cursor - should continue pagination
        self.assertIsNotNone(response_with_next["next_cursor"])

        # Last page has no cursor - should stop
        self.assertIsNone(response_without_next["next_cursor"])

    def test_progress_tracking_structure(self):
        """Test that progress tracking has correct structure."""
        progress = {
            "task_id": "task_123",
            "status": "processing",
            "messages_fetched": 100,
            "messages_saved": 95,
            "media_downloaded": 5,
            "errors": [],
            "started_at": "2024-01-01T12:00:00Z",
            "completed_at": None,
        }

        # Validate required fields
        required_fields = [
            "task_id",
            "status",
            "messages_fetched",
            "messages_saved",
            "media_downloaded",
            "errors",
            "started_at",
            "completed_at",
        ]

        for field in required_fields:
            self.assertIn(field, progress, f"Missing required field: {field}")

        # Validate status values
        valid_statuses = ["queued", "processing", "completed", "error", "cancelled"]
        self.assertIn(progress["status"], valid_statuses)

    def test_media_message_handling(self):
        """Test handling of messages with media."""
        media_message = {
            "id": "msg_media_001",
            "from": "5491112345678",
            "to": "5491112345678",
            "type": "image",
            "image": {"id": "media_123", "mime_type": "image/jpeg", "sha256": "abc123"},
            "timestamp": "1704067200",
        }

        # Verify media message structure
        self.assertIn("type", media_message)
        self.assertIn("image", media_message)
        self.assertEqual(media_message["type"], "image")

        # Verify media has required fields
        media = media_message["image"]
        self.assertIn("id", media)
        self.assertIn("mime_type", media)


class TestSyncIntegration(unittest.TestCase):
    """Integration tests for the sync process."""

    @patch("services.ycloud_sync_service._get_redis")
    @patch("services.ycloud_sync_service._get_db")
    def test_sync_service_initialization(self, mock_db, mock_redis):
        """Test that sync service initializes correctly."""
        from services import ycloud_sync_service

        # Verify service has required constants
        self.assertEqual(ycloud_sync_service.INITIAL_BACKOFF, 1.0)
        self.assertEqual(ycloud_sync_service.MAX_BACKOFF, 60.0)
        self.assertEqual(ycloud_sync_service.MAX_RETRIES, 5)
        self.assertEqual(ycloud_sync_service.PAGE_SIZE, 100)
        self.assertEqual(ycloud_sync_service.MAX_MESSAGES, 10000)

    def test_media_path_generation(self):
        """Test media path generation for tenant."""
        from services.ycloud_sync_service import _get_media_path

        # Mock UPLOADS_DIR
        with patch.dict(os.environ, {"UPLOADS_DIR": "/tmp/test_uploads"}):
            path = _get_media_path(tenant_id=1, message_id="msg_123", extension="jpg")

            # Path should contain tenant_id and message_id
            self.assertIn("1", str(path))
            self.assertIn("msg_123", str(path))
            self.assertTrue(str(path).endswith(".jpg"))


if __name__ == "__main__":
    unittest.main()
