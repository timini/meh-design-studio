# Implementation status

The mirror-group electrical validator now distinguishes cut diaphragm area from
physical coil multiplicity using hashed source meshes. Its native quarter-model
checks pass at the unchanged 1e-8 limit. Scoring and amplifier-current reports
also sum the physical coils, preventing incorrect parallel-bank load acceptance.
The latest 4/3 mm quarter-mesh comparison passes 2% at 1.55%, but the new quarter
model differs by 8.70% from the older full reference. Mirror reduction therefore
remains an experimental route to faster search. See
[driver accounting, scoring and refinement evidence](mirror-bank-scoring.md).

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

The [strongly curved seed preparations](curved-mouth-preparation.md) now also
complete CAD, tagged air meshing and coupled-solver input generation for
exponential-round and quadratic rounded-square flares. Their native mouth
conforming preserves the curved walls exactly and passes the existing topology,
interface, volume and mesh limits. The [exponential-round native search](nonlinear-commercial-search.md)
now completes both candidates and the selected export. Its seed remains better
than its mutation, but both fail the 6 dB response screen (14.26 and 15.09 dB).
The quadratic rounded-square seed completes all 15 frequencies but fails the
response screen at 20.35 dB; its mutation exceeds the exterior mesh budget.
Both searches, their selected exports and the failed preparations remain archived.

[Tilted entries](tilted-mid-entries.md) now also complete a two-candidate native
FP64 search and export. The selected mutation improves its synthetic four-frequency
reference score, but fails the unchanged 2% rotation/axis-equality check, and both
candidates fail the strict electrical reciprocity check. This extends the real
geometry/solver workflow without establishing an accepted commercial design.

[Adaptive search](adaptive-search.md) mutates profile and geometry controls using
preceding simulated fitness, with periodic random exploration, bound checks and
verified ancestral evidence. [Wide-mid objectives](wide-mid-objectives.md) add
LR4 crossover/polarity/delay selection, H/V coverage scoring and full coupled
parallel-bank impedance. Finalists freeze the DSP and compare raw complex
pressures across the sampled coverage sectors. Optional [whole-sphere scoring](whole-sphere-objectives.md)
adds native off-plane pressure observations and denser finalist angular checks;
its exterior analytical reference passes the unchanged 2% complex-error limit.
Commercial source calibration,
full-band numerical convergence, comparable measured performance, manufacturing
qualification and an actual finished affordable design remain open.

A completed [coarse screening comparison](coarse-screening.md) reverses the
ranking of two retained candidates and fails the declared complex-field agreement
limit. Both native runs and the original preparation failure are preserved.
This cheaper pipeline is not established as a reliable search screen.

The [measured CRAM reference](measured-cram-reference.md) now completes native
FP64 evaluation and verification after correcting named FEM volume selection.
Its fixed conditional comparison fails the 3 dB held-out response-shape limit
at 5.193 dB maximum error. The unmatched ground/measurement conditions and
preserved failure do not establish physical accuracy of the target horn.

Explicit [boundary integration controls](bem-quadrature.md) now pass through
solve requests, search candidates, finalists and recovery with verified native
settings. A four-level FP64 CRAM study reproduces the default fields exactly and
passes its 1% final-pair field-stability screen at 0.00553%, while every level
still fails the unchanged 1e-8 electrical reciprocity limit. Finer integration
alone has not resolved that failure; no mesh or physical convergence is claimed.

The first [350–7,500 Hz four-proposal search](wide-mid-target-experiment.md)
completed with reported FaitalPRO mid circuits and a synthetic HF placeholder.
Selection reduced sampled target residual variation from 13.17 to 11.81 dB;
the selected design still fails the practical response target. Raw trials,
fixed DSP, build-cost estimate and exact geometry export are archived.
[Operating reports](operating-predictions.md) now map verified native voltage
transfer ratios to explicit RMS drive, pressure, excursion and amplifier current.
This is numerical source normalisation, not physical driver calibration.

The subsequent [larger-horn search](larger-target-experiment.md) completed three
native candidates from eight proposals, preserving five geometry/interface
failures. Its selected mutation improved response variation from 8.25 to 7.35 dB
with identical selected DSP, but still missed the provisional 6 dB limit. The
verified export and £261.30 planning estimate remain experimental. Independent
[mid-port placement](eccentric-mid-ports.md) now also completes the native
geometry/simulation/mutation/export loop, with spherical observations in a
separate synthetic diagnostic. The completed [target-size port-shift experiment](target-entry-experiment.md)
worsened the response and was rejected. A new search enforces the
[actual acoustic mid/HF handover](wide-mid-objectives.md), instead of relying on
the electrical crossover setting alone.

The [larger-port experiment](large-port-handover-evidence.md) completed all 15
native frequencies but failed the declared acoustic handover for every DSP
combination. A continuous-gain diagnostic also finds no feasible gain within the
tested LR4 family. Its complete fields and original failed search are retained;
it supplies no winner or selected build export.

