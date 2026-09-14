# Annular fixed-mesh integration sensitivity

At 4 kHz, increasing boundary integration orders from 2/2 to 4/4 changes the
common-mid complex pressure by **0.117317%**. The earlier coarse/refined mesh
comparison changes it by **51.07%**. Integration-order sensitivity is therefore
small for this fixed refined mesh; the horn remains numerically unqualified.
This does not identify which mesh domain dominates the error or establish that
4/4 integration itself has converged.

## Controlled experiment

Two new FP64 `coupled_reference` evaluations use the same archived refined
project, meshes, circuits, source basis and observers. The baseline uses the
exact historical request (effective regular/singular orders 2/2); the second
uses explicit fixed 4/4 integration. Native runtime identities match between
these new evaluations, and every array in their domain archives is identical.
The historical baseline is reproduced within 2e-13 relative pressure error.

| Quantity | Relative change, 2/2 → 4/4 |
| --- | ---: |
| Diaphragm velocity basis | 0.00133703% |
| Voice-coil current basis | 0.00019610% |
| Horizontal pressure basis | 0.11433227% |
| Vertical pressure basis | 0.12003065% |
| Common-mid pressure, combined H/V | 0.11731705% |

Each change is the complex L2 difference divided by the baseline L2 norm.
The common bank sums the two mid-pair voltage-basis rows once, retaining
induced throat motion; symmetry multiplicity is not applied again.
Both new native assessments were verified in their original run directories,
and both electrical checks pass the unchanged 1e-8 limit. The original failed
2% mesh/rotation checks are preserved. One frequency and two integration orders
do not qualify full-band acoustics, source accuracy or a printed speaker.

Application source: `084547174cbb4450ec52e9876c1064ba14c31c9d`.
Boundary Lab source: `8cb166226e412877d3f71f2845918e479b97aa85`.
Project SHA-256: `1ee99b3781654e6c7d1e1b7378e87f842404ef5b9a3849b27fb006402be962fc`.
Native runs use Python 3.11, Julia 1.12.6 and four Julia threads.
Complete runtime identities, raw complex arrays, requests, project/meshes,
logs, native assessments and comparison script are retained in `evidence.zip`.
`report.json` records the archive hash and every member hash; original native
path metadata is retained unchanged.

## Portable reproduction

From the repository root, with the project Python dependencies installed:

```sh
unzip validation/evidence/annular-fixed-quadrature/evidence.zip -d /tmp/meh-quadrature-reproduction
PYTHONPATH=src python /tmp/meh-quadrature-reproduction/compare.py \
  validation/evidence/annular-mid-refinement/evidence-part-000.zip \
  validation/evidence/annular-fixed-quadrature/report.json
```

Use an empty extraction directory. The historical part-000 archive is required
because it contains the historical frequency basis used here; this comparison
does not reconstruct or validate the whole historical multipart experiment.
The script checks its fixed SHA-256 and every new archive member against the
checked-in report, recomputes complex differences, checks identical runtime,
project and domain arrays, and writes `reproduced-comparison.json`.

Portable mode retains the original electrical results after hash verification;
it does **not** rerun the path-bound native assessment/electrical verifier or the
solver. Omitting the report argument instead invokes those checks in the
original run directory, whose exact paths are recorded in native metadata.
Archive CRC/hash verification and portable reproduction have passed after
extraction into a fresh temporary directory. No acceptance limit was relaxed.
