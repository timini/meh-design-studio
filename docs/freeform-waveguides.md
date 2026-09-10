# Freeform waveguide geometry

`HornGeometry.profile_sections` extends the generated acoustic/build model beyond
cones. Each section specifies an axial fraction and eight positive radial scales
at 0°, 45°, …, 315°. A periodic interpolating spline forms each section and a smooth
CAD loft connects the circular throat to those sections. Two to eight sections
are supported; the final fraction must be 1. Empty controls retain the original
conical model and its content identity.

`examples/freeform-ring-geometry.json` is a small, explicitly unoptimised five-driver
example with different horizontal and vertical flare. Unequal opposite controls
also permit asymmetric profiles. These are actual 3D CAD surfaces: air, material,
entry chamber positions, tagged meshes and exterior radiation share the same
parameter record. `SearchBrief.profiles` can include multiple profiles (including
an empty conical baseline), so existing native searches evaluate distinct shapes.
Adaptive mutation and off-axis scoring are the next integration increment.

The mouth need not be circular. Its interface is identified by the actual planar
CAD cap and exported into the exterior envelope. Saved mesh facets are checked
against that cap's area and conformed to the authoritative FEM mouth mesh. The
existing 1% area, 1 ppm CAD-import volume and 2% exterior mesh-volume limits remain.

Spline solids require adaptive volume integration: OCCT's default fixed quadrature
changed the apparent volume of an unchanged test envelope by 0.019% after a mouth
split. Adaptive integration at 1e-9 relative tolerance agrees to better than
1 ppm. The freeform mesher retains imported STEP snapshots used for this check.
This corrects integration, rather than changing the acceptance threshold.

The grammar has a straight axis and planar source/mouth interfaces. It does not
represent every possible waveguide, folding, a real cone surface or an HF phase
plug. Chambers are placed outside the entire nearby profile envelope and retain
cylindrical ports. Radius controls do not guarantee monotonic flare or a minimum
normal wall thickness. CAD containment, part/air overlap and mesh checks reject
invalid candidates; structural and print qualification remain separate. The
mesh-work estimate is heuristic with a final actual-count guard.

Do not call the example a Solana equivalent or an acoustically optimised design.
Performance requires real coupled solves, common-fidelity finalist validation and
calibrated measurements of the selected driver/build combination.

The first native freeform ring evaluation completed at 1000, 2000 and 3000 Hz
using frozen source `f595a31` and the same pinned solver as the conical ring run.
[Report](../validation/evidence/freeform-ring/report.json) and
[raw evidence](../validation/evidence/freeform-ring/raw-run.zip) preserve the full
five-source fields, current/motion matrices and horizontal/vertical polars.
The three samples establish coupled execution on the non-circular geometry;
they neither establish response flatness nor show that this shape is improved.
Complex64 storage remains unsupported by the unchanged strict electrical gate.
