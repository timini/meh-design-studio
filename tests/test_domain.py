import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from meh_studio.domain import Band, DesignBrief, DriverRevision, Provenance, SourceModel, OperatingLevel, LevelQualification

ROOT = Path(__file__).resolve().parents[1]
LEVEL = OperatingLevel(spl_db=90, distance_m=1,
                       signal_definition="Pink noise, 6 dB crest factor, 60 seconds")
QUALIFIED_LEVEL = {"min_spl_db": 80, "max_spl_db": 96, "distance_m": 1,
                   "signal_definition": LEVEL.signal_definition}


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
    assert "synthetic_record" in driver.eligibility_reasons(band, "load-a", LEVEL)
    with pytest.raises(ValidationError):
        DriverRevision.model_validate(driver.model_dump() | {"qualification": {
            "band": band.model_dump(), "level": QUALIFIED_LEVEL, "mounting": "load-a", "report_sha256": "a"*64,
            "reviewer": "test"}})


def test_declared_qualification_stays_in_band_and_mounting(driver):
    data = driver.model_dump()
    data["provenance"]["kind"] = "measured"
    data["source_model"]["provenance"]["kind"] = "measured"
    data["qualification"] = {"band": {"low_hz": 300, "high_hz": 2000},
                             "mounting": "load-a", "level": QUALIFIED_LEVEL, "report_sha256": "a"*64, "reviewer": "test"}
    record = DriverRevision.model_validate(data)
    assert record.eligibility_reasons(Band(low_hz=400, high_hz=1000), "load-a", LEVEL) == ()
    assert record.eligibility_reasons(Band(low_hz=100, high_hz=3000), "load-b", LEVEL) == (
        "outside_qualified_band", "mounting_mismatch")


def test_permission_needs_evidence():
    with pytest.raises(ValidationError):
        Provenance(kind="reported", source="a source", permission="redistribution_allowed")


@pytest.mark.parametrize("field", ["re_ohm", "le_h", "bl_n_a", "mmd_kg", "cms_m_n", "rms_ns_m", "sd_m2"])
@pytest.mark.parametrize("bad", [True, False, "1.0"])
def test_physical_source_values_are_strict(source, field, bad):
    with pytest.raises(ValidationError):
        SourceModel.model_validate(source.model_dump() | {field: bad})


@pytest.mark.parametrize("field", ["driver_budget", "total_material_budget", "target_spl_db", "distance_m",
    "response_tolerance_db", "horizontal_coverage_deg", "vertical_coverage_deg", "coverage_control_from_hz"])
def test_brief_physical_values_reject_boolean(brief_data, field):
    with pytest.raises(ValidationError):
        DesignBrief.model_validate(brief_data | {field: True})


def test_nested_dimensions_and_frequencies_reject_boolean(brief_data):
    with pytest.raises(ValidationError):
        Band(low_hz=True, high_hz=100)
    brief_data["printer"]["envelope_m"][0] = True
    with pytest.raises(ValidationError):
        DesignBrief.model_validate(brief_data)


@pytest.mark.parametrize("level_patch,reason", [
    ({"spl_db": 97}, "outside_qualified_level"),
    ({"spl_db": 79}, "outside_qualified_level"),
    ({"distance_m": 2}, "level_distance_mismatch"),
    ({"signal_definition": "Pink noise, 12 dB crest factor, 60 seconds"}, "signal_mismatch"),
])
def test_qualification_rejects_outside_level_conditions(driver, level_patch, reason):
    data = driver.model_dump()
    data["provenance"]["kind"] = "measured"
    data["source_model"]["provenance"]["kind"] = "measured"
    data["qualification"] = {"band": {"low_hz": 300, "high_hz": 2000}, "level": QUALIFIED_LEVEL,
                             "mounting": "load-a", "report_sha256": "a"*64, "reviewer": "test"}
    record = DriverRevision.model_validate(data)
    request = OperatingLevel.model_validate(LEVEL.model_dump() | level_patch)
    assert record.eligibility_reasons(Band(low_hz=400, high_hz=1000), "load-a", request) == (reason,)
    del data["qualification"]["level"]
    with pytest.raises(ValidationError):
        DriverRevision.model_validate(data)


def test_brief_level_conditions_are_preserved(brief_data):
    brief = DesignBrief.model_validate(brief_data)
    assert brief.operating_level.spl_db == brief.target_spl_db
    assert brief.operating_level.distance_m == brief.distance_m
    assert brief.operating_level.signal_definition == brief.level_definition
    with pytest.raises(ValidationError):
        LevelQualification.model_validate(QUALIFIED_LEVEL | {"min_spl_db": 100})
