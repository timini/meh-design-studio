# Explicit curved mid diaphragms

`HornGeometry.diaphragm_profile_m` replaces the flat mid disks with explicitly
specified, axisymmetric moving surfaces. The same surface determines front air,
rear air, the reserved driver gap, source tags and exterior closure. This makes
cone depth part of the solved geometry; T/S parameters alone do not supply it.
Existing designs omit the field and retain their previous identities and shape.

The values are Bezier height controls in metres at uniformly spaced radii from
the axis to `front_radius_m`. For example, `[0.010, 0.010, 0.005, 0.0]` describes
a smooth depression into the rear enclosure, with its rim on the existing source
reference plane. This is a synthetic example, not a Faital cone measurement.
There must be four to nine nonnegative controls, a positive centre, equal first
two controls for a flat centre tangent, and a zero rim. Heights are limited to
100 mm. The resulting radius is monotonic, so the surface is a graph without
folds or an overhang. These are control points, not interpolation samples.

The source translates rigidly along the existing motion axis. Its effective area
remains the projected disk `pi * front_radius_m**2`, matching the source circuit's
Sd. The curved surface has a larger actual area. Meshing checks both areas
separately against CAD at the existing one-percent limit. The native solver
already projects each surface normal onto the motion axis for velocity flux and
pressure force; it does not apply uniform normal velocity to the cone.

The rear air is an axial sweep of the curved source through `rear_depth_m`.
Consequently its rigid termination is a translated copy of that profile, and its
volume remains `Sd * rear_depth_m`. The printed cup's flat exterior encloses that
exact curved termination. This choice supports the existing source-face layered
mesh, whose volume and overlap must still agree with exported CAD. It does not
silently substitute a flat-ended cylindrical cavity or a lumped compliance.

Full geometry retains all physical drivers. XY reduction clips the curved source
at the same symmetry planes as the air, checks its actual half-area and retains
the projected half-area and physical coil multiplicities independently. Cleaning
the periodic revolution seam prevents a source from being split into two tags
when its retained half crosses that seam.

The geometry tests compare added front volume with an independent polynomial
integral, verify rear and reserved-gap volumes, check air/material separation,
and execute full and quarter five-driver meshing, interior compilation and closed
exterior generation. Numerical acoustic evidence for this new family must be
reported separately from those preparation checks.

Public CAD sections or measured profiles can inform the explicit controls, with
their source and fitting uncertainty recorded in experiment provenance. No cone
profile is inferred from a driver name, Sd or an outline drawing. Basket and
motor displacement, surround flexibility, breakup, mounting hardware and source
qualification remain separate modelling work. This change is not a claim that
an existing commercial candidate fits its purchased drivers or meets its response
target.
