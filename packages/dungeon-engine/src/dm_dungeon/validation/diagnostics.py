"""Structured deterministic validation diagnostics."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import model_validator

from dm_dungeon.contracts.common import (
    ContractModel,
    NonEmptyText,
    OpaqueId,
)

TOPOLOGY_VALIDATOR_VERSION: Literal["1.0.0"] = "1.0.0"


class DiagnosticSeverity(StrEnum):
    """Machine-readable validation severity."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class TopologyDiagnosticCode(StrEnum):
    """Stable codes emitted by topology validation."""

    BRANCH_NOT_REALIZED = "topology.branch_not_realized"
    CHOKEPOINT_NOT_REALIZED = "topology.chokepoint_not_realized"
    CLUE_GATE_MISMATCH = "topology.clue_gate_mismatch"
    FLOOR_TRANSITION_INVALID = "topology.floor_transition_invalid"
    GATE_DEPENDENCY_CYCLE = "topology.gate_dependency_cycle"
    GATE_UNRESOLVABLE = "topology.gate_unresolvable"
    KEY_GATE_MISMATCH = "topology.key_gate_mismatch"
    LOOP_NOT_REALIZED = "topology.loop_not_realized"
    MISSING_ENTRANCE = "topology.missing_entrance"
    MISSING_EXIT = "topology.missing_exit"
    REQUIRED_ROOM_GATE_BLOCKED = "topology.required_room_gate_blocked"
    REQUIRED_ROOM_UNREACHABLE_FROM_ENTRANCE = (
        "topology.required_room_unreachable_from_entrance"
    )
    REQUIRED_ROOM_UNREACHABLE_FROM_EXIT = "topology.required_room_unreachable_from_exit"
    SAME_FLOOR_CONNECTION_INVALID = "topology.same_floor_connection_invalid"
    SECRET_BYPASS_NOT_REALIZED = "topology.secret_bypass_not_realized"
    SECRET_BYPASS_NOT_SECRET = "topology.secret_bypass_not_secret"
    SELF_CONNECTION = "topology.self_connection"
    UNKNOWN_CLUE_REFERENCE = "topology.unknown_clue_reference"
    UNKNOWN_CONNECTION_REFERENCE = "topology.unknown_connection_reference"
    UNKNOWN_FLOOR_REFERENCE = "topology.unknown_floor_reference"
    UNKNOWN_GATE_REFERENCE = "topology.unknown_gate_reference"
    UNKNOWN_KEY_REFERENCE = "topology.unknown_key_reference"
    UNKNOWN_ROOM_REFERENCE = "topology.unknown_room_reference"


class ValidationDiagnostic(ContractModel):
    """One deterministic, repair-oriented validation finding."""

    code: TopologyDiagnosticCode
    severity: DiagnosticSeverity
    message: NonEmptyText
    affected_ids: tuple[OpaqueId, ...]
    repair_hint: NonEmptyText


class TopologyValidationReport(ContractModel):
    """Complete deterministic validation result for one topology graph."""

    validator_version: Literal["1.0.0"]
    topology_id: OpaqueId
    valid: bool
    diagnostics: tuple[ValidationDiagnostic, ...]

    @model_validator(mode="after")
    def valid_matches_diagnostics(self) -> Self:
        has_errors = any(
            item.severity is DiagnosticSeverity.ERROR for item in self.diagnostics
        )
        if self.valid == has_errors:
            raise ValueError("valid must be false exactly when error diagnostics exist")
        return self
