"""
Validación predictiva de datos - FASE 1
Implementa validación proactiva antes de tool calls para reducir errores
"""

import re
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger(__name__)

class DataValidator:
    """Validador predictivo para datos de pacientes y turnos"""
    
    @staticmethod
    def validate_dni_format(dni: str) -> Tuple[bool, str]:
        """
        Valida formato de DNI argentino
        Formato aceptado: 8-9 dígitos numéricos
        """
        if not dni:
            return False, "DNI no puede estar vacío"
        
        # Limpiar espacios y puntos
        dni_clean = dni.strip().replace(".", "").replace(" ", "")
        
        # Validar que sean solo números
        if not dni_clean.isdigit():
            return False, "DNI debe contener solo números"
        
        # Validar longitud (Argentina: 7-8 dígitos, pero aceptamos 6-9)
        if len(dni_clean) < 6 or len(dni_clean) > 9:
            return False, f"DNI debe tener entre 6 y 9 dígitos (tiene {len(dni_clean)})"
        
        return True, dni_clean
    
    @staticmethod
    def validate_date_not_past(date_str: str) -> Tuple[bool, str]:
        """
        Valida que la fecha no sea pasada
        Formato esperado: YYYY-MM-DD HH:MM:SS o variantes
        """
        try:
            # Intentar diferentes formatos
            formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M",
                "%Y-%m-%d",
                "%d/%m/%Y %H:%M:%S",
                "%d/%m/%Y %H:%M",
                "%d/%m/%Y"
            ]
            
            parsed_date = None
            for fmt in formats:
                try:
                    parsed_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            
            if not parsed_date:
                return False, f"Formato de fecha no reconocido: {date_str}"
            
            # Comparar con fecha actual (sin hora)
            today = datetime.now().date()
            if parsed_date.date() < today:
                return False, f"La fecha {parsed_date.date()} ya pasó"
            
            return True, "Fecha válida"
            
        except Exception as e:
            logger.error(f"Error validando fecha {date_str}: {e}")
            return False, f"Error validando fecha: {str(e)}"
    
    @staticmethod
    def validate_email_format(email: str) -> Tuple[bool, str]:
        """
        Valida formato básico de email
        """
        if not email or email == "sin_email@placeholder.com":
            return True, "Email placeholder aceptado"
        
        # Expresión regular básica para email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if re.match(email_pattern, email):
            return True, "Email válido"
        else:
            return False, "Formato de email inválido"
    
    @staticmethod
    def validate_name_length(name: str, field_name: str = "nombre") -> Tuple[bool, str]:
        """
        Valida longitud y formato de nombres
        """
        if not name or not name.strip():
            return False, f"{field_name.capitalize()} no puede estar vacío"
        
        name_clean = name.strip()
        
        # Validar longitud mínima
        if len(name_clean) < 2:
            return False, f"{field_name.capitalize()} debe tener al menos 2 caracteres"
        
        # Validar longitud máxima
        if len(name_clean) > 50:
            return False, f"{field_name.capitalize()} no puede exceder 50 caracteres"
        
        # Validar que contenga al menos una letra
        if not any(c.isalpha() for c in name_clean):
            return False, f"{field_name.capitalize()} debe contener al menos una letra"
        
        return True, "Nombre válido"
    
    @staticmethod
    def validate_date_query(date_query: str) -> Tuple[bool, str]:
        """
        Valida consultas de fecha como 'hoy', 'mañana', 'lunes', etc.
        """
        if not date_query or not date_query.strip():
            return False, "Consulta de fecha vacía"
        
        date_query_lower = date_query.strip().lower()
        
        # Términos relativos aceptados
        relative_terms = [
            'hoy', 'mañana', 'pasado mañana', 'ayer',
            'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo',
            'esta semana', 'la semana que viene', 'próxima semana',
            'tarde', 'mañana'  # horarios
        ]
        
        # También aceptar fechas específicas
        date_patterns = [
            r'\d{1,2}/\d{1,2}/\d{4}',  # DD/MM/YYYY
            r'\d{4}-\d{1,2}-\d{1,2}',  # YYYY-MM-DD
            r'\d{1,2} de [a-z]+',      # 15 de marzo
        ]
        
        # Verificar si es término relativo
        if date_query_lower in relative_terms:
            return True, "Término relativo válido"
        
        # Verificar si coincide con algún patrón de fecha
        for pattern in date_patterns:
            if re.search(pattern, date_query_lower):
                return True, "Fecha específica válida"
        
        # Si no es ninguno, podría ser un error
        return False, f"Consulta de fecha no reconocida: {date_query}"


