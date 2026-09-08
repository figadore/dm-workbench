"""Shared default-model policy for prompted dungeon authoring."""

from dm_assistant.adapters.model_gateway import GatewayCatalogModel

DUNGEON_DEFAULT_MODEL_ID = "gpt-5.6-luna"

_PROVIDER_MODEL_PREFERENCES: dict[str, tuple[str, ...]] = {
    "github-copilot": (DUNGEON_DEFAULT_MODEL_ID, "gpt-4.1", "gpt-5-mini"),
    "openai-codex": (DUNGEON_DEFAULT_MODEL_ID, "gpt-5.4-mini", "gpt-5.4"),
}


def default_dungeon_model(
    models: tuple[GatewayCatalogModel, ...], provider_id: str
) -> GatewayCatalogModel | None:
    """Select the pinned dungeon baseline, then a stable compatible fallback."""
    compatible = tuple(
        model for model in models if {"text", "tool_calls"}.issubset(model.capabilities)
    )
    if not compatible:
        return None
    by_id = {model.id: model for model in compatible}
    for preferred_id in _PROVIDER_MODEL_PREFERENCES.get(provider_id, ()):
        if preferred_id in by_id:
            return by_id[preferred_id]
    return sorted(compatible, key=lambda item: item.id)[0]
