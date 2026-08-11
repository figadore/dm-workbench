"""Binary asset and canonical manifest file adapters."""

from pathlib import Path

from dm_dungeon.export.contracts import PdfArtifact, PngArtifact
from dm_dungeon.serialization import to_canonical_json


def write_png_artifact(
    asset_path: str | Path,
    manifest_path: str | Path,
    artifact: PngArtifact,
) -> None:
    """Write successful PNG bytes and their canonical manifest."""
    if artifact.data is None or artifact.result.manifest is None:
        raise ValueError("cannot write an unsuccessful PNG artifact")
    Path(asset_path).write_bytes(artifact.data)
    Path(manifest_path).write_text(
        to_canonical_json(artifact.result.manifest),
        encoding="utf-8",
    )


def write_pdf_artifact(
    asset_path: str | Path,
    manifest_path: str | Path,
    artifact: PdfArtifact,
) -> None:
    """Write successful PDF bytes and their canonical manifest."""
    if artifact.data is None or artifact.result.manifest is None:
        raise ValueError("cannot write an unsuccessful PDF artifact")
    Path(asset_path).write_bytes(artifact.data)
    Path(manifest_path).write_text(
        to_canonical_json(artifact.result.manifest),
        encoding="utf-8",
    )