The [FP64 reference backend](reference-backend-evidence.md) now completes the
same optimisation/replay/export workflow. Both trials in its synthetic diagnostic
passed the unchanged electrical consistency limits. The older, different
freeform geometry's reciprocity failure remains unresolved.
[Observation distance](observation-distance.md) is now an explicit acoustic
search control carried through native compilation and finalist validation.
Historical one-metre results remain one-metre results. Commercial HF source
qualification is still open; the [source audit](research/commercial-hf-source-audit.md)
records the available manufacturer evidence and remaining gaps.

An explicit [ideal diaphragm-to-outlet transformer](ideal-compression-source.md)
now separates physical throat-driver area from horn-exit area, including circuit
conversion and physical diaphragm excursion reporting. Its circuit equivalence
checks do not qualify a commercial compression driver or its phase plug.

An [independent pulsating-sphere comparison](pulsating-sphere-reference.md)
passed its predeclared 2% complex-pressure limit at 350, 2,000, 5,000 and 7,500 Hz
(maximum 0.708%). This validates the tested exterior formulation and normalisation
on that reference; it does not validate horn source models. The earlier adaptive
finalist's two completed mesh levels agreed within 0.0063 dB/0.137 degrees, but
the third level exceeded the historical mesh workload cap and the study failed.
Its raw failure is retained in [mesh workload evidence](mesh-workloads.md).

## R1 requested horn experiment

The [240–3000 Hz R1 prototype](../designs/240hz-3khz-four-driver/README.md) now has archived print geometry, a four-entry front-air domain, tagged meshes and an executed prescribed-flow FEM diagnostic with an independent tube check. A 17-point sweep and three mesh levels retain numerical failures: the 3 kHz complex-transfer stability screen fails the unchanged 10% limit even at the 10-to-7.5 mm comparison (10.208%). This is internal mean pressure with local mouth impedance, not exterior radiation or a commercial-driver response. Actual driver/source coupling, rear loads, radiation and physical qualification remain open; R1 has not achieved its acoustic target.

## Available

- `meh resume-optimise` continues stopped searches using saved inputs and verified completed trials. It preserves the original evidence and retries incomplete trials; partial solver sweeps, abrupt-death recovery and total lifetime compute accounting remain open. See [search recovery](end-to-end-search.md#continue-a-stopped-search).

- Durable SQLite job leases, cancellation, one automatic recovery retry, bounded completion descriptors and integrity-checked publication. An isolated CAD worker is accessible through `meh jobs` with managed input snapshots, cancellation, retry and verified result retrieval; dependency-aware scheduling and full search/solver orchestration through durable workers remain to implement.
- Explicit RMS complex source synthesis, signed real electrical power, pressure-level null handling and full-sphere pressure quadrature. Verified winning voltage bases now feed single-tone operating predictions. Native sphere data now feeds optional search scoring; physical amplitude calibration, radiated-power qualification and angular quadrature convergence remain open.

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

1. Find a target-band candidate with acceptable response, coverage and operating requirements; verify frozen DSP on held-out frequencies and progressively refined meshes.
2. Obtain commercial HF source/load data and driver/chamber geometry, and test model uncertainty and the unresolved strict electrical reciprocity discrepancy.
3. Make manufacturing interfaces and estimated material costs correspond to actual driver mounts, cone clearances, assembly and slicing; complete physical source and speaker measurements.
4. Connect the existing durable job infrastructure to complete search/solver orchestration where it improves these end-to-end experiments. This is secondary to the acoustic and manufacturing gaps above.

Physical source/load acquisition, actual builds, calibrated measurements and rights-cleared catalogue release remain external evidence work. Reference tests passing cannot mark those items complete.

Each meaningful increment uses one review round. Address material findings, verify
the fixes and merge under the maintainer’s standing authorisation when relevant
checks pass. Routine fixes and evidence updates do not require another review or
fresh approval on every commit. Defer non-blocking polish and speculative hardening.
An unavailable automated reviewer does not create an indefinite merge block; inspect
the change directly and record the limitation. See [repository working instructions](../AGENTS.md).

Completed frequencies from a timed-out or cancelled managed solve can now be
[verified and assembled with a supplementary run](partial-frequency-evidence.md).
Source identity, overlapping complex arrays and complete requested coverage are
checked without rewriting the original failure. The
[actual 15-frequency vocal-band assessment](wide-vocal-completion.md) completes
numerical coverage but fails the 6 dB response screen at 15.66 dB with the required
mid/HF handover. This is further evidence that the current horn is not ready to build.

[Linked profile symmetry and versioned periodic cubic interpolation](profile-symmetry-search.md)
now let the optimiser preserve reflection or quarter-turn geometry while searching
nonconical surfaces. The [native evidence](periodic-profile-evidence.md) retains a
legacy spline seam defect, its CAD correction, and a two-candidate coupled FP64
search whose selected offspring and exported geometry verify. This numerical
reference does not resolve the full-size horn's remaining response or commercial
source and manufacturing gaps.

The [completed full-size quarter-turn search](quarter-turn-vocal-search.md)
retains three native candidates and one exterior-mesh failure. Its selected
mutation improves the combined coverage/response/cost objective, but all three
candidates fail the 6 dB response screen. A separate bounded common-EQ diagnostic
also remains above that limit; the work continues with different curved flares.
