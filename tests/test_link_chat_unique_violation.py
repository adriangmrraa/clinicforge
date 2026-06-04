"""
Unit and integration tests for link_chat_to_patient unique violation fix.
"""

import json
import pytest
import uuid as _uuid
from unittest.mock import patch, AsyncMock, MagicMock
from contextlib import contextmanager

TEST_TENANT_ID = 42
TEST_PATIENT_ID = 123
TEST_CONV_ID = "11111111-1111-1111-1111-111111111111"


@contextmanager
def override_auth(app):
    """Override verify_admin_token and get_resolved_tenant_id on the FastAPI app."""
    import orchestrator_service.admin_routes as _ar
    verify_admin_token = _ar.verify_admin_token
    get_resolved_tenant_id = _ar.get_resolved_tenant_id

    async def _fake_verify_admin():
        return {"user_id": 1, "tenant_id": TEST_TENANT_ID}

    async def _fake_tenant_id():
        return TEST_TENANT_ID

    app.dependency_overrides[verify_admin_token] = _fake_verify_admin
    app.dependency_overrides[get_resolved_tenant_id] = _fake_tenant_id
    try:
        yield
    finally:
        app.dependency_overrides.pop(verify_admin_token, None)
        app.dependency_overrides.pop(get_resolved_tenant_id, None)


def _get_app():
    from orchestrator_service.main import app
    return app


