"""P7-15b private creative capture; all responses and secrets are synthetic."""

import copy
import json
import runpy
import stat
import sys
from pathlib import Path

import pytest

from dm_assistant.modules.modeling import PromptMessage, ToolCall
from dm_assistant.orchestration.dungeons.trial_capture import (
    PrivateTrialCapture,
    TrialCaptureError,
)
from dm_assistant.orchestration.dungeons.whole_adventure_prototype import (
    TOOL,
    build_fixed_map,
    run_trial,
)
from dm_assistant.orchestration.modeling.service import ModelTransportError
from dm_dungeon import DungeonPlan

ROOT = Path(__file__).resolve().parents[2]
ADAPTER = runpy.run_path(str(ROOT / "scripts/dungeon-whole-adventure-prototype.py"))
FIXTURES = ROOT / "tests/evals/golden/whole_adventure"


@pytest.fixture
def inputs():
    return {
        "profile": ADAPTER["fixture_profile"](),
        "fixed": build_fixed_map(
            DungeonPlan.model_validate_json((FIXTURES / "plan.json").read_bytes())
        ),
        "brief": json.loads((FIXTURES / "cases.json").read_text())[0],
        "consistency": True,
    }


def response():
    return json.loads((FIXTURES / "signal_house.json").read_text())


@pytest.mark.parametrize("failure", ("schema", "reference"))
def test_capture_saves_actual_dispatch_and_rejected_candidate_before_validation(
    tmp_path, inputs, failure
):
    from dm_assistant.orchestration.dungeons.trial_capture import PrivateTrialCapture

    capture = PrivateTrialCapture(tmp_path / "creative-capture")
    inputs["profile"] = inputs["profile"].model_copy(
        update={
            "observed_capabilities": (
                "text",
                "tool_calls",
                "json_schema_constrained_sampling",
            ),
        }
    )
    bad = response()
    if failure == "schema":
        del bad["pitch"]
    else:
        bad["guide_content"]["room_narratives"][0]["room_ref"] = "absent"
    original_bad = copy.deepcopy(bad)

    class Gateway(ADAPTER["FixtureGateway"]):
        def complete(self, **kwargs):
            number = self.calls + 1
            request = json.loads(
                (capture.directory / f"{number:02d}-request.json").read_text()
            )
            assert request == {
                "profile": kwargs["profile"].model_dump(mode="json"),
                "messages": [
                    message.model_dump(mode="json") for message in kwargs["messages"]
                ],
                "allowed_tools": list(kwargs["allowed_tools"]),
                "tool_schemas": [
                    schema.model_dump(mode="json") for schema in kwargs["tool_schemas"]
                ],
            }
            assert request["tool_schemas"][0]["constrained_sampling"] == "prefer"
            journal = json.loads((capture.directory / "journal.json").read_text())
            assert journal["creative_capture_enabled"] is True
            assert journal["attempts"][-1]["dispatched"] is True
            if number == 2:
                rejected = json.loads(
                    (capture.directory / "01-candidates.json").read_text()
                )
                assert rejected == [original_bad]
                assert any(
                    "Rejected submission data:" in message["content"]
                    for message in request["messages"]
                )
                assert (
                    kwargs["profile"].token_budget
                    == inputs["profile"].token_budget - 12000
                )
            return super().complete(**kwargs)

    gateway = Gateway([bad, response()])
    accepted, report = run_trial(gateway, **inputs, capture=capture)
    assert accepted is not None and gateway.calls == 2
    assert json.loads((capture.directory / "02-candidates.json").read_text()) == [
        response()
    ]
    assert json.loads((capture.directory / "journal.json").read_text()) == report
    assert (
        report["attempts"][0]["status"]
        == f"{failure if failure == 'schema' else 'references'}_rejected"
    )
    assert "Inspection complete" not in json.dumps(report)
    assert stat.S_IMODE(capture.directory.stat().st_mode) == 0o700
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o600
        for path in capture.directory.iterdir()
    )


def test_capture_is_absent_by_default(tmp_path, inputs, monkeypatch):
    monkeypatch.chdir(tmp_path)
    accepted, report = run_trial(ADAPTER["FixtureGateway"]([response()]), **inputs)
    assert accepted is not None
    assert report["creative_capture_enabled"] is False
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind", ("unauthorized", "multiple", "overage"))
def test_capture_excludes_noncreative_fields_even_when_runner_rejects(
    tmp_path, inputs, kind, monkeypatch
):
    monkeypatch.setenv(
        "DM_MODEL_GATEWAY_INTERNAL_TOKEN", "synthetic-credential-sentinel"
    )
    capture = PrivateTrialCapture(tmp_path / "capture")

    class Gateway(ADAPTER["FixtureGateway"]):
        secret = "synthetic-credential-sentinel"

        def complete(self, **kwargs):
            completion = super().complete(**kwargs)
            calls = completion.tool_calls
            if kind == "unauthorized":
                calls = (
                    ToolCall(
                        tool_name="approve_preparation",
                        call_id="private-call-id",
                        arguments={"private": "unrelated-tool-sentinel"},
                    ),
                )
            elif kind == "multiple":
                calls = (
                    *calls,
                    calls[0].model_copy(update={"call_id": "private-call-id"}),
                )
            return completion.model_copy(
                update={
                    "content": "commentary-and-reasoning-sentinel",
                    "tool_calls": calls,
                    "output_tokens": 16001 if kind == "overage" else 2000,
                }
            )

    accepted, report = run_trial(Gateway([response()]), **inputs, capture=capture)
    assert accepted is None and len(report["attempts"]) == 1
    candidates = json.loads((capture.directory / "01-candidates.json").read_text())
    assert candidates == (
        []
        if kind == "unauthorized"
        else [response()] * (2 if kind == "multiple" else 1)
    )
    captured = "".join(path.read_text() for path in capture.directory.iterdir())
    for sentinel in (
        "synthetic-credential-sentinel",
        "unrelated-tool-sentinel",
        "private-call-id",
        "commentary-and-reasoning-sentinel",
    ):
        assert sentinel not in captured


