# Implementation plan

7 September 2026 · Proposed baseline · Implementation has not begun

## Delivery approach

Deliver one measured, reproducible MEH pipeline first, then automate broader searches. The first decision is whether we have a sufficiently accurate source/load model at an affordable solve cost. Catalogue breadth and UI polish follow that decision.

Use three core roles: acoustics/numerics (AN), geometry/manufacturing (GM), application/optimisation (AO), with measurement/data support (MD) and product owner (PO). Assign actual people at kickoff. Roles below indicate accountability, not existing staffing. The sequence is approximately 24–32 weeks if procurement and specialist access align; the full programme has not been costed by suppliers. See [feasibility assumptions](feasibility-report.md).

## Target architecture and boundaries

Python owns domain contracts, catalogue, scheduling, optimisation and metrics. Parametric CadQuery geometry produces both air domains and material solids. Gmsh builds semantically tagged analysis meshes. A versioned adapter compiles a physical system and talks to a pinned Boundary Lab headless process. SQLite tracks durable jobs and catalogue revisions; immutable array files retain complex solver results. Evaluate the upstream desktop UI before creating a separate UI surface.

Implement these as packages in one repository initially, with separate worker processes for CAD/solver isolation. They are proposed modules, not existing folders:

| Module | Contract and responsibility |
| --- | --- |
| `domain` | Versioned briefs, driver revisions, candidates, geometry/evaluation/build manifests; SI conversion and immutable identity |
| `catalogue` | Read-only bundled pack plus user overlay; provenance, capability/band filtering and price snapshots |
| `geometry` | Supported family generators, driver placement, chambers/ports, boundary tags and build solids |
| `solver` | Adapter, capability checks, protocol translation, excitation normalisation, raw arrays and diagnostics |
| `metrics` | Complex summation, angular weighting, real-power accounting, uncertainty and validity-aware constraints |
| `jobs` | Durable queue, resource limits, atomic completion, retry/cancel/resume and cache dependencies |
| `search` | Discrete family/model/count selection, continuous geometry/DSP search, fidelity promotion and Pareto archive |
| `manufacturing` | Segmentation, joints, fit checks, export and assembled-geometry comparison |
| `ui` / `cli` | Brief, catalogue, progress, comparison and build workflows over the same application service |
| `validation` | Independent references, fixture manifests, acquisition protocols and evidence reports |

Adapter calls must return complex pressure, current and motion with coordinate axes and source normalisation. Retain every driver's response to every excitation, including nominally inactive drivers. Keep DSP recombination separate from changes to physical termination. Preserve Mmd/Mms distinctions and prevent duplicate rear loads. The [PRD](product-requirements.md) contains detailed functional contracts; the [upstream evidence review](research/upstream-review.md) identifies where pin-specific tests are required.

Use canonical input serialisation and content hashes. Price-only changes invalidate cost scoring; DSP-only changes may reuse fixed-system transfer bases; source/load/geometry changes invalidate acoustic evaluation. Solver build, precision, frequency grid, medium, boundary conventions and meshing all belong in the evaluation identity.

## Phase A — feasibility, weeks 1–4

| Work ID | Owner | Depends on | Deliverable and exit evidence |
| --- | --- | --- | --- |
| A01 | PO/AN | None | Freeze first brief, validated band/levels, supported family, compute ceiling, protocol v1 and decision thresholds |
| A02 | AO/AN | A01 | Pin upstream, record environment/dependencies and capabilities; run a headless source/load example; retain input/output/logs and restart behaviour |
| A03 | MD/AN | A01 | Procure first source samples, document rights route, measure impedance and calibrate source in load A; blind prediction in load B |
| A04 | GM/AO | A01 | Generate a three-driver common horn with front/rear volumes and tagged interfaces from one parameter record; also generate printable solids |
| A05 | AN/AO | A02, A04 | Execute V01–V06 subset, absolute gain/phase checks and mesh/precision scaling; profile CAD/mesh/solve/output separately |
| A06 | GM/MD/AN | A03, A04 | Print and measure baseline; archive geometry, voltage-calibrated low-level data, polars and preliminary output/assembly findings |
| A07 | PO/all | A05, A06 | G0 decision report: proceed, narrow, hold or change approach, with failed evidence and revised estimates |

