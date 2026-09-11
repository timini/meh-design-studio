import json
from pathlib import Path

import numpy as np
import pytest

from meh_studio.boundary_lab import SolveRequest, inspect_result, sha256
from meh_studio.generated_system import HornSources
from meh_studio.references import solve_driver_circuit
from meh_studio.validation import validate_electrical_basis


@pytest.fixture
def circuit_artifact(tmp_path):
    source = HornSources.model_validate_json((Path(__file__).resolve().parents[1] /
        "examples/synthetic-horn-sources.json").read_text()).side
    ids = ["a", "b"]
    components = [{"id": name, "kind": "electrodynamic_transducer", "parameters": {
        "re_ohm": source.re_ohm, "le_h": source.le_h, "bl_n_per_a": source.bl_n_a}} for name in ids]
    project = tmp_path / "project.json"
    project.write_text(json.dumps({"physical_system": {"meshes": [{"id": "mesh:a", "purpose": "fem_volume", "file": str(tmp_path / "evaluation/upstream/fixture.msh")}],
        "regions": [{"id": "region:a", "kind": "bounded_air", "mesh_ids": ["mesh:a"], "volume_groups":[{"mesh_id":"mesh:a","tag":1}]}], "components": components,
        "excitation_ports": [{"id": name, "component_id": name, "kind": "voltage"} for name in ids]}}))
    root = tmp_path / "evaluation"
    upstream = root / "upstream"
    upstream.mkdir(parents=True)
    request = SolveRequest(frequencies_hz=(1000,))
    (root / "request.json").write_text(request.model_dump_json())
    response = [solve_driver_circuit((source, source), [1000], [row], [[[2, .3], [.3, 2]]])
                for row in (2.83*np.eye(2))]
    arrays = {"current": np.stack([r.current_a[0] for r in response]),
              "velocity": np.stack([r.velocity_m_s[0] for r in response]),
              "pressure": np.zeros((2,4),dtype=np.complex128)}
    np.savez(upstream / "arrays.npz", **arrays)
    quantities = [{"key": key, "id": {"voice_coil_current":"electrical:voice-coil-current", "diaphragm_velocity":"mechanical:diaphragm-velocity"}[name], "quantity": name, "unit": unit,
        "dtype": "complex128", "shape": [2, 2], "axes": ["excitation", "transducer"],
        "target_id": "components:electrodynamic-transducers", "metadata": {"component_ids": ids}} for key, name, unit in (
            ("current", "voice_coil_current", "A"), ("velocity", "diaphragm_velocity", "m/s"))]
    # Pressure is a placeholder in this circuit-only fixture, not acoustic evidence.
    quantities.append({"key":"pressure", "id":"acoustic:pressure:fem-nodes", "quantity":"fem_nodal_pressure",
        "unit":"Pa", "dtype":"complex128", "shape":[2,4], "axes":["excitation","fem_node"],
        "target_id":"domain:fem-volume", "metadata":{"mesh_ids":["mesh:a"],"region_ids":["region:a"],
        "node_counts":[4],"node_offsets":[0]}})
    (upstream / "metadata.json").write_text(json.dumps({"freq_hz": 1000, "excitation_port_ids": ids,
        "arrays_file": "arrays.npz", "quantities": quantities,
        "diagnostics": {"transducer_reference_voltage_v": 2.83}}))
    np.savez(upstream / "domains.npz", ids=np.array(ids), points=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]),tetra=np.array([[0,1,2,3]]))
    (upstream / "domains.json").write_text(json.dumps({"domains": [{
        "id": "components:electrodynamic-transducers", "coordinates": {"component_id": "ids"},
        "topology": {}, "metadata": {}}, {"id":"domain:fem-volume", "coordinates":{"points_m":"points"},
        "topology":{"tetrahedra":"tetra"}, "metadata":{"mesh_ids":["mesh:a"],"node_counts":[4],"tetra_counts":[1],"tetra_offsets":[0],"element_order":1}}]}))
    (upstream / "project.snapshot.blab.json").write_bytes(project.read_bytes())
    mesh_file = upstream / "fixture.msh"
    mesh_file.write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$Nodes\n4\n1 0 0 0\n2 1 0 0\n3 0 1 0\n4 0 0 1\n$EndNodes\n$Elements\n1\n1 4 2 1 1 1 2 3 4\n$EndElements\n")
    (upstream / "manifest.json").write_text(json.dumps({"project_file": "project.snapshot.blab.json",
        "domains_file": "domains.npz", "domains_metadata_file": "domains.json",
        "project_sha256": sha256(project), "meshes": [{"id": "mesh:a", "purpose": "fem_volume",
            "file": str(mesh_file), "sha256": sha256(mesh_file), "size_bytes": mesh_file.stat().st_size}], "schema": "boundary-lab-headless-result",
        "schema_version": 2, "status": "complete", "backend_id": "beat_cpu", "solve_kind": "interior_fem",
        "phasor_convention": "exp(-i omega t)", "frequencies_hz": [1000],
        "excitation_port_ids": ids, "completion_mask": [True],
        "results": [{"freq_hz": 1000, "metadata_file": "metadata.json", "arrays_file": "arrays.npz"}]}))
    def publish():
        (root / "preflight.json").write_text("{}")
        (root / "evaluation.json").write_text(json.dumps({"status": "complete",
            "project_sha256": sha256(project), "request_sha256": sha256(root / "request.json"),
            "preflight_sha256":sha256(root/"preflight.json"), "runtime": {"backend": "beat_cpu"}, "result": inspect_result(upstream, request, "beat_cpu")}))
    publish()
    return project, root, arrays, publish


