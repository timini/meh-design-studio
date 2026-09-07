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
    project.write_text(json.dumps({"physical_system": {"components": components,
        "excitation_ports": [{"id": name, "component_id": name, "kind": "voltage"} for name in ids]}}))
    root = tmp_path / "evaluation"
    upstream = root / "upstream"
    upstream.mkdir(parents=True)
    request = SolveRequest(frequencies_hz=(1000,))
    (root / "request.json").write_text(request.model_dump_json())
    response = [solve_driver_circuit((source, source), [1000], [row], [[[2, .3], [.3, 2]]])
                for row in (2.83*np.eye(2))]
    arrays = {"current": np.stack([r.current_a[0] for r in response]),
              "velocity": np.stack([r.velocity_m_s[0] for r in response])}
    np.savez(upstream / "arrays.npz", **arrays)
    quantities = [{"key": key, "id": name, "quantity": name, "unit": unit,
        "dtype": "complex128", "shape": [2, 2], "axes": ["excitation", "transducer"],
        "metadata": {"component_ids": ids}} for key, name, unit in (
            ("current", "voice_coil_current", "A"), ("velocity", "diaphragm_velocity", "m/s"))]
    (upstream / "metadata.json").write_text(json.dumps({"freq_hz": 1000, "excitation_port_ids": ids,
        "arrays_file": "arrays.npz", "quantities": quantities,
        "diagnostics": {"transducer_reference_voltage_v": 2.83}}))
    (upstream / "manifest.json").write_text(json.dumps({"schema": "boundary-lab-headless-result",
        "schema_version": 2, "status": "complete", "backend_id": "beat_cpu", "solve_kind": "interior_fem",
        "phasor_convention": "exp(-i omega t)", "frequencies_hz": [1000],
        "excitation_port_ids": ids, "completion_mask": [True],
        "results": [{"freq_hz": 1000, "metadata_file": "metadata.json", "arrays_file": "arrays.npz"}]}))
    def publish():
        (root / "evaluation.json").write_text(json.dumps({"status": "complete",
            "project_sha256": sha256(project), "request_sha256": sha256(root / "request.json"),
            "runtime": {"backend": "beat_cpu"}, "result": inspect_result(upstream, request, "beat_cpu")}))
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
