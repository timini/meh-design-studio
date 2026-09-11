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
changed outlet coordinates. An independent fresh native alternate-circuit
comparison is still required before accepting this path for design decisions.

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
search status and scores are untouched. This command supplies no selected DSP,
winning score, qualified physical prediction or manufacturing export.
