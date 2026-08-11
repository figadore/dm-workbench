"""Synthetic Workbench unit-test configuration."""

from pathlib import Path

import pytest

from dm_assistant.config import RuntimeEnvironment, Settings

TEST_API_TOKEN = "unit-test-token-000000000000000000"


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    source_root = tmp_path / "sources"
    source_root.mkdir()
    return Settings(
        environment=RuntimeEnvironment.TEST,
        database_url="postgresql+psycopg://test_user:test_password@db/test_db",
        source_roots=(source_root,),
        asset_root=tmp_path / "assets",
        scratch_root=tmp_path / "scratch",
        api_token=TEST_API_TOKEN,
        session_secret="unit-session-secret-000000000000000",
    )
