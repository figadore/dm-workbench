"""Shared strict contract primitives for the dungeon kernel."""

from collections.abc import Iterable, Mapping
from enum import StrEnum
from typing import Annotated, ClassVar

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

OpaqueId = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    ),
]
NonEmptyText = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=256)]


class Visibility(StrEnum):
    """Whether an element is safe to include in a player-facing artifact."""

    PLAYER_SAFE = "player_safe"
    DM_ONLY = "dm_only"


class ContractModel(BaseModel):
    """Immutable, strict base for serialized dungeon contracts."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
        validate_default=True,
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_json_arrays(cls, value: object) -> object:
        """Convert JSON arrays to immutable tuples without coercing scalars."""
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value
        return {
            key: tuple(item) if isinstance(item, list) else item
            for key, item in value.items()
        }


class VersionedContract(ContractModel):
    """Reject missing and unsupported root-contract schema versions."""

    supported_schema_version: ClassVar[str]

    @model_validator(mode="before")
    @classmethod
    def require_supported_schema_version(cls, value: object) -> object:
        if isinstance(value, cls) or not isinstance(value, Mapping):
            return value

        actual = value.get("schema_version")
        if actual != cls.supported_schema_version:
            rendered = "<missing>" if actual is None else repr(actual)
            raise ValueError(
                f"Unsupported {cls.__name__} schema version {rendered}; "
                f"expected {cls.supported_schema_version!r}"
            )
        return value


class VisibleContract(ContractModel):
    """A contract element with mandatory publication classification."""

    visibility: Visibility


def ensure_unique_ids(groups: Mapping[str, Iterable[str]]) -> None:
    """Require opaque component IDs to be unique across named groups."""
    seen: dict[str, str] = {}
    for group_name, identifiers in groups.items():
        for identifier in identifiers:
            previous_group = seen.get(identifier)
            if previous_group is not None:
                raise ValueError(
                    f"Duplicate component ID {identifier!r} in {group_name}; "
                    f"already used in {previous_group}"
                )
            seen[identifier] = group_name
