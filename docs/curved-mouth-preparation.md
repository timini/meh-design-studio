# Preparing strongly curved horn geometries

The full-size nonlinear seeds use the existing eight-control periodic spline
grammar: one has exponential axial radius controls and circular sections; the
other has quadratic axial radius controls and rounded-square sections. They are
spline lofts through those controls, not exact analytic flares between stations.
Both retain four mid sources feeding one horn and the provisional Peerless throat
model. CAD validity alone does not establish driver fit or acoustic performance.

The initial preparation failed in two places. The exponential seed generated a
225,596-tetrahedron front-air mesh, but the native conformer treated nearby curved
wall triangles as part of the flat mouth rim. Its inferred surrounding plane
then failed the existing geometry tolerance. The rounded-square seed was rejected
before front meshing by a 6.51-million-tetrahedron estimate against its 5-million
cap. The failures and exact source inputs are retained.

## Planar rim classification

The generated mouth lies at the design's declared axial length. A standalone
adapter, run inside the pinned Boundary Lab Python environment, checks both mouth
interfaces against that plane at `1e-8 m`. Only rigid triangles whose vertices
all lie in this plane are available for annulus remeshing. The remaining rigid
triangles receive a temporary protected physical group passed to the upstream
`conform_bem_interface_to_fem` API.

After conforming, the adapter requires the protected triangles' oriented
coordinate multiset to be unchanged, then restores their original rigid group.
It does not change upstream geometry or merging tolerances. The subsequent
authoritative FEM-coordinate restoration, exact mouth-facet comparison, closed
oriented exterior check, triangle cap and enclosed-volume check still apply.

The helper records its own source hash, both input hashes, the raw output hash,
classification counts and native conformer diagnostics. Radiating compilation
checks those bindings and records the result. The pinned upstream checkout is
unchanged. This adapter is for the generator's planar mouths; it does not claim
to conform arbitrary curved or disconnected interfaces.

## Workload estimation

The previous freeform multiplier used the largest and smallest radial scales
across *all* axial stations. That counted a strongly changing circular radius as
cross-section anisotropy: the exponential seed received a factor of 17.18 despite
having circular sections. Its estimate was 3.82 million tetrahedra, versus 225,596
in the actual generated front mesh.

The aspect multiplier now uses the largest ratio **within each cross-section**.
Axial radius and actual CAD volume remain in the existing workload calculation.
The estimate remains a heuristic, not a guaranteed upper bound. The actual mesh
element cap and quality, topology, volume and source-area checks are unchanged.
No acoustic convergence or acceptance criterion is relaxed by this correction.
