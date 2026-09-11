# Quarter-mouth rim classification

A large quarter-model mouth with a thin rim can fail native conforming even
when the FEM and BEM opening geometry agrees. The pinned conformer's default
classification tolerance scales with mouth diameter. At a mirror cut, the
midpoint of a short rim connector can fall inside that tolerance and be mistaken
for part of the opening. The resulting opening path then ends at the outer rim.

The generated XY adapter now identifies opening edges from shared mouth/rim
mesh topology. For every other boundary edge of the planar rim, it measures the
midpoint's distance to that opening. It passes the smaller of the upstream
default and half the minimum distance through the public geometry_tolerance
argument. This tightens classification without changing FEM coordinates,
protected exterior facets, upstream code, seam/merge tolerances or final
interface and volume criteria. If the more restrictive geometry check fails,
the candidate remains a failure.

The original commercial seed had a 3 mm rim. Its connector midpoint was 1.5 mm
from the opening, within the default 1.5556 mm tolerance. Native conforming
therefore reported a 3 mm perimeter disagreement. The topology-derived tolerance
is 0.75 mm. A retained-input diagnostic with that stricter value completes at
8,064 exterior triangles, preserves protected facets, restores exact FEM/BEM
mouth membership and passes the original 2% CAD-volume check at 0.19199% error.
The original failed inputs and report remain unchanged. This is an interface
preparation check, not an acoustic frequency solve or physical qualification.

The production adapter at `188a933137c3d11f9df7bb7fa35c7f188827a6e1`
passes three retained-input regressions: this thin-rim commercial quarter, the
earlier valid quarter and the earlier full model. The latter two reproduce their
previous conformed meshes byte for byte, at 2,612 and 2,690 triangles respectively.
All three pass exact interface, protected-facet and original volume checks.
The non-CAD suite passes 838 tests, with three platform/version skips.

The [evidence report](../validation/evidence/quarter-rim-classification/report.json)
indexes a [15,111,940-byte archive](../validation/evidence/quarter-rim-classification/evidence.zip)
with SHA-256 `34397b7169e9f65449ebfe331b0e8745bc95a9cd51ded7991c26fafedcc67d0b`.
Its 40 verified members preserve the failed commercial inputs and conformer
report, standalone diagnosis, production checks, scripts and test log. The
separate commercial evolutionary search is not included while it is running.