Week 1 should prioritise measurement booking and source procurement alongside headless integration. Week 2 should produce the first geometry/solve and calibrated driver measurements. Weeks 3–4 address convergence, print/measurement comparison and the decision. If lead times prevent the measurement, G0 remains pending; the software team can complete independent verification but cannot declare physical feasibility.

G0 requires a credible source-transfer result, generated coupled solve, elementary verification, useful measured agreement over a declared domain, measured compute envelope and a viable data-rights path. Details and fallback actions are in the [feasibility report](feasibility-report.md). No broad search or extensive UI investment is necessary to resolve this gate.

## Phase B — reproducible vertical slice, weeks 5–12

| Work ID | Owner | Depends on | Deliverable and acceptance |
| --- | --- | --- | --- |
| B01 | AO | G0 | Versioned domain contracts and import validation; reject unit, mass, missing-price and source-band errors; retain provenance |
| B02 | GM | B01, A04 | Parameterised three/five-driver families; port/chamber/driver clearances and semantic topology checks; ≥95% success on predeclared valid samples, reject every known invalid fixture |
| B03 | AO/AN | B01, A02 | Pinned adapter with multi-excitation arrays and explicit normalisation; V01–V06 pass for supported fixtures without model-fitting offsets |
| B04 | AO | B01 | Durable job lifecycle and atomic results; force interruption at every stage, recover without false completion or duplicated cost |
| B05 | AN/AO | B03 | Versioned metrics with non-null/null policies, angular quadrature and real-power checks; independent reference calculations |
| B06 | GM/AO | B02 | First complete print bundle: 3MF/STL/STEP, BOM, assembly transforms, source hashes and crossover configuration; correct-scale import in two selected slicers |
| B07 | AO/MD | B01, B05 | Measurement importer and overlay; validity windows, calibration evidence and uncertainty retained; no silent fit-to-prediction |
| B08 | all | B02–B07 | G1: fresh machine runs a saved brief through catalogue→geometry→solve→metrics→build with traceable raw evidence and a baseline comparison |

The vertical slice may use a small private qualified catalogue. It does not satisfy the full offline-pack release gate until rights and record counts are met. Experimental exports must clearly identify unverified predictions.

## Phase C — optimisation and catalogue, weeks 13–20

| Work ID | Owner | Depends on | Deliverable and acceptance |
| --- | --- | --- | --- |
| C01 | AN/AO | G1 | F0 screens for packaging, costs and reduced acoustics; define applicable domain and rejected-candidate audit |
| C02 | AO/AN | C01 | Mixed-variable search with explicit topology/model/count, bounded geometry and active DSP; reproducible seeds, budget, cancellation and checkpoints |
| C03 | AO/AN | C02 | F1/F2 promotion and common-fidelity Pareto archive; resource limits and exploration allocation; never compare an unchecked coarse score as a verified finalist |
| C04 | MD/AO | B01, A03 | Curated pack release candidate; source qualification by band, permissions, conflict review and independent price offers; offline reference search |
| C05 | AO/PO | C03, C04 | Five-step UI with candidate cutaway, constraints, evidence state, cost scope and failure explanations; reuse upstream view components if integration spike supports it |
| C06 | AN/MD | C03 | Three fixed briefs × ≥3 seeds, hand-tuned and random-search controls; equal budget, ranking/false-negative audit and full failed-run records |
| C07 | all | C04–C06 | G2: meaningful constrained search demonstrated, catalogue route credible and baseline/finalist predictions frozen for blind measurements |

Start with explicit multiobjective mixed-variable search. Add a surrogate only if profiling shows value and held-out ranking/calibration tests support it. Its training set must exclude final physical holdouts. Algorithm novelty is not a release requirement.

## Phase D — physical beta, weeks 21–28

| Work ID | Owner | Depends on | Deliverable and acceptance |
| --- | --- | --- | --- |
| D01 | GM/MD | G2 | Two printed samples per family, plus distinct nominated improved build if needed; independent build/assembly records |
| D02 | MD/AN | D01 | Execute V08/V09 and the acquisition protocol: low-level curves, sufficient polars, actual electrical input, distortion/compression, reassembly and uncertainty |
| D03 | AN/GM | D02 | Investigate discrepancy with controlled source, leakage, bracing and port experiments; constrain supported domain or fix model and requalify |
| D04 | AN/AO/MD | D02 | V10 blind baseline-versus-improvement report; improvement beyond uncertainty without broken constraints; disclose briefs with no improvement |
| D05 | GM/AO | D01, D03 | Re-evaluate manufactured assembly geometry, support/joint effects and print cost; two-slicer and physical fit evidence for final exports |
| D06 | all | D02–D05 | G3: all physical and manufacturing criteria met for the released domain; uncertainty and unsupported claims visible |

