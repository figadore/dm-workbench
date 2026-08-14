"""Preparation contracts reject incomplete provenance and unknown fields."""

import uuid

import pytest
from pydantic import ValidationError

from dm_assistant.modules.preparation import (
    ArtifactAssetRole,
    AttachArtifactAsset,
    ContextSourceLink,
    DungeonGenerationContext,
    GenerationContextEnvelope,
    GenerationContextPin,
    PendingArtifactAsset,
    PublishGeneratedPackage,
    RequiredArtifactAsset,
    StartGenerationRun,
    ToolRunPin,
    VisibilityPolicy,
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


def test_generation_context_envelope_round_trips_hash_and_rejects_grounding() -> None:
    payload = DungeonGenerationContext(
        context_version="1.0.0",
        prompt_input_sha256="a" * 64,
        requested_constraints=("single entrance", "low light"),
        preparation_owner_id="dm",
        standalone_provenance="prompt_to_dungeon",
    )
    envelope = GenerationContextEnvelope(
        context_kind="dungeon_generation",
        payload_version="1.0.0",
        visibility_policy=VisibilityPolicy.DM_ONLY,
        payload=payload.model_dump(mode="json"),
        payload_sha256=canonical_json_sha256(payload.model_dump(mode="json")),
    )

    assert envelope.payload_sha256 == canonical_json_sha256(
        payload.model_dump(mode="json")
    )
    assert envelope.campaign_revision_id is None
    assert envelope.corpus_snapshot_id is None
    assert envelope.rules_profile_id is None

    with pytest.raises(ValidationError, match="does not match payload"):
        GenerationContextEnvelope.model_validate(
            {
                **envelope.model_dump(),
                "payload_sha256": "b" * 64,
            }
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


def test_generated_package_requires_exact_declared_asset_set() -> None:
    common = {
        "campaign_id": uuid.uuid4(),
        "generation_run_id": uuid.uuid4(),
        "title": "Synthetic complete package",
        "schema_version": "1.0.0",
        "specification": {"package_id": "synthetic"},
        "validation_report": {"valid": True},
        "change_summary": "Publish a complete synthetic package.",
        "created_by": "synthetic-dm",
        "assets": (
            PendingArtifactAsset(
                role=ArtifactAssetRole.SPECIFICATION,
                media_type="application/json",
                data=b"{}",
            ),
        ),
    }
    package = PublishGeneratedPackage(
        **common,
        required_assets=(RequiredArtifactAsset(role=ArtifactAssetRole.SPECIFICATION),),
    )
    assert package.assets == common["assets"]

    with pytest.raises(ValidationError, match="required role set"):
        PublishGeneratedPackage(
            **common,
            required_assets=(RequiredArtifactAsset(role=ArtifactAssetRole.MANIFEST),),
        )


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
