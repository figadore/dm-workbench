"""Code-owned deterministic SVG themes."""

from dataclasses import dataclass

from dm_dungeon.rendering.contracts import SvgThemeName


@dataclass(frozen=True, slots=True)
class SvgTheme:
    """Trusted style values selected by a named theme."""

    css: str
    background: str
    grid_stroke: str
    wall_stroke: str
    secret_stroke: str
    annotation_stroke: str
    callout_css: str


LOW_INK_THEME = SvgTheme(
    css=(
        ".map-background{fill:#fff}"
        ".grid-line{stroke:#d2d2d2;stroke-width:.5;vector-effect:non-scaling-stroke}"
        ".room{fill:none;stroke:#111;stroke-width:2;vector-effect:non-scaling-stroke}"
        ".corridor-outline{fill:none;stroke:#111;stroke-linecap:square;vector-effect:non-scaling-stroke}"
        ".corridor{fill:#fff;stroke:none}"
        ".door{stroke:#111;stroke-width:6;vector-effect:non-scaling-stroke}"
        ".door-secret{stroke:#555;stroke-dasharray:4 3}"
        ".door-trapped{stroke:#111;stroke-dasharray:2 2}"
        ".terrain{fill:#eee;stroke:#777;stroke-width:1;vector-effect:non-scaling-stroke}"
        ".zone{fill:none;stroke:#777;stroke-width:1;stroke-dasharray:4 3;vector-effect:non-scaling-stroke}"
        ".feature,.marker,.stair,.start-marker{fill:#fff;stroke:#111;stroke-width:1.5;vector-effect:non-scaling-stroke}"
        ".hazard{fill:none;stroke:#111;stroke-width:2;vector-effect:non-scaling-stroke}"
        ".label{fill:#111;font-family:system-ui,sans-serif;font-size:12px}"
        ".annotation{fill:#111;font-family:monospace;font-size:10px}"
    ),
    background="#fff",
    grid_stroke="#d2d2d2",
    wall_stroke="#111",
    secret_stroke="#555",
    annotation_stroke="#777",
    callout_css=(
        ".room-callout,.component-callout{fill:#fff;stroke:#111;stroke-width:1.5;vector-effect:non-scaling-stroke}"
        ".hazard-callout{fill:#fff;stroke:#111;stroke-width:1.5;vector-effect:non-scaling-stroke}"
        ".feature-callout{fill:#fff;stroke:#111;stroke-width:1.5;vector-effect:non-scaling-stroke}"
        ".callout-badge-shape{fill:#fff;stroke:#111;stroke-width:1.5;vector-effect:non-scaling-stroke}"
        ".callout-text,.callout-badge{fill:#111;font-family:system-ui,sans-serif;font-weight:bold}"
        ".callout-leader{stroke:#777;stroke-width:1;vector-effect:non-scaling-stroke}"
        ".map-legend-panel{fill:#fff;stroke:#111;stroke-width:1.5;vector-effect:non-scaling-stroke}"
        ".legend-title,.legend-text,.legend-symbol-text{fill:#111;font-family:system-ui,sans-serif;font-weight:bold}"
        ".legend-symbol{fill:#fff;stroke:#111;stroke-width:1.5;vector-effect:non-scaling-stroke}"
    ),
)

DRAFT_THEME = SvgTheme(
    css=(
        ".map-background{fill:#fff}"
        ".grid-line{stroke:#e2e2e2;stroke-width:.4;vector-effect:non-scaling-stroke}"
        ".room{fill:none;stroke:#444;stroke-width:1;vector-effect:non-scaling-stroke}"
        ".corridor-outline{fill:none;stroke:#777;stroke-linecap:square;vector-effect:non-scaling-stroke}"
        ".corridor{fill:#fff;stroke:none}"
        ".door{stroke:#444;stroke-width:5;vector-effect:non-scaling-stroke}"
        ".door-secret,.door-trapped{stroke-dasharray:3 3}"
        ".terrain,.zone{fill:none;stroke:#aaa;stroke-width:1;vector-effect:non-scaling-stroke}"
        ".feature,.marker,.stair,.hazard,.start-marker{fill:#fff;stroke:#666;stroke-width:1;vector-effect:non-scaling-stroke}"
        ".label{fill:#333;font-family:system-ui,sans-serif;font-size:11px}"
        ".annotation{fill:#555;font-family:monospace;font-size:9px}"
    ),
    background="#fff",
    grid_stroke="#e2e2e2",
    wall_stroke="#444",
    secret_stroke="#666",
    annotation_stroke="#aaa",
    callout_css=(
        ".room-callout,.component-callout,.hazard-callout,.feature-callout,.callout-badge-shape{fill:#fff;stroke:#555;stroke-width:1;vector-effect:non-scaling-stroke}"
        ".callout-text,.callout-badge{fill:#333;font-family:system-ui,sans-serif;font-weight:bold}"
        ".callout-leader{stroke:#999;stroke-width:1;vector-effect:non-scaling-stroke}"
        ".map-legend-panel{fill:#fff;stroke:#555;stroke-width:1;vector-effect:non-scaling-stroke}"
        ".legend-title,.legend-text,.legend-symbol-text{fill:#333;font-family:system-ui,sans-serif;font-weight:bold}"
        ".legend-symbol{fill:#fff;stroke:#555;stroke-width:1;vector-effect:non-scaling-stroke}"
    ),
)

THEMES = {
    SvgThemeName.LOW_INK: LOW_INK_THEME,
    SvgThemeName.DRAFT: DRAFT_THEME,
}


def get_theme(name: SvgThemeName) -> SvgTheme:
    """Return a trusted immutable theme by enum name."""
    return THEMES[name]