A model corrected after seeing a holdout failure requires a fresh holdout for unbiased evaluation. This can extend the phase; plan measurement access and spare components accordingly.

## Phase E — release, approximately weeks 29–32

| Work ID | Owner | Depends on | Deliverable and acceptance |
| --- | --- | --- | --- |
| E01 | AO | G3 | Supported CPU installer on selected platforms; clean offline install and reference search; optional backend matrix qualified separately |
| E02 | PO/AO/MD | C04, G3 | Component inventory, distribution decision and driver-pack permission records; no unresolved rights in shipped assets |
| E03 | AO/GM | E01 | Builder documentation, known limits, measurement import and complete example build package; reproducible manifests |
| E04 | all | E01–E03 | G4 release review against every P0 requirement and evidence report; version-tagged dependency/data/fixture manifests |

Phases can overlap for independent work. The feasibility report's 20–32 week/person-week ranges are broad capacity assumptions; this table deliberately uses a 32-week sequential baseline. Reduce elapsed time only with demonstrated throughput, not by removing validation.

## P0 traceability

| PRD requirement | Implementation | Acceptance evidence |
| --- | --- | --- |
| PR01 goals | A01, B01, C05 | Brief round-trip, units and constraint validation |
| PR02 included database | C04, E01–E02 | Rights-cleared pack count/qualification gate and fresh offline search |
| PR03 driver/count/path search | B02, C02, C06 | Distinct counts/models/positions selected under controlled briefs; supported straight-path scope explicit |
| PR04 generated geometry | B02, B06 | Valid/invalid parameter sample and clearance/tag checks |
| PR05 coupled drivers | B03, D02 | V01–V08, induced inactive motion and correct terminations |
| PR06 optimisation lifecycle | B04, C02 | Forced interruption, resume/cancel and budget accounting |
| PR07 comparable results | B05, C03, C05 | Common-fidelity archive, traceable metrics/cost/evidence state |
| PR08 active crossover | B03, C02, B06 | Complex synthesis agrees with direct combined excitation; exported gain/delay/filter conventions |
| PR09 printable package | B06, D05 | Correct-scale two-slicer import, final-assembly comparison and physical fit |
| PR10 measurements | B07, D02 | Calibrated import/overlay and valid-band reporting |
| PR11 honest failure/unknowns | B01, B04, C05 | Invalid input, numerical failure, infeasible, partial and unknown outcomes remain distinct |

PR12 is deferred. A curved path, new driver-source type, passive network or new loss model requires an additional fixture and supported-domain decision before release.

## Operational details to implement early

Evaluation states: queued, validating, meshing, solving, scoring, completed, plus explicit invalid-input, infeasible, numerical-failure, resource-limit and cancelled outcomes. Write incomplete outputs to a temporary directory; only publish completed manifests after required arrays and checks are present. Terminate crashed workers without losing completed results.

Target UI cancellation acknowledgement within two seconds and immediate prevention of new scheduling. Active solver work follows backend-safe termination. Record timeouts and at most one automatic retry for a transient failure; do not hide numerical failure through repeated retries or silent fallback fidelity.

Keep the server local by default. Imported projects are data, not executable CAD scripts. Validate archive paths and file sizes. Remote execution is a later configuration with authentication and job isolation; it is not needed for the first desktop product.

## First development tickets

1. Freeze A01 reference brief and V01–V09 protocol; assign people and measurement date.
2. Implement A02 adapter spike against the research pin and archive one complete headless run.
3. Create independent V01/V02 reference cases and absolute complex-response comparator.
4. Build A04 named-domain geometry and verify one print/analysis correspondence.
5. Execute A03 source/load campaign with locked calibration/holdout roles.
6. Benchmark accuracy, memory and wall time on A04 across mesh densities; estimate actual search budget.
7. Print/measure A06, then hold A07 with a written proceed/narrow/hold decision.

These are ready to turn into implementation issues once staffing and the first brief are fixed. This repository contains their specifications, not completed implementations or claimed passing tests.
