# Experimental exterior radiation

This stage replaces the interior experiment's matched-tube mouth termination with a conforming FEM/BEM mouth interface and a closed exterior acoustic surface. The shared horn construction fills the omitted driver packages to form an ideal rigid exterior envelope. This envelope is an acoustic domain, not a printable part.

```sh
meh compile-radiating runs/horn --sources examples/synthetic-horn-sources.json \
  --checkout /path/to/boundary-lab --python /path/to/boundary-python \
  --julia /path/to/julia-1.12.6 --output runs/radiating-system
```

The source air meshes must already exist, as described in the [generated-system guide](generated-system.md). The compiler uses the pinned upstream `conform-interface` command to replace the exterior mouth triangles with the authoritative FEM facets. Both original and conformed surface meshes must be closed, connected, consistently oriented linear triangular surfaces with positive enclosed volume. CAD/surface volumes must agree within 2%; this is a geometry integrity tolerance, not an acoustic error bound. The experimental surface budget is 8,000 triangles and the exterior target spacing is limited to 10–50 mm.

Solve the resulting `project.blab.json` using the normal adapter. A request with `include_project_observations: true` retains horizontal and vertical complex polar pressures; requesting `bem_boundary_traces` and `fem_nodal_pressure` additionally preserves the boundary and interior fields. A source remains connected when another source is driven.

A later run using `examples/radiation-smoke-request.json` completed 500, 1000 and 2000 Hz through the adapter’s independent source-mesh/domain checks. Its full evaluation is included in the report. This establishes execution and artifact integrity at those points, not acoustic qualification.

## Executed evidence and unresolved validation

The [integration report](../validation/reports/coupled-radiation-integration.json) records a real three-source coupled solve at 1 kHz. The conformed exterior had 1,621 nodes, 3,246 triangles and no open edges or orientation errors. The solver produced interior pressure, BEM pressure/normal derivative, driver velocity/current and two polar pressure sets.

The pinned production BEM path uses FP32. Its independent circuit-voltage residual was about `5.4e-8` and electrical reciprocity residual about `1.5e-7`, so it **fails** the current strict `1e-8` consistency criterion. A historical FP64 reference run, produced by the older runner without a recorded Julia identity, reduced the circuit residual to about `1.3e-16` but retained a reciprocity residual of `4.0e-8`, which **also fails** that criterion. This failure remains recorded. No tolerance was relaxed to obtain a pass.

The two paths differed by approximately 0.0026% in the polar-pressure matrix norm, 0.00049% in velocity and 0.032% in BEM normal derivative. Agreement between two precisions of the same formulation is not an independent acoustic accuracy comparison. Further mesh/quadrature/refinement analysis and declared observable-specific acceptance criteria are needed to determine the remaining reciprocity error.

The validation-only runner uses the upstream public `CoupledReferenceBackend` and result writer APIs without modifying the pinned checkout. Run it with the external Boundary Lab Python environment and the adapter's saved, versioned request:

```sh
/path/to/boundary-python -I validation/fixtures/run_coupled_reference.py \
  runs/radiating-system/project.blab.json runs/solve/request.json runs/fp64-reference \
  --julia /path/to/julia-1.12.6
```

This research runner is separate from the durable production adapter. It has no integrated scheduler or process-tree timeout supervisor; use a bounded worker when automating it. It explicitly labels the reference backend and holds static condensation enabled for this comparison.

The source circuits remain synthetic. Driver internals, actual frames/motors and throat rear loading are absent. There is no mesh/band, nonlinear, structural, measured speaker or print qualification. This stage supplies executable radiation infrastructure and diagnostic evidence, not a release-qualified loudspeaker.

## Exterior mesh sensitivity

A historical three-level study held the FEM source meshes and project definitions fixed while reducing exterior target spacing from 20 to 15 to 10 mm. The conformed surfaces contained 3,246, 3,834 and 5,990 triangles. Those runs at 500/1,000/2,000 Hz passed the checks available at the time, but predate the current runtime, CAD and compiled-mesh binding contract. The [machine-readable study](../validation/reports/exterior-refinement.json) preserves input mesh hashes, evaluation identities, independent electrical checks and per-quantity comparisons.

In that historical report, across horizontal and vertical polar cuts and all three separately excited sources, the largest successive magnitude changes were 0.0543 dB (20→15 mm) and 0.0425 dB (15→10 mm); phase changes were 0.509° and 0.680°. No gain or phase was fitted. The comparison excludes samples at or below 0.001 times each source's reference peak and reports their count; none of these polar samples was excluded. Smaller mesh spacing did not monotonically reduce every error estimate, so these differences are sensitivity observations, not a demonstrated asymptotic error bound.

All three runs still fail the existing strict electrical consistency criterion. The interior discretisation and angular grids were fixed, only three frequencies were sampled, and no independent acoustic solver or physical speaker was compared. This study does not establish full-band convergence or qualification. Earlier runs that finished frequency output but failed macOS process cleanup remain failed; the historical study used completed evaluations that still require regeneration under the current contract.

Reproduce the comparison with `validation/fixtures/compare_exterior_refinement.py`, passing three `--run PROJECT EVALUATION` pairs in coarse-to-fine order and a new `--output REPORT` path. It checks current evaluation integrity and requires identical project definitions, FEM mesh hashes, backend, phase, frequency and excitation identities. It refuses to overwrite an existing report. Independent tests verify that known gain/phase changes are retained and that weak sources are not hidden by louder sources in the null policy.

Refinement comparisons now require matching originating design and CAD identities,
with the evaluated exterior mesh bound to its compilation report. Each run retains its full STEP byte hash for integrity, while cross-run identity
uses the STEP data section with timestamp-bearing headers and OCCT-generated
product-label counters excluded. Geometry entities and coordinates remain hashed. The standard
compilation workflow can therefore regenerate the same geometry for each level. Historical reports without this
evidence remain historical experimental observations and cannot pass the current
comparison gate; regenerate the compilation evidence before a new comparison.

The archived FP32/FP64 comparison is historical evidence only: its reference runner
hash predates the current Julia identity gate. It is not current pinned-runtime
evidence. A fresh reference run and regenerated comparison remain required;
no new numerical result is claimed here.

All numerical values in the archived exterior refinement report are historical.
That report predates the current runtime, observable, compiled-mesh and CAD identity
gates; its runs must be regenerated before it can support a current-contract
mesh-sensitivity claim. The new reference runner requires Python 3.11 and records
the complete installed package inventory, alongside Julia and checkout identity.
Package inventories must match when comparing precision or refinement; the runner
does not claim a fully locked Python environment.

New exterior compilations also record the host Python, CadQuery/OCP, Gmsh and
NumPy versions and generator source digests. Exterior-only comparisons require
these host identities to match, independently of the external solver runtime.
Comparison reports bind project hashes to the checked snapshot and record the
comparison runner digest. Older records without these fields require fresh runs
before they can satisfy the current comparison contract.
