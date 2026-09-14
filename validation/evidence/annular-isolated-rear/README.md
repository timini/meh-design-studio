# Isolated rear-mesh sensitivity at 4 kHz

Replacing only the refined annular model's two rear meshes with their original
coarse counterparts changes common-mid complex pressure by **0.009691%** relative
to the fully refined baseline. The earlier whole-mesh comparison remains failed
at 51.07%. Rear discretisation has little effect in this controlled comparison;
front/exterior discretisation still needs investigation. This is a sensitivity
result at one frequency, not a converged acoustic design.

The experiment retains the refined front and conforming exterior meshes byte for
byte. Historical coarse/refined project records differ only in mesh hashes:
physical geometry, circuits, boundary definitions and observations are identical.
The new project explicitly declares the replacement rear mesh hashes. No old
project, native result or failure was rewritten. The same baseline request uses
FP64 `coupled_reference` and effective 2/2 boundary integration.

| Quantity | Change relative to fully refined baseline |
| --- | ---: |
| Diaphragm velocity basis | 0.000712787% |
| Voice-coil current basis | 0.000132051% |
| Horizontal pressure basis | 0.000089531% |
| Vertical pressure basis | 0.000088651% |
| Common-mid pressure, H/V combined | 0.009691014% |

These are complex L2 differences divided by the refined baseline norm. The common
mid bank sums its two voltage-basis rows once without repeating symmetry counts;
induced throat motion remains included. These norms and the historical 51.07%
coarse-reference norm have different denominators, so they are not an additive
error decomposition. This test does not exclude interactions between domains.

Native assessment verification and the electrical check pass in the original run
directory at the unchanged 1e-8 electrical limit. The original 2% mesh/rotation
failures remain. Software source is `a1ce74dfc604da9441d012a38b729258a915c44e`;
Boundary Lab is pinned at `8cb166226e412877d3f71f2845918e479b97aa85`.
Runtime identities match except for equivalent absolute Julia executable paths
(one contains `meh-current/../work`). The comparator normalises that spelling
only; archived manifests are unchanged. The completed solve took 29.35 seconds.
The initial wrong-module CLI failure, before evaluation creation, is also retained.

## Reproduce without a native solve

Install NumPy, retain this directory and the adjacent `annular-fixed-quadrature`
and `annular-mid-entry` evidence directories, then run from the repository root:

```sh
python validation/evidence/annular-isolated-rear/reproduce.py
```

The script reads both ZIPs in memory, verifies archive/member hashes and complete
inventories, checks unchanged project fields, binds both replacement rear meshes to the
hash-verified historical coarse archive, checks the two changed mesh hashes,
identical requests and runtime/solver settings, and recomputes pressure/current/
velocity differences. It compares the numbers with `report.json`. It neither
extracts archive paths nor invokes native code. Original path-bound electrical
verification is retained evidence, not rerun by portable reproduction.

`evidence.zip` retains the native project, meshes, request, full output, logs,
original comparison script and provenance. `report.json` includes the member
inventory and electrical result. The adjacent archive supplies the fully refined
baseline; it is required rather than silently substituted. Portable reproduction
passed with exactly the recorded derived values. No solver rerun or relaxed
acceptance criterion was needed for this package.

The copied compilation record describes the **parent refined input**, not the
replacement project. Its exact original bytes are retained under
`parent-input/compilation.json`; `derivation.json` binds parent and derived project
hashes and records its original location. There is no derived compilation claim
or resumable search candidate in this manual diagnostic. The original run
directory remains untouched. Portable reproduction checks this derivation and
binds the reported electrical result to the archived comparison, project and
evaluation hashes.
