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


def test_explicit_throat_transform_compiles_outlet_circuit_and_retains_physical_source(generated):
    from meh_studio.operating import diaphragm_velocity_ratios
    root, original, output = generated
    data = original.model_dump(mode='json')
    data['throat']['ideal_outlet_area_m2'] = data['throat']['sd_m2']
    data['throat']['sd_m2'] *= 3
    sources = HornSources.model_validate(data)
    compile_interior_system(root, sources, output)
    system = json.loads((output / 'project.blab.json').read_text())['physical_system']
    throat = next(c for c in system['components'] if c['id'] == 'component:throat')
    assert throat['parameters']['mmd_kg'] == pytest.approx(sources.throat.mmd_kg / 9)
    assert throat['parameters']['bl_n_per_a'] == pytest.approx(sources.throat.bl_n_a / 3)
    assert HornSources.model_validate_json((output / 'sources.json').read_text()) == sources
    ids = [c['id'] for c in system['components']]
    ratios = diaphragm_velocity_ratios(system, ids, output / 'sources.json')
    assert ratios.tolist() == pytest.approx([3., 1., 1.])
    system['metadata']['ideal_outlet_transforms']['component:throat']['diaphragm_area_m2'] *= 2
    with pytest.raises(ValueError, match='physical source record'):
        diaphragm_velocity_ratios(system, ids, output / 'sources.json')


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
    import meh_studio.radiating_system as radiation
    monkeypatch.setattr(radiation,'require_cad_dependencies',lambda:None)
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
    monkeypatch.setattr(radiation,'require_cad_dependencies',lambda:None)
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


def test_changed_source_axis_cannot_compile(generated):
    root, sources, output = generated
    path = root/'geometry.json'
    saved = json.loads(path.read_text())
    saved['sources'][0]['motion_axis'] = [0,1,0]
    path.write_text(json.dumps(saved))
    with pytest.raises(ValueError, match='motion axes'):
        compile_interior_system(root, sources, output)


@pytest.mark.parametrize('angle',[None,10.])
@pytest.mark.parametrize('distance',[1.,20.,.1])
def test_sphere_observations_are_bound_into_compiled_project_identity(generated,monkeypatch,angle,distance):
    import meh_studio.radiating_system as radiation
    root,sources,output=generated
    monkeypatch.setattr(radiation,'require_cad_dependencies',lambda:None)
    def exterior(design,destination,size):
        destination.mkdir();(destination/'exterior.json').write_text('{}')
        return {'cad_volume_m3':1.,'compiler_runtime':{},'cad_geometry_sha256':'fixture'}
    monkeypatch.setattr(radiation,'export_exterior',exterior)
    monkeypatch.setattr(radiation,'conform_mouth_interface',lambda *args:{})
    monkeypatch.setattr(radiation,'restore_fem_interface_coordinates',lambda *args:{})
    monkeypatch.setattr(radiation,'surface_integrity',lambda *args,**kwargs:{'sha256':'fixture','enclosed_volume_m3':1.})
    monkeypatch.setattr(radiation,'verify_exterior_groups',lambda *args:None)
    monkeypatch.setattr(radiation,'meshing_runtime_identity',lambda:{})
    monkeypatch.setattr(radiation,'observation_enclosing_radius',lambda path:.3)
    class Runtime:
        python=Path('fixture-python');checkout=Path('.')
        def verify(self):return {}
    if distance == .1:
        with pytest.raises(ValueError,match='enclose the complete exterior'):
            radiation.compile_radiating_system(root,sources,output,Runtime(),sphere_angle_deg=angle,
                                              observation_distance_m=distance)
        assert json.loads((output/'compilation.json').read_text())['status']=='failed'
        return
    report=radiation.compile_radiating_system(root,sources,output,Runtime(),sphere_angle_deg=angle,
                                             observation_distance_m=distance)
    project=json.loads((output/'project.blab.json').read_text())
    assert report['project_sha256']==sha256(output/'project.blab.json')
    assert project['project_preferences']['spherical_sampling_enabled']==(angle is not None)
    assert project['project_preferences']['polar_observation_distance_m']==distance
    assert report['observations']['distance_m']==distance
    assert report['observations']['far_field_qualified'] is False
    if angle is not None:
        assert project['project_preferences']['balloon_angle_precision_deg']==angle
        assert report['sphere_sampling']['point_count']==413
    else: assert 'sphere_sampling' not in report
