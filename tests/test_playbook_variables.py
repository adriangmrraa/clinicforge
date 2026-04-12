"""Tests for playbook variable resolver and substitution."""

import pytest
import tests._import_stubs  # noqa: F401

from services.playbook_variables import substitute_variables


class TestSubstituteVariables:
    def test_basic_substitution(self):
        text = "Hola {{nombre_paciente}}, tu turno es el {{fecha_turno}}"
        variables = {"nombre_paciente": "María", "fecha_turno": "14/05"}
        result = substitute_variables(text, variables)
        assert result == "Hola María, tu turno es el 14/05"

    def test_multiple_same_variable(self):
        text = "{{nombre_paciente}} tiene turno. Confirmanos {{nombre_paciente}}"
        variables = {"nombre_paciente": "Carlos"}
        result = substitute_variables(text, variables)
        assert result == "Carlos tiene turno. Confirmanos Carlos"

    def test_missing_variable_stays_empty(self):
        text = "Hola {{nombre_paciente}}, precio: {{precio}}"
        variables = {"nombre_paciente": "Ana", "precio": ""}
        result = substitute_variables(text, variables)
        assert result == "Hola Ana, precio: "

    def test_none_text(self):
        result = substitute_variables(None, {"x": "y"})
        assert result is None

    def test_empty_text(self):
        result = substitute_variables("", {"x": "y"})
        assert result == ""

    def test_no_variables_in_text(self):
        result = substitute_variables("Hola mundo", {"nombre_paciente": "Test"})
        assert result == "Hola mundo"

    def test_all_16_variables(self):
        variables = {
            "nombre_paciente": "María",
            "apellido_paciente": "López",
            "telefono": "+5491112345678",
            "tratamiento": "Implante Simple",
            "categoria_tratamiento": "implantes",
            "profesional": "Dra. Laura Delgado",
            "fecha_turno": "14/05",
            "hora_turno": "10:00",
            "dia_semana": "lunes",
            "sede": "Sede Norte",
            "precio": "$45.000",
            "saldo_pendiente": "$22.500",
            "dias_sin_turno": "45",
            "link_anamnesis": "https://app.test/anamnesis/1/abc",
            "nombre_clinica": "Clínica Test",
            "nombre_servicio": "Implante Simple",
        }
        text = "{{nombre_paciente}} {{apellido_paciente}} - {{tratamiento}} con {{profesional}} el {{dia_semana}} {{fecha_turno}} a las {{hora_turno}}"
        result = substitute_variables(text, variables)
        assert "María" in result
        assert "López" in result
        assert "Implante Simple" in result
        assert "Dra. Laura Delgado" in result
        assert "lunes" in result
        assert "14/05" in result
        assert "10:00" in result

    def test_aliases_work(self):
        """first_name, treatment_name etc. should also work as variable names."""
        text = "Hi {{first_name}}, your {{treatment_name}} is ready"
        variables = {"first_name": "John", "treatment_name": "Cleaning"}
        result = substitute_variables(text, variables)
        assert result == "Hi John, your Cleaning is ready"
