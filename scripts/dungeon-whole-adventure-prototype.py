#!/usr/bin/env python3
"""P7-15b fixture-first file adapter with explicit single-case live opt-in."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import JsonValue

from dm_assistant.adapters.model_gateway import GatewayProvider, PiGatewayClient
from dm_assistant.modules.modeling import (
    PromptMessage,
    ReasoningEffort,
    ReasoningLevel,
    ResolvedModelRunProfile,
    ToolCall,
)
from dm_assistant.orchestration.dungeons.whole_adventure_prototype import (
    TOOL,
    build_fixed_map,
    build_input,
    render_trial_guide,
    run_trial,
)
from dm_assistant.orchestration.modeling.service import (
    GatewayCompletion,
    GatewayToolSchema,
)
from dm_dungeon import (
    DungeonPlan,
    RenderAudience,
    SvgRenderRequest,
    SvgThemeName,
    render_svg,
    to_canonical_json,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/evals/golden/whole_adventure"


def fixture_profile() -> ResolvedModelRunProfile:
    """Synthetic accounting ceilings only, NOT proposed or authorized live budgets."""
    return ResolvedModelRunProfile(
        endpoint_profile_id=UUID("71500000-0000-0000-0000-000000000001"),
        endpoint_profile_version="1.0.0",
        task_profile_id=UUID("71500000-0000-0000-0000-000000000002"),
        task_profile_version="1.0.0",
        provider_id="fixture",
        model_id="whole-adventure-fixture",
        runtime_adapter="fixture",
        requested_effort=ReasoningEffort.STANDARD,
        resolved_reasoning_level=ReasoningLevel.MEDIUM,
        supported_efforts=(ReasoningEffort.STANDARD,),
        observed_capabilities=("text", "tool_calls"),
        prompt_version="whole-adventure-prototype-1",
        instruction_version="whole-adventure-prototype-1",
        output_schema_name="whole_adventure_prototype",
        output_schema_version="1.0.0",
        allowed_tools=(TOOL.name,),
        turn_budget=1,
        tool_budget=1,
        time_budget_seconds=180,
        token_budget=100_000,
        require_citation_ids=False,
        require_authorized_citations=False,
        allow_source_retrieval_tools=False,
        fallback_order=(),
        override_notes={"output_token_limit": 16_000, "repair_limit": 1},
    )


def live_profile(provider: GatewayProvider, model_id: str) -> ResolvedModelRunProfile:
    """Use catalog capacity, not fixture ceilings or a monetary spending target."""
    model = next((item for item in provider.models if item.id == model_id), None)
    if not provider.authenticated or model is None:
        raise ValueError(
            "selected provider must be authenticated and advertise the exact model"
        )
    if not {"text", "thinking", "tool_calls"}.issubset(model.capabilities):
        raise ValueError("selected model must support text, reasoning and tool calls")
    return fixture_profile().model_copy(
        update={
            "endpoint_profile_id": uuid5(
                NAMESPACE_URL, f"pi_ai:{provider.id}:{model.id}"
            ),
            "provider_id": provider.id,
            "model_id": model.id,
            "runtime_adapter": "pi_ai",
            "requested_effort": ReasoningEffort.DEEP,
            "resolved_reasoning_level": ReasoningLevel.HIGH,
            "supported_efforts": (ReasoningEffort.DEEP,),
            "observed_capabilities": model.capabilities,
            "time_budget_seconds": 600,
            "token_budget": min(model.context_window, 262_144),
            "override_notes": {
                "output_token_limit": min(model.max_output_tokens, 131_072),
                "repair_limit": 1,
                "ceiling_policy": "technical_capacity_only_no_monetary_ceiling",
                "sdk_retries": 0,
            },
        }
    )


class FixtureGateway:
    """No network/configuration access; fixed synthetic counters exercise reservation."""

    def __init__(self, responses: list[dict[str, JsonValue]]) -> None:
        self.responses = list(responses)
        self.calls = 0

    def complete(
        self,
        *,
        profile: ResolvedModelRunProfile,
        messages: tuple[PromptMessage, ...],
        allowed_tools: tuple[str, ...],
        tool_schemas: tuple[GatewayToolSchema, ...],
    ) -> GatewayCompletion:
        if not self.responses:
            raise AssertionError("unexpected additional creative/editorial call")
        self.calls += 1
        return GatewayCompletion(
            tool_calls=(
                ToolCall(
                    tool_name=TOOL.name,
                    call_id=f"fixture_{self.calls}",
                    arguments=self.responses.pop(0),
                ),
            ),
            input_tokens=10_000,
            output_tokens=2_000,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "generated/p7-15b-prototype"
    )
    parser.add_argument("--consistency", choices=("both", "on", "off"), default="both")
    parser.add_argument(
        "--scenario", choices=("valid", "reference-repair", "rejected"), default="valid"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Explicitly authorize one live case/condition, at most two calls.",
    )
    parser.add_argument(
        "--brief",
        type=Path,
        help="One synthetic brief JSON object (required for live).",
    )
    parser.add_argument(
        "--provider", help="Exact gateway provider ID (required for live)."
    )
    parser.add_argument(
        "--model",
        help="Exact gateway model ID (required for live); high effort is fixed.",
    )
    args = parser.parse_args()
    if args.live:
        if (
            not (args.brief and args.provider and args.model)
            or args.consistency == "both"
            or args.scenario != "valid"
        ):
            parser.error(
                "--live requires --brief, --provider, --model, one --consistency condition, and --scenario valid"
            )
    elif args.brief or args.provider or args.model:
        parser.error("--brief/--provider/--model require explicit --live")
    output = args.output.resolve()
    if output.exists():
        parser.error(f"destination already exists: {output}")
    fixed = build_fixed_map(
        DungeonPlan.model_validate_json((FIXTURES / "plan.json").read_bytes())
    )
    cases = json.loads((FIXTURES / "cases.json").read_text())
    profile = fixture_profile()
    gateway: PiGatewayClient | None = None
    if args.live:
        brief = json.loads(args.brief.read_text(encoding="utf-8"))
        if not isinstance(brief, dict) or not all(
            isinstance(brief.get(key), str) and brief[key].strip()
            for key in ("case_id", "title", "assumptions", "prompt")
        ):
            parser.error(
                "live brief requires nonempty case_id, title, assumptions and prompt strings"
            )
        case_id = brief["case_id"]
        if not case_id.isascii() or not all(c.isalnum() or c in "_-" for c in case_id):
            parser.error(
                "case_id must contain only ASCII letters, digits, underscores or hyphens"
            )
        cases = [brief]
        try:
            gateway = PiGatewayClient(
                base_url=os.environ["DM_MODEL_GATEWAY_URL"],
                internal_token=os.environ["DM_MODEL_GATEWAY_INTERNAL_TOKEN"],
            )
        except KeyError:
            parser.error(
                "live mode requires configured DM_MODEL_GATEWAY_URL and DM_MODEL_GATEWAY_INTERNAL_TOKEN"
            )
        provider = next(
            (item for item in gateway.providers() if item.id == args.provider), None
        )
        if provider is None:
            parser.error("selected provider is not in the gateway catalog")
        profile = live_profile(provider, args.model)
    conditions = (
        (False, True) if args.consistency == "both" else (args.consistency == "on",)
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.live:
        output.mkdir(
            mode=0o700
        )  # Exclusive claim; retain interrupted live attempt journals.
        staging = output
    else:
        staging = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    all_accepted = True
    live_calls = 0

    def save_json(path: Path, value: object) -> None:
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        temporary.replace(path)

    try:
        (staging / "package.json").write_text(
            to_canonical_json(fixed.package), encoding="utf-8"
        )
        (staging / "plan.json").write_text(
            to_canonical_json(fixed.plan), encoding="utf-8"
        )
        (staging / "layout-request.json").write_text(
            to_canonical_json(fixed.request), encoding="utf-8"
        )
        save_json(
            staging / "submission-schema.json", TOOL.input_schema.model_json_schema()
        )
        for audience in RenderAudience:
            rendered = render_svg(
                fixed.package,
                SvgRenderRequest(
                    schema_version="1.0.0",
                    package_id=fixed.package.id,
                    floor_id=fixed.package.floors[0].id,
                    audience=audience,
                    theme=SvgThemeName.LOW_INK,
                ),
            )
            if not rendered.success or rendered.svg is None:
                raise RuntimeError("fixed map render failed")
            (staging / f"{audience.value}-map.svg").write_text(
                rendered.svg, encoding="utf-8"
            )
        for brief in cases:
            response = (
                {}
                if args.live
                else json.loads((FIXTURES / f"{brief['case_id']}.json").read_text())
            )
            for consistency in conditions:
                folder = staging / brief["case_id"] / ("on" if consistency else "off")
                folder.mkdir(parents=True)
                bad = copy.deepcopy(response)
                if not args.live:
                    bad["guide_content"]["room_narratives"][0]["room_ref"] = (
                        "missing_room"
                    )
                save_json(folder / "brief.json", brief)
                save_json(
                    folder / "input.json",
                    build_input(fixed, brief, consistency=consistency).model_dump(
                        mode="json"
                    ),
                )

                def journal(
                    value: dict[str, JsonValue],
                    target: Path = folder / "measurement.json",
                ) -> None:
                    save_json(
                        target,
                        {
                            **value,
                            "evidence_kind": "live_feasibility",
                            "usage_kind": "gateway_measured_input_includes_cache",
                            "quality_or_readiness_established": False,
                        },
                    )

                responses = {
                    "valid": [response],
                    "reference-repair": [bad, response],
                    "rejected": [bad, bad],
                }[args.scenario]
                submission, report = run_trial(
                    gateway if gateway is not None else FixtureGateway(responses),
                    profile=profile,
                    fixed=fixed,
                    brief=brief,
                    consistency=consistency,
                    on_progress=journal if args.live else None,
                )
                attempts = report["attempts"]
                if args.live and isinstance(attempts, list):
                    live_calls += len(
                        [
                            item
                            for item in attempts
                            if isinstance(item, dict) and item["dispatched"]
                        ]
                    )
                report.update(
                    {
                        "evidence_kind": "live_feasibility"
                        if args.live
                        else "provider_free_fixture",
                        "usage_kind": "gateway_measured_input_includes_cache"
                        if args.live
                        else "synthetic_test_counters_not_provider_measurements",
                        "scenario": args.scenario,
                        "guide_words": None,
                        "guide_sha256": None,
                        "quality_or_readiness_established": False,
                    }
                )
                if submission is not None:
                    guide = render_trial_guide(fixed, brief, submission)
                    (folder / "dm-guide.md").write_text(guide, encoding="utf-8")
                    save_json(
                        folder / "submission.json", submission.model_dump(mode="json")
                    )
                    report["guide_words"] = len(guide.split())
                    report["guide_sha256"] = hashlib.sha256(guide.encode()).hexdigest()
                else:
                    all_accepted = False
                save_json(folder / "measurement.json", report)
                (folder / "human-review.md").write_text(
                    "# Human review — blank, not AI evidence\n\n"
                    + (
                        "Live single-case feasibility sample; not readiness evidence.\n"
                        if args.live
                        else "Provider-free fixture only; short plumbing samples are not full one-shots.\n"
                    )
                    + "Condition labels are visible; this packet is not blinded.\n\n"
                    "- Reviewer/date and exact guide hash:\n"
                    "- Would you run it? What core authoring is still missing?\n"
                    "- Causal repairs needed (quote passages; do not supply imagined excuses):\n"
                    "- Actual review minutes / editing minutes (unknown until measured):\n"
                    "- Useful detail lost or explanations added?\n"
                    "- Map/procedure/clue/answer mismatches:\n"
                    "- Practical comparison with chat-assisted authoring plus a map:\n"
                    "- Tabletop walkthrough and actual session length, if performed:\n",
                    encoding="utf-8",
                )
        save_json(
            staging / "manifest.json",
            {
                "task": "P7-15b",
                "evidence_kind": "live_feasibility"
                if args.live
                else "provider_free_fixture",
                "live_calls": live_calls,
                "editorial_calls": 0,
                "word_count_method": "len(complete_rendered_markdown.split()); includes headings and deterministic mechanics",
                "files": {
                    str(path.relative_to(staging)): hashlib.sha256(
                        path.read_bytes()
                    ).hexdigest()
                    for path in sorted(staging.rglob("*"))
                    if path.is_file()
                },
            },
        )
        if not args.live:
            if output.exists():
                raise FileExistsError(output)
            staging.rename(output)
    finally:
        if not args.live and staging.exists():
            shutil.rmtree(staging)
    print(
        f"P7-15b {'live feasibility' if args.live else 'provider-free'} packet: {output}"
    )
    print("DM guide is private; technical acceptance is not human readiness evidence.")
    return 0 if all_accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
