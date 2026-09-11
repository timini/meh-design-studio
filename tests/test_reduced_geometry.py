import json
from pathlib import Path

import numpy as np
import pytest

from meh_studio.geometry import HornGeometry, export_geometry, mesh_geometry
from meh_studio.generated_system import HornSources, compile_interior_system
from meh_studio.radiation_geometry import export_exterior, surface_integrity


EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def design_data():
    return json.loads((EXAMPLES / 'three-driver-geometry.json').read_text())


def test_quarter_mode_changes_identity_without_changing_physical_inventory():
    original = HornGeometry.model_validate(design_data())
    reduced = HornGeometry.model_validate(design_data() | {'solver_symmetry': 'xy'})
    assert original.driver_count == reduced.driver_count == 3
    assert original.entry_sites == reduced.entry_sites
    assert len(reduced.solver_entry_sites) == 1
    assert original.content_hash != reduced.content_hash
    assert 'solver_symmetry' not in original.model_dump(mode='json')
    with pytest.raises(ValueError):
        HornGeometry.model_validate(design_data() | {'solver_symmetry': 'x'})


@pytest.mark.cad
@pytest.mark.parametrize('layout', ['opposed_pairs', 'four_driver_ring'])
def test_complete_physical_export_compiles_reduced_sources(tmp_path, layout):
    pytest.importorskip('cadquery')
    pytest.importorskip('gmsh')
    design = HornGeometry.model_validate(design_data() | {'solver_symmetry': 'xy', 'entry_layout': layout})
    root = tmp_path / 'geometry'
    physical = export_geometry(design, root)
    mesh = mesh_geometry(root)
    assert physical['driver_count'] == design.driver_count
    assert len(physical['sources']) == design.driver_count - 1
    assert len(mesh['regions']) == 1 + (design.driver_count - 1) // 2
    for region in mesh['regions']:
        fraction = .25 if region['id'] == 'front' else .5
        assert region['volume_m3'] == pytest.approx(physical['air_volume_m3'][region['id']] * fraction, rel=1e-6)
        assert all(check['relative_area_error'] <= .01 for check in region['source_area_checks'])
        assert '$MeshFormat\n4.1 0 ' in (root / region['path']).read_text()
    sources = HornSources.model_validate_json((EXAMPLES / 'synthetic-horn-sources.json').read_text())
    compiled = compile_interior_system(root, sources, tmp_path / 'system')
    assert compiled['driver_count'] == design.driver_count
    assert compiled['represented_component_count'] == len(mesh['regions'])
    assert sum(v['physical_driver_orbit_count'] for v in compiled['driver_symmetry'].values()) == design.driver_count
    project = json.loads((tmp_path / 'system/project.blab.json').read_text())
    assert project['symmetry'] == 'xy'
    assert len(project['physical_system']['components']) == len(mesh['regions'])
    exterior = export_exterior(design, tmp_path / 'exterior')
    assert exterior['surface']['validation'] == 'closed_oriented_fourfold_reflection'
    assert exterior['surface']['native_open_edges'] > 0
    assert exterior['surface']['enclosed_volume_m3'] == pytest.approx(exterior['cad_volume_m3'], rel=.02)
    # Partition provenance is required even when the meshes themselves are intact.
    with (root / 'analysis/partition.json').open('a') as stream:
        stream.write('\n')
    with pytest.raises(ValueError, match='partition identity'):
        compile_interior_system(root, sources, tmp_path / 'tampered')


@pytest.mark.cad
def test_requested_mirrors_must_hold_in_actual_cad():
    pytest.importorskip('cadquery')
    from meh_studio.cad_runtime import load_cadquery
    from meh_studio.reduced_geometry import mirror_difference
    cq = load_cadquery()
    design = HornGeometry.model_validate(design_data())
    shape = cq.Workplane().box(100, 100, 100).translate((10, 0, 0)).val()
    with pytest.raises(ValueError, match='mirror symmetry'):
        mirror_difference(design, shape, shape.mirror('YZ'))


@pytest.mark.cad
@pytest.mark.parametrize('fault', [None, 'missing', 'orientation', 'outside', 'cap'])
def test_quarter_open_boundary_requires_closed_reflected_topology(tmp_path, fault):
    pytest.importorskip('gmsh')
    import meshio
    # Quarter octahedron: two external faces; X/Y cuts must remain absent.
    points = np.array([[0., 0, -1], [1., 0, 0], [0, 1., 0], [0, 0, 1.]])
    faces = np.array([[0, 2, 1], [3, 1, 2]])
    if fault == 'missing': faces = faces[:1]
    if fault == 'orientation': faces[0] = faces[0, ::-1]
    if fault == 'outside': points[1, 1] = -.01
    if fault == 'cap': faces = np.vstack([faces, [0, 1, 3]])
    path = tmp_path / 'quarter.msh'
    meshio.write(path, meshio.Mesh(points, [('triangle', faces)]), file_format='gmsh22', binary=False)
    if fault:
        with pytest.raises(ValueError):
            surface_integrity(path, symmetry='xy')
    else:
        report = surface_integrity(path, symmetry='xy', maximum_triangles=2)
        assert report['triangles'] == 2
        assert report['native_open_edges'] == 4
        assert report['enclosed_volume_m3'] == pytest.approx(1 / 3)
        with pytest.raises(ValueError):
            surface_integrity(path, symmetry='off')


def test_profile_evolution_cannot_break_required_solver_mirrors():
    from meh_studio.evolution import EvolutionSettings, validate_bounds
    design = HornGeometry.model_validate(design_data() | {'solver_symmetry': 'xy',
        'profile_interpolation': 'periodic_cubic',
        'profile_sections': [{'fraction': z, 'radial_scales': [1.] * 8} for z in (.5, 1.)]})
    with pytest.raises(ValueError, match='quarter model profile evolution'):
        validate_bounds(EvolutionSettings(), design)
    validate_bounds(EvolutionSettings(profile_symmetry='mirror_xy'), design)