def test_independent_circuit_passes_consistency_checks(circuit_artifact):
    project, root, _, _ = circuit_artifact
    report = validate_electrical_basis(project, root)
    assert report["passed"] and not report["acoustic_accuracy_validated"]


@pytest.mark.parametrize("fault", ["phase", "amplitude", "nonreciprocal"])
def test_self_consistent_but_physically_wrong_response_fails(circuit_artifact, fault):
    project, root, arrays, publish = circuit_artifact
    if fault == "phase": arrays["current"] = arrays["current"].conj()
    if fault == "amplitude": arrays["velocity"] *= 2
    if fault == "nonreciprocal": arrays["current"][0, 1] *= 10
    np.savez(root / "upstream/arrays.npz", **arrays)
    publish()
    assert not validate_electrical_basis(project, root)["passed"]


def test_changed_artifacts_are_rejected_before_equation_checks(circuit_artifact):
    project, root, arrays, _ = circuit_artifact
    arrays["current"] *= 2
    np.savez(root / "upstream/arrays.npz", **arrays)
    with pytest.raises(ValueError, match="differ"):
        validate_electrical_basis(project, root)


def test_changed_preflight_rejected(circuit_artifact):
    project,root,*_=circuit_artifact
    (root/'preflight.json').write_text('{"changed":true}')
    with pytest.raises(ValueError,match='preflight contract'):
        validate_electrical_basis(project,root)


@pytest.mark.parametrize("field", ["project_sha256", "result", "request_sha256", "runtime"])
def test_missing_evaluation_fields_return_cli_artifact_error(circuit_artifact, capsys, field):
    from meh_studio.cli import main

    project, root, *_ = circuit_artifact
    path = root / "evaluation.json"
    evaluation = json.loads(path.read_text())
    del evaluation[field]
    path.write_text(json.dumps(evaluation))
    assert main(["validate-electrical", str(project), str(root)]) == 2
    captured = capsys.readouterr()
    assert not captured.out
    assert "invalid electrical validation artifact" in json.loads(captured.err)["error"]


def test_complex64_storage_cannot_fail_strict_physical_consistency(circuit_artifact):
    project, root, arrays, publish = circuit_artifact
    for name in ('current','velocity'):
        arrays[name] = arrays[name].astype(np.complex64)
    np.savez(root/'upstream/arrays.npz', **arrays)
    path = root/'upstream/metadata.json'
    metadata = json.loads(path.read_text())
    for quantity in metadata['quantities']:
        if quantity['key'] in {'current','velocity'}: quantity['dtype'] = 'complex64'
    path.write_text(json.dumps(metadata))
    publish()
    with pytest.raises(ValueError, match='requires complex128'):
        validate_electrical_basis(project, root)


