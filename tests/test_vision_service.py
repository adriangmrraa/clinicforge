"""Tests para vision_service.py — Análisis batch de imágenes y PDFs."""
import pytest
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

from services.vision_service import (
    analyze_attachments_batch,
    analyze_image_url,
    analyze_pdf_url,
    MAX_IMAGES,
    MAX_PDFS,
    MAX_FILE_SIZE,
    VISION_TIMEOUT,
    MAX_CONCURRENT_VISION_CALLS,
)


class TestConstants:
    def test_max_images_is_10(self):
        assert MAX_IMAGES == 10

    def test_max_pdfs_is_5(self):
        assert MAX_PDFS == 5

    def test_max_file_size_is_5mb(self):
        assert MAX_FILE_SIZE == 5 * 1024 * 1024

    def test_vision_timeout_is_30s(self):
        assert VISION_TIMEOUT == 30

    def test_max_concurrent_is_5(self):
        assert MAX_CONCURRENT_VISION_CALLS == 5


class TestAnalyzeImageUrl:
    @patch("services.vision_service.aclient")
    async def test_external_url_calls_openai(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Imagen dental con caries visibles"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await analyze_image_url("https://example.com/foto.jpg", tenant_id=1)

        assert result == "Imagen dental con caries visibles"
        mock_client.chat.completions.create.assert_awaited_once()
        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["model"] == "gpt-4o"

    @patch("services.vision_service.aclient")
    async def test_local_file_uses_base64(self, mock_client, tmp_path):
        # Create a fake image file
        img_file = tmp_path / "uploads" / "test.jpg"
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Radiografía dental"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {"UPLOADS_DIR": str(tmp_path / "uploads")}):
            result = await analyze_image_url(f"/uploads/test.jpg", tenant_id=1)

        assert result == "Radiografía dental"
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        # Should use base64 data URL
        image_content = messages[0]["content"][1]
        assert "data:image/jpeg;base64," in image_content["image_url"]["url"]

    @patch("services.vision_service.aclient")
    async def test_nonexistent_local_file_returns_none(self, mock_client):
        with patch.dict(os.environ, {"UPLOADS_DIR": "/nonexistent"}):
            result = await analyze_image_url("/uploads/missing.jpg", tenant_id=1)

        assert result is None
        mock_client.chat.completions.create.assert_not_called()

    @patch("services.vision_service.aclient")
    async def test_openai_error_returns_none(self, mock_client):
        mock_client.chat.completions.create = AsyncMock(side_effect=Exception("API Error"))
        result = await analyze_image_url("https://example.com/foto.jpg", tenant_id=1)
        assert result is None

    @patch("services.vision_service.aclient")
    async def test_png_mime_type_detected(self, mock_client, tmp_path):
        img_file = tmp_path / "uploads" / "scan.png"
        img_file.parent.mkdir(parents=True, exist_ok=True)
        img_file.write_bytes(b"\x89PNG" + b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="PNG scan"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {"UPLOADS_DIR": str(tmp_path / "uploads")}):
            result = await analyze_image_url("/uploads/scan.png", tenant_id=1)

        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert "data:image/png;base64," in messages[0]["content"][1]["image_url"]["url"]


class TestAnalyzePdfUrl:
    @patch("services.vision_service.aclient")
    async def test_external_pdf_calls_openai(self, mock_client):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Informe clínico dental"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await analyze_pdf_url("https://example.com/informe.pdf", tenant_id=1)

        assert result == "Informe clínico dental"
        call_args = mock_client.chat.completions.create.call_args
        assert call_args.kwargs["model"] == "gpt-4o"

    @patch("services.vision_service.aclient")
    async def test_local_pdf_base64(self, mock_client, tmp_path):
        pdf_file = tmp_path / "uploads" / "receta.pdf"
        pdf_file.parent.mkdir(parents=True, exist_ok=True)
        pdf_file.write_bytes(b"%PDF-1.4" + b"\x00" * 100)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="Receta médica"))]
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

        with patch.dict(os.environ, {"UPLOADS_DIR": str(tmp_path / "uploads")}):
            result = await analyze_pdf_url("/uploads/receta.pdf", tenant_id=1)

        assert result == "Receta médica"
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args.kwargs["messages"]
        assert "data:application/pdf;base64," in messages[0]["content"][1]["image_url"]["url"]

    @patch("services.vision_service.aclient")
    async def test_oversized_pdf_returns_none(self, mock_client, tmp_path):
        pdf_file = tmp_path / "uploads" / "huge.pdf"
        pdf_file.parent.mkdir(parents=True, exist_ok=True)
        pdf_file.write_bytes(b"%PDF" + b"\x00" * (MAX_FILE_SIZE + 1))

        with patch.dict(os.environ, {"UPLOADS_DIR": str(tmp_path / "uploads")}):
            result = await analyze_pdf_url("/uploads/huge.pdf", tenant_id=1)

        assert result is None
        mock_client.chat.completions.create.assert_not_called()

    @patch("services.vision_service.aclient")
    async def test_missing_pdf_returns_none(self, mock_client):
        with patch.dict(os.environ, {"UPLOADS_DIR": "/nonexistent"}):
            result = await analyze_pdf_url("/uploads/missing.pdf", tenant_id=1)
        assert result is None


