# Boundary Lab adapter

This increment implements the headless integration part of A02. It runs a separately installed, pinned Boundary Lab checkout and preserves its complex result files. It does not generate MEH geometry or establish physical accuracy.

## Runtime contract

Supported source revision: `8cb166226e412877d3f71f2845918e479b97aa85`. The initial runtime is Python 3.11 with Julia **1.12.6**, matching the upstream Julia manifest. The real execution evidence is for `beat_cpu` on macOS ARM64. Explicit CUDA/ROCm selections exist in the adapter but have not been exercised or qualified here.

The adapter checks the Git revision, rejects tracked source modifications, verifies that the configured Python is version 3.11 and imports this checkout, and checks the Julia version. It records Python dependency versions. This is runtime identity checking, not a fully reproducible binary distribution: operating-system libraries, hardware and all dependency artifacts are not locked by the adapter. Untracked files and environment variables are not a sandbox; run trusted local installations only.

An initial attempt to instantiate the pinned dependencies with Julia 1.10.12 exposed precompilation incompatibilities. Julia 1.12.6 compiled and ran successfully. The adapter now rejects the mismatched version before launching a solve.

## Setup and run

Install this repository as described in the README. Install Boundary Lab in a separate environment following its [headless workflow](https://github.com/JWSound/boundary-lab/blob/8cb166226e412877d3f71f2845918e479b97aa85/docs/advanced/cli-workflow.md), using the pinned revision. The minimal sequence below assumes Git, Python 3.11 and Julia 1.12.6 are already available. Substitute your platform's virtual-environment executable paths; Windows uses `Scripts/python.exe`.

```sh
git clone https://github.com/JWSound/boundary-lab.git boundary-lab
git -C boundary-lab checkout 8cb166226e412877d3f71f2845918e479b97aa85
python3.11 -m venv boundary-lab-env
boundary-lab-env/bin/python -m pip install -e boundary-lab
julia --project=boundary-lab/src/blab/solvers/julia_local -e 'using Pkg; Pkg.instantiate()'
```

From the MEH repository, with the paths above adjusted to their actual locations:

```sh
meh solve-project /path/to/boundary-lab/examples/compression_driver/compression_driver.blab.json \
  --request examples/solver-smoke-request.json \
  --checkout /path/to/boundary-lab \
  --python /path/to/boundary-lab-env/bin/python \
  --julia /path/to/julia-1.12.6/bin/julia \
  --backend beat_cpu \
  --output runs/compression-driver-check \
  --timeout-per-stage-s 600
```

The output directory must be new. `--timeout-per-stage-s` applies separately to preflight and solve; it is not a total optimisation budget. Runtime probes have their own 30-second limits. A custom `JULIA_DEPOT_PATH` may be inherited by the process to keep downloaded Julia dependencies local to a workspace. First execution can include precompilation and is not a representative steady-state timing.

The request contract currently supports an explicit increasing frequency vector, project-observation inclusion and retained field selections. Arbitrary probe overlays, excitation-subset selection and solver options are future adapter extensions. The upstream tool has broader capabilities than this initial product contract.

## Durable outputs and failure handling

Each evaluation retains:

- `request.json`: normalised immutable request.
- `preflight.json`: upstream validation output, including mesh hashes and expected quantities.
- `solve.ndjson`: process progress and diagnostic output; stderr is retained in the same log, so consumers must not assume every line is JSON.
- `upstream/`: untouched project snapshot, compiled physical system, result domains, frequency metadata and NPZ arrays.
- `evaluation.json`: atomic adapter state, runtime identity, input hashes, elapsed time, completion/evidence status and per-frequency result hashes, and hashes of the verified manifest and result-domain files.

Required driver-current and diaphragm-velocity outputs are derived independently from the project’s electrodynamic components. The adapter verifies the complete frequency grid and mask, excitation axis, compiled output IDs, every explicitly requested retained field, quantity-specific units, shapes, data types and finite numerical values throughout arrays and metadata. A nonempty mesh inventory with well-formed identities is mandatory. Referenced result files must remain inside their directories. The project, request, source mesh hashes and runtime must remain unchanged across evaluation. No amplitude or phase alignment is fitted, and no DSP synthesis or pressure-to-SPL/power conversion occurs. The raw upstream excitation normalisation is preserved in the upstream physical-system artifacts and implementation conventions; do not assume a 1 V response or an RMS/peak conversion without a separately established convention.

Every process exit cleans up residual solver children, including successful and nonzero parent exits. Windows launches children suspended, assigns them to a kill-on-close Job Object, then resumes execution; POSIX uses a dedicated process group. A timeout terminates that group and leaves an explicit `timed_out` report. On POSIX, SIGTERM installs a cancellation path that stops the solver group and records `cancelled`; the synchronous adapter must run in the main thread of its worker process. Keyboard interruption also records `cancelled`; other failures record `failed`. Partial upstream arrays remain available for diagnosis. They cannot acquire a successful `complete` result. An existing evaluation is never overwritten. Automatic resume, scheduling and resource/memory prediction remain future work.

## Executed evidence

The [machine-readable integration report](../validation/reports/boundary-lab-integration.json) records two real runs of the upstream compression-driver fixture:

| Run | Frequencies | Observed wall time |
| --- | --- | --- |
| Initial single-frequency run | 1,000 Hz | 45.13 seconds |
| Subsequent three-frequency run | 500, 1,000 and 2,000 Hz | 20.60 seconds |

Both retained complex pressure at 1,665 FEM nodes, diaphragm velocity and voice-coil current. The shared 1 kHz arrays agreed exactly in these executions. This is a repeatability/integration observation, not an independent accuracy test. Timing includes process startup and some compilation effects; no peak-memory or scaling claim is made.

The fixture couples front and rear chambers to one electrodynamic diaphragm and uses a tube termination. It is **interior FEM**, not an exterior FEM/BEM MEH. Full coupled radiation, generated geometry, mesh convergence, source-model transfer and physical measurements remain outstanding. G0 is not passed by this increment.

Input meshes and upstream design files are referenced at the pinned source, not redistributed in this repository. The local ignored `runs/` directory retains the full outputs; the checked-in report contains hashes, metadata, repeat differences and selected numerical results so the acquisition can be repeated without bundling upstream geometry.

Result inspection binds each mesh to the original project declaration, including its resolved path, size and hash. When project mesh paths are relative, callers must supply the original `project_path` to `inspect_result`; the copied snapshot cannot establish that location. Frequency metadata and arrays are hashed before inspection and checked again before publication. Coupled requests must explicitly retain an acoustic field or enable project observations; electrical and mechanical outputs alone cannot complete a coupled evaluation.
