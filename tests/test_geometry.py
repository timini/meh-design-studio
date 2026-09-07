import json
import math
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

import pytest

from meh_studio.geometry import HornGeometry, build_geometry, export_geometry, mesh_geometry


@pytest.fixture
def geometry_data():
    return json.loads((Path(__file__).resolve().parents[1] / "examples/three-driver-geometry.json").read_text())


@pytest.mark.parametrize("patch", [
    {"entry_positions_m": []}, {"entry_positions_m": [.01]},
    {"entry_positions_m": [.07, .09]}, {"entry_positions_m": [.17, .07]},
    {"mouth_radius_m": .001}, {"front_radius_m": .003}, {"wall_m": .1},
    {"mesh_size_m": .1}, {"mesh_size_m": 1e-100}, {"rear_depth_m": 1e200},
    {"length_m": True}, {"throat_radius_m": float("nan")},
])
def test_invalid_geometry_rejected_before_kernel(geometry_data, patch):
    with pytest.raises(ValueError):
        HornGeometry.model_validate(geometry_data | patch)


@pytest.mark.cad
@pytest.mark.parametrize("entries", [[.09], [.075, .17]])
def test_material_and_air_are_valid_disjoint_solids(geometry_data, entries):
    pytest.importorskip("cadquery")
    design = HornGeometry.model_validate(geometry_data | {"entry_positions_m": entries})
    air, parts, sources = build_geometry(design)
    assert design.driver_count == 1+len(sources) == 1+2*len(entries)
    for name, solid in air.items():
        assert solid.isValid() and len(solid.Solids()) == 1
        if name.startswith("rear"):
            assert solid.Volume()/1e9 == pytest.approx(math.pi*design.front_radius_m**2*design.rear_depth_m)
        for part in parts.values():
            assert solid.intersect(part).Volume()/1e9 < 1e-12
    items = list(parts.values())
    for i, part in enumerate(items):
        assert part.isValid()
        for other in items[i+1:]:
            assert part.intersect(other).Volume()/1e9 < 1e-12


@pytest.mark.cad
def test_export_mesh_units_and_source_tags(geometry_data, tmp_path):
    pytest.importorskip("cadquery")
    pytest.importorskip("gmsh")
    design = HornGeometry.model_validate(geometry_data)
    report = export_geometry(design, tmp_path / "export")
    assert report["status"] == "complete" and report["print_verified"] is False
    assert report["driver_count"] == 3
    with zipfile.ZipFile(tmp_path / "export/parts/horn.3mf") as archive:
        model = next(name for name in archive.namelist() if name.endswith('.model'))
        root = ET.fromstring(archive.read(model))
        assert root.attrib["unit"] == "millimeter"
    mesh = mesh_geometry(tmp_path / "export")
    assert mesh["status"] == "complete" and mesh["units"] == "m"
    assert mesh["accuracy"] == "not_converged"
    front = next(region for region in mesh["regions"] if region["id"] == "front")
    assert {b["role"] for b in front["boundaries"]} == {"source", "radiation_interface", "rigid_wall"}
    assert sum(b["role"] == "source" for b in front["boundaries"]) == 3
    for region in mesh["regions"]:
        assert region["volume_m3"] == pytest.approx(report["air_volume_m3"][region["id"]], rel=1e-6)
        assert region["tetrahedra"] > 0 and region["minimum_quality"] > 0
    with pytest.raises(FileExistsError):
        export_geometry(design, tmp_path / "export")
    with pytest.raises(FileExistsError):
        mesh_geometry(tmp_path / "export")
