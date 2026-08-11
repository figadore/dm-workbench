"""JSON/file adapters for versioned layout requests and results."""

import json
from pathlib import Path

from dm_dungeon.layout.contracts import (
    LAYOUT_REQUEST_SCHEMA_VERSION,
    LayoutRequest,
    LayoutResult,
)
from dm_dungeon.serialization import (
    InvalidContractDocumentError,
    UnsupportedSchemaVersionError,
    to_canonical_json,
)


def load_layout_request_json(document: str | bytes | bytearray) -> LayoutRequest:
    """Validate a serialized layout request with explicit version rejection."""
    payload = json.loads(document)
    if not isinstance(payload, dict):
        raise InvalidContractDocumentError(
            "LayoutRequest document must be a JSON object"
        )
    actual_version = payload.get("schema_version")
    if actual_version != LAYOUT_REQUEST_SCHEMA_VERSION:
        rendered = "<missing>" if actual_version is None else repr(actual_version)
        raise UnsupportedSchemaVersionError(
            f"Unsupported LayoutRequest schema version {rendered}; "
            f"expected {LAYOUT_REQUEST_SCHEMA_VERSION!r}"
        )
    return LayoutRequest.model_validate_json(document)


def read_layout_request(path: str | Path) -> LayoutRequest:
    """Read and validate a layout request JSON file."""
    return load_layout_request_json(Path(path).read_bytes())


def write_layout_result(path: str | Path, result: LayoutResult) -> None:
    """Write one canonical layout result document."""
    Path(path).write_text(to_canonical_json(result), encoding="utf-8")
