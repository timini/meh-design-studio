"""Validation-only FP64 runner using the pinned external Boundary Lab API.

Run with Boundary Lab's Python environment. Production CLI solves use FP32 for
BEM; this keeps that fact explicit instead of silently changing their backend.
"""
import argparse
from dataclasses import replace
from pathlib import Path
import json
import subprocess
import sys
import importlib.metadata
import hashlib
import tempfile

def verify_julia(executable):
    path = str(Path(executable).absolute())
    version = subprocess.check_output([path, '--version'], text=True, timeout=30).strip()
    if version != 'julia version 1.12.6':
        raise ValueError('FP64 reference requires pinned Julia 1.12.6')
    return {'julia_executable': path, 'julia_version': version}


def python_identity():
    if sys.version_info[:2] != (3, 11):
        raise ValueError('FP64 reference requires the production Python 3.11 runtime')
    return {'python': sys.version, 'python_executable': sys.executable,
            'packages': sorted((d.metadata.get('Name', ''), d.version)
                               for d in importlib.metadata.distributions())}


def finish_failed_reference(session, writer, error):
    try:
        if session is not None:
            session.stop()
    except BaseException as cleanup_error:
        error.add_note(f'reference cleanup also failed: {cleanup_error}')
    finally:
        try:
            writer.finish(status='failed', error=str(error))
        except BaseException as report_error:
            error.add_note(f'failure report could not be finalized: {report_error}')


def request_snapshot(path, loader):
    payload = path.read_bytes()
    with tempfile.TemporaryDirectory(prefix='meh-reference-request-') as directory:
        snapshot = Path(directory)/'request.json'
        snapshot.write_bytes(payload)
        spec = loader(snapshot)
        if snapshot.read_bytes() != payload:
            raise ValueError('request snapshot changed during parsing')
    return spec, json.loads(payload), hashlib.sha256(payload).hexdigest()


def execute_reference(writer, output, runtime, request_path, request_digest, make_session, canonicalize):
    session = None
    try:
        runtime_payload = (json.dumps(runtime, indent=2) + '\n').encode()
        runtime_path = output/'runtime.json'
        runtime_path.write_bytes(runtime_payload)
        writer.manifest['reference_runtime'] = {
            'file':'runtime.json', 'sha256':hashlib.sha256(runtime_payload).hexdigest(), 'identity':runtime}
        writer.manifest['source_request_sha256'] = request_digest
        session = make_session()
        for result in session.solve_stream():
            writer.write_result(canonicalize(result))
        if hashlib.sha256(request_path.read_bytes()).hexdigest() != request_digest:
            raise ValueError('source request changed during reference solve')
        if runtime_path.read_bytes() != runtime_payload:
            raise ValueError('reference runtime evidence changed during solve')
        writer.finish(status='complete')
    except BaseException as exc:
        finish_failed_reference(session, writer, exc)
        raise


def main():
    import blab
    from blab.headless import load_headless_project, load_headless_solve_spec, prepare_headless_solve, HeadlessResultWriter
    from blab.system_solve import canonicalize_observation_result
    from blab.solvers.coupled_backend import CoupledReferenceBackend

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("request", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--julia", required=True)
    args = parser.parse_args()
    checkout = Path(blab.__file__).resolve().parents[2]
    revision = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    if revision != "8cb166226e412877d3f71f2845918e479b97aa85":
        raise ValueError("unsupported upstream revision")
    if subprocess.check_output(["git", "-C", str(checkout), "diff", "HEAD", "--name-only"], text=True).strip():
        raise ValueError("upstream tracked files have changed")
    julia_identity = verify_julia(args.julia)
    runtime_identity = {**julia_identity, **python_identity()}
    project = load_headless_project(args.project)
    spec, public_request, request_digest = request_snapshot(args.request, load_headless_solve_spec)
    prepared = prepare_headless_solve(project, spec, backend_id="beat_cpu")
    # Hold condensation fixed to compare numerical precision on the same formulation.
    request = replace(prepared.request, solver_options=dict(prepared.request.solver_options) | {"static_condensation": True})
    prepared = replace(prepared, request=request)
    writer = HeadlessResultWriter(args.output, project=project, prepared=prepared,
        backend_id="coupled_reference", public_request=public_request)
    execute_reference(writer, args.output, {"revision":revision, **runtime_identity},
        args.request, request_digest,
        lambda: CoupledReferenceBackend(julia_executable=args.julia, julia_threads="4",
            persistent_worker=False).create_system_session(request),
        lambda result: canonicalize_observation_result(prepared, result))
    print(json.dumps({"status": "complete", "backend": "coupled_reference", "precision": "float64",
                      "revision": revision, "runtime": runtime_identity, "output": str(args.output.resolve())}))


if __name__ == '__main__':
    main()
