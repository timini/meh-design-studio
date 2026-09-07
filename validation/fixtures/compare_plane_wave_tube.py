"""Compare a generated uniform-tube solve against its exact input load."""
import argparse
import json
from pathlib import Path

import numpy as np

from meh_studio.boundary_lab import _contained, _read_json, sha256
from meh_studio.domain import SourceModel
from meh_studio.references import solve_driver_circuit
from meh_studio.validation import validate_electrical_basis

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("fixture", type=Path)
parser.add_argument("evaluation", type=Path)
args = parser.parse_args()
reference = _read_json(args.fixture / "reference.json")
project_path = args.fixture / "project.blab.json"
consistency = validate_electrical_basis(project_path, args.evaluation)
project = _read_json(project_path)
p = reference["source_parameters"]
if project["physical_system"]["components"][0]["parameters"] != p:
    raise ValueError("fixture source and project parameters differ")
source = SourceModel(re_ohm=p["re_ohm"], le_h=p["le_h"], bl_n_a=p["bl_n_per_a"],
    mmd_kg=p["mmd_kg"], cms_m_n=p["cms_m_per_n"], rms_ns_m=p["rms_n_s_per_m"],
    sd_m2=reference["area_m2"], provenance={"kind": "synthetic", "source": "Original uniform-tube fixture",
        "permission": "redistribution_allowed", "permission_evidence": "Original synthetic equations fixture"})
load = reference["density_kg_m3"] * reference["sound_speed_m_s"] * reference["area_m2"]
upstream = args.evaluation / "upstream"
manifest = _read_json(upstream / "manifest.json")
rows = []
for row in manifest["results"]:
    exact = solve_driver_circuit((source,), [row["freq_hz"]], [[2.83]], [[[load]]])
    metadata = _read_json(_contained(upstream, row["metadata_file"]))
    quantities = {q["quantity"]: q for q in metadata["quantities"]}
    with np.load(_contained(upstream, row["arrays_file"]), allow_pickle=False) as arrays:
        velocity = arrays[quantities["diaphragm_velocity"]["key"]]
        current = arrays[quantities["voice_coil_current"]["key"]]
        rows.append({"frequency_hz": row["freq_hz"],
            "velocity_relative_error": float(abs(velocity[0, 0] / exact.velocity_m_s[0, 0] - 1)),
            "current_relative_error": float(abs(current[0, 0] / exact.current_a[0, 0] - 1))})
report = {"schema_version": 1, "kind": "analytic_uniform_tube_comparison", "mechanical_load_ns_m": load,
    "mesh_size_m": reference["mesh_size_m"], "rows": rows, "consistency": consistency,
    "evaluation_sha256": sha256(args.evaluation / "evaluation.json"), "physical_validation": False,
    "limitations": ["Input loading check only, not nodal field accuracy", "Synthetic piston, not a purchased driver",
                    "Only the supplied frequencies and mesh level are compared"]}
print(json.dumps(report, indent=2, allow_nan=False))
