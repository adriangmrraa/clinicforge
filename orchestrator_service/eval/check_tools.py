"""Chequeo AST de las tools del agente (sin importar main.py ni sus dependencias).

Valida que:
  1. Cada funcion listada en DENTAL_TOOLS este decorada con @tool — si falta,
     AgentExecutor crashea con pydantic ValidationError AL BOOT (incidente
     2026-07-08: _insurance_min_booking_date quedo insertado entre el @tool y
     book_appointment, y el deploy de PRUEBAS entro en crash-loop).
  2. Ningun helper interno (prefijo _) este decorado con @tool — el decorador
     lo convierte en StructuredTool y rompe las llamadas internas directas.

Correr SIEMPRE antes de pushear cambios en main.py:
    python -m eval.check_tools        (desde orchestrator_service/)
"""
import ast
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "main.py"


def main() -> int:
    tree = ast.parse(SRC.read_text(encoding="utf-8"))

    decorated = set()
    helpers_decorated = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in node.decorator_list:
                name = d.id if isinstance(d, ast.Name) else getattr(getattr(d, "func", None), "id", None)
                if name == "tool":
                    decorated.add(node.name)
                    if node.name.startswith("_"):
                        helpers_decorated.append((node.name, node.lineno))

    dental = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "DENTAL_TOOLS" and isinstance(node.value, ast.List):
                    dental = [e.id for e in node.value.elts if isinstance(e, ast.Name)]

    errors = []
    if dental is None:
        errors.append("No encontre la lista DENTAL_TOOLS en main.py")
    else:
        missing = [n for n in dental if n not in decorated]
        if missing:
            errors.append(f"En DENTAL_TOOLS sin @tool (crashea AgentExecutor al boot): {missing}")
    for name, line in helpers_decorated:
        errors.append(f"Helper interno decorado con @tool (rompe llamadas internas): {name} linea {line}")

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print(f"OK: {len(dental)} tools en DENTAL_TOOLS, todas con @tool; ningun helper decorado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
