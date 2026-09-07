# Validation strategy

7 September 2026 · Proposed engineering protocol v0.1

## Purpose and evidence states

Verification asks whether the implementation solves the specified equations correctly. Validation asks whether those equations and inputs predict the physical speaker well enough for the intended design decision. Optimisation validation asks whether the search improves real outcomes within budget. All three are required.

Evidence progresses through `planned → acquired → quality_checked → qualified`, with `rejected` and `superseded` alternatives. A fixture's existence or a clean test process does not imply qualification. Qualification records a claim, band, level, mounting, hardware/backend and tolerances; it never attaches an unrestricted “validated” badge to a driver or application.

An evaluation additionally carries `screening`, `predicted`, `numerically_verified` or `physically_measured` status. Physical evidence can qualify a family/domain without every export having been built, but the application must distinguish that family-level support from a measurement of the exact exported unit. Unsupported distortion, absent price or incomplete polar coverage is `unknown`, not passing or zero.

## Verification ladder and gates

All targets below are provisional, pre-experiment acceptance proposals. Freeze a protocol version before each campaign. Changes after observing failures require a new version, rationale and re-run; retain the original outcome.

| ID | Fixture / experiment | Observable and proposed acceptance | Evidence required |
| --- | --- | --- | --- |
| V01 | Units, excitation and analytic electrical/mechanical circuit | Reproduce declared RMS/peak and voltage basis; circuit complex values within 0.1% away from singularities | Independently derived equations and numeric reference values; no solver-output golden file as oracle |
| V02 | Rigid rectangular cavity, varied source position | First applicable modes within 1%; correct suppressed/excited mode pattern | Analytic eigenfrequencies and at least three mesh densities |
| V03 | Baffled piston / simple radiation case | Non-null complex response: magnitude within 0.5 dB and phase within 5° | Documented radiation convention, piston size, velocity, distance and angular regime |
| V04 | Sealed and vented lumped/meshed loads | Applicable resonance within 1%; impedance/response within 0.5 dB and 5° outside singular regions | Independently authored lumped reference, explicit validity regime and damping |
| V05 | Two electrodynamic sources, active and inactive cases | Reciprocal suitable cases and power balance to 1%; nonzero induced motion where expected | Full transfer matrix, terminations, input/radiated/dissipated powers; open/short termination variants |
| V06 | FEM/BEM interface and backend convergence | Absolute response changes <0.5 dB / 5°; resonance <1%; beamwidth change <5° where defined | Three meshes, refined frequency/angle grids, supported FP32 vs FP64 reference; no fitted gain or phase |
| V07 | Independent MEH numerical model | Investigate differences >1 dB, 10° phase or 2% resonance; resolve before claiming qualification | Independently compiled geometry/loads in a second solver and convergence on both sides; these are investigation gates, not proof of truth |
| V08 | Measured low-level MEH | Defined-band MAE ≤2 dB; ≥95% bins within 3 dB; major impedance resonances within 5%; beamwidth within 10° where defined | Calibrated repeated builds, raw data, uncertainty, fixed comparison procedure |
| V09 | Output capability and print behaviour | Meets frozen brief's distortion/compression/rattle and fit/sealing limits | Level sweeps, terminal voltage/current, thermal history, assembly checks; no linear-model substitution |
| V10 | Search benefit | Constraint-feasible non-dominated improvement under equal compute; reproducible across saved briefs/seeds | Baselines, complete evaluation accounting, common fidelity and withheld physical confirmation |

V02 analytic reference for a rigid box is `f(nx,ny,nz) = c/2 * sqrt((nx/Lx)^2 + (ny/Ly)^2 + (nz/Lz)^2)`, with nonnegative integer indices excluding all zero. Modes must be matched by shape/participation when close; sorting peaks alone can misidentify them. Avoid ideal undamped resonance amplitudes as finite reference values. V03 must distinguish an infinite baffle idealisation from a finite test baffle.

V05's power calculation must use consistent phasors: for RMS electrical amplitudes, `Pin = Σ Re(V * conjugate(I))`; peak amplitudes require the factor 1/2. Acoustic boundary flux uses the corresponding pressure/normal-velocity convention and outward normals. Include every dissipative element and radiation surface. Apply the relative energy threshold only above a documented power floor.

Near deep nulls, phase and dB ratios become ill-conditioned. Predeclare a reference-pressure floor and report absolute complex error divided by a fixed reference alongside the null depth/frequency. Do not omit all hard regions to improve an average. Store unsmoothed curves; smoothing is a named comparison view.

## Absolute response, mesh and grid protocol

Upstream relative field comparisons can remove common gain and phase. They are useful for shape but insufficient for our absolute-response gate; see [upstream review](research/upstream-review.md). Hold excitation, propagation reference, medium and observation coordinates fixed when comparing meshes/backends. Do not estimate gain or delay from their differences.

Run three systematically refined meshes, document edge statistics and poor-quality elements, and check ports/interfaces separately. The finest two agreeing is necessary; an inconsistent trend or a mesh-independent modelling error still needs investigation. Frequency refinement must resolve narrow resonances and interference notches. Double angular density near beamwidth crossings and off-axis lobes. Re-evaluate final contenders on the same grid, fidelity and backend policy.

Compare symmetry-reduced and full geometry for at least one finalist. Excitation parity and physical driver terminations must agree. Test deliberately reversed normals, missing tags, duplicate rear compliance, wrong mass type and wrong voltage basis; the compiler must reject invalid contracts or the physics checks must expose them.

## Physical measurement protocol