class TestAnalyzeAttachmentsBatch:
    @patch("services.vision_service.analyze_pdf_url", new_callable=AsyncMock)
    @patch("services.vision_service.analyze_image_url", new_callable=AsyncMock)
    async def test_batch_processes_images_and_pdfs(self, mock_image, mock_pdf):
        mock_image.return_value = "Imagen dental"
        mock_pdf.return_value = "PDF clínico"

        attachments = [
            {"url": "https://ex.com/1.jpg", "mime_type": "image/jpeg", "index": 0},
            {"url": "https://ex.com/2.pdf", "mime_type": "application/pdf", "index": 1},
        ]
        results = await analyze_attachments_batch(attachments, tenant_id=1)

        assert len(results) == 2
        assert results[0]["vision_description"] == "Imagen dental"
        assert results[0]["error"] is None
        assert results[1]["vision_description"] == "PDF clínico"
        assert results[1]["error"] is None

    @patch("services.vision_service.analyze_image_url", new_callable=AsyncMock)
    async def test_limits_enforce_max_images(self, mock_image):
        mock_image.return_value = "desc"

        # 12 images — should truncate to 10
        attachments = [
            {"url": f"https://ex.com/{i}.jpg", "mime_type": "image/jpeg", "index": i}
            for i in range(12)
        ]
        results = await analyze_attachments_batch(attachments, tenant_id=1)

        assert len(results) == MAX_IMAGES
        assert mock_image.await_count == MAX_IMAGES

    @patch("services.vision_service.analyze_pdf_url", new_callable=AsyncMock)
    async def test_limits_enforce_max_pdfs(self, mock_pdf):
        mock_pdf.return_value = "desc"

        # 7 PDFs — should truncate to 5
        attachments = [
            {"url": f"https://ex.com/{i}.pdf", "mime_type": "application/pdf", "index": i}
            for i in range(7)
        ]
        results = await analyze_attachments_batch(attachments, tenant_id=1)

        assert len(results) == MAX_PDFS
        assert mock_pdf.await_count == MAX_PDFS

    @patch("services.vision_service.analyze_image_url", new_callable=AsyncMock)
    async def test_unsupported_mime_type_skipped(self, mock_image):
        attachments = [
            {"url": "https://ex.com/file.mp4", "mime_type": "video/mp4", "index": 0},
        ]
        results = await analyze_attachments_batch(attachments, tenant_id=1)

        # video/mp4 is neither image/ nor application/pdf → filtered out
        assert len(results) == 0
        mock_image.assert_not_awaited()

    @patch("services.vision_service.analyze_image_url", new_callable=AsyncMock)
    async def test_timeout_returns_error(self, mock_image):
        async def slow_analyze(*args, **kwargs):
            await asyncio.sleep(60)
            return "never"

        mock_image.side_effect = slow_analyze

        attachments = [
            {"url": "https://ex.com/1.jpg", "mime_type": "image/jpeg", "index": 0},
        ]

        # Patch VISION_TIMEOUT to 0.1s for fast test
        with patch("services.vision_service.VISION_TIMEOUT", 0.1):
            results = await analyze_attachments_batch(attachments, tenant_id=1)

        assert len(results) == 1
        assert results[0]["error"] == "timeout"
        assert results[0]["vision_description"] is None

    @patch("services.vision_service.analyze_image_url", new_callable=AsyncMock)
    async def test_individual_failure_doesnt_break_batch(self, mock_image):
        # First call fails, second succeeds
        mock_image.side_effect = [None, "Imagen 2 OK"]

        attachments = [
            {"url": "https://ex.com/1.jpg", "mime_type": "image/jpeg", "index": 0},
            {"url": "https://ex.com/2.jpg", "mime_type": "image/jpeg", "index": 1},
        ]
        results = await analyze_attachments_batch(attachments, tenant_id=1)

        assert len(results) == 2
        assert results[0]["error"] == "vision_failed"
        assert results[1]["vision_description"] == "Imagen 2 OK"
        assert results[1]["error"] is None

    @patch("services.vision_service.analyze_image_url", new_callable=AsyncMock)
    async def test_results_sorted_by_index(self, mock_image):
        mock_image.return_value = "desc"

        attachments = [
            {"url": "https://ex.com/2.jpg", "mime_type": "image/jpeg", "index": 2},
            {"url": "https://ex.com/0.jpg", "mime_type": "image/jpeg", "index": 0},
            {"url": "https://ex.com/1.jpg", "mime_type": "image/jpeg", "index": 1},
        ]
        results = await analyze_attachments_batch(attachments, tenant_id=1)

        indices = [r["index"] for r in results]
        assert indices == [0, 1, 2]
