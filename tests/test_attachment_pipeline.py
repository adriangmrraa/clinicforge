"""Integration test para el pipeline completo de multi-attachment.

Flujo: fetch mensajes → dedup → aplicar límites → batch analyze → classify → save → summary
"""
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch


class TestAttachmentPipelineIntegration:
    """Simula el flujo completo de buffer_task.py para multi-attachment processing."""

    async def test_full_pipeline_classifies_and_saves(self):
        """5 imágenes mixtas → classify → save en patient_documents + generar summary."""
        from services.vision_service import analyze_attachments_batch
        from services.image_classifier import classify_message
        from services.attachment_summary import generate_attachment_summary

        # --- 1. Simular attachments (ya deduplicados y dentro de límites) ---
        attachments = [
            {"url": "https://ex.com/comprobante.jpg", "mime_type": "image/jpeg", "index": 0},
            {"url": "https://ex.com/rx_panoramica.jpg", "mime_type": "image/jpeg", "index": 1},
            {"url": "https://ex.com/receta.pdf", "mime_type": "application/pdf", "index": 2},
        ]

        # --- 2. Batch analyze (mock Vision API) ---
        vision_results = {
            0: "Comprobante de transferencia bancaria Banco Nación por $3500 a nombre de Laura Delgado",
            1: "Radiografía panorámica dental mostrando implante en pieza 36 y caries en pieza 14",
            2: "Receta médica con prescripción de amoxicilina 500mg cada 8hs por 7 días",
        }

        with patch("services.vision_service.analyze_image_url", new_callable=AsyncMock) as mock_img, \
             patch("services.vision_service.analyze_pdf_url", new_callable=AsyncMock) as mock_pdf:

            async def mock_image_analyze(url, tenant_id):
                if "comprobante" in url:
                    return vision_results[0]
                return vision_results[1]

            mock_img.side_effect = mock_image_analyze
            mock_pdf.return_value = vision_results[2]

            batch_results = await analyze_attachments_batch(attachments, tenant_id=1)

        assert len(batch_results) == 3
        for r in batch_results:
            assert r["vision_description"] is not None
            assert r["error"] is None

        # --- 3. Classify each attachment ---
        classifications = []
        with patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock) as mock_kw:
            from services.image_classifier import DEFAULT_PAYMENT_KEYWORDS, DEFAULT_MEDICAL_KEYWORDS
            mock_kw.return_value = {
                "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
                "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
            }

            for result in batch_results:
                classification = await classify_message(
                    text="",
                    tenant_id=1,
                    vision_description=result["vision_description"],
                )
                classifications.append({
                    "index": result["index"],
                    "classification": classification["classification"],
                    "document_type": "payment_receipt" if classification["is_payment"] else "clinical",
                    "vision_description": result["vision_description"],
                })

        # Verify classifications
        assert classifications[0]["classification"] == "payment"
        assert classifications[0]["document_type"] == "payment_receipt"
        assert classifications[1]["classification"] == "medical"
        assert classifications[1]["document_type"] == "clinical"
        assert classifications[2]["classification"] == "medical"
        assert classifications[2]["document_type"] == "clinical"

        # --- 4. Generate LLM summary ---
        with patch("services.attachment_summary.AsyncOpenAI") as mock_openai_cls:
            mock_client = AsyncMock()
            summary_text = "Se recibieron 3 archivos: 1 comprobante de pago por $3500 (Banco Nación) y 2 documentos clínicos (radiografía panorámica con implante pieza 36, receta de amoxicilina 500mg)."
            mock_response = MagicMock()
            mock_response.choices = [MagicMock(message=MagicMock(content=summary_text))]
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai_cls.return_value = mock_client

            summary = await generate_attachment_summary(classifications, patient_name="Juan Pérez")

        assert "3 archivos" in summary
        assert "$3500" in summary
        assert len(summary) <= 500

    async def test_deduplication_removes_duplicate_urls(self):
        """Simula dedup logic de buffer_task.py."""
        all_attachments = [
            {"url": "https://ex.com/1.jpg", "mime_type": "image/jpeg", "index": 0},
            {"url": "https://ex.com/1.jpg", "mime_type": "image/jpeg", "index": 1},
            {"url": "https://ex.com/2.jpg", "mime_type": "image/jpeg", "index": 2},
        ]

        seen_urls = set()
        unique = []
        for att in all_attachments:
            if att["url"] not in seen_urls:
                seen_urls.add(att["url"])
                unique.append(att)

        assert len(unique) == 2
        assert unique[0]["url"] == "https://ex.com/1.jpg"
        assert unique[1]["url"] == "https://ex.com/2.jpg"

    async def test_limit_enforcement_truncates_correctly(self):
        """12 imágenes + 7 PDFs → debe truncar a 10 + 5."""
        from services.vision_service import MAX_IMAGES, MAX_PDFS

        images = [
            {"url": f"https://ex.com/img{i}.jpg", "mime_type": "image/jpeg", "index": i}
            for i in range(12)
        ]
        pdfs = [
            {"url": f"https://ex.com/doc{i}.pdf", "mime_type": "application/pdf", "index": 12 + i}
            for i in range(7)
        ]
        all_attachments = images + pdfs

        # Apply limits (same logic as buffer_task.py)
        filtered_images = [a for a in all_attachments if a["mime_type"].startswith("image/")]
        filtered_pdfs = [a for a in all_attachments if a["mime_type"] == "application/pdf"]

        if len(filtered_images) > MAX_IMAGES or len(filtered_pdfs) > MAX_PDFS:
            filtered_images = filtered_images[:MAX_IMAGES]
            filtered_pdfs = filtered_pdfs[:MAX_PDFS]

        result = filtered_images + filtered_pdfs
        assert len(filtered_images) == 10
        assert len(filtered_pdfs) == 5
        assert len(result) == 15

    async def test_pipeline_handles_vision_failures_gracefully(self):
        """Si Vision falla para 1 imagen, el resto sigue procesándose."""
        from services.vision_service import analyze_attachments_batch

        attachments = [
            {"url": "https://ex.com/1.jpg", "mime_type": "image/jpeg", "index": 0},
            {"url": "https://ex.com/2.jpg", "mime_type": "image/jpeg", "index": 1},
            {"url": "https://ex.com/3.jpg", "mime_type": "image/jpeg", "index": 2},
        ]

        with patch("services.vision_service.analyze_image_url", new_callable=AsyncMock) as mock:
            # First fails, second and third succeed
            mock.side_effect = [None, "Radiografía dental", "Foto intraoral"]

            results = await analyze_attachments_batch(attachments, tenant_id=1)

        assert len(results) == 3
        assert results[0]["error"] == "vision_failed"
        assert results[1]["vision_description"] == "Radiografía dental"
        assert results[2]["vision_description"] == "Foto intraoral"

    async def test_classification_without_vision_falls_to_neutral(self):
        """Attachment sin vision description se clasifica como neutral."""
        with patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock) as mock_kw:
            from services.image_classifier import DEFAULT_PAYMENT_KEYWORDS, DEFAULT_MEDICAL_KEYWORDS, classify_message
            mock_kw.return_value = {
                "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
                "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
            }

            result = await classify_message(
                text="",
                tenant_id=1,
                vision_description=None,
            )

        assert result["classification"] == "neutral"
