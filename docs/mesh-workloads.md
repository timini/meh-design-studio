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
