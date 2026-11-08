"""The frontend and the backend never import each other's code."""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def imported_top_level_modules(package: str) -> set[str]:
    modules = set()
    for path in (ROOT / package).rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules.add(node.module.split(".")[0])
    return modules


@pytest.mark.parametrize(
    ("package", "forbidden"), [("frontend", "backend"), ("backend", "frontend")]
)
def test_no_cross_imports(package, forbidden):
    assert forbidden not in imported_top_level_modules(package)
