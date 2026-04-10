"""
Tests for exponential backoff in ycloud-sync rate limiting.
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from services.ycloud_sync_service import (
    _fetch_with_backoff,
    RateLimitError,
    INITIAL_BACKOFF,
    MAX_BACKOFF,
    MAX_RETRIES,
)


class MockYCloudClient:
    """Mock YCloudClient for testing."""

    def __init__(self, fail_count=0, fail_with=None):
        self.fail_count = fail_count
        self.fail_with = fail_with
        self.call_count = 0

    async def fetch_messages(self, cursor=None, limit=100):
        self.call_count += 1
        if self.call_count <= self.fail_count:
            raise self.fail_with or RateLimitError("Rate limited", retry_after=60)
        return {
            "messages": [{"id": "msg1", "from": "5491112345678"}],
            "next_cursor": None,
        }


class TestExponentialBackoff(unittest.TestCase):
    """Test cases for exponential backoff rate limiting."""

    def test_backoff_values(self):
        """Test that backoff values are correct."""
        # Initial backoff should be 1 second
        self.assertEqual(INITIAL_BACKOFF, 1.0)
        # Max backoff should be 60 seconds
        self.assertEqual(MAX_BACKOFF, 60.0)
        # Max retries should be 5
        self.assertEqual(MAX_RETRIES, 5)

    def test_first_attempt_succeeds(self):
        """Test that first attempt succeeds when no rate limit."""
        client = MockYCloudClient(fail_count=0)

        result = asyncio.run(_fetch_with_backoff(client))

        self.assertEqual(client.call_count, 1)
        self.assertIn("messages", result)

    def test_backoff_on_first_rate_limit(self):
        """Test backoff triggers on first 429 response."""
        client = MockYCloudClient(
            fail_count=1, fail_with=RateLimitError("Rate limited", retry_after=60)
        )

        result = asyncio.run(_fetch_with_backoff(client))

        # Should have retried once
        self.assertEqual(client.call_count, 2)
        self.assertIn("messages", result)

    def test_multiple_backoff_retries(self):
        """Test multiple retries with exponential backoff."""
        # This will fail 3 times, then succeed
        client = MockYCloudClient(
            fail_count=3, fail_with=RateLimitError("Rate limited", retry_after=60)
        )

        result = asyncio.run(_fetch_with_backoff(client))

        # Should have retried 3 times + 1 initial attempt = 4 calls
        self.assertEqual(client.call_count, 4)

    def test_max_retries_exceeded(self):
        """Test that RateLimitError is raised after max retries."""
        # Fail more times than MAX_RETRIES
        client = MockYCloudClient(
            fail_count=10, fail_with=RateLimitError("Rate limited", retry_after=60)
        )

        with self.assertRaises(RateLimitError):
            asyncio.run(_fetch_with_backoff(client))

        # Should have tried MAX_RETRIES times
        self.assertEqual(client.call_count, MAX_RETRIES)

    def test_backoff_sequence(self):
        """Test that backoff times follow exponential pattern."""
        backoff_times = []

        class BackoffClient:
            def __init__(self):
                self.call_count = 0

            async def fetch_messages(self, cursor=None, limit=100):
                self.call_count += 1
                if self.call_count <= 3:
                    raise RateLimitError("Rate limited", retry_after=60)
                return {"messages": [], "next_cursor": None}

        client = BackoffClient()

        # Patch sleep to record wait times
        original_sleep = asyncio.sleep

        async def mock_sleep(duration):
            backoff_times.append(duration)
            # Don't actually sleep in tests

        with patch("asyncio.sleep", mock_sleep):
            result = asyncio.run(_fetch_with_backoff(client))

        # First wait should be INITIAL_BACKOFF (1s)
        # Second wait should be 2s, third should be 4s (exponential)
        self.assertGreaterEqual(backoff_times[0], INITIAL_BACKOFF)
        self.assertGreaterEqual(backoff_times[1], INITIAL_BACKOFF * 2)

    def test_backoff_capped_at_max(self):
        """Test that backoff is capped at MAX_BACKOFF."""
        backoff_times = []

        class CappedBackoffClient:
            def __init__(self):
                self.call_count = 0

            async def fetch_messages(self, cursor=None, limit=100):
                self.call_count += 1
                raise RateLimitError("Rate limited", retry_after=60)

        client = CappedBackoffClient()

        async def mock_sleep(duration):
            backoff_times.append(duration)

        with patch("asyncio.sleep", mock_sleep):
            with self.assertRaises(RateLimitError):
                asyncio.run(_fetch_with_backoff(client))

        # All wait times should be capped at MAX_BACKOFF (60)
        for wait_time in backoff_times:
            self.assertLessEqual(wait_time, MAX_BACKOFF)


class TestRateLimitError(unittest.TestCase):
    """Test cases for RateLimitError exception."""

    def test_error_attributes(self):
        """Test that RateLimitError has correct attributes."""
        error = RateLimitError("Rate limited", retry_after=30)

        self.assertEqual(str(error), "Rate limited")
        self.assertEqual(error.retry_after, 30)

    def test_default_retry_after(self):
        """Test default retry_after value."""
        error = RateLimitError("Rate limited")

        self.assertEqual(error.retry_after, 60)


if __name__ == "__main__":
    unittest.main()
