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
    "Create a one-floor archive dungeon with exactly five rooms. The critical path "
    "must begin at one entrance and end at the Lantern Ledger, which must be the named "
    "final objective. Include one optional flooded branch containing a key for one "
    "locked critical-path door, plus one optional secret loop from that branch to the "
    "objective room. Include one runnable exploration challenge in the branch, one "
    "moderate room trap, and one concrete three-step puzzle in a critical-path room. "
    "Make every guide interaction physically diagrammable, distinguish visible trap "
    "warnings from concealed triggers, and state exact recovery and repeated-failure "
    "outcomes. No creature or alarm responder is present."
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
