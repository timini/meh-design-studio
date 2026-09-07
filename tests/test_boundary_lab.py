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
                "quantities": [{"key": "q0000", "id": "pressure", "quantity": "fem_nodal_pressure", "unit": "Pa",
                                "target_id": "domain:fem-volume", "axes": ["excitation", "fem_node"], "shape": [1, 2], "dtype": "complex64",
                                "metadata": {"mesh_ids": ["mesh:a"], "region_ids": ["region:a"],
                                             "node_counts": [2], "node_offsets": [0]}}]}
    (root / "frequencies/000000.json").write_text(json.dumps(metadata), encoding="utf-8")
    manifest = {"schema": "boundary-lab-headless-result", "schema_version": 2, "status": "complete",
                "backend_id": "beat_cpu", "phasor_convention": "exp(-i omega t)",
                "frequencies_hz": [1000], "excitation_port_ids": ["voltage:a"],
                "completion_mask": [True], "solve_kind": "interior_fem",
                "results": [{"freq_hz": 1000, "metadata_file": "frequencies/000000.json",
                             "arrays_file": "frequencies/000000.npz"}]}
    source = root / "fixture.msh"
    source.write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$Nodes\n2\n1 0 0 0\n2 0 0 1\n$EndNodes\n$Elements\n0\n$EndElements\n")
    project = {"physical_system": {"meshes": [{"id": "mesh:a", "purpose": "fem_volume"}],
        "regions": [{"id": "region:a", "kind": "bounded_air", "mesh_ids": ["mesh:a"]}],
        "components": [], "excitation_ports": [{"id": "voltage:a"}]}}
    snapshot = root / "project.snapshot.blab.json"
    snapshot.write_text(json.dumps(project))
    np.savez(root / "domains.npz", points=np.array([[0.,0.,0.],[0.,0.,1.]]))
    (root / "domains.json").write_text(json.dumps({"domains": [{"id": "domain:fem-volume",
        "coordinates": {"points_m": "points"}, "topology": {}, "metadata": {
            "mesh_ids": ["mesh:a"], "node_counts": [2]}}]}))
    manifest.update(domains_file="domains.npz", domains_metadata_file="domains.json", project_file=snapshot.name, project_sha256=sha256(snapshot), meshes=[{
        "id": "mesh:a", "file": str(source), "purpose": "fem_volume", "sha256": sha256(source),
        "size_bytes": source.stat().st_size}])
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


def test_missing_runtime_records_initialization_failure(tmp_path):
    runtime = BoundaryLabRuntime(tmp_path / "missing", Path(sys.executable), tmp_path / "julia")
    with pytest.raises(subprocess.CalledProcessError):
        runtime.solve(tmp_path / "project.json", SolveRequest(frequencies_hz=(1000,)), tmp_path / "output")
    assert json.loads((tmp_path / "output/evaluation.json").read_text())["status"] == "failed"


def test_failed_solve_records_failure_and_does_not_reuse_output(tmp_path, monkeypatch):
    import meh_studio.boundary_lab as adapter
    runtime = BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path / "julia")
    monkeypatch.setattr(BoundaryLabRuntime, "verify", lambda self: {"revision": "test-double"})
    def fail(*args, **kwargs):
        raise ValueError("test preflight failed")
    monkeypatch.setattr(adapter, "_execute", fail)
    project, output = tmp_path / "project.json", tmp_path / "output"
    project.write_text('{}', encoding="utf-8")
    with pytest.raises(ValueError, match="preflight"):
        runtime.solve(project, SolveRequest(frequencies_hz=(1000,)), output)
    assert json.loads((output / "evaluation.json").read_text())["status"] == "failed"
    with pytest.raises(FileExistsError):
        runtime.solve(project, SolveRequest(frequencies_hz=(1000,)), output)


@pytest.mark.parametrize("fault", ["revision", "dirty", "module", "julia", "python"])
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
            return json.dumps({"module": str(module), "python": "test", "python_version": [3, 12] if fault == "python" else [3, 11], "packages": {}})
        return "julia version 1.10.12" if fault == "julia" else "julia version 1.12.6"
    monkeypatch.setattr(subprocess, "check_output", check_output)
    with pytest.raises(ValueError):
        runtime.verify()