class TestLinkChatUniqueViolation:
    """Test suite for unique violation fixes in chat linking."""

    def test_unique_filename_generation_and_migration_check(self, app_with_mock_pool):
        """
        Verify that multiple attachments in the same message are migrated:
        1. Base filenames are preserved and get an 8-character hex suffix.
        2. Attachments with missing filenames get a default base name 'chat_doc_{msg_id}' + suffix.
        3. Already migrated check uses both source_message_id and file_path.
        """
        client, mock_pool = app_with_mock_pool

        # Setup standard mock values
        def mock_fetchrow(query, *args):
            if "chat_conversations" in query:
                return {
                    "id": _uuid.UUID(TEST_CONV_ID),
                    "external_user_id": "contact_user",
                    "display_name": "Jesus Contact",
                }
            elif "patients" in query:
                return {
                    "id": TEST_PATIENT_ID,
                    "first_name": "Wilda",
                    "last_name": "Patient",
                    "phone_number": "+123456789",
                }
            return None

        mock_pool.fetchrow = AsyncMock(side_effect=mock_fetchrow)

        # Message with 2 attachments: one with file_name, one without
        fake_messages = [
            {
                "id": 999,
                "created_at": "2026-06-04T12:00:00Z",
                "content": "",
                "content_attributes": [
                    {
                        "url": "http://example.com/receipt.pdf",
                        "file_name": "receipt.pdf",
                        "mime_type": "application/pdf",
                        "description": "Comprobante de pago",
                    },
                    {
                        "url": "http://example.com/image.png",
                        "file_name": None,
                        "mime_type": "image/png",
                        "description": "Estudio clinico",
                    }
                ]
            }
        ]
        mock_pool.fetch = AsyncMock(return_value=fake_messages)

        # First run: nothing exists in database
        mock_pool.fetchval = AsyncMock(return_value=None)
        
        inserted_files = []
        async def mock_execute(query, *args):
            if "INSERT INTO patient_documents" in query:
                # args: tenant_id, patient_id, file_name, file_path, mime_type, document_type, source_details, msg['created_at']
                inserted_files.append({
                    "file_name": args[2],
                    "file_path": args[3],
                    "mime_type": args[4],
                    "document_type": args[5],
                })
            return None

        mock_pool.execute = AsyncMock(side_effect=mock_execute)

        with override_auth(_get_app()):
            response = client.post(
                "/admin/chat/link-to-patient",
                json={
                    "patient_id": TEST_PATIENT_ID,
                    "conversation_id": TEST_CONV_ID,
                    "migrate_documents": True,
                },
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 200
        assert response.json()["migrated_documents"] == 2

        # Verify filenames and content
        assert len(inserted_files) == 2
        
        # 1. receipt.pdf -> receipt_{8-char-hex}.pdf
        receipt_doc = inserted_files[0]
        assert receipt_doc["file_path"] == "http://example.com/receipt.pdf"
        assert receipt_doc["mime_type"] == "application/pdf"
        assert receipt_doc["document_type"] == "receipt"
        assert receipt_doc["file_name"].startswith("receipt_")
        assert receipt_doc["file_name"].endswith(".pdf")
        # Ensure 8-character hex is appended (e.g. len("receipt_") is 8, len(".pdf") is 4, total len should be 8 + 8 + 4 = 20)
        assert len(receipt_doc["file_name"]) == 20

        # 2. None -> chat_doc_999_{8-char-hex}
        image_doc = inserted_files[1]
        assert image_doc["file_path"] == "http://example.com/image.png"
        assert image_doc["mime_type"] == "image/png"
        assert image_doc["document_type"] == "clinical"
        assert image_doc["file_name"].startswith("chat_doc_999_")
        # No extension since file_name was missing
        assert len(image_doc["file_name"]) == len("chat_doc_999_") + 8

    def test_duplicate_filenames_in_different_messages(self, app_with_mock_pool):
        """
        Verify that duplicate filenames in different messages are both migrated without conflicts
        because unique suffixes ensure they have distinct filenames.
        """
        client, mock_pool = app_with_mock_pool

        def mock_fetchrow(query, *args):
            if "chat_conversations" in query:
                return {
                    "id": _uuid.UUID(TEST_CONV_ID),
                    "external_user_id": "contact_user",
                    "display_name": "Jesus Contact",
                }
            elif "patients" in query:
                return {
                    "id": TEST_PATIENT_ID,
                    "first_name": "Wilda",
                    "last_name": "Patient",
                    "phone_number": "+123456789",
                }
            return None

        mock_pool.fetchrow = AsyncMock(side_effect=mock_fetchrow)

        # Message A and Message B have "receipt.pdf"
        fake_messages = [
            {
                "id": 100,
                "created_at": "2026-06-04T12:00:00Z",
                "content": "",
                "content_attributes": [
                    {
                        "url": "http://example.com/msgA/receipt.pdf",
                        "file_name": "receipt.pdf",
                        "mime_type": "application/pdf",
                        "description": "Comprobante de pago",
                    }
                ]
            },
            {
                "id": 101,
                "created_at": "2026-06-04T12:05:00Z",
                "content": "",
                "content_attributes": [
                    {
                        "url": "http://example.com/msgB/receipt.pdf",
                        "file_name": "receipt.pdf",
                        "mime_type": "application/pdf",
                        "description": "Otro Comprobante",
                    }
                ]
            }
        ]
        mock_pool.fetch = AsyncMock(return_value=fake_messages)
        mock_pool.fetchval = AsyncMock(return_value=None)
        
        inserted_files = []
        async def mock_execute(query, *args):
            if "INSERT INTO patient_documents" in query:
                inserted_files.append(args[2]) # filename
            return None

        mock_pool.execute = AsyncMock(side_effect=mock_execute)

        with override_auth(_get_app()):
            response = client.post(
                "/admin/chat/link-to-patient",
                json={
                    "patient_id": TEST_PATIENT_ID,
                    "conversation_id": TEST_CONV_ID,
                    "migrate_documents": True,
                },
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 200
        assert response.json()["migrated_documents"] == 2
        assert len(inserted_files) == 2
        assert inserted_files[0] != inserted_files[1]
        assert inserted_files[0].startswith("receipt_")
        assert inserted_files[1].startswith("receipt_")

    def test_re_run_migration_skips_already_migrated(self, app_with_mock_pool):
        """
        Verify that re-running migration with already migrated attachments skips them.
        The exists check MUST pass the media_url/file_path as query parameter $4.
        """
        client, mock_pool = app_with_mock_pool

        def mock_fetchrow(query, *args):
            if "chat_conversations" in query:
                return {
                    "id": _uuid.UUID(TEST_CONV_ID),
                    "external_user_id": "contact_user",
                    "display_name": "Jesus Contact",
                }
            elif "patients" in query:
                return {
                    "id": TEST_PATIENT_ID,
                    "first_name": "Wilda",
                    "last_name": "Patient",
                    "phone_number": "+123456789",
                }
            return None

        mock_pool.fetchrow = AsyncMock(side_effect=mock_fetchrow)

        fake_messages = [
            {
                "id": 102,
                "created_at": "2026-06-04T12:00:00Z",
                "content": "",
                "content_attributes": [
                    {
                        "url": "http://example.com/receipt.pdf",
                        "file_name": "receipt.pdf",
                        "mime_type": "application/pdf",
                        "description": "Comprobante",
                    }
                ]
            }
        ]
        mock_pool.fetch = AsyncMock(return_value=fake_messages)
        
        # Simulate that it already exists in the database
        mock_pool.fetchval = AsyncMock(return_value=1)
        mock_pool.execute = AsyncMock()

        with override_auth(_get_app()):
            response = client.post(
                "/admin/chat/link-to-patient",
                json={
                    "patient_id": TEST_PATIENT_ID,
                    "conversation_id": TEST_CONV_ID,
                    "migrate_documents": True,
                },
                headers={"Authorization": "Bearer fake", "X-Admin-Token": "fake"},
            )

        assert response.status_code == 200
        assert response.json()["migrated_documents"] == 0

        # Verify the duplicate check was called with proper parameters
        mock_pool.fetchval.assert_called_once()
        call_args = mock_pool.fetchval.call_args[0]
        # Query check:
        # SELECT 1 FROM patient_documents
        # WHERE tenant_id = $1 AND patient_id = $2
        # AND source_details->>'source_message_id' = $3
        # AND file_path = $4
        assert "AND file_path = $4" in call_args[0]
        assert call_args[1] == TEST_TENANT_ID
        assert call_args[2] == TEST_PATIENT_ID
        assert call_args[3] == "102"
        assert call_args[4] == "http://example.com/receipt.pdf"

        # Execute should not have been called for insertion
        # Note: execute was called for the initial "UPDATE chat_conversations SET linked_patient_id = $1"
        # but NOT for "INSERT INTO patient_documents"
        insert_calls = [c for c in mock_pool.execute.call_args_list if "INSERT INTO patient_documents" in c[0][0]]
        assert len(insert_calls) == 0
