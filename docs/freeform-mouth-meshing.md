# Curved mouth edge meshing

The first adaptive search's random exploration candidate exposed an integration
failure: separate coarse FEM/BEM polygons of the same curved STEP mouth differed
by 0.9725 mm, exceeding the native 0.8022 mm conformity limit. Its original failed
trial remains unchanged in the adaptive-search evidence.

For freeform profiles, exterior generation now samples each shared mouth boundary
curve with a transfinite edge count targeting half the smaller FEM/exterior mesh
spacing. Exterior face targets, authoritative FEM facets, native conformity
limits and topology/volume checks are unchanged. This resolves the curved edge
before the native command replaces the BEM cap with the exact FEM facets.
Conical geometry retains its existing mesh policy.

Native recompilation of the original failed candidate and original FEM input
completed with the new edge sampling. The exported surface and final conformed
surface passed existing topology/volume checks, and the cap exactly matched FEM
triangle membership. The independent CAD regression checks both directed rim
polygon deviations against 0.5 mm, stricter than that failed native tolerance.
The existing freeform CAD case also passes; 589 non-CAD tests pass with 3 platform
skips. One bounded review found no material issue.

The edge count is a sampling target, not a guarantee for all future spline
curvatures. Every generated candidate still passes the native acceptance checks
or remains a recorded failed trial. No acoustic score is assigned by this mesh
repair, and the original failed search result is not replaced or reranked.
