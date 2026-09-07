import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from meh_studio.boundary_lab import BoundaryLabRuntime, SolveRequest, _execute, inspect_result, sha256


@pytest.fixture
def artifact(tmp_path):
    root = tmp_path / "upstream"
    root.mkdir()
    (root / "frequencies").mkdir()
    values = np.array([[1+2j, 3-4j]], dtype=np.complex64)
    np.savez(root / "frequencies/000000.npz", q0000=values)
    metadata = {"freq_hz": 1000, "excitation_port_ids": ["voltage:a"], "arrays_file": "000000.npz",
                "quantities": [{"key": "q0000", "id": "pressure", "unit": "Pa",
                                "axes": ["excitation", "node"], "shape": [1, 2], "dtype": "complex64"}]}
    (root / "frequencies/000000.json").write_text(json.dumps(metadata), encoding="utf-8")
    manifest = {"schema": "boundary-lab-headless-result", "schema_version": 2, "status": "complete",
                "backend_id": "beat_cpu", "phasor_convention": "exp(-i omega t)",
                "frequencies_hz": [1000], "excitation_port_ids": ["voltage:a"],
                "completion_mask": [True], "solve_kind": "interior_fem",
                "results": [{"freq_hz": 1000, "metadata_file": "frequencies/000000.json",
                             "arrays_file": "frequencies/000000.npz"}]}
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return root, manifest


def test_complete_complex_result_is_only_a_prediction(artifact):
    root, _ = artifact
    report = inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")
    assert report["evidence"] == "predicted"
    assert report["inventory"][0]["arrays_sha256"] == sha256(root / "frequencies/000000.npz")
    with np.load(root / "frequencies/000000.npz") as values:
        assert values["q0000"][0, 1] == 3-4j


@pytest.mark.parametrize("patch", [
    {"status": "running"}, {"completion_mask": [False]}, {"completion_mask": [1]},
    {"frequencies_hz": [999]}, {"backend_id": "beat_cuda"}, {"schema_version": 1},
    {"phasor_convention": "exp(+i omega t)"}, {"results": [None]},
    {"excitation_port_ids": []}, {"results": []},
])
def test_incomplete_or_incompatible_artifacts_fail(artifact, patch):
    root, manifest = artifact
    (root / "manifest.json").write_text(json.dumps(manifest | patch), encoding="utf-8")
    with pytest.raises(ValueError):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


def test_missing_and_escaping_files_are_rejected(artifact):
    root, manifest = artifact
    outside = root.parent / "outside.json"
    outside.write_text('{}', encoding="utf-8")
    manifest["results"][0]["metadata_file"] = "../outside.json"
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


@pytest.mark.parametrize("values", [np.array([[np.nan+1j, 3]], dtype=np.complex64),
                                  np.array([[1+2j]], dtype=np.complex64),
                                  np.array([[1, 2]], dtype=np.float64)])
def test_nonfinite_wrong_shape_or_dtype_fail(artifact, values):
    root, _ = artifact
    np.savez(root / "frequencies/000000.npz", q0000=values)
    with pytest.raises(ValueError):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


@pytest.mark.parametrize("frequencies", [(), (1000, 500), (1000, 1000), (True,), (float("inf"),)])
def test_invalid_request(frequencies):
    with pytest.raises(ValueError):
        SolveRequest(frequencies_hz=frequencies)


def test_process_failures_and_timeouts_retain_logs(tmp_path):
    log = tmp_path / "process.log"
    with pytest.raises(ValueError, match="code 7"):
        _execute([sys.executable, "-c", "print('diagnostic',flush=True);raise SystemExit(7)"],
                 tmp_path, log, 10)
    assert "diagnostic" in log.read_text(encoding="utf-8")
    with pytest.raises(subprocess.TimeoutExpired):
        _execute([sys.executable, "-c", "import time;time.sleep(30)"], tmp_path, log, .1)


def test_missing_runtime_fails_before_output_creation(tmp_path):
    runtime = BoundaryLabRuntime(tmp_path / "missing", Path(sys.executable), tmp_path / "julia")
    with pytest.raises(subprocess.CalledProcessError):
        runtime.solve(tmp_path / "project.json", SolveRequest(frequencies_hz=(1000,)), tmp_path / "output")
    assert not (tmp_path / "output").exists()


def test_failed_solve_records_failure_and_does_not_reuse_output(tmp_path, monkeypatch):
    import meh_studio.boundary_lab as adapter
    runtime = BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path / "julia")
    monkeypatch.setattr(BoundaryLabRuntime, "verify", lambda self: {"revision": "test-double"})
    def fail(*args):
        raise ValueError("test preflight failed")
    monkeypatch.setattr(adapter, "_execute", fail)
    project, output = tmp_path / "project.json", tmp_path / "output"
    project.write_text('{}', encoding="utf-8")
    with pytest.raises(ValueError, match="preflight"):
        runtime.solve(project, SolveRequest(frequencies_hz=(1000,)), output)
    assert json.loads((output / "evaluation.json").read_text())["status"] == "failed"
    with pytest.raises(FileExistsError):
        runtime.solve(project, SolveRequest(frequencies_hz=(1000,)), output)


@pytest.mark.parametrize("fault", ["revision", "dirty", "module", "julia"])
def test_runtime_identity_checks_reject_mismatches(tmp_path, monkeypatch, fault):
    import meh_studio.boundary_lab as adapter
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    runtime = BoundaryLabRuntime(checkout, tmp_path / "venv/python", tmp_path / "julia")
    def check_output(command, **kwargs):
        if command[0] == "git":
            if "rev-parse" in command:
                return "wrong" if fault == "revision" else adapter.BOUNDARY_LAB_REVISION
            return "src/blab/changed.py" if fault == "dirty" else ""
        if "-I" in command:
            module = tmp_path / "elsewhere/blab/__init__.py" if fault == "module" else checkout / "src/blab/__init__.py"
            return json.dumps({"module": str(module), "python": "test", "packages": {}})
        return "julia version 1.10.12" if fault == "julia" else "julia version 1.12.6"
    monkeypatch.setattr(subprocess, "check_output", check_output)
    with pytest.raises(ValueError):
        runtime.verify()


def test_timeout_status_is_distinct_from_numerical_failure(tmp_path, monkeypatch):
    import meh_studio.boundary_lab as adapter
    runtime = BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path / "julia")
    monkeypatch.setattr(BoundaryLabRuntime, "verify", lambda self: {"revision": "test-double"})
    def timeout(*args):
        raise subprocess.TimeoutExpired("test", .1)
    monkeypatch.setattr(adapter, "_execute", timeout)
    project = tmp_path / "project.json"
    project.write_text('{}', encoding="utf-8")
    with pytest.raises(subprocess.TimeoutExpired):
        runtime.solve(project, SolveRequest(frequencies_hz=(1000,)), tmp_path / "output")
    result = json.loads((tmp_path / "output/evaluation.json").read_text(encoding="utf-8"))
    assert result["status"] == "timed_out"


def test_missing_compiled_output_is_rejected(artifact):
    root, _ = artifact
    with pytest.raises(ValueError, match="compiled output contract"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu", ("pressure", "current"))
    assert inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu", ("pressure",))["evidence"] == "predicted"
