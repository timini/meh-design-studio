"""Validation-only FP64 runner using the pinned external Boundary Lab API.

Run with Boundary Lab's Python environment. Production CLI solves use FP32 for
BEM; this keeps that fact explicit instead of silently changing their backend.
"""
import argparse
from dataclasses import replace
from pathlib import Path
import json
import subprocess

def verify_julia(executable):
    path = str(Path(executable).absolute())
    version = subprocess.check_output([path, '--version'], text=True, timeout=30).strip()
    if version != 'julia version 1.12.6':
        raise ValueError('FP64 reference requires pinned Julia 1.12.6')
    return {'julia_executable': path, 'julia_version': version}


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
    project = load_headless_project(args.project)
    spec = load_headless_solve_spec(args.request)
    prepared = prepare_headless_solve(project, spec, backend_id="beat_cpu")
    # Hold condensation fixed to compare numerical precision on the same formulation.
    request = replace(prepared.request, solver_options=dict(prepared.request.solver_options) | {"static_condensation": True})
    prepared = replace(prepared, request=request)
    writer = HeadlessResultWriter(args.output, project=project, prepared=prepared,
        backend_id="coupled_reference", public_request=json.loads(args.request.read_text()))
    (args.output / "runtime.json").write_text(json.dumps({"revision": revision, **julia_identity}, indent=2) + "\n", encoding="utf-8")
    backend = CoupledReferenceBackend(julia_executable=args.julia, julia_threads="4", persistent_worker=False)
    session = None
    try:
        session = backend.create_system_session(request)
        for result in session.solve_stream():
            writer.write_result(canonicalize_observation_result(prepared, result))
        writer.finish(status="complete")
    except BaseException as exc:
        if session is not None:
            session.stop()
        writer.finish(status="failed", error=str(exc))
        raise
    print(json.dumps({"status": "complete", "backend": "coupled_reference", "precision": "float64",
                      "revision": revision, "runtime": julia_identity, "output": str(args.output.resolve())}))


if __name__ == '__main__':
    main()
