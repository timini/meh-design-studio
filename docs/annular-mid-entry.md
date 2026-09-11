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
