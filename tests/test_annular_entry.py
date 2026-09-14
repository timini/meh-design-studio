import json
import math
from pathlib import Path

import pytest

from meh_studio.geometry import HornGeometry, build_geometry, export_geometry, mesh_geometry

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def data():
    return json.loads((EXAMPLES / 'three-driver-geometry.json').read_text()) | {
        'port_radius_m': .024, 'port_core_radius_m': .016, 'entry_layout': 'four_driver_ring'}


def test_annular_constraints_and_legacy_identity():
    values = data()
    annular = HornGeometry.model_validate(values)
    old = HornGeometry.model_validate(values | {'port_core_radius_m': 0.})
    assert 'port_core_radius_m' not in old.model_dump()
    assert HornGeometry.model_validate_json(annular.model_dump_json()) == annular
    assert annular.content_hash != old.content_hash
    for change in ({'port_core_radius_m': -.001}, {'port_core_radius_m': .022},
                   {'port_core_radius_m': .002}, {'driver_axial_offset_m': .001}):
        with pytest.raises(ValueError):
            HornGeometry.model_validate(values | change)


@pytest.mark.cad
def test_annular_channels_conserve_volume_sources_and_end_area():
    cq = pytest.importorskip('cadquery')
    from meh_studio.annular_entry import supported_core
    design = HornGeometry.model_validate(data())
    plain = HornGeometry.model_validate(data() | {'port_core_radius_m': 0.})
    air, parts, sources = build_geometry(design)
    old_air, old_parts, old_sources = build_geometry(plain)
    assert sources == old_sources
    removed = old_air['front'].Volume(tol=1e-9) - air['front'].Volume(tol=1e-9)
    assert removed > 0
    assert parts['horn'].Volume(tol=1e-9) - old_parts['horn'].Volume(tol=1e-9) == pytest.approx(removed, rel=1e-7)
    for name in air:
        if name != 'front':
            assert air[name].Volume() == pytest.approx(old_air[name].Volume(), rel=1e-8)
    # Independently integrate two crossing strips through an annulus at the
    # chamber inlet. Their overlap lies wholly inside the central disk.
    r, core, half_width, length = (design.port_radius_m * 1000,
        design.port_core_radius_m * 1000, design.wall_m * 500, design.port_length_m * 1000)
    def strip(radius):
        return 2 * (half_width * math.sqrt(radius**2 - half_width**2)
                    + radius**2 * math.asin(half_width / radius))
    expected = math.pi * (r*r - core*core) - 2 * (strip(r) - strip(core))
    thickness = .0001
    disk = cq.Solid.makeCylinder(r, thickness, cq.Vector(0, 0, length - thickness))
    channels = disk.cut(supported_core(design))
    assert len(channels.Solids()) == 4
    assert channels.Volume() / thickness == pytest.approx(expected, rel=2e-5)


@pytest.mark.cad
@pytest.mark.parametrize('symmetry,curved', [('off', False), ('xy', False), ('xy', True)])
def test_annular_ring_exports_meshes_and_compiles(tmp_path, symmetry, curved):
    pytest.importorskip('cadquery'); pytest.importorskip('gmsh')
    from meh_studio.generated_system import HornSources, compile_interior_system
    values = data() | {'solver_symmetry': symmetry, 'rear_axial_mesh_size_m': .002}
    if curved:
        values.update(diaphragm_profile_m=[.005, .005, .0025, 0.],
            profile_interpolation='periodic_cubic', profile_sections=[
                {'fraction': f, 'radial_scales': [scale] * 8}
                for f, scale in [(.4, .9), (.7, 1.1), (1., 1.0)]])
    design = HornGeometry.model_validate(values)
    state = export_geometry(design, tmp_path / 'geometry')
    assert state['export_checks']['mesh_checks_passed']
    mesh = mesh_geometry(tmp_path / 'geometry')
    for region in mesh['regions']:
        for row in region['source_area_checks']:
            assert row['relative_area_error'] < .01
    sources = HornSources.model_validate_json((EXAMPLES / 'synthetic-horn-sources.json').read_text())
    compiled = compile_interior_system(tmp_path / 'geometry', sources, tmp_path / 'system')
    assert compiled['driver_count'] == 5
