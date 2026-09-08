import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec=importlib.util.spec_from_file_location('refinement',Path(__file__).resolve().parents[1]/'validation/fixtures/compare_exterior_refinement.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_comparison_preserves_gain_and_phase_changes():
    result=module.compare(np.array([[1.,2.]],dtype=complex),np.array([[1.,2.]])*2*np.exp(1j*np.pi/4))
    assert result['maximum_absolute_magnitude_change_db'] == pytest.approx(20*np.log10(2))
    assert result['maximum_absolute_phase_change_deg'] == pytest.approx(45)
    assert result['relative_matrix_norm_change'] == pytest.approx(np.sqrt(5-2*np.sqrt(2)))


def test_null_policy_retains_weak_sources_and_reports_excluded_samples():
    before=np.array([[1.,0.],[1e-8,0.]],dtype=complex)
    after=before*np.array([[1],[2]])
    result=module.compare(before,after)
    assert result['compared_samples'] == 2
    assert result['excluded_null_samples'] == 2
    assert result['maximum_absolute_magnitude_change_db'] == pytest.approx(20*np.log10(2))
    null=module.compare(before,np.zeros_like(before))
    assert null['compared_samples'] == 0
    assert null['maximum_absolute_phase_change_deg'] is None


@pytest.mark.parametrize('fault', [None, 'cad', 'design', 'surface', 'missing', 'target'])
def test_refinement_requires_bound_cad_identity(tmp_path, fault):
    import json
    from meh_studio.boundary_lab import sha256
    project = tmp_path / 'project.blab.json'
    project.write_text('{}')
    exterior = tmp_path / 'exterior'
    exterior.mkdir()
    cad = exterior / 'envelope.step'
    cad.write_text('original CAD')
    identity = {'design_hash': 'design-a', 'cad_sha256': sha256(cad)}
    compilation = {'status': 'complete', 'geometry_hash': 'design-a',
                   'project_sha256': sha256(project), 'exterior_identity': identity,
                   'exterior_surface': {'sha256': 'surface-a'}}
    report = {'status': 'complete', 'mesh_size_m': .02, **identity}
    (exterior/'exterior.json').write_text(json.dumps(report))
    compilation.update(exterior_mesh_size_m=.02, exterior_report_sha256=sha256(exterior/'exterior.json'))
    if fault == 'target': report['mesh_size_m'] = .01
    manifest = {'meshes': [{'id': 'mesh:exterior', 'purpose': 'bem_surface', 'sha256': 'surface-a'}]}
    if fault == 'cad': cad.write_text('different CAD')
    if fault == 'design': report['design_hash'] = 'different-design'
    if fault == 'surface': manifest['meshes'][0]['sha256'] = 'different-surface'
    if fault == 'missing': del compilation['exterior_identity']
    (tmp_path / 'compilation.json').write_text(json.dumps(compilation))
    (exterior / 'exterior.json').write_text(json.dumps(report))
    if fault:
        with pytest.raises(ValueError): module.exterior_identity(project, manifest)
    else:
        assert module.exterior_identity(project, manifest) == identity


@pytest.mark.parametrize('sizes', [[.01,.02,.03], [.02,.02,.01], [.03,float('nan'),.01], [.03,0,.01]])
def test_invalid_refinement_order_or_sizes_rejected(sizes):
    records = [{'mesh_size_m': size, 'mesh_inventory':[{'purpose':'bem_surface','sha256':str(i)}]}
               for i, size in enumerate(sizes)]
    with pytest.raises(ValueError): module.validate_refinement_levels(records)


def test_distinct_decreasing_refinements_required():
    records = [{'mesh_size_m': size, 'mesh_inventory':[{'purpose':'bem_surface','sha256':str(i)}]}
               for i, size in enumerate([.02,.015,.01])]
    module.validate_refinement_levels(records)
    records[1]['mesh_inventory'] = records[0]['mesh_inventory']
    with pytest.raises(ValueError, match='distinct exterior'):
        module.validate_refinement_levels(records)


def test_refinement_project_identity_only_allows_exterior_digest_changes(tmp_path):
    import json
    path = tmp_path/'project.json'
    data = {'physical_system': {'metadata': {'generated_mesh_sha256': {'mesh:front':'a', 'mesh:exterior':'b'}}}}
    path.write_text(json.dumps(data))
    original = module.refinement_project_hash(path)
    data['physical_system']['metadata']['generated_mesh_sha256']['mesh:exterior'] = 'c'
    path.write_text(json.dumps(data))
    assert module.refinement_project_hash(path) == original
    data['physical_system']['metadata']['generated_mesh_sha256']['mesh:front'] = 'd'
    path.write_text(json.dumps(data))
    assert module.refinement_project_hash(path) != original


@pytest.mark.parametrize('fault', [None, 'no_pressure', 'changed_artifact'])
def test_load_requires_pressure_and_revalidates_artifacts(tmp_path, monkeypatch, fault):
    import json
    project = tmp_path/'project.json'
    project.write_text('{}')
    (tmp_path/'compilation.json').write_text('{"exterior_mesh_size_m":0.02}')
    root = tmp_path/'evaluation'
    upstream = root/'upstream'
    upstream.mkdir(parents=True)
    (root/'evaluation.json').write_text('{"runtime":{"python":"pinned"}}')
    (upstream/'manifest.json').write_text(json.dumps({'meshes':[], 'results':[{'metadata_file':'metadata.json','arrays_file':'arrays.npz'}]}))
    kind = 'voice_coil_current' if fault == 'no_pressure' else 'exterior_pressure'
    (upstream/'metadata.json').write_text(json.dumps({'quantities':[{'id':'observable','key':'p','quantity':kind}]}))
    np.savez(upstream/'arrays.npz',p=np.array([[1+1j]]))
    calls = []
    def validate(*args):
        calls.append(True)
        if fault == 'changed_artifact' and len(calls) == 2:
            raise ValueError('artifact hash mismatch')
        return {'passed':True}
    monkeypatch.setattr(module,'validate_electrical_basis',validate)
    monkeypatch.setattr(module,'exterior_identity',lambda *args:{'design':'same'})
    if fault:
        with pytest.raises(ValueError): module.load(project,root)
    else:
        record, _, rows = module.load(project,root)
        assert record['pressure_ids'] == ['observable']
        assert record['runtime'] == {'python':'pinned'}
        assert len(calls) == 2 and len(rows) == 1


def test_comparison_rejects_different_dependency_runtime(tmp_path, monkeypatch):
    import sys
    runs = []
    for i, size in enumerate([.02,.015,.01]):
        record = {'mesh_size_m':size, 'mesh_inventory':[{'purpose':'bem_surface','sha256':str(i)}],
                  'runtime':{'packages':{'numpy':str(i)}}, 'exterior_identity':{'cad':'same'},
                  'pressure_ids':['polar'], 'project_definition_sha256':'same'}
        manifest = {'frequencies_hz':[1000], 'excitation_port_ids':['a'], 'meshes':[]}
        runs.append((record, manifest, []))
    monkeypatch.setattr(module, 'load', lambda *args: runs.pop(0))
    monkeypatch.setattr(sys, 'argv', ['compare', '--run','p1','e1','--run','p2','e2',
                                     '--run','p3','e3','--output',str(tmp_path/'report.json')])
    with pytest.raises(ValueError, match='runtime changed'):
        module.main()
    assert not (tmp_path/'report.json').exists()
