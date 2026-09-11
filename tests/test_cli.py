import json
from pathlib import Path

from meh_studio.cli import main
import pytest


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


def test_utf8_inputs_do_not_depend_on_locale(tmp_path, driver, capsys, monkeypatch):
    from meh_studio.domain import DriverRevision
    # Emulate a legacy Windows locale when callers omit encoding.
    original_read = Path.read_text
    def locale_read(path, encoding=None, errors=None):
        return original_read(path, encoding=encoding or "cp1252", errors=errors)
    monkeypatch.setattr(Path, "read_text", locale_read)
    data = driver.model_dump()
    data["manufacturer"] = "Électroacoustique 日本"
    record = DriverRevision.model_validate(data)
    record_path, database = tmp_path / "utf8.json", tmp_path / "drivers.sqlite"
    record_path.write_text(record.canonical_json(), encoding="utf-8")
    # Ensure literal Unicode bytes, not only ASCII JSON escape sequences.
    record_path.write_text(json.dumps(record.model_dump(), ensure_ascii=False), encoding="utf-8")
    assert main(["catalogue", "init", str(database)]) == 0
    capsys.readouterr()
    assert main(["catalogue", "add", str(database), str(record_path)]) == 0
    assert json.loads(capsys.readouterr().out)["record_hash"] == record.content_hash
    example = Path(__file__).resolve().parents[1] / "examples/reference-brief.json"
    brief = json.loads(original_read(example, encoding="utf-8"))
    brief["level_definition"] = "Bruit rose, durée 60 s, référence 日本"
    brief_path = tmp_path / "brief.json"
    brief_path.write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    assert main(["validate-brief", str(brief_path)]) == 0
    assert json.loads(capsys.readouterr().out)["brief"]["level_definition"] == brief["level_definition"]


@pytest.mark.parametrize('command',['solve-project','optimise','resume-optimise'])
def test_explicit_reference_backend_reaches_workflow_commands(command,tmp_path,monkeypatch,capsys):
    from meh_studio.boundary_lab import BoundaryLabRuntime
    import meh_studio.optimisation as search
    import meh_studio.search_resume as resume
    root=Path(__file__).resolve().parents[1]
    observed=[]
    def capture(runtime):
        observed.append((runtime.backend,runtime.julia_threads))
        return {'status':'test-dispatch-only'}
    monkeypatch.setattr(BoundaryLabRuntime,'solve',lambda self,*args,**kwargs:capture(self))
    monkeypatch.setattr(search,'optimise',lambda brief,base,database,runtime,*args,**kwargs:capture(runtime))
    monkeypatch.setattr(resume,'resume_optimise',lambda source,runtime,*args:capture(runtime))
    extra=[]
    if command=='solve-project':
        path=tmp_path/'project.json'
        request=tmp_path/'request.json';request.write_text('{"frequencies_hz":[1000]}')
        extra=['--request',str(request)]
    elif command=='optimise':
        path=root/'examples/synthetic-search-brief.json'
        extra=['--geometry',str(root/'examples/three-driver-geometry.json'),'--database',str(tmp_path/'db')]
    else:
        path=tmp_path/'search'
    result=main([command,str(path),*extra,'--checkout',str(tmp_path),'--python','python',
        '--julia','julia','--output',str(tmp_path/'output'),'--backend','coupled_reference','--julia-threads','2'])
    assert result==0,capsys.readouterr()
    assert observed==[('coupled_reference',2)]
