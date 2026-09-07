# Implementation status

The foundation PR implements parts of B01 and the independent-reference infrastructure for A05. It does **not** pass G0 or any physical release gate. A01's example brief is provisional; its measurement protocol has not been ratified. No upstream acoustic solver has been run by this implementation.

## Available

- Input snapshot library with bounded dependency copies, portable content identities and verification against queued job input digests. See [input snapshots](input-snapshots.md). Worker execution and automatic dependency discovery remain to implement.

- Immutable, versioned SI contracts for briefs, source models, driver records, provenance and declared band/mounting/level qualification; canonical content hashes.
- Explicit dry moving mass and source-data validation. Synthetic records cannot qualify. A declared qualification is user-supplied metadata, not independently verified evidence.
- Private SQLite catalogue import/list with immutable revisions, idempotent insertion, conflict rejection, read-only access and content-integrity checking. No bundled driver data is claimed.
- Independent rigid-box modal reference and coupled linear driver circuit reference with explicit RMS/phase/load conventions. Circuit tests cover known resonant impedance, mutual motion, reciprocity, power conservation and complex superposition.
- Headless commands, regression tests and a Linux/macOS/Windows CI matrix for Python 3.11/3.14.

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

1. Boundary Lab pinned adapter and executed headless validation/solve; archive full upstream result conventions and failure states (A02).
2. Single-origin horn geometry with real source boundary tags, print solids and generated mesh validation (A04/B02).
3. Generated geometry/source coupling, independent-oracle and mesh convergence comparisons; durable evaluations and metrics (A05/B03–B05).
4. Supported mixed-variable search and manufacturing export, followed by measured qualification gates in the plan.

Physical source/load acquisition, actual builds, calibrated measurements and rights-cleared catalogue release remain external evidence work. Reference tests passing cannot mark those items complete.

Each increment is proposed through a pull request. Wait for review, address feedback and require passing checks plus approval before merging. A successful test run alone is not review approval.