def test_timeout_status_is_distinct_from_numerical_failure(tmp_path, monkeypatch):
    import meh_studio.boundary_lab as adapter
    runtime = BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path / "julia")
    monkeypatch.setattr(BoundaryLabRuntime, "verify", lambda self: {"revision": "test-double"})
    def timeout(*args, **kwargs):
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


@pytest.mark.parametrize("retain", [("bem_boundary_pressure",), ("bem_boundary_traces",)])
def test_requested_retained_fields_cannot_be_omitted_by_preflight(artifact, retain):
    root, _ = artifact
    with pytest.raises(ValueError, match="requested retained"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,), retain=retain), "beat_cpu", ("pressure",))


@pytest.mark.parametrize("unit,name", [("A", "fem_nodal_pressure"), ("Pa", "voice_coil_current"),
    ("Pa", "bem_boundary_neumann"), ("Pa", "unknown")])
def test_units_follow_quantity_contract(artifact, unit, name):
    root, _ = artifact
    path = root / "frequencies/000000.json"
    metadata = json.loads(path.read_text())
    metadata["quantities"][0].update(unit=unit, quantity=name)
    path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="unit"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nested_nonfinite_metadata_rejected(artifact, value):
    root, _ = artifact
    path = root / "frequencies/000000.json"
    metadata = json.loads(path.read_text())
    metadata["quantities"][0]["metadata"] = {"nested": [{"value": value}]}
    path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


@pytest.mark.parametrize("meshes", [None, [], [None], [{}],
    [{"id": "m", "file": "/mesh", "purpose": "fem", "sha256": "x", "size_bytes": 1}]])
def test_mesh_inventory_cannot_be_missing_or_malformed(meshes):
    from meh_studio.boundary_lab import _mesh_inventory
    with pytest.raises(ValueError):
        _mesh_inventory({"meshes": meshes})


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX SIGTERM lifecycle")
def test_sigterm_cancels_report_and_kills_solver_group(tmp_path):
    import os
    import signal
    import time
    # Launch an actual adapter process with only the upstream runtime replaced.
    script = tmp_path / "adapter.py"
    script.write_text('''
import sys
from pathlib import Path
import meh_studio.boundary_lab as a
root=Path(sys.argv[1])
a.BoundaryLabRuntime.verify=lambda self: {"revision":"test"}
execute=a._execute
child="import os,time;from pathlib import Path;Path('ready').write_text(str(os.getpid()));time.sleep(2);Path('survived').write_text('bad');time.sleep(60)"
a._execute=lambda command,cwd,log,timeout,**kwargs: execute([sys.executable,"-c",child],root,log,timeout)
(root/'project.json').write_text('{}')
a.BoundaryLabRuntime(root,Path(sys.executable),root/'julia').solve(root/'project.json',a.SolveRequest(frequencies_hz=(1000,)),root/'output')
''', encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(script), str(tmp_path)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "ready").exists() and time.monotonic() < deadline:
            assert process.poll() is None
            time.sleep(.02)
        assert (tmp_path / "ready").exists()
        os.kill(process.pid, signal.SIGTERM)
        process.wait(timeout=10)
        report = json.loads((tmp_path / "output/evaluation.json").read_text())
        assert report["status"] == "cancelled"
        time.sleep(2.2)
        assert not (tmp_path / "survived").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()


def test_nonfinite_result_metadata_records_failed_evaluation(artifact, tmp_path, monkeypatch):
    import shutil
    import meh_studio.boundary_lab as adapter
    root, _ = artifact
    metadata_file = root / "frequencies/000000.json"
    data = json.loads(metadata_file.read_text())
    data["quantities"][0]["metadata"] = {"invalid": [float("nan")]}
    metadata_file.write_text(json.dumps(data), encoding="utf-8")
    source = tmp_path / "source.msh"
    source.write_bytes(b"mesh fixture")
    mesh = {"id": "mesh:a", "file": str(source), "purpose": "fem_volume",
            "sha256": sha256(source), "size_bytes": source.stat().st_size}
    output, project = tmp_path / "evaluation", tmp_path / "project.json"
    project.write_text('{}', encoding="utf-8")
    runtime = BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path / "julia")
    monkeypatch.setattr(BoundaryLabRuntime, "verify", lambda self: {"revision": "test"})
    def execute(command, cwd, log, timeout, **kwargs):
        if "validate" in command:
            log.write_text(json.dumps({"valid": True, "output_ids": ["pressure"], "meshes": [mesh]}), encoding="utf-8")
        else:
            shutil.copytree(root, output / "upstream")
    monkeypatch.setattr(adapter, "_execute", execute)
    with pytest.raises(ValueError):
        runtime.solve(project, SolveRequest(frequencies_hz=(1000,)), output)
    report = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"


