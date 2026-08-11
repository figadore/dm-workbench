"""Preparation contracts reject incomplete provenance and unknown fields."""

import uuid

import pytest
from pydantic import ValidationError

from dm_assistant.modules.preparation import (
    ArtifactAssetRole,
    AttachArtifactAsset,
    ContextSourceLink,
    GenerationContextPin,
    StartGenerationRun,
    ToolRunPin,
    canonical_json_sha256,
)


def context_pin() -> GenerationContextPin:
    payload = {"location_ids": ["loc_synthetic"], "tone": "tense"}
    return GenerationContextPin(
        envelope_kind="dungeon_generation",
        payload_version="1.0.0",
        envelope={
            "schema_version": "1.0.0",
            "context_kind": "dungeon_generation",
            "payload": payload,
        },
        payload_sha256=canonical_json_sha256(payload),
        source_links=(
            ContextSourceLink(
                source_kind="document_revision",
                source_id="source-synthetic",
                revision_id="revision-synthetic",
                sha256="a" * 64,
            ),
        ),
    )


def test_context_pin_verifies_canonical_payload_hash() -> None:
    context = context_pin()

    assert context.payload_sha256 == canonical_json_sha256(context.envelope["payload"])

    payload = context.model_dump()
    payload["payload_sha256"] = "b" * 64
    with pytest.raises(ValidationError, match="does not match payload"):
        GenerationContextPin.model_validate(payload)


def test_context_pin_requires_payload_without_defining_domain_shape() -> None:
    with pytest.raises(ValidationError, match="requires a payload"):
        GenerationContextPin(
            envelope_kind="dungeon_generation",
            payload_version="1.0.0",
            envelope={"context_kind": "dungeon_generation"},
            payload_sha256="a" * 64,
        )


def test_generation_run_requires_schema_versions_and_strict_tool_pins() -> None:
    common = {
        "campaign_id": uuid.uuid4(),
        "generation_kind": "dungeon_layout",
        "input_scope": {"artifact": "synthetic"},
    }
    with pytest.raises(ValidationError):
        StartGenerationRun(**common, schema_versions={})

    run = StartGenerationRun(
        **common,
        seed=42,
        context=context_pin(),
        schema_versions={"dungeon_package": "1.0.0"},
        generator_versions={"layout": "orthogonal-v1"},
        renderer_versions={"svg": "svg-v1"},
        tool_runs=(
            ToolRunPin(
                tool_name="validate_topology",
                schema_version="1.0.0",
                input_sha256="c" * 64,
                output_sha256="d" * 64,
                status="succeeded",
            ),
        ),
    )
    assert run.seed == 42
    assert run.context is not None


def test_asset_attachment_rejects_unknown_roles_media_and_fields() -> None:
    values = {
        "campaign_id": uuid.uuid4(),
        "artifact_version_id": uuid.uuid4(),
        "role": ArtifactAssetRole.PLAYER_PNG,
        "media_type": "image/png",
        "data": b"png",
    }
    attachment = AttachArtifactAsset(**values)
    assert attachment.ordinal == 0

    with pytest.raises(ValidationError):
        AttachArtifactAsset(**values, unexpected="value")
    with pytest.raises(ValidationError):
        AttachArtifactAsset(**{**values, "media_type": "not a media type"})
