"""Application readiness orchestration and safe CLI rendering."""

import json
from collections.abc import Callable

from sqlalchemy import Engine

from dm_assistant.config import Settings, load_settings
from dm_assistant.db import build_engine
from dm_assistant.errors import ConfigurationError
from dm_assistant.readiness import (
    ReadinessReport,
    check_readiness,
    configuration_failure_report,
)

SettingsLoader = Callable[[], Settings]
EngineBuilder = Callable[[Settings], Engine]
ReadinessProbe = Callable[[Engine], ReadinessReport]


def collect_doctor_report(
    *,
    settings_loader: SettingsLoader = load_settings,
    engine_builder: EngineBuilder = build_engine,
    readiness_probe: ReadinessProbe = check_readiness,
) -> ReadinessReport:
    """Validate full settings, probe dependencies, and always dispose the engine."""
    try:
        settings = settings_loader()
    except ConfigurationError:
        return configuration_failure_report()
    engine = engine_builder(settings)
    try:
        return readiness_probe(engine)
    finally:
        engine.dispose()


def render_doctor_json(report: ReadinessReport) -> str:
    """Render deterministic machine-readable diagnostics."""
    return json.dumps(
        report.doctor_payload(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def render_doctor_human(report: ReadinessReport) -> str:
    """Render stable human diagnostics without any configuration values."""
    lines: list[str] = []
    for component in report.components:
        details: list[str] = []
        if component.version is not None:
            details.append(f"version={component.version}")
        if component.expected_version is not None:
            details.append(f"expected={component.expected_version}")
        if component.code is not None:
            details.append(f"reason={component.code.value}")
        suffix = f" ({', '.join(details)})" if details else ""
        lines.append(f"{component.name.value}: {component.state.value}{suffix}")
    lines.append(f"overall: {'ready' if report.ready else 'not_ready'}")
    return "\n".join(lines)