@pytest.mark.parametrize(
    "filename,expected_calls",
    (
        ("01-request.json", 0),
        ("02-request.json", 1),
        ("01-candidates.json", 1),
        ("journal.json", 0),
    ),
)
def test_capture_write_failure_stops_without_dispatch_or_retry(
    tmp_path, inputs, monkeypatch, filename, expected_calls
):
    import dm_assistant.orchestration.dungeons.trial_capture as storage

    capture = PrivateTrialCapture(tmp_path / "capture")
    original_link, original_replace = storage.os.link, storage.os.replace

    def fail_selected(source, destination):
        if Path(destination).name == filename:
            raise OSError("synthetic-private-filesystem-error")
        (
            original_replace
            if Path(destination).name == "journal.json"
            else original_link
        )(source, destination)

    monkeypatch.setattr(storage.os, "link", fail_selected)
    monkeypatch.setattr(storage.os, "replace", fail_selected)
    gateway = ADAPTER["FixtureGateway"]([{}, response()])
    with pytest.raises(TrialCaptureError) as error:
        run_trial(gateway, **inputs, capture=capture)
    assert "synthetic-private" not in str(error.value)
    assert gateway.calls == expected_calls
    assert not (capture.directory / filename).exists()
    assert not (capture.directory / "02-candidates.json").exists()
    if expected_calls:
        assert (capture.directory / "01-request.json").exists()
    if filename != "journal.json":
        journal = json.loads((capture.directory / "journal.json").read_text())
        assert journal["accepted"] is False
        assert journal["attempts"][-1]["status"] == "capture_failed"


@pytest.mark.parametrize("cancel", ("interrupt", "transport"))
def test_interrupted_attempt_remains_truthfully_incomplete(tmp_path, inputs, cancel):
    capture = PrivateTrialCapture(tmp_path / "capture")

    class Gateway:
        calls = 0

        def complete(self, **kwargs):
            self.calls += 1
            if cancel == "interrupt":
                raise KeyboardInterrupt
            raise ModelTransportError("private-error-sentinel", code="cancelled")

    gateway = Gateway()
    if cancel == "interrupt":
        with pytest.raises(KeyboardInterrupt):
            run_trial(gateway, **inputs, capture=capture)
    else:
        accepted, report = run_trial(gateway, **inputs, capture=capture)
        assert accepted is None and report["terminal_code"] == "cancelled"
    journal = json.loads((capture.directory / "journal.json").read_text())
    assert journal["accepted"] is False
    assert journal["attempts"][0]["capture_request"] == "saved"
    assert journal["attempts"][0]["capture_candidates"] == "pending"
    assert journal["attempts"][0]["input_tokens"] is None
    assert not (capture.directory / "01-candidates.json").exists()
    assert gateway.calls == 1
    assert "private-error-sentinel" not in json.dumps(journal)


def test_slow_capture_cannot_dispatch_after_cumulative_deadline(
    tmp_path, inputs, monkeypatch
):
    import dm_assistant.orchestration.dungeons.whole_adventure_prototype as prototype

    now = prototype.time.monotonic()

    class SlowCapture(PrivateTrialCapture):
        def request(self, *args, **kwargs):
            super().request(*args, **kwargs)
            monkeypatch.setattr(prototype.time, "monotonic", lambda: now + 1000)

    capture = SlowCapture(tmp_path / "capture")
    gateway = ADAPTER["FixtureGateway"]([response()])
    accepted, report = run_trial(gateway, **inputs, capture=capture)
    assert accepted is None and gateway.calls == 0
    assert report["terminal_code"] == "submission_time_budget_exhausted"
    assert report["attempts"][0]["capture_request"] == "saved"
    assert report["attempts"][0]["dispatched"] is False
    assert not (capture.directory / "01-candidates.json").exists()


