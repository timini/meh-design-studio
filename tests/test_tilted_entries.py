import json
import math
from pathlib import Path

import numpy as np
import pytest

from meh_studio.geometry import HornGeometry, build_geometry, export_geometry, mesh_geometry


def data():
    return json.loads((Path(__file__).resolve().parents[1] / 'examples/three-driver-geometry.json').read_text())


def test_zero_tilt_preserves_radial_design_identity():
    original = HornGeometry.model_validate(data())
    explicit = HornGeometry.model_validate(data() | {'driver_tilt_deg': 0.})
    assert explicit.model_dump_json() == original.model_dump_json()
    assert 'driver_tilt_deg' not in original.model_dump()
    assert original.entry_sites == [('entry_0_positive', .09, (1, 0, 0)), ('entry_0_negative', .09, (-1, 0, 0))]


@pytest.mark.parametrize('patch', [
    {'driver_tilt_deg': -1.}, {'driver_tilt_deg': 60.1}, {'driver_tilt_deg': True},
    {'driver_tilt_deg': float('nan')}, {'driver_tilt_deg': float('inf')},
    {'driver_tilt_deg': 20., 'driver_axial_offset_m': -.001},
])
def test_unsupported_tilt_rejected_before_kernel(patch):
    with pytest.raises(ValueError): HornGeometry.model_validate(data() | patch)


def test_tilted_ring_axes_are_unit_length_and_rotate_together():
    design = HornGeometry.model_validate(data() | {'entry_layout': 'four_driver_ring', 'driver_tilt_deg': 25.})
    axes = {name: np.array(axis) for name, _, axis in design.entry_sites}
    for axis in axes.values():
        assert np.linalg.norm(axis) == pytest.approx(1., abs=1e-15)
        assert axis[2] == pytest.approx(-math.sin(math.radians(25.)))
    rotation = np.array([[0., -1., 0.], [1., 0., 0.], [0., 0., 1.]])
    assert rotation @ axes['entry_0_positive'] == pytest.approx(axes['entry_0_positive_y'])
    assert rotation @ axes['entry_0_positive_y'] == pytest.approx(axes['entry_0_negative'])


@pytest.mark.cad
@pytest.mark.parametrize('freeform', [False, True])
def test_tilt_changes_real_air_geometry_and_keeps_source_planes_clear(freeform):
    pytest.importorskip('cadquery')
    patch = {'entry_layout': 'four_driver_ring'}
    if freeform:
        patch.update(profile_interpolation='periodic_cubic', profile_sections=[
            {'fraction': f, 'radial_scales': [1., 1.1, 1., 1.1, 1., 1.1, 1., 1.1]}
            for f in (.35, .7, 1.)])
    radial = HornGeometry.model_validate(data() | patch)
    tilted = HornGeometry.model_validate(data() | patch | {'driver_tilt_deg': 25.})
    old_air, _, _ = build_geometry(radial)
    air, parts, sources = build_geometry(tilted)
    assert air['front'].cut(old_air['front']).Volume() > 1.
    assert old_air['front'].cut(air['front']).Volume() > 1.
    for region in air.values():
        for part in parts.values(): assert region.intersect(part).Volume() < 1e-3
    for source in sources:
        axis = np.array(source['motion_axis'])
        front, rear = np.array(source['front_center_m']), np.array(source['rear_center_m'])
        assert rear - front == pytest.approx(tilted.wall_m * axis, abs=1e-12)
        assert np.cross(front - [0., 0., .09], axis) == pytest.approx([0., 0., 0.], abs=1e-12)
        for region, centre in ((air['front'], front), (air['rear_' + source['id']], rear)):
            faces = [face for face in region.Faces() if np.linalg.norm(np.array(face.Center().toTuple()) / 1000 - centre) < 1e-8]
            assert len(faces) == 1
            assert faces[0].Area() / 1e6 == pytest.approx(math.pi * tilted.front_radius_m ** 2, rel=1e-8)
            assert abs(np.dot(faces[0].normalAt().toTuple(), axis)) == pytest.approx(1., abs=1e-10)


