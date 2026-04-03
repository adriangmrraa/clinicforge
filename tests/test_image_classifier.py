"""Tests para image_classifier.py — Clasificación de mensajes WhatsApp."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from services.image_classifier import (
    classify_message,
    classify_message_sync,
    classify_from_vision,
    DEFAULT_PAYMENT_KEYWORDS,
    DEFAULT_MEDICAL_KEYWORDS,
    STRONG_PAYMENT_KEYWORDS,
    STRONG_MEDICAL_KEYWORDS,
    _compile_keywords,
    _match_keywords,
)


class TestCompileKeywords:
    def test_compiles_valid_patterns(self):
        patterns = _compile_keywords(["transferencia", r"\$\d+"])
        assert len(patterns) == 2

    def test_skips_invalid_regex(self):
        patterns = _compile_keywords(["valid", r"[invalid"])
        assert len(patterns) == 1

    def test_empty_list(self):
        assert _compile_keywords([]) == []


class TestMatchKeywords:
    def test_matches_found(self):
        patterns = _compile_keywords(["transferencia", "pago"])
        matches = _match_keywords("hice una transferencia", patterns)
        assert "transferencia" in matches
        assert "pago" not in matches

    def test_no_matches(self):
        patterns = _compile_keywords(["transferencia"])
        matches = _match_keywords("hola buen día", patterns)
        assert matches == []

    def test_case_insensitive(self):
        patterns = _compile_keywords(["comprobante"])
        matches = _match_keywords("COMPROBANTE de pago", patterns)
        assert len(matches) == 1


class TestClassifyMessageSync:
    def test_empty_text_returns_neutral(self):
        result = classify_message_sync("")
        assert result["classification"] == "neutral"
        assert result["is_payment"] is False
        assert result["is_medical"] is False
        assert result["confidence"] == 0.0

    def test_strong_payment_keyword(self):
        result = classify_message_sync("te envío el comprobante de la transferencia")
        assert result["classification"] == "payment"
        assert result["is_payment"] is True
        assert result["confidence"] == 1.0

    def test_strong_medical_keyword(self):
        result = classify_message_sync("acá te mando la receta del doctor")
        assert result["classification"] == "medical"
        assert result["is_medical"] is True
        assert result["confidence"] == 1.0

    def test_medical_overrides_payment_with_strong(self):
        result = classify_message_sync("receta y factura del tratamiento")
        assert result["classification"] == "medical"

    def test_weak_payment_single_keyword(self):
        result = classify_message_sync("ya pagué")
        assert result["classification"] == "payment"
        assert result["is_payment"] is True

    def test_amount_pattern_detected(self):
        result = classify_message_sync("te transferí $5000 por el turno")
        assert result["is_payment"] is True

    def test_dental_terms_classified_medical(self):
        result = classify_message_sync("me duele la muela y tengo caries")
        assert result["classification"] == "medical"

    def test_neutral_message(self):
        result = classify_message_sync("hola, ¿cómo están?")
        assert result["classification"] == "neutral"

    def test_custom_payment_keywords(self):
        result = classify_message_sync(
            "envié el voucher",
            payment_keywords=["voucher"],
        )
        assert result["is_payment"] is True


class TestClassifyMessageAsync:
    @patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock)
    async def test_vision_description_classified(self, mock_keywords):
        mock_keywords.return_value = {
            "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
            "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
        }
        result = await classify_message(
            text="",
            tenant_id=1,
            vision_description="Comprobante de transferencia bancaria por $3500 del Banco Nación",
        )
        assert result["is_payment"] is True
        assert result["classification"] == "payment"

    @patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock)
    async def test_vision_medical_document(self, mock_keywords):
        mock_keywords.return_value = {
            "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
            "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
        }
        result = await classify_message(
            text="",
            tenant_id=1,
            vision_description="Radiografía panorámica dental con implante en pieza 36",
        )
        assert result["is_medical"] is True
        assert result["classification"] == "medical"

    @patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock)
    async def test_vision_weight_double(self, mock_keywords):
        """Vision matches count 2x — a single vision payment keyword should reach weight >= 2."""
        mock_keywords.return_value = {
            "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
            "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
        }
        result = await classify_message(
            text="",
            tenant_id=1,
            vision_description="pago registrado",
        )
        assert result["is_payment"] is True

    @patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock)
    async def test_empty_inputs_neutral(self, mock_keywords):
        result = await classify_message(text="", tenant_id=1, vision_description=None)
        assert result["classification"] == "neutral"
        mock_keywords.assert_not_awaited()

    @patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock)
    async def test_text_plus_vision_combined(self, mock_keywords):
        mock_keywords.return_value = {
            "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
            "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
        }
        result = await classify_message(
            text="acá va el comprobante",
            tenant_id=1,
            vision_description="transferencia por $2000",
        )
        assert result["is_payment"] is True
        assert result["confidence"] >= 0.8

    @patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock)
    async def test_strong_medical_overrides_payment_vision(self, mock_keywords):
        mock_keywords.return_value = {
            "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
            "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
        }
        result = await classify_message(
            text="",
            tenant_id=1,
            vision_description="Receta médica con indicación de implante dental y factura adjunta",
        )
        # Strong medical (receta, implante) should override payment (factura)
        assert result["classification"] == "medical"

    @patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock)
    async def test_pdf_medical_keywords(self, mock_keywords):
        mock_keywords.return_value = {
            "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
            "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
        }
        result = await classify_message(
            text="",
            tenant_id=1,
            vision_description="Informe de análisis de sangre con resultados de laboratorio",
        )
        assert result["classification"] == "medical"


class TestClassifyFromVision:
    @patch("services.image_classifier.get_tenant_keywords", new_callable=AsyncMock)
    async def test_delegates_to_classify_message(self, mock_keywords):
        mock_keywords.return_value = {
            "payment_keywords": DEFAULT_PAYMENT_KEYWORDS,
            "medical_keywords": DEFAULT_MEDICAL_KEYWORDS,
        }
        result = await classify_from_vision(
            vision_description="Comprobante bancario",
            tenant_id=1,
        )
        assert result["is_payment"] is True


class TestGetTenantKeywords:
    @patch("db.get_pool")
    async def test_returns_tenant_custom_keywords(self, mock_get_pool):
        mock_pool = AsyncMock()
        mock_pool.fetchrow = AsyncMock(return_value={
            "payment_kw": ["custom_pago"],
            "medical_kw": ["custom_medico"],
        })
        mock_get_pool.return_value = mock_pool

        from services.image_classifier import get_tenant_keywords
        result = await get_tenant_keywords(tenant_id=1)

        assert result["payment_keywords"] == ["custom_pago"]
        assert result["medical_keywords"] == ["custom_medico"]

    @patch("db.get_pool")
    async def test_returns_defaults_on_db_error(self, mock_get_pool):
        mock_pool = AsyncMock()
        mock_pool.fetchrow = AsyncMock(side_effect=Exception("DB down"))
        mock_get_pool.return_value = mock_pool

        from services.image_classifier import get_tenant_keywords
        result = await get_tenant_keywords(tenant_id=1)

        assert result["payment_keywords"] == DEFAULT_PAYMENT_KEYWORDS
        assert result["medical_keywords"] == DEFAULT_MEDICAL_KEYWORDS

    @patch("db.get_pool")
    async def test_returns_defaults_when_null(self, mock_get_pool):
        mock_pool = AsyncMock()
        mock_pool.fetchrow = AsyncMock(return_value={
            "payment_kw": None,
            "medical_kw": None,
        })
        mock_get_pool.return_value = mock_pool

        from services.image_classifier import get_tenant_keywords
        result = await get_tenant_keywords(tenant_id=1)

        assert result["payment_keywords"] == DEFAULT_PAYMENT_KEYWORDS
        assert result["medical_keywords"] == DEFAULT_MEDICAL_KEYWORDS