def test_electrical_validation_rechecks_arrays_after_metrics(circuit_artifact, monkeypatch):
    import meh_studio.validation as validation
    project, root, arrays, _ = circuit_artifact
    original = validation.np.linalg.eigvalsh
    def change_after_calculation(matrix):
        result = original(matrix)
        arrays['current'] *= 2
        np.savez(root/'upstream/arrays.npz', **arrays)
        return result
    monkeypatch.setattr(validation.np.linalg,'eigvalsh',change_after_calculation)
    with pytest.raises(ValueError):
        validate_electrical_basis(project,root)


@pytest.fixture
def mirrored_circuit_artifact(circuit_artifact):
    """Two mirror-related coils plus one cut central coil, with known full circuit."""
    import meshio
    project, root, arrays, publish = circuit_artifact
    source = HornSources.model_validate_json((Path(__file__).resolve().parents[1] /
        'examples/synthetic-horn-sources.json').read_text()).side
    inputs = np.array([[2.83, 2.83, 0.], [0., 0., 2.83]])
    load = [[2., .4, .3], [.4, 2., .3], [.3, .3, 3.]]
    full = [solve_driver_circuit((source,) * 3, [1000], [row], [load]) for row in inputs]
    full_current = np.stack([r.current_a[0] for r in full])
    full_velocity = np.stack([r.velocity_m_s[0] for r in full])
    arrays.update(current=full_current[:, [0, 2]], velocity=full_velocity[:, [0, 2]],
                  pressure=np.zeros((2, 8), dtype=np.complex128))
    upstream = root / 'upstream'
    np.savez(upstream / 'arrays.npz', **arrays)
    # The first moving triangle is wholly away from X=0, representing two
    # physical coils. The second has a perimeter edge on X=0, completing one.
    points = np.array([[2., 0., 0.], [3., 0., 0.], [2., 1., 0.], [2., 0., 1.],
                       [0., 2., 0.], [1., 2., 0.], [0., 3., 0.], [0., 2., 1.]])
    tetra = np.array([[0, 1, 2, 3], [4, 5, 6, 7]])
    mesh = meshio.Mesh(points, [('tetra', tetra), ('triangle', [[0, 1, 2], [4, 5, 6]])],
                       cell_data={'gmsh:physical': [np.array([1, 1]), np.array([10, 11])],
                                  'gmsh:geometrical': [np.array([1, 1]), np.array([10, 11])]},
                       field_data={'air_a': np.array([1, 3]), 'moving_a': np.array([10, 2]),
                                   'moving_b': np.array([11, 2])})
    mesh_file = upstream / 'fixture.msh'
    meshio.write(mesh_file, mesh, file_format='gmsh22', binary=False)
    p = json.loads(project.read_text()); p['symmetry'] = 'x'
    p['physical_system']['boundaries'] = [
        {'id': 'boundary:' + name, 'kind': 'moving', 'region_id': 'region:a',
         'group': {'mesh_id': 'mesh:a', 'dimension': 2, 'name': 'moving_' + name, 'tag': tag}}
        for name, tag in [('a', 10), ('b', 11)]]
    for c in p['physical_system']['components']:
        c['boundary_ids'] = ['boundary:' + c['id']]
        c['parameters']['motion_axis'] = [0., 0., 1.]
    project.write_text(json.dumps(p)); (upstream / 'project.snapshot.blab.json').write_bytes(project.read_bytes())
    meta_path = upstream / 'metadata.json'; meta = json.loads(meta_path.read_text())
    for q in meta['quantities']:
        if q['key'] == 'pressure':
            q['shape'] = [2, 8]; q['metadata']['node_counts'] = [8]
        else:
            q['metadata'].update(physical_driver_orbit_counts=[2, 1], surface_completion_factors=[1., 2.])
    meta_path.write_text(json.dumps(meta))
    np.savez(upstream / 'domains.npz', ids=np.array(['a', 'b']), points=points, tetra=tetra)
    domain_path = upstream / 'domains.json'; domains = json.loads(domain_path.read_text())
    domains['domains'][1]['metadata'].update(node_counts=[8], tetra_counts=[2])
    domain_path.write_text(json.dumps(domains))
    manifest_path = upstream / 'manifest.json'; manifest = json.loads(manifest_path.read_text())
    manifest['project_sha256'] = sha256(project)
    manifest['meshes'][0].update(sha256=sha256(mesh_file), size_bytes=mesh_file.stat().st_size)
    manifest_path.write_text(json.dumps(manifest)); publish()
    return project, root, arrays, publish, full_current


