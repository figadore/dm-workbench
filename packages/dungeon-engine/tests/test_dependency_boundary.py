"""Dependency-direction tests for the pure dungeon package."""

import ast
import re
import subprocess
import sys
import tomllib
from pathlib import Path

PACKAGE_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src" / "dm_dungeon"
FORBIDDEN_IMPORT_ROOTS = {
    "alembic",
    "anthropic",
    "dm_assistant",
    "fastapi",
    "httpx",
    "litellm",
    "openai",
    "pi_ai",
    "psycopg",
    "requests",
    "sqlalchemy",
    "starlette",
}
FORBIDDEN_MODULE_PARTS = {"repositories", "repository", "retrieval"}


def imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_source_imports_respect_pure_package_boundary() -> None:
    violations: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        for module in imported_module_names(path):
            parts = set(module.split("."))
            root = module.split(".", maxsplit=1)[0]
            if root in FORBIDDEN_IMPORT_ROOTS or parts & FORBIDDEN_MODULE_PARTS:
                violations.append(f"{path.relative_to(PACKAGE_ROOT)} imports {module}")

    assert violations == []


def test_runtime_dependencies_are_limited_to_contract_validation() -> None:
    configuration = tomllib.loads(
        (PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    dependencies = configuration["project"]["dependencies"]
    dependency_names = {
        re.split(r"[<>=!~\s\[]", requirement, maxsplit=1)[0]
        for requirement in dependencies
    }

    assert dependency_names == {"pillow", "pydantic", "reportlab"}


def test_deterministic_package_source_does_not_call_uuid4() -> None:
    offenders: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "uuid4":
                offenders.append(str(path.relative_to(PACKAGE_ROOT)))
            if isinstance(node, ast.Attribute) and node.attr == "uuid4":
                offenders.append(str(path.relative_to(PACKAGE_ROOT)))

    assert offenders == []


def test_layout_source_uses_no_module_global_randomness() -> None:
    offenders: list[str] = []
    layout_root = SOURCE_ROOT / "layout"
    for path in sorted(layout_root.rglob("*.py")):
        for module in imported_module_names(path):
            if module.split(".", maxsplit=1)[0] in {"random", "secrets"}:
                offenders.append(f"{path.relative_to(PACKAGE_ROOT)} imports {module}")

    assert offenders == []


def test_installed_package_imports_without_workbench_configuration() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            "import dm_dungeon; print(dm_dungeon.__version__)",
        ],
        cwd=PACKAGE_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "0.1.0\n"
