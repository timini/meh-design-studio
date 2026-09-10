# Implementation status

Merged increments now include the foundation, geometry generator, durable job ledger and initial complex metric library. These implement parts of B01/B02/B04/B05 and independent-reference infrastructure for A05. It does **not** pass G0 or any physical release gate. A01's example brief is provisional; its measurement protocol has not been ratified. The pinned Boundary Lab CPU solver has now executed the interior compression-driver fixture at one and three frequencies; see the [adapter and evidence](boundary-lab-adapter.md). This demonstrates integration and repeatability, not independent acoustic accuracy. The experimental search now also executes generated multiple-entry FEM/BEM evaluations; see [the end-to-end workflow](end-to-end-search.md).

The generated interior experiment now connects synthetic three-source geometry to FEM and includes an 8-to-4 mm mesh sensitivity study, independent electrical consistency checks, and a uniform-tube analytic load comparison. See [generated-system evidence](generated-system.md). These remain experimental numerical results with no free-field, band or physical qualification.

The [complete compact native experiment](end-to-end-evidence.md) now passes its analytic-reference, held-out improvement and mesh-stability gates. Its 1–4 kHz result is an executed numerical demonstration with archived raw evidence and STEP/STL/3MF exports; physical qualification and broader product requirements remain open.

## Current wide-mid implementation

The maintainer's clarified target is an inexpensive, Solana-inspired freeform MEH
with approximately 350 Hz handover to X1/HD15 bass/kicks and a wide vocal midrange.
The [completion contract](completion-workflow.md) records the requested shared
2-ohm-capable amplifier bank, higher HF crossover and later diyAudio project post.

The shared geometry now supports a four-driver ring plus throat and smooth
non-circular/asymmetric lofts. Both have completed native five-source FEM/BEM
experiments, with archived full fields, induced inactive-driver motion and polars.
See [ring evidence](coupled-ring-evidence.md) and [freeform evidence](freeform-waveguides.md).
Those are three-frequency topology demonstrations, not target-band qualification.

[Adaptive search](adaptive-search.md) mutates profile and geometry controls using
preceding simulated fitness, with periodic random exploration, bound checks and
verified ancestral evidence. [Wide-mid objectives](wide-mid-objectives.md) add
LR4 crossover/polarity/delay selection, H/V coverage scoring and full coupled
parallel-bank impedance. Finalists freeze the DSP and compare raw complex
pressures across the sampled coverage sectors. Commercial source calibration,
full-band numerical convergence, comparable measured performance, manufacturing
qualification and an actual finished affordable design remain open.

## R1 requested horn experiment

The [240–3000 Hz R1 prototype](../designs/240hz-3khz-four-driver/README.md) now has archived print geometry, a four-entry front-air domain, tagged meshes and an executed prescribed-flow FEM diagnostic with an independent tube check. A 17-point sweep and three mesh levels retain numerical failures: the 3 kHz complex-transfer stability screen fails the unchanged 10% limit even at the 10-to-7.5 mm comparison (10.208%). This is internal mean pressure with local mouth impedance, not exterior radiation or a commercial-driver response. Actual driver/source coupling, rear loads, radiation and physical qualification remain open; R1 has not achieved its acoustic target.

## Available

