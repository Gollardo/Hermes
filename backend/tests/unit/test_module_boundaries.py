import ast
from pathlib import Path


def test_import_application_uses_only_operations_public_contract() -> None:
    backend = Path(__file__).resolve().parents[2]
    source = (backend / "app/application/imports.py").read_text(encoding="utf-8")
    imports = [
        node.module
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("app.modules.operations")
    ]

    assert imports == ["app.modules.operations.contracts"]
