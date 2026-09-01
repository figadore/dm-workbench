"""Frozen Tier A live-canary coverage."""

import hashlib

from dm_assistant.modules.modeling import ReasoningEffort
from dm_assistant.orchestration.dungeons import (
    DUNGEON_TIER_A_CANARY,
    resolve_dungeon_tier_a_canary_profiles,
)


def test_tier_a_canary_prompt_and_seed_are_frozen() -> None:
    assert DUNGEON_TIER_A_CANARY.canary_id == "tier-a-live-canary-v1"
    assert DUNGEON_TIER_A_CANARY.seed == 714_000_001
    assert hashlib.sha256(DUNGEON_TIER_A_CANARY.prompt.encode()).hexdigest() == (
        "7f853e689080eebaa64e547d7299daab1fbbf35bbea895d19c53a526e41607f1"
    )
    assert "one-floor" in DUNGEON_TIER_A_CANARY.prompt
    assert "exactly five rooms" in DUNGEON_TIER_A_CANARY.prompt
    assert "Windglass Seed" in DUNGEON_TIER_A_CANARY.prompt
    assert "player-observable clues and affordances" in DUNGEON_TIER_A_CANARY.prompt
    assert "reasonable approaches" in DUNGEON_TIER_A_CANARY.prompt
    assert "elaborate linked machinery" in DUNGEON_TIER_A_CANARY.prompt
    assert "flooded branch" not in DUNGEON_TIER_A_CANARY.prompt
    assert "physically diagrammable" not in DUNGEON_TIER_A_CANARY.prompt
    assert "alarm responder" not in DUNGEON_TIER_A_CANARY.prompt


def test_tier_a_canary_resolves_six_independent_bounded_task_profiles() -> None:
    profiles = resolve_dungeon_tier_a_canary_profiles(
        provider_id="faux",
        model_id="faux_deterministic_v1",
        capabilities=("text", "thinking", "tool_calls"),
        context_window_tokens=16_384,
        output_token_limit=4_096,
        requested_effort=ReasoningEffort.FAST,
    )
    resolved = (
        profiles.puzzle,
        profiles.exploration,
        profiles.feature_interaction,
        profiles.trap,
        profiles.objective,
        profiles.room_narrative,
    )

    assert len({profile.task_profile_id for profile in resolved}) == 6
    assert {profile.allowed_tools[0] for profile in resolved} == {
        "submit_dungeon_puzzle",
        "submit_dungeon_exploration",
        "submit_dungeon_feature_interaction",
        "submit_dungeon_trap",
        "submit_dungeon_objective",
        "submit_dungeon_room_narrative",
    }
    assert all(profile.requested_effort is ReasoningEffort.FAST for profile in resolved)
    assert all(
        profile.override_notes == {"output_token_limit": 2048, "repair_limit": 1}
        for profile in resolved
    )
