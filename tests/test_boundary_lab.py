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
    values = np.array([[1+2j, 3-4j, 1j, 2j]], dtype=np.complex64)
    np.savez(root / "frequencies/000000.npz", q0000=values)
    metadata = {"freq_hz": 1000, "excitation_port_ids": ["voltage:a"], "arrays_file": "000000.npz",
                "quantities": [{"key": "q0000", "id": "acoustic:pressure:fem-nodes", "quantity": "fem_nodal_pressure", "unit": "Pa",
                                "target_id": "domain:fem-volume", "axes": ["excitation", "fem_node"], "shape": [1, 4], "dtype": "complex64",
                                "metadata": {"mesh_ids": ["mesh:a"], "region_ids": ["region:a"],
                                             "node_counts": [4], "node_offsets": [0]}}]}
    (root / "frequencies/000000.json").write_text(json.dumps(metadata), encoding="utf-8")
    manifest = {"schema": "boundary-lab-headless-result", "schema_version": 2, "status": "complete",
                "backend_id": "beat_cpu", "phasor_convention": "exp(-i omega t)",
                "frequencies_hz": [1000], "excitation_port_ids": ["voltage:a"],
                "completion_mask": [True], "solve_kind": "interior_fem",
                "results": [{"freq_hz": 1000, "metadata_file": "frequencies/000000.json",
                             "arrays_file": "frequencies/000000.npz"}]}
    source = root / "fixture.msh"
    source.write_text("$MeshFormat\n2.2 0 8\n$EndMeshFormat\n$Nodes\n4\n1 0 0 0\n2 1 0 0\n3 0 1 0\n4 0 0 1\n$EndNodes\n$Elements\n1\n1 4 2 1 1 1 2 3 4\n$EndElements\n")
    project = {"physical_system": {"meshes": [{"id": "mesh:a", "purpose": "fem_volume", "file": str(source)}],
        "regions": [{"id": "region:a", "kind": "bounded_air", "mesh_ids": ["mesh:a"], "volume_groups": [{"mesh_id":"mesh:a","tag":1}]}],
        "components": [], "excitation_ports": [{"id": "voltage:a"}]}}
    snapshot = root / "project.snapshot.blab.json"
    snapshot.write_text(json.dumps(project))
    np.savez(root / "domains.npz", points=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]), tetra=np.array([[0,1,2,3]]))
    (root / "domains.json").write_text(json.dumps({"domains": [{"id": "domain:fem-volume",
        "coordinates": {"points_m": "points"}, "topology": {"tetrahedra":"tetra"}, "metadata": {"tetra_counts":[1], "tetra_offsets":[0], "element_order":1,
            "mesh_ids": ["mesh:a"], "node_counts": [4]}}]}))
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
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu", ("acoustic:pressure:fem-nodes", "current"))
    assert inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu", ("acoustic:pressure:fem-nodes",))["evidence"] == "predicted"