@pytest.mark.parametrize("dtype", ["float64", "int64", "bool"])
def test_self_consistent_real_arrays_cannot_replace_phasors(artifact, dtype):
    root, _ = artifact
    path = root / "frequencies/000000.json"
    metadata = json.loads(path.read_text())
    metadata["quantities"][0]["dtype"] = dtype
    path.write_text(json.dumps(metadata), encoding="utf-8")
    np.savez(root / "frequencies/000000.npz", q0000=np.array([[1, 2]], dtype=dtype))
    with pytest.raises(ValueError, match="quantity array"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


@pytest.mark.parametrize("axes", [["row", "node"], ["excitation", "excitation"]])
def test_response_requires_unique_excitation_axis(artifact, axes):
    root, _ = artifact
    path = root / "frequencies/000000.json"
    metadata = json.loads(path.read_text())
    metadata["quantities"][0]["axes"] = axes
    path.write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(ValueError, match="ax"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


def test_duplicate_output_identity_with_distinct_storage_keys_rejected(artifact):
    root, _ = artifact
    path = root / "frequencies/000000.json"
    metadata = json.loads(path.read_text())
    metadata["quantities"].append(metadata["quantities"][0] | {"key": "q0001"})
    path.write_text(json.dumps(metadata), encoding="utf-8")
    values = np.array([[1+2j, 3-4j]], dtype=np.complex64)
    np.savez(root / "frequencies/000000.npz", q0000=values, q0001=values)
    with pytest.raises(ValueError, match="output IDs"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu", ("pressure",))


@pytest.mark.parametrize("ids", [None, [], [""], [1], ["pressure", "pressure"]])
def test_invalid_compiled_output_ids(ids):
    from meh_studio.boundary_lab import _output_ids
    with pytest.raises(ValueError, match="output IDs"):
        _output_ids(ids)


def test_preflight_stderr_is_retained_without_corrupting_json(tmp_path):
    output, diagnostics = tmp_path / "preflight.json", tmp_path / "preflight.stderr.log"
    _execute([sys.executable, "-c", "import sys;print('{}');print('warning',file=sys.stderr)"],
             tmp_path, output, 10, stderr_log=diagnostics)
    assert json.loads(output.read_text()) == {}
    assert diagnostics.read_text().strip() == "warning"


def test_distinct_frequencies_cannot_reuse_array_artifact(artifact):
    root, manifest = artifact
    manifest.update(frequencies_hz=[1000, 2000], completion_mask=[True, True])
    manifest["results"].append(manifest["results"][0] | {
        "freq_hz": 2000, "metadata_file": "frequencies/000001.json"})
    metadata = json.loads((root / "frequencies/000000.json").read_text())
    metadata["freq_hz"] = 2000
    (root / "frequencies/000001.json").write_text(json.dumps(metadata), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="distinct array"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000, 2000)), "beat_cpu")


def test_observation_requirements_come_from_project():
    from meh_studio.boundary_lab import _project_observation_ids
    project = {"physical_system": {"regions": [{"kind": "unbounded_air"}]},
               "observation_planes": [{"type": "combined"}]}
    request = SolveRequest(frequencies_hz=(1000,), include_project_observations=True)
    assert _project_observation_ids(project, request) == {
        "ui:exterior-pressure", "acoustic:pressure:fem-nodes",
        "acoustic:pressure:bem-boundary", "acoustic:normal-derivative:bem-boundary"}


@pytest.mark.parametrize("output_ids", [["pressure", "pressure"], ["pressure"]])
def test_preflight_contract_failure_stops_before_solver(tmp_path, monkeypatch, output_ids):
    import meh_studio.boundary_lab as adapter
    project = tmp_path / "project.json"
    project.write_text(json.dumps({"physical_system": {"regions": [{"kind": "unbounded_air"}]}}))
    mesh = tmp_path / "air.msh"
    mesh.write_bytes(b"test")
    calls = []
    def execute(command, cwd, log, timeout, **kwargs):
        calls.append(command)
        log.write_text(json.dumps({"valid": True, "solve_kind": "exterior_bem", "output_ids": output_ids, "meshes": [{
            "id": "air", "file": str(mesh), "purpose": "fem_volume", "sha256": sha256(mesh),
            "size_bytes": mesh.stat().st_size}]}))
    monkeypatch.setattr(adapter, "_execute", execute)
    monkeypatch.setattr(BoundaryLabRuntime, "verify", lambda self: {"revision": "test"})
    runtime = BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path / "julia")
    with pytest.raises(ValueError, match="output IDs|observations"):
        runtime.solve(project, SolveRequest(frequencies_hz=(1000,), include_project_observations=True),
                      tmp_path / "output")
    assert len(calls) == 1
    assert json.loads((tmp_path / "output/evaluation.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("patch", [
    {"axes": ["excitation", "transducer"]},
    {"metadata": {"mesh_ids": ["m"], "region_ids": ["r"], "node_counts": [3], "node_offsets": [0]}},
    {"metadata": {"mesh_ids": ["m"], "region_ids": ["r"], "node_counts": [2], "node_offsets": [1]}},
    {"metadata": {}},
])
def test_field_axes_and_mesh_inventory_are_required(artifact, patch):
    root, _ = artifact
    path = root / "frequencies/000000.json"
    metadata = json.loads(path.read_text())
    metadata["quantities"][0].update(patch)
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


