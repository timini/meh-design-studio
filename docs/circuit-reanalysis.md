# Driver-circuit comparisons on fixed native acoustic geometry

`meh reanalyse-circuits` derives new voltage-driven fields from a complete,
verified native velocity basis. It can change circuit parameters and explicitly
modelled throat area transformation while retaining the exact acoustic geometry,
moving-boundary areas, medium and motion profiles. A geometry mutation, different
mid diaphragm area or changed acoustic medium still requires a new field solve.

This enables commercial-source and circuit-uncertainty comparisons without
discarding mutual loading or rerunning an unchanged FEM/BEM discretisation.
It does not add missing phase-plug geometry, breakup, nonlinear behaviour or
source measurements. Its output is explicitly derived evidence; native search
readers and build exporters do not treat it as a new completed native search.

## Reconstruction

At each frequency, use receiving components as rows and independent voltage
excitations as columns. The original native velocity and current matrices are
`V` and `I`. In the native outlet coordinate, the acoustic reaction is
`F = diag(Bl) I − diag(Zm) V`. Solving `Za V = F` reconstructs the discretised
acoustic load matrix. There is no inversion of a partial or rank-deficient basis.

With the replacement circuit, solve
`[Za + diag(Zm_new + Bl_new² / Ze_new)] V_new = diag(Bl_new / Ze_new) E`,
where `E` contains the original independent 2.83 V excitations. New coil currents
follow from the new electrical equation. Solving `V W = V_new` then supplies
the weights that recombine every retained complex pressure/normal-derivative
field. **Old coil currents cannot simply be recombined with those weights.**

The source model and compiled parameters must agree before reconstruction.
Both old and new physical circuits use the explicit outlet-coordinate conversion
when declared. The resulting velocity basis is in that native coordinate;
physical diaphragm velocity is obtained by dividing the relevant receiving
column by its source's outlet velocity ratio.

## Numerical screens and limits

Defaults reject a velocity basis or replacement circuit with condition number
above 1e6. The input voltage-equation residual screen is 1e-5, allowing exploratory
complex64 inputs; the new circuit/recombination algebra must agree within 1e-10.
These are declared reanalysis screens, **not a relaxation or pass of the separate
1e-8 native electrical gate**. The original assessment, input precision,
conditioning and residuals are retained. Complex128 calculations cannot restore
information lost in complex64 native storage. Acoustic-load reciprocity and its
Hermitian eigenvalue are reported without symmetrising, clipping or correcting
the inferred load.

Unit checks compare against independently solved physical driver equations on a
known reciprocal load, including induced current, volume flow, pressure and
changed outlet coordinates. The independent fresh native alternate-circuit
comparison below has passed. This establishes numerical agreement for that
discretised reference, not the accuracy of a commercial driver model.

## Executed independent native comparison

Runtime source `40e23d4` reconstructed the load from the original
[`ab6714f` periodic-profile reference](periodic-profile-evidence.md), then replaced
its synthetic HF with the [provisional Peerless ideal-outlet circuit](research/commercial-hf-source-audit.md).
The four synthetic mids, acoustic medium, geometry and all six compiled mesh
hashes were retained. A separate CAD compilation and fresh `coupled_reference`
solve evaluated the replacement circuit at 350, 1000, 2000 and 3000 Hz.

The relative complex L2 tolerance of `1e-8` was recorded before either the derived
arrays or new native arrays were produced. All 32 quantity/frequency pairs passed,
including exterior pressure, sphere and polar fields, FEM pressure, BEM traces,
driver velocities and coil currents. The largest error was
`5.832485738303627e-12`, in the 3000 Hz BEM normal derivative. The fresh native
result independently passed the unchanged `1e-8` electrical consistency gate;
its largest electrical reciprocity residual was `9.427044770619989e-9`.

The [evidence report](../validation/evidence/circuit-reanalysis/report.json) binds
archives containing the new native search, separate derived dataset, comparison
rows, predeclared controls and runners. The original native basis remains in the
[periodic-profile evidence archive](../validation/evidence/periodic-profile-symmetry/report.json).
The reanalysis retains the original load's numerical reciprocity and passivity
diagnostics without altering it to force agreement.

This small reference has synthetic mids, a disabled 2-ohm screen and a £100
fixture driver allowance. The HF record remains provisional, and its separate
unfitted plane-wave-tube comparison still fails the declared 3 dB screen. The
new reference's 12.46 dB selected response variation is not acceptance of the
full-size design. This experiment establishes neither mesh convergence nor
physical source, mechanical fit, print or output qualification.

## Run a comparison

Create a `HornSources` JSON by retaining a solved system's medium and side source
and replacing its `throat` with the desired driver's `source_model`. Retain its
provenance and explicit `ideal_outlet_area_m2`; the latter must match the solved
throat opening. Then run:

```sh
meh reanalyse-circuits runs/SEARCH/trial-000/system/project.blab.json \
  --evaluation runs/SEARCH/trial-000/evaluation \
  --sources runs/replacement-sources.json \
  --output runs/replacement-circuit-fields
```

The new directory contains `derived.json`, the circuit matrices and weights,
and separate recombined field arrays. It records original native identities,
replacement sources, limits and array hashes. The original project, evaluation,
search status and scores are untouched.

Add `--brief runs/SEARCH/brief.json` to select DSP for the replacement circuit
using the same scoring calculation as native optimisation. The complete frequency
grid and observation distance must match. The brief supplies acoustic objectives
and gain/crossover/polarity/delay choices, including its parallel-bank impedance
and acoustic handover constraints. The reported bank load uses the replacement
coil currents, including mutually induced motion.

`derived.json` then records `acoustic_scoring.controls`, the brief hash and a
separate `acoustic_scoring.score`. This is an acoustic comparison: it does not
check catalogue eligibility, replacement-driver prices or mechanical fit. No
derived score becomes a native search winner or manufacturing export, and the
original electrical assessment is not represented as a qualification of the
replacement source. A completed score is not itself acoustic acceptance.

If no DSP setting satisfies the constraints, the command fails and records the
failed scoring status and reason while retaining all recombined fields. Failed
experiments can therefore be inspected without weakening the declared constraints.
