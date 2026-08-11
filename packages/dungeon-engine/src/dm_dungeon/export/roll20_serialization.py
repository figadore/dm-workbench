"""Integrity validation and safe file adapters for Roll20 bundles."""

import hashlib
import io
import zipfile
from pathlib import Path

from PIL import Image

from dm_dungeon.export.roll20_contracts import (
    Roll20Artifact,
    Roll20AssetRole,
)
from dm_dungeon.serialization import to_canonical_json


def validate_roll20_artifact(artifact: Roll20Artifact) -> None:
    """Fail closed unless bytes, paths, dimensions, hashes, and ZIP agree."""
    if not artifact.result.success:
        if artifact.files or artifact.zip_data is not None:
            raise ValueError("failed Roll20 artifact cannot contain files")
        return
    manifest = artifact.result.manifest
    zip_data = artifact.zip_data
    if manifest is None or zip_data is None or artifact.result.bundle_sha256 is None:
        raise ValueError("successful Roll20 artifact is incomplete")
    files = {item.filename: item.data for item in artifact.files}
    if len(files) != len(artifact.files) or any(
        Path(name).name != name for name in files
    ):
        raise ValueError("bundle filenames must be unique safe relative basenames")

    grid_asset, gridless_asset = manifest.assets
    if (
        grid_asset.role is not Roll20AssetRole.GRID_ON_MAP
        or gridless_asset.role is not Roll20AssetRole.GRIDLESS_MAP
        or not grid_asset.filename.endswith(".grid.png")
        or not gridless_asset.filename.endswith(".gridless.png")
    ):
        raise ValueError("Roll20 assets must use paired grid filename suffixes")
    grid_prefix = grid_asset.filename.removesuffix(".grid.png")
    gridless_prefix = gridless_asset.filename.removesuffix(".gridless.png")
    if grid_prefix != gridless_prefix:
        raise ValueError("Roll20 paired asset filename prefixes must match")
    manifest_filename = f"{grid_prefix}.manifest.json"
    expected_names = {
        grid_asset.filename,
        gridless_asset.filename,
        manifest_filename,
    }
    if set(files) != expected_names:
        raise ValueError("Roll20 bundle must contain exactly two PNGs and its manifest")

    for asset in manifest.assets:
        data = files[asset.filename]
        if hashlib.sha256(data).hexdigest() != asset.sha256:
            raise ValueError(f"Roll20 asset hash mismatch: {asset.filename}")
        try:
            with Image.open(io.BytesIO(data)) as image:
                dimensions = image.size
                image.verify()
        except (OSError, SyntaxError) as error:
            raise ValueError(f"invalid Roll20 PNG: {asset.filename}") from error
        if dimensions != (asset.width_pixels, asset.height_pixels):
            raise ValueError(f"Roll20 asset dimensions mismatch: {asset.filename}")

    expected_manifest = to_canonical_json(manifest).encode("utf-8")
    if files[manifest_filename] != expected_manifest:
        raise ValueError("Roll20 manifest bytes do not match the result contract")
    if hashlib.sha256(zip_data).hexdigest() != artifact.result.bundle_sha256:
        raise ValueError("Roll20 ZIP hash does not match the result contract")
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)) or set(names) != expected_names:
                raise ValueError("Roll20 ZIP paths do not match bundle files")
            archived = {name: archive.read(name) for name in names}
    except zipfile.BadZipFile as error:
        raise ValueError("invalid Roll20 ZIP") from error
    if archived != files:
        raise ValueError("Roll20 ZIP contents do not match bundle files")


def write_roll20_zip(path: str | Path, artifact: Roll20Artifact) -> None:
    """Validate and write a successful deterministic bundle ZIP."""
    validate_roll20_artifact(artifact)
    if artifact.zip_data is None or not artifact.result.success:
        raise ValueError("cannot write an unsuccessful Roll20 artifact")
    Path(path).write_bytes(artifact.zip_data)


def write_roll20_directory(path: str | Path, artifact: Roll20Artifact) -> None:
    """Validate and write files beneath one caller-selected directory."""
    validate_roll20_artifact(artifact)
    if artifact.zip_data is None or not artifact.result.success:
        raise ValueError("cannot write an unsuccessful Roll20 artifact")
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    for bundle_file in artifact.files:
        (directory / bundle_file.filename).write_bytes(bundle_file.data)
