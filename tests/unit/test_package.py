"""Package-level tests."""

import dm_assistant


def test_package_exposes_version() -> None:
    assert dm_assistant.__version__ == "0.1.0"
