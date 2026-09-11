# Isolated candidate preparation

Optimisation now prepares each candidate in a fresh application Python process.
That child exports full CAD, checks the build budget, meshes the air regions and
compiles the coupled exterior. Native simulation and scoring stay in the parent
workflow, including any caller-supplied native resource checks.

A killed CAD kernel or abnormal child exit raises a candidate failure in the
parent search. It does not require the CAD process to reach a Python exception
handler. The existing search then records that failure and considers its next
proposal. The per-stage timeout also bounds the complete preparation process;
the existing cross-platform process-tree cancellation helper cleans up children.
This isolates process state and lifetime, not acoustic approximation or geometry
acceptance. It does not establish a hard memory quota.

Each attempt retains preparation-request.json, preparation.log and
preparation.json. A normally exiting child also writes preparation-child.json.
Requests bind the saved candidate, brief, complete application fingerprint and
native runtime identity. Both processes verify those identities, and the parent
checks every prepared artifact hash before allowing the solver to run. Complete
CAD, mesh and coupled-compilation reports are required. Source mismatches or
changed artifacts fail the attempt. Existing native and numerical verifiers
remain in place after preparation.

This change follows the first commercial quarter search. Its initial seed
exceeded the 16,000-triangle raw exterior preparation limit; subsequent proposals
failed CAD validity, symmetry, clearance or workload checks. The process exited
with code 137 during proposal 10, leaving its original search manifest marked
running. There was no Python traceback and no established termination cause.
The terminal observation and original partial files are preserved separately;
they are not rewritten as a successful or cleanly finalised search. No commercial
native evaluation completed in that attempt.

Real subprocess tests exercise abrupt exit without child finalisation and a
preparation timeout, then complete the next attempt in the same parent. Other
checks cover artifact tampering, forwarding observation settings and preserving
the over-budget estimate while stopping before meshing. Numerical and physical
qualification are separate from these reliability checks.

Nested native mouth conformers stay inside the preparation process group on
POSIX, so a parent timeout also kills a conformer that is still running. Windows
retains the enclosing Job Object containment. A real nested-process test verifies
group membership and that the nested process no longer runs after timeout.

The [interrupted commercial evidence](../validation/evidence/quarter-commercial-interruption/report.json)
contains the original unfinalised search, ten recorded candidate failures,
proposal 10's partial preparation and the external termination observation.

## Executed preparation checks

Using frozen source `4dadcfdeb8ede70f3723db5ab60a72a61bbc8961`, the retained valid
five-driver noncircular reference completes isolated CAD, meshes and coupled
compilation in 30.55 seconds. The parent verifies 48 prepared artifact hashes,
five physical drivers, three representatives and the XY mouth interface. No
native frequency solve is claimed for this preparation-only check.

The next twelve-proposal commercial attempt also uses that frozen source. Its
proposal 10 CAD child exits with signal 9; the parent records the failure,
continues to proposal 11 and finalises the search as failed because no candidate
completed a native solve. The first seed instead fails in native mouth conforming:
the reduced opening/rim perimeter selection needs a separate correction. These
results establish successful preparation and containment of an actual hard CAD
failure, without claiming a completed commercial acoustic search.

The [preparation and containment evidence](../validation/evidence/isolated-candidate-preparation/report.json)
archives both the successful reference and the twelve-proposal commercial
attempt, including the killed child's partial files, the next proposal's failure
report, immutable controls and source fingerprints.
