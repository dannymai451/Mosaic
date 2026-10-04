"""Run Phase 2 acceptance tests in a disposable PostgreSQL 18 container."""

import json
import os
import secrets
import subprocess
import time
from pathlib import Path


def docker(*args, capture=True):
    return (
        subprocess.check_output(["docker", *args], text=True).strip()
        if capture
        else subprocess.check_call(["docker", *args])
    )


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
        result = subprocess.run(
            ["uv", "run", "pytest", "-ra", "--tb=short"],
            cwd=Path(__file__).resolve().parents[1],
            env=test_env,
            check=False,
        )
        raise SystemExit(result.returncode)
    finally:
        docker("stop", container)


if __name__ == "__main__":
    main()
