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

## Retained native comparison

A separate FP64 coupled experiment at source
`4fc55f731c7159131d492cd38e348156edac284c` completes both the flat and curved
five-driver models at 350, 2,000 and 5,000 Hz. Both use the same synthetic
circuits, projected areas, 8 mm general mesh target, 2 mm rear layers and 20 mm
exterior target. Boundary Lab remains pinned at `8cb166226e412877d3f71f2845918e479b97aa85`.
Controls were recorded before preparation and solving. This compares two explicit
geometries; it does not isolate front curvature from the changed rear termination.

| Case | Tetrahedra | Exterior triangles | Electrical check, 1e-8 | Independent force balance, 1e-8 | Maximum C4 field error, 2% limit |
|---|---:|---:|---|---|---|
| Flat | 50,082 | 842 | Pass | Pass, 1.79e-14 | Pass, 1.799% |
| Curved | 60,042 | 870 | Pass | Pass, 2.73e-14 | **Fail, 2.127%** |

The force check independently finds each moving triangle's interior tetrahedron,
orients its area vector outward, projects it onto the motion axis and integrates
the retained complex nodal pressure. The completed front/rear forces agree with
`Bl * I - Zm * V` for every source excitation. The curved source therefore enters
the actual coupled equations; it is not only a visual CAD change.

The curved rotation failure occurs in the mid polar basis at 5 kHz. Its limit is
unchanged, and no mesh-convergence or accurate upper-band ranking is claimed.
The flat-to-curved changes in H/V complex pressure norm are about 10.52% at
350 Hz, 3.21% at 2 kHz and 0.65–1.20% at 5 kHz. These are descriptive changes,
not improvements or acoustic acceptance results.

The [evidence report](../validation/evidence/curved-mid-diaphragms/report.json)
indexes 147 SHA-verified archive members, including both native runs, controls,
geometry exports, source-force checks, the failed rotation check, comparison
scripts and the upstream licence. The source, tests and failed result remain
distinct from later commercial-driver work.

Subsequent export integration also found collapsed empty pole facets in the
curved cups. The [material exporter](material-export-tolerance.md) now removes
only those collapsed facets and validates closed, oriented STL geometry before
preparing a solver input. The archived native experiment retains its original
files; it is not a corrected build bundle.
