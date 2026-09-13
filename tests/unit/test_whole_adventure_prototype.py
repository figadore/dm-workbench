"""P7-15b provider-free plumbing is not human authoring/readiness evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from dm_assistant.adapters.model_gateway import (
    GatewayProvider,
    _profile_output_token_limit,
)
from dm_assistant.orchestration.dungeons.whole_adventure_prototype import (
    CONSISTENCY_INSTRUCTION,
    PRESENTATION_EXAMPLE,
    TOOL,
    WholeAdventureSubmission,
    build_fixed_map,
    build_input,
    content_diagnostics,
    render_trial_guide,
    resolved_map_brief,
    run_trial,
)
from dm_assistant.orchestration.modeling.service import (
    GatewayCompletion,
    ModelTransportError,
)
from dm_dungeon import DungeonPlan, validate_geometry, validate_topology

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/dungeon-whole-adventure-prototype.py"
FIXTURES = ROOT / "tests/evals/golden/whole_adventure"
ADAPTER = runpy.run_path(str(SCRIPT))
CASES = json.loads((FIXTURES / "cases.json").read_text())


@pytest.fixture(scope="module")
def fixed():
    return build_fixed_map(
        DungeonPlan.model_validate_json((FIXTURES / "plan.json").read_bytes())
    )


def response(case_id="signal_house"):
    return json.loads((FIXTURES / f"{case_id}.json").read_text())


class Gateway(ADAPTER["FixtureGateway"]):
    def __init__(
        self, responses, *, usage=True, output_tokens=2000, tool_name=TOOL.name
    ):
        super().__init__(responses)
        self.usage = usage
        self.output_tokens = output_tokens
        self.tool_name = tool_name
        self.inputs = []
        self.profiles = []

    def complete(self, **kwargs):
        self.inputs.append(kwargs["messages"])
        self.profiles.append(kwargs["profile"])
        completion = super().complete(**kwargs)
        return completion.model_copy(
            update={
                "tool_calls": (
                    completion.tool_calls[0].model_copy(
                        update={"tool_name": self.tool_name}
                    ),
                ),
                "input_tokens": 10_000 if self.usage else None,
                "output_tokens": self.output_tokens if self.usage else None,
            }
        )


def trial(fixed, gateway, *, brief=CASES[0], consistency=True, profile=None):
    return run_trial(
        gateway,
        fixed=fixed,
        brief=brief,
        consistency=consistency,
        profile=profile or ADAPTER["fixture_profile"](),
    )


@pytest.mark.parametrize("brief", CASES, ids=lambda brief: brief["case_id"])
def test_three_cases_share_one_valid_map_and_only_instruction_changes(fixed, brief):
    before = fixed.package.model_dump_json()
    assert validate_geometry(fixed.package).valid
    assert validate_topology(fixed.package.topology).valid
    off = build_input(fixed, brief, consistency=False)
    on = build_input(fixed, brief, consistency=True)
    assert (
        on.messages[0].content
        == off.messages[0].content + "\n\n" + CONSISTENCY_INSTRUCTION
    )
    assert on.messages[1:] == off.messages[1:]
    assert all(len(message.content) <= 16000 for message in on.messages)
    reports = []
    guides = []
    for consistency in (False, True):
        gateway = Gateway([response(brief["case_id"])])
        accepted, report = trial(fixed, gateway, brief=brief, consistency=consistency)
        assert accepted is not None
        assert not content_diagnostics(fixed, accepted)
        guides.append(render_trial_guide(fixed, brief, accepted))
        assert gateway.calls == 1
        assert report["editorial_calls"] == 0
        assert report["human_review"] is None
        assert report["cost_usd"] is None
        reports.append(report)
    for field in (
        "brief_sha256",
        "plan_sha256",
        "layout_request_sha256",
        "map_sha256",
        "profile",
        "schema_sha256",
    ):
        assert reports[0][field] == reports[1][field]
    assert reports[0]["input_sha256"] != reports[1]["input_sha256"]
    assert (
        guides[0] == guides[1]
    )  # Scripted response is NOT an instruction-effect result.
    assert fixed.package.model_dump_json() == before


@pytest.mark.parametrize("failure", ("schema", "reference", "gate_missing"))
@pytest.mark.parametrize("consistency", (False, True))
def test_one_technical_repair_preserves_objective_and_cumulative_budget(
    fixed, failure, consistency
):
    bad = response()
    if failure == "schema":
        bad["canonical_write"] = "forbidden"
    elif failure == "reference":
        bad["guide_content"]["room_narratives"][0]["room_ref"] = "absent"
    else:
        bad["guide_content"]["entries"] = bad["guide_content"]["entries"][1:]
    gateway = Gateway([bad, response()])
    accepted, report = trial(fixed, gateway, consistency=consistency)
    assert accepted is not None
    assert gateway.calls == 2
    assert len(report["attempts"]) == 2
    assert report["attempts"][0]["diagnostics"]
    assert report["attempts"][1]["status"] == "accepted"
    assert report["cumulative_input_tokens"] == 20_000
    assert report["cumulative_output_tokens"] == 4000
    assert gateway.inputs[1][: len(gateway.inputs[0])] == gateway.inputs[0]
    assert gateway.profiles[1].token_budget == gateway.profiles[0].token_budget - 12_000
    assert (
        gateway.profiles[1].time_budget_seconds
        <= gateway.profiles[0].time_budget_seconds
    )
    assert "submit_whole_adventure" == gateway.profiles[1].allowed_tools[0]
    assert "warning reports" not in json.dumps(
        report
    )  # No response transcript in measurement.


def test_failed_repair_stops_without_third_attempt_or_guide(fixed):
    gateway = Gateway([{}, {}, response()])
    accepted, report = trial(fixed, gateway)
    assert accepted is None
    assert gateway.calls == 2
    assert report["terminal_code"] == "rejected_after_technical_repair"
    assert report["accepted"] is False
    with pytest.raises(ValidationError):
        WholeAdventureSubmission.model_validate_json(
            json.dumps({**response(), "geometry": {}})
        )


def test_unknown_usage_does_not_become_free_repair(fixed):
    gateway = Gateway([{}, response()], usage=False)
    accepted, report = trial(fixed, gateway)
    assert accepted is None
    assert gateway.calls == 1
    assert report["terminal_code"] == "repair_usage_unavailable"
    assert report["cumulative_input_tokens"] is None
    assert report["cumulative_output_tokens"] is None


def test_reservation_denial_retains_initial_attempt(fixed):
    gateway = Gateway([{}, response()])
    profile = ADAPTER["fixture_profile"]().model_copy(update={"token_budget": 12_000})
    accepted, report = trial(fixed, gateway, profile=profile)
    assert accepted is None
    assert gateway.calls == 1
    assert report["terminal_code"] == "repair_budget_exhausted"
    assert report["repair_reserve"]["token_arithmetic"]["request_token_budget"] == 0
    assert report["attempts"][0]["status"] == "schema_rejected"
    assert report["cumulative_input_tokens"] == 10_000


@pytest.mark.parametrize(
    "option", ("output_overage", "unauthorized_tool", "cumulative_overage")
)
def test_runner_rejection_retains_usage_and_never_publishes(fixed, option):
    gateway = Gateway(
        [response()],
        output_tokens=16_001 if option == "output_overage" else 2000,
        tool_name="approve_preparation" if option == "unauthorized_tool" else TOOL.name,
    )
    profile = ADAPTER["fixture_profile"]()
    if option == "cumulative_overage":
        profile = profile.model_copy(update={"token_budget": 11_999})
    accepted, report = trial(fixed, gateway, profile=profile)
    assert accepted is None
    assert gateway.calls == 1
    assert report["terminal_code"]
    assert report["attempts"][0]["status"] == "abstained"
    assert report["cumulative_input_tokens"] == 10_000
    assert report["cumulative_output_tokens"] == gateway.output_tokens
    if option != "unauthorized_tool":
        assert report["terminal_code"] == "token_budget_exceeded"
        assert report["budget_failure"]["limit_kind"] == (
            "output" if option == "output_overage" else "cumulative"
        )


def test_transport_failure_has_unknown_usage_and_no_raw_body(fixed):
    class FailedGateway:
        def complete(self, **kwargs) -> GatewayCompletion:
            raise ModelTransportError("private transport body", code="rate_limited")

    accepted, report = trial(fixed, FailedGateway())
    assert accepted is None
    assert report["terminal_code"] == "rate_limited"
    assert report["cumulative_input_tokens"] is None
    assert "private transport body" not in json.dumps(report)
    assert report["attempts"][0]["dispatched"] is True


def test_progress_journals_dispatch_before_contact_and_all_attempts(fixed):
    snapshots = []

    class JournalGateway(Gateway):
        def complete(self, **kwargs):
            assert snapshots[-1]["attempts"][-1]["dispatched"] is True
            assert snapshots[-1]["attempts"][-1]["input_tokens"] is None
            return super().complete(**kwargs)

    gateway = JournalGateway([{}, response()])
    accepted, report = run_trial(
        gateway,
        fixed=fixed,
        profile=ADAPTER["fixture_profile"](),
        brief=CASES[0],
        consistency=True,
        on_progress=lambda value: snapshots.append(copy.deepcopy(value)),
    )
    assert accepted is not None
    assert len(snapshots[-1]["attempts"]) == 2
    assert snapshots[-1] == report
    assert '"guide_content":' not in json.dumps(snapshots)


def test_room_local_note_is_lossless_private_and_map_linked(fixed):
    from dm_assistant.orchestration.dungeons.service import build_dungeon_dm_guide
    from dm_dungeon import RenderAudience, SvgRenderRequest, render_svg

    document = response()
    note = json.loads((FIXTURES / "local_note.json").read_text())
    document["guide_content"]["room_narratives"][1] = note
    submission = WholeAdventureSubmission.model_validate_json(json.dumps(document))
    assert not content_diagnostics(fixed, submission)
    guide = build_dungeon_dm_guide(
        fixed.request, fixed.package, fixed.plan, submission.guide_content
    )
    text = render_trial_guide(fixed, CASES[0], submission)
    assert text.count("\n# ") == 0
    assert text.index("## The job") < text.index("## 1 —") < text.index("## Settle up")
    assert "[DM map](../../dm-map.svg)" in text
    for room in guide.rooms:
        assert str(room.presentation_number) == room.map_reference.token
        assert f"## {room.map_reference.token} — {room.name}" in text
    gallery = next(room for room in guide.rooms if room.name == "Gallery")
    local = text.split(f"## {gallery.map_reference.token} — Gallery\n", 1)[1].split(
        "\n## ", 1
    )[0]
    for value in (
        *note["sensory_details"],
        note["local_content"][0]["delivery"],
        note["local_content"][0]["revealed_text"],
    ):
        assert value in local
        assert text.count(value) == 1
    vault = next(room for room in guide.rooms if room.name == "Repository")
    assert (
        f"[Repository ({vault.map_reference.token})](#room-{vault.map_reference.token})"
        in local
    )
    assert "[[room:" not in text
    assert f'<a id="room-{gallery.map_reference.token}"></a>\n\n## ' in text
    puzzle = submission.guide_content.entries[2]
    assert text.index(puzzle.situation) < text.index(puzzle.solution)
    assert "**Exits — DM reference:**" in local
    assert (
        gallery.local_content[0].revealed_text
        == note["local_content"][0]["revealed_text"]
    )
    player = render_svg(
        fixed.package,
        SvgRenderRequest(
            schema_version="1.0.0",
            package_id=fixed.package.id,
            floor_id=fixed.package.floors[0].id,
            audience=RenderAudience.PLAYER,
        ),
    ).svg
    assert player is not None
    assert "Inspector Vale" not in player
    assert "dispatch" not in player
    assert not fixed.plan.room_contents or all(
        item.room_ref != "gallery" or item.feature is None
        for item in fixed.plan.room_contents
    )


@pytest.mark.parametrize("missing", ("delivery", "revealed_text"))
def test_conditional_room_text_requires_its_delivery_pair(missing):
    document = response()
    del document["guide_content"]["room_narratives"][1]["local_content"][0][missing]
    with pytest.raises(ValidationError, match="delivery cue"):
        WholeAdventureSubmission.model_validate_json(json.dumps(document))


@pytest.mark.parametrize("location", ("overview", "local", "mechanical"))
def test_unknown_explicit_room_links_are_rejected_not_guessed(fixed, location):
    document = response()
    if location == "overview":
        document["background"] += " See [[room:absent]]."
    elif location == "local":
        document["guide_content"]["room_narratives"][1]["local_content"][0][
            "dm_text"
        ] += " See [[room:absent]]."
    else:
        document["guide_content"]["entries"][0]["adjudication"] += (
            " See [[room:absent]]."
        )
    submission = WholeAdventureSubmission.model_validate_json(json.dumps(document))
    assert content_diagnostics(fixed, submission)
    with pytest.raises(ValueError, match="technically rejected"):
        render_trial_guide(fixed, CASES[0], submission)


@pytest.mark.parametrize("extra", ("visibility", "geometry", "approved_for_play"))
def test_local_prose_cannot_grant_authority_or_change_map(extra):
    document = response()
    document["guide_content"]["room_narratives"][1]["local_content"][0][extra] = (
        "forbidden"
    )
    with pytest.raises(ValidationError, match="Extra inputs"):
        WholeAdventureSubmission.model_validate_json(json.dumps(document))


@pytest.mark.parametrize(
    "reference", ("[[room:private document body]]", "[[room:unfinished")
)
def test_invalid_prose_link_diagnostics_remain_body_free(fixed, reference):
    document = response()
    document["background"] = reference
    submission = WholeAdventureSubmission.model_validate_json(json.dumps(document))
    diagnostics = content_diagnostics(fixed, submission)
    assert diagnostics
    assert reference not in json.dumps(diagnostics)


def test_resolved_context_uses_exact_openings_not_destination_bearings(fixed):
    from dm_assistant.orchestration.dungeons.guide_presentation import room_exit_lines
    from dm_assistant.orchestration.dungeons.service import build_dungeon_dm_guide

    guide = build_dungeon_dm_guide(fixed.request, fixed.package, fixed.plan)
    openings = {
        (item.corridor_id, item.room_id): item.approach_direction.value
        for item in fixed.package.passage_openings
    }
    for connection in guide.connections:
        assert (
            connection.from_direction
            == openings[connection.connection_id, connection.from_room_id]
        )
        assert (
            connection.to_direction
            == openings[connection.connection_id, connection.to_room_id]
        )
        for room in guide.rooms:
            if room.room_id in (connection.from_room_id, connection.to_room_id):
                assert any(
                    connection.map_reference.token in line
                    for line in room_exit_lines(guide, room)
                )
    secret = next(
        connection for connection in guide.connections if connection.concealed
    )
    # The bent bypass leaves Annex eastward but Repository northward, NOT westward.
    assert (secret.from_direction, secret.to_direction) == ("east", "north")
    context = build_input(fixed, CASES[0], consistency=False)
    assert context.messages[1].content == resolved_map_brief(fixed)
    assert context.messages[2].content == PRESENTATION_EXAMPLE
    assert "1 — Entrance" in context.messages[1].content
    assert "Inner Gate Key" in context.messages[1].content
    assert "Secret discovery DC 13" in context.messages[1].content
    assert "structure only" in context.messages[2].content


def test_technical_repair_can_keep_unreserved_evidence_in_its_original_room(fixed):
    document = response()
    local = document["guide_content"]["room_narratives"][1]["local_content"]
    bad = copy.deepcopy(document)
    # A spurious feature target cannot be accepted, even with ordinary prose available.
    bad["guide_content"]["entries"].append(
        {
            "kind": "feature",
            "ref": "dispatch",
            "room_ref": "gallery",
            "feature_name": "Dispatch",
            "situation": local[0]["revealed_text"],
            "adjudication": local[0]["dm_text"],
            "player_choices": bad["guide_content"]["entries"][0]["player_choices"],
        }
    )
    gateway = Gateway([bad, document])
    accepted, report = trial(fixed, gateway)
    assert accepted is not None
    assert report["attempts"][0]["status"] == "references_rejected"
    assert "Never move it to another room" in gateway.inputs[1][-1].content
    repaired = accepted.guide_content.model_dump(mode="json")
    original = WholeAdventureSubmission.model_validate_json(json.dumps(document))
    assert (
        accepted.guide_content.room_narratives[1].local_content
        == original.guide_content.room_narratives[1].local_content
    )
    assert not any(entry["kind"] == "feature" for entry in repaired["entries"])


def test_existing_detail_template_preserves_local_fields_and_escapes_prose(fixed):
    from types import SimpleNamespace

    from jinja2 import Environment, FileSystemLoader, select_autoescape

    from dm_assistant.orchestration.dungeons.service import build_dungeon_dm_guide

    document = response()
    document["guide_content"]["room_narratives"][1]["local_content"][0]["dm_text"] = (
        "<script>synthetic-secret</script>"
    )
    submission = WholeAdventureSubmission.model_validate_json(json.dumps(document))
    guide = build_dungeon_dm_guide(
        fixed.request, fixed.package, fixed.plan, submission.guide_content
    )
    template = Environment(
        loader=FileSystemLoader(ROOT / "src/dm_assistant/web/templates"),
        autoescape=select_autoescape(),
    ).get_template("dungeon_detail.html")
    version = SimpleNamespace(
        id="synthetic-version",
        version_number=1,
        change_summary="Fixture",
        parent_version_id=None,
        specification_sha256="synthetic",
        specification={"layout_request": {"brief": {"summary": "Fixture"}}},
        validation_report={},
        input_pins=SimpleNamespace(model_dump=lambda **kwargs: {}),
    )
    html = template.render(
        detail={
            "title": "Fixture",
            "lifecycle": "draft",
            "current_version_id": version.id,
        },
        versions=[version],
        dm_notes_by_version={version.id: SimpleNamespace(source_prompt=None)},
        dm_guides_by_version={version.id: guide},
        generation_runs={version.id: None},
        version_assets={version.id: []},
        campaign_id="synthetic",
        csrf_token="synthetic",
    )
    assert "<script>synthetic-secret</script>" not in html
    assert "&lt;script&gt;synthetic-secret&lt;/script&gt;" in html
    assert "When someone unfolds the dispatch" in html
    assert "Inspection complete. The landing is unsafe." in html
    assert "The paper smells faintly of mint." in html
    assert "2 — Gallery" in html
    assert "(Map " not in html
    assert "Exits — DM reference:" in html


def astra_provider():
    return GatewayProvider.model_validate(
        {
            "id": "openai-codex",
            "name": "Synthetic Codex",
            "authenticated": True,
            "authModes": ["oauth"],
            "models": [
                {
                    "id": "gpt-6-astra",
                    "name": "Synthetic Astra",
                    "capabilities": ["text", "thinking", "tool_calls"],
                    "contextWindow": 272_000,
                    "maxOutputTokens": 128_000,
                }
            ],
        }
    )


def test_live_profile_uses_exact_catalog_high_effort_and_technical_capacity():
    provider = astra_provider()
    profile = ADAPTER["live_profile"](provider, "gpt-6-astra")
    assert profile.model_id == "gpt-6-astra"
    assert profile.requested_effort.value == "deep"
    assert profile.resolved_reasoning_level.value == "high"
    assert profile.time_budget_seconds == 600
    assert profile.token_budget == 262_144
    assert _profile_output_token_limit(profile) == 128_000
    assert _profile_output_token_limit(ADAPTER["fixture_profile"]()) == 16_000
    assert profile.override_notes["sdk_retries"] == 0
    with pytest.raises(ValueError):
        ADAPTER["live_profile"](provider, "not-in-catalog")
    with pytest.raises(ValueError):
        ADAPTER["live_profile"](
            provider.model_copy(update={"authenticated": False}), "gpt-6-astra"
        )


@pytest.mark.parametrize("interrupt", (False, True))
def test_live_cli_is_explicit_single_case_and_preserves_interrupted_journal(
    tmp_path, monkeypatch, interrupt
):
    output = tmp_path / "live"
    brief_file = tmp_path / "brief.json"
    brief_file.write_text(json.dumps(CASES[0]))
    calls = []

    class FakeClient(Gateway):
        def __init__(self, **kwargs):
            super().__init__([response()])

        def providers(self):
            return (astra_provider(),)

        def complete(self, **kwargs):
            calls.append(kwargs)
            measurement = json.loads(
                (output / "signal_house/on/measurement.json").read_text()
            )
            assert measurement["attempts"][0]["dispatched"] is True
            assert measurement["evidence_kind"] == "live_feasibility"
            if interrupt:
                raise KeyboardInterrupt
            return super().complete(**kwargs)

    monkeypatch.setitem(ADAPTER["main"].__globals__, "PiGatewayClient", FakeClient)
    monkeypatch.setenv("DM_MODEL_GATEWAY_URL", "http://fixture.invalid")
    monkeypatch.setenv("DM_MODEL_GATEWAY_INTERNAL_TOKEN", "synthetic-internal-token")
    args = [
        str(SCRIPT),
        "--output",
        str(output),
        "--live",
        "--provider",
        "openai-codex",
        "--model",
        "gpt-6-astra",
        "--brief",
        str(brief_file),
    ]
    # Default 'both' must fail before even one live submission.
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit) as error:
        ADAPTER["main"]()
    assert error.value.code == 2
    assert not calls
    monkeypatch.setattr(sys, "argv", [*args, "--consistency", "on"])
    if interrupt:
        with pytest.raises(KeyboardInterrupt):
            ADAPTER["main"]()
        assert not (output / "manifest.json").exists()
        assert (
            json.loads((output / "signal_house/on/measurement.json").read_text())[
                "attempts"
            ][0]["input_tokens"]
            is None
        )
    else:
        assert ADAPTER["main"]() == 0
        assert json.loads((output / "manifest.json").read_text())["live_calls"] == 1
    assert len(calls) == 1
    with pytest.raises(SystemExit) as error:
        ADAPTER["main"]()
    assert error.value.code == 2
    assert len(calls) == 1


def test_invalid_fixed_map_fails_before_any_submission():
    plan = json.loads((FIXTURES / "plan.json").read_text())
    plan["loops"] *= 2
    with pytest.raises((ValidationError, ValueError)):
        build_fixed_map(DungeonPlan.model_validate_json(json.dumps(plan)))


def test_invalid_reference_content_cannot_render(fixed):
    bad = copy.deepcopy(response())
    bad["guide_content"]["entries"][0]["dependency_name"] = "Wrong Key"
    with pytest.raises(ValueError, match="technically rejected"):
        render_trial_guide(
            fixed,
            CASES[0],
            WholeAdventureSubmission.model_validate_json(json.dumps(bad)),
        )


@pytest.mark.parametrize(
    "scenario,exit_code", (("valid", 0), ("reference-repair", 0), ("rejected", 1))
)
def test_cli_packets_keep_failures_hashes_secrecy_and_no_overwrite(
    tmp_path, scenario, exit_code
):
    output = tmp_path / "packet"
    command = [
        sys.executable,
        str(SCRIPT),
        "--output",
        str(output),
        "--scenario",
        scenario,
    ]
    completed = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert completed.returncode == exit_code, completed.stderr
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["live_calls"] == 0
    for filename, digest in manifest["files"].items():
        assert hashlib.sha256((output / filename).read_bytes()).hexdigest() == digest
    measurements = list(output.glob("*/*/measurement.json"))
    assert len(measurements) == 6
    for path in measurements:
        value = json.loads(path.read_text())
        assert value["human_review"] is None
        assert value["quality_or_readiness_established"] is False
        assert value["evidence_kind"] == "provider_free_fixture"
        assert len(value["attempts"]) == (1 if scenario == "valid" else 2)
        assert (path.parent / "dm-guide.md").exists() == (exit_code == 0)
        if exit_code == 0:
            assert value["guide_words"] == len(
                (path.parent / "dm-guide.md").read_text().split()
            )
    player = (output / "player-map.svg").read_text()
    assert "Prepared Objective" not in player
    assert "Inner Gate Key" not in player
    assert "dm-guide" not in player
    again = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert again.returncode == 2
    assert "destination already exists" in again.stderr
    assert json.loads((output / "manifest.json").read_text()) == manifest
