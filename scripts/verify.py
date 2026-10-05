"""Full repository verification: uv run --project backend --locked python scripts/verify.py."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(label, command, cwd):
    print(f"\n{label}", flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def main():
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    uv = shutil.which("uv")
    if not npm or not uv or not shutil.which("docker"):
        print("Verification requires npm, uv, and Docker on PATH. See README.md.")
        return 1
    if not (ROOT / "frontend" / "node_modules").is_dir():
        print("Install frontend dependencies first: cd frontend, then npm ci.")
        return 1
    backend = ROOT / "backend"
    frontend = ROOT / "frontend"
    try:
        run("Backend architecture boundaries", [sys.executable, "scripts/check_boundaries.py"], ROOT)
        run(
            "Python lint (backend and verification scripts)",
            [uv, "run", "--locked", "ruff", "check", "--config", "pyproject.toml", ".", "../scripts"],
            backend,
        )
        run("Frontend lint", [npm, "run", "lint"], frontend)
        run("Frontend types", [npm, "run", "typecheck"], frontend)
        run("Frontend production build", [npm, "run", "build"], frontend)
        run(
            "Backend tests with disposable PostgreSQL (no skips)",
            [uv, "run", "--locked", "python", "scripts/verify_phase2.py"],
            backend,
        )
    except subprocess.CalledProcessError as exc:
        print(f"\nVerification failed (exit {exc.returncode}).", flush=True)
        return exc.returncode if exc.returncode > 0 else 1
    except OSError as exc:
        print(f"\nCannot run verification: {exc}", flush=True)
        return 1
    print("\nFull repository verification passed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