@pytest.mark.parametrize("kind", [None, "unknown", "exterior_bem"])
def test_solve_kind_matches_expected_topology(artifact, kind):
    root, manifest = artifact
    manifest["solve_kind"] = kind
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="solve kind"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu", expected_solve_kind="interior_fem")


@pytest.mark.parametrize("name,axes,shape", [
    ("radiation_impedance", [], ()), ("radiation_impedance", ["radiator"], (0,)),
    ("fem_nodal_pressure", ["excitation", "fem_node"], (1, 0)),
    ("diaphragm_velocity", ["excitation", "transducer"], (1, 2)),
])
def test_empty_or_unindexed_physical_dimensions_fail(name, axes, shape):
    from meh_studio.boundary_lab import _quantity_dimensions
    with pytest.raises(ValueError):
        _quantity_dimensions({"quantity": name, "axes": axes}, np.zeros(shape, dtype=complex), 1)


@pytest.mark.parametrize("sphere", [False, True])
def test_compiled_polar_block_expands_to_saved_output_contract(sphere):
    from meh_studio.boundary_lab import _result_output_ids
    project = {"project_preferences": {"spherical_sampling_enabled": sphere}}
    ids = _result_output_ids(project, ("ui:exterior-pressure", "mechanical:diaphragm-velocity"))
    assert set(ids) == {"mechanical:diaphragm-velocity", "acoustic:pressure:horizontal-polar",
                        "acoustic:pressure:vertical-polar"} | ({"acoustic:pressure:sphere"} if sphere else set())


@pytest.mark.parametrize("patch", [{"mesh_ids": ["mesh:absent"]}, {"region_ids": ["region:absent"]}])
def test_field_identities_must_belong_to_solved_project(artifact, patch):
    root, _ = artifact
    path = root / "frequencies/000000.json"
    metadata = json.loads(path.read_text())
    metadata["quantities"][0]["metadata"].update(patch)
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match="identities"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


def test_omitted_project_excitation_cannot_appear_complete(artifact):
    root, manifest = artifact
    path = root / "project.snapshot.blab.json"
    project = json.loads(path.read_text())
    project["physical_system"]["excitation_ports"].append({"id": "voltage:b"})
    path.write_text(json.dumps(project))
    manifest["project_sha256"] = sha256(path)
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="excitation basis"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


