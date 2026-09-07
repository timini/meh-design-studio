import json
from pathlib import Path

import pytest

from meh_studio.boundary_lab import sha256
from meh_studio.generated_system import HornSources, compile_interior_system
from meh_studio.geometry import HornGeometry


@pytest.fixture
def generated(tmp_path):
    """Contract fixture only; native meshes are covered by integration evidence."""
    examples = Path(__file__).resolve().parents[1] / "examples"
    design = HornGeometry.model_validate_json((examples / "three-driver-geometry.json").read_text())
    sources = HornSources.model_validate_json((examples / "synthetic-horn-sources.json").read_text())
    root = tmp_path / "geometry"
    (root / "analysis").mkdir(parents=True)
    locations = [{"id": "entry_0_" + side, "motion_axis": [sign, 0, 0]}
                 for side, sign in (("positive", 1), ("negative", -1))]
    geometry = {"status": "complete", "design": design.model_dump(mode="json"),
                "design_hash": design.content_hash, "sources": locations}
    regions = []
    for name in ("front", "rear_entry_0_positive", "rear_entry_0_negative"):
        mesh_path = root / "analysis" / (name + ".msh")
        mesh_path.write_bytes(b"contract fixture, not a solver mesh")
        labels = (["throat_source", "mouth_interface", "entry_0_positive_front_source", "entry_0_negative_front_source"]
                  if name == "front" else [name.removeprefix("rear_") + "_rear_source"])
        labels += ["rigid_walls"]
        regions.append({"id": name, "path": str(mesh_path.relative_to(root)), "sha256": sha256(mesh_path),
                        "boundaries": [{"name": label, "tag": tag} for tag, label in enumerate(labels, 10)]})
    mesh = {"status": "complete", "design_hash": design.content_hash, "units": "m", "regions": regions}
    (root / "geometry.json").write_text(json.dumps(geometry))
    (root / "analysis/mesh.json").write_text(json.dumps(mesh))
    return root, sources, tmp_path / "compiled"


def test_compilation_keeps_passive_sources_and_explicit_rear_air(generated):
    root, sources, output = generated
    report = compile_interior_system(root, sources, output)
    assert report["status"] == "complete" and report["qualified"] is False
    project = json.loads((output / "project.blab.json").read_text())["physical_system"]
    assert len(project["components"]) == len(project["excitation_ports"]) == 3
    for component in project["components"]:
        parameters = component["parameters"]
        assert parameters["motion_profile"] == "rigid_translation"
        assert "mmd_kg" in parameters and "mms_kg" not in parameters
        assert "rear_compliance" not in parameters
        assert len(component["boundary_ids"]) == (1 if component["name"] == "throat" else 2)
    assert sum(b["kind"] == "moving" for b in project["boundaries"]) == 5
    assert all(m["scale_to_m"] == 1 for m in project["meshes"])
    with pytest.raises(FileExistsError):
        compile_interior_system(root, sources, output)


def test_effective_area_mismatch_is_not_silently_rescaled(generated):
    root, sources, output = generated
    data = sources.model_dump(mode="json")
    data["side"]["sd_m2"] *= 2
    with pytest.raises(ValueError, match="effective area"):
        compile_interior_system(root, HornSources.model_validate(data), output)
    assert not output.exists()


@pytest.mark.parametrize("fault", ["units", "hash", "region", "boundary", "file"])
def test_incomplete_or_changed_mesh_cannot_compile(generated, fault):
    root, sources, output = generated
    path = root / "analysis/mesh.json"
    mesh = json.loads(path.read_text())
    if fault == "units": mesh["units"] = "mm"
    if fault == "hash": mesh["design_hash"] = "0" * 64
    if fault == "region": mesh["regions"].pop()
    if fault == "boundary": mesh["regions"][0]["boundaries"].pop()
    if fault == "file": (root / mesh["regions"][0]["path"]).write_bytes(b"changed")
    path.write_text(json.dumps(mesh))
    with pytest.raises(ValueError):
        compile_interior_system(root, sources, output)
    assert not output.exists()
