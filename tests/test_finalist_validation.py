"""Exercise saved-search replay without invoking the native solver."""
import importlib.util
import json
from pathlib import Path
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('finalist_runner', Path(__file__).resolve().parents[1] / 'validation/fixtures/validate_search_finalist.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize('changed_input',[False,True])
def test_finalist_replays_catalogue_array_and_freezes_gain(tmp_path, monkeypatch, changed_input):
    examples = Path(__file__).resolve().parents[1] / 'examples'
    search = tmp_path / 'search'
    search.mkdir()
    for source, target in [('synthetic-search-brief.json', 'brief.json'),
                           ('three-driver-geometry.json', 'base-geometry.json'),
                           ('synthetic-search-drivers.json', 'catalogue-snapshot.json')]:
        (search / target).write_bytes((examples / source).read_bytes())
    (search / 'search.json').write_text(json.dumps({'status': 'complete', 'winner_index': 0,
                                                  'winner': {'side_gain': .5}}))
    calls = []
    def evaluate(candidate, root, runtime, brief, *, mesh_size, timeout_s):
        calls.append((brief.side_gains, brief.frequencies_hz, mesh_size))
        return {'electrical_validation': {'passed': False}}
    monkeypatch.setattr(module, 'evaluate_candidate', evaluate)
    monkeypatch.setattr(module, 'mesh_identity', lambda *args: {'cad_geometry_sha256':'test','exterior_mesh_size_m':.02})
    monkeypatch.setattr(module, 'pressure', lambda *args: np.ones(5, dtype=complex))
    monkeypatch.setattr(module, 'validate_export', lambda *args: {'print_qualified': False})
    class Runtime:
        def verify(self): return {'revision':'test'}
    if changed_input:
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
    assert all(gain == (.5,) and len(frequencies) == 5 for gain, frequencies, _ in calls)
    assert [call[2] for call in calls] == pytest.approx([.008, .006, .004])
