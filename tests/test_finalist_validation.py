"""Exercise saved-search replay without invoking the native solver."""
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('finalist_runner', Path(__file__).resolve().parents[1] / 'validation/fixtures/validate_search_finalist.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('changed_input',[False,True,'before','wide','unstable','gain','both_gains','score_changed','last_runtime',pytest.param('cancel',marks=pytest.mark.skipif(__import__('sys').platform=='win32',reason='POSIX SIGTERM lifecycle'))])
def test_finalist_replays_catalogue_array_and_freezes_gain(tmp_path, monkeypatch, changed_input):
    examples = Path(__file__).resolve().parents[1] / 'examples'
    search = tmp_path / 'search'
    search.mkdir()
    for source, target in [('synthetic-search-brief.json', 'brief.json'),
                           ('three-driver-geometry.json', 'base-geometry.json'),
                           ('synthetic-search-drivers.json', 'catalogue-snapshot.json')]:
        (search / target).write_bytes((examples / source).read_bytes())
    if changed_input=='wide':
        data=json.loads((search/'brief.json').read_text());data['frequencies_hz']=[500+15*i for i in range(100)]
        (search/'brief.json').write_text(json.dumps(data))
    candidate=search/'trial-000/candidate.json';candidate.parent.mkdir()
    pool=module.candidates(module.SearchBrief.model_validate_json((search/'brief.json').read_text()),
        module.HornGeometry.model_validate_json((search/'base-geometry.json').read_text()),
        [module.DriverRevision.model_validate(d) for d in json.loads((search/'catalogue-snapshot.json').read_text())])
    candidate.write_text(json.dumps(module.candidate_record(pool[0])))
    winning_trial={'index':0,'status':'complete','side_gain':.5}
    score=candidate.parent/'score.json';score.write_text(json.dumps({'side_gain':.5}))
    (search / 'search.json').write_text(json.dumps({'status': 'complete', 'winner_index': 0,
        'winner':winning_trial,'trials':[winning_trial],'winner_candidate_sha256':module.sha256(candidate),'winner_score_sha256':module.sha256(score),
        'control_sha256':{name:module.sha256(search/name) for name in
            ('brief.json','base-geometry.json','catalogue-snapshot.json')}}))
    calls = []
    def evaluate(candidate, root, runtime, brief, *, mesh_size, timeout_s, frequencies):
        calls.append((brief.side_gains, frequencies, mesh_size))
        return {'electrical_validation': {'passed': False}}
    monkeypatch.setattr(module, 'evaluate_candidate', evaluate)
    monkeypatch.setattr(module, 'mesh_identity', lambda *args: {'cad_geometry_sha256':'test','exterior_mesh_size_m':.02,'compiler_runtime':{'gmsh':'test'}})
    monkeypatch.setattr(module, 'pressure', lambda *args: np.ones(len(calls[-1][1]), dtype=complex))
    monkeypatch.setattr(module, 'validate_export', lambda *args: {'print_qualified': False})
    class Runtime:
        def verify(self): return {'revision':'changed' if changed_input=='last_runtime' and len(calls)==3 else 'test'}
    if changed_input in ('both_gains','score_changed'):
        if changed_input=='both_gains':
            result=json.loads((search/'search.json').read_text());result['winner']['side_gain']=.8;result['trials'][0]['side_gain']=.8
            (search/'search.json').write_text(json.dumps(result))
        else:score.write_text('{"side_gain":0.8}')
        with pytest.raises(ValueError,match='scored artifact'):
            module.validate(search,tmp_path/'validation',Runtime())
        return
    if changed_input=='gain':
        result=json.loads((search/'search.json').read_text());result['winner']['side_gain']=.8
        (search/'search.json').write_text(json.dumps(result))
        with pytest.raises(ValueError,match='winner record differs'):
            module.validate(search,tmp_path/'validation',Runtime())
        return
    if changed_input=='last_runtime':
        with pytest.raises(ValueError,match='runtime changed before completion'):
            module.validate(search,tmp_path/'validation',Runtime())
        report=json.loads((tmp_path/'validation/validation.json').read_text())
        assert report['status']=='failed' and not report['refinement_passed']
        return
    if changed_input=='unstable':
        monkeypatch.setattr(module,'pressure',lambda *args: np.ones(len(calls[-1][1]),dtype=complex)*len(calls))
        with pytest.raises(ValueError,match='mesh stability limits exceeded'):
            module.validate(search,tmp_path/'validation',Runtime())
        report=json.loads((tmp_path/'validation/validation.json').read_text())
        assert report['status']=='failed' and not report['refinement_passed']
        assert len(calls)==2 and report['successive_changes'][0]['maximum_magnitude_change_db']>6
        return
    if changed_input=='cancel':
        import signal
        def cancel(*args,**kwargs): signal.raise_signal(signal.SIGTERM)
        monkeypatch.setattr(module,'evaluate_candidate',cancel)
        with pytest.raises(KeyboardInterrupt): module.validate(search,tmp_path/'validation',Runtime())
        assert json.loads((tmp_path/'validation/validation.json').read_text())['status']=='cancelled'
        return
    if changed_input=='before':
        (search/'brief.json').write_text('{}')
        with pytest.raises(ValueError,match='do not match completed search'):
            module.validate(search,tmp_path/'validation',Runtime())
        return
    if changed_input is True:
        def changed_pressure(*args):
            (search / 'brief.json').write_text('{}')
            return np.ones(5, dtype=complex)
        monkeypatch.setattr(module, 'pressure', changed_pressure)
        with pytest.raises(ValueError, match='controls changed'):
            module.validate(search, tmp_path / 'validation', Runtime())
        report=json.loads((tmp_path/'validation/validation.json').read_text())
        assert report['status']=='failed' and not report['refinement_passed']
        return
    result = module.validate(search, tmp_path / 'validation', Runtime())
    assert result['status'] == 'complete' and result['refinement_passed']
    assert not result['qualified'] and not result['electrical_consistency_passed']
    assert len(calls) == 3
    assert all(gain == (.5,) and len(frequencies) == (199 if changed_input=='wide' else 5) for gain, frequencies, _ in calls)
    assert [call[2] for call in calls] == pytest.approx([.008, .006, .004])
