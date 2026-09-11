"""Version-pinned subprocess adapter. A completed solve is a prediction, not validation."""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import zipfile
from typing import Annotated, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .domain import Positive, Record

BOUNDARY_LAB_REVISION = "8cb166226e412877d3f71f2845918e479b97aa85"


class BEMQuadrature(BaseModel):
    """Explicit fixed integration rules supported by the pinned CPU solvers."""
    model_config = ConfigDict(extra='forbid', frozen=True)
    quadrature_order: Annotated[int, Field(strict=True)] = 2
    singular_order: Annotated[int, Field(strict=True, ge=1, le=8)] = 2
    regular_quadrature_mode: Literal['fixed'] = 'fixed'

    @model_validator(mode='after')
    def supported_rule(self):
        # Other positive orders silently fall back to order 2 upstream.
        if self.quadrature_order not in (1, 2, 4):
            raise ValueError('regular BEM quadrature order must be 1, 2 or 4')
        return self


class SolveRequest(Record):
    frequencies_hz: tuple[Positive, ...]
    include_project_observations: bool = False
    retain: tuple[Literal["bem_boundary_pressure", "bem_boundary_neumann",
                          "bem_boundary_traces", "fem_nodal_pressure"], ...] = ()
    solver_options: BEMQuadrature | None = None

    @model_serializer(mode='wrap')
    def preserve_legacy_request(self, handler):
        value = handler(self)
        if self.solver_options is None:
            value.pop('solver_options', None)
        return value

    @model_validator(mode="after")
    def ordered(self):
        if not self.frequencies_hz or len(self.frequencies_hz) > 10000:
            raise ValueError("request requires 1–10000 frequencies")
        if any(b <= a for a, b in zip(self.frequencies_hz, self.frequencies_hz[1:])):
            raise ValueError("frequencies must be strictly increasing")
        if len(set(self.retain)) != len(self.retain):
            raise ValueError("retained quantities must be unique")
        return self


def _requested_solver_options(request, backend, solve_kind):
    if request.solver_options is None:
        return None
    if backend not in ('beat_cpu', 'coupled_reference') or solve_kind not in ('exterior_bem', 'coupled_bem_fem'):
        raise ValueError('explicit BEM quadrature requires a supported CPU boundary solver')
    return request.solver_options.model_dump(mode='json')


def _verify_solver_options(request, backend, manifest):
    expected = _requested_solver_options(request, backend, manifest.get('solve_kind'))
    if expected is None:
        return
    observed = manifest.get('solver_options')
    if not isinstance(observed, dict) or any(
            type(observed.get(key)) is not type(value) or observed[key] != value
            for key, value in expected.items()):
        raise ValueError('result BEM quadrature differs from the requested integration rules')


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("artifact JSON root must be an object")
        # Check the whole tree, including overflowed numeric literals.
        json.dumps(payload, allow_nan=False)
        return payload
    except RecursionError as exc:
        raise ValueError("artifact JSON exceeds nesting limit") from exc


