import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from meh_studio.domain import Band, DesignBrief, DriverRevision, Provenance, SourceModel

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def brief_data():
    return json.loads((ROOT / "examples/reference-brief.json").read_text())


def test_brief_round_trip_is_canonical_and_immutable(brief_data):
    brief = DesignBrief.model_validate(brief_data)
    assert DesignBrief.model_validate_json(brief.canonical_json()) == brief
    assert len(brief.content_hash) == 64
    assert DesignBrief.model_validate(dict(reversed(list(brief_data.items())))).content_hash == brief.content_hash
    with pytest.raises(ValidationError):
        brief.max_drivers = 3


@pytest.mark.parametrize("patch", [
    {"max_drivers": 3}, {"max_drivers": True}, {"currency": "gbp"},
    {"driver_budget": 300}, {"target_spl_db": float("nan")},
    {"distance_m": float("inf")}, {"band": {"low_hz": 1000, "high_hz": 100}},
    {"coverage_control_from_hz": 20000}, {"topology_families": []},
    {"topology_families": ["straight_3", "straight_3"]},
    {"printer": {"envelope_m": [0.22, 0.22, 0.25], "minimum_wall_m": 0.2}},
    {"distance_mm": 1000},
])
def test_invalid_briefs_fail(brief_data, patch):
    with pytest.raises(ValidationError):
        DesignBrief.model_validate(brief_data | patch)


def test_missing_budget_is_not_zero(brief_data):
    del brief_data["driver_budget"]
    with pytest.raises(ValidationError):
        DesignBrief.model_validate(brief_data)


def test_air_loaded_mass_cannot_be_relabelled(source):
    data = source.model_dump()
    data["mms_kg"] = data.pop("mmd_kg")
    with pytest.raises(ValidationError):
        SourceModel.model_validate(data)


def test_synthetic_record_cannot_qualify(driver):
    band = Band(low_hz=300, high_hz=2000)
    assert "synthetic_record" in driver.eligibility_reasons(band, "load-a")
    with pytest.raises(ValidationError):
        DriverRevision.model_validate(driver.model_dump() | {"qualification": {
            "band": band.model_dump(), "mounting": "load-a", "report_sha256": "a"*64,
            "reviewer": "test"}})


def test_declared_qualification_stays_in_band_and_mounting(driver):
    data = driver.model_dump()
    data["provenance"]["kind"] = "measured"
    data["source_model"]["provenance"]["kind"] = "measured"
    data["qualification"] = {"band": {"low_hz": 300, "high_hz": 2000},
                             "mounting": "load-a", "report_sha256": "a"*64, "reviewer": "test"}
    record = DriverRevision.model_validate(data)
    assert record.eligibility_reasons(Band(low_hz=400, high_hz=1000), "load-a") == ()
    assert record.eligibility_reasons(Band(low_hz=100, high_hz=3000), "load-b") == (
        "outside_qualified_band", "mounting_mismatch")


def test_permission_needs_evidence():
    with pytest.raises(ValidationError):
        Provenance(kind="reported", source="a source", permission="redistribution_allowed")