def test_frequency_axis_contract_cannot_change(artifact):
    root, manifest = artifact
    metadata = json.loads((root / "frequencies/000000.json").read_text())
    metadata.update(freq_hz=2000, arrays_file="000001.npz")
    metadata["quantities"][0].update(shape=[1, 3])
    metadata["quantities"][0]["metadata"]["node_counts"] = [3]
    np.savez(root / "frequencies/000001.npz", q0000=np.ones((1,3), dtype=np.complex64))
    (root / "frequencies/000001.json").write_text(json.dumps(metadata))
    manifest.update(frequencies_hz=[1000,2000], completion_mask=[True,True])
    manifest["results"].append({"freq_hz":2000,"metadata_file":"frequencies/000001.json","arrays_file":"frequencies/000001.npz"})
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="changed across|physical domain|source mesh"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,2000)), "beat_cpu")


def test_cancellation_during_runtime_verification_is_recorded(tmp_path, monkeypatch):
    from meh_studio.boundary_lab import EvaluationCancelled
    def cancel(self):
        raise EvaluationCancelled("verification interrupted")
    monkeypatch.setattr(BoundaryLabRuntime, "verify", cancel)
    with pytest.raises(EvaluationCancelled):
        BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path/'julia').solve(
            tmp_path/'project.json', SolveRequest(frequencies_hz=(1000,)), tmp_path/'output')
    assert json.loads((tmp_path/'output/evaluation.json').read_text())["status"] == "cancelled"


def test_self_consistent_truncation_cannot_override_source_mesh(artifact):
    root, _ = artifact
    path = root / "frequencies/000000.json"
    metadata = json.loads(path.read_text())
    metadata["quantities"][0].update(shape=[1,1])
    metadata["quantities"][0]["metadata"]["node_counts"] = [1]
    path.write_text(json.dumps(metadata))
    np.savez(root / "frequencies/000000.npz", q0000=np.ones((1,1), dtype=np.complex64))
    domain = json.loads((root / "domains.json").read_text())
    domain["domains"][0]["metadata"]["node_counts"] = [1]
    (root / "domains.json").write_text(json.dumps(domain))
    np.savez(root / "domains.npz", points=np.zeros((1,3)))
    with pytest.raises(ValueError, match="hashed source mesh"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


def test_background_thread_rejection_leaves_no_running_evaluation(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    if sys.platform == "win32": pytest.skip("POSIX signal thread guard")
    runtime = BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path/'julia')
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(runtime.solve, tmp_path/'project', SolveRequest(frequencies_hz=(1000,)), tmp_path/'output')
        with pytest.raises(ValueError, match="worker process"):
            future.result()
    assert not (tmp_path/'output').exists()


@pytest.mark.parametrize("target,count", [(None,73), ("observation:vertical-polar",73), ("observation:horizontal-polar",1)])
def test_observation_grid_identity_and_count_are_required(target, count):
    from meh_studio.result_domains import check_quantity_domain
    q = {"quantity":"exterior_pressure", "id":"acoustic:pressure:horizontal-polar", "target_id":target}
    domains = {"observation:horizontal-polar": {"coordinates": {"points_m":np.zeros((73,3))}}}
    with pytest.raises(ValueError):
        check_quantity_domain(q, np.zeros((1,count),dtype=complex), domains)


def test_radiator_order_is_bound_to_project_components(tmp_path):
    from meh_studio.result_domains import load_domains
    (tmp_path/'domains.json').write_text(json.dumps({"domains":[{"id":"components:radiators", "coordinates":{"component_id":"ids"}, "topology":{}, "metadata":{}}]}))
    np.savez(tmp_path/'domains.npz', ids=np.array(['b','a']))
    (tmp_path/"project.json").write_text("{}")
    manifest = {"domains_metadata_file":"domains.json", "domains_file":"domains.npz", "project_file":"project.json"}
    system = {"components":[{"id":"a"},{"id":"b"}],"meshes":[]}
    with pytest.raises(ValueError, match="component identities"):
        load_domains(tmp_path, manifest, system, {})