class ToolValidator:
    """Validador específico para herramientas del agente"""
    
    def __init__(self):
        self.data_validator = DataValidator()
    
    def validate_before_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecuta validación predictiva antes de llamar a una tool
        Retorna dict con {is_valid: bool, errors: List[str], warnings: List[str]}
        """
        validators_map = {
            "book_appointment": self._validate_book_appointment,
            "check_availability": self._validate_check_availability,
            "get_service_details": self._validate_get_service_details,
            "save_patient_anamnesis": self._validate_save_patient_anamnesis,
        }
        
        if tool_name not in validators_map:
            logger.warning(f"No hay validadores definidos para tool: {tool_name}")
            return {"is_valid": True, "errors": [], "warnings": []}
        
        validator_func = validators_map[tool_name]
        return validator_func(params)
    
    def _validate_book_appointment(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Valida parámetros para book_appointment"""
        errors = []
        warnings = []
        
        # Validar fecha/hora
        if "date_time" in params:
            is_valid, msg = self.data_validator.validate_date_not_past(params["date_time"])
            if not is_valid:
                errors.append(f"Fecha/hora inválida: {msg}")
        
        # Validar tratamiento
        if "treatment_reason" not in params or not params["treatment_reason"]:
            errors.append("Tratamiento no especificado")
        
        # Validar datos del paciente (si es nuevo)
        if "first_name" in params:
            is_valid, msg = self.data_validator.validate_name_length(params["first_name"], "nombre")
            if not is_valid:
                errors.append(f"Nombre inválido: {msg}")
        
        if "last_name" in params:
            is_valid, msg = self.data_validator.validate_name_length(params["last_name"], "apellido")
            if not is_valid:
                errors.append(f"Apellido inválido: {msg}")
        
        if "dni" in params:
            is_valid, msg = self.data_validator.validate_dni_format(params["dni"])
            if not is_valid:
                errors.append(f"DNI inválido: {msg}")
        
        # Validar email si está presente
        if "email" in params and params["email"]:
            is_valid, msg = self.data_validator.validate_email_format(params["email"])
            if not is_valid:
                warnings.append(f"Email inválido: {msg}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_check_availability(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Valida parámetros para check_availability"""
        errors = []
        warnings = []
        
        # Validar consulta de fecha
        if "date_query" in params:
            is_valid, msg = self.data_validator.validate_date_query(params["date_query"])
            if not is_valid:
                errors.append(f"Consulta de fecha inválida: {msg}")
        else:
            errors.append("Consulta de fecha requerida")
        
        # Validar tratamiento
        if "treatment_name" not in params or not params["treatment_name"]:
            errors.append("Nombre de tratamiento requerido")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    def _validate_get_service_details(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Valida parámetros para get_service_details"""
        errors = []
        
        # Validar código de servicio
        if "code" not in params or not params["code"]:
            errors.append("Código de servicio requerido")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": []
        }
    
    def _validate_save_patient_anamnesis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Valida parámetros para save_patient_anamnesis"""
        errors = []
        warnings = []
        
        # Validar que haya algún dato
        required_fields = ["patient_id", "tenant_id"]
        for field in required_fields:
            if field not in params or not params[field]:
                errors.append(f"Campo requerido: {field}")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }


# Instancia global para uso fácil
tool_validator = ToolValidator()


def validate_before_tool(tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Función de conveniencia para validación predictiva
    """
    return tool_validator.validate_before_tool(tool_name, params)