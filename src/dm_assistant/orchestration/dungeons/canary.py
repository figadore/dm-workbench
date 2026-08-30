"""Frozen synthetic Tier A live-canary definition and explicit budget policy."""

from __future__ import annotations

from dataclasses import dataclass

from dm_assistant.config import RuntimeEnvironment
from dm_assistant.modules.modeling import ResolvedModelRunProfile
from dm_assistant.orchestration.modeling import (
    ADVISORY_STRUCTURED_OUTPUT_CAP_POLICY,
)

DUNGEON_TIER_A_CANARY_ID = "tier-a-live-canary-v1"
DUNGEON_TIER_A_CANARY_SEED = 714_000_001
DUNGEON_TIER_A_CANARY_PROMPT = (
    "Create a one-floor abandoned mountain shrine dungeon with exactly five rooms. The "
    "critical path must begin at one entrance and end at the Windglass Seed, which must "
    "be the named final objective. Include one optional windswept branch containing a "
    "key for one locked critical-path door, plus one optional secret loop from that "
    "branch to the objective room. Include one runnable exploration challenge in the "
    "branch, one moderate room trap, and one concise puzzle in a critical-path room. "
    "Give the puzzle and exploration challenge clear player-observable clues and "
    "affordances, meaningful stakes and consequences, and reasonable approaches. Include "
    "reset or retry details only where useful, and keep hidden information out of "
    "read-aloud. Do not default to elaborate linked machinery, alarm systems, or one "
    "prescribed physical manipulation unless the premise calls for it."
)

ADVISORY_OUTPUT_CAP_POLICY = ADVISORY_STRUCTURED_OUTPUT_CAP_POLICY


@dataclass(frozen=True, slots=True)
class DungeonTierACanary:
    """One frozen prompt/seed pair; provider and model remain explicit run inputs."""

    canary_id: str = DUNGEON_TIER_A_CANARY_ID
    prompt: str = DUNGEON_TIER_A_CANARY_PROMPT
    seed: int = DUNGEON_TIER_A_CANARY_SEED


DUNGEON_TIER_A_CANARY = DungeonTierACanary()


def apply_advisory_output_cap_override(
    profile: ResolvedModelRunProfile,
    *,
    environment: RuntimeEnvironment,
) -> ResolvedModelRunProfile:
    """Acknowledge Codex's advisory cap for this frozen non-production canary only."""
    if environment is RuntimeEnvironment.PRODUCTION:
        raise ValueError("the advisory output-cap override is forbidden in production")
    if profile.provider_id != "openai-codex":
        raise ValueError(
            "the advisory output-cap override is restricted to openai-codex"
        )
    return profile.model_copy(
        update={
            "override_notes": {
                **profile.override_notes,
                "canary_id": DUNGEON_TIER_A_CANARY_ID,
                "output_cap_enforcement": ADVISORY_OUTPUT_CAP_POLICY,
            }
        }
    )
