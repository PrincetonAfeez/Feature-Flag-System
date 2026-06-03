"""Tests for the decoupling of the core from Django."""

import ast
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[2] / "flags_core"


def test_flags_core_imports_no_django_modules():
    paths = list(CORE_ROOT.rglob("*.py"))
    # Guard against a silently-empty sweep (e.g. wrong cwd): the assertion below
    # would pass vacuously if no files were found.
    assert paths, f"no core modules found under {CORE_ROOT}"

    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "django" not in alias.name, f"{path} imports {alias.name}"
            if isinstance(node, ast.ImportFrom):
                assert "django" not in (node.module or ""), f"{path} imports from {node.module}"