- `meh resume-optimise` continues stopped searches using saved inputs and verified completed trials. It preserves the original evidence and retries incomplete trials; partial solver sweeps, abrupt-death recovery and total lifetime compute accounting remain open. See [search recovery](end-to-end-search.md#continue-a-stopped-search).

- Durable SQLite job leases, cancellation, one automatic recovery retry, bounded completion descriptors and integrity-checked publication. An isolated CAD worker is accessible through `meh jobs` with managed input snapshots, cancellation, retry and verified result retrieval; dependency-aware scheduling and full search/solver orchestration through durable workers remain to implement.
- Explicit RMS complex source synthesis, signed real electrical power, pressure-level null handling and full-sphere pressure quadrature. Native-solver amplitude calibration and evaluation-to-metrics integration remain to implement.

- Input snapshot library with bounded dependency copies, portable content identities and verification against queued job input digests. See [input snapshots](input-snapshots.md). CAD worker execution is connected; automatic dependency discovery and solver snapshots remain to implement.
- Pinned Boundary Lab subprocess adapter, preflight, explicit backend/runtime checks, preserved complex output, timeout/failure reports and result integrity checks.

- Immutable, versioned SI contracts for briefs, source models, driver records, provenance and declared band/mounting/level qualification; canonical content hashes.
- Explicit dry moving mass and source-data validation. Synthetic records cannot qualify. A declared qualification is user-supplied metadata, not independently verified evidence.
- Private SQLite catalogue import/list with immutable revisions, idempotent insertion, conflict rejection, read-only access and content-integrity checking. Original synthetic driver fixtures are bundled for experiments; no qualified commercial catalogue is claimed.
- Independent rigid-box modal reference and coupled linear driver circuit reference with explicit RMS/phase/load conventions. Circuit tests cover known resonant impedance, mutual motion, reciprocity, power conservation and complex superposition.
- Headless commands, regression tests and a Linux/macOS/Windows CI matrix for Python 3.11/3.14.

- A repeatable [experimental build-bundle exporter](search-build-bundle.md) packages a completed search with verified geometry, driver BOM, fixed gains and source identities. Manufacturing interfaces and two-slicer/physical qualification remain open (B06).

## Commands

```sh
meh validate-brief examples/reference-brief.json
meh cavity-reference --lengths-m 0.47 0.33 0.22 --max-hz 1000
meh catalogue init my-private-drivers.sqlite
meh catalogue add my-private-drivers.sqlite my-driver-record.json
meh catalogue list my-private-drivers.sqlite
```

Record structure is defined by `DriverRevision` in `src/meh_studio/domain.py`; `model_json_schema()` exposes its JSON schema. Driver geometry records use actual outer and cutout dimensions in metres, not a rounded commercial size. Eligibility requires an explicit operating level, tested SPL range, identical measurement distance and identical signal/protocol definition. No distance scaling or signal equivalence is inferred; the SPL evidence applies only to the named mounting fixture and does not establish amplifier voltage limits or full-system summed output. Source parameters are a minimal complete linear circuit, not a substitute for measured high-frequency transfer behaviour. Per-parameter provenance, offers, user-overlay composition and automatic evidence verification remain to implement.

The circuit accepts a prescribed mechanical load matrix in N·s/m. It does not derive that matrix from geometry. Zero voltage means a connected, zero-voltage source, not an open circuit. Loaded response must never be presented as a 3D horn simulation. The cavity command emits reference values without claiming a solver comparison passed.

## Next reviewable increments

1. Extend the executed adapter to generated geometry and full FEM/BEM radiation; establish independent acoustic accuracy and source normalisation checks (remaining A02/A05).
2. Connect durable jobs to isolated CAD/solver workers with cancellation, input snapshots, resource accounting and restart tests (remaining B04).
3. Complete generated geometry/source convergence comparisons and connect trusted evaluations to metrics with explicit amplitude calibration (A05/B03–B05).
4. Extend the experimental bounded search beyond straight conical geometry and relative ripple, integrate manufacturing constraints and qualified driver data, and complete measured qualification gates in the plan.

Physical source/load acquisition, actual builds, calibrated measurements and rights-cleared catalogue release remain external evidence work. Reference tests passing cannot mark those items complete.

Each meaningful increment uses one review round. Address material findings, verify
the fixes and merge under the maintainer’s standing authorisation when relevant
checks pass. Routine fixes and evidence updates do not require another review or
fresh approval on every commit. Defer non-blocking polish and speculative hardening.
An unavailable automated reviewer does not create an indefinite merge block; inspect
the change directly and record the limitation. See [repository working instructions](../AGENTS.md).
