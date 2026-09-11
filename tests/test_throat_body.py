import json
import math
from pathlib import Path

import pytest

from meh_studio.geometry import HornGeometry, build_geometry, export_geometry, mesh_geometry, throat_body_solid


EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def data():
    return json.loads((EXAMPLES / 'three-driver-geometry.json').read_text())


def overhanging(symmetry='off'):
    return HornGeometry.model_validate(data() | {
        'entry_layout': 'four_driver_ring', 'entry_positions_m': [.02],
        'port_length_m': .04, 'solver_symmetry': symmetry,
        'throat_body': {'radius_m': .045, 'depth_m': .0508}})


def test_body_preserves_legacy_identity_and_requires_finite_package_dimensions():
    original = HornGeometry.model_validate(data())
    assert HornGeometry.model_validate(data() | {'throat_body': None}).model_dump_json() == original.model_dump_json()
    assert 'throat_body' not in original.model_dump()
    design = overhanging()
    assert HornGeometry.model_validate_json(design.model_dump_json()) == design
    with pytest.raises(ValueError, match='clear throat'):
        HornGeometry.model_validate(design.model_dump() | {'throat_body': None})
    for body in ({'radius_m': .01, 'depth_m': .05},
                 {'radius_m': .045, 'depth_m': 0.},
                 {'radius_m': True, 'depth_m': .05},
                 {'radius_m': .045, 'depth_m': float('nan')},
                 {'radius_m': .045, 'depth_m': .501}):
        with pytest.raises(ValueError):
            HornGeometry.model_validate(data() | {'throat_body': body})
    with pytest.raises(ValueError, match='ports must clear'):
        HornGeometry.model_validate(design.model_dump() | {'entry_positions_m': [.008]})
    with pytest.raises(ValueError, match='clear throat and mouth'):
        HornGeometry.model_validate(design.model_dump() | {'entry_positions_m': [.24]})


@pytest.mark.cad
def test_overhanging_chambers_clear_real_package_volume_and_reject_collision():
    pytest.importorskip('cadquery')
    design = overhanging()
    air, parts, sources = build_geometry(design)
    body = throat_body_solid(design)
    assert air['front'].BoundingBox().zmin < -10
    for shape in [*air.values(), *parts.values()]:
        assert shape.isValid()
        assert body.intersect(shape).Volume() < 1e-3
    assert body.Volume() / 1e9 == pytest.approx(math.pi * .045**2 * .0508)
    assert len(sources) == 4
    with pytest.raises(ValueError, match='intersects the throat body'):
        build_geometry(HornGeometry.model_validate(design.model_dump() | {
            'throat_body': {'radius_m': .08, 'depth_m': .0508}}))
    # Adding the body to an existing layout changes only the exterior package.
    original = HornGeometry.model_validate(data())
    packaged = HornGeometry.model_validate(data() | {'throat_body': design.throat_body.model_dump()})
    old_air, old_parts, old_sources = build_geometry(original)
    new_air, new_parts, new_sources = build_geometry(packaged)
    assert old_sources == new_sources
    for old, new in ((old_air, new_air), (old_parts, new_parts)):
        for name in old:
            assert old[name].cut(new[name]).Volume() < 1e-3
            assert new[name].cut(old[name]).Volume() < 1e-3


@pytest.mark.cad
@pytest.mark.parametrize('symmetry', ['off', 'xy'])
def test_export_mesh_and_exterior_share_the_body_and_keep_five_drivers(tmp_path, symmetry):
    pytest.importorskip('cadquery'); pytest.importorskip('gmsh')
    import cadquery as cq
    import meshio
    import numpy as np
    from meh_studio.generated_system import HornSources, compile_interior_system
    from meh_studio.radiation_geometry import export_exterior
    design = overhanging(symmetry)
    directory = tmp_path / 'geometry'
    report = export_geometry(design, directory)
    reference = report['throat_body']
    assert reference['clearance_checked'] and not reference['print_part']
    body = cq.importers.importStep(str(directory / reference['file'])).val()
    assert body.isValid() and len(body.Solids()) == 1
    assert body.BoundingBox().zmin / 1000 == pytest.approx(-.0508)
    assert not any('throat-body' in name for name in report['material_volume_m3'])
    mesh = mesh_geometry(directory)
    assert mesh['status'] == 'complete'
    sources = HornSources.model_validate_json((EXAMPLES / 'synthetic-horn-sources.json').read_text())
    compiled = compile_interior_system(directory, sources, tmp_path / 'system')
    assert compiled['driver_count'] == 5
    exterior = export_exterior(design, tmp_path / 'exterior')
    assert exterior['status'] == 'complete' and not exterior['throat_body']['print_part']
    envelope = cq.importers.importStep(str(tmp_path / 'exterior/envelope.step')).val()
    assert envelope.isValid() and len(envelope.Solids()) == 1
    assert envelope.BoundingBox().zmin / 1000 == pytest.approx(-.0508)
    expected = sum(report['air_volume_m3'].values()) + sum(report['material_volume_m3'].values())
    expected += len(report['sources']) * math.pi * design.front_radius_m**2 * design.wall_m
    expected += reference['volume_m3']
    assert exterior['cad_volume_m3'] == pytest.approx(expected / (4 if symmetry == 'xy' else 1), rel=1e-6)
    surface = meshio.read(tmp_path / 'exterior/exterior.msh')
    assert np.min(surface.points[:, 2]) == pytest.approx(-.0508)
