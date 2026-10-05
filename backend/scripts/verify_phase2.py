"""Run Phase 2 acceptance tests in a disposable PostgreSQL 18 container."""

import json
import os
import secrets
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree


def docker(*args, capture=True):
    return (
        subprocess.check_output(["docker", *args], text=True).strip()
        if capture
        else subprocess.check_call(["docker", *args])
    )


def require_complete_suite(report):
    cases = list(ElementTree.parse(report).iter("testcase"))
    if not cases or any(case.find("skipped") is not None for case in cases):
        raise ValueError("Full verification requires a nonempty suite with no skipped tests.")


def main():
    password = secrets.token_urlsafe(24)
    env = {**os.environ, "POSTGRES_PASSWORD": password}
    container = subprocess.check_output(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "-e",
            "POSTGRES_PASSWORD",
            "-p",
            "127.0.0.1::5432",
            "postgres:18",
        ],
        env=env,
        text=True,
    ).strip()
    try:
        for _ in range(60):
            ready = subprocess.run(
                ["docker", "exec", container, "pg_isready", "-U", "postgres"],
                capture_output=True,
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Test PostgreSQL did not become ready")
        info = json.loads(docker("inspect", container))[0]
        port = info["NetworkSettings"]["Ports"]["5432/tcp"][0]["HostPort"]
        test_env = {
            **os.environ,
            "TEST_DATABASE_URL": f"postgresql+asyncpg://postgres:{password}@127.0.0.1:{port}/postgres",
        }
        with TemporaryDirectory(prefix="mosaic-verification-") as report_dir:
            report = Path(report_dir) / "pytest.xml"
            result = subprocess.run(
                [
                    "uv", "run", "--locked", "pytest", "-ra", "--tb=short",
                    "-p", "no:cacheprovider", f"--junitxml={report}",
                ],
                cwd=Path(__file__).resolve().parents[1],
                env=test_env,
                check=False,
            )
            if result.returncode:
                raise SystemExit(result.returncode)
            try:
                require_complete_suite(report)
            except ValueError as exc:
                print(exc)
                raise SystemExit(1) from exc
    finally:
        docker("stop", container)


if __name__ == "__main__":
    main()
