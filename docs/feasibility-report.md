# Feasibility report

7 September 2026 · Decision proposal · No acoustic benchmarks or physical tests executed by this project

## Recommendation

**Proceed with a bounded feasibility study; do not yet commit to a general-purpose automatic MEH designer.** A constrained, active two-way product is technically credible. Demonstrating that it reliably discovers cheaper, efficient, printable hi-fi speakers remains an experimental question. The first investment should buy trustworthy source models, a reproducible coupled solve and a measured baseline.

The central risk is model discrepancy: an optimiser can exploit errors in driver loading, damping, mesh resolution, phase, prices or manufacturability and return a numerically excellent but physically disappointing design. More search cannot fix an invalid objective or source model. The proposed response is to qualify a limited operating domain, measure prediction error, reserve independent holdouts and make unsupported outputs explicitly provisional.

Boundary Lab is the preferred engine to evaluate, rather than a reason to skip evaluation. See the [pinned upstream review](research/upstream-review.md) for primary evidence and its limits. Solana demonstrates a relevant design precedent, not a quantified success probability for this product or every cheap driver. [JW Sound Solana](https://www.jwsound.live/designs/solana-diy).

## Feasibility by subsystem

| Area | Assessment | Evidence and critical experiment |
| --- | --- | --- |
| Parametric geometry and printable solids | Plausible using established CAD tools | CadQuery supports the relevant solid/export workflow. Prove port, driver and split-part validity across a declared parameter sample; export support alone is not printability. [CadQuery](https://cadquery.readthedocs.io/en/stable/index.html) |
| Coupled small-signal acoustics | Promising, unqualified for our application | Upstream documents the necessary coupled path. Run our analytic, source-loading and interface cases, then compare a physical MEH. |
| Cheap-driver high-frequency prediction | Highest data risk | A rigid-piston small-signal model does not resolve breakup, complex throat loading or nonlinear output. Qualify source behaviour in the intended mounting and band. [COMSOL driver modelling](https://www.comsol.com/support/learning-center/course/modeling-speaker-drivers-in-comsol-multiphysics-202/modeling-speaker-drivers-lumped-methods-88401) |
| Search over count/model/geometry | Algorithms available; benefit unproven | Mixed-variable search is supported by libraries, but candidate validity, comparable fidelities and useful ranking must be demonstrated. [pymoo mixed variables](https://pymoo.org/customization/mixed.html) |
| Full-band compute | Material risk | Measure the coupled solver's cost at converged resolution. A GPU cannot rescue a problem that exceeds memory. |
| Bundled catalogue | Achievable with focused curation; acquisition unresolved | Useful manufacturer material exists; access alone does not settle redistribution or source qualification. [Dayton ND91-4](https://www.daytonaudio.com/product/1046/nd91-4-3-1-2-aluminum-cone-full-range-driver-4-ohm) |
| Printed acoustic fidelity | Requires build tests | Joints, leakage, wall motion and mounting tolerances can change the model. Check repeated assemblies and low-level/high-level behaviour. [Prusa sealing guidance](https://help.prusa3d.com/article/watertight-prints_112324?product=mk3s-2) |
| “Hi-fi” at target output | Not established by linear simulation | Measure distortion, compression, noise and spatial response under a frozen signal/level specification. |

## Physical constraints and scope

A useful first release selects actual catalogue driver models and supported counts, then optimises a straight common horn's length, flare, transitions, entries, front chambers, rear chambers and active filters. The initial three- and five-driver symmetric families give genuine driver-count choice while keeping geometry and measurements tractable. Driver diameter is selected through real models, not freely scaled on an existing motor.

Deep bass, compact size, wide bandwidth, controlled directivity, high output and minimal cost compete. The example 150 Hz–18 kHz brief in the PRD is an illustrative challenge, not a promised feasible envelope. The feasibility study must freeze one reference brief, including coverage-control frequency, assembled size and a subwoofer handoff if needed. It may discover that the cheapest credible design uses a narrower bandwidth or larger horn.

Curved and folded paths are deferred geometry families, not supported features hidden behind “horn-path optimisation.” Each needs new validity constraints, source/loading checks and measured transfer evidence. Passive networks are also deferred: independent voltage-source/DSP recombination is not a general circuit solver.

Efficiency must use real electrical power and a defined acoustic output measure. SPL at 2.83 V is useful sensitivity information but is not equal-power efficiency when impedance differs. Without adequate spherical radiation data, report directional output per real watt and avoid claiming total acoustic efficiency. Maximum excursion from a linear model is an estimated limit, not measured clean output.

## Why validation data is the critical path

A database can contain hundreds of specification sheets yet very few usable simulation sources. A qualifying source record needs the correct mechanical mass convention, geometry, complex electrical/acoustic behaviour, mounting reference, uncertainty and validated band. An HF source fitted in one acoustic load may not transfer to another. The study must predict a second load or entry configuration without refitting to its response.

Available upstream assets shorten integration but do not provide a turnkey validation corpus. The inspected CRAM record lacks voltage calibration. The compression-driver case demonstrates an internal configuration rather than an experimentally qualified broadband source. The cavity fixtures are valuable numerical evidence, but cannot establish leakage, distortion or driver behaviour. See the [data plan](validation-data-plan.md).

Minimum evidence for a useful product comprises independent elementary references, a voltage-calibrated source/load dataset, repeated printed MEHs, and an untouched evaluation set. Four units across two families are a sensible initial release minimum, but a weak basis for claims about all manufacturers or production tolerances. Claims must stay within the tested domain; expand sample sizes before broad reliability claims.

## Compute and economic sensitivity

Use measured timings to price searches. The following arithmetic is a planning model, not a benchmark:

`search_hours = (N0*t0 + N1*t1 + N2*t2 + N3*t3)/3600`

Here each t is wall time per complete candidate at its fidelity, including CAD, meshing, all frequencies and outputs. For illustration, 1,000 screens at 0.1 s, 100 coarse candidates at 120 s, 10 fine candidates at 1,800 s and five final verifications at 3,600 s require about **13.4 serial hours**. If the acoustic stages take ten times longer, the same programme takes about **133.4 hours**. Queue concurrency only helps if memory and backend capability permit it. Extra tolerance samples add separate evaluations unless a validated approximation is used.

For a dense retained matrix, one complex FP32 array alone occupies approximately `8*N*N` bytes: at N=20,000, 3.2 GB decimal. Factorisation, copies, geometry, interior matrices and multiple outputs add overhead. N is the actual retained unknown count, not an arbitrary mesh-file element total. Dense factorisation can scale cubically; static condensation does not remove all dense radiation cost. The [coupled solver documentation](https://github.com/JWSound/boundary-lab/blob/8cb166226e412877d3f71f2845918e479b97aa85/docs/Coupled%20Solver.md) motivates a measured scaling gate.

The [upstream cavity notes](https://github.com/JWSound/boundary-lab/blob/8cb166226e412877d3f71f2845918e479b97aa85/tests/fixtures/noncubic_cavity/README.md) further warn against treating eight elements per wavelength as sufficient for tight modal accuracy. Our performance experiment must use meshes that pass accuracy gates, not merely meshes that fit in memory.

Hardware planning envelopes are CPU/32 GB RAM and optional 64 GB RAM/16 GB GPU. These are test targets, not certified minimum specifications. No overnight search or cross-platform installer performance is yet established.

### Programme cost assumptions

Use these as internal allowance ranges in GBP, not supplier quotes or current market prices:

| Item | Planning allowance | Basis / exclusions |
| --- | --- | --- |
| Four-week feasibility labour | 6–10 person-weeks total | Acoustics 3–4, software 2–4, CAD/measurement 1–2; needs coordinated access to a print/measurement facility |
| Drivers, print iterations, fixtures, seals and electronics | £1,500–£4,000 | Several sacrificial builds and repeated driver samples; excludes major equipment purchases |
| External measurement access | £1,000–£5,000 | Reserve subject to facility quote; calibrated spherical work may exceed this |
| Compute and storage | £300–£1,000 | Contingency if local equipment exists; hardware purchase separately approved |
| Full implementation | Approximately 60–96 person-weeks | Three core contributors across roughly 20–32 working weeks, plus part-time measurement/release work; physical procurement may extend elapsed time |

At an assumed blended £1,000 per person-day, feasibility labour would be £30,000–£50,000 before expenses and tax. This is a sensitivity example, not an assessed market rate. Do not equate low BOM cost for the final speaker with low development cost. Obtain quotes and revise after the four-week gate.

Per-speaker accounting must distinguish driver subtotal, all-in purchased parts, filament/support/waste, electricity, print failure allowance, optional labour and amortisation. Optimisation uses a frozen price snapshot with quantity, currency and tax/shipping treatment. Missing prices are unknown, never zero. The release catalogue gate requires both data rights and suitable availability.

## Risk register

| ID | Risk / impact | Early evidence | Mitigation and decision |
| --- | --- | --- | --- |
| R1 | HF source model fails under new load; false rankings | Predict second fixture without response refit | Restrict source/band; measure effective interface; stop general HF claims if transfer remains poor |
| R2 | Converged solves exceed budget | Three mesh sizes and representative frequencies, retained unknowns and measured peak memory | Narrow band/geometry; use validated screening; evaluate another solver only after measured bottleneck |
| R3 | Optimiser exploits model error or coarse null sampling | Dense finalist grids, random rejected-candidate audit and physical holdout | Limit search to qualified domain; reserve exploration and report disagreement |
| R4 | Port loss/leakage/wall compliance dominates | Change port aspect ratio, reseal joints, compare braced build | Calibrate a supported loss model or exclude regime; never fit arbitrary damping per finalist |
| R5 | Catalogue cannot be legally and technically bundled | Permission records plus qualified source completeness | Prioritise owned measurements and explicit agreements; PR02 remains blocked if pack unavailable |
| R6 | Printing changes acoustic geometry | Scan/dimension checks, reassembly and slicer checks | Feed manufactured changes back through solver; reject unverifiable export |
| R7 | Tests share upstream mistakes | Analytic oracle and independently authored second solver model | Require independent evidence, not only upstream regression agreement |
| R8 | Scope expands before evidence | Milestone review against fixed first families | Defer folds, passive networks and cloud features until their own evidence exists |

## Four-week decision

G0 below approves proceeding to the vertical slice; it does not approve a public performance claim.

**Proceed:** one generated MEH runs unattended with explicit source/loading conventions; elementary and absolute-response comparisons meet the declared gates; a voltage-calibrated first build agrees over a declared useful band or has a bounded, explainable discrepancy; a second source-load test supports transfer; representative compute fits the frozen search budget; a viable data acquisition/rights path exists. Store all evidence and failures.

**Narrow:** numerical verification works but measurement agrees only in a smaller domain, or compute needs a smaller family/band. Publish the restricted scope and revised brief. Re-estimate costs; do not silently relax accuracy limits.

**Hold:** a measurement slot or permission decision is pending. Extend the study explicitly; absence of evidence is not a pass.

**Stop or change engine/model:** elementary physics remains inconsistent, source transfer fails after a bounded investigation, or converged runtime exceeds a useful budget even after honest scope reduction. A new solver is a separate investment decision with a new validation obligation.

The feasible first milestone is a reproducible, measured design pipeline. The broad inverse-design product becomes justified when that pipeline also demonstrates repeatable optimisation benefit on withheld briefs and physical builds.
