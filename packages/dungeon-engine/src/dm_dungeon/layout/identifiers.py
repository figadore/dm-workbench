"""Stable deterministic IDs for auxiliary generated components."""

import hashlib


def derive_component_id(
    prefix: str,
    package_id: str,
    generator_version: str,
    stable_component_key: str,
) -> str:
    """Derive an opaque ID without random UUIDs or geometry-dependent values."""
    material = "\x1f".join(
        (package_id, generator_version, stable_component_key)
    ).encode()
    digest = hashlib.sha256(material).hexdigest()[:24]
    return f"{prefix}_{digest}"
