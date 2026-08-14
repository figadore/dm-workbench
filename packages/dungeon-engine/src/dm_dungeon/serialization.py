"""Canonical JSON and file adapters for dungeon package contracts."""

import json
from pathlib import Path
from typing import Any

from dm_dungeon.contracts.common import ContractModel
from dm_dungeon.contracts.design_v2 import (
    DUNGEON_DESIGN_V2_SCHEMA_VERSION,
    DungeonDesignSpecV2,
)
from dm_dungeon.contracts.package import (
    DUNGEON_PACKAGE_SCHEMA_VERSION,
    DungeonPackage,
)


class UnsupportedSchemaVersionError(ValueError):
    """Raised when serialized input names an unsupported root schema."""


class InvalidContractDocumentError(ValueError):
    """Raised when a serialized root contract is not a JSON object."""


class InvalidDungeonPackageDocumentError(InvalidContractDocumentError):
    """Raised when serialized package input is not a JSON object."""


def to_canonical_json(contract: ContractModel) -> str:
    """Serialize a contract with stable key ordering and no insignificant space."""
    payload = contract.model_dump(mode="json", round_trip=True)
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def dungeon_design_v2_json_schema() -> dict[str, Any]:
    """Return the current compact V2 design JSON Schema document."""
    return DungeonDesignSpecV2.model_json_schema(mode="validation")


def load_dungeon_design_v2_json(
    document: str | bytes | bytearray,
) -> DungeonDesignSpecV2:
    """Validate serialized V2 design input, rejecting unknown versions first."""
    payload = json.loads(document)
    if not isinstance(payload, dict):
        raise InvalidContractDocumentError(
            "DungeonDesignSpecV2 document must be a JSON object"
        )
    actual_version = payload.get("schema_version")
    if actual_version != DUNGEON_DESIGN_V2_SCHEMA_VERSION:
        rendered = "<missing>" if actual_version is None else repr(actual_version)
        raise UnsupportedSchemaVersionError(
            f"Unsupported DungeonDesignSpecV2 schema version {rendered}; "
            f"expected {DUNGEON_DESIGN_V2_SCHEMA_VERSION!r}"
        )
    return DungeonDesignSpecV2.model_validate_json(document)


def dungeon_package_json_schema() -> dict[str, Any]:
    """Return the current DungeonPackage JSON Schema document."""
    return DungeonPackage.model_json_schema(mode="validation")


def load_dungeon_package_json(document: str | bytes | bytearray) -> DungeonPackage:
    """Validate a serialized DungeonPackage, rejecting unknown versions first."""
    payload = json.loads(document)
    if not isinstance(payload, dict):
        raise InvalidDungeonPackageDocumentError(
            "DungeonPackage document must be a JSON object"
        )

    actual_version = payload.get("schema_version")
    if actual_version != DUNGEON_PACKAGE_SCHEMA_VERSION:
        rendered = "<missing>" if actual_version is None else repr(actual_version)
        raise UnsupportedSchemaVersionError(
            f"Unsupported DungeonPackage schema version {rendered}; "
            f"expected {DUNGEON_PACKAGE_SCHEMA_VERSION!r}"
        )

    return DungeonPackage.model_validate_json(document)


def read_dungeon_design_v2(path: str | Path) -> DungeonDesignSpecV2:
    """Read and validate a compact V2 design JSON file."""
    return load_dungeon_design_v2_json(Path(path).read_bytes())


def read_dungeon_package(path: str | Path) -> DungeonPackage:
    """Read and validate a DungeonPackage JSON file."""
    return load_dungeon_package_json(Path(path).read_bytes())


def write_dungeon_package(path: str | Path, package: DungeonPackage) -> None:
    """Write canonical UTF-8 package JSON to a file."""
    Path(path).write_text(to_canonical_json(package), encoding="utf-8")
