# Annular mid entry exploration

`HornGeometry.port_core_radius_m` optionally adds a conical central core and four
radial supports to each mid entry. The core's large circular face ends at the
front chamber inlet; its tip points toward the horn. Supports use `wall_m` as
their thickness, join the surrounding material, and are trimmed to the actual
horn flare. The diaphragm retains its declared front clearance and moving area.
Zero core radius preserves the original open circular duct and its design hash.

This adds a shape hypothesis for investigating the retained mid-band dips:
an annular collection opening can reduce differences between acoustic paths
from different diaphragm locations. It does not presume that this particular
core shape improves response. The core also changes channel area, inertance
and cavity loading, which must be evaluated together in the coupled solver.

The same boolean solids generate the material exports and air domain. The core
and supports become rigid FEM walls; source circuits and physical driver counts
are unchanged. The air remains connected through the chamber and horn. Concentric
entries are required, and the radial air gap must exceed the support thickness.
Flat and explicitly curved source faces, nonconical flares, and XY reduction can
be combined with the annular entry.

`port_core_radius_m` is an evolutionary geometry bound. Elite mutations and
random exploration retain their parentage and replay the resulting core radii.
The example [annular-entry-ring-geometry.json](../examples/annular-entry-ring-geometry.json)
is an integration fixture, not a selected commercial horn.

Checks cover an independently calculated four-channel inlet area, conservation
of air-plus-material CAD volume, unchanged source surfaces, saved material mesh
validation, and full/XY meshing and five-driver compilation. Trimmed cone solids
use adaptive CAD volume integration. No acoustic improvement, viscothermal loss,
cone breakup, purchased-driver fit, structural strength or print qualification
is established by these geometry checks.

## Retained coupled comparison

[Native evidence](../validation/evidence/annular-mid-entry/report.json) preserves
the declared comparison from source `381eb8c`, using the public FaitalPRO 4FE32
and provisional Peerless outlet circuits on the concentric nonconical horn.
Both cases use a 24 mm outer port radius. The annular case adds a 16 mm core and
four 3 mm supports. The 8 mm front mesh, 2 mm rear layers and 20 mm exterior
target deliberately make this a coarse screening experiment.

All three frequencies (700, 2750 and 4000 Hz) completed with the coupled FP64
solver. Plain/annular models contain 67,650/74,248 tetrahedra and 2,254 exterior
triangles each. Both pass electrical and independently reconstructed pressure
force equations at `1e-8`; maximum force residuals are `2.32e-15` and `1.30e-15`.

Neither case passes the unchanged 2% rotational field criterion. The plain case
reaches 2.12137% at 4 kHz. The annular case reaches 108.62022% there, with a small
mid pressure norm near a predicted dip. Its common-mid on-axis pressure changes
by +1.005 dB at 700 Hz, +0.056 dB at 2750 Hz and -21.923 dB at 4 kHz relative to
the plain case. Those are descriptive outputs of these coarse meshes, not an
accepted acoustic improvement or a trustworthy estimate of the 4 kHz dip depth.

The archive retains all fields, CAD/mesh exports, controls, source identities,
force/rotation checks and comparison scripts. No candidate is selected from
these three frequencies. Refinement, dense frequency sampling and the existing
commercial-source/physical checks remain necessary.

### 4 kHz refinement

[A separate refinement](../validation/evidence/annular-mid-refinement/report.json)
retains exactly the same 11 STEP geometries and circuits while changing the front
target from 8 to 6 mm and rear layers from 2 to 1 mm. The 20 mm exterior target
is unchanged, but the refined mouth interface increases the actual exterior
mesh to 3,332 triangles. Preparation first failed its 3,000-triangle compute cap;
that failure is preserved. A separate run reused the completed 149,441-tetrahedron
mesh with an explicitly declared 4,000-triangle cap. No acoustic limit changed.

Electrical and pressure-force checks pass; the maximum force residual is
`1.64e-15`. Rotational error remains 46.31383%, failing 2%. Coarse-to-refined
horizontal and vertical pressure changes are 12.08233% and 11.51388%, also failing
2%; velocity and current changes pass at 0.14911% and 0.02297%. The acoustic
field around this predicted dip remains numerically unresolved. This result
neither qualifies the annular candidate nor establishes a reliable dip depth.

### Equal-voltage shared mid bank

An [offline shared-bank diagnostic](../validation/evidence/annular-shared-bank/README.md)
sums the original mid-pair voltage bases without repeating a solve. At 4 kHz,
common-drive rotational errors are below 1% for both coarse cases and the refined
annular case. However, the annular common-mid field changes **51.07%** between
meshes. Common-drive symmetry therefore does not resolve the failed convergence
or qualify the dip. Original individual-basis checks and limits remain unchanged.

### Fixed-mesh integration sensitivity

A [controlled 4 kHz comparison](../validation/evidence/annular-fixed-quadrature/README.md)
holds the refined project and meshes fixed while raising boundary integration
orders from 2/2 to 4/4. A matched-runtime baseline reproduces the historical
fields within 2e-13 relative error. The common-mid pressure changes 0.117317%,
far below the earlier 51.07% mesh change; both electrical checks pass unchanged.
This points toward mesh discretisation as the larger unresolved issue for this
comparison, without identifying a domain or establishing acoustic convergence.

### Isolated rear-mesh sensitivity

A [separate controlled rear-mesh test](../validation/evidence/annular-isolated-rear/README.md)
keeps the refined front/exterior pair and replaces only the two rear meshes with
the historical coarse versions. At 4 kHz the common-mid field changes 0.009691%
relative to the refined baseline, with electrical validation still passing.
This leaves front/exterior discretisation as the larger unresolved concern in
the earlier whole-mesh comparison; it does not establish convergence or exclude
interactions between mesh domains.

### Fixed-geometry exterior enrichment

An [isolated rigid-exterior test](../validation/evidence/annular-isolated-exterior/README.md)
subdivides rigid surface triangles while preserving every FEM mesh and mouth
facet. Common-mid pressure changes 0.496418% at 4 kHz and electrical checks pass.
This is a limited surface-basis test on the same polyhedral shape: it does not
refine original edges, the mouth or CAD curvature, and cannot by itself assign
the original 51.07% discrepancy to the interior mesh.
