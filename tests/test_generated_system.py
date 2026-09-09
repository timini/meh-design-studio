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
        labels = (["throat_source", "mouth_interface", "entry_0_positive_front_source", "entry_0_negative_front_source"]
                  if name == "front" else [name.removeprefix("rear_") + "_rear_source"])
        labels += ["rigid_walls"]
        physical = [f'2 {tag} "{label}"' for tag, label in enumerate(labels, 10)]
        physical += [f'3 1 "air_{name}"']
        lines = ['$MeshFormat', '2.2 0 8', '$EndMeshFormat', '$PhysicalNames', str(len(physical)),
                 *physical, '$EndPhysicalNames', '$Nodes', '4', '1 0 0 0', '2 1 0 0', '3 0 1 0',
                 '4 0 0 1', '$EndNodes', '$Elements', str(len(labels) + 1)]
        lines += [f'{i} 2 2 {tag} 1 1 2 3' for i, tag in enumerate(range(10, 10+len(labels)), 1)]
        lines += [f'{len(labels)+1} 4 2 1 1 1 2 3 4', '$EndElements']
        mesh_path.write_text('\n'.join(lines) + '\n')
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


@pytest.mark.parametrize('field', ['design', 'sources', 'regions', 'boundaries'])
def test_missing_geometry_fields_are_structured_cli_errors(generated, field, capsys):
    from meh_studio.cli import main
    root, sources, output = generated
    path = root / ('geometry.json' if field in {'design', 'sources'} else 'analysis/mesh.json')
    data = json.loads(path.read_text())
    if field == 'boundaries': del data['regions'][0][field]
    else: del data[field]
    path.write_text(json.dumps(data))
    source_path = root / 'sources.json'
    source_path.write_text(sources.model_dump_json())
    assert main(['compile-interior', str(root), '--sources', str(source_path), '--output', str(output)]) == 2
    assert 'invalid geometry compilation artifact' in json.loads(capsys.readouterr().err)['error']
    assert not output.exists()


@pytest.mark.parametrize('fault', ['wrong', 'duplicate', 'swapped'])
def test_boundary_tags_must_match_mesh_bytes(generated, fault):
    root, sources, output = generated
    path = root / 'analysis/mesh.json'
    data = json.loads(path.read_text())
    boundaries = data['regions'][0]['boundaries']
    if fault == 'wrong': boundaries[0]['tag'] = 999
    if fault == 'duplicate': boundaries[0]['tag'] = boundaries[1]['tag']
    if fault == 'swapped': boundaries[0]['tag'], boundaries[1]['tag'] = boundaries[1]['tag'], boundaries[0]['tag']
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='physical-group'):
        compile_interior_system(root, sources, output)
    assert not output.exists()


@pytest.mark.cad
def test_real_generated_mesh_groups_compile(tmp_path):
    import importlib.util
    if importlib.util.find_spec('cadquery') is None or importlib.util.find_spec('gmsh') is None:
        pytest.skip('CAD runtimes unavailable')
    from meh_studio.geometry import export_geometry, mesh_geometry
    examples = Path(__file__).resolve().parents[1] / 'examples'
    design = HornGeometry.model_validate_json((examples/'three-driver-geometry.json').read_text())
    sources = HornSources.model_validate_json((examples/'synthetic-horn-sources.json').read_text())
    root = tmp_path/'geometry'
    export_geometry(design, root)
    mesh_geometry(root)
    assert compile_interior_system(root, sources, tmp_path/'compiled')['status'] == 'complete'


