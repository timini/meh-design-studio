# Isolated rigid-exterior enrichment at 4 kHz

Splitting each rigid exterior triangle into three coplanar triangles changes the
annular common-mid complex pressure by **0.496418%** relative to the fully refined
baseline. Front/rear FEM meshes and mouth facets are unchanged. This tests the
rigid-surface discretisation on a fixed polyhedral shape; it does not qualify
exterior geometry, the mouth, the interior field or an acoustic design.

The surface grows from 3,332 to 4,964 triangles. Each added vertex is its parent
triangle's centroid; old edges and original vertices remain. Independent checks
confirm unchanged FEM mouth membership, closed oriented topology after XY
reflection and less than 1e-12 relative enclosed-volume change. A declared
10,000-triangle compute cap accommodates this diagnostic. No numerical accuracy
limit was changed.

| Quantity | Relative change from refined baseline |
| --- | ---: |
| Diaphragm velocity basis | 0.00367438% |
| Voice-coil current basis | 0.00053890% |
| Horizontal pressure basis | 0.49004951% |
| Vertical pressure basis | 0.50186807% |
| Common-mid pressure, combined H/V | 0.49641784% |

Changes are complex L2 differences divided by baseline norms. Common-mid pressure
sums the two mid-pair voltage bases once, including induced throat motion. The
historical whole-mesh change of 51.07% remains failed; its denominator differs,
and these tests are not an additive decomposition of that error. Surface edges,
mouth tessellation and curvature are not refined here. This result alone cannot
attribute the original discrepancy to the interior mesh.

Both this run and the retained baseline use identical native runtime identities,
FP64 `coupled_reference`, effective 2/2 integration, circuits and the exact same
4 kHz request. The new solve completed in 38.67 seconds. Its native assessment
and electrical equations pass at the unchanged 1e-8 electrical limit. Application
source is `a31597a8c320dd751d19e2d0bb625edc0d962a7e`; Boundary Lab is pinned to
`8cb166226e412877d3f71f2845918e479b97aa85`.

## Reproduce

With NumPy and meshio installed, retain this directory and the adjacent
`annular-fixed-quadrature` directory, then run from the repository root:

```sh
python validation/evidence/annular-isolated-exterior/reproduce.py
```

The portable script checks both complete archives and member inventories,
project/mesh identities, unchanged physical inputs and request, identical native
runtime/settings, and retained electrical evidence bound to the project and
evaluation hashes. It independently reconstructs every centroid subdivision from
the baseline mesh and compares its vertices, oriented faces and physical tags.
All unchanged mesh hashes are verified. Raw complex differences reproduce the
recorded values; no native solver is invoked.

`evidence.zip` retains the full native result, preparation/comparison scripts,
requests, meshes, topology report and original logs. `derivation.json` records
parent and derived identities. The unchanged parent compilation is stored under
`parent-input/compilation.json`; this manual diagnostic is not a resumable
compiled search candidate. Electrical validation was performed in the original
run directory; portable reproduction binds that retained report but does not
rerun the path-bound native verifier. No physical measurements or print
qualification are claimed.
