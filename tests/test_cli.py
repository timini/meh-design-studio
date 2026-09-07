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
    assert json.loads(capsys.readouterr().out)["added"] is True
    assert main(["catalogue", "list", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["drivers"][0]["id"] == driver.id
