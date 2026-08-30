"""Frozen Tier A live-canary and manual output-cap policy coverage."""

import hashlib

import pytest

from dm_assistant.config import RuntimeEnvironment
from dm_assistant.modules.modeling import ResolvedModelRunProfile
from dm_assistant.orchestration.dungeons import (
    ADVISORY_OUTPUT_CAP_POLICY,
    DUNGEON_TIER_A_CANARY,
    apply_advisory_output_cap_override,
    resolve_dungeon_prompt_profile,
)


def _profile(provider_id: str = "openai-codex") -> ResolvedModelRunProfile:
    return resolve_dungeon_prompt_profile(
        provider_id=provider_id,
        model_id="synthetic-model",
        capabilities=("text", "tool_calls"),
        context_window_tokens=128_000,
        output_token_limit=16_384,
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


def test_advisory_output_cap_override_is_narrow_and_durable_in_profile() -> None:
    profile = apply_advisory_output_cap_override(
        _profile(), environment=RuntimeEnvironment.DEVELOPMENT
    )

    assert profile.token_budget == 12_000
    assert profile.override_notes == {
        "output_token_limit": 4096,
        "canary_id": "tier-a-live-canary-v1",
        "output_cap_enforcement": ADVISORY_OUTPUT_CAP_POLICY,
    }

    with pytest.raises(ValueError, match="forbidden in production"):
        apply_advisory_output_cap_override(
            _profile(), environment=RuntimeEnvironment.PRODUCTION
        )
    with pytest.raises(ValueError, match="restricted to openai-codex"):
        apply_advisory_output_cap_override(
            _profile("github-copilot"), environment=RuntimeEnvironment.DEVELOPMENT
        )
