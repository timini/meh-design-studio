# Preserve FEM mouth coordinates through interface conversion

A mutation in the larger 350 Hz horn search failed the exact mouth-facet check
although its FEM and BEM interfaces had identical connectivity: 5,418 triangles
and 2,796 mouth vertices. The native conformer had merged 30 FEM vertices with
nearby annulus coordinates; the largest displacement was 9.061 nanometres. The
original failed trial remains unchanged and is not scored as a completed solve.

The pinned conformer appends FEM points after its remeshed annulus, then merges
vertices within `1e-8 m`. This can preserve the earlier annulus coordinate. The
application now retains that raw conformer output and restores each BEM mouth
vertex to its unique matching authoritative FEM coordinate. Matching must be
one-to-one within the same existing `1e-8 m` merge radius, and mapped triangle
membership must already match exactly. Ambiguous matches, changed connectivity
or larger discrepancies fail before publishing a corrected mesh.

Only coordinates of existing mouth vertices change; triangle connectivity,
physical tags and all other vertices remain unchanged. Shared rigid-surface
vertices move with the mouth, preserving connectivity. The normal exact mouth
check, closed/oriented surface checks, nondegenerate triangles and the existing
2% enclosed-volume check still run on the final mesh. No acceptance limit is
relaxed. The compiler records raw/FEM/final hashes, correction count and maximum
distance, and binds the final mesh into the project used by the native solver.

This is an interface-conversion correction, not a geometric mutation or evidence
of improved acoustics. Old results and failed adaptive ancestors retain their
original status; replaying that geometry is a distinct run with a new source
identity. The frozen active search is allowed to finish with its original code.

Fresh compiler replay from frozen source `f969e1d` completed successfully. It
recreated the same raw native mesh, restored the same 30 coordinates, and passed
exact interface membership, all surface checks, volume validation and saved
candidate reconstruction. The replay also enabled the 413-point spherical
observation setting, verifying that it survives compilation and candidate
identity checks. No acoustic solve was performed for this replay.

The [report](../validation/evidence/mouth-coordinate-restoration/report.json)
identifies both application sources and archives the original failed trial and
the new compilation, including complete geometry, meshes and exact replay
scripts. The original adaptive search remains a separate historical run.