def test_mirrored_voltage_ports_match_three_physical_coils(mirrored_circuit_artifact):
    project, root, arrays, _, physical = mirrored_circuit_artifact
    per_coil_y = arrays['current'].T / 2.83
    assert np.linalg.norm(per_coil_y - per_coil_y.T) / np.linalg.norm(per_coil_y) > 1e-4
    report = validate_electrical_basis(project, root)
    assert report['passed'] and report['relative_tolerance'] == 1e-8
    assert report['symmetry']['components'] == {
        'a': {'physical_driver_orbit_count': 2, 'surface_completion_factor': 1, 'fractional_symmetry_axes': []},
        'b': {'physical_driver_orbit_count': 1, 'surface_completion_factor': 2, 'fractional_symmetry_axes': ['x']}}
    # Independent full-circuit power agrees for a nontrivial complex drive.
    voltage = np.array([.7 + .2j, -1.1 + .4j])
    physical_current = voltage @ physical / 2.83
    grouped_current = (voltage @ arrays['current'] / 2.83) * [2, 1]
    full_power = np.real(np.vdot(voltage[[0, 0, 1]], physical_current))
    assert np.real(np.vdot(voltage, grouped_current)) == pytest.approx(full_power, rel=1e-13)
    assert full_power > 0


@pytest.mark.parametrize('quantity', ['current', 'velocity'])
@pytest.mark.parametrize('fault', ['orbit', 'completion', 'missing', 'boolean'])
def test_reduced_metadata_must_match_source_mesh(mirrored_circuit_artifact, quantity, fault):
    project, root, _, publish, _ = mirrored_circuit_artifact
    path = root / 'upstream/metadata.json'; metadata = json.loads(path.read_text())
    q = next(q for q in metadata['quantities'] if q['key'] == quantity)
    if fault == 'orbit': q['metadata']['physical_driver_orbit_counts'] = [1, 2]
    if fault == 'completion': q['metadata']['surface_completion_factors'] = [2., 1.]
    if fault == 'missing': del q['metadata']['physical_driver_orbit_counts']
    if fault == 'boolean': q['metadata']['physical_driver_orbit_counts'] = [2, True]
    path.write_text(json.dumps(metadata)); publish()
    with pytest.raises(ValueError, match='multiplicities differ'):
        validate_electrical_basis(project, root)


def test_nonreciprocal_group_current_still_fails(mirrored_circuit_artifact):
    project, root, arrays, publish, _ = mirrored_circuit_artifact
    arrays['current'][0, 1] *= 1.1
    np.savez(root / 'upstream/arrays.npz', **arrays); publish()
    report = validate_electrical_basis(project, root)
    assert not report['passed']
    assert report['rows'][0]['electrical_reciprocity_relative_residual'] > 1e-8


def test_disconnected_source_patches_cannot_imply_different_driver_counts(mirrored_circuit_artifact):
    from meh_studio.driver_symmetry import driver_symmetry_from_meshes
    project, root, *_ = mirrored_circuit_artifact
    p = json.loads(project.read_text())
    p['physical_system']['components'][0]['boundary_ids'].append('boundary:b')
    manifest = json.loads((root / 'upstream/manifest.json').read_text())
    with pytest.raises(ValueError, match='inconsistent symmetry cuts'):
        driver_symmetry_from_meshes(p, manifest)


def test_unreduced_metadata_cannot_invent_extra_coils(circuit_artifact):
    project, root, _, publish = circuit_artifact
    path = root / 'upstream/metadata.json'; metadata = json.loads(path.read_text())
    q = next(q for q in metadata['quantities'] if q['key'] == 'current')
    q['metadata']['physical_driver_orbit_counts'] = [2, 1]
    path.write_text(json.dumps(metadata)); publish()
    with pytest.raises(ValueError, match='multiplicities differ'):
        validate_electrical_basis(project, root)
