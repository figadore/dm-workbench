"""Frozen Tier A live-canary coverage."""

import hashlib

from dm_assistant.orchestration.dungeons import DUNGEON_TIER_A_CANARY


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
