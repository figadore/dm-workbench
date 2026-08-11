"""Package-level tests."""

from importlib.resources import files

import dm_assistant
import dm_assistant.web
import dm_dungeon


def test_package_exposes_version() -> None:
    assert dm_assistant.__version__ == "0.1.0"


def test_distributions_include_web_templates_and_typing_marker() -> None:
    assert files(dm_assistant.web).joinpath("templates/login.html").is_file()
    assert files(dm_dungeon).joinpath("py.typed").is_file()
