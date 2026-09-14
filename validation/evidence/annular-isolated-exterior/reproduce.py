"""Recompute retained field differences without invoking path-bound validators."""
from pathlib import Path
import hashlib
import io
import json
import tempfile
import meshio
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


def verify_subdivision(parent_bytes, derived_bytes):
    with tempfile.TemporaryDirectory() as folder:
        paths = [Path(folder) / name for name in ('parent.msh', 'derived.msh')]
        for path, data in zip(paths, (parent_bytes, derived_bytes)):
            path.write_bytes(data)
        parent, derived = [meshio.read(path) for path in paths]
    assert set(parent.field_data) == set(derived.field_data)
    for key in parent.field_data:
        np.testing.assert_array_equal(parent.field_data[key], derived.field_data[key])
    points = parent.points.tolist()
    faces, tags = [], []
    for cell, physical in zip(parent.cells, parent.cell_data['gmsh:physical']):
        assert cell.type == 'triangle'
        for face, tag in zip(cell.data, physical):
            if tag == 10:
                faces.append(face.tolist()); tags.append(10)
            else:
                assert tag == 99
                centre = len(points)
                points.append(parent.points[face].mean(axis=0).tolist())
                for i in range(3):
                    faces.append([int(face[i]), int(face[(i+1) % 3]), centre]); tags.append(99)
    assert all(cell.type == 'triangle' for cell in derived.cells)
    np.testing.assert_allclose(derived.points, points, rtol=0, atol=1e-15)
    np.testing.assert_array_equal(np.concatenate([cell.data for cell in derived.cells]), faces)
    np.testing.assert_array_equal(np.concatenate(derived.cell_data['gmsh:physical']), tags)


def reproduce():
    report, enriched = read_verified(ROOT)
    _, baseline = read_verified(ROOT.parent / 'annular-fixed-quadrature')
    a = json.loads(baseline['evaluation-baseline/upstream/manifest.json'])
    b = json.loads(enriched['evaluation/upstream/manifest.json'])
    assert a['reference_runtime']['identity'] == b['reference_runtime']['identity']
    assert a['solver_options'] == b['solver_options']
    pa, pb = [json.loads(m['system/project.blab.json']) for m in (baseline, enriched)]
    derivation = json.loads(enriched['derivation.json'])
    assert enriched['parent-input/compilation.json'] == baseline['system/compilation.json']
    assert derivation['parent_project_sha256'] == a['project_sha256']
    assert derivation['derived_project_sha256'] == b['project_sha256']
    assert json.loads(enriched['parent-input/compilation.json'])['project_sha256'] == a['project_sha256']
    assert 'system/compilation.json' not in enriched
    retained_check = json.loads(enriched['comparison.json'])['electrical_check']
    assert retained_check == report['electrical_check']
    assert retained_check['project_sha256'] == b['project_sha256']
    assert retained_check['evaluation_sha256'] == hashlib.sha256(enriched['evaluation/evaluation.json']).hexdigest()
    for project, members, manifest in [(pa, baseline, a), (pb, enriched, b)]:
        assert hashlib.sha256(members['system/project.blab.json']).hexdigest() == manifest['project_sha256']
        for mesh in project['physical_system']['meshes']:
            assert hashlib.sha256(members['system/' + mesh['file']]).hexdigest() == project['physical_system']['metadata']['generated_mesh_sha256'][mesh['id']]
    ha = pa['physical_system']['metadata'].pop('generated_mesh_sha256')
    hb = pb['physical_system']['metadata'].pop('generated_mesh_sha256')
    assert pa == pb
    assert {key for key in ha if ha[key] != hb[key]} == {'mesh:exterior'}
    verify_subdivision(baseline['system/meshes/exterior.msh'], enriched['system/meshes/exterior.msh'])
    assert baseline['request-baseline.json'] == enriched['request.json']
    x, y = arrays(baseline, 'evaluation-baseline/upstream'), arrays(enriched, 'evaluation/upstream')
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
