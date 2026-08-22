"""Proof-carrying contracts for the constructive Tier A topology grammar."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from dm_dungeon.contracts.common import ContractModel, OpaqueId
from dm_dungeon.contracts.plan import LocalRef

TOPOLOGY_CERTIFICATE_VERSION: Literal["topology-certificate-v1"] = (
    "topology-certificate-v1"
)
TOPOLOGY_GRAMMAR_VERSION: Literal["series-parallel-with-spurs-v1"] = (
    "series-parallel-with-spurs-v1"
)
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonNegativeCount = Annotated[int, Field(ge=0)]
PositiveCount = Annotated[int, Field(ge=1)]


class CertifiedRoomRef(ContractModel):
    ref: LocalRef
    room_id: OpaqueId


class CertifiedConnectionRef(ContractModel):
    ref: LocalRef
    connection_id: OpaqueId
    kind: Literal["critical_path", "branch", "loop"]
    from_room_id: OpaqueId
    to_room_id: OpaqueId


class GrammarStep(ContractModel):
    kind: Literal["critical_path", "branch", "loop"]
    ref: LocalRef
    room_ids: tuple[OpaqueId, ...] = Field(min_length=2)
    connection_ids: tuple[OpaqueId, ...] = Field(min_length=1)


class CriticalPathWitness(ContractModel):
    room_ids: tuple[OpaqueId, ...] = Field(min_length=2)
    connection_ids: tuple[OpaqueId, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def require_path_cardinality(self) -> Self:
        if len(self.connection_ids) != len(self.room_ids) - 1:
            raise ValueError("critical-path edges must be one fewer than rooms")
        return self


class BranchWitness(ContractModel):
    ref: LocalRef
    attachment_room_id: OpaqueId
    room_ids: tuple[OpaqueId, ...] = Field(min_length=1)
    connection_ids: tuple[OpaqueId, ...] = Field(min_length=1)
    band: Literal["upper", "lower"]
    band_index: PositiveCount

    @model_validator(mode="after")
    def require_branch_cardinality(self) -> Self:
        if len(self.connection_ids) != len(self.room_ids):
            raise ValueError("branch paths require one edge per introduced room")
        return self


class LoopWitness(ContractModel):
    ref: LocalRef
    from_room_id: OpaqueId
    to_room_id: OpaqueId
    connection_id: OpaqueId
    cycle_room_ids: tuple[OpaqueId, ...] = Field(min_length=3)
    cycle_connection_ids: tuple[OpaqueId, ...] = Field(min_length=3)
    interval_start: NonNegativeCount
    interval_end: PositiveCount
    band: Literal["loop"] = "loop"
    band_index: PositiveCount = 1
    secret: bool


class GateReachabilityWitness(ContractModel):
    gate_id: OpaqueId
    dependency_id: OpaqueId
    dependency_room_id: OpaqueId
    blocked_connection_id: OpaqueId
    reachable_before_gate_room_ids: tuple[OpaqueId, ...]
    opened_order: PositiveCount


class RoomDemandWitness(ContractModel):
    room_id: OpaqueId
    degree: NonNegativeCount
    required_ports: NonNegativeCount
    opening_width_cells: PositiveCount = 1
    separation_clearance_cells: NonNegativeCount
    minimum_boundary_cells: NonNegativeCount
    base_interior_cells: PositiveCount
    encounter_cells: NonNegativeCount
    feature_cells: NonNegativeCount
    trap_cells: NonNegativeCount
    required_interior_cells: PositiveCount


class EmbeddingRoomWitness(ContractModel):
    room_id: OpaqueId
    region: Literal["backbone", "branch"]
    order: NonNegativeCount
    band: Literal["backbone", "upper", "lower"]
    band_index: NonNegativeCount


class TopologyCertificate(ContractModel):
    """Deterministic proof data that validators recompute rather than trust."""

    certificate_version: Literal["topology-certificate-v1"]
    grammar_version: Literal["series-parallel-with-spurs-v1"]
    plan_hash: Sha256
    topology_hash: Sha256
    topology_id: OpaqueId
    rooms: tuple[CertifiedRoomRef, ...]
    connections: tuple[CertifiedConnectionRef, ...]
    grammar_steps: tuple[GrammarStep, ...] = Field(min_length=1)
    critical_path: CriticalPathWitness
    component_count: PositiveCount
    room_count: PositiveCount
    connection_count: NonNegativeCount
    cycle_rank: NonNegativeCount
    branches: tuple[BranchWitness, ...]
    loops: tuple[LoopWitness, ...]
    gates: tuple[GateReachabilityWitness, ...]
    full_reachable_room_ids: tuple[OpaqueId, ...]
    public_reachable_room_ids: tuple[OpaqueId, ...]
    room_demands: tuple[RoomDemandWitness, ...]
    embedding_rooms: tuple[EmbeddingRoomWitness, ...]
    required_bands: PositiveCount


class TopologyCertificateDiagnostic(ContractModel):
    code: Annotated[str, Field(pattern=r"^certificate\.[a-z0-9_]+$")]
    path: Annotated[str, Field(min_length=1, max_length=256)]
    affected_ids: tuple[OpaqueId, ...] = Field(max_length=8)
    repair: Annotated[str, Field(min_length=1, max_length=300)]


class TopologyCertificateValidationReport(ContractModel):
    certificate_version: Literal["topology-certificate-v1"]
    topology_id: OpaqueId
    valid: bool
    diagnostics: tuple[TopologyCertificateDiagnostic, ...]

    @model_validator(mode="after")
    def require_valid_to_match_diagnostics(self) -> Self:
        if self.valid == bool(self.diagnostics):
            raise ValueError("valid must be true exactly when diagnostics are empty")
        return self
