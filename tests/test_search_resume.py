import json
from pathlib import Path

import pytest

import meh_studio.optimisation as search
import meh_studio.search_resume as recovery
from meh_studio.boundary_lab import SolveRequest, _write_json, sha256
from meh_studio.catalogue import Catalogue
from test_optimisation import inputs


class Runtime:
    def verify(self):
        return {'fixture': 'test-only'}


def fake_score(*args):
    return {'ripple_db': 1., 'side_gain': .5, 'relative_response_db': [0., -1., 0.],
            'electrical_validation': {'passed': False}}


def fake_evaluate(candidate, root, runtime, brief, **kwargs):
    root.mkdir()
    _write_json(root/'candidate.json', search.candidate_record(candidate))
    (root/'geometry').mkdir()
    _write_json(root/'geometry/geometry.json', {'design': candidate['design'].model_dump(mode='json')})
    (root/'geometry/test-only.stl').write_text('synthetic test bytes, not real STL')
    (root/'evaluation').mkdir()
    _write_json(root/'evaluation/evaluation.json', {'runtime': runtime.verify()})
    request = SolveRequest(frequencies_hz=brief.frequencies_hz,
        include_project_observations=True, retain=('fem_nodal_pressure','bem_boundary_traces'))
    _write_json(root/'evaluation/request.json', request.model_dump(mode='json'))
    score = fake_score()
    score.update(objective=1.+brief.cost_weight_db*candidate['cost']/brief.max_driver_cost,
                 driver_count=candidate['design'].driver_count, driver_cost=candidate['cost'],
                 evaluation_sha256=sha256(root/'evaluation/evaluation.json'),
                 geometry_manifest_sha256=sha256(root/'geometry/geometry.json'))
    _write_json(root/'score.json', score)
    return score


@pytest.fixture
def stopped(tmp_path, monkeypatch):
    brief, base, drivers = inputs()
    brief = brief.model_copy(update={'trial_budget': 2})
    database = tmp_path/'drivers.sqlite'
    with Catalogue.create(database) as catalogue:
        for driver in drivers:
            catalogue.add(driver)
    def stop(candidate, root, *args, **kwargs):
        if root.name == 'trial-001':
            root.mkdir()
            (root/'partial.txt').write_text('preserved interrupted work')
            raise KeyboardInterrupt('test interruption')
        return fake_evaluate(candidate, root, *args, **kwargs)
    monkeypatch.setattr(search, 'evaluate_candidate', stop)
    original = tmp_path/'original'
    with pytest.raises(KeyboardInterrupt):
        search.optimise(brief, base, database, Runtime(), original)
    monkeypatch.setattr(recovery, 'response_score', fake_score)
    import meh_studio.export_validation as export
    monkeypatch.setattr(export, 'validate_export', lambda root: None)
    return original


def test_resume_reuses_only_complete_trials_and_preserves_original(stopped, tmp_path, monkeypatch):
    before = recovery._inventory(stopped)
    calls = []
    def evaluate(candidate, root, *args, **kwargs):
        calls.append(root.name)
        return fake_evaluate(candidate, root, *args, **kwargs)
    monkeypatch.setattr(search, 'evaluate_candidate', evaluate)
    output = tmp_path/'continued'
    result = recovery.resume_optimise(stopped, Runtime(), output)
    assert calls == ['trial-001']
    assert result['status'] == 'complete'
    assert result['recovery']['reused_trial_indices'] == [0]
    assert result['recovery']['original_search_required'] is True
    assert recovery._inventory(stopped) == before
    assert recovery._inventory(stopped/'trial-000') == recovery._inventory(output/'trial-000')
    assert not (output/'trial-001/partial.txt').exists()


@pytest.mark.parametrize('field,value', [('runtime', {}), ('application_runtime', {}), ('status','running'), ('status','complete')])
def test_resume_rejects_incompatible_checkpoints_before_output(stopped, tmp_path, field, value):
    record = search._read_json(stopped/'search.json')
    record[field] = value
    _write_json(stopped/'search.json', record)
    output = tmp_path/'continued'
    with pytest.raises(ValueError):
        recovery.resume_optimise(stopped, Runtime(), output)
    assert not output.exists()


def test_changed_controls_are_rejected(stopped, tmp_path):
    (stopped/'brief.json').write_text((stopped/'brief.json').read_text()+' ')
    with pytest.raises(ValueError, match='control identity'):
        recovery.resume_optimise(stopped, Runtime(), tmp_path/'continued')


@pytest.mark.parametrize('target', ['score.json','geometry/geometry.json','evaluation/request.json'])
def test_changed_completed_artifacts_abort_recovery(stopped, tmp_path, target):
    path = stopped/'trial-000'/target
    value = search._read_json(path)
    if target == 'score.json': value['objective'] = -1
    elif target.startswith('geometry'): value['design']['length_m'] += .001
    else: value['frequencies_hz'] = [100.,200.,300.]
    _write_json(path, value)
    output = tmp_path/'continued'
    with pytest.raises(ValueError):
        recovery.resume_optimise(stopped, Runtime(), output)
    assert search._read_json(output/'search.json')['status'] == 'failed'
    assert not (output/'winner-geometry').exists()


def test_changed_score_and_ledger_still_fail_recomputation(stopped, tmp_path):
    score = search._read_json(stopped/'trial-000/score.json')
    score['objective'] = -999.
    _write_json(stopped/'trial-000/score.json', score)
    report = search._read_json(stopped/'search.json')
    report['trials'][0]['objective'] = -999.
    _write_json(stopped/'search.json', report)
    with pytest.raises(ValueError, match='recomputation'):
        recovery.resume_optimise(stopped, Runtime(), tmp_path/'continued')


def test_nested_output_is_rejected(stopped):
    with pytest.raises(ValueError, match='outside'):
        recovery.resume_optimise(stopped, Runtime(), stopped/'continued')


def test_resume_cli_dispatch_preserves_runtime_options(tmp_path, monkeypatch, capsys):
    from meh_studio.cli import main
    calls = []
    def resume(source, runtime, output):
        calls.append((source, runtime.julia_threads, output))
        return {'status': 'complete', 'fixture': True}
    monkeypatch.setattr(recovery, 'resume_optimise', resume)
    assert main(['resume-optimise', str(tmp_path/'source'), '--output', str(tmp_path/'output'),
                 '--checkout', '/solver', '--python', '/python', '--julia', '/julia',
                 '--julia-threads', '1']) == 0
    assert calls == [(tmp_path/'source', 1, tmp_path/'output')]
    assert json.loads(capsys.readouterr().out)['fixture'] is True
