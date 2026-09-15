# Front-volume sensitivity with fixed boundary facets

Remeshing only the annular front air volume changes the shared-mid complex
pressure by **133.9963%** at 4 kHz. Every tagged boundary facet, rear mesh and
exterior mesh remains unchanged. This exposes substantial front-volume numerical
sensitivity even with a fixed acoustic boundary. The model is not converged and
this experiment does not select a buildable horn.

The original front mesh has 64,181 tetrahedra. A separate 5 mm volume-remeshing
operation produces 80,834 tetrahedra while retaining the original discrete
surfaces. Both have positive tetrahedral volumes, manifold face incidence and
exact agreement between tetrahedral boundaries and declared surface triangles.
Tagged boundary coordinate facets match exactly. Both enclosed volumes are
0.0020326749275969397 m³. This is a fixed-boundary remesh, not a nested refinement
sequence or a study of boundary/CAD accuracy.

| Quantity | Relative change from retained refined baseline |
| --- | ---: |
| Diaphragm velocity basis | 0.296696% |
| Voice-coil current basis | 0.045021% |
| Horizontal pressure basis | 2.511592% |
| Vertical pressure basis | 2.684589% |
| Common-mid pressure, combined H/V | 133.996321% |

Changes use the complex L2 difference divided by the baseline norm. The common
mid sums its two voltage-basis rows once, including induced throat motion. Its
combined H/V norm changes from 0.143575 to 0.212282 Pa; the relative complex error
also includes phase changes. The full pressure basis includes the throat-source
excitation and therefore has a different denominator. These numbers and the
historical 51.07% whole-mesh comparison are not an additive error decomposition.
The unchanged 2% field screen is failed, and electrical consistency is not proof
of acoustic accuracy.

The first attempt cleared the discrete volume but generated zero tetrahedra.
That failed script, mesh and log are retained. The successful separate attempt
creates a volume bounded by the existing discrete surfaces. Its log warns that
old entity 1 is empty; all 80,834 tetrahedra belong to entity 2, selected by the
unchanged physical group 1, `air_front`. There are no unselected tetrahedra.

The native FP64 `coupled_reference` run completed in 32.22 seconds. Runtime
identities and effective 2/2 integration settings match the baseline, as do the
request, physical inputs and observations. Native assessment and electrical
checks pass at the unchanged 1e-8 electrical limit. Application source is
`5eff8a3c44128743941af34d71a11968b0205a06`; Boundary Lab is pinned to
`8cb166226e412877d3f71f2845918e479b97aa85`.

## Reproduce the retained comparison

Install NumPy and meshio and keep the adjacent `annular-fixed-quadrature`
evidence directory. From the repository root:

```sh
python validation/evidence/annular-isolated-front/reproduce.py
```

The portable script verifies complete archives/member inventories, project and
mesh hashes, unchanged physical inputs/request/runtime, and parent derivation.
It independently checks both front meshes' physical volume tags, positive
volumes, face incidence, boundary equality, tetrahedron counts and volume
agreement. Electrical evidence is bound to the archived comparison and exact
project/evaluation hashes. It then recomputes the complex errors and checks the
recorded values. This reproduction passes; the acoustic field screen still fails.

The archive includes preparation failures, successful meshes, raw native arrays,
logs and checks. The original parent compilation is retained separately under
`parent-input/compilation.json`, with an explicit derivation record. This manual
diagnostic is not a compiled search candidate or a recovery bundle. Original
path-bound native/electrical verification is retained evidence; portable mode
does not rerun it or the solver. No physical, commercial-source or print
qualification follows from these results.