@pytest.mark.parametrize("retain", [("bem_boundary_pressure",), ("bem_boundary_traces",)])
def test_requested_retained_fields_cannot_be_omitted_by_preflight(artifact, retain):
    root, _ = artifact
    with pytest.raises(ValueError, match="requested retained"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,), retain=retain), "beat_cpu", ("acoustic:pressure:fem-nodes",))


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
    project.write_bytes((root / "project.snapshot.blab.json").read_bytes())
    runtime = BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path / "julia")
    monkeypatch.setattr(BoundaryLabRuntime, "verify", lambda self: {"revision": "test"})
    calls = []
    def execute(command, cwd, log, timeout, **kwargs):
        calls.append(command)
        if "validate" in command:
            log.write_text(json.dumps({"valid": True, "solve_kind": "interior_fem", "output_ids": ["acoustic:pressure:fem-nodes"], "meshes": json.loads((root/"manifest.json").read_text())["meshes"]}), encoding="utf-8")
        else:
            shutil.copytree(root, output / "upstream")
    monkeypatch.setattr(adapter, "_execute", execute)
    with pytest.raises(ValueError):
        runtime.solve(project, SolveRequest(frequencies_hz=(1000,)), output)
    report = json.loads((output / "evaluation.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert len(calls) == 2
    assert "JSON compliant" in report["error"]


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
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu", ("acoustic:pressure:fem-nodes",))


@pytest.mark.parametrize("ids", [None, [], [""], [1], ["acoustic:pressure:fem-nodes", "acoustic:pressure:fem-nodes"]])
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


@pytest.mark.parametrize("output_ids", [["acoustic:radiation-impedance", "acoustic:radiation-impedance"], ["acoustic:radiation-impedance"]])
def test_preflight_contract_failure_stops_before_solver(tmp_path, monkeypatch, output_ids):
    import meh_studio.boundary_lab as adapter
    project = tmp_path / "project.json"
    mesh = tmp_path / "air.msh"
    mesh.write_bytes(b"test")
    project.write_text(json.dumps({"physical_system": {"regions": [{"kind":"unbounded_air"}], "meshes":[{"id":"air","file":str(mesh),"purpose":"fem_volume"}]}}))
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
    np.savez(root / "domains.npz", points=np.zeros((1,3)),tetra=np.array([[0,0,0,0]]))
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


def test_transducer_responses_cannot_be_omitted_consistently(artifact):
    root, manifest = artifact
    snapshot = root / manifest["project_file"]
    project = json.loads(snapshot.read_text())
    project["physical_system"]["components"] = [{"id": "driver", "kind": "electrodynamic_transducer"}]
    snapshot.write_text(json.dumps(project))
    manifest["project_sha256"] = sha256(snapshot)
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="mandatory project outputs"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu", ("acoustic:pressure:fem-nodes",))


def test_missing_automatic_outputs_stop_before_solver(artifact, tmp_path, monkeypatch):
    import meh_studio.boundary_lab as adapter
    root, manifest = artifact
    project = tmp_path / "project.json"
    payload = json.loads((root / manifest["project_file"]).read_text())
    payload["physical_system"]["components"] = [{"id": "driver", "kind": "electrodynamic_transducer"}]
    project.write_text(json.dumps(payload))
    calls = []
    def execute(command, cwd, log, timeout, **kwargs):
        calls.append(command)
        log.write_text(json.dumps({"valid":True,"solve_kind":"interior_fem", "meshes":manifest["meshes"],
                                  "output_ids":["acoustic:pressure:fem-nodes"]}))
    monkeypatch.setattr(adapter, "_execute", execute)
    monkeypatch.setattr(BoundaryLabRuntime, "verify", lambda self: {"revision":"test"})
    with pytest.raises(ValueError, match="mandatory project outputs"):
        BoundaryLabRuntime(tmp_path, Path(sys.executable), tmp_path/'julia').solve(
            project, SolveRequest(frequencies_hz=(1000,)), tmp_path/'evaluation')
    assert len(calls) == 1


def test_completed_evidence_hashes_domains_and_manifest(artifact):
    root, _ = artifact
    before = inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")
    assert before["artifact_hashes"] == {"manifest":sha256(root/'manifest.json'),
        "domains_metadata":sha256(root/'domains.json'), "domains_arrays":sha256(root/'domains.npz')}
    domain = json.loads((root/'domains.json').read_text())
    domain["archive_note"] = "changed after completion"
    (root/'domains.json').write_text(json.dumps(domain))
    after = inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")
    assert before["artifact_hashes"] != after["artifact_hashes"]


def test_domain_mutation_during_inspection_is_rejected(artifact, monkeypatch):
    import meh_studio.result_domains as domains
    root, _ = artifact
    original = domains.load_domains
    def mutate(*args,**kwargs):
        result = original(*args,**kwargs)
        path = root/'domains.json'
        path.write_text(path.read_text()+'\n')
        return result
    monkeypatch.setattr(domains, "load_domains", mutate)
    with pytest.raises(ValueError, match="changed during inspection"):
        inspect_result(root, SolveRequest(frequencies_hz=(1000,)), "beat_cpu")


def test_substitute_mesh_cannot_reuse_declared_identity(artifact):
    root,manifest = artifact
    original = Path(manifest['meshes'][0]['file'])
    substitute = root/'substitute.msh'
    substitute.write_bytes(original.read_bytes())
    manifest['meshes'][0]['file'] = str(substitute)
    (root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='project declaration'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


def test_relative_mesh_declarations_require_original_project_location(artifact):
    root,manifest = artifact
    path = root/manifest['project_file']
    project = json.loads(path.read_text())
    project['physical_system']['meshes'][0]['file'] = 'fixture.msh'
    path.write_text(json.dumps(project))
    manifest['project_sha256'] = sha256(path)
    (root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='original project path'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')
    assert inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu',project_path=path)['evidence'] == 'predicted'


@pytest.mark.parametrize('file',['frequencies/000000.json','frequencies/000000.npz'])
def test_frequency_artifact_mutation_during_inspection_fails(artifact,monkeypatch,file):
    import meh_studio.boundary_lab as adapter
    root,_ = artifact
    original = adapter._field_identity
    def mutate(*args):
        original(*args)
        path = root/file
        if file.endswith('.json'): path.write_text(path.read_text()+'\n')
        else: np.savez(path,q0000=np.zeros((1,2),dtype=np.complex64))
    monkeypatch.setattr(adapter,'_field_identity',mutate)
    with pytest.raises(ValueError,match='frequency artifacts changed'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


def test_coupled_run_cannot_omit_every_acoustic_output():
    from meh_studio.boundary_lab import _require_project_outputs
    system = {'components':[{'kind':'electrodynamic_transducer'}],
              'regions':[{'kind':'bounded_air'},{'kind':'unbounded_air'}]}
    ids = ['mechanical:diaphragm-velocity','electrical:voice-coil-current']
    with pytest.raises(ValueError,match='acoustic field'):
        _require_project_outputs(system,ids)
    _require_project_outputs(system,ids+['acoustic:pressure:fem-nodes'])


@pytest.mark.parametrize('exit_code',[0,7])
def test_parent_exit_cleans_up_residual_children(tmp_path,exit_code):
    import time
    child = "import sys,time;from pathlib import Path;root=Path(sys.argv[1]);(root/'ready').write_text('ready');time.sleep(1);(root/'survived').write_text('orphan')"
    parent = f"""
import subprocess,sys,time
from pathlib import Path
subprocess.Popen([sys.executable,'-c',{child!r},sys.argv[1]])
deadline=time.monotonic()+5
while not (Path(sys.argv[1])/'ready').exists():
    if time.monotonic()>deadline: raise RuntimeError('child did not start')
    time.sleep(.01)
raise SystemExit({exit_code})
"""
    command = [sys.executable,'-c',parent,str(tmp_path)]
    if exit_code:
        with pytest.raises(ValueError,match='code 7'): _execute(command,tmp_path,tmp_path/'process.log',10)
    else:
        _execute(command,tmp_path,tmp_path/'process.log',10)
    time.sleep(1.2)
    assert (tmp_path/'ready').exists() and not (tmp_path/'survived').exists()


@pytest.mark.parametrize('snapshot',['123 Z\n456 S\n','456 S\n'])
def test_darwin_empty_or_zombie_group_does_not_fail_cleanup(monkeypatch,snapshot):
    from meh_studio import boundary_lab as module
    monkeypatch.setattr(module.sys,'platform','darwin')
    monkeypatch.setattr(module.signal,'SIGKILL',9,raising=False)
    def denied(*_): raise PermissionError('simulated Darwin zombie-group EPERM')
    monkeypatch.setattr(module.os,'killpg',denied,raising=False)
    monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**k:snapshot)
    module._kill_process_group(123)


def test_darwin_live_child_permission_failure_is_not_hidden(monkeypatch):
    from meh_studio import boundary_lab as module
    monkeypatch.setattr(module.sys,'platform','darwin')
    monkeypatch.setattr(module.signal,'SIGKILL',9,raising=False)
    def denied(*_): raise PermissionError('live child')
    monkeypatch.setattr(module.os,'killpg',denied,raising=False)
    monkeypatch.setattr(module.subprocess,'check_output',lambda *a,**k:'123 Z\n123 S\n')
    with pytest.raises(PermissionError,match='live child'):
        module._kill_process_group(123)


@pytest.mark.skipif(sys.platform == 'win32',reason='POSIX signal guard')
def test_sigterm_immediately_after_running_write_records_cancelled(tmp_path,monkeypatch):
    from meh_studio import boundary_lab as a
    original = a._write_json
    def write(path,record):
        original(path,record)
        if record.get('status') == 'running':
            a.os.kill(a.os.getpid(),a.signal.SIGTERM)
    monkeypatch.setattr(a,'_write_json',write)
    runtime=BoundaryLabRuntime(tmp_path,Path(sys.executable),tmp_path/'julia')
    with pytest.raises(KeyboardInterrupt):
        runtime.solve(tmp_path/'project.json',SolveRequest(frequencies_hz=(1000,)),tmp_path/'output')
    assert json.loads((tmp_path/'output/evaluation.json').read_text())['status'] == 'cancelled'


@pytest.mark.parametrize('mutate',[False,True])
def test_preflight_contract_is_hashed_and_mutation_fails(artifact,tmp_path,monkeypatch,mutate):
    import shutil
    from meh_studio import boundary_lab as a
    root,manifest=artifact
    project=root/'project.snapshot.blab.json'
    output=tmp_path/'evaluation'
    monkeypatch.setattr(BoundaryLabRuntime,'verify',lambda self:{'revision':'test'})
    def execute(command,cwd,log,timeout,**kwargs):
        if 'validate' in command:
            log.write_text(json.dumps({'valid':True,'solve_kind':'interior_fem',
                'meshes':manifest['meshes'],'output_ids':['acoustic:pressure:fem-nodes']}))
        else:
            shutil.copytree(root,output/'upstream')
            if mutate: (output/'preflight.json').write_text('{}')
    monkeypatch.setattr(a,'_execute',execute)
    runtime=BoundaryLabRuntime(tmp_path,Path(sys.executable),tmp_path/'julia')
    if mutate:
        with pytest.raises(ValueError,match='preflight contract changed'):
            runtime.solve(project,SolveRequest(frequencies_hz=(1000,)),output)
        assert json.loads((output/'evaluation.json').read_text())['status'] == 'failed'
    else:
        report=runtime.solve(project,SolveRequest(frequencies_hz=(1000,)),output)
        assert report['preflight_sha256'] == sha256(output/'preflight.json')


@pytest.mark.parametrize('cells',[np.array([[0,1,3,2]]),np.array([[0,1,2,2]]),np.array([[0.,1.,2.,3.]])])
def test_fem_connectivity_must_match_hashed_source(artifact,cells):
    root,_=artifact
    with np.load(root/'domains.npz') as archive: points=archive['points']
    np.savez(root/'domains.npz',points=points,tetra=cells)
    with pytest.raises(ValueError,match='connectivity'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


def test_darwin_exiting_group_gets_bounded_reaping_grace(monkeypatch):
    from meh_studio import boundary_lab as a
    monkeypatch.setattr(a.sys,'platform','darwin')
    monkeypatch.setattr(a.signal,'SIGKILL',9,raising=False)
    def denied(*_): raise PermissionError('exiting')
    snapshots=iter(['123 E\n','123 Z\n'])
    monkeypatch.setattr(a.os,'killpg',denied,raising=False)
    monkeypatch.setattr(a.subprocess,'check_output',lambda *args,**kwargs:next(snapshots))
    monkeypatch.setattr(a.time,'sleep',lambda _:None)
    a._kill_process_group(123)


@pytest.mark.parametrize('corrupt',[False,True])
def test_quadratic_fem_connectivity_includes_midside_nodes(artifact,corrupt):
    import meshio
    root,manifest=artifact
    corners=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]])
    points=np.vstack((corners,[(corners[a]+corners[b])/2 for a,b in ((0,1),(1,2),(0,2),(0,3),(1,3),(2,3))]))
    source=Path(manifest['meshes'][0]['file'])
    meshio.write(source,meshio.Mesh(points,[('tetra10',np.arange(10)[None,:])],
        cell_data={'gmsh:physical':[np.array([1])],'gmsh:geometrical':[np.array([1])]}),file_format='gmsh22',binary=False)
    manifest['meshes'][0].update(sha256=sha256(source),size_bytes=source.stat().st_size)
    (root/'manifest.json').write_text(json.dumps(manifest))
    domain=json.loads((root/'domains.json').read_text())['domains'][0]
    domain['metadata'].update(element_order=2,node_counts=[10])
    domain['topology']['tetrahedra10']='quadratic'
    (root/'domains.json').write_text(json.dumps({'domains':[domain]}))
    cells=np.arange(10)[None,:]
    if corrupt: cells[0,4],cells[0,5]=cells[0,5],cells[0,4]
    np.savez(root/'domains.npz',points=points,tetra=np.arange(4)[None,:],quadratic=cells)
    path=root/'frequencies/000000.json';metadata=json.loads(path.read_text())
    metadata['quantities'][0]['shape']=[1,10]
    metadata['quantities'][0]['metadata']['node_counts']=[10]
    path.write_text(json.dumps(metadata))
    np.savez(root/'frequencies/000000.npz',q0000=np.ones((1,10),dtype=np.complex64))
    if corrupt:
        with pytest.raises(ValueError,match='quadratic FEM connectivity'):
            inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')
    else:
        assert inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')['evidence'] == 'predicted'


@pytest.mark.parametrize('signum',[2,15])
@pytest.mark.skipif(sys.platform == 'win32',reason='POSIX signal delivery')
def test_cancellation_during_directory_creation_records_owned_output(tmp_path,monkeypatch,signum):
    from meh_studio import boundary_lab as a
    output=tmp_path/'output';mkdir=Path.mkdir
    def interrupted(path,*args,**kwargs):
        mkdir(path,*args,**kwargs)
        if path == output: a.signal.raise_signal(signum)
    monkeypatch.setattr(Path,'mkdir',interrupted)
    runtime=BoundaryLabRuntime(tmp_path,Path(sys.executable),tmp_path/'julia')
    with pytest.raises(a.EvaluationCancelled):
        runtime.solve(tmp_path/'project.json',SolveRequest(frequencies_hz=(1000,)),output)
    assert json.loads((output/'evaluation.json').read_text())['status'] == 'cancelled'


@pytest.mark.parametrize('signum',[2,15])
@pytest.mark.parametrize('fail',[False,True])
@pytest.mark.skipif(sys.platform == 'win32',reason='POSIX signal delivery')
def test_terminal_report_commits_despite_new_cancellation(artifact,tmp_path,monkeypatch,signum,fail):
    import shutil
    from meh_studio import boundary_lab as a
    root,manifest=artifact;output=tmp_path/'evaluation'
    monkeypatch.setattr(BoundaryLabRuntime,'verify',lambda self:{'revision':'test'})
    original=a._write_json
    def write(path,report):
        if report.get('status') in {'complete','failed'}:
            a.signal.raise_signal(signum)
            a.signal.raise_signal(signum)
        original(path,report)
    monkeypatch.setattr(a,'_write_json',write)
    def execute(command,cwd,log,timeout,**kwargs):
        if fail: raise ValueError('solver failure')
        if 'validate' in command:
            log.write_text(json.dumps({'valid':True,'solve_kind':'interior_fem',
                'meshes':manifest['meshes'],'output_ids':['acoustic:pressure:fem-nodes']}))
        else: shutil.copytree(root,output/'upstream')
    monkeypatch.setattr(a,'_execute',execute)
    runtime=BoundaryLabRuntime(tmp_path,Path(sys.executable),tmp_path/'julia')
    def solve(): return runtime.solve(root/'project.snapshot.blab.json',SolveRequest(frequencies_hz=(1000,)),output)
    if fail:
        with pytest.raises(ValueError,match='solver failure'): solve()
    else: solve()
    assert json.loads((output/'evaluation.json').read_text())['status'] == ('failed' if fail else 'complete')


def test_float_bem_connectivity_is_rejected(tmp_path):
    import meshio
    from meh_studio.result_domains import load_domains
    points=np.array([[0.,0.,0.],[1.,0.,0.],[0.,1.,0.]])
    source=tmp_path/'source.msh'
    meshio.write(source,meshio.Mesh(points,[('triangle',np.array([[0,1,2]]))]),file_format='gmsh22',binary=False)
    np.savez(tmp_path/'domains.npz',points=points,triangles=np.array([[0.,1.,2.]]))
    (tmp_path/'domains.json').write_text(json.dumps({'domains':[{'id':'domain:bem-boundary',
        'coordinates':{'points_m':'points'},'topology':{'triangles':'triangles'},
        'metadata':{'mesh_ids':['mesh:a'],'node_counts':[3]}}]}))
    (tmp_path/'project.json').write_text('{}')
    manifest={'project_file':'project.json','domains_metadata_file':'domains.json','domains_file':'domains.npz'}
    system={'meshes':[{'id':'mesh:a'}]}
    meshes={'mesh:a':{'file':str(source),'purpose':'bem_surface','sha256':sha256(source)}}
    with pytest.raises(ValueError,match='face count'):
        load_domains(tmp_path,manifest,system,meshes)


@pytest.mark.skipif(sys.platform == 'win32',reason='POSIX signal delivery')
def test_cancellation_while_classifying_failure_cannot_leave_running(tmp_path,monkeypatch):
    import builtins
    from meh_studio import boundary_lab as a
    def failure(self): raise ValueError('original failure')
    monkeypatch.setattr(BoundaryLabRuntime,'verify',failure)
    def classify(value,kind):
        if kind is subprocess.TimeoutExpired: a.signal.raise_signal(a.signal.SIGTERM)
        return builtins.isinstance(value,kind)
    monkeypatch.setattr(a,'isinstance',classify,raising=False)
    runtime=BoundaryLabRuntime(tmp_path,Path(sys.executable),tmp_path/'julia')
    with pytest.raises(a.EvaluationCancelled):
        runtime.solve(tmp_path/'project.json',SolveRequest(frequencies_hz=(1000,)),tmp_path/'output')
    assert json.loads((tmp_path/'output/evaluation.json').read_text())['status'] == 'cancelled'


@pytest.mark.parametrize('payload',[[],None,'text',3,True])
def test_nonobject_manifest_is_a_validation_error(artifact,payload):
    root,_=artifact
    (root/'manifest.json').write_text(json.dumps(payload))
    with pytest.raises(ValueError,match='root must be an object'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


def test_unknown_output_identity_cannot_publish_known_quantity(artifact):
    root,_=artifact;path=root/'frequencies/000000.json'
    metadata=json.loads(path.read_text());metadata['quantities'][0]['id']='unknown:pressure'
    path.write_text(json.dumps(metadata))
    with pytest.raises(ValueError):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu',('unknown:pressure',))


@pytest.mark.parametrize('signum',[2,15])
@pytest.mark.skipif(sys.platform == 'win32',reason='POSIX signal lifecycle')
def test_cancellation_inside_popen_cleans_up_new_child(tmp_path,monkeypatch,signum):
    from meh_studio import boundary_lab as a
    real_popen=subprocess.Popen;children=[]
    def interrupted(*args,**kwargs):
        child=real_popen(*args,**kwargs);children.append(child)
        a.signal.raise_signal(signum)
        return child
    monkeypatch.setattr(a.subprocess,'Popen',interrupted)
    report={'status':'running'}
    with pytest.raises(a.EvaluationCancelled):
        with a._termination_guard(report) as activate:
            activate()
            a._execute([sys.executable,'-c','import time;time.sleep(30)'],tmp_path,tmp_path/'log',10)
    assert len(children)==1 and children[0].poll() is not None


@pytest.mark.parametrize('unsupported_tag',[1,2])
def test_selected_non_tetrahedral_volume_is_not_silently_dropped(artifact,unsupported_tag):
    import meshio
    root,manifest=artifact;source=Path(manifest['meshes'][0]['file'])
    raw=meshio.read(source)
    meshio.write(source,meshio.Mesh(raw.points,[('tetra',np.array([[0,1,2,3]])),
        ('hexahedron',np.array([[0,1,2,3,0,1,2,3]]))],
        cell_data={'gmsh:physical':[np.array([1]),np.array([unsupported_tag])],
                   'gmsh:geometrical':[np.array([1]),np.array([2])]}),file_format='gmsh22',binary=False)
    manifest['meshes'][0].update(sha256=sha256(source),size_bytes=source.stat().st_size)
    (root/'manifest.json').write_text(json.dumps(manifest))
    if unsupported_tag == 1:
        with pytest.raises(ValueError,match='non-tetrahedral'):
            inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')
    else:
        assert inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')['evidence']=='predicted'


def test_multi_mesh_region_remains_explicitly_unsupported_by_pinned_runtime(artifact):
    root,manifest=artifact;path=root/manifest['project_file'];project=json.loads(path.read_text())
    project['physical_system']['regions'][0]['mesh_ids'].append('mesh:other')
    path.write_text(json.dumps(project));manifest['project_sha256']=sha256(path)
    (root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='pinned Boundary Lab requires one FEM mesh'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


@pytest.mark.parametrize('signum,code',[(2,130),(15,143),(None,130)])
def test_cli_returns_structured_cancellation(tmp_path,monkeypatch,capsys,signum,code):
    from meh_studio.boundary_lab import EvaluationCancelled
    from meh_studio.cli import main
    request=tmp_path/'request.json';request.write_text(SolveRequest(frequencies_hz=(1000,)).model_dump_json())
    def cancel(*args,**kwargs):raise EvaluationCancelled('cancelled test',signum=signum)
    monkeypatch.setattr(BoundaryLabRuntime,'solve',cancel)
    result=main(['solve-project',str(tmp_path/'project.json'),'--request',str(request),
        '--checkout',str(tmp_path),'--python',sys.executable,'--julia','julia','--output',str(tmp_path/'output')])
    assert result==code
    assert json.loads(capsys.readouterr().err)=={'status':'cancelled','error':'cancelled test'}


@pytest.mark.parametrize('kind',['exterior_bem','coupled_bem_fem'])
def test_standalone_inspection_derives_topology_from_saved_project(artifact,kind):
    root,manifest=artifact;manifest['solve_kind']=kind
    (root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='saved project topology'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


@pytest.mark.parametrize('field',['coordinates','topology','metadata'])
@pytest.mark.parametrize('value',[[],None,'bad'])
def test_nested_domain_mappings_are_required_objects(artifact,field,value):
    root,_=artifact;path=root/'domains.json';document=json.loads(path.read_text())
    document['domains'][0][field]=value;path.write_text(json.dumps(document))
    with pytest.raises(ValueError,match='must be objects'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


def test_snapshot_changed_after_verification_cannot_complete(artifact,monkeypatch):
    from meh_studio import result_domains as d
    root,_=artifact;original=d.load_domains
    def mutate(*args,**kwargs):
        result=original(*args,**kwargs)
        (root/'project.snapshot.blab.json').write_text('{}')
        return result
    monkeypatch.setattr(d,'load_domains',mutate)
    with pytest.raises(ValueError,match='snapshot changed'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


def test_deep_artifact_json_is_structured_validation_failure(artifact):
    root,_=artifact;(root/'manifest.json').write_text('{"nested":'+'['*10000+'0'+']'*10000+'}')
    with pytest.raises(ValueError):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


def test_json_decoder_recursion_is_normalized(tmp_path,monkeypatch):
    from meh_studio import boundary_lab as a
    path=tmp_path/'document.json';path.write_text('{}')
    def fail(*args,**kwargs):raise RecursionError('decoder depth')
    with monkeypatch.context() as patch:
        patch.setattr(a.json,'loads',fail)
        with pytest.raises(ValueError,match='nesting limit'):a._read_json(path)


def test_source_mesh_changed_after_domain_read_is_rejected(artifact,monkeypatch):
    from meh_studio import result_domains as d
    root,manifest=artifact;original=d.load_domains
    def mutate(*args,**kwargs):
        result=original(*args,**kwargs)
        path=Path(manifest['meshes'][0]['file']);path.write_bytes(path.read_bytes()+b'\n')
        return result
    monkeypatch.setattr(d,'load_domains',mutate)
    with pytest.raises(ValueError,match='source mesh changed during inspection'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


@pytest.mark.parametrize('filename',['domains.npz','frequencies/000000.npz'])
def test_empty_numpy_artifacts_are_validation_errors(artifact,filename):
    root,_=artifact;(root/filename).write_bytes(b'')
    with pytest.raises(ValueError):inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'beat_cpu')


@pytest.mark.parametrize('signum',[2,15])
@pytest.mark.skipif(sys.platform=='win32',reason='POSIX child-group cancellation')
def test_first_signal_during_group_cleanup_does_not_leave_child(tmp_path,monkeypatch,signum):
    import time
    from meh_studio import boundary_lab as a
    original=a._kill_process_group
    def interrupted(pgid):
        a.signal.raise_signal(signum)
        original(pgid)
    monkeypatch.setattr(a,'_kill_process_group',interrupted)
    child="import time;from pathlib import Path;Path('ready').write_text('yes');time.sleep(1);Path('survived').write_text('bad')"
    parent=f"import subprocess,sys,time;from pathlib import Path;subprocess.Popen([sys.executable,'-c',{child!r}]);\nwhile not Path('ready').exists():time.sleep(.01)"
    with pytest.raises(a.EvaluationCancelled):
        with a._termination_guard({'status':'running'}) as activate:
            activate()
            a._execute([sys.executable,'-c',parent],tmp_path,tmp_path/'log',10)
    time.sleep(1.1)
    assert not (tmp_path/'survived').exists()


def test_missing_retained_output_stops_after_preflight(artifact,tmp_path,monkeypatch):
    from meh_studio import boundary_lab as a
    root,manifest=artifact;calls=[]
    monkeypatch.setattr(BoundaryLabRuntime,'verify',lambda self:{'revision':'test'})
    def execute(command,cwd,log,timeout,**kwargs):
        calls.append(command)
        log.write_text(json.dumps({'valid':True,'solve_kind':'interior_fem','meshes':manifest['meshes'],
            'output_ids':['acoustic:pressure:fem-nodes']}))
    monkeypatch.setattr(a,'_execute',execute)
    runtime=BoundaryLabRuntime(tmp_path,Path(sys.executable),tmp_path/'julia')
    with pytest.raises(ValueError,match='preflight omitted requested retained'):
        runtime.solve(root/'project.snapshot.blab.json',SolveRequest(frequencies_hz=(1000,),retain=('bem_boundary_traces',)),tmp_path/'out')
    assert len(calls)==1 and 'validate' in calls[0]


def test_standalone_inspection_requires_declared_observation_outputs(artifact):
    root,manifest=artifact;path=root/manifest['project_file'];project=json.loads(path.read_text())
    project['observation_planes']=[{'type':'exterior'}]
    path.write_text(json.dumps(project));manifest['project_sha256']=sha256(path)
    (root/'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='requested project observations'):
        inspect_result(root,SolveRequest(frequencies_hz=(1000,),include_project_observations=True),'beat_cpu')


@pytest.mark.parametrize('threads', [0, 65, True, 1.5])
def test_invalid_julia_thread_count_fails_before_runtime_probes(tmp_path, threads):
    runtime=BoundaryLabRuntime(tmp_path,Path(sys.executable),tmp_path/'julia',julia_threads=threads)
    with pytest.raises(ValueError,match='thread count'):
        runtime.verify()


def test_explicit_julia_thread_count_reaches_only_solve_command(artifact, tmp_path, monkeypatch):
    import shutil
    import meh_studio.boundary_lab as adapter
    root,manifest=artifact
    project=root/'project.snapshot.blab.json';output=tmp_path/'out'
    monkeypatch.setattr(BoundaryLabRuntime,'verify',lambda self:{'julia_threads':self.julia_threads})
    commands=[]
    def execute(command,*args,**kwargs):
        commands.append(command)
        if 'validate' in command:
            assert '--julia-threads' not in command
            (output/'preflight.json').write_text(json.dumps({'valid':True,'solve_kind':'interior_fem',
                'meshes':manifest['meshes'],'output_ids':['acoustic:pressure:fem-nodes']}))
        else: shutil.copytree(root,output/'upstream')
    monkeypatch.setattr(adapter,'_execute',execute)
    runtime=BoundaryLabRuntime(tmp_path,Path(sys.executable),tmp_path/'julia',julia_threads=1)
    runtime.solve(project,SolveRequest(frequencies_hz=(1000,)),output)
    index=commands[1].index('--julia-threads')
    assert commands[1][index+1]=='1'


def reference_artifact(artifact, *, dtype='complex128'):
    from meh_studio.boundary_lab import BOUNDARY_LAB_REVISION
    root, manifest = artifact
    manifest['backend_id'] = 'coupled_reference'
    runtime = {'revision': BOUNDARY_LAB_REVISION}
    (root/'runtime.json').write_text(json.dumps(runtime))
    manifest['reference_runtime'] = {'file':'runtime.json',
        'sha256':sha256(root/'runtime.json'), 'identity':runtime}
    with np.load(root/'frequencies/000000.npz') as arrays:
        values = arrays['q0000'].astype(dtype)
    np.savez(root/'frequencies/000000.npz', q0000=values)
    path = root/'frequencies/000000.json'
    metadata = json.loads(path.read_text())
    metadata['quantities'][0]['dtype'] = dtype
    path.write_text(json.dumps(metadata))
    (root/'manifest.json').write_text(json.dumps(manifest))
    return root, manifest


@pytest.mark.parametrize('fault',[None,'complex64','runtime_changed'])
def test_reference_precision_and_runtime_artifacts(artifact, fault):
    root, manifest = reference_artifact(artifact, dtype='complex64' if fault=='complex64' else 'complex128')
    if fault == 'runtime_changed':
        (root/'runtime.json').write_text('{}')
    if fault:
        with pytest.raises(ValueError, match='complex128|runtime evidence'):
            inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'coupled_reference')
    else:
        result=inspect_result(root,SolveRequest(frequencies_hz=(1000,)),'coupled_reference')
        assert result['artifact_hashes']['reference_runtime'] == manifest['reference_runtime']['sha256']
        assert result['evidence'] == 'predicted'


@pytest.mark.parametrize('fault',[None,'runner_identity','wrong_topology'])
def test_reference_adapter_uses_separate_runner_and_retains_identity(artifact,tmp_path,monkeypatch,fault):
    import shutil
    import meh_studio.boundary_lab as adapter
    root,manifest=reference_artifact(artifact)
    kind='interior_fem' if fault=='wrong_topology' else 'coupled_bem_fem'
    # This test exercises dispatch/identity. The native integration uses real coupled CAD.
    monkeypatch.setattr(adapter,'_project_solve_kind',lambda project:kind)
    manifest['solve_kind']=kind
    runner=Path(adapter.__file__).with_name('native_reference.py')
    runtime_identity={'backend':'coupled_reference','reference_runner_sha256':sha256(runner)}
    monkeypatch.setattr(BoundaryLabRuntime,'verify',lambda self:runtime_identity)
    output=tmp_path/'reference-output';commands=[]
    def execute(command,*args,**kwargs):
        commands.append(command)
        if 'validate' in command:
            assert command[command.index('--backend')+1]=='beat_cpu'
            (output/'preflight.json').write_text(json.dumps({'valid':True,'solve_kind':kind,
                'meshes':manifest['meshes'],'output_ids':['acoustic:pressure:fem-nodes']}))
        else:
            assert command[:3] == [str(Path(sys.executable).absolute()),'-I',str(runner.resolve())]
            assert command[-2:] == ['--julia-threads','2']
            assert kwargs['stderr_log'] == output/'solve.stderr.log'
            manifest['reference_runner_sha256']='changed' if fault=='runner_identity' else sha256(runner)
            manifest['source_request_sha256']=sha256(output/'request.json')
            (root/'manifest.json').write_text(json.dumps(manifest))
            shutil.copytree(root,output/'upstream')
    monkeypatch.setattr(adapter,'_execute',execute)
    runtime=BoundaryLabRuntime(tmp_path,Path(sys.executable),tmp_path/'julia','coupled_reference',2)
    if fault:
        with pytest.raises(ValueError,match='runner or request|requires a coupled'):
            runtime.solve(root/'project.snapshot.blab.json',SolveRequest(frequencies_hz=(1000,)),output)
        assert json.loads((output/'evaluation.json').read_text())['status']=='failed'
    else:
        result=runtime.solve(root/'project.snapshot.blab.json',SolveRequest(frequencies_hz=(1000,)),output)
        assert result['status']=='complete'
        assert result['runtime']==runtime_identity
    assert len(commands)==(1 if fault=='wrong_topology' else 2)
