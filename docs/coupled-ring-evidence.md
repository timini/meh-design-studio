# Executed four-driver ring coupling

Source `aea3256`, pinned Boundary Lab `8cb166226e412877d3f71f2845918e479b97aa85`,
Julia 1.12.6, CPU, one requested Julia thread. A detached clean source worktree
was retained while the next implementation increment proceeded independently.

The compact four-side-driver ring plus throat completed full FEM/BEM solves at
1000, 2000 and 3000 Hz. Each sample retains the full 5×5 voltage-to-motion/current
matrices, interior fields, exterior boundary traces and horizontal/vertical
pressure polars. Nonzero off-diagonal motion demonstrates induced motion of
nominally unexcited drivers in the shared horn. Four explicit rear-air domains
and the actual exterior BEM mouth interface were included.

[Machine-readable report](../validation/evidence/coupled-ring/report.json) and
[raw run archive](../validation/evidence/coupled-ring/raw-run.zip) retain original
files, identities, runtime details and the exact original runner. The runner's
absolute runtime/worktree locations must be substituted for reproduction; original
raw files contain their original paths and have not been relabelled.

This is topology/pipeline evidence, not a frequency-response qualification: three
samples cannot establish passband ripple. The synthetic circuits and prices are
not commercial-driver data. Strict electrical consistency remains unsupported at
the pinned solver's complex64 output precision; its 1e-8 complex128-only gate was
not weakened. No mesh convergence or physical measurement claim is made.

The general ring uses radial cylindrical ducts and ideal source disks. It does
not retroactively turn R1's different wall-normal transitions into a coupled or
optimised design. Freeform shapes, adaptive search, high crossover/directivity
objectives and the actual affordable-driver design remain subsequent work.
