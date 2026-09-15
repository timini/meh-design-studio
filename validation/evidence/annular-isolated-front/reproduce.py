"""Recompute retained field differences without invoking path-bound validators."""
from pathlib import Path
import hashlib
import io
import json
import tempfile
from collections import Counter
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


def verify_volume_remesh(parent_bytes, derived_bytes):
    with tempfile.TemporaryDirectory() as folder:
        paths = [Path(folder) / name for name in ('parent.msh', 'derived.msh')]
        for path, data in zip(paths, (parent_bytes, derived_bytes)):
            path.write_bytes(data)
        meshes = [meshio.read(path) for path in paths]
    boundaries, volumes, counts = [], [], []
    for mesh in meshes:
        assert tuple(mesh.field_data['air_front']) == (1, 3)
        boundary = Counter()
        declared = set()
        tetrahedra = []
        for cell, tags in zip(mesh.cells, mesh.cell_data['gmsh:physical']):
            if cell.type == 'triangle':
                for face, tag in zip(cell.data, tags):
                    boundary[(int(tag), tuple(sorted(tuple(point) for point in mesh.points[face])))] += 1
                    declared.add(tuple(sorted(face)))
            elif cell.type == 'tetra':
                assert (tags == 1).all()
                tetrahedra.extend(cell.data)
        tet = np.asarray(tetrahedra)
        assert len(tet) > 0
        points = mesh.points[tet]
        det = np.linalg.det(np.stack([points[:, i] - points[:, 0] for i in (1, 2, 3)], axis=2))
        assert np.isfinite(det).all() and (det > 0).all()
        incidence = Counter(tuple(sorted(face)) for t in tet
                            for face in (t[[0, 1, 2]], t[[0, 1, 3]], t[[0, 2, 3]], t[[1, 2, 3]]))
        assert all(count in (1, 2) for count in incidence.values())
        assert {face for face, count in incidence.items() if count == 1} == declared
        boundaries.append(boundary); volumes.append(float(det.sum() / 6)); counts.append(len(tet))
    assert boundaries[0] == boundaries[1]
    assert counts == [64181, 80834]
    np.testing.assert_allclose(volumes[1], volumes[0], rtol=1e-12, atol=0)


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
    assert {key for key in ha if ha[key] != hb[key]} == {'mesh:front'}
    verify_volume_remesh(baseline['system/meshes/front.msh'], enriched['system/meshes/front.msh'])
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
