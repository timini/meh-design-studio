"""Independent consistency checks on full voltage-basis electrodynamic results.

These verify circuit conservation and reciprocal/passive electrical response;
none is an independent test of the acoustic discretisation's accuracy.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np

from .boundary_lab import SolveRequest, _contained, _read_json, inspect_result, sha256


def validate_electrical_basis(project_path: Path, evaluation_directory: Path) -> dict:
    project_path, root = Path(project_path), Path(evaluation_directory)
    evaluation = _read_json(root / "evaluation.json")
    if evaluation.get("status") != "complete" or evaluation["project_sha256"] != sha256(project_path):
        raise ValueError("validation requires a complete evaluation of this project")
    if "artifact_hashes" not in evaluation["result"]:
        raise ValueError("saved evaluation predates domain integrity checks; rerun the solver")
    request_path = root / "request.json"
    if sha256(request_path) != evaluation["request_sha256"]:
        raise ValueError("request identity mismatch")
    request = SolveRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    backend = evaluation["result"].get("backend_id", evaluation["runtime"]["backend"])
    result = inspect_result(root / "upstream", request, backend)
    if result != evaluation["result"]:
        raise ValueError("result artifacts differ from the completed evaluation")
    system = _read_json(project_path)["physical_system"]
    components = {c["id"]: c for c in system["components"]}
    ports = {p["id"]: p for p in system["excitation_ports"]}
    excitation_ids = result["excitation_port_ids"]
    if set(excitation_ids) != set(ports) or any(p["kind"] != "voltage" for p in ports.values()):
        raise ValueError("a complete voltage excitation basis is required")
    component_ids = [ports[p]["component_id"] for p in excitation_ids]
    if len(set(component_ids)) != len(component_ids) or set(component_ids) != set(components):
        raise ValueError("one voltage port per electrodynamic component is required")
    if any(c["kind"] != "electrodynamic_transducer" for c in components.values()):
        raise ValueError("electrodynamic components are required")
    parameters = [components[c]["parameters"] for c in component_ids]
    re = np.array([p["re_ohm"] for p in parameters])
    le = np.array([p["le_h"] for p in parameters])
    bl = np.array([p["bl_n_per_a"] for p in parameters])
    rows = []
    manifest = _read_json(root / "upstream/manifest.json")
    for row in manifest["results"]:
        metadata = _read_json(_contained(root / "upstream", row["metadata_file"]))
        reference_v = metadata.get("diagnostics", {}).get("transducer_reference_voltage_v")
        if reference_v != 2.83:
            raise ValueError("the pinned native voltage normalisation must be explicit")
        quantities = {q["quantity"]: q for q in metadata["quantities"]}
        arrays = {}
        with np.load(_contained(root / "upstream", row["arrays_file"]), allow_pickle=False) as archive:
            for name in ("voice_coil_current", "diaphragm_velocity"):
                q = quantities[name]
                ids = q["metadata"]["component_ids"]
                if set(ids) != set(component_ids) or len(ids) != len(component_ids):
                    raise ValueError("response component identities do not match the voltage basis")
                if q["axes"] != ["excitation", "transducer"]:
                    raise ValueError("unsupported response axis order")
                arrays[name] = archive[q["key"]][:, [ids.index(c) for c in component_ids]]
        current, velocity = arrays["voice_coil_current"], arrays["diaphragm_velocity"]
        voltage = reference_v * np.eye(len(component_ids))
        ze = re - 1j * 2 * np.pi * row["freq_hz"] * le
        kvl_relative = float(np.linalg.norm(voltage - ze * current - bl * velocity) / np.linalg.norm(voltage))
        admittance = current.T / reference_v
        scale = max(float(np.linalg.norm(admittance)), np.finfo(float).tiny)
        reciprocity_relative = float(np.linalg.norm(admittance - admittance.T) / scale)
        passive_min = float(np.linalg.eigvalsh((admittance + admittance.conj().T) / 2).min())
        passed = kvl_relative <= 1e-8 and reciprocity_relative <= 1e-8 and passive_min >= -1e-8 * scale
        rows.append({"frequency_hz": row["freq_hz"], "passed": passed,
                     "circuit_voltage_relative_residual": kvl_relative,
                     "electrical_reciprocity_relative_residual": reciprocity_relative,
                     "minimum_hermitian_admittance_eigenvalue_s": passive_min})
    return {"schema_version": 1, "evidence": "independent_equation_consistency",
            "passed": all(r["passed"] for r in rows), "project_sha256": sha256(project_path),
            "evaluation_sha256": sha256(root / "evaluation.json"), "rows": rows,
            "relative_tolerance": 1e-8, "acoustic_accuracy_validated": False,
            "limitations": ["Circuit consistency cannot establish acoustic field accuracy",
                            "No measured driver or speaker comparison", "No RMS or absolute SPL qualification"]}