def _write_json(path: Path, payload):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def _contained(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError("result references a missing file or a path outside its directory")
    return path


QUANTITY_UNITS = {
    "fem_nodal_pressure": "Pa", "bem_boundary_pressure": "Pa",
    "bem_boundary_neumann": "Pa/m", "exterior_pressure": "Pa",
    "diaphragm_velocity": "m/s", "voice_coil_current": "A",
    "radiation_impedance": "N*s/m",
}
OUTPUT_QUANTITIES = {
    "ui:exterior-pressure": "exterior_pressure",
    "acoustic:pressure:fem-nodes": "fem_nodal_pressure",
    "acoustic:pressure:bem-boundary": "bem_boundary_pressure",
    "acoustic:normal-derivative:bem-boundary": "bem_boundary_neumann",
    "mechanical:diaphragm-velocity": "diaphragm_velocity",
    "electrical:voice-coil-current": "voice_coil_current",
    "acoustic:radiation-impedance": "radiation_impedance",
    "acoustic:pressure:horizontal-polar": "exterior_pressure",
    "acoustic:pressure:vertical-polar": "exterior_pressure",
    "acoustic:pressure:sphere": "exterior_pressure",
}


QUANTITY_AXES = {
    "fem_nodal_pressure": ["excitation", "fem_node"],
    "bem_boundary_pressure": ["excitation", "bem_node"],
    "bem_boundary_neumann": ["excitation", "bem_face"],
    "exterior_pressure": ["excitation", "observation"],
    "diaphragm_velocity": ["excitation", "transducer"],
    "voice_coil_current": ["excitation", "transducer"],
    # The pinned upstream publishes one self impedance per radiator, not a matrix.
    "radiation_impedance": ["radiator"],
}
SOLVE_KINDS = {"interior_fem", "exterior_bem", "coupled_bem_fem"}


def _project_solve_kind(project: dict) -> str:
    regions = project.get("physical_system", {}).get("regions")
    if not isinstance(regions, list) or not regions:
        raise ValueError("explicit physical-system regions are required")
    kinds = [r.get("kind") for r in regions]
    if any(k not in {"bounded_air", "unbounded_air"} for k in kinds) or kinds.count("unbounded_air") > 1:
        raise ValueError("unsupported acoustic region topology")
    return ("interior_fem" if "unbounded_air" not in kinds else
            "exterior_bem" if "bounded_air" not in kinds else "coupled_bem_fem")


def _quantity_dimensions(quantity: dict, values: np.ndarray, excitation_count: int):
    name = quantity["quantity"]
    if quantity["axes"] != QUANTITY_AXES[name] or any(n <= 0 for n in values.shape):
        raise ValueError("quantity axes or dimensions differ from the physical contract")
    metadata = quantity.get("metadata", {})
    if not isinstance(metadata, dict):
        raise ValueError("quantity metadata must be an object")
    if name in {"diaphragm_velocity", "voice_coil_current"}:
        if len(_output_ids(metadata.get("component_ids"))) != values.shape[1]:
            raise ValueError("transducer dimension differs from component inventory")
    if name == "radiation_impedance" and values.shape[0] != excitation_count:
        raise ValueError("radiator dimension differs from the full excitation basis")
    counts_key = {"fem_nodal_pressure": "node_counts", "bem_boundary_pressure": "vertex_counts",
                  "bem_boundary_neumann": "face_counts"}.get(name)
    if counts_key and (name == "fem_nodal_pressure" or counts_key in metadata):
        counts = metadata.get(counts_key)
        if (not isinstance(counts, list) or not counts or
                any(type(n) is not int or n <= 0 for n in counts) or sum(counts) != values.shape[1]):
            raise ValueError("field dimension differs from mesh node/face inventory")
        if len(_output_ids(metadata.get("mesh_ids"))) != len(counts):
            raise ValueError("field inventory differs from mesh identities")
        offset_key = {"node_counts": "node_offsets", "vertex_counts": "vertex_offsets",
                      "face_counts": "face_offsets"}[counts_key]
        if metadata.get(offset_key) != [sum(counts[:i]) for i in range(len(counts))]:
            raise ValueError("field offsets differ from mesh inventory")
        if name == "fem_nodal_pressure" and len(_output_ids(metadata.get("region_ids"))) != len(counts):
            raise ValueError("field inventory differs from region identities")


def _output_ids(ids) -> tuple[str, ...]:
    if (not isinstance(ids, (list, tuple)) or not ids
            or any(not isinstance(item, str) or not item for item in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("output IDs must be nonempty unique strings")
    return tuple(ids)


def _automatic_output_ids(system: dict) -> set[str]:
    required = set()
    if any(c.get("kind") == "electrodynamic_transducer" for c in system.get("components", [])):
        required.update(("mechanical:diaphragm-velocity", "electrical:voice-coil-current"))
    kinds = {r.get("kind") for r in system.get("regions", [])}
    if kinds == {"bounded_air"}:
        required.add("acoustic:pressure:fem-nodes")
    if kinds == {"unbounded_air"}:
        required.add("acoustic:radiation-impedance")
    return required


def _require_project_outputs(system: dict, output_ids):
    if not _automatic_output_ids(system).issubset(output_ids):
        raise ValueError("omitted mandatory project outputs")
    kinds = {r.get("kind") for r in system.get("regions", [])}
    acoustic_ids = {"ui:exterior-pressure", "acoustic:pressure:horizontal-polar",
                   "acoustic:pressure:vertical-polar", "acoustic:pressure:sphere",
                   "acoustic:pressure:fem-nodes", "acoustic:pressure:bem-boundary",
                   "acoustic:normal-derivative:bem-boundary"}
    if kinds == {"bounded_air", "unbounded_air"} and not acoustic_ids.intersection(output_ids):
        raise ValueError("coupled evaluation requires an explicitly requested acoustic field or observation")


def _verify_mesh_declarations(system: dict, meshes: dict, project_path: Path | None):
    declared = {m["id"]: m for m in system["meshes"]}
    if set(meshes) != set(declared):
        raise ValueError("solved mesh inventory differs from the project")
    bound_hashes = system.get("metadata", {}).get("generated_mesh_sha256")
    if bound_hashes is not None:
        if not isinstance(bound_hashes, dict) or set(bound_hashes) != set(declared):
            raise ValueError("generated mesh identity inventory differs from project")
        if any(bound_hashes[identity] != mesh["sha256"] for identity, mesh in meshes.items()):
            raise ValueError("evaluated mesh differs from compiled geometry identity")
    for identity, mesh in meshes.items():
        source = Path(declared[identity]["file"])
        if not source.is_absolute():
            if project_path is None:
                raise ValueError("original project path is required to resolve declared relative meshes")
            source = project_path.parent / source
        source = source.resolve()
        if (Path(mesh["file"]).resolve() != source or mesh["purpose"] != declared[identity]["purpose"]
                or source.stat().st_size != mesh["size_bytes"] or sha256(source) != mesh["sha256"]):
            raise ValueError("solved mesh file identity differs from the project declaration")


def _retained_output_ids(request: SolveRequest) -> set[str]:
    mapping = {"fem_nodal_pressure":{"acoustic:pressure:fem-nodes"},
               "bem_boundary_pressure":{"acoustic:pressure:bem-boundary"},
               "bem_boundary_neumann":{"acoustic:normal-derivative:bem-boundary"},
               "bem_boundary_traces":{"acoustic:pressure:bem-boundary","acoustic:normal-derivative:bem-boundary"}}
    return set().union(*(mapping[name] for name in request.retain))


def _project_observation_ids(project: dict, request: SolveRequest) -> set[str]:
    """Derive requirements from the pinned project format, not solver preflight."""
    required = set()
    if request.include_project_observations:
        system = project.get("physical_system")
        if not isinstance(system, dict) or not isinstance(system.get("regions"), list):
            raise ValueError("project observations require explicit physical-system regions")
        if any(region.get("kind") == "unbounded_air" for region in system["regions"]):
            required.add("ui:exterior-pressure")
    # Upstream retains plane fields even when polar observations are disabled.
    for plane in project.get("observation_planes", []):
        kind = plane.get("type", "interior")
        if kind in {"interior", "combined"}:
            required.add("acoustic:pressure:fem-nodes")
        if kind in {"exterior", "combined"}:
            required.update(("acoustic:pressure:bem-boundary",
                             "acoustic:normal-derivative:bem-boundary"))
    return required


def _result_output_ids(project: dict, compiled_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Pinned upstream splits its compact polar block before saving artifacts."""
    ids = list(_output_ids(compiled_ids))
    if "ui:exterior-pressure" in ids:
        ids.remove("ui:exterior-pressure")
        ids.extend(("acoustic:pressure:horizontal-polar", "acoustic:pressure:vertical-polar"))
        if project.get("project_preferences", {}).get("spherical_sampling_enabled", False):
            ids.append("acoustic:pressure:sphere")
    return _output_ids(ids)


def _mesh_inventory(payload: dict) -> list[dict]:
    meshes = payload.get("meshes")
    if not isinstance(meshes, list) or not meshes:
        raise ValueError("a nonempty mesh inventory is required")
    seen = set()
    for mesh in meshes:
        if not isinstance(mesh, dict):
            raise ValueError("malformed mesh identity")
        for key in ("id", "file", "purpose", "sha256"):
            if not isinstance(mesh.get(key), str) or not mesh[key]:
                raise ValueError("missing mesh identity field")
        if mesh["id"] in seen:
            raise ValueError("duplicate mesh identity")
        seen.add(mesh["id"])
        digest = mesh["sha256"]
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError("invalid mesh digest")
        if type(mesh.get("size_bytes")) is not int or mesh["size_bytes"] <= 0:
            raise ValueError("invalid mesh byte size")
        if not Path(mesh["file"]).is_absolute():
            raise ValueError("mesh identity must contain an absolute source path")
    return meshes


class EvaluationCancelled(KeyboardInterrupt):
    """Termination requested by the process supervisor."""

    def __init__(self, message, signum=None):
        super().__init__(message)
        self.signum = signum


@contextmanager
def _termination_guard(report):
    if threading.current_thread() is not threading.main_thread():
        raise ValueError("run the solver adapter in a worker process, not a background thread")
    signals = (signal.SIGINT,) if os.name == "nt" else (signal.SIGINT, signal.SIGTERM)
    previous = {sig: signal.getsignal(sig) for sig in signals}
    state = {"reserving": True, "requested": None, "cancelling": False}
    def terminate(signum, frame):
        # Once a terminal state is selected, commit it without interruption.
        # Repeated signals must also allow child cleanup/reporting to finish.
        if report["status"] != "running" or state["cancelling"]:
            return
        if state["reserving"]:
            state["requested"] = signum
            return
        state["cancelling"] = True
        # Select cancellation before unwinding, including an interrupt inside
        # the exception-reporting handler rather than its protected try body.
        report.update(status="cancelled", error=f"signal {signum} requested cancellation")
        raise EvaluationCancelled(f"signal {signum} requested cancellation", signum=signum)
    def activate():
        state["reserving"] = False
        if state["requested"] is not None:
            terminate(state["requested"], None)
    try:
        for sig in signals:
            signal.signal(sig, terminate)
        yield activate
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _result_project(root: Path, manifest: dict, project_path: Path | None) -> tuple[dict, dict]:
    path = _contained(root, manifest["project_file"])
    if sha256(path) != manifest.get("project_sha256"):
        raise ValueError("project snapshot hash mismatch")
    project = _read_json(path)
    system = project["physical_system"]
    meshes = {m["id"]: m for m in _mesh_inventory(manifest)}
    if project_path is not None and sha256(project_path) != manifest["project_sha256"]:
        raise ValueError("result project snapshot differs from the original project")
    _verify_mesh_declarations(system, meshes, project_path)
    return project, meshes


def _field_identity(quantity: dict, system: dict, meshes: dict):
    name = quantity["quantity"]
    metadata = quantity.get("metadata", {})
    if name in {"diaphragm_velocity", "voice_coil_current"}:
        expected = {c["id"] for c in system["components"] if c["kind"] == "electrodynamic_transducer"}
        if set(metadata["component_ids"]) != expected:
            raise ValueError("response component inventory differs from the project")
    if name in {"fem_nodal_pressure", "bem_boundary_pressure", "bem_boundary_neumann"}:
        purpose = "fem_volume" if name == "fem_nodal_pressure" else "bem_surface"
        applicable = {mid for mid, mesh in meshes.items() if mesh["purpose"] == purpose}
        # Exterior-only upstream BEM outputs have no per-quantity mesh metadata;
        # their field spans all exterior meshes. Supplied identities must be exact.
        ids = metadata.get("mesh_ids", list(applicable))
        if set(ids) != applicable or len(ids) != len(applicable) or not applicable:
            raise ValueError("field mesh identities differ from the solved inventory")
        if name == "fem_nodal_pressure":
            regions = {r["id"]: r for r in system["regions"] if r["kind"] == "bounded_air"}
            if set(metadata["region_ids"]) != set(regions):
                raise ValueError("field region identities differ from the project")
            for mid, rid in zip(ids, metadata["region_ids"]):
                if mid not in regions[rid]["mesh_ids"]:
                    raise ValueError("field mesh does not belong to the declared region")


def _inspect_result(root: Path, request: SolveRequest, backend: str,
                    expected_output_ids: tuple[str, ...] | None = None,
                    expected_solve_kind: str | None = None, project_path: Path | None = None,
                    *, partial: bool = False) -> dict:
    """Inspect complete results, or explicitly identified completed rows of a stopped run."""
    if expected_output_ids is not None:
        expected_output_ids = _output_ids(expected_output_ids)
    root = Path(root)
    manifest_hash = sha256(root / "manifest.json")
    manifest = _read_json(root / "manifest.json")
    if (manifest.get("schema") != "boundary-lab-headless-result"
            or manifest.get("schema_version") != 2):
        raise ValueError("unsupported Boundary Lab result schema")
    if manifest.get("solve_kind") not in SOLVE_KINDS or (
            expected_solve_kind is not None and manifest["solve_kind"] != expected_solve_kind):
        raise ValueError("result solve kind differs from the physical contract")
    if partial and manifest.get('status') not in ('running','complete','failed','cancelled'):
        raise ValueError('unknown upstream partial result status')
    if not partial and manifest.get("status") != "complete":
        raise ValueError("upstream result is not complete")
    if manifest.get("backend_id") != backend or manifest.get("phasor_convention") != "exp(-i omega t)":
        raise ValueError("backend or phasor convention mismatch")
    _verify_solver_options(request, backend, manifest)
    artifact_paths = {"manifest": root / "manifest.json",
                      "domains_metadata": _contained(root, manifest["domains_metadata_file"]),
                      "domains_arrays": _contained(root, manifest["domains_file"])}
    if backend == 'coupled_reference':
        reference = manifest['reference_runtime']
        runtime_path = _contained(root, reference['file'])
        if (sha256(runtime_path) != reference['sha256']
                or _read_json(runtime_path) != reference['identity']
                or reference['identity'].get('revision') != BOUNDARY_LAB_REVISION):
            raise ValueError('FP64 reference runtime evidence mismatch')
        artifact_paths['reference_runtime'] = runtime_path
    artifact_hashes = {name: sha256(path) for name, path in artifact_paths.items()}
    if artifact_hashes["manifest"] != manifest_hash:
        raise ValueError("manifest changed while inspecting results")
    project, meshes = _result_project(root, manifest, Path(project_path).resolve() if project_path is not None else None)
    system = project["physical_system"]
    if manifest["solve_kind"] != _project_solve_kind(project):
        raise ValueError("result solve kind differs from the saved project topology")
    from .result_domains import load_domains, check_quantity_domain
    domains = load_domains(root, manifest, system, meshes, project=project)
    observations = _project_observation_ids(project, request)
    observation_outputs = set(_result_output_ids(project, tuple(sorted(observations)))) if observations else set()
    frequencies = list(request.frequencies_hz)
    if manifest.get("frequencies_hz") != frequencies:
        raise ValueError("result frequency grid differs from request")
    completion = manifest.get("completion_mask", [])
    if (len(completion) != len(frequencies) or any(type(x) is not bool for x in completion)
            or not partial and not all(completion)):
        raise ValueError("incomplete frequency mask")
    excitations = manifest.get("excitation_port_ids")
    if (not isinstance(excitations, list) or not excitations
            or any(not isinstance(x, str) or not x for x in excitations)
            or len(set(excitations)) != len(excitations)):
        raise ValueError("invalid excitation axis")
    expected_excitations = _output_ids([p["id"] for p in system["excitation_ports"]])
    if tuple(excitations) != expected_excitations:
        raise ValueError("result excitation basis differs from the project")
    rows = manifest.get("results", [])
    if len(rows) != len(frequencies):
        raise ValueError("missing frequency results")
    requested_frequencies=frequencies
    if partial:
        if not any(completion):raise ValueError('partial result has no completed frequencies')
        if any(row is not None for row,done in zip(rows,completion) if not done):
            raise ValueError('incomplete frequency must not have a result row')
        rows=[row for row,done in zip(rows,completion) if done]
        frequencies=[frequency for frequency,done in zip(frequencies,completion) if done]
    inventory = []
    seen_arrays = set()
    frequency_hashes = {}
    first_contract = None
    for frequency, row in zip(frequencies, rows):
        if not isinstance(row, dict) or row.get("freq_hz") != frequency:
            raise ValueError("frequency result mismatch")
        metadata_path = _contained(root, row["metadata_file"])
        array_path = _contained(root, row["arrays_file"])
        if array_path in seen_arrays:
            raise ValueError("frequency rows must reference distinct array artifacts")
        seen_arrays.add(array_path)
        frequency_hashes[metadata_path] = sha256(metadata_path)
        frequency_hashes[array_path] = sha256(array_path)
        metadata = _read_json(metadata_path)
        if metadata.get("freq_hz") != frequency or metadata.get("excitation_port_ids") != excitations:
            raise ValueError("frequency metadata axis mismatch")
        if _contained(metadata_path.parent, metadata["arrays_file"]) != array_path:
            raise ValueError("array references disagree")
        quantities = metadata.get("quantities", [])
        if not quantities or len({q["key"] for q in quantities}) != len(quantities):
            raise ValueError("missing or duplicate quantities")
        actual_ids = _output_ids([q["id"] for q in quantities])
        _require_project_outputs(system, actual_ids)
        if not observation_outputs.issubset(actual_ids):
            raise ValueError("result omitted requested project observations")
        if expected_output_ids is not None and set(actual_ids) != set(expected_output_ids):
            raise ValueError("returned quantities differ from the compiled output contract")
        required = set(request.retain)
        if "bem_boundary_traces" in required:
            required.remove("bem_boundary_traces")
            required.update(("bem_boundary_pressure", "bem_boundary_neumann"))
        if not required.issubset({q.get("quantity") for q in quantities}):
            raise ValueError("result is missing a requested retained quantity")
        with np.load(array_path, allow_pickle=False) as arrays:
            if set(arrays.files) != {q["key"] for q in quantities}:
                raise ValueError("quantity metadata does not match stored arrays")
            for quantity in quantities:
                values = arrays[quantity["key"]]
                if (list(values.shape) != quantity["shape"] or str(values.dtype) != quantity["dtype"]
                        or values.dtype not in (np.dtype("complex64"), np.dtype("complex128")) or not np.all(np.isfinite(values))):
                    raise ValueError("non-finite or inconsistent quantity array")
                if backend == 'coupled_reference' and values.dtype != np.dtype('complex128'):
                    raise ValueError('FP64 reference requires complex128 quantity storage')
                axes = quantity["axes"]
                name = quantity.get("quantity")
                if name not in QUANTITY_UNITS or quantity.get("unit") != QUANTITY_UNITS[name]:
                    raise ValueError("quantity unit does not match the physical contract")
                expected_name = OUTPUT_QUANTITIES.get(quantity["id"])
                if expected_name is None or expected_name != name:
                    raise ValueError("quantity name does not match its output ID")
                if (not isinstance(axes, list) or len(axes) != values.ndim
                        or any(not isinstance(axis, str) or not axis for axis in axes)
                        or len(set(axes)) != len(axes)):
                    raise ValueError("missing or duplicate quantity axes")
                if name != "radiation_impedance" and axes.count("excitation") != 1:
                    raise ValueError("quantity requires an excitation axis")
                if "excitation" in axes and values.shape[axes.index("excitation")] != len(excitations):
                    raise ValueError("quantity excitation count mismatch")
                _quantity_dimensions(quantity, values, len(excitations))
                _field_identity(quantity, system, meshes)
                check_quantity_domain(quantity, values, domains)
        contract = {q["id"]: {k: v for k, v in q.items() if k != "key"} for q in quantities}
        if first_contract is not None and contract != first_contract:
            raise ValueError("physical quantity inventories changed across frequencies")
        first_contract = contract
        inventory.append({"frequency_hz": frequency, "metadata_sha256": frequency_hashes[metadata_path],
                          "arrays_sha256": frequency_hashes[array_path], "quantities": quantities})
    if any(sha256(path) != digest for path, digest in frequency_hashes.items()):
        raise ValueError("frequency artifacts changed during inspection")
    if project_path is not None and sha256(Path(project_path)) != manifest["project_sha256"]:
        raise ValueError("original project changed during inspection")
    if any(sha256(Path(mesh["file"])) != mesh["sha256"] for mesh in meshes.values()):
        raise ValueError("source mesh changed during inspection")
    if sha256(_contained(root, manifest["project_file"])) != manifest["project_sha256"]:
        raise ValueError("project snapshot changed during inspection")
    if any(sha256(path) != artifact_hashes[name] for name, path in artifact_paths.items()):
        raise ValueError("result domain artifacts changed during inspection")
    result={"evidence": "predicted", "artifact_hashes": artifact_hashes, "solve_kind": manifest.get("solve_kind"),
            "phasor_convention": manifest["phasor_convention"], "frequencies_hz": frequencies,
            "excitation_port_ids": excitations, "inventory": inventory}
    if partial:
        result.update(evidence='predicted_partial',upstream_status=manifest['status'],
            requested_frequencies_hz=requested_frequencies,
            missing_frequencies_hz=[f for f,done in zip(requested_frequencies,completion) if not done])
    return result


def inspect_result(root: Path, request: SolveRequest, backend: str,
                   expected_output_ids: tuple[str, ...] | None = None,
                    expected_solve_kind: str | None = None, project_path: Path | None = None) -> dict:
    try:
        return _inspect_result(root, request, backend, expected_output_ids, expected_solve_kind, project_path)
    except (KeyError, TypeError, AttributeError, RecursionError, EOFError, OSError, IndexError, zipfile.BadZipFile) as exc:
        raise ValueError(f"invalid or missing result artifact: {exc}") from exc


def inspect_partial_result(root: Path, request: SolveRequest, backend: str,
                           expected_output_ids: tuple[str, ...] | None = None,
                           expected_solve_kind: str | None = None, project_path: Path | None = None) -> dict:
    """Read completed samples without promoting the original solve to complete.

    Callers must establish that the managed evaluation has stopped before reuse.
    All retained arrays, physical domains, sources and requested outputs receive
    the same checks as a complete result. Missing rows remain explicit.
    """
    try:
        return _inspect_result(root,request,backend,expected_output_ids,expected_solve_kind,project_path,partial=True)
    except (KeyError, TypeError, AttributeError, RecursionError, EOFError, OSError, IndexError, zipfile.BadZipFile) as exc:
        raise ValueError(f'invalid or missing partial result artifact: {exc}') from exc


def _kill_process_group(pgid: int):
    last_error = None
    for attempt in range(20):
        try:
            os.killpg(pgid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
        except PermissionError as exc:
            if sys.platform != "darwin":
                raise
            last_error = exc
            # Darwin can return EPERM for members already exiting. Inspect the
            # whole group and permit a bounded grace for kernel exit/reaping.
            snapshot = subprocess.check_output(
                ["/bin/ps", "-A", "-o", "pgid=,stat="], text=True, timeout=5)
            live = []
            for line in snapshot.splitlines():
                group, state = line.split()
                if int(group) == pgid and not state.startswith("Z"):
                    live.append(state)
            if not live:
                return
            if attempt < 19:
                time.sleep(.05)
    raise last_error


@contextmanager
def _process_cancellation_guard():
    if threading.current_thread() is not threading.main_thread():
        raise ValueError("process launch must run in its worker main thread")
    signals = (signal.SIGINT,) if os.name == "nt" else (signal.SIGINT, signal.SIGTERM)
    previous = {sig:signal.getsignal(sig) for sig in signals}
    pending = set()
    state = {"deferred":True}
    def forward(sig):
        handler = previous[sig]
        if callable(handler):
            handler(sig,None)
        elif handler != signal.SIG_IGN:
            raise EvaluationCancelled(f"signal {sig} during process lifecycle", signum=sig)
    def dispatch(signum, frame):
        if previous[signum] == signal.SIG_IGN:
            return
        if state["deferred"]:
            pending.add(signum)
        else:
            forward(signum)
    def defer():
        state["deferred"] = True
    def activate():
        state["deferred"] = False
        while pending:
            forward(pending.pop())
    try:
        for sig in signals:
            signal.signal(sig,dispatch)
        yield activate,defer
    finally:
        for sig,handler in previous.items():
            signal.signal(sig,handler)


_inherit_process_group = ContextVar('meh_inherit_process_group', default=False)


@contextmanager
def _preparation_process_group():
    """Keep nested conformers inside the group owned by the search parent.

    Windows uses the enclosing Job Object instead. On POSIX this context is
    valid only in the isolated group leader created for candidate preparation.
    """
    if os.name != 'nt' and os.getpgrp() != os.getpid():
        raise ValueError('preparation child must lead its isolated process group')
    token = _inherit_process_group.set(os.name != 'nt')
    try:
        yield
    finally:
        _inherit_process_group.reset(token)


def _execute(command: list[str], cwd: Path, log: Path, timeout_s: float,
             stderr_log: Path | None = None, *, process_name: str = 'Boundary Lab') -> None:
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout must be positive and finite")
    with ExitStack() as stack:
        job = None
        inherited = _inherit_process_group.get()
        options = {"start_new_session": not inherited}
        if os.name == "nt":
            from .windows_job import WindowsJob, CREATE_SUSPENDED
            job = stack.enter_context(WindowsJob())
            options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED}
        stream = stack.enter_context(log.open("wb"))
        diagnostics = (stack.enter_context(stderr_log.open("wb"))
                       if stderr_log is not None else subprocess.STDOUT)
        activate, defer = stack.enter_context(_process_cancellation_guard())
        process = None
        try:
            process = subprocess.Popen(command, cwd=cwd, stdout=stream, stderr=diagnostics, **options)
            activate()
            if job is not None:
                job.assign_and_resume(process.pid)
            code = process.wait(timeout=timeout_s)
            defer()
        except BaseException:
            defer()
            raise
        finally:
            # The PID is covered before deferred cancellation can be raised.
            if process is not None:
                try:
                    if job is not None:
                        job.close()
                    elif not inherited:
                        _kill_process_group(process.pid)
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.wait()
            activate()
    if code:
        raise ValueError(f"{process_name} exited with code {code}; see {log.name}")


@dataclass(frozen=True)
class BoundaryLabRuntime:
    checkout: Path
    python: Path
    julia: Path
    backend: Literal["beat_cpu", "beat_cuda", "beat_rocm", "coupled_reference"] = "beat_cpu"
    julia_threads: int | None = None

    def verify(self) -> dict:
        if self.julia_threads is not None and (type(self.julia_threads) is not int or not 1 <= self.julia_threads <= 64):
            raise ValueError("Julia thread count must be an integer in [1, 64]")
        if self.backend not in {"beat_cpu", "beat_cuda", "beat_rocm", "coupled_reference"}:
            raise ValueError("unsupported explicit backend")
        checkout = Path(self.checkout).resolve()
        revision = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"],
                                           text=True, timeout=30).strip()
        if revision != BOUNDARY_LAB_REVISION:
            raise ValueError("Boundary Lab revision differs from the supported pin")
        dirty = subprocess.check_output(["git", "-C", str(checkout), "diff", "HEAD", "--name-only"],
                                        text=True, timeout=30).strip()
        if dirty:
            raise ValueError("Boundary Lab tracked files have local modifications")
        # Preserve the virtualenv executable path; resolving its symlink loses its environment.
        python = Path(self.python).absolute()
        probe = subprocess.check_output([str(python), "-I", "-c",
            "import blab, json, sys, importlib.metadata as m; "
            "print(json.dumps({'module':blab.__file__,'python':sys.version,'python_version':list(sys.version_info[:2]),"
            "'packages':{d.metadata['Name']:d.version for d in m.distributions()}}))"],
            cwd=checkout, text=True, encoding="utf-8", timeout=30)
        environment = json.loads(probe)
        if environment.get("python_version") != [3, 11]:
            raise ValueError("the supported Boundary Lab runtime requires Python 3.11")
        if Path(environment["module"]).resolve() != checkout / "src/blab/__init__.py":
            raise ValueError("Python imports Boundary Lab from a different checkout")
        julia_version = subprocess.check_output([str(Path(self.julia).absolute()), "--version"],
                                               text=True, encoding="utf-8", timeout=30).strip()
        if julia_version != "julia version 1.12.6":
            raise ValueError("pinned Boundary Lab dependencies require the manifest-matched Julia 1.12.6 runtime")
        reference = ({'reference_runner_sha256':sha256(Path(__file__).with_name('native_reference.py')),
                      'precision':'float64', 'static_condensation':True}
                     if self.backend == 'coupled_reference' else {})
        return {"revision": revision, "backend": self.backend, "python": environment["python"],
                "julia": julia_version, "packages": environment["packages"],
                "julia_threads": self.julia_threads if self.julia_threads is not None else
                    (4 if self.backend == 'coupled_reference' else "upstream_default"),
                **reference}

    def solve(self, project: Path, request: SolveRequest, output: Path, *, timeout_s: float = 1800) -> dict:
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout must be positive and finite")
        if threading.current_thread() is not threading.main_thread():
            raise ValueError("run the solver adapter in a worker process, not a background thread")
        project, output = Path(project).resolve(), Path(output).resolve()
        request_file = output / "request.json"
        started = time.monotonic()
        report = {"schema_version": 1, "status": "running",
                  "started_at_utc": datetime.now(timezone.utc).isoformat()}
        with _termination_guard(report) as activate:
            owned = False
            try:
                output.mkdir(parents=True, exist_ok=False)
                owned = True
                activate()
                _write_json(output / "evaluation.json", report)
                base = [str(Path(self.python).absolute()), "-I", "-m", "blab.cli", "project"]
                preflight_backend = 'beat_cpu' if self.backend == 'coupled_reference' else self.backend
                common = [str(project), "--request", str(request_file), "--backend", preflight_backend,
                          "--julia-executable", str(Path(self.julia).absolute())]
                runtime = self.verify()
                solve_options = (["--julia-threads", str(self.julia_threads)]
                                 if self.julia_threads is not None else [])
                project_hash = sha256(project)
                _write_json(request_file, request.model_dump(mode="json"))
                report.update(runtime=runtime, project_sha256=project_hash, request_sha256=sha256(request_file))
                _execute(base + ["validate"] + common + ["--json"], Path(self.checkout),
                         output / "preflight.json", timeout_s, stderr_log=output / "preflight.stderr.log")
                preflight_hash = sha256(output / "preflight.json")
                preflight = _read_json(output / "preflight.json")
                report["preflight_sha256"] = preflight_hash
                if preflight.get("valid") is not True:
                    raise ValueError("upstream preflight did not confirm validity")
                project_data = _read_json(project)
                solve_kind = _project_solve_kind(project_data)
                if preflight.get("solve_kind") != solve_kind:
                    raise ValueError("preflight solve kind differs from project topology")
                _requested_solver_options(request, self.backend, solve_kind)
                preflight_meshes = _mesh_inventory(preflight)
                expected_outputs = _output_ids(preflight.get("output_ids"))
                _verify_mesh_declarations(project_data["physical_system"], {m["id"]:m for m in preflight_meshes}, project)
                _require_project_outputs(project_data["physical_system"], expected_outputs)
                if not _retained_output_ids(request).issubset(expected_outputs):
                    raise ValueError("preflight omitted requested retained quantities")
                observations = _project_observation_ids(project_data, request)
                if not observations.issubset(expected_outputs):
                    raise ValueError("preflight omitted requested project observations")
                if self.backend == 'coupled_reference':
                    if solve_kind != 'coupled_bem_fem':
                        raise ValueError('FP64 reference backend requires a coupled FEM/BEM project')
                    runner = Path(__file__).with_name('native_reference.py').resolve()
                    _execute([str(Path(self.python).absolute()), '-I', str(runner), str(project),
                              str(request_file), str(output/'upstream'), '--julia', str(Path(self.julia).absolute()),
                              '--julia-threads', str(self.julia_threads if self.julia_threads is not None else 4)],
                             Path(self.checkout), output/'solve.ndjson', timeout_s,
                             stderr_log=output/'solve.stderr.log')
                else:
                    _execute(base + ["solve"] + common + solve_options + ["--events", "ndjson", "--output", str(output / "upstream")],
                             Path(self.checkout), output / "solve.ndjson", timeout_s)
                result = inspect_result(output / "upstream", request, self.backend,
                                        _result_output_ids(project_data, expected_outputs), solve_kind, project)
                if sha256(project) != project_hash or sha256(request_file) != report["request_sha256"]:
                    raise ValueError("project or request changed during evaluation")
                manifest = _read_json(output / "upstream/manifest.json")
                if self.backend == 'coupled_reference' and (
                        manifest.get('reference_runner_sha256') != runtime['reference_runner_sha256']
                        or manifest.get('source_request_sha256') != report['request_sha256']):
                    raise ValueError('FP64 runner or request identity differs from the evaluated input')
                if manifest.get("project_sha256") != project_hash:
                    raise ValueError("solver project snapshot differs from evaluated input")
                meshes = _mesh_inventory(manifest)
                if meshes != preflight_meshes:
                    raise ValueError("mesh identity changed between preflight and solve")
                for mesh in meshes:
                    if (Path(mesh["file"]).stat().st_size != mesh["size_bytes"]
                            or sha256(Path(mesh["file"])) != mesh["sha256"]):
                        raise ValueError("source mesh changed during evaluation")
                if self.verify() != runtime:
                    raise ValueError("runtime changed during evaluation")
                if sha256(output / "preflight.json") != preflight_hash:
                    raise ValueError("preflight contract changed during evaluation")
                report.update(status="complete", result=result)
            except BaseException as exc:
                status = ("timed_out" if isinstance(exc, subprocess.TimeoutExpired) else
                          "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed")
                report.update(status=status, error=f"{type(exc).__name__}: {exc}")
                raise
            finally:
                if owned:
                    report["elapsed_s"] = time.monotonic() - started
                    _write_json(output / "evaluation.json", report)
            return report
