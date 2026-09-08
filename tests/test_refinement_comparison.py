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


@pytest.mark.parametrize('fault', [None, 'cad', 'design', 'surface', 'missing'])
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
    report = {'status': 'complete', **identity}
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
