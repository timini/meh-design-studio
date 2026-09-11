# Commercial shape sensitivity to the provisional HF circuit

The irregular trial 2 remains ahead of the seed in each fixed-DSP sensitivity
comparison where both designs satisfy the acoustic handover condition. Neither
shape reaches the 6 dB response target. A hypothetical 10% increase in HF dry
moving mass makes both fail mid-channel dominance at 2 kHz with their fixed DSP.

These are **synthetic one-at-a-time probes**, not manufacturer tolerances,
measured part variation, statistical confidence bounds or source qualification.
The study keeps the 4 mm native acoustic meshes, which remain unqualified in the
upper band. It does not establish physical robustness of either design.

## Controlled calculation

The original public FaitalPRO mid circuits remain unchanged. Six HF circuit
parameters—Re, Le, Bl, dry Mmd, Cms and Rms—are each multiplied by 0.9 or 1.1,
one at a time. The nominal case is included, giving 13 cases on each of two
completed native geometries. The same perturbation applies to both shapes.
Moving-boundary areas, outlet transform area, medium, geometry and frequency
sampling remain fixed. Each shape retains its original selected DSP; no gain,
phase, filter or source fitting occurs.

The [grouped circuit reconstruction](circuit-reanalysis.md#symmetric-driver-groups)
uses all mutual velocity/current terms and mesh-verified physical coil counts.
It recomputes the circuit and mixes the retained native pressure bases. The
nominal reconstruction reproduces both original scores within `1e-8` and pressure
bases within the declared `1e-10` relative limit. The maximum algebra residual
across all probes is `1.37e-15`. These checks verify the algebra; they do not turn
an unconverged acoustic mesh into an accurate one.

## Results with fixed DSP

| Quantity | Seed, trial 0 | Irregular shape, trial 2 |
| --- | --- | --- |
| Nominal response ripple | 14.4204 dB | 13.6641 dB |
| Ripple range among scored cases | 13.8186–14.9345 dB | 13.2598–14.2386 dB |
| Lowest sampled bank impedance among scored cases | 3.1261 Ω | 3.1265 Ω |
| HF Mmd × 1.1 | Handover rejected at 2 kHz | Handover rejected at 2 kHz |
| Cases passing the 6 dB response limit | 0 | 0 |

There are 12 jointly scored comparisons, including nominal. The irregular
shape's advantage in the combined ripple/directivity objective ranges from
0.4413 to 0.7577. Both Mmd × 1.1 cases are retained as rejected, with their derived
fields and the exact failed handover check. No replacement score is assigned
to those failures.

The study supports continuing geometry exploration rather than expecting these
small HF circuit changes alone to flatten the response. It does not identify the
physical cause of the remaining irregularities, bound omitted phase-plug or
breakup effects, or establish which DSP would work on a measured speaker.

## Evidence

[The report and archive](../validation/evidence/commercial-source-sensitivity/report.json)
retain the controls, synthetic source records, derived observation/current/velocity
bases, diagnostics, runners and handover failures. They also retain trial 2's
original native system/results and its failed 4.56% rotational check; trial 0's
native dataset remains in the linked baseline archive. Every archived member and
ZIP CRC is verified.

Native geometry and fields remain attributed to
`188a933137c3d11f9df7bb7fa35c7f188827a6e1`; circuit reanalysis uses frozen source
`7e2cc14d96d320ff5e99fd0b2046d7657882ac03`. The still-running twelve-proposal search
is separate. This study does not change its controls, winners, fields or exports.