def test_capture_refuses_overwrite_reuse_and_symlinks(tmp_path, inputs):
    capture = PrivateTrialCapture(tmp_path / "capture")
    run_trial(ADAPTER["FixtureGateway"]([response()]), **inputs, capture=capture)
    before = {path.name: path.read_bytes() for path in capture.directory.iterdir()}
    with pytest.raises(TrialCaptureError):
        PrivateTrialCapture(capture.directory)
    with pytest.raises(TrialCaptureError):
        run_trial(ADAPTER["FixtureGateway"]([response()]), **inputs, capture=capture)
    link = tmp_path / "symlink"
    link.symlink_to(capture.directory, target_is_directory=True)
    with pytest.raises(TrialCaptureError):
        PrivateTrialCapture(link)
    assert before == {
        path.name: path.read_bytes() for path in capture.directory.iterdir()
    }
    with pytest.raises(TrialCaptureError):
        capture._write_json("01-candidates.json", ["replacement"])
    assert (capture.directory / "01-candidates.json").read_bytes() == before[
        "01-candidates.json"
    ]


@pytest.mark.parametrize(
    "message",
    (
        PromptMessage(role="assistant", content="private commentary"),
        PromptMessage(
            role="user",
            content="synthetic input",
            opaque_continuity_signatures=("private-signature",),
        ),
    ),
)
def test_capture_refuses_transcript_reasoning_or_signatures(tmp_path, inputs, message):
    capture = PrivateTrialCapture(tmp_path / "capture")
    with pytest.raises(TrialCaptureError):
        capture.request(
            1,
            profile=inputs["profile"],
            messages=(message,),
            allowed_tools=(TOOL.name,),
            tool_schemas=(TOOL.gateway_schema(),),
        )
    assert not (capture.directory / "01-request.json").exists()


@pytest.mark.parametrize("enabled", (False, True))
def test_cli_capture_opt_in_is_private_ignored_and_does_not_enable_live(
    tmp_path, monkeypatch, enabled
):
    output = tmp_path / "packet"
    args = [
        "prototype",
        "--output",
        str(output),
        "--consistency",
        "on",
        "--scenario",
        "reference-repair",
    ]
    if enabled:
        args.append("--retain-creative-candidates")
    monkeypatch.setattr(sys, "argv", args)
    assert ADAPTER["main"]() == 0
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["live_calls"] == 0
    assert manifest["creative_capture_enabled"] is enabled
    assert (output / ".gitignore").exists() is enabled
    for folder in output.glob("*/on"):
        measurement = json.loads((folder / "measurement.json").read_text())
        assert measurement["creative_capture_enabled"] is enabled
        assert (folder / "creative-capture").exists() is enabled
        if enabled:
            assert (folder / "creative-capture/01-candidates.json").exists()
            assert (folder / "creative-capture/02-request.json").exists()
            assert stat.S_IMODE((folder / "creative-capture").stat().st_mode) == 0o700
            assert (folder / "creative-capture/.gitignore").read_text() == "*\n"
    if enabled:
        assert stat.S_IMODE(output.stat().st_mode) == 0o700
    with pytest.raises(SystemExit):
        ADAPTER["main"]()


def test_cli_preserves_opted_in_fixture_on_interruption(tmp_path, monkeypatch):
    output = tmp_path / "packet"

    class InterruptedGateway(ADAPTER["FixtureGateway"]):
        def complete(self, **kwargs):
            raise KeyboardInterrupt

    monkeypatch.setitem(
        ADAPTER["main"].__globals__, "FixtureGateway", InterruptedGateway
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["prototype", "--output", str(output), "--retain-creative-candidates"],
    )
    with pytest.raises(KeyboardInterrupt):
        ADAPTER["main"]()
    assert (output / "signal_house/off/creative-capture/01-request.json").exists()
    assert not (output / "manifest.json").exists()
    assert not list(output.rglob("dm-guide.md"))
    with pytest.raises(SystemExit):
        ADAPTER["main"]()


def test_cli_capture_failure_keeps_evidence_without_guide_or_final_manifest(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "packet"
    calls = []

    class FailedCapture(PrivateTrialCapture):
        def request(self, *args, **kwargs):
            raise TrialCaptureError()

    class Gateway(ADAPTER["FixtureGateway"]):
        def complete(self, **kwargs):
            calls.append(kwargs)
            return super().complete(**kwargs)

    monkeypatch.setitem(
        ADAPTER["main"].__globals__, "PrivateTrialCapture", FailedCapture
    )
    monkeypatch.setitem(ADAPTER["main"].__globals__, "FixtureGateway", Gateway)
    monkeypatch.setattr(
        sys,
        "argv",
        ["prototype", "--output", str(output), "--retain-creative-candidates"],
    )
    assert ADAPTER["main"]() == 1
    assert calls == []
    assert "No automatic retry" in capsys.readouterr().err
    assert not (output / "manifest.json").exists()
    assert not list(output.rglob("dm-guide.md"))
    journal = json.loads(
        (output / "signal_house/off/creative-capture/journal.json").read_text()
    )
    assert journal["attempts"][0]["status"] == "capture_failed"
    assert journal["attempts"][0]["dispatched"] is False


def test_cli_refuses_in_repository_unignored_destination(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prototype",
            "--output",
            str(ROOT / "tests/forbidden-capture-output"),
            "--retain-creative-candidates",
        ],
    )
    with pytest.raises(SystemExit):
        ADAPTER["main"]()
    assert not (ROOT / "tests/forbidden-capture-output").exists()
