"""Verification must fail closed on a failed check or skipped database suite."""

import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def load_script(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


database_runner = load_script("database_runner", ROOT / "backend/scripts/verify_phase2.py")
verifier = load_script("verifier", ROOT / "scripts/verify.py")


@pytest.mark.parametrize(
    "body",
    [
        "",
        '<testcase name="db"><skipped message="database unavailable" /></testcase>',
        '<testcase name="db"><skipped type="pytest.xfail" /></testcase>',
    ],
)
def test_rejects_empty_or_skipped_suite(tmp_path, body):
    report = tmp_path / "report.xml"
    report.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>")
    with pytest.raises(ValueError, match="nonempty suite with no skipped tests"):
        database_runner.require_complete_suite(report)


def test_accepts_complete_suite(tmp_path):
    report = tmp_path / "report.xml"
    report.write_text('<testsuites><testsuite><testcase name="db" /></testsuite></testsuites>')
    database_runner.require_complete_suite(report)


def test_verification_stops_and_returns_failure(tmp_path, monkeypatch):
    (tmp_path / "frontend/node_modules").mkdir(parents=True)
    monkeypatch.setattr(verifier, "ROOT", tmp_path)
    monkeypatch.setattr(verifier.shutil, "which", lambda name: name)
    calls = []

    def fail_first_check(label, command, cwd):
        calls.append(label)
        raise subprocess.CalledProcessError(7, command)

    monkeypatch.setattr(verifier, "run", fail_first_check)
    assert verifier.main() == 7
    assert calls == ["Backend architecture boundaries"]
