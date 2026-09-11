# Completed commercial evolutionary search

The twelve-proposal search completes geometry generation, shared-horn native
FEM/BEM evaluation, fitness-driven mutation, verified result replay and a selected
five-driver export. **No proposal meets the 6 dB response limit.** The exported
selection is retained experiment output, not an accepted build design.

| Proposal | Response residual | Maximum rotational error | Outcome |
| --- | ---: | ---: | --- |
| 0, seed | 14.4204 dB | 7.2014% | Response and rotation fail |
| 2, selected | 13.6641 dB | 4.5558% | Response and rotation fail |
| 5 | 14.3154 dB | 1.5210% | Response fails; rotation passes |
| 7 | 16.6117 dB | 5.0677% | Response and rotation fail |
| 8 | 15.8235 dB | 1.8417% | Response fails; rotation passes |
| 10 | 14.6329 dB | 8.0726% | Response and rotation fail |

All six completed proposals have fifteen frequency results from 350 to 7,500 Hz
and pass the unchanged electrical checks at `1e-8`. Their sampled four-mid
parallel-bank minimum impedance magnitudes exceed 3.12 ohms against the 2-ohm
limit. The rotational complex-error limit remains 2%; it covers pressure, source
motion and coil current. It is independent of the optimiser's response score.

The other six proposals preserve their preparation failures: 1, 4 and 9 exceed the
estimated tetrahedral budget; 3 fails tilted chamber clearance; 6 and 11 fail
freeform material containment. These proposals are
not counted as completed acoustic evaluations. The parent search continues after
each failed preparation.

Proposal 2 improves response residual by 0.7563 dB relative to the seed. Its
verified export includes all five physical drivers and has a declared build
allowance of £254.26, including £180 for drivers. These are cost assumptions, not
supplier quotations. The selection does not include passing finalist validation,
commercial basket-fit or print qualification.

## Evidence and interpretation

[The evidence index](../validation/evidence/commercial-quarter-search/report.json)
retains every search file, all failed proposals, native fields, controls, replay
validation and export verification. Each file maps to a checked archive member;
byte-identical baseline and proposal-2 data reuse the previously committed
archives. Restore the indexed paths under `runs/` and verify their SHA-256 values.

The exact application source is
`188a933137c3d11f9df7bb7fa35c7f188827a6e1`; Boundary Lab remains
`8cb166226e412877d3f71f2845918e479b97aa85`. Later meshing changes were not applied
to this running experiment or used to relabel its results.

The original isotropic rear meshes are now known to misrepresent upper-band
cylinder loading. Consequently, this ranking is exploratory even where rotation
passes. [Layered rear refinement](mesh-workloads.md#axial-refinement-inside-rear-cavities)
addresses that observed discretisation error in a separate experiment. A new
six-proposal search explores closer entries and front-chamber/port geometry on the
same nonconical profile with the refined rear mesh. Its controls and native
results are separate; it remains in progress.

The retained FaitalPRO and Peerless parameters come from public sources. This
completed numerical loop does not establish measured acoustic accuracy, maximum
output, a buildable commercial-driver assembly, or Solana-equivalent performance.
