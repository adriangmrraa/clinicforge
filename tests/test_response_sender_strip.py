"""
Unit tests para _strip_internal_markers en response_sender.
Verifica que los marcadores [INTERNAL_*:*] no lleguen al paciente.
"""
import sys
import os

# Asegurar que el módulo sea importable sin dependencias de runtime
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'orchestrator_service', 'services'))

from response_sender import _strip_internal_markers


def test_single_price_marker_in_middle():
    """Caso 1: marcador INTERNAL_PRICE en el medio del texto → eliminado."""
    text = "Tenés disponibilidad el martes [INTERNAL_PRICE:7000000]"
    result = _strip_internal_markers(text)
    assert "[INTERNAL_PRICE:7000000]" not in result
    assert "Tenés disponibilidad el martes" in result


def test_debt_marker_at_end():
    """Caso 2: marcador INTERNAL_DEBT al final → eliminado."""
    text = "Tu saldo pendiente es bajo [INTERNAL_DEBT:50000]"
    result = _strip_internal_markers(text)
    assert "[INTERNAL_DEBT:50000]" not in result
    assert "Tu saldo pendiente es bajo" in result


def test_multiple_markers_in_same_text():
    """Caso 3: múltiples marcadores en el mismo texto → todos eliminados."""
    text = "[INTERNAL_FOO:bar] texto [INTERNAL_PRICE:1000] fin"
    result = _strip_internal_markers(text)
    assert "[INTERNAL_FOO:bar]" not in result
    assert "[INTERNAL_PRICE:1000]" not in result
    assert "texto" in result
    assert "fin" in result


def test_text_without_markers_unchanged():
    """Caso 4: texto sin marcadores → salida idéntica al input."""
    text = "Texto sin marcadores"
    result = _strip_internal_markers(text)
    assert result == text


def test_marker_with_spaces_in_value():
    """Caso 5: marcador con valor que contiene espacios → eliminado."""
    text = "algo [INTERNAL_FOO:bar baz] más texto"
    result = _strip_internal_markers(text)
    assert "[INTERNAL_FOO:bar baz]" not in result
    assert "algo" in result
    assert "más texto" in result


def test_only_markers_produces_empty_or_whitespace():
    """Caso extra: texto compuesto solo de marcadores → vacío tras strip."""
    text = "[INTERNAL_PRICE:7000000][INTERNAL_DEBT:0]"
    result = _strip_internal_markers(text)
    assert result == ""
