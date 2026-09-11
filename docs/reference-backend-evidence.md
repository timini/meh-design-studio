# Native FP64 optimisation and export evidence

A two-proposal search completed the generated-geometry, coupled FP64 solve,
scoring, winner verification and export workflow. Both five-driver candidates
pass the unchanged electrical-consistency checks at 350, 1,000, 2,000 and
3,000 Hz. This proves that the reference backend works through the design
workflow; it does not qualify the acoustic accuracy of these synthetic sources.

The diagnostic uses the small freeform four-around-one ring from the
[eccentric-port study](eccentric-mid-ports.md), not the larger user-target horn.
Each proposal is generated and meshed separately, with full independent voltage
bases, H/V cuts and 413 sphere observation points. The second proposal is an
evolutionary mutation; its worse objective correctly leaves trial 0 selected.

| Trial | Target-relative response range | Objective | Maximum circuit residual | Maximum reciprocity residual |
|---|---:|---:|---:|---:|
| 0 | 14.1547 dB | 19.4195 | 2.35e-16 | 6.58e-9 |
| 1 | 14.6278 dB | 19.9104 | 2.63e-16 | 7.91e-9 |

The electrical relative tolerance remains **1e-8**. Both cases retain positive
minimum Hermitian-admittance eigenvalues at every solved frequency. Their poor
acoustic response remains a failure to meet the target response screen. The
synthetic mid circuits present approximately 1.5 ohms in parallel; the 2-ohm
screen is explicitly disabled in this diagnostic. This is not an amplifier
selection or a design meeting the user's load requirement.

## Comparison with production precision

All six baseline mesh files have identical SHA256 hashes to the earlier FP32
run. Physical source circuits, frequency samples and observation coordinates
also match. Comparing every independently excited source across both polar cuts
and the sphere gives maximum changes of **0.008561 dB** and **0.039514 degrees**.
The largest relative complex matrix-norm change is 0.000108843. No gain, phase
or DSP correction is fitted. The declared 0.001 relative-null threshold is
applied per excitation for magnitude/phase comparisons; no samples are excluded.
The complex matrix norm retains every sample regardless of that threshold.
The FP32 run used one Julia thread and the FP64 run used two; this comparison
therefore covers those recorded solver configurations rather than isolating the
effect of precision from the thread setting.

This is precision sensitivity on identical meshes, not a mesh-convergence or
physical-measurement result. The different geometry in the
[historical freeform reference study](freeform-reference-study.md) remains a
failed reciprocity case; these passing results do not overwrite it.

The [evidence report](../validation/evidence/reference-backend/report.json)
records source `9ee5b03`, the pinned upstream runtime, both native trials, exact
runners, electrical checks, precision comparison and verified export. Three
archives passed SHA256 and ZIP CRC checks. The subsequent validation-CLI routing
fix is separately identified as `cd0191a` and checked with focused tests; it
does not change the native runner used here. The initial fixture plan omitted
the low-crossover frequency and was rejected before creating output or a
database; its input and diagnostic are retained.

The exported research bundle is verified but not print-qualified. There is no
commercial source calibration, independent frequency holdout or measured
speaker evidence in this experiment.
