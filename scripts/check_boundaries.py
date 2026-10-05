"""Check two observed backend boundaries without importing application code."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOWER_LAYERS = ("models", "repositories", "schemas")
TRANSACTION_METHODS = {"commit", "rollback", "begin", "begin_nested"}


def imported_modules(node, package):
    """Resolve static imports, including relative and `from app import services`."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if not isinstance(node, ast.ImportFrom):
        return []
    if node.level:
        parts = package.split(".")
        base = ".".join(parts[: len(parts) - node.level + 1])
        module = ".".join(part for part in (base, node.module) if part)
    else:
        module = node.module or ""
    return [module, *(f"{module}.{alias.name}" for alias in node.names)]


def check_source(source, relative_path):
    """Return location-bearing diagnostics for a lower-layer Python file."""
    relative_path = Path(relative_path)
    tree = ast.parse(source, filename=str(relative_path))
    package = ".".join(relative_path.parent.parts[1:])  # backend/app/... -> app...
    repository = "repositories" in relative_path.parts[2:3]
    errors = []
    for node in ast.walk(tree):
        for module in imported_modules(node, package):
            if any(
                module == banned or module.startswith(f"{banned}.")
                for banned in ("app.api", "app.services")
            ):
                errors.append(
                    f"{relative_path.as_posix()}:{node.lineno}: "
                    f"lower layers cannot import {module}; keep orchestration in callers"
                )
                break
        if (
            repository
            and isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in TRANSACTION_METHODS
        ):
            errors.append(
                f"{relative_path.as_posix()}:{node.lineno}: "
                f"repositories cannot call {node.func.attr}(); callers own transactions"
            )
    return errors


def main():
    errors = []
    for layer in LOWER_LAYERS:
        directory = ROOT / "backend" / "app" / layer
        if not directory.is_dir():
            errors.append(f"Missing expected layer: {directory.relative_to(ROOT)}")
            continue
        for path in sorted(directory.rglob("*.py")):
            try:
                errors.extend(
                    check_source(path.read_text(encoding="utf-8"), path.relative_to(ROOT))
                )
            except SyntaxError as exc:
                errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
    if errors:
        print("\n".join(errors))
        return 1
    print("Backend boundary checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
