"""Small deterministic DM-only presentation helpers; no authoring or state writes."""

from __future__ import annotations

import re
from collections.abc import Mapping

from pydantic import BaseModel

from dm_assistant.orchestration.dungeons.contracts import (
    DungeonDmGuide,
    DungeonGuideRoom,
)

_ROOM_REFERENCE = re.compile(r"\[\[room:([^\[\]\n]+)\]\]")


def room_reference_targets(value: BaseModel) -> set[str]:
    """Explicit prose links are local handles, never model-assigned display numbers."""
    text = value.model_dump_json()
    matches = _ROOM_REFERENCE.findall(text)
    targets = set(matches)
    if text.count("[[room:") != len(matches):
        targets.add("")  # Invalid syntax cannot be mistaken for a known local ref.
    return targets


def room_link(room: DungeonGuideRoom) -> str:
    return (
        f"[{room.name} ({room.map_reference.token})](#room-{room.map_reference.token})"
    )


def resolve_room_references(text: str, rooms: Mapping[str, DungeonGuideRoom]) -> str:
    def replace(match: re.Match[str]) -> str:
        if match[1] not in rooms:
            raise ValueError("unknown room reference in guide prose")
        return room_link(rooms[match[1]])

    resolved = _ROOM_REFERENCE.sub(replace, text)
    if "[[room:" in resolved:
        raise ValueError("malformed room reference in guide prose")
    return resolved


def room_exit_lines(guide: DungeonDmGuide, room: DungeonGuideRoom) -> tuple[str, ...]:
    rooms = {item.room_id: item for item in guide.rooms}
    lines = []
    for connection in guide.connections:
        if room.room_id == connection.from_room_id:
            target, direction = connection.to_room_id, connection.from_direction
        elif room.room_id == connection.to_room_id:
            target, direction = connection.from_room_id, connection.to_direction
        else:
            continue
        state = []
        if connection.concealed:
            state.append("secret")
        if connection.gate_id:
            state.append(connection.gate_kind.value)
        if connection.trap_id:
            state.append("trapped")
        token = (
            f" ({connection.map_reference.token})" if connection.map_reference else ""
        )
        label = ", ".join(state) if state else "open"
        # No centre-to-centre guess for missing/unsupported opening geometry.
        departure = direction.title() if direction else "Direction unavailable"
        lines.append(
            f"- {departure}: {connection.passage}{token} to {room_link(rooms[target])} — {label}."
        )
    return tuple(lines)