@pytest.mark.cad
def test_tilted_disk_mesh_normals_reach_compiled_physical_drivers(tmp_path):
    pytest.importorskip('cadquery'); pytest.importorskip('gmsh')
    from meh_studio.generated_system import HornSources, compile_interior_system
    from meh_studio.radiation_geometry import export_exterior
    design = HornGeometry.model_validate(data() | {'entry_layout': 'four_driver_ring', 'driver_tilt_deg': 25.})
    geometry = export_geometry(design, tmp_path / 'geometry')
    mesh = mesh_geometry(tmp_path / 'geometry')
    assert mesh['status'] == 'complete'
    assert all(check['relative_area_error'] <= .01 for region in mesh['regions'] for check in region['source_area_checks'])
    import meshio
    for region in mesh['regions']:
        native_mesh = meshio.read(tmp_path / 'geometry' / region['path'])
        for source in geometry['sources']:
            name = source['id'] + ('_front_source' if region['id'] == 'front' else '_rear_source')
            if name not in native_mesh.field_data: continue
            tag = int(native_mesh.field_data[name][0])
            centre = np.array(source['front_center_m'] if region['id'] == 'front' else source['rear_center_m'])
            axis = np.array(source['motion_axis'])
            count = 0
            for cell, physical in zip(native_mesh.cells, native_mesh.cell_data['gmsh:physical'], strict=True):
                if cell.type != 'triangle': continue
                vertices = native_mesh.points[cell.data[physical == tag]]
                count += len(vertices)
                if not len(vertices): continue
                assert np.max(abs((vertices - centre) @ axis)) < 1e-8
                normals = np.cross(vertices[:, 1] - vertices[:, 0], vertices[:, 2] - vertices[:, 0])
                alignment = abs(normals @ axis) / np.linalg.norm(normals, axis=1)
                assert np.min(alignment) > 1 - 1e-10
            assert count > 0
    sources = HornSources.model_validate_json((Path(__file__).resolve().parents[1] / 'examples/synthetic-horn-sources.json').read_text())
    compile_interior_system(tmp_path / 'geometry', sources, tmp_path / 'system')
    system = json.loads((tmp_path / 'system/project.blab.json').read_text())['physical_system']
    for source in geometry['sources']:
        component = next(c for c in system['components'] if c['name'] == source['id'])
        assert component['parameters']['motion_axis'] == source['motion_axis']
        assert len(component['boundary_ids']) == 2
    exterior = export_exterior(design, tmp_path / 'exterior', .02)
    assert exterior['status'] == 'complete' and exterior['surface']['open_edges'] == 0


@pytest.mark.cad
def test_tilted_back_wall_damage_is_rejected():
    cq = pytest.importorskip('cadquery')
    from meh_studio.geometry import verify_front_chamber_back_walls
    from meh_studio.waveguide_profile import entry_support_radius, horn_solids
    design = HornGeometry.model_validate(data() | {'driver_tilt_deg': 25.})
    air, parts, _ = build_geometry(design)
    _, entry, axis = design.entry_sites[0]
    support = entry_support_radius(design, horn_solids(design)[0], entry, axis)
    start = (support + design.port_length_m) * 1000
    centre = cq.Vector(axis[0] * start, axis[1] * start, entry * 1000 + axis[2] * start)
    cut = cq.Solid.makeCylinder(design.front_radius_m * 1000, design.wall_m * 1000, centre, cq.Vector(*axis))
    damaged = parts['horn'].cut(cut)
    assert damaged.isValid()
    with pytest.raises(ValueError, match='back wall'):
        verify_front_chamber_back_walls(design, air['front'], damaged)


def test_tilt_is_mutated_and_replayed_from_simulated_fitness():
    from test_evolution import inputs
    from meh_studio.optimisation import SearchBrief, candidates, candidate_record
    from meh_studio.evolution import propose, replay
    brief, base, drivers = inputs()
    value = brief.model_dump(mode='json')
    value['evolution'].update(mutation_fraction=1., geometry_bounds={'driver_tilt_deg': [0., 40.]})
    brief = SearchBrief.model_validate(value)
    seeds = candidates(brief, base, drivers)
    first, p0 = propose(brief, seeds, [], [])
    history = [{'status': 'complete', 'objective': 10.}]
    second, p1 = propose(brief, seeds, history, [first])
    assert second['design'].driver_tilt_deg != first['design'].driver_tilt_deg
    assert any(m['key'] == 'driver_tilt_deg' for m in p1['mutations'])
    history.append({'status': 'complete', 'objective': 9.})
    again, proposals = replay(brief, base, drivers, history)
    assert [candidate_record(c) for c in again] == [candidate_record(first), candidate_record(second)]
    assert proposals == [p0, p1]


@pytest.mark.parametrize('bounds', [[-1., 40.], [0., 61.], [20., 20.]])
def test_invalid_tilt_search_bounds_rejected(bounds):
    from meh_studio.evolution import EvolutionSettings
    with pytest.raises(ValueError): EvolutionSettings(geometry_bounds={'driver_tilt_deg': bounds})
