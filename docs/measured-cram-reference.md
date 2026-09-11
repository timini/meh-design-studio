# Measured low-frequency reference and named-volume verification

The supplied Boundary Lab `2x12_CRAM` example now completes the adapter's
FP64 coupled solve and result verification. A conditional comparison against
the measurement supplied with that example **fails** its predeclared 3 dB
response-shape limit: maximum held-out error is 5.193 dB, RMS 3.211 dB.
This is not physical validation of the solver or the target MEH.

## Integration correction

The source project selects its interior volume by physical name `interior`,
with a null numeric tag. The native compiler supports this, but the adapter's
result verifier previously collected numeric tags only. It selected no source
tetrahedra and rejected the otherwise complete native result with
`FEM source requires supported same-order tetrahedra`.

The verifier now resolves physical names from the independently hashed source
mesh's `field_data`, checks volume dimension, and requires agreement if a numeric
tag is also supplied. Numeric-only groups remain supported. The existing source
hash, tetrahedron order, topology, connectivity and node checks remain in place.
The correction does not change meshing, native equations or solver tolerances.

The original failed adapter evaluation from `5c5fab1` is preserved. Reinspection
with the corrected verifier is recorded separately. A fresh end-to-end run from
frozen commit `c217b86ba76a2c10c6032091bfded518180fa5d4` passes verification,
with all 63 native result arrays exactly equal to those in the original attempt.
The two attempts have identical physical inputs and sampling controls.

## Fixed comparison protocol

The [upstream example](https://github.com/JWSound/boundary-lab/tree/8cb166226e412877d3f71f2845918e479b97aa85/examples/2x12_CRAM)
contains the project, meshes, `Measured/Onaxis.txt` and measurement notes. Their
original hashes are retained. The model's two fractional physical drivers,
x symmetry, air properties, circuits and bulk losses were unchanged. Only
observation preferences changed: no spherical sampling and 15-degree H/V steps.

Before native evaluation, the experiment declared nine frequencies from 63 to
400 Hz. Both physical drivers receive coherent 1 V RMS, reconstructed from
the complete independent 2.83 V excitation bases. A single additive level offset
is the mean measured-minus-predicted difference at **100, 125 and 160 Hz only**.
Measurement SPL is interpolated in log-frequency. There is no phase comparison,
frequency-dependent correction, source fitting, loss fitting or geometry fitting.

| Held-out frequency (Hz) | Offset-adjusted model minus measured (dB) |
| ---: | ---: |
| 63 | −0.004 |
| 80 | +1.315 |
| 200 | +5.193 |
| 250 | +4.538 |
| 315 | −3.299 |
| 400 | −1.298 |

The calibration offset is +9.907 dB. Three of six held-out samples exceed the
unchanged ±3 dB limit. The nine-point simulation is a sparse comparison; it does
not resolve all the narrow features visible in the measured response.

## Interpretation and evidence

The measurement notes describe ground-plane acquisition 10 m from the DUT front,
without voltage calibration or a timing reference. The supplied model uses a
free exterior domain with x symmetry. Ground loading and microphone height are
unmatched; exact measured build revision and source/loss calibration are also
not independently established. Those differences prevent attributing this error
to a particular numerical or physical mechanism. Even a passing shape screen
would not qualify absolute SPL, phase, the commercial HF model or our wide-mid
horn. Matching the physical reference conditions is still required.

The [evidence report](../validation/evidence/measured-cram-reference/report.json)
and its archive preserve both native attempts, original source files, controls,
comparison plot, reinspection, runners, hashes and upstream licence. The original
failed evaluation remains failed. Local verification passed 758 tests, with
three platform-dependent skips and 26 CAD tests deselected; the meaningful code
increment received one bounded review with no material findings.
