# Generated interior acoustic experiment

This increment connects generated three/five-source geometry to Boundary Lab's actual FEM solver. It is a numerical integration experiment, not a qualified MEH speaker design. The initial executable evidence covers a three-source horn at 500, 1000 and 2000 Hz.

## Reproduce

Use the pinned runtime described in [the adapter guide](boundary-lab-adapter.md). Install the optional CAD dependencies and generate the example's air meshes first:

```sh
meh-geometry examples/three-driver-geometry.json --output runs/horn --mesh
meh compile-interior runs/horn --sources examples/synthetic-horn-sources.json --output runs/system
meh solve-project runs/system/project.blab.json --request examples/solver-smoke-request.json \
  --checkout /path/to/boundary-lab --python /path/to/boundary-python \
  --julia /path/to/julia-1.12.6 --output runs/solve
meh validate-electrical runs/system/project.blab.json runs/solve
```

Set `JULIA_DEPOT_PATH` to the instantiated Boundary Lab depot where needed. All output directories must be new. The validation command returns zero for passing equation checks, one for a numerical check failure and two for invalid inputs/artifacts.

`HornSources` requires explicit dry-mass source circuits. The bundled example is invented synthetic data, clearly labelled and unsuitable for selecting a purchased driver. Its effective diaphragm areas equal the circular source disks; mismatches fail instead of silently changing the acoustic-to-mechanical transformation.

The compiler checks design and mesh identity, expected region/boundary inventories, metre units and file hashes, then copies the mesh files into a standalone project directory. Front and rear side-driver surfaces share one rigid-translation mechanical component. Rear chamber loading comes from explicit air volumes, with no additional rear compliance. Each component has its own voltage excitation port; zero-voltage sources remain connected and reactive when another driver is excited.

The throat is an ideal piston without a modelled rear acoustic load or compression-driver internals. The mouth uses Boundary Lab's plane-wave tube termination. This provides an executable starting point but is not the free-field radiation impedance of a horn mouth. No directivity, sensitivity, maximum output or hi-fi claim follows from this experiment.

## Independent consistency checks

Historical evaluation records without domain-file or preflight hashes must be rerun before this validator will accept them; archived reports retain their original provenance.

`validate-electrical` verifies the full voltage basis against the saved project and hashed evaluation, preserves component ordering and checks the explicit native 2.83 V convention. For each frequency it evaluates the independent electrical equation `V = (Re - iωLe)I + Bl·v`, symmetry of the electrical admittance matrix and nonnegative Hermitian admittance. This strict validator requires complex128 current/velocity storage; complex64 results remain inspectable but cannot be assessed at this tolerance. Relative residual tolerance is `1e-8`; passivity permits numerical error of `1e-8` times the admittance norm. There is no conversion to RMS or SPL.

These checks catch missing phase, incorrect voltage scaling, some source-sign errors and nonreciprocal/nonpassive responses. They cannot establish acoustic discretisation accuracy: an incorrect but reciprocal acoustic load can still pass. Tests deliberately damage otherwise internally consistent arrays to verify that failures are detected.

## Executed evidence

The [machine-readable report](../validation/reports/generated-interior-integration.json) retains historical results for both meshes. The refined run lacks the current preflight and domain-artifact hashes; subsequent complete-contract rechecks cover only the coarse mesh. A fresh refined solve is still required before this comparison can serve as current-contract evidence. The 8 mm mesh contained 32,733 tetrahedra; the 4 mm mesh contained 239,894. The relative matrix-norm changes from coarse to fine were:

| Frequency | Diaphragm velocity | Voice-coil current |
|---|---:|---:|
| 500 Hz | 0.6695% | 0.1791% |
| 1000 Hz | 0.4497% | 0.1728% |
| 2000 Hz | 0.0987% | 0.0472% |

Historical checks reported electrical conservation, reciprocity and passivity passes at both levels; the refined result has not passed the current artifact-provenance gate. Two mesh levels at three sparse frequencies are a sensitivity study, not a convergence or band qualification. Repeat by copying the geometry input, changing `mesh_size_m` from `0.008` to `0.004`, and generating/compiling/solving into fresh directories. Compare complex velocity/current arrays in the preserved excitation and transducer order.

Next numerical work must add exterior radiation, independent acoustic reference comparisons, denser adaptive frequency sampling and at least three refinement levels with declared observable-specific tolerances. Physical driver qualification and speaker measurements remain separate release gates.

## Analytic acoustic load comparison

`validation/fixtures/generate_plane_wave_tube.py runs/tube` creates a square, constant-area tube with a uniform piston and matched plane-wave termination. Its exact input mechanical load is `rho * c * area = 0.664048 N·s/m`, independent of tube length. Coupling that load to the independent driver circuit gives a reference for the solver's complex velocity and current.

The [executed comparison](../validation/reports/analytic-tube-comparison.json) at 10 mm mesh spacing found velocity errors of 0.0028%, 0.0032% and 0.0141% at 500, 1000 and 2000 Hz. Current errors were below 0.0006%. This is an independent acoustic input-load comparison, with a deliberately simpler geometry than the horn. It does not qualify the horn's field accuracy or real drivers. The fixture generator uses original synthetic parameters and creates its own mesh; it redistributes no third-party mesh data.
