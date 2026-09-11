# Coarse screening comparison

The tested cheaper mesh pipeline does **not** reliably reproduce the retained
fine-mesh results. It reverses the ordering of two candidates and fails the
predeclared complex-field agreement limit. It is not enabled as an optimisation
screen on the strength of this study.

The two geometries are candidates 0 and 2 from the
[quarter-turn vocal search](quarter-turn-vocal-search.md). Their source positions,
circuits, physical dimensions, 15 frequencies and 20 m observation coordinates
are unchanged. Interior mesh targets increase from 8 to 16 mm and exterior
targets from 10 to 20 mm. The actual coarse models contain 294,226 and 462,922
tetrahedra, with 4,478 and 4,602 final exterior triangles. Both finish all native
frequencies within the declared 500,000-tetrahedron/5,000-triangle workload cap.

| Candidate | Fine ripple | Coarse ripple | Fine coverage error | Coarse coverage error | Fine acoustic objective | Coarse acoustic objective |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 14.4678 dB | 14.7365 dB | 7.0929 dB | 7.0889 dB | 18.0142 | 18.2810 |
| 2 | 14.6227 dB | 15.9434 dB | 6.0566 dB | 6.3144 dB | 17.6510 | 19.1006 |

Lower acoustic objective is better. Candidate 2 wins the fine comparison;
candidate 0 wins the coarse comparison. Candidate 0's three score differences
meet the declared 0.5 dB limit, but candidate 2's ripple and objective differences
are 1.3207 and 1.4496 dB and fail it.

The comparison also checks every common observation/transducer quantity at each
frequency and excitation, retaining complex phase. It does not compare field
values at different mesh nodes. The maximum relative L2 differences are 176.12%
and 163.10%, both above the declared 10% limit; both maxima occur at 7,500 Hz for
HF excitation. Similar scalar scores therefore cannot establish field agreement.
Accumulation uses FP64 while the original native arrays remain complex64.

## Provenance and limits

The [report and archive inventory](../validation/evidence/coarse-screening/report.json)
preserve both complete native runs, their inputs, controls, raw fields, scores,
comparison runner and hashes. The fine reference remains in the separately
SHA-verified quarter-turn search archives. Both scores were recomputed from
verified fields; the fine search's ancestral replay and file identities were
checked before and after archiving.

The original preparation attempt failed before native execution because a
diagnostic tried to divide dictionaries of material volumes. That failed attempt
is retained. The corrected runner compares every material part and air volume
within the original 1e-6 tolerance and verifies identical source positions.

Fine results use application source `ab6714f`; coarse results use
`852a5a33af9617ac3a40f9956ca12f744e3d0ba8`, including the later curved-mouth
preservation fix. Both use pinned Boundary Lab
`8cb166226e412877d3f71f2845918e479b97aa85`. This is a comparison of the current
screening pipeline with retained reference results; it does not isolate mesh
size from every intervening preparation change. The larger field discrepancies
cannot be attributed solely to mesh size from this evidence.

Two retrospectively selected candidates would not establish general ranking
reliability even if they agreed. These runs use the original synthetic HF source,
and neither mesh is an independent physical reference. No acoustic, electrical,
manufacturing or commercial-driver qualification follows from this comparison.
The response, ranking and field limits have not been relaxed.
