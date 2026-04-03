"""Tests para attachment_summary.py — Generación de resúmenes LLM de adjuntos."""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from services.attachment_summary import (
    generate_attachment_summary,
    save_summary_to_db,
    generate_and_save_summary,
)


class TestGenerateAttachmentSummary:
    @patch("services.attachment_summary.AsyncOpenAI")
    async def test_generates_summary_from_analyses(self, mock_openai_cls):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content="Se recibieron 2 archivos: 1 comprobante de pago por $3500 y 1 radiografía dental panorámica."))
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_cls.return_value = mock_client

        analyses = [
            {"index": 0, "document_type": "payment_receipt", "vision_description": "Comprobante de transferencia por $3500"},
            {"index": 1, "document_type": "clinical", "vision_description": "Radiografía panorámica dental"},
        ]

        result = await generate_attachment_summary(analyses, patient_name="Juan Pérez")

        assert "2 archivos" in result
        mock_client.chat.completions.create.assert_awaited_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["temperature"] == 0.3

    @patch("services.attachment_summary.AsyncOpenAI")
    async def test_truncates_to_500_chars(self, mock_openai_cls):
        mock_client = AsyncMock()
        long_text = "A" * 700
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content=long_text))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_cls.return_value = mock_client

        result = await generate_attachment_summary(
            [{"index": 0, "document_type": "clinical", "vision_description": "test"}],
            patient_name="Test",
        )
        assert len(result) <= 500

    @patch("services.attachment_summary.AsyncOpenAI")
    async def test_fallback_on_llm_error_mixed(self, mock_openai_cls):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
        mock_openai_cls.return_value = mock_client

        analyses = [
            {"index": 0, "document_type": "payment_receipt", "vision_description": "pago"},
            {"index": 1, "document_type": "clinical", "vision_description": "rx"},
        ]
        result = await generate_attachment_summary(analyses, patient_name="Test")

        assert "2 archivos" in result
        assert "1 comprobantes de pago" in result
        assert "1 documentos clínicos" in result

    @patch("services.attachment_summary.AsyncOpenAI")
    async def test_fallback_payment_only(self, mock_openai_cls):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
        mock_openai_cls.return_value = mock_client

        analyses = [
            {"index": 0, "document_type": "payment_receipt", "vision_description": "pago"},
        ]
        result = await generate_attachment_summary(analyses, patient_name="Test")
        assert "1 comprobantes de pago" in result

    @patch("services.attachment_summary.AsyncOpenAI")
    async def test_fallback_clinical_only(self, mock_openai_cls):
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("fail"))
        mock_openai_cls.return_value = mock_client

        analyses = [
            {"index": 0, "document_type": "clinical", "vision_description": "rx"},
        ]
        result = await generate_attachment_summary(analyses, patient_name="Test")
        assert "1 documentos clínicos" in result

    async def test_empty_analyses_returns_message(self):
        result = await generate_attachment_summary([], patient_name="Test")
        assert result == "No hay archivos para resumir."

    @patch("services.attachment_summary.AsyncOpenAI")
    async def test_prompt_includes_patient_name(self, mock_openai_cls):
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Resumen"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_openai_cls.return_value = mock_client

        await generate_attachment_summary(
            [{"index": 0, "document_type": "clinical", "vision_description": "rx"}],
            patient_name="María García",
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        user_msg = call_kwargs["messages"][1]["content"]
        assert "María García" in user_msg


def _make_pool_with_conn(mock_conn):
    """Helper: create a mock asyncpg pool that yields mock_conn from acquire()."""
    mock_pool = MagicMock()
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_pool.acquire.return_value = mock_ctx
    return mock_pool


class TestSaveSummaryToDb:
    async def test_upserts_into_clinical_record_summaries(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 42})
        mock_conn.execute = AsyncMock()
        mock_pool = _make_pool_with_conn(mock_conn)

        analyses = [
            {"document_type": "payment_receipt"},
            {"document_type": "clinical"},
        ]

        success, summary_id = await save_summary_to_db(
            pool=mock_pool,
            tenant_id=1,
            patient_id=100,
            conversation_id="conv-123",
            summary_text="Resumen test",
            analyses=analyses,
        )

        assert success is True
        assert summary_id == 42
        mock_conn.fetchrow.assert_awaited_once()
        insert_sql = mock_conn.fetchrow.call_args.args[0]
        assert "clinical_record_summaries" in insert_sql

    async def test_updates_first_document_source_details(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 42})
        mock_conn.execute = AsyncMock()
        mock_pool = _make_pool_with_conn(mock_conn)

        success, _ = await save_summary_to_db(
            pool=mock_pool,
            tenant_id=1,
            patient_id=100,
            conversation_id="conv-123",
            summary_text="Resumen",
            analyses=[{"document_type": "clinical"}],
            first_document_id=55,
        )

        assert success is True
        assert mock_conn.execute.await_count == 1
        update_sql = mock_conn.execute.call_args.args[0]
        assert "patient_documents" in update_sql
        assert "llm_summary" in update_sql

    async def test_returns_false_on_db_error(self):
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(side_effect=Exception("DB error"))
        mock_pool = _make_pool_with_conn(mock_conn)

        success, summary_id = await save_summary_to_db(
            pool=mock_pool,
            tenant_id=1,
            patient_id=100,
            conversation_id="conv-123",
            summary_text="Resumen",
            analyses=[],
        )

        assert success is False
        assert summary_id is None


class TestGenerateAndSaveSummary:
    @patch("services.attachment_summary.save_summary_to_db", new_callable=AsyncMock)
    @patch("services.attachment_summary.generate_attachment_summary", new_callable=AsyncMock)
    async def test_orchestrates_generate_and_save(self, mock_generate, mock_save):
        mock_generate.return_value = "Resumen generado"
        mock_save.return_value = (True, 99)

        mock_pool = AsyncMock()
        analyses = [{"document_type": "clinical", "vision_description": "rx", "index": 0}]

        success, summary_id, text = await generate_and_save_summary(
            pool=mock_pool,
            tenant_id=1,
            patient_id=100,
            patient_name="Test Patient",
            analyses=analyses,
            conversation_id="conv-1",
        )

        assert success is True
        assert summary_id == 99
        assert text == "Resumen generado"
        mock_generate.assert_awaited_once_with(analyses, "Test Patient")
        mock_save.assert_awaited_once()
