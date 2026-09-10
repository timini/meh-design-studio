# Freeform precision and quadrature study

The archived [report](../validation/evidence/freeform-reference/report.json) and
[raw reference runs](../validation/evidence/freeform-reference/raw-reference-runs.zip)
compare the same five-source freeform geometry at 1000, 2000 and 3000 Hz. The
shared CAD, meshes and production basis are in the earlier
[freeform archive](../validation/evidence/freeform-ring/raw-run.zip). Application
source was the clean detached `f595a31` worktree. The first reference used its
unchanged runner; the second used the archived, separately hashed runner with
regular and singular quadrature orders raised from 2 to 4. All used the pinned
Boundary Lab revision and identical Python/Julia package versions. The production
run used one Julia thread; references used four. The reference runs are native
raw results, not relabelled production adapter evaluations.

All three cases **fail** the existing electrical consistency gate. FP32 storage
cannot satisfy its complex128 requirement. FP64 reduces the circuit residual
below 2.4e-16 and retains positive Hermitian admittance eigenvalues, but its
reciprocity residual is 4.54e-8 at 1 kHz and 1.21e-8 at 3 kHz. Higher quadrature
changes those residuals to 4.02e-8 and 1.26e-8; it does not resolve the failure.
The tolerance remains 1e-8.

Across all five independently excited sources and both complete polar cuts,
FP32-to-FP64 changes reach 0.00788 dB and 0.0433 degrees. Raising quadrature in
FP64 changes them by up to 0.1495 dB and 0.689 degrees. No fitted gain or phase
was applied; no samples were excluded by the declared relative-null policy.
These are numerical sensitivity observations on three frequencies, not a mesh
convergence result, independent acoustic reference or measured loudspeaker test.
The remaining reciprocity discrepancy requires investigation of discretisation
and coupling; increased floating-point precision alone is insufficient.
