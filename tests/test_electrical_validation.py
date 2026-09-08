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
