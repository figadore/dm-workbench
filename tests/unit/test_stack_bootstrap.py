"""Local stack bootstrap and managed-source import safety tests."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[2]
BOOTSTRAP = ROOT / "scripts/bootstrap-local-env.sh"
IMPORT = ROOT / "scripts/import-sources.sh"


def test_bootstrap_generates_distinct_persistent_secrets(tmp_path: Path) -> None:
    first = subprocess.run(
        [str(BOOTSTRAP)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    env_path = tmp_path / ".env"
    first_values = _read_env(env_path)

    assert "Created .env" in first.stdout
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    secrets = {
        first_values["POSTGRES_PASSWORD"],
        first_values["DM_API_TOKEN"],
        first_values["DM_SESSION_SECRET"],
        first_values["DM_MODEL_GATEWAY_INTERNAL_TOKEN"],
    }
    assert len(secrets) == 4
    assert all(len(value) == 64 for value in secrets)

    second = subprocess.run(
        [str(BOOTSTRAP)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )

    assert _read_env(env_path) == first_values
    assert "Local runtime configuration is ready" in second.stdout
    assert first_values["DM_API_TOKEN"] not in second.stdout


def test_bootstrap_replaces_documented_placeholders(tmp_path: Path) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "POSTGRES_PASSWORD=replace-database\n"
        "DM_API_TOKEN=replace-api\n"
        "DM_SESSION_SECRET=replace-session\n"
        "# DM_MODEL_GATEWAY_INTERNAL_TOKEN=replace-gateway\n",
        encoding="utf-8",
    )

    subprocess.run([str(BOOTSTRAP)], cwd=tmp_path, check=True, capture_output=True)

    values = _read_env(env_path)
    assert all(not value.startswith("replace-") for value in values.values())
    assert "DM_MODEL_GATEWAY_INTERNAL_TOKEN" in values


def test_source_import_rejects_symlinks_before_container_access(
    tmp_path: Path,
) -> None:
    source = tmp_path / "sources"
    source.mkdir()
    (source / "actual.md").write_text("synthetic", encoding="utf-8")
    (source / "linked.md").symlink_to(source / "actual.md")

    result = subprocess.run(
        [str(IMPORT), "campaign", str(source)],
        env={**os.environ, "CONTAINER_ENGINE": "must-not-run"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "cannot contain symbolic links" in result.stderr


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values
