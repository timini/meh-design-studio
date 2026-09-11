import json
import os
from pathlib import Path
import sys

import pytest

from meh_studio import candidate_preparation as preparation
from meh_studio.boundary_lab import BoundaryLabRuntime, sha256


def inputs():
    from meh_studio.optimisation import SearchBrief, candidates
    from meh_studio.geometry import HornGeometry
    from meh_studio.domain import DriverRevision
    examples = Path(__file__).resolve().parents[1] / 'examples'
    brief = SearchBrief.model_validate_json((examples / 'synthetic-search-brief.json').read_text())
    base = HornGeometry.model_validate_json((examples / 'three-driver-geometry.json').read_text())
    drivers = [DriverRevision.model_validate(value) for value in json.loads((examples / 'synthetic-search-drivers.json').read_text())]
    return candidates(brief, base, drivers)[0], brief


@pytest.mark.skipif(os.name == 'nt', reason='POSIX process-group containment; Windows uses Job Objects')
def test_nested_conformer_stays_in_preparation_group_and_dies_on_timeout(tmp_path):
    import subprocess
    import time
    from meh_studio.boundary_lab import _execute
    package = str(Path(preparation.__file__).resolve().parents[1])
    child = "import os,json,time; from pathlib import Path; Path('child.json').write_text(json.dumps({'pid':os.getpid(),'pgid':os.getpgrp()})); time.sleep(30)"
    program = f"""
import sys,os,json
from pathlib import Path
sys.path.insert(0,{package!r})
from meh_studio.boundary_lab import _execute,_preparation_process_group
Path('parent.json').write_text(json.dumps({{'pid':os.getpid()}}))
with _preparation_process_group():
 _execute([sys.executable,'-I','-c',{child!r}],Path.cwd(),Path('nested.log'),30)
"""
    with pytest.raises(subprocess.TimeoutExpired):
        _execute([sys.executable, '-I', '-c', program], tmp_path, tmp_path / 'outer.log', 5)
    parent = json.loads((tmp_path / 'parent.json').read_text())
    child_state = json.loads((tmp_path / 'child.json').read_text())
    assert child_state['pgid'] == parent['pid']
    for _ in range(50):
        state = subprocess.run(['ps', '-o', 'stat=', '-p', str(child_state['pid'])],
                               capture_output=True, text=True).stdout.strip()
        if not state or state.startswith('Z'):
            break
        time.sleep(.02)
    assert not state or state.startswith('Z'), 'nested preparation process survived parent cleanup'


@pytest.mark.parametrize('termination', ['abrupt_exit', 'timeout'])
def test_abnormal_preparation_is_recorded_and_next_attempt_can_complete(tmp_path, monkeypatch, termination):
    from meh_studio.optimisation import candidate_record
    candidate, brief = inputs()
    runtime = BoundaryLabRuntime(tmp_path, Path(sys.executable), Path(sys.executable))
    monkeypatch.setattr(BoundaryLabRuntime, 'verify', lambda self: {'test': 'runtime'})
    monkeypatch.setattr(preparation, '_identity', lambda: {'test': 'application'})
    # Real subprocesses: the first never reaches normal report finalisation.
    bad = 'import os; os._exit(137)' if termination == 'abrupt_exit' else 'import time; time.sleep(30)'
    def command(request, root):
        if root.name == 'failed':
            return [sys.executable, '-I', '-c', bad]
        code = """
import hashlib,json
from pathlib import Path
root=Path.cwd()
for name in ('geometry/geometry.json','geometry/analysis/mesh.json','system/compilation.json','system/project.blab.json'):
 p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('{"status":"complete"}')
files={str(p.relative_to(root)).replace('\\\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('geometry','system') for p in (root/folder).rglob('*') if p.is_file()}
files['candidate.json']=hashlib.sha256((root/'candidate.json').read_bytes()).hexdigest()
(root/'preparation-child.json').write_text(json.dumps({'status':'complete','request_sha256':hashlib.sha256((root/'preparation-request.json').read_bytes()).hexdigest(),'files_sha256':files}))
"""
        return [sys.executable, '-I', '-c', code]
    monkeypatch.setattr(preparation, '_command', command)
    for name in ('failed', 'next'):
        root = tmp_path / name
        root.mkdir()
        (root / 'candidate.json').write_text(json.dumps(candidate_record(candidate)))
        if name == 'failed':
            with pytest.raises(Exception):
                preparation.prepare_candidate(candidate, root, runtime, brief,
                                              timeout_s=.2 if termination == 'timeout' else 10)
            report = json.loads((root / 'preparation.json').read_text())
            assert report['status'] == 'failed'
            if termination == 'abrupt_exit':
                assert 'Candidate preparation exited with code 137' in report['error']
            assert not (root / 'preparation-child.json').exists()
            assert (root / 'preparation.log').exists()
        else:
            report = preparation.prepare_candidate(candidate, root, runtime, brief, timeout_s=10)
            assert report['status'] == 'complete'
            assert report['files_sha256']['candidate.json'] == sha256(root / 'candidate.json')
            (root / 'geometry/geometry.json').write_text('{"status":"failed"}')
            with pytest.raises(ValueError, match='changed'):
                preparation.verify_prepared_files(root, report['files_sha256'])


def test_child_preparation_forwards_observations_and_stops_over_budget_before_meshing(tmp_path, monkeypatch):
    from meh_studio.optimisation import SearchBrief
    import meh_studio.geometry as geometry
    import meh_studio.radiating_system as radiating
    import meh_studio.build_cost as costs
    candidate, initial = inputs()
    brief = SearchBrief.model_validate(initial.model_dump(mode='json') | {
        'frequencies_hz': [350., 1000., 8000.],
        'acoustic_objectives': {'observation_distance_m': 20., 'sphere': {}}})
    def export(design, root):
        root.mkdir(); (root / 'geometry.json').write_text('{}')
    monkeypatch.setattr(geometry, 'export_geometry', export)
    calls = []
    monkeypatch.setattr(geometry, 'mesh_geometry', lambda root: calls.append('mesh'))
    monkeypatch.setattr(radiating, 'compile_radiating_system', lambda *args, **kwargs: calls.append(kwargs))
    root = tmp_path / 'normal'; root.mkdir()
    preparation.prepare_in_process(candidate, root, None, brief)
    assert calls == ['mesh', {'exterior_mesh_size_m': brief.exterior_mesh_size_m,
                              'observation_distance_m': 20., 'sphere_angle_deg': 10.}]
    calls.clear()
    budget = SearchBrief.model_validate(brief.model_dump(mode='json') | {'build_budget': {
        'maximum_total_cost': 300., 'material_density_kg_m3': 1270., 'material_cost_per_kg': 16.}})
    monkeypatch.setattr(costs, 'estimate_build_cost', lambda *args: {'within_budget': False})
    root = tmp_path / 'over-budget'; root.mkdir()
    with pytest.raises(ValueError, match='build budget'):
        preparation.prepare_in_process(candidate, root, None, budget)
    assert calls == []
    assert json.loads((root / 'build-cost.json').read_text())['within_budget'] is False
