# HF body and overhanging mid chambers

An optional `throat_body` describes a rigid cylindrical HF package behind the
throat. Its `radius_m` and `depth_m` are explicit SI dimensions. The package runs
from `z = -depth_m` to the throat plane at `z = 0`; its radius must cover the
throat aperture and wall. Use a conservative envelope including any required
assembly clearance.

[The five-driver example](../examples/five-driver-throat-body-geometry.json)
places concentric mid entries 20 mm along the horn. Their chambers extend behind
the throat plane and clear a 45 mm radius, 50.8 mm deep HF envelope. The previous
axial-plane restriction alone rejected this arrangement.

When a body is declared, CAD collision checks replace that lower axial-plane
restriction. Mid air, printed parts and the reserved diaphragm gap must all avoid
the body. Mouth-plane clearance, port clearance, connected solids, chamber walls,
mesh limits and source-area checks still apply. Omitting the body preserves the
previous geometry constraints and serialised design identity.

The same cylinder is included in the closed exterior BEM envelope. Adding it
therefore requires a new exterior simulation, even when interior air is unchanged.
The geometry export includes `reference/throat-body.step` as a non-print reference;
it is excluded from printable parts and material costs. Driver cost remains part
of the BOM. Full and XY-reduced models retain all five physical drivers.

This feature represents the external package and checks geometric interference.
It does not describe compression-driver internals, mounting screws, terminals,
cone breakup or the real mid-driver basket. Those still require corresponding
geometry/source evidence. No acoustic improvement or print qualification follows
from the CAD checks alone.
