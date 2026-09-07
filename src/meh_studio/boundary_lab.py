"""Version-pinned subprocess adapter. A completed solve is a prediction, not validation."""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import zipfile
from typing import Literal

import numpy as np
from pydantic import model_validator

from .domain import Positive, Record

BOUNDARY_LAB_REVISION = "8cb166226e412877d3f71f2845918e479b97aa85"


class SolveRequest(Record):
    frequencies_hz: tuple[Positive, ...]
    include_project_observations: bool = False
    retain: tuple[Literal["bem_boundary_pressure", "bem_boundary_neumann",
                          "bem_boundary_traces", "fem_nodal_pressure"], ...] = ()

    @model_validator(mode="after")
    def ordered(self):
        if not self.frequencies_hz or len(self.frequencies_hz) > 10000:
            raise ValueError("request requires 1–10000 frequencies")
        if any(b <= a for a, b in zip(self.frequencies_hz, self.frequencies_hz[1:])):
            raise ValueError("frequencies must be strictly increasing")
        if len(set(self.retain)) != len(self.retain):
            raise ValueError("retained quantities must be unique")
        return self


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Check the whole tree, including metadata and overflowed numeric literals.
    json.dumps(payload, allow_nan=False)
    return payload


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


def _output_ids(ids) -> tuple[str, ...]:
    if (not isinstance(ids, (list, tuple)) or not ids
            or any(not isinstance(item, str) or not item for item in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("output IDs must be nonempty unique strings")
    return tuple(ids)


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


@contextmanager
def _termination_guard():
    if os.name == "nt":
        yield
        return
    if threading.current_thread() is not threading.main_thread():
        raise ValueError("run the solver adapter in a worker process, not a background thread")
    previous = signal.getsignal(signal.SIGTERM)
    def terminate(signum, frame):
        # Let cleanup finish even if a supervisor repeats SIGTERM.
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        raise EvaluationCancelled("SIGTERM requested cancellation")
    signal.signal(signal.SIGTERM, terminate)
    try:
        yield
    finally:
        signal.signal(signal.SIGTERM, previous)


def _inspect_result(root: Path, request: SolveRequest, backend: str,
                    expected_output_ids: tuple[str, ...] | None = None) -> dict:
    """Reject partial runs and retain raw complex quantities without DSP synthesis."""
    if expected_output_ids is not None:
        expected_output_ids = _output_ids(expected_output_ids)
    root = Path(root)
    manifest = _read_json(root / "manifest.json")
    if (manifest.get("schema") != "boundary-lab-headless-result"
            or manifest.get("schema_version") != 2):
        raise ValueError("unsupported Boundary Lab result schema")
    if manifest.get("status") != "complete":
        raise ValueError("upstream result is not complete")
    if manifest.get("backend_id") != backend or manifest.get("phasor_convention") != "exp(-i omega t)":
        raise ValueError("backend or phasor convention mismatch")
    frequencies = list(request.frequencies_hz)
    if manifest.get("frequencies_hz") != frequencies:
        raise ValueError("result frequency grid differs from request")
    completion = manifest.get("completion_mask", [])
    if len(completion) != len(frequencies) or any(x is not True for x in completion):
        raise ValueError("incomplete frequency mask")
    excitations = manifest.get("excitation_port_ids")
    if (not isinstance(excitations, list) or not excitations
            or any(not isinstance(x, str) or not x for x in excitations)
            or len(set(excitations)) != len(excitations)):
        raise ValueError("invalid excitation axis")
    rows = manifest.get("results", [])
    if len(rows) != len(frequencies):
        raise ValueError("missing frequency results")
    inventory = []
    seen_arrays = set()
    for frequency, row in zip(frequencies, rows):
        if not isinstance(row, dict) or row.get("freq_hz") != frequency:
            raise ValueError("frequency result mismatch")
        metadata_path = _contained(root, row["metadata_file"])
        array_path = _contained(root, row["arrays_file"])
        if array_path in seen_arrays:
            raise ValueError("frequency rows must reference distinct array artifacts")
        seen_arrays.add(array_path)
        metadata = _read_json(metadata_path)
        if metadata.get("freq_hz") != frequency or metadata.get("excitation_port_ids") != excitations:
            raise ValueError("frequency metadata axis mismatch")
        if _contained(metadata_path.parent, metadata["arrays_file"]) != array_path:
            raise ValueError("array references disagree")
        quantities = metadata.get("quantities", [])
        if not quantities or len({q["key"] for q in quantities}) != len(quantities):
            raise ValueError("missing or duplicate quantities")
        actual_ids = _output_ids([q["id"] for q in quantities])
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
                axes = quantity["axes"]
                name = quantity.get("quantity")
                if name not in QUANTITY_UNITS or quantity.get("unit") != QUANTITY_UNITS[name]:
                    raise ValueError("quantity unit does not match the physical contract")
                expected_name = OUTPUT_QUANTITIES.get(quantity["id"])
                if expected_name is not None and expected_name != name:
                    raise ValueError("quantity name does not match its output ID")
                if (not isinstance(axes, list) or len(axes) != values.ndim
                        or any(not isinstance(axis, str) or not axis for axis in axes)
                        or len(set(axes)) != len(axes)):
                    raise ValueError("missing or duplicate quantity axes")
                if name != "radiation_impedance" and axes.count("excitation") != 1:
                    raise ValueError("quantity requires an excitation axis")
                if "excitation" in axes and values.shape[axes.index("excitation")] != len(excitations):
                    raise ValueError("quantity excitation count mismatch")
        inventory.append({"frequency_hz": frequency, "metadata_sha256": sha256(metadata_path),
                          "arrays_sha256": sha256(array_path), "quantities": quantities})
    return {"evidence": "predicted", "solve_kind": manifest.get("solve_kind"),
            "phasor_convention": manifest["phasor_convention"], "frequencies_hz": frequencies,
            "excitation_port_ids": excitations, "inventory": inventory}


def inspect_result(root: Path, request: SolveRequest, backend: str,
                   expected_output_ids: tuple[str, ...] | None = None) -> dict:
    try:
        return _inspect_result(root, request, backend, expected_output_ids)
    except (KeyError, TypeError, OSError, IndexError, zipfile.BadZipFile) as exc:
        raise ValueError(f"invalid or missing result artifact: {exc}") from exc


def _execute(command: list[str], cwd: Path, log: Path, timeout_s: float,
             stderr_log: Path | None = None) -> None:
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout must be positive and finite")
    options = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
    with ExitStack() as stack:
        stream = stack.enter_context(log.open("wb"))
        diagnostics = (stack.enter_context(stderr_log.open("wb"))
                       if stderr_log is not None else subprocess.STDOUT)
        process = subprocess.Popen(command, cwd=cwd, stdout=stream, stderr=diagnostics, **options)
        try:
            code = process.wait(timeout=timeout_s)
        except BaseException:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.poll() is None:
                process.kill()
            process.wait()
            raise
    if code:
        raise ValueError(f"Boundary Lab exited with code {code}; see {log.name}")


@dataclass(frozen=True)
class BoundaryLabRuntime:
    checkout: Path
    python: Path
    julia: Path
    backend: Literal["beat_cpu", "beat_cuda", "beat_rocm"] = "beat_cpu"

    def verify(self) -> dict:
        if self.backend not in {"beat_cpu", "beat_cuda", "beat_rocm"}:
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
        return {"revision": revision, "backend": self.backend, "python": environment["python"],
                "julia": julia_version, "packages": environment["packages"]}

    @_termination_guard()
    def solve(self, project: Path, request: SolveRequest, output: Path, *, timeout_s: float = 1800) -> dict:
        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("timeout must be positive and finite")
        project, output = Path(project).resolve(), Path(output).resolve()
        runtime = self.verify()
        project_hash = sha256(project)
        output.mkdir(parents=True, exist_ok=False)
        request_file = output / "request.json"
        _write_json(request_file, request.model_dump(mode="json"))
        started = time.monotonic()
        report = {"schema_version": 1, "status": "running", "runtime": runtime,
                  "started_at_utc": datetime.now(timezone.utc).isoformat(),
                  "project_sha256": project_hash, "request_sha256": sha256(request_file)}
        _write_json(output / "evaluation.json", report)
        base = [str(Path(self.python).absolute()), "-I", "-m", "blab.cli", "project"]
        common = [str(project), "--request", str(request_file), "--backend", self.backend,
                  "--julia-executable", str(Path(self.julia).absolute())]
        try:
            _execute(base + ["validate"] + common + ["--json"], Path(self.checkout),
                     output / "preflight.json", timeout_s, stderr_log=output / "preflight.stderr.log")
            preflight = _read_json(output / "preflight.json")
            if preflight.get("valid") is not True:
                raise ValueError("upstream preflight did not confirm validity")
            preflight_meshes = _mesh_inventory(preflight)
            expected_outputs = _output_ids(preflight.get("output_ids"))
            observations = _project_observation_ids(_read_json(project), request)
            if not observations.issubset(expected_outputs):
                raise ValueError("preflight omitted requested project observations")
            _execute(base + ["solve"] + common + ["--events", "ndjson", "--output", str(output / "upstream")],
                     Path(self.checkout), output / "solve.ndjson", timeout_s)
            result = inspect_result(output / "upstream", request, self.backend,
                                    expected_outputs)
            if sha256(project) != project_hash or sha256(request_file) != report["request_sha256"]:
                raise ValueError("project or request changed during evaluation")
            manifest = _read_json(output / "upstream/manifest.json")
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
            report.update(status="complete", result=result)
        except BaseException as exc:
            status = ("timed_out" if isinstance(exc, subprocess.TimeoutExpired) else
                      "cancelled" if isinstance(exc, KeyboardInterrupt) else "failed")
            report.update(status=status, error=f"{type(exc).__name__}: {exc}")
            raise
        finally:
            report["elapsed_s"] = time.monotonic() - started
            _write_json(output / "evaluation.json", report)
        return report