1. Register the design, driver revisions, sample serials, build lot, intended test band/levels, protocol and data split before measurement. Freeze the predicted response and hashes before the holdout operator reveals observations.
2. Measure individual electrical impedance and dimensions. Record preconditioning, temperature and instrumentation. Fit source parameters only on designated calibration data, with bounds and uncertainty. Use at least two acoustic loads to test whether a fitted source transfers.
3. Verify microphone and electrical channel calibration, fixture geometry, distance, axis and polar origin. Measure actual driver-terminal voltage/current rather than assuming amplifier settings. Capture a loopback timing reference for complex response; do not independently time-align every angle or driver.
4. Measure low-level impedance, each active channel, all channels together and relevant inactive-driver terminations. Save complex frequency data and raw impulse/time records where available. A summed measurement should agree with linear superposition at the chosen level; a failure requires investigation.
5. Acquire axial and listening-window response, dense horizontal/vertical slices, and enough spherical sampling for claims about sound power/directivity index. Begin with 5° slices and refine to 2.5° around crossings/lobes as a proposed sampling check. Two slices alone are not a sound-power measurement.
6. Record window, reflections and environmental noise. Establish the valid lower frequency using the actual time window and setup; do not score gated low-frequency bins without support. For ground-plane/near-field extension, retain separate traces, geometric assumptions, phase reference, overlap and splice rule. A splice that cannot represent all radiating openings must be marked limited.
7. Repeat acquisition after a full repositioning on at least three runs for the reference setup, then repeat disassembly/reassembly and compare a second printed sample. This separates instrument/setup, assembly and unit variation; it does not establish population statistics from two units.
8. Run level steps under the specified signal, crest factor and duration, beginning low. Capture distortion harmonics, compression relative to low-level transfer, noise floor, thermal state and mechanical symptoms. Define stopping criteria from the driver and amplifier limits. Retain failed/limited points.

For a initial engineering brief, propose ≤1 dB output compression and THD <3% at the declared listening level in the qualified band. These are product targets to ratify, not universal definitions of hi-fi. Specify harmonic order coverage, weighting, stimulus, duration, spatial location and noise floor. Broadband/IMD tests may expose weaknesses missed by stepped-sine THD. Do not predict a passing result from Xmax alone.

Print checks include dimensions at the throat/entries, wall thickness, driver clearance, sealing, fastener access and repeated mounting. Assess wall vibration using an accelerometer or vibrometry if available; compare temporary bracing and resealing as controlled diagnostics. Define a leakage test fixture and allowable leak relative to the design before testing; an open horn cannot be treated as a globally sealed vessel without isolating intended openings. The material parts must be closed solids while the acoustic apertures remain open by design.

## Comparison and uncertainty

Compare using fixed 1/12-octave centres and a documented averaging method; weight each log-frequency bin equally unless the brief freezes another weighting. Compute response MAE and the fraction within 3 dB on the declared valid band and angular set. Apply the response gate to the axis and prescribed listening-window views separately; archive angle-wise errors so an average cannot hide a bad crossover lobe. Report unsmoothed maximum deviations and resonance/notch positions as diagnostics.

Absolute sensitivity comparisons use instrument calibration. A single common level correction is permitted only when supported by an independently measured calibration offset, recorded and bounded by that uncertainty. Show the uncorrected result too. It must not be fitted to the DUT to obtain a pass. A known acquisition/propagation delay can be removed consistently across channels and angles; arbitrary fitted time shifts and per-frequency EQ are prohibited for validation.

Estimate repeatability, microphone/voltage calibration, angle/distance error, temperature, sample variation and parameter uncertainty separately. Use sensitivity or Monte Carlo propagation within plausible joint parameter bounds; preserve correlations from parameter fitting. Compare model error with measurement uncertainty. If the measurement uncertainty is too large to resolve a tolerance, the result is inconclusive rather than an automatic pass. Small sample counts warrant ranges and conditional claims, not spurious confidence percentages.

## Optimisation-specific validation

Freeze three design briefs covering cost pressure, coverage pressure and size/output pressure. For each, compare a hand-tuned seed, equal-budget random or space-filling search, and the optimiser using at least three seeds. All use the same catalogue/price snapshot and constraints. Count failed CAD and numerical evaluations in cost accounting and report both solver calls and wall time.

Fix Pareto normalisation and any hypervolume reference point before running. Report feasible fraction, objective distributions, budget-to-first-feasible, non-dominated quality and run variability. Three seeds provide an engineering smoke test, not strong statistical generalisation. A 10% cost reduction is an aspirational outcome, not a mandatory result to manufacture by changing a baseline.

Audit screening false negatives: reserve an initial 10% of expensive evaluation budget for stratified random candidates rejected or disfavoured by lower fidelity. Measure rank agreement and the fraction of unexpectedly feasible/good designs. If screening discards good designs, soften pruning or increase exploration; do not claim coarse rankings are reliable without evidence. Surrogates remain topology/domain specific until transfer is demonstrated.

Blindly measure at least a baseline and the nominated improved candidate using the frozen protocol; count that additional build in procurement. Improvement must exceed combined uncertainty and satisfy all hard constraints. A prettier simulated Pareto front without measured support only validates search on the model.

## Release evidence and regression policy

Keep small analytic/contract checks on every implementation change. Run representative CPU numerical fixtures on solver/compiler changes; full convergence and backend matrices before qualification releases. GPU or physical checks require their actual equipment and explicit reports; missing infrastructure yields `not_run`, never a green substitute.

Each report records input/result hashes, dependency revisions, hardware, environment, metrics version, protocol version, thresholds, raw-data paths, exceptions, owner and reviewer. Release sign-off requires the P0 traceability table in the implementation plan, the qualified catalogue gate and all supported-domain checks. Changes to geometry families, source conventions, meshing, solver or manufacturing require affected evidence to be requalified. Preserve prior failed reports as part of the audit trail.
