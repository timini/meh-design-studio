import json
import math
from pathlib import Path

import pytest

from meh_studio.geometry import HornGeometry, build_geometry, export_geometry, mesh_geometry


EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'
HEIGHTS = [.010, .010, .005, 0.]


def data():
    return json.loads((EXAMPLES / 'three-driver-geometry.json').read_text())


def test_explicit_profile_validation_and_legacy_identity():
    old = HornGeometry.model_validate(data())
    assert 'diaphragm_profile_m' not in old.model_dump()
    assert HornGeometry.model_validate(data() | {'diaphragm_profile_m': []}) == old
    curved = HornGeometry.model_validate(data() | {'diaphragm_profile_m': HEIGHTS})
    assert curved.content_hash != old.content_hash
    assert HornGeometry.model_validate_json(curved.model_dump_json()) == curved
    for heights in ([.01, .01, 0.], [0., 0., .01, 0.], [.01, .02, .005, 0.],
                    [.01, .01, .005, .001], [.01, .01, -.001, 0.],
                    [.01, .01, float('nan'), 0.], [.01, .01, True, 0.],
                    [.01, .01] + [.001] * 7 + [0.]):
        with pytest.raises(ValueError):
            HornGeometry.model_validate(data() | {'diaphragm_profile_m': heights})


@pytest.mark.cad
def test_curved_air_and_reserved_driver_have_analytic_volumes():
    pytest.importorskip('cadquery')
    from meh_studio.diaphragm_geometry import diaphragm_gap
    flat = HornGeometry.model_validate(data())
    curved = HornGeometry.model_validate(data() | {'diaphragm_profile_m': HEIGHTS})
    old_air, _, _ = build_geometry(flat)
    air, parts, sources = build_geometry(curved)
    # Independent integration of this cubic: h(t)=.01-.015t²+.005t³.
    profile_volume_m3 = 2 * math.pi * curved.front_radius_m**2 * (.01/2 - .015/4 + .005/5)
    assert (air['front'].Volume() - old_air['front'].Volume()) / 1e9 == pytest.approx(
        len(sources) * profile_volume_m3, rel=1e-6)
    for source in sources:
        rear = air['rear_' + source['id']]
        assert rear.Volume() == pytest.approx(old_air['rear_' + source['id']].Volume(), rel=1e-6)
        gap = diaphragm_gap(curved, source)
        assert gap.Volume() / 1e9 == pytest.approx(math.pi * curved.front_radius_m**2 * curved.wall_m, rel=1e-6)
        assert source['front_surface']['area_m2'] > math.pi * curved.front_radius_m**2 * 1.05
        assert source['front_surface']['area_m2'] == pytest.approx(source['rear_surface']['area_m2'])
        for shape in [*air.values(), *parts.values()]:
            assert gap.intersect(shape).Volume() < 1e-3


@pytest.mark.cad
@pytest.mark.parametrize('symmetry', ['off', 'xy'])
def test_curved_ring_meshing_compilation_and_closed_exterior(tmp_path, symmetry):
    pytest.importorskip('cadquery'); pytest.importorskip('gmsh')
    from meh_studio.generated_system import HornSources, compile_interior_system
    from meh_studio.radiation_geometry import export_exterior
    design = HornGeometry.model_validate(data() | {'diaphragm_profile_m': HEIGHTS,
        'entry_layout': 'four_driver_ring', 'solver_symmetry': symmetry,
        'rear_axial_mesh_size_m': .002})
    geometry = export_geometry(design, tmp_path / 'geometry')
    mesh = mesh_geometry(tmp_path / 'geometry')
    for region in mesh['regions']:
        moving = [row for row in region['source_area_checks'] if 'entry_' in row['name']]
        assert moving
        for row in moving:
            expected = math.pi * design.front_radius_m**2 / (2 if symmetry == 'xy' else 1)
            assert row['cad_area_m2'] == pytest.approx(expected)
            assert row['area_convention'] == 'projected_on_motion_axis'
            assert row['cad_surface_area_m2'] > expected * 1.05
            assert row['relative_area_error'] < .01
            assert row['relative_surface_area_error'] < .01
        if region['id'] != 'front':
            assert region['layered_rear_mesh']['actual_axial_spacing_m'] == pytest.approx(.002)
    sources = HornSources.model_validate_json((EXAMPLES / 'synthetic-horn-sources.json').read_text())
    compiled = compile_interior_system(tmp_path / 'geometry', sources, tmp_path / 'system')
    assert compiled['driver_count'] == 5
    exterior = export_exterior(design, tmp_path / 'exterior')
    expected = sum(geometry['air_volume_m3'].values()) + sum(geometry['material_volume_m3'].values())
    expected += 4 * math.pi * design.front_radius_m**2 * design.wall_m
    assert exterior['status'] == 'complete'
    assert exterior['cad_volume_m3'] == pytest.approx(expected / (4 if symmetry == 'xy' else 1), rel=1e-6)
