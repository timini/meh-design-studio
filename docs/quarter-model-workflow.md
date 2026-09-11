# Mirror-reduced geometry and optimisation

Set `"solver_symmetry": "xy"` in the geometry JSON to request an even quarter
model. The default remains `"off"`, including for asymmetric shape exploration.
The same export, mesh, compile-radiating and optimisation commands consume this
setting; it is part of candidate identity and survives mutation and replay.

Full physical CAD, driver inventory, material quantities and geometry exports
remain complete. The mesher checks the actual front-air CAD against both mirrors,
checks paired rear chambers and their remaining mirror, then clips representative
air regions to positive X/Y. Quarter volumes and adaptively integrated source
areas must match their physical fractions within `1e-6`. Saved linear source
facets retain the existing 1% area check. Failed partition or mesh preparation is
recorded in `analysis/mesh.json`.

The exterior envelope independently passes the two CAD mirror checks. Its X/Y
cut faces are omitted from the BEM surface, while the FEM cut faces remain rigid
symmetry boundaries. A diagnostic fourfold reflection must be closed, connected,
manifold and consistently oriented. The native triangle budget applies to the
actual quarter surface; the diagnostic reflection is not sent to the solver.
Only symmetry-plane roundoff below `1e-12 m` is snapped in that diagnostic copy.
The FEM/BEM mouth conformer receives the same explicit XY mode and retains its
existing protected-wall and exact shared-facet checks.

The compiler independently reads the saved moving meshes to verify that the
central quarter diaphragm represents one physical HF coil and each retained
half mid diaphragm represents two physical coils. A four-mid ring therefore has
three voltage ports and five physical drivers. All mirror partners receive equal
voltage; independent excitation of one member of a pair requires the full model.
The [bank scorer](mirror-bank-scoring.md) sums all physical receiving currents
without multiplying already-complete group excitation or pressure again.

For freeform evolution, use `profile_symmetry: "mirror_xy"` or `"quarter_turn"`
with `periodic_cubic` interpolation. Unconstrained azimuthal mutations cannot be
combined with quarter reduction. This preserves noncircular, axially varying
shapes while keeping the requested mirror relationships. CAD checks still run
on every candidate; symmetry is not accepted from the control label alone.

## Matched-discretisation native check

The retained 4 mm quarter mesh was reflected across Y to produce an X half
model with identical element shapes, source areas and volumes. Matching
excitation groups and observation coordinates isolate symmetry reduction from
the independently meshed full-reference discrepancy. Both use the frozen
application source `25e69a8575077df2c533ccab6db13ee4a823cc53`, FP64 coupled FEM/BEM
and 350, 1,000, 2,000 and 3,000 Hz.

| Check | Maximum difference | Declared limit |
| --- | ---: | ---: |
| Corresponding complex observation/transducer vectors | 0.00112979% | 2% |
| Parallel-bank complex impedance | 0.0000232483% | 2% |
| Electrical checks, both models | Pass | `1e-8` |

The half model contains 216,608 tetrahedra and 6,656 exterior triangles. Its
native evaluation took 227.92 seconds. The first attempt failed before solving
because its volume mesh was Gmsh 2.2. Conversion to required Gmsh 4.1 ASCII
preserved every coordinate, cell connectivity and physical group without
remeshing; the failed attempt remains archived.

The [matched-reduction evidence](../validation/evidence/matched-mirror-reduction/report.json)
contains the protocols, original failure, conversion checks, raw native fields
and comparison. This and the [4/3 mm refinement](mirror-bank-scoring.md) support
this tested reduction. They do not establish commercial-band convergence,
physical acoustic accuracy, purchased-driver fit or Solana-equivalent output.
Older failed full/quarter comparisons remain unchanged.
