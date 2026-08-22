"""Canonical JSON and file adapters for dungeon package contracts."""

import json
from pathlib import Path
from typing import Any

from dm_dungeon.contracts.common import ContractModel
from dm_dungeon.contracts.package import (
    DUNGEON_PACKAGE_SCHEMA_VERSION,
    DungeonPackage,
)
from dm_dungeon.contracts.plan import DUNGEON_PLAN_SCHEMA_VERSION, DungeonPlan


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


def dungeon_plan_json_schema() -> dict[str, Any]:
    """Return the sole provider-visible alpha V1 plan schema."""
    return DungeonPlan.model_json_schema(mode="validation")


def load_dungeon_plan_json(document: str | bytes | bytearray) -> DungeonPlan:
    """Validate serialized V1 plan input, rejecting unknown versions first."""
    payload = json.loads(document)
    if not isinstance(payload, dict):
        raise InvalidContractDocumentError("DungeonPlan document must be a JSON object")
    actual_version = payload.get("schema_version")
    if actual_version != DUNGEON_PLAN_SCHEMA_VERSION:
        rendered = "<missing>" if actual_version is None else repr(actual_version)
        raise UnsupportedSchemaVersionError(
            f"Unsupported DungeonPlan schema version {rendered}; "
            f"expected {DUNGEON_PLAN_SCHEMA_VERSION!r}"
        )
    return DungeonPlan.model_validate_json(document)


def dungeon_package_json_schema() -> dict[str, Any]:
    """Return the sole alpha V1 DungeonPackage JSON Schema document."""
    return DungeonPackage.model_json_schema(mode="validation")


def load_dungeon_package_json(
    document: str | bytes | bytearray,
) -> DungeonPackage:
    """Validate the sole alpha V1 package, rejecting other versions."""
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


def read_dungeon_plan(path: str | Path) -> DungeonPlan:
    """Read and validate a compact V1 plan JSON file."""
    return load_dungeon_plan_json(Path(path).read_bytes())


def read_dungeon_package(path: str | Path) -> DungeonPackage:
    """Read and validate a DungeonPackage JSON file."""
    return load_dungeon_package_json(Path(path).read_bytes())


def write_dungeon_package(
    path: str | Path,
    package: DungeonPackage,
) -> None:
    """Write canonical UTF-8 package JSON to a file."""
    Path(path).write_text(to_canonical_json(package), encoding="utf-8")
