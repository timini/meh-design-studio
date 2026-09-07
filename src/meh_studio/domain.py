"""Versioned immutable inputs. Field suffixes define SI units; extra keys fail."""
from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Positive = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Nonnegative = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Identifier = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,95}$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    schema_version: Literal[1] = 1

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True,
                          separators=(",", ":"), allow_nan=False)

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


class Band(Record):
    low_hz: Positive
    high_hz: Positive

    @model_validator(mode="after")
    def ordered(self):
        if self.low_hz >= self.high_hz:
            raise ValueError("band low_hz must be below high_hz")
        return self

    def contains(self, other: Band) -> bool:
        return self.low_hz <= other.low_hz and self.high_hz >= other.high_hz


class Printer(Record):
    # No hidden bed/wall defaults. These describe a proposed printing process.
    envelope_m: tuple[Positive, Positive, Positive]
    minimum_wall_m: Positive

    @model_validator(mode="after")
    def wall_fits(self):
        if 2 * self.minimum_wall_m >= min(self.envelope_m):
            raise ValueError("minimum wall consumes the printer envelope")
        return self


class OperatingLevel(Record):
    spl_db: Annotated[float, Field(strict=True, ge=0, le=150)]
    distance_m: Positive
    # Exact protocol identity: includes stimulus, duration and crest factor.
    signal_definition: Annotated[str, Field(min_length=10)]


class LevelQualification(Record):
    min_spl_db: Annotated[float, Field(strict=True, ge=0, le=150)]
    max_spl_db: Annotated[float, Field(strict=True, ge=0, le=150)]
    distance_m: Positive
    signal_definition: Annotated[str, Field(min_length=10)]

    @model_validator(mode="after")
    def ordered_levels(self):
        if self.min_spl_db > self.max_spl_db:
            raise ValueError("qualified SPL range must be ordered")
        return self


class DesignBrief(Record):
    id: Identifier
    band: Band
    max_drivers: Annotated[int, Field(strict=True, ge=3, le=64)]
    driver_budget: Positive
    total_material_budget: Positive
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$")]
    target_spl_db: Annotated[float, Field(strict=True, ge=0, le=150, allow_inf_nan=False)]
    distance_m: Positive
    level_definition: Annotated[str, Field(min_length=10)]
    response_tolerance_db: Positive
    horizontal_coverage_deg: Annotated[float, Field(strict=True, gt=0, le=180)]
    vertical_coverage_deg: Annotated[float, Field(strict=True, gt=0, le=180)]
    coverage_control_from_hz: Positive
    assembled_envelope_m: tuple[Positive, Positive, Positive]
    printer: Printer
    topology_families: tuple[Literal["straight_3", "straight_5"], ...]

    @property
    def operating_level(self) -> OperatingLevel:
        return OperatingLevel(spl_db=self.target_spl_db, distance_m=self.distance_m,
                              signal_definition=self.level_definition)

    @model_validator(mode="after")
    def consistent(self):
        if self.total_material_budget < self.driver_budget:
            raise ValueError("total material budget must include the driver budget")
        if not self.band.low_hz <= self.coverage_control_from_hz <= self.band.high_hz:
            raise ValueError("coverage control frequency must be inside the target band")
        if not self.topology_families or len(set(self.topology_families)) != len(self.topology_families):
            raise ValueError("topology families must be nonempty and unique")
        if any(int(f.rsplit("_", 1)[1]) > self.max_drivers for f in self.topology_families):
            raise ValueError("a selected topology exceeds max_drivers")
        return self


class Provenance(Record):
    kind: Literal["measured", "reported", "derived", "synthetic"]
    source: Annotated[str, Field(min_length=1)]
    permission: Literal["private_import", "redistribution_allowed", "unknown"]
    permission_evidence: str | None = None

    @model_validator(mode="after")
    def rights(self):
        if self.permission == "redistribution_allowed" and not self.permission_evidence:
            raise ValueError("redistribution requires permission evidence")
        return self


class SourceModel(Record):
    re_ohm: Positive
    le_h: Nonnegative
    bl_n_a: Positive
    mmd_kg: Positive
    cms_m_n: Positive
    rms_ns_m: Positive
    sd_m2: Positive
    # Explicit dry mass only. Mms is not an accepted alias.
    provenance: Provenance


class Qualification(Record):
    band: Band
    level: LevelQualification
    mounting: Annotated[str, Field(min_length=1)]
    report_sha256: Digest
    reviewer: Annotated[str, Field(min_length=1)]


class DriverRevision(Record):
    id: Identifier
    revision: Annotated[int, Field(strict=True, ge=1)]
    manufacturer: Annotated[str, Field(min_length=1)]
    model: Annotated[str, Field(min_length=1)]
    outer_diameter_m: Positive
    cutout_diameter_m: Positive
    depth_m: Positive
    provenance: Provenance
    source_model: SourceModel | None = None
    qualification: Qualification | None = None

    @model_validator(mode="after")
    def qualified_source(self):
        if self.cutout_diameter_m > self.outer_diameter_m:
            raise ValueError("cutout cannot exceed the declared outer diameter")
        if self.qualification:
            if self.source_model is None:
                raise ValueError("qualification requires a source model")
            if self.provenance.kind == "synthetic" or self.source_model.provenance.kind == "synthetic":
                raise ValueError("synthetic records cannot be acoustically qualified")
        return self

    def eligibility_reasons(self, band: Band, mounting: str, level: OperatingLevel) -> tuple[str, ...]:
        reasons = []
        if self.source_model is None:
            reasons.append("missing_source_model")
        if self.provenance.kind == "synthetic" or (
            self.source_model and self.source_model.provenance.kind == "synthetic"
        ):
            reasons.append("synthetic_record")
        if self.qualification is None:
            reasons.append("missing_qualification")
        else:
            if not self.qualification.band.contains(band):
                reasons.append("outside_qualified_band")
            if self.qualification.mounting != mounting:
                reasons.append("mounting_mismatch")
            conditions = self.qualification.level
            if not conditions.min_spl_db <= level.spl_db <= conditions.max_spl_db:
                reasons.append("outside_qualified_level")
            # Do not extrapolate propagation or equate different test signals.
            if conditions.distance_m != level.distance_m:
                reasons.append("level_distance_mismatch")
            if conditions.signal_definition != level.signal_definition:
                reasons.append("signal_mismatch")
        return tuple(reasons)
