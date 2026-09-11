# Explicit mesh workload limits

The original fixed resource caps prevented a larger target-band geometry and a
third finalist refinement from running. Geometry inputs now accept explicit
computing limits:

```json
{
  "maximum_tetrahedra": 3000000,
  "maximum_exterior_triangles": 16000
}
```

Defaults remain 2,000,000 tetrahedra per air region and 8,000 exterior triangles.
Default fields are omitted from canonical serialization, preserving old design
identities. Explicit nondefaults are part of the immutable candidate and its
geometry hash. The bounded supported maxima are 10,000,000 and 32,000 respectively;
these are workload limits, not a guarantee that the solver fits available memory.

Both the conservative pre-mesh estimate and actual tetrahedral count enforce the
selected per-region limit. Exterior counts are checked both before and after
native interface conformity. Mesh and exterior reports record the selected
limits. The meshing algorithms and spacing do not change when a cap increases.

Source-area, CAD-volume, surface-topology, native-interface and acoustic acceptance
limits remain unchanged. Increasing a computing budget cannot turn a failed
numerical comparison into a pass. Original failed runs remain failed; larger-budget
experiments have new input identities and directories.

The first larger reported-mid experiment generated 14,036 exterior triangles at
10 mm and 11,376 at 15 mm; both exceeded the old 8,000 limit. The adaptive finalist's
first two mesh levels completed and agreed within 0.0063 dB and 0.137 degrees at
five samples. Its third level was refused by the conservative estimate. Those
observations motivate configurable resource limits; they do not establish complete
convergence or physical performance.

## Preserved failed refinement study

The adaptive freeform winner was re-evaluated at 1,000, 1,414, 2,000, 2,449 and
3,000 Hz with frozen gain, using source `2b21d93`. The 8 mm and 6 mm levels
completed: maximum successive pressure change was 0.00630 dB and 0.1368 degrees.
The requested 4 mm level stopped at the original two-million estimated-tetrahedron
budget. **The three-level study failed; no convergence pass is claimed.**

[Original report and raw level archives](../validation/evidence/adaptive-finalist-incomplete/)
retain both completed levels and the failed third attempt. They use the historical
source and mesh policy, before the configurable caps and curved-rim fix. New code
or larger budgets do not retroactively turn those records into successful runs.

## Separate raw exterior preparation limit

A finer mouth can make the temporary exterior surface much larger than the final
conformed BEM mesh. `maximum_raw_exterior_triangles` optionally permits up to
64,000 triangles at this preparation stage. `maximum_exterior_triangles` continues
to limit the final conformed mesh, with its existing 8,000 default and 32,000
supported maximum. For example, a raw limit of 64,000 and final limit of 16,000
allows preparation to proceed but still rejects a final 16,001-triangle surface.

Omitting the raw limit uses the existing final limit at both stages and preserves
legacy serialization and candidate hashes. Explicit raw limits are hashed with
the candidate and recorded in the exterior report alongside the final limit.
No triangulation, protected mouth facet, topology or volume check changes.
The commercial 3 mm refinement exposed this need when its temporary surface
contained 41,972 triangles and failed the original 32,000 preparation limit.
That failed attempt remains preserved; an expanded preparation budget is a new
experiment, not a retrospective pass.

The separate retry from source `7e2cc14d96d320ff5e99fd0b2046d7657882ac03`
now prepares successfully: 422,377 total tetrahedra, 41,972 raw exterior triangles
and 12,464 final exterior triangles, below its declared 750,000 / 16,000 final
limits. The original three FEM meshes and raw exterior mesh are byte-identical
between the failed and successful attempts. Exterior volume differs from CAD by
0.192%, within the unchanged 2% limit; protected mouth facets and topology checks
pass. [Raw preparation evidence](../validation/evidence/raw-exterior-preparation/report.json)
retains both attempts and verifies every archived file. This archive contains no
new frequency solve and makes no acoustic convergence claim.

## Axial refinement inside rear cavities

`rear_axial_mesh_size_m` optionally refines the mesh along each cylindrical rear
cavity's motion axis. For example, `0.0005` requests layers no more than 0.5 mm
apart while `mesh_size_m` continues to control the cross-section and front horn.
Omission preserves the original unstructured mesher and geometry identity.
The setting must be at least 0.1 mm and no larger than `mesh_size_m`.

The mesher extrudes the actual imported source face into linear tetrahedra. It
checks the new volume and its intersection with the original CAD at the existing
1 ppm tolerance, so a wrong direction or a different cavity shape is rejected.
This supports full and quarter models, including tilted drivers. It changes
neither the physical rear cup nor its exterior scattering surface. Tests verify
that enabling it leaves the front FEM mesh byte-identical.

The actual source triangulation determines the layer workload before the 3D mesh
is generated. Both that count and the final tetrahedral count must fit
`maximum_tetrahedra`. The region report retains the layer count, actual spacing,
source triangle count, CAD overlap and mesher identity. Fine layers can increase
memory requirements; a region count is not a whole-solver memory guarantee.

This option addresses an observed longitudinal standing-wave discretisation
error in the ideal 70 mm sealed rear cylinder. An independent P1 calculation on
the original commercial 4 mm mesh reproduces its coupled-native rear impedance,
but differs from the analytic cylinder impedance by over 400% at 7.5 kHz. The
prepared isotropic 3 mm rear meshes still differ by about 94%. An exploratory
0.5 mm axial mesh reduces that isolated error to 0.84%, retaining a 4 mm
cross-section target. These comparisons are numerical diagnostics, not measured
driver performance or whole-horn convergence.

The regression solves the independent P1 Helmholtz equations on a generated
layered cylinder at 350, 2,000, 5,000 and 7,500 Hz and compares its force/velocity
impedance with `i rho c S cot(k L)` for the native `exp(-i omega t)` convention,
at a 2% relative limit. This is the distributed sealed-cylinder solution, which
retains its longitudinal resonances; a low-frequency compliance approximation
would not suffice. See the [IIT Kanpur tube-acoustics lecture](https://archive.nptel.ac.in/content/storage2/courses/112104176/pdf/31.pdf).
The test does not qualify arbitrary cavities, cone/basket geometry, damping,
front/BEM meshes, response flatness or printing. The commercial coupled
comparison remains a separate required experiment.
