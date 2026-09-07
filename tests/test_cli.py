import json
from pathlib import Path

from meh_studio.cli import main


def test_brief_cli_reports_feasibility_not_evaluated(capsys):
    path = Path(__file__).resolve().parents[1] / "examples/reference-brief.json"
    assert main(["validate-brief", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["acoustic_feasibility"] == "not_evaluated"


def test_reference_cli_is_not_a_solver_claim(capsys):
    assert main(["cavity-reference", "--lengths-m", "1", "1", "1", "--max-hz", "200"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["acoustic_solver_executed"] is False
    assert len(result["modes"]) == 3


def test_missing_and_invalid_files_produce_structured_errors(tmp_path, capsys):
    assert main(["validate-brief", str(tmp_path / "missing.json")]) == 2
    assert "error" in json.loads(capsys.readouterr().err)
    bad = tmp_path / "bad.json"
    bad.write_text('{"band": NaN}')
    assert main(["validate-brief", str(bad)]) == 2
    assert "error" in json.loads(capsys.readouterr().err)


def test_catalogue_cli(tmp_path, driver, capsys):
    path, record = tmp_path / "private.sqlite", tmp_path / "record.json"
    record.write_text(driver.canonical_json())
    assert main(["catalogue", "init", str(path)]) == 0
    capsys.readouterr()
    assert main(["catalogue", "add", str(path), str(record)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["added"] is True
    assert result["qualification"] == "not_qualified"
    assert main(["catalogue", "list", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["drivers"][0]["id"] == driver.id


def test_catalogue_cli_reports_declared_qualification_only_when_present(tmp_path, driver, capsys):
    from meh_studio.domain import DriverRevision
    data = driver.model_dump()
    data["provenance"]["kind"] = "measured"
    data["source_model"]["provenance"]["kind"] = "measured"
    data["qualification"] = {
        "band": {"low_hz": 300, "high_hz": 2000}, "mounting": "load-a",
        "level": {"min_spl_db": 80, "max_spl_db": 96, "distance_m": 1,
                  "signal_definition": "Pink noise, 6 dB crest factor, 60 seconds"},
        "report_sha256": "a" * 64, "reviewer": "test fixture reviewer"}
    record = tmp_path / "declared.json"
    record.write_text(DriverRevision.model_validate(data).canonical_json())
    database = tmp_path / "private.sqlite"
    assert main(["catalogue", "init", str(database)]) == 0
    capsys.readouterr()
    for expected_added in (True, False):
        assert main(["catalogue", "add", str(database), str(record)]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["added"] is expected_added
        assert result["qualification"] == "user_declared_not_independently_verified"
