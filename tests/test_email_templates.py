"""
Tests for email_templates module — country-to-language mapping and template rendering.

Covers:
- _language_from_country mapping for common country codes
- Default to Spanish for unknown country codes
- Template rendering with placeholders
- All required placeholders present in templates
"""

import pytest
from services import email_templates


# ─── _language_from_country tests ───


def test_language_from_country_argentina():
    """AR → Spanish."""
    assert email_templates._language_from_country("AR") == "es"
    assert email_templates._language_from_country("ar") == "es"


def test_language_from_country_united_states():
    """US → English."""
    assert email_templates._language_from_country("US") == "en"
    assert email_templates._language_from_country("us") == "en"


def test_language_from_country_france():
    """FR → French."""
    assert email_templates._language_from_country("FR") == "fr"
    assert email_templates._language_from_country("fr") == "fr"


def test_language_from_country_brazil():
    """BR → Portuguese."""
    assert email_templates._language_from_country("BR") == "pt"
    assert email_templates._language_from_country("br") == "pt"


def test_language_from_country_spain():
    """ES → Spanish (Spain variant could be 'es_ES' but we keep generic 'es')."""
    assert email_templates._language_from_country("ES") == "es"


def test_language_from_country_mexico():
    """MX → Spanish."""
    assert email_templates._language_from_country("MX") == "es"


def test_language_from_country_unknown_default_spanish():
    """Unknown country code defaults to Spanish."""
    assert email_templates._language_from_country("ZZ") == "es"
    assert email_templates._language_from_country("") == "es"
    assert email_templates._language_from_country("XX") == "es"


def test_language_from_country_case_insensitive():
    """Mapping is case‑insensitive."""
    assert email_templates._language_from_country("us") == "en"
    assert email_templates._language_from_country("Us") == "en"
    assert email_templates._language_from_country("US") == "en"


# ─── Template structure tests ───


def test_templates_dict_has_required_languages():
    """PAYMENT_EMAIL_TEMPLATES must contain at least Spanish, English, French, Portuguese."""
    templates = email_templates.PAYMENT_EMAIL_TEMPLATES
    assert "es" in templates
    assert "en" in templates
    assert "fr" in templates
    assert "pt" in templates


def test_each_template_has_subject_and_html():
    """Each language entry must have 'subject' and 'html' keys."""
    templates = email_templates.PAYMENT_EMAIL_TEMPLATES
    for lang, tmpl in templates.items():
        assert "subject" in tmpl
        assert "html" in tmpl
        assert isinstance(tmpl["subject"], str)
        assert isinstance(tmpl["html"], str)


def test_placeholders_in_spanish_template():
    """Spanish template must contain all required placeholders."""
    tmpl = email_templates.PAYMENT_EMAIL_TEMPLATES["es"]
    html = tmpl["html"]
    # Required data placeholders
    assert "{patient_name}" in html
    assert "{clinic_name}" in html
    assert "{appointment_date}" in html
    assert "{appointment_time}" in html or "{appointment_datetime}" in html
    assert "{treatment}" in html
    assert "{amount}" in html
    assert "{payment_method}" in html
    # Clinic details optional but recommended
    # Subject must also contain clinic_name
    assert "{clinic_name}" in tmpl["subject"]


def test_placeholders_in_english_template():
    """English template must contain all required placeholders."""
    tmpl = email_templates.PAYMENT_EMAIL_TEMPLATES["en"]
    html = tmpl["html"]
    assert "{patient_name}" in html
    assert "{clinic_name}" in html
    assert "{appointment_date}" in html
    assert "{appointment_time}" in html or "{appointment_datetime}" in html
    assert "{treatment}" in html
    assert "{amount}" in html
    assert "{payment_method}" in html
    assert "{clinic_name}" in tmpl["subject"]


def test_placeholder_rendering():
    """Test that placeholders are replaced correctly."""
    # Use Spanish template for the test
    from services.email_templates import render_payment_email

    rendered = render_payment_email(
        "es",
        patient_name="Juan Pérez",
        clinic_name="Clínica Salud",
        appointment_date="15/04/2026",
        appointment_time="10:30",
        treatment="Limpieza dental",
        amount="$25.000",
        payment_method="Transferencia bancaria",
        clinic_phone="+54 11 1234-5678",
        clinic_address="Av. Siempreviva 123",
    )
    # Should not contain literal placeholders
    assert "{patient_name}" not in rendered["subject"]
    assert "{patient_name}" not in rendered["html"]
    assert "Juan Pérez" in rendered["html"]
    assert "Clínica Salud" in rendered["html"]
    assert "$25.000" in rendered["html"]


def test_render_with_missing_language_falls_back_to_spanish():
    """If language not in templates, fall back to Spanish."""
    from services.email_templates import render_payment_email

    # 'zz' does not exist → should fall back to 'es'
    rendered = render_payment_email(
        "zz",
        patient_name="Test",
        clinic_name="Test Clinic",
        appointment_date="01/01/2026",
        appointment_time="00:00",
        treatment="Test",
        amount="$0",
        payment_method="Test",
    )
    # Should still produce a subject and html (Spanish template)
    assert rendered["subject"]
    assert rendered["html"]
    # Spanish clinic name placeholder should be replaced
    assert "Test Clinic" in rendered["html"]
