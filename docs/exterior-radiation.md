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

The pinned production BEM path uses FP32. Its independent circuit-voltage residual was about `5.4e-8` and electrical reciprocity residual about `1.5e-7`, so it **fails** the current strict `1e-8` consistency criterion. A separate FP64 reference run reduced the circuit residual to about `1.3e-16` but retained a reciprocity residual of `4.0e-8`, which **also fails** that criterion. This failure remains recorded. No tolerance was relaxed to obtain a pass.

The two paths differed by approximately 0.0026% in the polar-pressure matrix norm, 0.00049% in velocity and 0.032% in BEM normal derivative. Agreement between two precisions of the same formulation is not an independent acoustic accuracy comparison. Further mesh/quadrature/refinement analysis and declared observable-specific acceptance criteria are needed to determine the remaining reciprocity error.

The validation-only runner uses the upstream public `CoupledReferenceBackend` and result writer APIs without modifying the pinned checkout. Run it with the external Boundary Lab Python environment and the adapter's saved, versioned request:

```sh
/path/to/boundary-python -I validation/fixtures/run_coupled_reference.py \
  runs/radiating-system/project.blab.json runs/solve/request.json runs/fp64-reference \
  --julia /path/to/julia-1.12.6
```

This research runner is separate from the durable production adapter. It has no integrated scheduler or process-tree timeout supervisor; use a bounded worker when automating it. It explicitly labels the reference backend and holds static condensation enabled for this comparison.

The source circuits remain synthetic. Driver internals, actual frames/motors and throat rear loading are absent. There is no mesh/band, nonlinear, structural, measured speaker or print qualification. This stage supplies executable radiation infrastructure and diagnostic evidence, not a release-qualified loudspeaker.
