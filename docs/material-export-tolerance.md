# Absolute material tessellation and early export validation

The completed concentric-entry experiment exposed a build-export failure: its
horn STL volume differed from its CAD volume by 1.387%, exceeding the existing
1% limit. The native acoustic calculation completed, but completed-search replay
and the build bundle correctly rejected that STL. The original files and native
results remain unchanged.

The generic CadQuery STL exporter calls `Shape.exportStl` with its default
`relative=True`. Passing the design's millimetre tolerance into that API therefore
scaled it by edge size. The material exporter now meshes explicitly with absolute
linear deflection. For example, `tessellation_tolerance_m=0.0001` requests 0.1 mm,
independent of the horn's edge lengths.

The exporter checks OCCT's reported triangulation deflection against that request,
including the coordinate rounding required by binary STL. If necessary, it
tightens linear and angular deflection together, within five attempts. The
manifest records each attempt and the exporter source hash. An unsuccessful
attempt sequence fails instead of silently accepting a coarser mesh.

STL and 3MF use the same checked vertices and triangles. Exact coordinate welding
can collapse an empty triangle at a revolution pole; only facets containing a
repeated vertex are removed. There is no proximity welding, hole filling or
removal of nonzero-area facets. Remaining degenerate triangles, open/nonmanifold
or inconsistently oriented edges, and volume errors above 1% are still rejected.

These checks now run before publishing a successful geometry manifest, so a bad
print mesh stops candidate preparation before an expensive acoustic solve.
`validate_export` continues to provide the same independent check on saved files.
The new regression fixture is the exact design that exposed the original failure;
tests also compare its saved STL and 3MF triangle counts and volumes, and inject
an incorrect STL scale to verify that geometry preparation fails early.

This fixes numerical export fidelity. It does not qualify mounting interfaces,
seals, structural strength, slicing, a printer or the horn's acoustic response.
Retessellating material for an old experiment must be recorded as a separate
derived export; it must not rewrite that experiment's geometry hashes or claim
its native fields were generated from newer application code.
