"""File adapters for deterministic SVG render results."""

from pathlib import Path

from dm_dungeon.rendering.contracts import SvgRenderResult


def write_svg(path: str | Path, result: SvgRenderResult) -> None:
    """Write a successful SVG document without changing its bytes."""
    if not result.success or result.svg is None:
        raise ValueError("cannot write an unsuccessful SVG render result")
    Path(path).write_text(result.svg, encoding="utf-8")
