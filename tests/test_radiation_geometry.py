from pathlib import Path

import pytest

from meh_studio.geometry import HornGeometry
from meh_studio.radiation_geometry import export_exterior, surface_integrity


@pytest.mark.cad
def test_closed_exterior_has_one_mouth_and_positive_volume(tmp_path):
    pytest.importorskip("cadquery")
    pytest.importorskip("gmsh")
    design = HornGeometry.model_validate_json((Path(__file__).resolve().parents[1] /
        "examples/three-driver-geometry.json").read_text())
    report = export_exterior(design, tmp_path / "exterior")
    assert report["status"] == "complete" and report["print_part"] is False
    assert report["surface"]["open_edges"] == report["surface"]["orientation_errors"] == 0
    assert report["surface"]["enclosed_volume_m3"] == pytest.approx(report["cad_volume_m3"], rel=.02)


@pytest.mark.cad
@pytest.mark.parametrize("fault", [None, "open", "mixed_orientation", "inward", "disconnected", "pinched"])
def test_bem_topology_checks_reject_invalid_surfaces(tmp_path, fault):
    pytest.importorskip("gmsh")
    nodes = [(0,0,0), (1,0,0), (0,1,0), (0,0,1)]
    faces = [(1,3,2), (1,2,4), (1,4,3), (2,3,4)]
    if fault == "open": faces.pop()
    if fault == "mixed_orientation": faces[0] = tuple(reversed(faces[0]))
    if fault == "inward": faces = [tuple(reversed(face)) for face in faces]
    if fault == "disconnected":
        nodes += [(x+2,y,z) for x,y,z in nodes[:]]
        faces += [tuple(node+4 for node in face) for face in faces[:]]
    if fault == "pinched":
        nodes += [(-1,0,0), (0,-1,0), (0,0,-1)]
        mapping = {1:1, 2:5, 3:6, 4:7}
        faces += [tuple(mapping[n] for n in reversed(face)) for face in faces[:]]
    lines = ["$MeshFormat", "2.2 0 8", "$EndMeshFormat", "$Nodes", str(len(nodes))]
    lines += [f"{i} {x} {y} {z}" for i,(x,y,z) in enumerate(nodes,1)]
    lines += ["$EndNodes", "$Elements", str(len(faces))]
    lines += [f"{i} 2 2 1 1 " + " ".join(map(str,face)) for i,face in enumerate(faces,1)]
    lines += ["$EndElements"]
    path = tmp_path / "surface.msh"
    path.write_text("\n".join(lines) + "\n")
    if fault is not None:
        with pytest.raises(ValueError): surface_integrity(path)
    else:
        assert surface_integrity(path)["enclosed_volume_m3"] == pytest.approx(1/6)


def test_radiating_command_imports_and_reports_invalid_runtime(tmp_path, monkeypatch, capsys):
    from meh_studio.radiating_system import compile_radiating_system
    class InvalidRuntime:
        def verify(self):
            raise ValueError("invalid runtime")
    with pytest.raises(ValueError, match="invalid runtime"):
        compile_radiating_system(tmp_path, None, tmp_path / "output", InvalidRuntime())
