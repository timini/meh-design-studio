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