def test_malformed_matching_hash_mesh_is_a_cli_error(generated, capsys):
    from meh_studio.cli import main
    root, sources, output = generated
    path = root/'analysis/mesh.json'
    data = json.loads(path.read_text())
    mesh_path = root/data['regions'][0]['path']
    mesh_path.write_text('not a mesh')
    data['regions'][0]['sha256'] = sha256(mesh_path)
    path.write_text(json.dumps(data))
    source_path = root/'sources.json'
    source_path.write_text(sources.model_dump_json())
    assert main(['compile-interior',str(root),'--sources',str(source_path),'--output',str(output)]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert 'invalid generated mesh artifact' in json.loads(captured.err)['error']


def test_compiled_mesh_identity_rejects_replacement(generated):
    from meh_studio.boundary_lab import _verify_mesh_declarations
    root, sources, output = generated
    compile_interior_system(root, sources, output)
    project = output/'project.blab.json'
    system = json.loads(project.read_text())['physical_system']
    inventory = {}
    for mesh in system['meshes']:
        path = output/mesh['file']
        inventory[mesh['id']] = {'file':str(path),'purpose':mesh['purpose'],
                                'sha256':sha256(path),'size_bytes':path.stat().st_size}
    _verify_mesh_declarations(system, inventory, project)
    first = next(iter(inventory.values()))
    path = Path(first['file'])
    path.write_bytes(path.read_bytes()+b'\n')
    first.update(sha256=sha256(path),size_bytes=path.stat().st_size)
    with pytest.raises(ValueError, match='compiled geometry identity'):
        _verify_mesh_declarations(system, inventory, project)


@pytest.mark.cad
def test_analytic_tube_fixture_binds_generated_mesh(tmp_path):
    import subprocess
    import sys
    pytest.importorskip('gmsh')
    script = Path(__file__).resolve().parents[1]/'validation/fixtures/generate_plane_wave_tube.py'
    output = tmp_path/'tube'
    subprocess.run([sys.executable,str(script),str(output),'--mesh-size-m','0.02'],check=True,capture_output=True)
    project = json.loads((output/'project.blab.json').read_text())
    assert project['physical_system']['metadata']['generated_mesh_sha256'] == {'mesh:tube':sha256(output/'tube.msh')}
    assert project['physical_system']['metadata']['analytic_reference_sha256'] == sha256(output/'reference.json')


def test_radiating_cancellation_during_interior_copy_is_terminal(generated, monkeypatch):
    import os
    import signal
    import meh_studio.generated_system as interior
    from meh_studio.radiating_system import compile_radiating_system
    if os.name == 'nt':
        pytest.skip('POSIX termination signal')
    root, sources, output = generated
    previous = signal.getsignal(signal.SIGTERM)
    def terminate(*args):
        os.kill(os.getpid(), signal.SIGTERM)
    monkeypatch.setattr(interior.shutil, 'copyfile', terminate)
    class Runtime:
        def verify(self): return {}
    with pytest.raises(KeyboardInterrupt):
        compile_radiating_system(root, sources, output, Runtime())
    assert json.loads((output/'compilation.json').read_text())['status'] == 'cancelled'
    assert signal.getsignal(signal.SIGTERM) == previous


def test_analytic_reference_identity_rejects_changed_load(tmp_path):
    import importlib.util
    import hashlib
    spec = importlib.util.spec_from_file_location('tube_comparison', Path(__file__).resolve().parents[1]/'validation/fixtures/compare_plane_wave_tube.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path/'reference.json'
    path.write_text('{"area_m2":0.0016}')
    project = {'physical_system':{'metadata':{'analytic_reference_sha256':hashlib.sha256(path.read_bytes()).hexdigest()}}}
    assert module.bound_reference(path,project)['area_m2'] == .0016
    path.write_text('{"area_m2":0.1}')
    with pytest.raises(ValueError,match='fixture identity'):
        module.bound_reference(path,project)


def test_cancellation_at_interior_exterior_transition_is_retained(generated, monkeypatch):
    import os
    import signal
    import meh_studio.radiating_system as radiation
    if os.name == 'nt': pytest.skip('POSIX termination')
    root,sources,output=generated
    original=radiation.compile_interior_system
    def completed(*args, **kwargs):
        result=original(*args, **kwargs)
        assert result['status']=='running'
        os.kill(os.getpid(),signal.SIGTERM)
        return result
    monkeypatch.setattr(radiation,'compile_interior_system',completed)
    class Runtime:
        def verify(self):return {}
    with pytest.raises(KeyboardInterrupt):radiation.compile_radiating_system(root,sources,output,Runtime())
    assert json.loads((output/'compilation.json').read_text())['status']=='cancelled'
