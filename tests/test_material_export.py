import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

import numpy as np
import pytest

from meh_studio.geometry import HornGeometry, export_geometry
from meh_studio.export_validation import validate_export


ROOT = Path(__file__).resolve().parents[1]


def three_mf_volume(path):
    ns = {'m': 'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None
        model = ET.fromstring(archive.read('3D/3dmodel.model'))
    assert model.attrib['unit'] == 'millimeter'
    total, count = 0., 0
    for mesh in model.findall('.//m:mesh', ns):
        points = np.array([[float(v.attrib[k]) for k in ('x', 'y', 'z')]
                           for v in mesh.findall('m:vertices/m:vertex', ns)])
        faces = np.array([[int(t.attrib[k]) for k in ('v1', 'v2', 'v3')]
                          for t in mesh.findall('m:triangles/m:triangle', ns)])
        a, b, c = [points[faces[:, i]] for i in range(3)]
        total += float(np.einsum('ij,ij->i', a, np.cross(b, c)).sum() / 6 / 1e9)
        count += len(faces)
    return total, count


@pytest.mark.cad
def test_completed_concentric_candidate_exports_at_absolute_tolerance(tmp_path):
    pytest.importorskip('cadquery')
    # Exact design from the native candidate whose old relative STL differed
    # from its CAD volume by 1.387%, preventing replay and build export.
    design = HornGeometry.model_validate_json(
        (ROOT / 'tests/fixtures/concentric-overhang-export.json').read_text())
    result = export_geometry(design, tmp_path / 'geometry')
    checks = validate_export(tmp_path / 'geometry')
    assert result['export_checks'] == checks
    assert len(checks['parts']) == 5
    for part in checks['parts']:
        name = Path(part['file']).stem
        policy = result['material_tessellation'][name]
        assert policy['relative'] is False
        assert policy['linear_tolerance_m'] == design.tessellation_tolerance_m
        assert policy['attempts'][-1]['requested_tolerance_confirmed']
        volume, count = three_mf_volume(tmp_path / 'geometry/parts' / f'{name}.3mf')
        assert count == part['triangles']
        assert volume == pytest.approx(part['volume_m3'], rel=1e-5)
        assert abs(volume / result['material_volume_m3'][name] - 1) <= .01
        assert part['relative_cad_volume_error'] <= .01


@pytest.mark.cad
def test_bad_print_mesh_fails_geometry_before_acoustic_preparation(tmp_path, monkeypatch):
    pytest.importorskip('cadquery')
    import meshio
    import meh_studio.material_export as material
    original = material.export_material_meshes

    def wrong_scale(shape, stl, threemf, tolerance):
        result = original(shape, stl, threemf, tolerance)
        mesh = meshio.read(stl)
        mesh.points *= 1.1
        meshio.write(stl, mesh, file_format='stl', binary=True)
        return result

    monkeypatch.setattr(material, 'export_material_meshes', wrong_scale)
    design = HornGeometry.model_validate_json((ROOT / 'examples/three-driver-geometry.json').read_text())
    with pytest.raises(ValueError, match='STL volume differs from CAD'):
        export_geometry(design, tmp_path / 'geometry')
    saved = json.loads((tmp_path / 'geometry/geometry.json').read_text())
    assert saved['status'] == 'failed'
    assert 'STL volume differs from CAD' in saved['error']
    assert not (tmp_path / 'geometry/analysis').exists()
