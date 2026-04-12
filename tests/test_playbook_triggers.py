"""Tests for playbook trigger condition matching."""

import pytest
import tests._import_stubs  # noqa: F401

from jobs.playbook_triggers import _match_treatment_filter


class TestTreatmentFilter:
    def test_exact_match(self):
        assert _match_treatment_filter("cirugia_simple", ["cirugia_simple"]) is True

    def test_exact_no_match(self):
        assert _match_treatment_filter("cirugia_simple", ["implante_simple_risa"]) is False

    def test_wildcard_match(self):
        assert _match_treatment_filter("implante_simple_risa", ["implante_*"]) is True

    def test_wildcard_match_complex(self):
        assert _match_treatment_filter("implante_complejo_cima", ["implante_*"]) is True

    def test_wildcard_no_match(self):
        assert _match_treatment_filter("cirugia_simple", ["implante_*"]) is False

    def test_multiple_filters(self):
        filters = ["implante_*", "cirugia_*", "rehabilitacion_*"]
        assert _match_treatment_filter("cirugia_compleja", filters) is True
        assert _match_treatment_filter("implante_guiado_tomo", filters) is True
        assert _match_treatment_filter("limpieza_dental", filters) is False

    def test_empty_treatment(self):
        assert _match_treatment_filter("", ["implante_*"]) is False

    def test_empty_filters(self):
        assert _match_treatment_filter("cirugia_simple", []) is False

    def test_consulta_wildcard(self):
        assert _match_treatment_filter("consulta_general", ["consulta_*"]) is True
        assert _match_treatment_filter("consulta_urgencia", ["consulta_*"]) is True

    def test_exact_and_wildcard_combined(self):
        filters = ["endodoncia", "cirugia_*"]
        assert _match_treatment_filter("endodoncia", filters) is True
        assert _match_treatment_filter("cirugia_simple", filters) is True
        assert _match_treatment_filter("limpieza_dental", filters) is False
