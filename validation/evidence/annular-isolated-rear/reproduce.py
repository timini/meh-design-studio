"""Recompute retained field differences without invoking path-bound validators."""
from pathlib import Path
import hashlib
import io
import json
import posixpath
import zipfile
import numpy as np

ROOT = Path(__file__).resolve().parent


def read_verified(folder):
    report = json.loads((folder / 'report.json').read_text())
    blob = (folder / 'evidence.zip').read_bytes()
    assert hashlib.sha256(blob).hexdigest() == report['archive_sha256']
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        assert archive.testzip() is None
        assert len(archive.namelist()) == len(set(archive.namelist()))
        assert set(archive.namelist()) == set(report['archive_members_sha256'])
        members = {name: archive.read(name) for name in archive.namelist()}
    for name, data in members.items():
        assert hashlib.sha256(data).hexdigest() == report['archive_members_sha256'][name]
    return report, members


def arrays(members, prefix):
    quantities = {q['id']: q for q in json.loads(members[prefix + '/frequencies/000000.json'])['quantities']}
    assert quantities['mechanical:diaphragm-velocity']['metadata']['component_ids'] == [
        'component:throat', 'component:entry_0_positive', 'component:entry_0_positive_y']
    with np.load(io.BytesIO(members[prefix + '/frequencies/000000.npz']), allow_pickle=False) as data:
        return {name: data[q['key']].copy() for name, q in quantities.items()}


def verify_coarse_origin(rear, project):
    # Bind replacement bytes to the historical coarse archive, not only this package.
    provenance = json.loads(rear['provenance.json'])
    coarse_blob = (ROOT.parent / 'annular-mid-entry/evidence.zip').read_bytes()
    assert hashlib.sha256(coarse_blob).hexdigest() == provenance['coarse_archive_sha256']
    with zipfile.ZipFile(io.BytesIO(coarse_blob)) as archive:
        prefix = 'annular-entry-native/annular/system/'
        coarse_project = json.loads(archive.read(prefix + 'project.blab.json'))
        for mesh in project['physical_system']['meshes']:
            if mesh['id'].startswith('mesh:rear_'):
                original = archive.read(prefix + mesh['file'])
                assert original == rear['system/' + mesh['file']]
                assert hashlib.sha256(original).hexdigest() == coarse_project['physical_system']['metadata']['generated_mesh_sha256'][mesh['id']]


def reproduce():
    report, rear = read_verified(ROOT)
    _, baseline = read_verified(ROOT.parent / 'annular-fixed-quadrature')
    a = json.loads(baseline['evaluation-baseline/upstream/manifest.json'])
    b = json.loads(rear['evaluation/upstream/manifest.json'])
    # Lexical normalisation works without requiring the original host filesystem.
    ra, rb = dict(a['reference_runtime']['identity']), dict(b['reference_runtime']['identity'])
    assert posixpath.normpath(ra.pop('julia_executable')) == posixpath.normpath(rb.pop('julia_executable'))
    assert ra == rb
    assert a['solver_options'] == b['solver_options']
    pa, pb = [json.loads(m['system/project.blab.json']) for m in (baseline, rear)]
    derivation = json.loads(rear['derivation.json'])
    assert rear['parent-input/compilation.json'] == baseline['system/compilation.json']
    assert derivation['parent_project_sha256'] == a['project_sha256']
    assert derivation['derived_project_sha256'] == b['project_sha256']
    assert json.loads(rear['parent-input/compilation.json'])['project_sha256'] == a['project_sha256']
    assert 'system/compilation.json' not in rear
    retained_check = json.loads(rear['comparison.json'])['electrical_check']
    assert retained_check == report['electrical_check']
    assert retained_check['project_sha256'] == b['project_sha256']
    assert retained_check['evaluation_sha256'] == hashlib.sha256(rear['evaluation/evaluation.json']).hexdigest()
    for project, members, manifest in [(pa, baseline, a), (pb, rear, b)]:
        assert hashlib.sha256(members['system/project.blab.json']).hexdigest() == manifest['project_sha256']
        for mesh in project['physical_system']['meshes']:
            assert hashlib.sha256(members['system/' + mesh['file']]).hexdigest() == project['physical_system']['metadata']['generated_mesh_sha256'][mesh['id']]
    ha = pa['physical_system']['metadata'].pop('generated_mesh_sha256')
    hb = pb['physical_system']['metadata'].pop('generated_mesh_sha256')
    assert pa == pb
    assert {key for key in ha if ha[key] != hb[key]} == {'mesh:rear_entry_0_positive', 'mesh:rear_entry_0_positive_y'}
    verify_coarse_origin(rear, pb)
    assert baseline['request-baseline.json'] == rear['request.json']
    x, y = arrays(baseline, 'evaluation-baseline/upstream'), arrays(rear, 'evaluation/upstream')
    errors = {}
    for key in ('mechanical:diaphragm-velocity', 'electrical:voice-coil-current',
                'acoustic:pressure:horizontal-polar', 'acoustic:pressure:vertical-polar'):
        errors[key] = float(np.linalg.norm(y[key] - x[key]) / np.linalg.norm(x[key]))
    common = [np.concatenate([v[f'acoustic:pressure:{plane}-polar'][1:].sum(axis=0)
                              for plane in ('horizontal', 'vertical')]) for v in (x, y)]
    errors['common_mid_pressure'] = float(np.linalg.norm(common[1] - common[0]) / np.linalg.norm(common[0]))
    for key, value in errors.items():
        np.testing.assert_allclose(value, report['relative_errors_against_refined_baseline'][key], rtol=1e-10, atol=1e-15)
    print(json.dumps({'relative_errors_against_refined_baseline': errors,
                      'electrical_verification': 'Retained original report; not rerun in portable mode.',
                      'qualified': False}, indent=2))


if __name__ == '__main__':
    reproduce()
